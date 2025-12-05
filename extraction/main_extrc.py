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
)
from extraction.fallback_ia import extrair_dados_ia

# 2. Import do Google Drive
from driveservice.driveservice_util import baixar_arqdrive


def processar_pdf(caminho_pdf: str) -> Dict:
    """
    Processa um arquivo PDF puxando todas as funções de regex.
    Lógica de fallback para extração de Envolvidos usando IA.
    Função principal de extração.
    """
    try:
        nome_arquivo = os.path.basename(caminho_pdf)
        
        info_arquivo = extrair_info_arquivo(caminho_pdf)
        cpf_cnpj = extrair_pfpj(caminho_pdf)
        emissao_doc = extrair_data(caminho_pdf)
        
        # --- EXTRAÇÃO DE ENVOLVIDOS (if regex funcionar: usamos, se não = IA COMO FALLBACK) ---
        
        envolvidos_regex = extrair_envolvidos(caminho_pdf, info_arquivo.get('empresas', []))

        usar_fallback = (
            not envolvidos_regex or 
            all(not e.get("representante") for e in envolvidos_regex)
        )

        if usar_fallback:
            print("⚠️ Regex não encontrou representantes. Usando IA como fallback.")
            dados_ia = extrair_dados_ia(caminho_pdf)
        else:
            print("✔️ Regex encontrou representantes. IA não será usada.")
            dados_ia = {"empresas": [], "representante": ""}

        # Monta lista final de envolvidos, e insere extraidos por IA e tb por regex, porém a IA só é ativada se regex falhar
        envolvidos_final = []

        for e in envolvidos_regex:
            envolvidos_final.append(e)

        if dados_ia.get("representante") and dados_ia.get("empresas"):
            for empresa in dados_ia["empresas"]:
                envolvidos_final.append({
                    "razao_social": empresa,
                    "representante": dados_ia["representante"]
                })
        
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
            'envolvidos': envolvidos_final,
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


def processar_arquivo_drive(file_id: str) -> Dict:
    """
    Orquestra todo o processo de extração para um arquivo do Google Drive.
    """

    caminho_pdf, nome_original = baixar_arqdrive(file_id)
    
    resultado = processar_pdf(caminho_pdf)
    
    resultado["documento"]["drive_id"] = file_id
    
    # limpa o arquivo temporário
    try:
        os.remove(caminho_pdf)
    except OSError as e:
        print(f"Erro ao deletar arquivo temporário {caminho_pdf}: {e}")
    
    # Adiciona o nome original do arquivo, se estiver faltando (embora 'processar_pdf' já o faça)
    if 'nm_arquivo' not in resultado['documento'] or resultado['documento']['nm_arquivo'] == os.path.basename(caminho_pdf):
        resultado['documento']['nm_arquivo'] = nome_original

    return resultado