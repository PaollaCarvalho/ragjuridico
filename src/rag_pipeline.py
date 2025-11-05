# src/rag_pipeline.py
import os
import torch
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Tuple

# Importa as classes dos outros módulos
from src.document_processing import PDFExtractor, SemanticChunker
from src.vector_store import PineconeService
from src.llm_handler import OpenAIHandler
import src.config as config

class RAGPipeline:
    def __init__(self):
        print("--- INICIANDO PIPELINE DE RAG JURÍDICO ---")
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        print(f"Dispositivo detectado: {self.device}")

        print(f"Modelo: {config.EMBEDDING_MODEL}")
        self.embedding_model = SentenceTransformer(config.EMBEDDING_MODEL, device=self.device)
        ###self.reranker_model = CrossEncoder(config.RERANKER_MODEL)

        #Serviços
        self.extractor = PDFExtractor()
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
        
        print("Pipeline inicializado com sucesso.")

    def index_doc(self, pdf_path: str, document_id: str) -> int:
        """
        Indexa um único arquivo PDF no Pinecone.
        Substitui index_directory() para processamento sob demanda.
        """
        print(f"Indexando arquivo: {pdf_path}")
        
        # Extrai texto e divide em chunks
        text = self.extractor.extract(pdf_path)

        chunks = self.chunker.chunk(text)
        if  chunks:
            print(f"Texto dividido em {len(chunks)} chunks.")
        
        # Gera embeddings
        embeddings = self.embedding_model.encode(chunks, show_progress_bar=True, device=self.device, batch_size=32)
           
        vectors_to_upsert = [{
            "id": f"{document_id}_chunk_{i}",
            "values": embedding.tolist(),
            "metadata": {"texto": chunk, "arquivo_origem": os.path.basename(pdf_path),
                        "document_id": document_id, "chunk_index": i, "num_caracteres": len(chunk)}
        } for i, (chunk, embedding) in enumerate(zip(chunks, embeddings))]

        self.vector_store.upsert(vectors_to_upsert)
        print("\n[4/4] Salvos no Pinecone...")
        
        return len(text)
    
    
    def search(self, query: str, document_id: str = None, top_k: int = 5) -> List[Dict]:

        query_embedding = self.embedding_model.encode(query, convert_to_tensor=True, device=self.device).tolist()

        filter_dict = None
        filter_dict = {"document_id": {"$eq": document_id}}
        
        results = self.vector_store.query(
            vector=query_embedding,
            top_k=config.TOP_K,
            filter_dict=filter_dict
        )

        if not results:
            return []
        print('Sem resultados')
            
        contexto = []
        for idx, doc in enumerate(results, 1):
            metadata = doc.get('metadata', {})
            score = doc.get('score', 0)
            
            contexto.append({
                'texto': metadata.get('texto', ''),
                'score': float(score),
                'arquivo_origem': metadata.get('arquivo_origem', 'N/A'),
                'chunk_index': metadata.get('chunk_index', 0),
                'rank': idx
            })
            
            print(f"   [{idx}] Score: {score:.4f} | Chunk {metadata.get('chunk_index', '?')}")
        return contexto


    def answer(self, query: str, document_id: str = None) -> Tuple[str, List[Dict]]:
            """
            Gera resposta para a pergunta usando RAG.
            
            Fluxo:
            1. Busca chunks relevantes (retrieval)
            2. Passa contexto + pergunta para LLM (generation)
            3. Retorna resposta + contexto usado
            
            Args:
                query: Pergunta do usuário
                document_id: ID do documento específico (opcional)
            
            Returns:
                Tuple (resposta_gerada, contexto_usado)
            """
            print(f"GERANDO RESPOSTA")
            
            if document_id:
                print(f"Documento: {document_id}")
            
            # 1. Busca contexto relevante
            context = self.search(query, document_id, top_k=5)
            
            if not context:
                resposta = "Desculpe, não encontrei informações no documento sobre sua pergunta."
                return resposta, []
            # RESPOSTA LLM 
            resposta = self.llm_handler.generate_response(query, context)
            
            return resposta
