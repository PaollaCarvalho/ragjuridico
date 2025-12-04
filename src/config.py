import os
from dotenv import load_dotenv

load_dotenv()

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

PDF_DIRECTORY = "rag-juridico\contratos"

PINECONE_INDEX_NAME = "rag-juridico"
PINECONE_CLOUD = 'aws'
PINECONE_REGION = 'us-east-1'

EMBEDDING_MODEL = 'intfloat/multilingual-e5-large'
RERANKER_MODEL = 'cross-encoder/ms-marco-MiniLM-L-6-v2'
LLM_MODEL = "gpt-3.5-turbo"
SPACY_MODEL = "pt_core_news_lg"

CHUNK_SIZE = 512 
EMBEDDING_DIMENSION = 1024 

RETRIEVAL_TOP_K = 25
RERANKER_TOP_K = 15