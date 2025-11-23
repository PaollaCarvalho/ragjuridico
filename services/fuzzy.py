from typing import List
from rapidfuzz import fuzz
import unidecode
import re


def normalizar_texto(texto: str) -> str:
    """Normaliza texto para busca (lowercase, remove pontuação extra)"""
    if not texto:
        return ""
    
    texto = unidecode.unidecode(texto)  # remove acentos
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
    
    if documento.get('CPF2'):
        textos.append(documento['CPF2'].replace('.', '').replace('-', ''))      
    
    if documento.get('CNPJ2'):
        textos.append(documento['CNPJ2'].replace('.', '').replace('/', '').replace('-', ''))
    
    texto_completo = ' '.join(textos)
    
    scores = []
    # Calcula scores diferentes
    scores.append(fuzz.partial_ratio(query_norm, texto_completo))
    scores.append(fuzz.token_sort_ratio(query_norm, texto_completo))
    scores.append(fuzz.token_set_ratio(query_norm, texto_completo))

    for t in textos:
        if t:
            scores.append(fuzz.partial_ratio(query_norm, t))
            scores.append(fuzz.token_set_ratio(query_norm, t))
    
    # Média ponderada (partial tem mais peso)
    score_final = max(scores) if scores else 0
    
    return round(score_final, 2)