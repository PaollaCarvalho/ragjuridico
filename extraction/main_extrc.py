import os
from typing import Dict
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from extraction.raspagem_pdf import extrair_envolvidos, extrair_data, extrair_info_arquivo, extrair_pfpj



def processar_pdf(caminho_pdf: str) -> Dict:

    try:
        nome_arquivo = os.path.basename(caminho_pdf)
        info_arquivo = extrair_info_arquivo(caminho_pdf)
        envolvidos = extrair_envolvidos(caminho_pdf, info_arquivo['empresas'])
        cpf_cnpj = extrair_pfpj(caminho_pdf)
        emissao_doc = extrair_data(caminho_pdf)
        
        resultado = {
            'documento': {
                'nm_arquivo': nome_arquivo,
                'caminho_completo': caminho_pdf,
                'tipo_doc': info_arquivo['tipo_documento'],
                'dt_cntr': emissao_doc,
                'id_empresa': 1 # Ajuste conforme necessário
            },
            'envolvidos': envolvidos,
            'cpf_cnpj': {
                'cpf': cpf_cnpj['cpf'],    
                'cnpj': cpf_cnpj['cnpj'],  
            },
            'status': 'sucesso',
            'erro': None
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
            'envolvidos': [],
            'cpf_cnpj': {'cpf': [], 'cnpj': []},
            'status': 'erro',
            'erro': str(e)
        }
    

