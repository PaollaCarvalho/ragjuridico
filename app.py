# app.py
from flask import Flask, render_template, request, redirect, url_for
from src.rag_pipeline import RAGPipeline
from src.config import PDF_DIRECTORY

# Inicializa a aplicação Flask
app = Flask(__name__)

# Carrega o pipeline RAG (isso acontece apenas uma vez, na inicialização)
print("="*50)
print("INICIANDO SERVIDOR WEB E CARREGANDO PIPELINE RAG...")
print("Isso pode levar alguns minutos, aguarde o carregamento dos modelos.")
pipeline = RAGPipeline()
print("Pipeline RAG carregado com sucesso.")

# Indexa os documentos da pasta 'contratos' na inicialização
print("Indexando documentos da pasta de PDFs...")
pipeline.index_directory(PDF_DIRECTORY)
print("Indexação concluída.")
print("Servidor pronto para receber perguntas em http://127.0.0.1:5000")
print("="*50)


# Define a rota principal da aplicação
@app.route('/', methods=['GET', 'POST'])
def home():
    # Variáveis para controlar o estado da página
    documento_foco = None
    resposta_especifica = None
    contexto_especifico = None
    pergunta_especifica = ""

    if request.method == 'POST':
        # --- LÓGICA DA ETAPA 1: ENCONTRAR O DOCUMENTO ---
        if 'submit_busca_doc' in request.form:
            query_doc = request.form.get('query_doc')
            if query_doc:
                print(f"\n[ETAPA 1] Buscando documento para: '{query_doc}'")
                # Busca sem filtro para encontrar o documento mais relevante
                contexto_doc = pipeline.search_and_rerank(query_doc)
                if contexto_doc:
                    # Define o documento encontrado como o foco
                    documento_foco = contexto_doc[0]['arquivo_origem']
                    print(f"Documento em foco definido: {documento_foco}")

        # --- LÓGICA DA ETAPA 2: PERGUNTAR SOBRE O DOCUMENTO EM FOCO ---
        elif 'submit_pergunta_especifica' in request.form:
            documento_foco = request.form.get('documento_foco')
            pergunta_especifica = request.form.get('pergunta_especifica')
            
            if documento_foco and pergunta_especifica:
                print(f"\n[ETAPA 2] Buscando resposta para '{pergunta_especifica}' em '{documento_foco}'")
                # Cria o filtro para pesquisar apenas no documento em foco
                filtro_pinecone = {"arquivo_origem": {"$eq": documento_foco}}
                # Chama o pipeline com o filtro
                resposta_especifica, contexto_especifico = pipeline.answer(pergunta_especifica, filter_metadata=filtro_pinecone)

    # Renderiza o template, passando todas as variáveis de estado
    return render_template('index.html', 
                           documento_foco=documento_foco,
                           answer=resposta_especifica,
                           context=contexto_especifico,
                           question=pergunta_especifica)

# Rota para limpar o foco e voltar à Etapa 1
@app.route('/voltar')
def voltar():
    return redirect(url_for('home'))

# Executa a aplicação
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)