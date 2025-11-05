import os
from dotenv import load_dotenv

load_dotenv()

# --- CHAVES DE API ---
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# --- CONFIGURAÇÕES DE DIRETÓRIO ---
###PDF_DIRECTORY = "rag-juridico\contratos"

# --- CONFIGURAÇÕES DO PINECONE ---
PINECONE_INDEX_NAME = "rag-juridico"
PINECONE_CLOUD = 'aws'
PINECONE_REGION = 'us-east-1'

# --- CONFIGURAÇÕES DOS MODELOS ---
EMBEDDING_MODEL = 'intfloat/multilingual-e5-large'
###RERANKER_MODEL = 'cross-encoder/ms-marco-MiniLM-L-6-v2'
LLM_MODEL = "gpt-3.5-turbo"
SPACY_MODEL = "pt_core_news_lg"

# --- CONFIGURAÇÕES DE PROCESSAMENTO ---
CHUNK_SIZE = 512 # Tamanho máximo de palavras por chunk
EMBEDDING_DIMENSION = 1024 # Dimensão do modelo 'multilingual-e5-large'

# --- CONFIGURAÇÕES DE BUSCA ---
TOP_K = 25
