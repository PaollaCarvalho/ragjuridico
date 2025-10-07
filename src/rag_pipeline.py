# src/rag_pipeline.py
import os
import glob
import unidecode
import torch
from sentence_transformers import SentenceTransformer, CrossEncoder
from typing import List, Dict

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

        # 1. Carregar modelos
        print("Carregando modelos de embedding e re-ranking...")
        self.embedding_model = SentenceTransformer(config.EMBEDDING_MODEL, device=self.device)
        self.reranker_model = CrossEncoder(config.RERANKER_MODEL)
        
        # Garante que a dimensão no config está correta
        if config.EMBEDDING_DIMENSION != self.embedding_model.get_sentence_embedding_dimension():
             raise ValueError("A dimensão do embedding no config.py não corresponde à dimensão real do modelo.")

        # 2. Inicializar serviços
        self.extractor = PDFExtractor()
        self.chunker = SemanticChunker(config.SPACY_MODEL, config.CHUNK_SIZE)
        self.vector_store = PineconeService(
            api_key=config.PINECONE_API_KEY,
            index_name=config.PINECONE_INDEX_NAME,
            dimension=config.EMBEDDING_DIMENSION,
            cloud=config.PINECONE_CLOUD,
            region=config.PINECONE_REGION
        )
        self.llm_handler = OpenAIHandler(api_key=config.OPENAI_API_KEY, model=config.LLM_MODEL)
        print("Pipeline inicializado com sucesso.")

    def index_directory(self, directory_path: str):
        print(f"\n--- INICIANDO ETAPA DE INDEXAÇÃO DA PASTA '{directory_path}' ---")
        pdf_files = glob.glob(os.path.join(directory_path, "*.pdf"))

        if not pdf_files:
            print(f"Nenhum arquivo PDF encontrado em '{directory_path}'.")
            return

        for pdf_path in pdf_files:
            file_name = os.path.basename(pdf_path)
            print(f"\n[INDEXANDO] Processando arquivo: '{file_name}'")
            
            text = self.extractor.extract(pdf_path)
            if not text:
                continue

            chunks = self.chunker.chunk(text)
            if not chunks:
                continue
            print(f"Texto dividido em {len(chunks)} chunks.")
            
            print("Gerando embeddings...")
            embeddings = self.embedding_model.encode(chunks, show_progress_bar=True, device=self.device)
            
            vectors_to_upsert = []
            sanitized_name = unidecode.unidecode(file_name)
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                vector_id = f"doc_{sanitized_name}_chunk_{i}"
                vectors_to_upsert.append({
                    "id": vector_id,
                    "values": embedding.tolist(),
                    "metadata": {"texto": chunk, "arquivo_origem": file_name}
                })
            
            self.vector_store.upsert(vectors_to_upsert)

        print("\n--- ETAPA DE INDEXAÇÃO CONCLUÍDA ---")
        print(f"Index Status: {self.vector_store.get_stats()}")

    def search_and_rerank(self, query: str, filter_metadata: Dict = None) -> List[Dict]:
        if not query:
            return []

        query_embedding = self.embedding_model.encode(query, convert_to_tensor=True).tolist()
        
        retrieved_docs = self.vector_store.query(
            vector=query_embedding,
            top_k=config.RETRIEVAL_TOP_K,
            filter_dict=filter_metadata
        )

        if not retrieved_docs:
            return []
            
        retrieved_texts = [doc['metadata']['texto'] for doc in retrieved_docs]
        reranker_pairs = [[query, text] for text in retrieved_texts]
        
        scores = self.reranker_model.predict(reranker_pairs)
        
        docs_with_scores = list(zip(retrieved_docs, scores))
        reranked_docs = sorted(docs_with_scores, key=lambda x: x[1], reverse=True)
        
        final_results = []
        for doc, score in reranked_docs[:config.RERANKER_TOP_K]:
            final_results.append({
                'texto': doc['metadata']['texto'],
                'score_reranker': float(score),
                'id': doc['id'],
                'arquivo_origem': doc['metadata'].get('arquivo_origem', 'N/A')
            })
        return final_results

    def answer(self, query: str, filter_metadata: Dict = None) -> str:
        print("Buscando e re-ranqueando documentos relevantes...")
        context = self.search_and_rerank(query, filter_metadata)
        
        print("Enviando contexto para o LLM gerar a resposta final...")
        return self.llm_handler.generate_response(query, context), context