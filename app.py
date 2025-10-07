# app.py
import os
from flask import Flask, render_template, request
from src.rag_pipeline import RAGPipeline
from src.config import PDF_DIRECTORY

# 1. Inicializa a aplicação Flask
app = Flask(__name__)

# 2. Carrega o pipeline RAG (isso acontece apenas uma vez, na inicialização)
print("="*50)
print("INICIANDO SERVIDOR WEB E CARREGANDO PIPELINE RAG...")
print("Isso pode levar alguns minutos, aguarde o carregamento dos modelos.")
pipeline = RAGPipeline()
print("Pipeline RAG carregado com sucesso.")

# 3. Indexa os documentos da pasta 'contratos' na inicialização
print("Indexando documentos da pasta de PDFs...")
pipeline.index_directory(PDF_DIRECTORY)
print("Indexação concluída.")
print("Servidor pronto para receber perguntas em http://127.0.0.1:5000")
print("="*50)


# 4. Define a rota principal da aplicação
@app.route('/', methods=['GET', 'POST'])
def home():
    answer = None
    context = None
    question = ""

    # Se o formulário for enviado (método POST)
    if request.method == 'POST':
        question = request.form.get('question')
        if question:
            print(f"\nRecebida nova pergunta: '{question}'")
            # Simplificamos a lógica aqui: uma única busca para encontrar a resposta.
            # O sistema RAG é robusto o suficiente para encontrar o contexto relevante
            # mesmo que o nome do documento esteja na pergunta.
            answer, context = pipeline.answer(question)
    
    # Renderiza a página HTML, passando as variáveis
    return render_template('index.html', question=question, answer=answer, context=context)

# 5. Executa a aplicação
if __name__ == '__main__':
    # debug=False para produção. Use debug=True apenas para desenvolvimento.
    app.run(host='0.0.0.0', port=5000, debug=True)