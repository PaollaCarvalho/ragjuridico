# src/vector_store.py
from pinecone import Pinecone, ServerlessSpec
from typing import List, Dict

class PineconeService:
    """Gerencia a conexão e as operações com o Pinecone."""
    def __init__(self, api_key: str, index_name: str, dimension: int, cloud: str, region: str):
        if not api_key:
            raise ValueError("API Key do Pinecone não fornecida.")
        
        self.pc = Pinecone(api_key=api_key)
        self.index_name = index_name
        self.dimension = dimension
        self.cloud = cloud
        self.region = region
        self.index = self._create_or_connect_index()

    def _create_or_connect_index(self):
        if self.index_name not in self.pc.list_indexes().names():
            print(f"Criando novo index: '{self.index_name}' com dimensão {self.dimension}...")
            self.pc.create_index(
                name=self.index_name,
                dimension=self.dimension,
                metric="cosine",
                spec=ServerlessSpec(cloud=self.cloud, region=self.region)
            )
            print("Index criado com sucesso!")
        else:
            print(f"Conectando ao index existente: '{self.index_name}'")
        
        return self.pc.Index(self.index_name)

    def upsert(self, vectors: List[Dict]):
        """Insere ou atualiza vetores no index."""
        if not vectors:
            print("Nenhum vetor para enviar.")
            return
        print(f"Enviando {len(vectors)} vetores para o index '{self.index_name}'...")
        self.index.upsert(vectors=vectors, batch_size=100)

    '''def query(self, vector: List[float], top_k: int, filter_dict: Dict = None) -> List[Dict]:
        """Consulta o index, permitindo filtros."""
        query_params = {
            "vector": vector,
            "top_k": top_k,
            "include_metadata": True
        }
        if filter_dict:
            query_params["filter"] = filter_dict
        
        try:
            results = self.index.query(**query_params)
            return results.get('matches', [])
        except Exception as e:
            print(f"Erro ao consultar o Pinecone: {e}")
            return []

    def get_stats(self):
        """Retorna as estatísticas do index."""
        return self.index.describe_index_stats()
'''