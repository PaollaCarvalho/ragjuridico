# src/llm_handler.py
from openai import OpenAI
from typing import List, Dict

class OpenAIHandler:
    """Gerencia a geração de respostas usando a API da OpenAI."""
    def __init__(self, api_key: str, model: str):
        if not api_key:
            raise ValueError("API Key da OpenAI não fornecida.")
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def generate_response(self, query: str, context: List[Dict]) -> str:
        if not context:
            return "Desculpe, não encontrei informações relevantes nos documentos para responder a esta pergunta."
        
        context_texts = "\n\n---\n\n".join(
            [f"Trecho do documento (Origem: {doc.get('arquivo_origem', 'N/A')}):\n{doc['texto']}" for doc in context]
        )
        
        prompt = f"""
        Você é um assistente especializado em direito brasileiro. Sua tarefa é responder à pergunta do usuário de forma precisa, objetiva e completa, baseando-se estritamente no contexto fornecido.

        **Contexto extraído dos documentos:**
        {context_texts}

        **Pergunta do usuário:**
        {query}

        **Instruções:**
        1. Responda à pergunta usando apenas as informações do contexto acima.
        2. Não invente, suponha ou adicione informações externas.
        3. Se a resposta não estiver no contexto, diga claramente: "Com base nos documentos fornecidos, não há informações suficientes para responder a esta pergunta."
        
        **Resposta:**
        """
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Você é um assistente especializado em direito brasileiro."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=1500
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Ocorreu um erro ao chamar a API da OpenAI: {e}"