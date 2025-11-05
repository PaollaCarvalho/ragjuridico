from typing import List
from rapidfuzz import fuzz
import re


def normalizar_texto(texto: str) -> str:
    """Normaliza texto para busca (lowercase, remove pontuação extra)"""
    if not texto:
        return ""
    # Remove pontuação mas mantém espaços e números
    texto = re.sub(r'[^\w\s]', ' ', texto)
    # Remove espaços múltiplos
    texto = re.sub(r'\s+', ' ', texto)
    return texto.lower().strip()

def extrair_termos_busca(query: str) -> List[str]:
    """Extrai termos de busca relevantes (remove palavras muito curtas)"""
    query_normalizada = normalizar_texto(query)
    termos = [t for t in query_normalizada.split() if len(t) >= 2]
    return termos

def calcular_score_fuzzy(query: str, documento: dict) -> float:
    """
    Calcula score de similaridade usando fuzzy matching.
    Retorna valor entre 0-100.
    """
    query_norm = normalizar_texto(query)
    
    # Monta texto completo do documento para comparação
    textos = []
    
    if documento.get('empresa_assoc'):
        textos.append(normalizar_texto(documento['empresa_assoc']))
    
    if documento.get('titular'):
        textos.append(normalizar_texto(documento['titular']))
    
    if documento.get('CPF'):
        textos.append(documento['CPF'].replace('.', '').replace('-', ''))
    
    if documento.get('CNPJ'):
        textos.append(documento['CNPJ'].replace('.', '').replace('/', '').replace('-', ''))
    
    texto_completo = ' '.join(textos)
    
    # Calcula scores diferentes
    score_partial = fuzz.partial_ratio(query_norm, texto_completo)
    score_token_sort = fuzz.token_sort_ratio(query_norm, texto_completo)
    score_token_set = fuzz.token_set_ratio(query_norm, texto_completo)
    
    # Média ponderada (partial tem mais peso)
    score_final = (score_partial * 0.5) + (score_token_sort * 0.3) + (score_token_set * 0.2)
    
    return round(score_final, 2)