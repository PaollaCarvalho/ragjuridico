# main.py
from src.rag_pipeline import RAGPipeline
from src.config import PDF_DIRECTORY

def display_results(document, query, response, context):
    """Formata e exibe os resultados da consulta."""
    print("\n=============================================")
    print("=             RESPOSTA FINAL                =")
    print("=============================================")
    if document:
        print(f"**Documento Analisado:** {document}")
    print(f"**Pergunta:** {query}\n")
    print(f"**Resposta Gerada:**\n{response}")
    
    if context:
        print("\n--- CONTEXTO UTILIZADO (TOP 5) ---")
        for i, doc in enumerate(context[:5]):
            print(f"[{i+1}] Score: {doc['score_reranker']:.4f} | ID: {doc.get('id', 'N/A')}")
            print(f"      Trecho: \"...{doc['texto'][:250].strip()}...\"\n")
    else:
        print("\n--- NENHUM CONTEXTO RELEVANTE FOI ENCONTRADO ---")
    print("=============================================")

def main():
    try:
        pipeline = RAGPipeline()
        
        # Etapa de Indexação
        pipeline.index_directory(PDF_DIRECTORY)
        
        # Etapa de Perguntas e Respostas
        print("\n--- INICIANDO ETAPA DE PERGUNTAS E RESPOSTAS ---")
        while True:
            print("\n=======================================================")
            print("ETAPA 1: IDENTIFICAÇÃO DO DOCUMENTO")
            print("=======================================================")
            doc_query = input("Sobre qual documento você quer perguntar? (Digite 'sair' para terminar): ")

            if doc_query.lower() in ['sair', 'exit', 'quit']:
                break

            # Busca inicial para encontrar o documento
            context_docs = pipeline.search_and_rerank(doc_query)
            if not context_docs:
                print("Não consegui identificar um documento relevante. Tente novamente.")
                continue

            found_doc = context_docs[0]['arquivo_origem']
            print(f"\n[FOCO ATIVADO] Documento identificado: '{found_doc}'")
            print(f"(Score de relevância: {context_docs[0]['score_reranker']:.4f})")

            # Loop para perguntas específicas sobre o documento encontrado
            while True:
                print("\n-------------------------------------------------------")
                print(f"ETAPA 2: PERGUNTA SOBRE '{found_doc}'")
                print("-------------------------------------------------------")
                specific_query = input("Qual sua pergunta? (Digite 'voltar' para escolher outro doc): ")

                if specific_query.lower() in ['voltar', 'back']:
                    break
                if specific_query.lower() in ['sair', 'exit', 'quit']:
                    doc_query = 'sair'
                    break

                # Filtro para buscar apenas no documento selecionado
                doc_filter = {"arquivo_origem": {"$eq": found_doc}}
                
                final_answer, specific_context = pipeline.answer(specific_query, filter_metadata=doc_filter)
                
                display_results(found_doc, specific_query, final_answer, specific_context)

            if doc_query == 'sair':
                break

    except Exception as e:
        print(f"\nOcorreu um erro crítico na aplicação: {e}")
    finally:
        print("\nEncerrando o programa.")

if __name__ == "__main__":
    main()  