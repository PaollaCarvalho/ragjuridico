Projeto de Recuperação de Informações Jurídicas

O objetivo é desenvolver uma aplicação que permita consultas em contratos jurídicos, utilizando técnicas e IA para buscar informações e auxiliar na análise e consulta de documentos.

🚧 Status do Projeto: Em desenvolvimento 

Este projeto une duas abordagens complementares para lidar com documentos jurídicos e empresariais em PDF:

1. **RAG (Retrieval-Augmented Generation)**  
   Permite fazer perguntas em linguagem natural sobre contratos e jurisprudência.  
   - O sistema busca informações relevantes no banco vetorial  
   - Passa o contexto para um modelo de linguagem (LLM)  
   - Retorna respostas fundamentadas e contextualizadas

PDF → Texto limpo → Embeddings → Pinecone → Re-ranking → Resposta final com OpenAI

2. **Extração Estruturada de Dados**  
   Além da busca semântica, o sistema extrai automaticamente informações-chave de PDFs, como:  
   - Nome da empresa  
   - CNPJ / CPF  
   - Titulares e representantes legais  
   Esses dados são armazenados em um **banco relacional** e podem ser consultados diretamente, sem precisar de IA.

> 🔮 Próximos passos: integrar **LangChain** para padronização do fluxo, e criar **interface** para consultas.
