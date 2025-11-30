import os
import sys
from typing import Dict

# Ajuste os caminhos conforme sua estrutura de pastas
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 1. Imports Unificados de Extração (assumindo que raspagem_pdf contém todas as funções)
from extraction.raspagem_pdf import (
    extrair_envolvidos, 
    extrair_data, 
    extrair_info_arquivo, 
    extrair_pfpj, 
    extrair_dados_ia # Import específico da lógica de fallback IA
)

# 2. Import do Google Drive
from driveservice.driveservice_util import baixar_arqdrive


def processar_pdf(caminho_pdf: str) -> Dict:
    """
    Processa um arquivo PDF localmente no caminho especificado.
    Inclui lógica de fallback para extração de Envolvidos usando IA.
    Esta é a função principal para arquivos locais.
    """
    try:
        nome_arquivo = os.path.basename(caminho_pdf)
        
        # --- 1. EXTRAÇÃO DE INFORMAÇÕES BÁSICAS (Sempre necessárias) ---
        info_arquivo = extrair_info_arquivo(caminho_pdf)
        cpf_cnpj = extrair_pfpj(caminho_pdf)
        emissao_doc = extrair_data(caminho_pdf)
        
        # --- 2. EXTRAÇÃO DE ENVOLVIDOS (REGEX PRIMEIRO, IA COMO FALLBACK) ---
        
        # Tenta extrair envolvidos usando Regex/Regras Fixas
        envolvidos_regex = extrair_envolvidos(caminho_pdf, info_arquivo.get('empresas', []))
        dados_ia = {'pessoas': [], 'empresas': []} # Inicializa IA como vazio
        
        # Se a extração por Regex falhou (lista vazia), usa a IA como fallback
        if not envolvidos_regex:
            print("⚠️ Regex não encontrou envolvidos. Usando IA como fallback.")
            dados_ia = extrair_dados_ia(caminho_pdf)
        else:
            print("✔️ Regex encontrou envolvidos. Pulando IA.")
        
        # --- 3. MONTAGEM DO DICIONÁRIO DE RESULTADO ---
        
        resultado = {
            'documento': {
                'nm_arquivo': nome_arquivo,
                'caminho_completo': caminho_pdf,
                'tipo_doc': info_arquivo.get('tipo_documento'),
                'dt_cntr': emissao_doc,
                'id_empresa': 1 
            },
            'envolvidos_regex': envolvidos_regex, 
            'envolvidos_ia': dados_ia, 
            'cpf_cnpj': {
                'cpf': cpf_cnpj['cpf'],    
                'cnpj': cpf_cnpj['cnpj'],  
            },
            'status': 'sucesso',
            'erro': None,
            'envolvidos': [] 
        }

        return resultado
        
    except Exception as e:
        return {
            'documento': {
                'nm_arquivo': os.path.basename(caminho_pdf),
                'caminho_completo': caminho_pdf,
                'tipo_doc': None,
                'dt_cntr': None,
                'id_empresa': 1
            },
            'envolvidos_regex': [],
            'envolvidos_ia': {'pessoas': [], 'empresas': []},
            'cpf_cnpj': {'cpf': [], 'cnpj': []},
            'status': 'erro',
            'erro': str(e),
            'envolvidos': [] 
        }
    
# 🚀 FUNÇÃO RESTAURADA E EXPORTADA PARA O save.py
def processar_arquivo_drive(file_id: str) -> Dict:
    """
    Orquestra todo o processo de extração para um arquivo do Google Drive.
    1) Baixa arquivo do Google Drive
    2) Processa o PDF temporário usando processar_pdf (que inclui o fallback IA)
    """

    # 1. Baixa o arquivo do Drive
    caminho_pdf, nome_original = baixar_arqdrive(file_id)
    
    # 2. Processa o PDF temporário usando a função principal
    resultado = processar_pdf(caminho_pdf) 
    
    # 3. (Opcional) Limpar o arquivo temporário
    try:
        os.remove(caminho_pdf)
    except OSError as e:
        print(f"Erro ao deletar arquivo temporário {caminho_pdf}: {e}")
    
    # Adiciona o nome original do arquivo, se estiver faltando (embora 'processar_pdf' já o faça)
    if 'nm_arquivo' not in resultado['documento'] or resultado['documento']['nm_arquivo'] == os.path.basename(caminho_pdf):
        resultado['documento']['nm_arquivo'] = nome_original

    return resultado