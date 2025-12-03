from fastapi import FastAPI, HTTPException, Query
from database.models import Documento, EntidadeEmpresa, PrtEnvolvida, CpfCnpj 
from database.config_conexao import DB_CONFIG, conectar_banco, fechar_conexao, executar_query
from extraction.main_extrc import processar_pdf
from database.models import Documento
from database.config_conexao import conectar_banco, executar_query
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Optional
from pydantic import BaseModel
from datetime import date, datetime
from fastapi.responses import HTMLResponse  
from fastapi.staticfiles import StaticFiles 
from fastapi import FastAPI, HTTPException, Query, Request
from services.redis_service import get_redis_service, RedisService
from driveservice.driveservice_util import service as drive_service
import os
import uvicorn
from services.db import buscar_documentos_mysql, agrupar_documentos
from services.fuzzy import calcular_score_fuzzy, extrair_termos_busca
from src.rag_pipeline import RAGPipeline

app = FastAPI()

# Pressupoẽ que seu app.py está em 'rag-juridico/'
# e seus arquivos estáticos em 'rag-juridico/static/'
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

# Caminhos para os arquivos HTML
INDEX_HTML_PATH = os.path.join(STATIC_DIR, "html", "index.html")
BUSCA_DIR = os.path.join(STATIC_DIR, "html", "busca-avancada.html")
LOGIN_HTML_PATH = os.path.join(STATIC_DIR, "html", "login.html")

# Esta linha serve a pasta "static" na URL "/static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

class Envolvido(BaseModel):
    empresa: str
    representante: str

class CPF_CNPJ(BaseModel):
    cpf: Optional[str] = None
    cnpj: Optional[str] = None
    cpf2: Optional[str] = None
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
# ENDPOINTS DE PÁGINAS HTML
# ============================================================================

@app.get("/", response_class=HTMLResponse)
async def redirect_to_login():
    """Redireciona raiz para login"""
    return HTMLResponse(
        content='<meta http-equiv="refresh" content="0; url=/login">',
        status_code=200
    )

@app.get("/login", response_class=HTMLResponse)
async def get_login():
    """Serve a página de login"""
    try:
        with open(LOGIN_HTML_PATH, "r", encoding="utf-8") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content, status_code=200)
    except FileNotFoundError:
        return HTMLResponse(
            "<h1>Erro 404: Arquivo login.html não encontrado.</h1>"
            f"<p>Verifique se ele existe em: {LOGIN_HTML_PATH}</p>",
            status_code=404
        )

@app.get("/index", response_class=HTMLResponse)
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
        with open(BUSCA_DIR, "r", encoding="utf-8") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content, status_code=200)
    except FileNotFoundError:
        return HTMLResponse(
            "<h1>Erro 404: Arquivo busca-avancada.html não encontrado.</h1>"
            f"<p>Verifique se o arquivo existe em: {BUSCA_DIR}</p>",
            status_code=404
        )

# ============================================================================
# ENDPOINTS DE API
# ============================================================================

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
# CACHE DE DOCUMENTO NO REDIS
# ============================================================================

@app.post("/documento/{id_doc}/cache")
async def cache_documento(id_doc: int):
    """
    Baixa documento do Google Drive e armazena no Redis
    Chamado quando usuário clica em "Chat RAG" ou "Detalhes"
    
    Returns:
        Status do cache
    """
    try:
        redis_service = get_redis_service()
        
        # 1. Verifica se já está em cache
        if redis_service.pdf_existe(id_doc):
            print(f"✅ Documento {id_doc} já está em cache")
            
            # Renova TTL para mais 1 hora
            redis_service.renovar_ttl(id_doc)
            
            metadados = redis_service.obter_metadados(id_doc)
            
            return {
                "status": "cached",
                "message": "Documento já estava em cache",
                "doc_id": id_doc,
                "nome_arquivo": metadados.get('nome_arquivo') if metadados else None
            }
        
        # 2. Busca informações do documento no banco
        query = """
            SELECT id_doc, nm_arquivo
            FROM documento 
            WHERE id_doc = %s
        """
        docs = executar_query(query, (id_doc,))
        
        if not docs:
            raise HTTPException(404, "Documento não encontrado no banco de dados")
        
        doc = docs[0]
        nome_arquivo = doc['nm_arquivo']
        
        # 3. BUSCA FILE_ID DO GOOGLE DRIVE
        # Assumindo que você tem uma forma de mapear id_doc -> file_id
        # Você pode adicionar uma coluna 'drive_file_id' no banco ou usar uma tabela de mapeamento
        
        # Por enquanto, vamos buscar pelo nome do arquivo
        from driveservice.config_google import folder_id
        
        query_drive = f"name='{nome_arquivo}' and '{folder_id}' in parents and trashed=false"
        results = drive_service.files().list(
            q=query_drive,
            fields="files(id, name)"
        ).execute()
        
        files = results.get('files', [])
        
        if not files:
            raise HTTPException(
                404,
                f"Arquivo {nome_arquivo} não encontrado no Google Drive"
            )
        
        file_id = files[0]['id']
        
        # 4. Baixa para Redis
        print(f"📥 Baixando {nome_arquivo} do Drive para Redis...")
        
        sucesso = redis_service.baixar_drive_para_redis(
            service=drive_service,
            file_id=file_id,
            doc_id=id_doc
        )
        
        if not sucesso:
            raise HTTPException(500, "Erro ao armazenar documento no cache")
        
        return {
            "status": "success",
            "message": "Documento baixado e armazenado em cache",
            "doc_id": id_doc,
            "nome_arquivo": nome_arquivo,
            "cache_ttl_seconds": 3600  # 1 hora
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Erro ao fazer cache do documento: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"Erro ao processar cache: {str(e)}")

@app.get("/cache/info")
async def info_cache():
    """Retorna informações sobre o cache Redis"""
    try:
        redis_service = get_redis_service()
        info = redis_service.info_cache()
        
        return {
            "redis": info,
            "rag_pinecone": {
                "documentos_indexados": len(rag_cache),
                "chunks_total": sum(doc.get('chunks', 0) for doc in rag_cache.values())
            }
        }
    except Exception as e:
        raise HTTPException(500, f"Erro ao obter info do cache: {str(e)}")


@app.delete("/cache/limpar")
async def limpar_cache():
    """Limpa cache Redis e Pinecone"""
    try:
        redis_service = get_redis_service()
        
        # Limpa Redis
        docs_redis = redis_service.limpar_todos()
        
        # Limpa cache RAG
        docs_rag = len(rag_cache)
        rag_cache.clear()
        
        return {
            "status": "success",
            "redis_documentos_removidos": docs_redis,
            "rag_cache_limpo": docs_rag
        }
    except Exception as e:
        raise HTTPException(500, f"Erro ao limpar cache: {str(e)}")


@app.delete("/cache/documento/{id_doc}")
async def limpar_cache_documento(id_doc: int):
    """Remove documento específico do cache"""
    try:
        redis_service = get_redis_service()
        
        # Remove do Redis
        removido_redis = redis_service.limpar_documento(id_doc)
        
        # Remove do cache RAG
        removido_rag = False
        if id_doc in rag_cache:
            del rag_cache[id_doc]
            removido_rag = True
        
        return {
            "status": "success",
            "id_doc": id_doc,
            "removido_redis": removido_redis,
            "removido_rag": removido_rag
        }
    except Exception as e:
        raise HTTPException(500, f"Erro ao remover documento do cache: {str(e)}")

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
    AGORA USA REDIS ao invés de disco local.
    
    Fluxo:
    1. Verifica se está em cache Redis
    2. Se não, baixa do Google Drive para Redis
    3. Processa PDF do Redis (cria arquivo temp se necessário)
    4. Indexa no Pinecone
    """
    try:
        redis_service = get_redis_service()
        
        # 1. Busca documento no banco
        query = """
            SELECT id_doc, nm_arquivo
            FROM documento 
            WHERE id_doc = %s
        """
        docs = executar_query(query, (id_doc,))
        
        if not docs:
            raise HTTPException(404, "Documento não encontrado no banco de dados")
        
        doc = docs[0]
        nome_arquivo = doc['nm_arquivo']
        
        print(f"📄 Documento solicitado: {nome_arquivo}")
        
        # 2. Verifica cache RAG (Pinecone já processado)
        if id_doc in rag_cache:
            print(f"✅ Documento já processado (Pinecone)")
            return {
                "status": "ja_processado",
                "documento": nome_arquivo,
                "chunks": rag_cache[id_doc].get('chunks', 0),
                "message": "Documento já foi indexado anteriormente"
            }
        
        # 3. Verifica se PDF está em cache Redis
        if not redis_service.pdf_existe(id_doc):
            print(f"⚠️ PDF não está em cache, baixando do Drive...")
            
            # Chama endpoint de cache
            cache_result = await cache_documento(id_doc)
            
            if cache_result['status'] != 'success' and cache_result['status'] != 'cached':
                raise HTTPException(500, "Erro ao fazer cache do documento")
        
        # 4. Obtém PDF do Redis como arquivo temporário
        print(f"📄 Recuperando PDF do Redis...")
        caminho_temp = redis_service.obter_pdf_como_arquivo_temp(id_doc)
        
        if not caminho_temp:
            raise HTTPException(500, "Erro ao recuperar PDF do cache")
        
        # 5. PROCESSA O DOCUMENTO (EXTRAÇÃO + INDEXAÇÃO)
        print(f"🔄 Processando documento: {nome_arquivo}")
        
        try:
            pipeline = get_rag_pipeline()
            document_id = f"doc_{id_doc}"
            
            # Indexa no Pinecone
            num_chunks = pipeline.index_doc(caminho_temp, document_id)
            
            # Remove arquivo temporário
            try:
                os.remove(caminho_temp)
                print(f"🗑️ Arquivo temporário removido: {caminho_temp}")
            except:
                pass
            
        except Exception as e:
            print(f"❌ Erro ao processar PDF: {e}")
            
            # Limpa arquivo temp em caso de erro
            try:
                if caminho_temp and os.path.exists(caminho_temp):
                    os.remove(caminho_temp)
            except:
                pass
            
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "Erro ao processar PDF",
                    "documento": nome_arquivo,
                    "mensagem": f"Não foi possível extrair texto do PDF: {str(e)}"
                }
            )

        # 6. Salva no cache RAG (em memória Python)
        rag_cache[id_doc] = {
            "arquivo": nome_arquivo,
            "document_id": document_id,
            "chunks": num_chunks,
            "processado_em": datetime.now(),
            "cache_redis": True  # Flag indicando que usa Redis
        }

        return {
            "status": "processado",
            "documento": nome_arquivo,
            "id_doc": id_doc,
            "chunks": num_chunks,
            "fonte": "redis_cache"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Erro inesperado ao processar documento {id_doc}: {e}")
        import traceback
        traceback.print_exc()
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
        # Query principal do documento (SEM caminho_arquivo)
        query_doc = """
            SELECT 
                d.id_doc,
                d.nm_arquivo as nome_arquivo,
                d.tipo_doc,
                d.emissao_doc as data_assinatura
            FROM documento d
            WHERE d.id_doc = %s
        """
        
        docs = executar_query(query_doc, (id_doc,))
        
        if not docs:
            raise HTTPException(status_code=404, detail="Documento não encontrado")
        
        doc = docs[0]
        
        # Busca envolvidos
        query_envolvidos = """
            SELECT pe.empresa_assoc as empresa, pe.titular as representante
            FROM prt_envolvida pe
            INNER JOIN doc_prt_envolvida dpe ON pe.id_prt = dpe.id_prt
            WHERE dpe.id_doc = %s
        """
        envolvidos_raw = executar_query(query_envolvidos, (id_doc,))
        
        # Garante que sempre retorna um array, mesmo vazio
        envolvidos = []
        if envolvidos_raw:
            envolvidos = [
                {
                    "empresa": e.get("empresa", "N/A"),
                    "representante": e.get("representante", "N/A")
                }
                for e in envolvidos_raw
            ]
        
        # Se não encontrou nenhum envolvido, adiciona um placeholder
        if not envolvidos:
            envolvidos = [{
                "empresa": "Informação não disponível",
                "representante": "Informação não disponível"
            }]
        
        # Busca CPF/CNPJ
        query_cpf_cnpj = """
            SELECT cc.CPF as cpf, cc.CNPJ as cnpj, cc.CPF2 as cpf2, cc.CNPJ2 as cnpj2
            FROM cpf_cnpj cc
            INNER JOIN doc_pf_pj dpj ON cc.id_pjpf = dpj.id_pjpf
            WHERE dpj.id_doc = %s
        """
        cpf_cnpj_raw = executar_query(query_cpf_cnpj, (id_doc,))

        # Formatação do CPF/CNPJ para o modelo esperado
        cpf_cnpj_formatado = []
        if cpf_cnpj_raw:
            for item in cpf_cnpj_raw:
                cpf_cnpj_formatado.append({
                    "cpf": item.get("cpf"),
                    "cnpj": item.get("cnpj"),
                    "cpf2": item.get("cpf2"),
                    "cnpj2": item.get("cnpj2")
                })
        
        # Se não tem CPF/CNPJ, adiciona objeto vazio
        if not cpf_cnpj_formatado:
            cpf_cnpj_formatado = [{
                "cpf": None,
                "cnpj": None,
                "cpf2": None,
                "cnpj2": None
            }]

        # Monta resposta (SEMPRE com arrays válidos)
        return {
            "id_doc": doc["id_doc"],
            "nome_arquivo": doc["nome_arquivo"] or "Documento sem nome",
            "tipo_doc": doc["tipo_doc"] or "Tipo não especificado",
            "data_assinatura": doc["data_assinatura"].isoformat() if doc.get("data_assinatura") else None,
            "envolvidos": envolvidos,  # ✅ Sempre um array
            "cpf_cnpj": cpf_cnpj_formatado  # ✅ Sempre um array
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Erro ao buscar documento {id_doc}: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"Erro ao buscar documento: {str(e)}")
    
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

# ============================================================================
# EXECUTAR
# ============================================================================
if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host=host, port=port, reload=True)