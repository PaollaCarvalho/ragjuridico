from fastapi import FastAPI, HTTPException, Query
from database.models import Documento, EntidadeEmpresa, PrtEnvolvida, CpfCnpj 
from database.config_conexao import DB_CONFIG, conectar_banco, fechar_conexao, executar_query
from regex.main_extrc import processar_pdf
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Optional
from pydantic import BaseModel
from datetime import date, datetime
import os
import uvicorn
from services.db import buscar_documentos_mysql, agrupar_documentos
from services.fuzzy import calcular_score_fuzzy, extrair_termos_busca
from src.rag_pipeline import RAGPipeline

app = FastAPI()

class Envolvido(BaseModel):
    empresa: str
    representante: str

class CPF_CNPJ(BaseModel):
    cpf: Optional[str] = None
    cnpj: Optional[str] = None

class Documento(BaseModel):
    id_doc: int
    nome_arquivo: str
    tipo_doc: str
    data_assinatura: Optional[date] = None
    envolvidos: List[Envolvido]
    cpf_cnpj: List[CPF_CNPJ]
    score_relevancia: Optional[float] = None

class BuscaResponse(BaseModel):
    total: int
    documentos: List[Documento]
    tempo_busca: float
    

# CORS (permite frontend acessar a API)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Em produção, especifique os domínios
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# ENDPOINTS
# ============================================================================

@app.get("/")
def root():
    """Endpoint raiz - informações da API"""
    return {
        "nome": "BIOPARK API - Documentos Jurídicos",
        "versao": "1.0.0",
        "status": "online",
        "endpoints": [
            "/buscar - Busca inteligente de documentos",
            "/documento/{id} - Detalhes de um documento específico",
            "/stats - Estatísticas do banco"
        ]
    }

@app.get("/buscar", response_model=BuscaResponse)
def buscar(
    q: str = Query(..., description="Termo de busca (nome, CPF, CNPJ, empresa)"),
    tipo: Optional[str] = Query(None, description="Filtro por tipo de documento"),
    data_inicio: Optional[date] = Query(None, description="Data início (YYYY-MM-DD)"),
    data_fim: Optional[date] = Query(None, description="Data fim (YYYY-MM-DD)"),
    limite: int = Query(20, ge=1, le=100, description="Número máximo de resultados")
):
    """
    Busca inteligente de documentos.
    
    Suporta busca por:
    - Nome de empresa (parcial, fuzzy)
    - Nome de representante
    - CPF (com ou sem formatação)
    - CNPJ (com ou sem formatação)
    - Múltiplas palavras-chave
    
    Exemplo: /buscar?q=João Silva 3G
    """
    import time
    inicio = time.time()
    
    # 1. Extrai termos de busca
    termos = extrair_termos_busca(q)
    
    if not termos:
        return BuscaResponse(
            total=0,
            documentos=[],
            tempo_busca=round(time.time() - inicio, 3)
        )
    
    # 2. Busca no MySQL (palavras-chave)
    resultados_mysql = buscar_documentos_mysql(termos, tipo, data_inicio, data_fim)
    
    # 3. Agrupa por documento
    documentos = agrupar_documentos(resultados_mysql)
    
    # 4. Calcula score fuzzy para cada documento
    for doc in documentos:
        # Cria dict temporário para calcular score
        temp_dict = {
            'empresa_assoc': doc['envolvidos'][0]['empresa'] if doc['envolvidos'] else '',
            'titular': doc['envolvidos'][0]['representante'] if doc['envolvidos'] else '',
            'CPF': doc['cpf_cnpj'][0]['cpf'] if doc['cpf_cnpj'] and doc['cpf_cnpj'][0]['cpf'] else '',
            'CNPJ': doc['cpf_cnpj'][0]['cnpj'] if doc['cpf_cnpj'] and doc['cpf_cnpj'][0]['cnpj'] else ''
        }
        doc['score_relevancia'] = calcular_score_fuzzy(q, temp_dict)
    
    # 5. Ordena por relevância (score fuzzy)
    documentos.sort(key=lambda x: x['score_relevancia'], reverse=True)
    
    # 6. Limita resultados
    documentos = documentos[:limite]
    
    tempo_total = round(time.time() - inicio, 3)
    
    return BuscaResponse(
        total=len(documentos),
        documentos=documentos,
        tempo_busca=tempo_total
    )

@app.get("/stats")
def estatisticas():
    """Retorna estatísticas do banco de dados"""
    
    stats = {}
    
    # Total de documentos
    query_docs = "SELECT COUNT(*) as total FROM documento"
    result = executar_query(query_docs)
    stats['total_documentos'] = result[0]['total'] if result else 0
    
    # Total de empresas
    query_empresas = "SELECT COUNT(DISTINCT empresa_assoc) as total FROM prt_envolvida"
    result = executar_query(query_empresas)
    stats['total_empresas'] = result[0]['total'] if result else 0
    
    # Tipos de documento
    query_tipos = """
        SELECT tipo_doc, COUNT(*) as quantidade 
        FROM documento 
        GROUP BY tipo_doc
    """
    result = executar_query(query_tipos)
    stats['tipos_documento'] = {row['tipo_doc']: row['quantidade'] for row in result}
    
    return stats

@app.get("/health")
def health_check():
    """Verifica saúde da API e conexão com banco"""
    conexao = conectar_banco()
    
    if conexao:
        conexao.close()
        return {"status": "healthy", "database": "connected"}
    else:
        return {"status": "unhealthy", "database": "disconnected"}
    

# ============================================================================
# RAG - CACHE EM MEMÓRIA
# ============================================================================
rag_cache: Dict[int, Dict] = {}
rag_pipeline: Optional[RAGPipeline] = None


def get_rag_pipeline():
    """
    Retorna instância do RAG Pipeline.
    Cria apenas na primeira vez que for chamado (lazy loading).
    """
    global rag_pipeline
    
    if rag_pipeline is None:

        print("🤖 PRIMEIRA CHAMADA AO RAG - INICIALIZANDO RAG PIPELINE // 1-3 min")
        rag_pipeline = RAGPipeline()
        print("✅ RAG PIPELINE PRONTO ")
    return rag_pipeline


# ============================================================================
# ENDPOINTS RAG
# ============================================================================


@app.post("/rag/processar/{id_doc}")
async def processar_documento_rag(id_doc: int):
    """
    Processa um documento específico para uso com RAG.
    Indexa apenas esse documento no Pinecone.
    
    Retorna: Status de processamento
    """
    try:
        # 1. Busca documento no banco
        query = """
            SELECT id_doc, nm_arquivo, caminho_arquivo 
            FROM documento 
            WHERE id_doc = %s
        """
        docs = executar_query(query, (id_doc,))
        
        if not docs:
            raise HTTPException(404, "Documento não encontrado")
        
        doc = docs[0]
        caminho_pdf = doc['caminho_arquivo']
        
        # Verifica se arquivo existe
        if not os.path.exists(caminho_pdf):
            raise HTTPException(404, f"PDF não encontrado: {caminho_pdf}")
        
        print(f"📄 Processando documento: {doc['nm_arquivo']}")
        
        # 2. Verifica cache
        if id_doc in rag_cache:
            print(f"✅ Documento já processado (cache)")
            return {
                "status": "ja_processado",
                "documento": doc['nm_arquivo'],
                "chunks": len(rag_cache[id_doc]['chunks'])
            }   
        
        pipeline = get_rag_pipeline()

        document_id = f"doc_{id_doc}"
        num_chunks = pipeline.index_doc(caminho_pdf, document_id)

        rag_cache[id_doc] = {
            "arquivo": doc['nm_arquivo'],
            "caminho": caminho_pdf,
            "document_id": document_id,
            "chunks": num_chunks,
            "processado_em": datetime.now()
        }

        return {
            "status": "processado",
            "documento": doc['nm_arquivo'],
            "id_doc": id_doc,
            "chunks": num_chunks,
        }
    
    except Exception as e:
        print(f"❌ Erro ao processar documento {id_doc}: {e}")
        raise HTTPException(500, f"Erro ao processar: {str(e)}")


@app.post("/rag/perguntar")
async def perguntar_rag(
    id_doc: int,
    pergunta: str
):
    """
    Faz pergunta ao RAG sobre documento específico.
    
    Payload:
    {
        "id_doc": 1,
        "pergunta": "Qual o valor do contrato?"
    }
    """
    try:
        # 1. Verifica se documento foi processado
        if id_doc not in rag_cache:
            # Processa automaticamente se necessário
            result = await processar_documento_rag(id_doc)
            
            if result['status'] == 'erro':
                raise HTTPException(500, "Erro ao processar documento")
        
        doc_info = rag_cache[id_doc]
        document_id = doc_info['document_id']

        pipeline = get_rag_pipeline()
        
        print(f"💬 Pergunta: '{pergunta}' para documento: {document_id}")
        
        # 2. Cria filtro Pinecone para buscar APENAS nesse documento
        filtro_pinecone = {"arquivo_origem": {"$eq": document_id}}
        
        # 3. Chama RAG
        resposta, contexto = rag_pipeline.answer(pergunta, filter_metadata=filtro_pinecone)
        
        print(f"✅ Resposta gerada")
        
        return {
            "resposta": resposta,
            "documento": doc_info['arquivo'],
            "id_doc": id_doc,
            "contexto": contexto[:3]  # Top 3
        }
        
    except Exception as e:
        print(f"❌ Erro ao responder: {e}")
        raise HTTPException(500, f"Erro ao gerar resposta: {str(e)}")
    
@app.get("/rag/status")
async def status_rag():
    """Status do sistema RAG"""
    
    return {
        "rag_carregado": rag_pipeline is not None,
        "documentos_em_cache": len(rag_cache),
        "cache": [
            {
                "id_doc": id_doc,
                "arquivo": info["arquivo"],
                "chunks": info["chunks"],
                "processado_em": info["processado_em"].isoformat()
            }
            for id_doc, info in rag_cache.items()
        ]
    }


# EXECUTAR

if __name__ == "__main__":
    host = os.getenv("HOST")
    port = os.getenv("PORT")
    uvicorn.run(app, host=host, port=port, reload=True)