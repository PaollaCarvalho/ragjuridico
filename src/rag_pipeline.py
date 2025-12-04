# src/rag_pipeline.py
import os
import io
import torch
import fitz  # PyMuPDF
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Tuple, Optional

# Importa as classes dos outros módulos
from src.document_processing import SemanticChunker
from src.vector_store import PineconeService
from src.llm_handler import OpenAIHandler
import src.config as config

class RAGPipeline:
    def __init__(self):
        print("--- INICIANDO PIPELINE DE RAG JURÍDICO (Redis) ---")
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        print(f"Dispositivo detectado: {self.device}")

        print(f"Modelo: {config.EMBEDDING_MODEL}")
        self.embedding_model = SentenceTransformer(config.EMBEDDING_MODEL, device=self.device)

        # Serviços
        self.chunker = SemanticChunker(config.SPACY_MODEL, config.CHUNK_SIZE)
        print("🔗 Conectando ao Pinecone e LLM Handler")
        self.vector_store = PineconeService(
            api_key=config.PINECONE_API_KEY,
            index_name=config.PINECONE_INDEX_NAME,
            dimension=config.EMBEDDING_DIMENSION,
            cloud=config.PINECONE_CLOUD,
            region=config.PINECONE_REGION
        )
        self.llm_handler = OpenAIHandler(api_key=config.OPENAI_API_KEY, model=config.LLM_MODEL)
        
        print("✅ Pipeline inicializado com sucesso.")

    def extrair_texto_pdf_bytes(self, pdf_bytes: bytes) -> str:
        """
        Extrai texto de PDF diretamente dos bytes (sem arquivo no disco)
        
        Args:
            pdf_bytes: Bytes do arquivo PDF
            
        Returns:
            Texto extraído
        """
        try:
            # Abre PDF direto da memória
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            
            # Extrai texto de todas as páginas
            full_text = "".join([page.get_text() for page in doc])
            
            doc.close()
            return full_text
            
        except Exception as e:
            print(f"❌ Erro ao extrair texto do PDF: {e}")
            return ""

    def index_doc_from_bytes(self, pdf_bytes: bytes, document_id: str, nome_arquivo: str = None) -> int:
        """
        Indexa um PDF diretamente dos bytes (SEM salvar no disco)
        
        Args:
            pdf_bytes: Bytes do PDF
            document_id: ID único do documento (ex: "doc_123")
            nome_arquivo: Nome original do arquivo (opcional)
            
        Returns:
            Número de chunks criados
        """
        print(f"📄 Indexando documento: {nome_arquivo or document_id}")
        
        # 1. Extrai texto dos bytes
        text = self.extrair_texto_pdf_bytes(pdf_bytes)
        
        if not text:
            print("⚠️ Nenhum texto extraído do PDF")
            return 0

        # 2. Divide em chunks semânticos
        chunks = self.chunker.chunk(text)
        
        if not chunks:
            print("⚠️ Nenhum chunk criado")
            return 0
            
        print(f"📑 Texto dividido em {len(chunks)} chunks")
        
        # 3. Gera embeddings
        print(f"🔢 Gerando embeddings...")
        embeddings = self.embedding_model.encode(
            chunks, 
            show_progress_bar=True, 
            device=self.device, 
            batch_size=32
        )
        
        # 4. Prepara vetores para Pinecone
        vectors_to_upsert = []
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            vectors_to_upsert.append({
                "id": f"{document_id}_chunk_{i}",
                "values": embedding.tolist(),
                "metadata": {
                    "texto": chunk,
                    "arquivo_origem": nome_arquivo or document_id,
                    "document_id": document_id,
                    "chunk_index": i,
                    "num_caracteres": len(chunk)
                }
            })

        # 5. Salva no Pinecone
        print(f"☁️ Enviando {len(vectors_to_upsert)} vetores para Pinecone...")
        self.vector_store.upsert(vectors_to_upsert)
        print("✅ Documento indexado com sucesso!")
        
        return len(chunks)
    
    def index_doc_from_redis(self, redis_service, doc_id: int) -> int:
        """
        Indexa documento diretamente do Redis
        
        Args:
            redis_service: Instância do RedisService
            doc_id: ID do documento no banco de dados
            
        Returns:
            Número de chunks criados
        """
        # 1. Busca PDF no Redis
        pdf_bytes = redis_service.obter_pdf(doc_id)
        
        if not pdf_bytes:
            raise ValueError(f"PDF {doc_id} não encontrado no Redis")
        
        # 2. Busca metadados
        metadados = redis_service.obter_metadados(doc_id)
        nome_arquivo = metadados.get('nome_arquivo') if metadados else f'doc_{doc_id}.pdf'
        
        # 3. Indexa
        document_id = f"doc_{doc_id}"
        return self.index_doc_from_bytes(pdf_bytes, document_id, nome_arquivo)

    # Mantém compatibilidade com arquivos no disco (para testes)
    def index_doc(self, pdf_path: str, document_id: str) -> int:
        """
        MÉTODO LEGADO: Indexa PDF de um arquivo no disco
        Use index_doc_from_redis() ou index_doc_from_bytes() para produção
        """
        print(f"⚠️ Usando método legado: indexando de arquivo no disco")
        
        with open(pdf_path, 'rb') as f:
            pdf_bytes = f.read()
        
        nome_arquivo = os.path.basename(pdf_path)
        return self.index_doc_from_bytes(pdf_bytes, document_id, nome_arquivo)
    
    def search(self, query: str, document_id: str = None, filter_metadata: Dict = None, top_k: int = 5) -> List[Dict]:
        """
        Busca chunks relevantes no Pinecone.
        Suporta filtro por ID antigo ou metadados customizados.
        """
        query_embedding = self.embedding_model.encode(query, convert_to_tensor=True, device=self.device).tolist()

        # Define o filtro: Prioridade para filter_metadata (do app.py), depois tenta document_id
        final_filter = None
        
        if filter_metadata:
            final_filter = filter_metadata
        elif document_id:
            final_filter = {"document_id": {"$eq": document_id}}
        
        print(f"🔍 Buscando no Pinecone. Filtro: {final_filter} | Top K: {top_k}")

        results = self.vector_store.query(
            vector=query_embedding,
            top_k=top_k,
            filter_dict=final_filter
        )

        if not results:
            print('⚠️ Sem resultados encontrados no Pinecone.')
            return []
            
        contexto = []
        for idx, doc in enumerate(results, 1):
            metadata = doc.get('metadata', {})
            score = doc.get('score', 0)
            
            contexto.append({
                'texto': metadata.get('texto', ''),
                'score': float(score),
                'arquivo_origem': metadata.get('arquivo_origem', 'N/A'),
                'document_id': metadata.get('document_id', 'N/A'), # Importante para debug
                'chunk_index': metadata.get('chunk_index', 0),
                'rank': idx,
                'metadata': metadata # Retorna metadados completos se necessário
            })
            
        return contexto
    
    def answer(self, query: str, document_id: str = None, filter_metadata: Dict = None, top_k: int = 5) -> Tuple[str, List[Dict]]:
        """
        Gera resposta para a pergunta usando RAG.
        Aceita filtros avançados e top_k variável.
        """
        print(f"🤖 GERANDO RESPOSTA | Pergunta: {query}")
        
        # 1. Busca contexto relevante passando os novos parâmetros
        context = self.search(query, document_id, filter_metadata=filter_metadata, top_k=top_k)
        
        if not context:
            resposta = "Desculpe, não encontrei informações suficientes nos documentos indexados para responder à sua pergunta."
            return resposta, []
            
        # 2. Gera resposta via LLM
        resposta = self.llm_handler.generate_response(query, context)
        
        return resposta, context
    
    def get_highlighted_chunks(self, query: str, document_id: str, top_k: int = 5) -> List[Dict]:
        """
        Retorna chunks relevantes com informações para highlight no PDF
        
        Returns:
            Lista de dicionários com:
            - texto: Texto do chunk
            - score: Score de relevância
            - chunk_index: Índice do chunk
            - pagina_inicio: Página onde o chunk começa (se disponível)
        """
        return self.search(query, document_id, top_k=top_k)