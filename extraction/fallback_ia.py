from openai import OpenAI
from dotenv import load_dotenv
import json
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from extraction.raspagem_pdf import ler_pgsdoc

load_dotenv()  
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

REPRESENTANTES_IGNORAR = [
    "Victor Donaduzzi",
    "Paulo Roberto Cordeiro Rocha"
]

EMPRESAS_IGNORAR = [
    'PARQUE CIENTÍFICO E TECNOLÓGICO DE BIOCIÊNCIAS LTDA',
    'BIOPARK',
    'PARQUE CIENTIFICO E TECNOLOGICO DE BIOCIENCIAS LTDA'
]


def extrair_dados_ia(caminho_pdf: str) -> dict:

    paginas = ler_pgsdoc(caminho_pdf, paginas=[0])
    texto = "\n".join(paginas)

    PROMPT = f"""
Você é um extrator de informações, NÃO UM GERADOR DE TEXTO. 
Sua tarefa é ler SOMENTE o trecho abaixo do PDF e retornar os dados em JSON.

REGRAS IMPORTANTES (SIGA À RISCA):
- Não invente nenhuma informação.
- Se não encontrar o nome da empresa, retorne uma lista vazia.
- Se não encontrar o representante, retorne string vazia.
- Não gere comentários, explicações ou texto fora do JSON.
- Nunca crie nomes fictícios.
- Extraia exatamente como está escrito no documento.

A partir do texto abaixo, procure SOMENTE:
1. Razão Social da Empresa (aparece logo após frases como:
   - "de um lado,"
   - "Pelo presente instrumento e na melhor forma de direito..."
)
2. Nome do Representante, que quase sempre aparece após:
   - "representada, neste ato, por seu"
   - "representada por seu titular"
   - "representada por sua sócia administradora"
   - "representada por sua sócia administradora"
   - "representada por seu empreendedor"
   O nome aparece LOGO após essas expressões.

DADOS A IGNORAR:
EMPRESAS_IGNORAR:
- PARQUE CIENTÍFICO E TECNOLÓGICO DE BIOCIÊNCIAS LTDA
- BIOPARK
- PARQUE CIENTIFICO E TECNOLOGICO DE BIOCIENCIAS LTDA

REPRESENTANTES_IGNORAR:
- Victor Donaduzzi
- Paulo Roberto Cordeiro Rocha

TEXTO DO PDF A SER ANALISADO:
\"\"\" 
{texto}
\"\"\"

FORMATO DE RESPOSTA (estritamente assim):
{{
    "empresas": ["empresa1", "empresa2"],
    "representante": "nome completo ou vazio"
}}
"""


    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": PROMPT}],
        temperature=0
    )

    try:
        dados = eval(response.choices[0].message.content)
    except:
        return {"empresas": [], "representante": ""}

    # filtraa empresas e representates proibidas por segurança
    validas = [
        e for e in dados.get("empresas", [])
        if all(bio.upper() not in e.upper() for bio in EMPRESAS_IGNORAR)
    ]

    representante = dados.get("representante", "")

    if any(ign.lower() in representante.lower() for ign in REPRESENTANTES_IGNORAR):
        representante = ""

    return {
        "empresas": validas,
        "representante": representante
    }


