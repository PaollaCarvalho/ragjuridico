from fastapi import FastAPI, HTTPException, Query
<<<<<<< HEAD
from database.models import Documento, EntidadeEmpresa, PrtEnvolvida, CpfCnpj 
from database.config_conexao import DB_CONFIG, conectar_banco, fechar_conexao, executar_query
from recon.main_extrc import processar_pdf
=======
from database.models import Documento
from database.config_conexao import conectar_banco, executar_query
>>>>>>> 956673175342fd5f3b4874e600070ee10c9aef7c
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Optional
from pydantic import BaseModel
from datetime import date, datetime
from fastapi.responses import HTMLResponse  
from fastapi.staticfiles import StaticFiles 
from fastapi import FastAPI, HTTPException, Query, Request
import os
import uvicorn
from services.db import buscar_documentos_mysql, agrupar_documentos
from services.fuzzy import calcular_score_fuzzy, extrair_termos_busca
from src.rag_pipeline import RAGPipeline

app = FastAPI()

# Pressupõe que seu app.py está em 'rag-juridico/'
# e seus arquivos estáticos em 'rag-juridico/static/'
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

# Caminho para o seu index.html
# ATENÇÃO: Mova seu index.html para 'static/html/index.html'
INDEX_HTML_PATH = os.path.join(STATIC_DIR, "html", "index.html")
BUSCA_DIR = os.path.join(STATIC_DIR, "html", "busca-avancada.html")

# Esta linha serve a pasta "static" na URL "/static"
# É por isso que o <link href="/static/css/style.css"> funciona
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

class Envolvido(BaseModel):
    empresa: str
    representante: str

class CPF_CNPJ(BaseModel):
    cpf: Optional[str] = None
    cnpj: Optional[str] = None
    cpf2: Optional[str] = None  # p caso com + de 1 cpf ou cnpj
    cnpj2: Optional[str] = None  

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

class PerguntaRAGRequest(BaseModel):
    id_doc: int
    pergunta: str
    

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

@app.get("/", response_class=HTMLResponse)
async def get_frontend(request: Request):
    """Serve o frontend (index.html)"""
    try:
        with open(INDEX_HTML_PATH, "r", encoding="utf-8") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content, status_code=200)

    except FileNotFoundError:
        return HTMLResponse(
            "<h1>Erro 500: Arquivo index.html não encontrado.</h1>"
            f"<p>Verifique se ele existe em: {INDEX_HTML_PATH}</p>",
            status_code=500
        )
    
@app.get("/busca-avancada", response_class=HTMLResponse)
async def get_busca_avancada():
    """Serve a página de Busca Avançada"""
    try:
        # Tenta ler o arquivo renomeado
        with open(BUSCA_DIR, "r", encoding="utf-8") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content, status_code=200)
    except FileNotFoundError:
        # Fallback caso você não tenha renomeado ou movido o arquivo ainda
        return HTMLResponse(
            "<h1>Erro 404: Arquivo busca-avancada.html não encontrado.</h1>"
            f"<p>Verifique se o arquivo existe em: {BUSCA_DIR}</p>",
            status_code=404
        )

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
    resultados_mysql = buscar_documentos_mysql(tipo, data_inicio, data_fim)
    
    # 3. Agrupa por documento
    documentos = agrupar_documentos(resultados_mysql)

    doc_unico = {}

    for doc in documentos:
        
        cpfs = [item['cpf'] for item in doc['cpf_cnpj'] if item.get('cpf')]
        cnpjs = [item['cnpj'] for item in doc['cpf_cnpj'] if item.get('cnpj')]

        identificador = cpfs[0] if cpfs else (cnpjs[0] if cnpjs else None)

        if identificador and identificador not in doc_unico:
            doc_unico[identificador] = doc

    documentos = list(doc_unico.values())
    
    # score fuzzy 
    for doc in documentos:
        todos_cpfs = " ".join([item['cpf'] for item in doc['cpf_cnpj'] if item.get('cpf')])
        todos_cnpjs = " ".join([item['cnpj'] for item in doc['cpf_cnpj'] if item.get('cnpj')])

        temp_dict = {
        'empresa_assoc': doc['envolvidos'][0]['empresa'] if doc['envolvidos'] else '',
        'titular': doc['envolvidos'][0]['representante'] if doc['envolvidos'] else '',
        'CPF': todos_cpfs,
        'CNPJ': todos_cnpjs
        }
        doc['score_relevancia'] = calcular_score_fuzzy(q, temp_dict)
    
    #  ordena por relevância (score fuzzy)
    documentos.sort(key=lambda x: x['score_relevancia'], reverse=True)
    
    # limit
    documentos = documentos[:limite]
    
    tempo_total = round(time.time() - inicio, 3)
    
    return BuscaResponse(
        total=len(documentos),
        documentos=documentos,
        tempo_busca=tempo_total
    )

@app.get("/stats")
def estatisticas():
    """Retorna estatísticas do banco de dados + RAG"""
    
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
    
<<<<<<< HEAD
    # ===== ADICIONE ESTAS LINHAS =====
=======
>>>>>>> 956673175342fd5f3b4874e600070ee10c9aef7c
    # Estatísticas RAG
    stats['rag'] = {
        "pipeline_carregado": rag_pipeline is not None,
        "documentos_processados": len(rag_cache),
        "total_chunks": sum(info.get('chunks', 0) for info in rag_cache.values())
    }
    
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
async def perguntar_rag(request: PerguntaRAGRequest):
    """
    Faz pergunta ao RAG sobre documento específico.
    
    Payload JSON:
    {
        "id_doc": 1,
        "pergunta": "Qual o valor do contrato?"
    }
    
    Returns:
        {
            "resposta": "O valor do contrato é...",
            "documento": "contrato_xyz.pdf",
            "id_doc": 1,
            "contexto": [...]
        }
    """
    try:
        # 1. Verifica se documento foi processado
        if request.id_doc not in rag_cache:
            # Processa automaticamente se necessário
            result = await processar_documento_rag(request.id_doc)
            
            if result.get('status') == 'erro':
                raise HTTPException(500, "Erro ao processar documento")
        
        doc_info = rag_cache[request.id_doc]
        document_id = doc_info['document_id']

        pipeline = get_rag_pipeline()
        
        print(f"💬 Pergunta: '{request.pergunta}' para documento: {document_id}")
        
        # 2. Cria filtro Pinecone para buscar APENAS nesse documento
        filtro_pinecone = {"arquivo_origem": {"$eq": document_id}}
        
        # 3. Chama RAG
        resposta, contexto = pipeline.answer(request.pergunta, filter_metadata=filtro_pinecone)
        
        print(f"✅ Resposta gerada: {resposta[:100]}...")
        
        return {
            "resposta": resposta,
            "documento": doc_info['arquivo'],
            "id_doc": request.id_doc,
            "contexto": contexto[:3] if contexto else []  # Top 3 chunks
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Erro ao responder: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"Erro ao gerar resposta: {str(e)}")
    
@app.post("/rag/perguntar_geral")
async def perguntar_rag_geral(
    pergunta: str = Query(..., description="Pergunta a ser feita"),
    limite_docs: int = Query(5, description="Número máximo de documentos a considerar")
):
    """
    Faz pergunta buscando em TODOS os documentos indexados.
    Útil para perguntas como "Quais contratos vencem este mês?"
    
    Query params:
        pergunta: A pergunta a ser feita
        limite_docs: Número máximo de documentos a considerar (padrão: 5)
    
    Returns:
        {
            "resposta": "...",
            "documentos_utilizados": [...],
            "total_documentos": 3
        }
    
    Exemplo:
        POST /rag/perguntar_geral?pergunta=Quais+contratos+da+3G&limite_docs=5
    """
    try:
        pipeline = get_rag_pipeline()
        
        print(f"🔍 Busca geral: '{pergunta}'")
        
        # Busca SEM filtro (todos os documentos)
        resposta, contexto = pipeline.answer(pergunta, filter_metadata=None, top_k=limite_docs*3)
        
        # Identifica quais documentos foram usados
        documentos_usados = set()
        for chunk in contexto[:limite_docs*3]:
            if 'arquivo_origem' in chunk.get('metadata', {}):
                doc_id = chunk['metadata']['arquivo_origem']
                documentos_usados.add(doc_id)
        
        # Busca informações dos documentos usados
        docs_info = []
        for doc_id in list(documentos_usados)[:limite_docs]:
            # Extrai ID numérico do formato "doc_123"
            if doc_id.startswith("doc_"):
                try:
                    id_num = int(doc_id.split("_")[1])
                    
                    # Busca info no banco
                    query = """
                        SELECT 
                            d.id_doc,
                            d.nm_arquivo as nome_arquivo,
                            d.tipo_doc,
                            d.dt_ass as data_assinatura,
                            e.empresa_assoc as empresa
                        FROM documento d
                        LEFT JOIN prt_envolvida e ON d.id_doc = e.id_doc
                        WHERE d.id_doc = %s
                        LIMIT 1
                    """
                    doc_data = executar_query(query, (id_num,))
                    
                    if doc_data:
                        doc = doc_data[0]
                        docs_info.append({
                            "id_doc": doc["id_doc"],
                            "nome_arquivo": doc["nome_arquivo"],
                            "tipo_doc": doc["tipo_doc"],
                            "data_assinatura": doc["data_assinatura"].isoformat() if doc.get("data_assinatura") else None,
                            "empresa": doc.get("empresa", "N/A")
                        })
                except Exception as e:
                    print(f"⚠️ Erro ao processar documento {doc_id}: {e}")
                    continue
        
        print(f"✅ Resposta gerada usando {len(docs_info)} documento(s)")
        
        return {
            "resposta": resposta,
            "documentos_utilizados": docs_info,
            "total_documentos": len(docs_info),
            "contextos": len(contexto)
        }
        
    except Exception as e:
        print(f"❌ Erro na busca geral: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"Erro ao processar busca geral: {str(e)}")
<<<<<<< HEAD
    
@app.get("/documento/{id_doc}")
async def buscar_documento_por_id(id_doc: int):
    """
    Busca detalhes completos de um documento específico.
    
    Args:
        id_doc: ID do documento
        
    Returns:
        Objeto Documento com todos os detalhes
    """
    try:
        # Query principal do documento
        query_doc = """
            SELECT 
                d.id_doc,
                d.nm_arquivo as nome_arquivo,
                d.tipo_doc,
                d.dt_ass as data_assinatura,
                d.caminho_arquivo
            FROM documento d
            WHERE d.id_doc = %s
        """
        
        docs = executar_query(query_doc, (id_doc,))
        
        if not docs:
            raise HTTPException(status_code=404, detail="Documento não encontrado")
        
        doc = docs[0]
        
        # Busca envolvidos
        query_envolvidos = """
            SELECT empresa_assoc as empresa, titular as representante
            FROM prt_envolvida
            WHERE id_doc = %s
        """
        envolvidos = executar_query(query_envolvidos, (id_doc,))
        
        # Busca CPF/CNPJ
        query_cpf_cnpj = """
            SELECT CPF as cpf, CNPJ as cnpj
            FROM cpf_cnpj
            WHERE id_doc = %s
        """
        cpf_cnpj = executar_query(query_cpf_cnpj, (id_doc,))
        
        # Monta resposta
        return {
            "id_doc": doc["id_doc"],
            "nome_arquivo": doc["nome_arquivo"],
            "tipo_doc": doc["tipo_doc"],
            "data_assinatura": doc["data_assinatura"].isoformat() if doc.get("data_assinatura") else None,
            "caminho_arquivo": doc.get("caminho_arquivo"),
            "envolvidos": [
                {
                    "empresa": e["empresa"],
                    "representante": e["representante"]
                }
                for e in envolvidos
            ],
            "cpf_cnpj": [
                {
                    "cpf": c.get("cpf"),
                    "cnpj": c.get("cnpj")
                }
                for c in cpf_cnpj
            ]
        }

        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Erro ao buscar documento {id_doc}: {e}")
        raise HTTPException(500, f"Erro ao buscar documento: {str(e)}")
=======
>>>>>>> 956673175342fd5f3b4874e600070ee10c9aef7c
    
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

@app.delete("/rag/cache/{id_doc}")
async def limpar_cache_documento(id_doc: int):
    """
    Remove documento do cache RAG.
    Útil para reprocessar um documento atualizado.
    """
    try:
        if id_doc in rag_cache:
            doc_info = rag_cache[id_doc]
            del rag_cache[id_doc]
            
            return {
                "status": "removido",
                "documento": doc_info.get("arquivo", "N/A"),
                "id_doc": id_doc
            }
        else:
            raise HTTPException(404, "Documento não está em cache")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Erro ao limpar cache: {str(e)}")

@app.delete("/rag/cache")
async def limpar_cache_completo():
    """
    Limpa TODO o cache RAG.
    Use com cuidado!
    """
    try:
        total = len(rag_cache)
        rag_cache.clear()
        
        return {
            "status": "cache_limpo",
            "documentos_removidos": total
        }
        
    except Exception as e:
        raise HTTPException(500, f"Erro ao limpar cache: {str(e)}")
# EXECUTAR

if __name__ == "__main__":
    host = os.getenv("HOST")
    port = os.getenv("PORT")
    uvicorn.run(app, host=host, port=port, reload=True)