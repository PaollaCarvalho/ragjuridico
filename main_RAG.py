import fitz
import spacy
import re
import os
import glob
import unidecode
from dotenv import load_dotenv
from pinecone import Pinecone, ServerlessSpec
from sentence_transformers import SentenceTransformer, CrossEncoder
from openai import OpenAI
import torch

# --- CARREGAR VARIÁVEIS DE AMBIENTE ---
load_dotenv()
PINECONE_API_KEY2 = os.getenv("PINECONE_API_KEY2")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# --- INICIALIZAÇÃO DE CLIENTES ---
if OPENAI_API_KEY:
    client_openai = OpenAI(api_key=OPENAI_API_KEY)

if PINECONE_API_KEY2:
    pc = Pinecone(api_key=PINECONE_API_KEY2)


# --------------------------------------------------------------------------
# ETAPA 1: EXTRAÇÃO DE TEXTO DO PDF
# --------------------------------------------------------------------------
def extrair_texto_de_pdf(caminho_do_arquivo: str) -> str:
    """Extrai texto de um único arquivo PDF."""
    try:
        documento = fitz.open(caminho_do_arquivo)
        texto_completo = "".join([pagina.get_text() for pagina in documento])
        documento.close()
        return texto_completo
    except Exception as e:
        print(f"Erro ao extrair texto do PDF '{caminho_do_arquivo}': {e}")
        return ""

# --------------------------------------------------------------------------
# ETAPA 2: CHUNKING SEMÂNTICO
# --------------------------------------------------------------------------
try:
    nlp = spacy.load("pt_core_news_lg", disable=["tagger", "parser", "ner", "lemmatizer", "textcat"])
    nlp.add_pipe('sentencizer')
except OSError:
    print("Modelo 'pt_core_news_lg' não encontrado. Execute: python -m spacy download pt_core_news_lg")
    nlp = None

def chunking_semantico(texto: str, tamanho_max_chunk: int = 512) -> list[str]:
    """Divide o texto em chunks semânticos baseados em sentenças."""
    if not nlp: return []
    texto_limpo = re.sub(r'\s+', ' ', texto).strip()
    doc = nlp(texto_limpo)
    
    # Usando sentenças como base para não quebrar ideias no meio
    sentencas = [s.text.strip() for s in doc.sents]
    
    chunks = []
    chunk_atual = ""
    for sentenca in sentencas:
        # Previne chunks excessivamente grandes
        if len(chunk_atual.split()) + len(sentenca.split()) <= tamanho_max_chunk:
            chunk_atual += " " + sentenca
        else:
            if chunk_atual: # Evita adicionar chunks vazios se uma sentença for muito longa
                chunks.append(chunk_atual.strip())
            chunk_atual = sentenca
    if chunk_atual:
        chunks.append(chunk_atual.strip())
    return chunks

# --------------------------------------------------------------------------
# ETAPA 3: GERAÇÃO DE EMBEDDINGS E INDEXAÇÃO
# --------------------------------------------------------------------------
def criar_ou_conectar_index(pc_client: Pinecone, index_name: str, dimension: int):
    """Cria um novo index no Pinecone se ele não existir, ou conecta-se a um existente."""
    if index_name not in pc_client.list_indexes().names():
        print(f"Criando novo index: '{index_name}' com dimensão {dimension}...")
        pc_client.create_index(
            name=index_name,
            dimension=dimension,
            metric="cosine",
            spec=ServerlessSpec(
                cloud='aws',
                region='us-east-1'
            )
        )
        print("Index criado com sucesso!")
    else:
        print(f"Conectando ao index existente: '{index_name}'")
    
    return pc_client.Index(index_name)

# --------------------------------------------------------------------------
# ETAPA 4: BUSCA E RE-RANKING
# --------------------------------------------------------------------------
def buscar_e_reranquear(
    query: str, 
    index, 
    embedding_model, 
    reranker_model, 
    top_k_retrieve: int = 25, 
    top_k_rerank: int = 15,
    filtro_metadata: dict = None
) -> list[dict]:
    """
    Realiza a busca em duas etapas: recuperação e re-ranking.
    Permite filtrar a busca por metadados (ex: por arquivo).
    """
    if not query: return []
    
    query_embedding = embedding_model.encode(query, convert_to_tensor=True)
    
    # --- Parâmetros da Query ---
    query_params = {
        "vector": query_embedding.tolist(),
        "top_k": top_k_retrieve,
        "include_metadata": True
    }
    
    # <-- MODIFICADO: Adiciona o filtro à query se ele for fornecido
    if filtro_metadata:
        query_params["filter"] = filtro_metadata
        print(f"Executando busca com filtro: {filtro_metadata}")
    
    try:
        retrieved_docs = index.query(**query_params)
    except Exception as e:
        print(f"Erro ao consultar o Pinecone (verifique se o filtro está correto): {e}")
        return []

    retrieved_texts = [doc['metadata']['texto'] for doc in retrieved_docs['matches']]
    if not retrieved_texts:
        return []
    
    pares_para_reranker = [[query, texto] for texto in retrieved_texts]
    scores = reranker_model.predict(pares_para_reranker)
    docs_com_scores = list(zip(retrieved_docs['matches'], scores))
    docs_reranqueados = sorted(docs_com_scores, key=lambda x: x[1], reverse=True)
    
    resultados_finais = []
    for doc, score in docs_reranqueados[:top_k_rerank]:
        resultados_finais.append({
            'texto': doc['metadata']['texto'],
            'score_reranker': float(score),
            'id': doc['id'],
            'arquivo_origem': doc['metadata'].get('arquivo_origem', 'N/A') 
        })
    return resultados_finais

# --------------------------------------------------------------------------
# ETAPA 5: GERAÇÃO DE RESPOSTA COM LLM
# --------------------------------------------------------------------------
def gerar_resposta(query: str, contexto: list[dict]) -> str:
    """Gera uma resposta usando um LLM com base na query e no contexto recuperado."""
    if not contexto:
        return "Desculpe, não encontrei informações relevantes nos documentos para responder a esta pergunta."
    
    textos_contexto = "\n\n---\n\n".join([f"Trecho do documento (ID: {doc.get('id', 'N/A')}, Origem: {doc.get('arquivo_origem', 'N/A')}):\n{doc['texto']}" for doc in contexto])
    
    prompt = f"""
    Você é um assistente especializado em direito brasileiro. Sua tarefa é responder à pergunta do usuário de forma precisa, objetiva e completa, baseando-se estritamente no contexto fornecido.

    **Contexto extraído dos documentos:**
    {textos_contexto}

    **Pergunta do usuário:**
    {query}

    **Instruções:**
    1. Responda à pergunta usando apenas as informações do contexto acima.
    2. Não invente, suponha ou adicione informações externas.
    3. Se a resposta não estiver no contexto, diga claramente: "Com base nos documentos fornecidos, não há informações suficientes para responder a esta pergunta."
    4. Cite trechos relevantes do contexto para embasar sua resposta, se possível.

    **Resposta:**
    """
    
    try:
        response = client_openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Você é um assistente especializado em direito brasileiro. Sua tarefa é responder à pergunta do usuário de forma precisa, objetiva e completa, baseando-se estritamente no contexto fornecido."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=1500
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Ocorreu um erro ao chamar a API da OpenAI: {e}"


# --- EXECUÇÃO DO PIPELINE COMPLETO ---

if __name__ == "__main__":
    # --- CONFIGURAÇÕES ---
    PASTA_DE_PDFS = "contratos"
    PINECONE_INDEX_NAME = "rag-juridico"
    MODELO_EMBEDDING = 'intfloat/multilingual-e5-large'
    MODELO_RERANKER = 'cross-encoder/ms-marco-MiniLM-L-6-v2'
    
    # --- VALIDAÇÕES INICIAIS ---
    if not all([PINECONE_API_KEY2, OPENAI_API_KEY]):
        print("ERRO: Verifique se as chaves PINECONE_API_KEY e OPENAI_API_KEY estão no seu arquivo .env")
        exit()

    if not os.path.isdir(PASTA_DE_PDFS):
        print(f"ERRO: O caminho '{PASTA_DE_PDFS}' não é um diretório válido.")
        exit()

    # --- CARREGAR MODELOS (FEITO UMA SÓ VEZ) ---
    print("--- INICIANDO PIPELINE DE RAG JURÍDICO ---")
    print("Carregando modelos de embedding e re-ranking (isso pode levar um momento)...")
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    embedding_model = SentenceTransformer(MODELO_EMBEDDING, device=device)
    reranker_model = CrossEncoder(MODELO_RERANKER)
    print(f"Modelos carregados com sucesso em '{device}'.")
    
    # --- CONECTAR AO PINECONE INDEX ---
    embedding_dim = embedding_model.get_sentence_embedding_dimension()
    index = criar_ou_conectar_index(pc, PINECONE_INDEX_NAME, embedding_dim)
    
    # --- PARTE 1: INDEXAÇÃO DE TODOS OS DOCUMENTOS NA PASTA ---
    print(f"\n--- INICIANDO ETAPA DE INDEXAÇÃO DA PASTA '{PASTA_DE_PDFS}' ---")
    
    lista_de_pdfs = glob.glob(os.path.join(PASTA_DE_PDFS, "*.pdf"))

    if not lista_de_pdfs:
        print(f"Nenhum arquivo PDF encontrado em '{PASTA_DE_PDFS}'.")
        # Mesmo sem PDFs novos para indexar, o programa pode continuar para a etapa de Q&A
        # se o índice já contiver dados. Se for obrigatório indexar, use exit()
    else:
        for caminho_pdf in lista_de_pdfs:
            print(f"\n[INDEXANDO] Processando arquivo: '{os.path.basename(caminho_pdf)}'")
            
            texto_completo = extrair_texto_de_pdf(caminho_pdf)
            if not texto_completo:
                print(f"Nenhum texto extraído de '{caminho_pdf}'. Pulando para o próximo.")
                continue
                
            chunks = chunking_semantico(texto_completo)
            if not chunks:
                print(f"Nenhum chunk gerado para '{caminho_pdf}'. Pulando para o próximo.")
                continue
            
            print(f"Texto dividido em {len(chunks)} chunks.")
            
            print("Gerando embeddings para os chunks...")
            embeddings = embedding_model.encode(chunks, show_progress_bar=True, device=device)
            
            vetores_para_upsert = []
            nome_arquivo_base = os.path.basename(caminho_pdf)
            nome_arquivo_sanitizado = unidecode.unidecode(nome_arquivo_base)
            
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                vetor_id = f"doc_{nome_arquivo_sanitizado}_chunk_{i}"
                vetores_para_upsert.append({
                "id": vetor_id,
                "values": embedding.tolist(),
                # O metadata 'arquivo_origem' é crucial para a nova lógica
                "metadata": {"texto": chunk, "arquivo_origem": nome_arquivo_base}
                })
            
            print(f"Enviando {len(vetores_para_upsert)} vetores para o index...")
            index.upsert(vectors=vetores_para_upsert, batch_size=100)

        print("\n--- ETAPA DE INDEXAÇÃO CONCLUÍDA ---")
        print(f"Index Status: {index.describe_index_stats()}")

    # --------------------------------------------------------------------------
    # PARTE 2 - LOOP DE Q&A EM DUAS ETAPAS -->
    # --------------------------------------------------------------------------
    print("\n--- INICIANDO ETAPA DE PERGUNTAS E RESPOSTAS ---")

    while True:
        # --- ETAPA 1: IDENTIFICAR O DOCUMENTO ---
        print("\n=======================================================")
        print("ETAPA 1: IDENTIFICAÇÃO DO DOCUMENTO")
        print("=======================================================")
        query_documento = input("Sobre qual documento você quer perguntar? (Descreva o assunto ou nome. Digite 'sair' para terminar): ")
        
        if query_documento.lower() in ['sair', 'exit', 'quit']:
            break
        
        print(f"\nIdentificando o documento para: '{query_documento}'...")
        
        # Faz uma busca geral, pegando apenas o resultado mais relevante (top_k_rerank=1)
        # para identificar o arquivo de origem.
        contexto_doc = buscar_e_reranquear(
            query_documento, 
            index, 
            embedding_model, 
            reranker_model,
            top_k_retrieve=15, # Recupera 15
            top_k_rerank=1    # Re-ranqueia e pega só o melhor 1
        )
        
        if not contexto_doc:
            print("Desculpe, não consegui identificar um documento relevante com base nessa descrição. Vamos tentar novamente.")
            continue # Volta para a Etapa 1
            
        # Pega o nome do arquivo do melhor resultado
        documento_encontrado = contexto_doc[0]['arquivo_origem']
        print(f"\n[FOCO ATIVADO] Documento identificado: '{documento_encontrado}'")
        print(f"(Score de relevância do documento: {contexto_doc[0]['score_reranker']:.4f})")
        
        # --- ETAPA 2: PERGUNTA ESPECÍFICA DENTRO DO DOCUMENTO ---
        while True:
            print("\n-------------------------------------------------------")
            print(f"ETAPA 2: PERGUNTA SOBRE '{documento_encontrado}'")
            print("-------------------------------------------------------")
            query_especifica = input(f"Qual sua pergunta específica sobre este documento? (Digite 'voltar' para escolher outro documento): ")

            if query_especifica.lower() in ['voltar', 'back']:
                print("Entendido. Voltando para a seleção de documento...")
                break # Sai do loop interno (Etapa 2) e volta para a Etapa 1
            
            if query_especifica.lower() in ['sair', 'exit', 'quit']:
                query_documento = 'sair' # Sinaliza para o loop externo sair
                break # Sai do loop interno (Etapa 2)

            # Prepara o filtro de metadados para o Pinecone
            filtro_pinecone = {"arquivo_origem": {"$eq": documento_encontrado}}

            # Etapa 4: Buscar e re-ranquear DENTRO do documento
            print(f"\nBuscando informações apenas em '{documento_encontrado}'...")
            contexto_especifico = buscar_e_reranquear(
                query_especifica, 
                index, 
                embedding_model, 
                reranker_model,
                filtro_metadata=filtro_pinecone, # <-- AQUI ESTÁ A MUDANÇA
                top_k_retrieve=25, # Podemos buscar mais, já que está filtrado
                top_k_rerank=15
            )
            
            # Etapa 5: Gerar a resposta final com o LLM
            print("Enviando contexto filtrado para o modelo de linguagem gerar a resposta final...")
            resposta_final = gerar_resposta(query_especifica, contexto_especifico)
            
            # Apresentar o resultado final
            print("\n=============================================")
            print("=               RESPOSTA FINAL                =")
            print("=============================================")
            print(f"**Documento Analisado:** {documento_encontrado}")
            print(f"**Pergunta:** {query_especifica}\n")
            print(f"**Resposta Gerada:**\n{resposta_final}")
            
            if contexto_especifico:
                print("\n--- CONTEXTO UTILIZADO (TOP 5) ---")
                for i, doc in enumerate(contexto_especifico[:5]): # Limita a 5 para legibilidade
                    print(f"[{i+1}] Score: {doc['score_reranker']:.4f} | ID: {doc.get('id', 'N/A')}")
                    print(f"     Trecho: \"...{doc['texto'][:250].strip()}...\"\n")
            else:
                 print("\n--- NENHUM CONTEXTO ESPECÍFICO FOI ENCONTRADO NESTE DOCUMENTO ---")
            print("=============================================")
            # O loop continua, pedindo outra pergunta sobre o MESMO documento
        if query_documento == 'sair':
            break # Sai do loop principal (Etapa 1)

    print("\nEncerrando o programa.")