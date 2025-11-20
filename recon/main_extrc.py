
import os
from pathlib import Path
from typing import List, Dict, Optional
from .raspagem_pdf import extrair_envolvidos, extrair_data, extrair_info_arquivo, extrair_pfpj

def processar_pdf(caminho_pdf: str) -> Dict:

    try:
        nome_arquivo = os.path.basename(caminho_pdf)
        info_arquivo = extrair_info_arquivo(caminho_pdf)
        envolvidos = extrair_envolvidos(caminho_pdf, info_arquivo['empresas'])
        data_assinatura = extrair_data(caminho_pdf)
        cpf_cnpj = extrair_pfpj(caminho_pdf)
        
        resultado = {
            'documento': {
                'nm_arquivo': nome_arquivo,
                'caminho_completo': caminho_pdf,
                'tipo_doc': info_arquivo['tipo_documento'],
                'dt_cntr': data_assinatura,
                'id_empresa': 1  
            },
            'envolvidos': envolvidos,
            'cpf_cnpj': [
                {'CPF': cpf, 'CNPJ': None} for cpf in cpf_cnpj['cpf']
            ] + [
                {'CPF': None, 'CNPJ': cnpj} for cnpj in cpf_cnpj['cnpj']
            ],
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
            'cpf_cnpj': [],
            'status': 'erro',
            'erro': str(e)
        }
''''''
def processar_pasta(pasta_pdfs: str, limite: int = None) -> List[Dict]:

    pasta = Path(pasta_pdfs)
    arquivos_pdf = list(pasta.glob('*.pdf'))
    
    if limite:
        arquivos_pdf = arquivos_pdf[:limite]
    
    total = len(arquivos_pdf)
    print(f"\n{'='*70}")
    print(f"INICIANDO PROCESSAMENTO DE {total} PDFs")
    print(f"{'='*70}\n")
    
    resultados = []
    sucessos = 0
    erros = 0
    
    for i, caminho_pdf in enumerate(arquivos_pdf, 1):
        print(f"[{i}/{total}] Processando: {caminho_pdf.name}")
        
        resultado = processar_pdf(str(caminho_pdf))
        resultados.append(resultado)
        
        if resultado['status'] == 'sucesso':
            sucessos += 1
            print(f"  ✓ Sucesso")
            print(f"    - Tipo: {resultado['documento']['tipo_doc']}")
            print(f"    - Data: {resultado['documento']['dt_cntr']}")
            print(f"    - Envolvidos: {len(resultado['envolvidos'])}")
            print(f"    - CPF/CNPJ: {len(resultado['cpf_cnpj'])}")
        else:
            erros += 1
            print(f"  ✗ Erro: {resultado['erro']}")
        
        print()
    
    
    print(f"\n{'='*70}")
    print(f"PROCESSAMENTO CONCLUÍDO")
    print(f"{'='*70}")
    print(f"Total processados: {total}")
    print(f"Sucessos: {sucessos} ({(sucessos/total)*100:.1f}%)")
    print(f"Erros: {erros} ({(erros/total)*100:.1f}%)")
    print(f"{'='*70}\n")
    
    return resultados

'''
def exibir_detalhes_resultado(resultado: Dict):
    """Exibe detalhes formatados de um resultado."""
    print(f"\n{'='*70}")
    print(f"ARQUIVO: {resultado['documento']['nm_arquivo']}")
    print(f"{'='*70}")
    print(f"Status: {resultado['status']}")
    
    if resultado['status'] == 'sucesso':
        print(f"\nDOCUMENTO:")
        print(f"  - Tipo: {resultado['documento']['tipo_doc']}")
        print(f"  - Data: {resultado['documento']['dt_cntr']}")
        
        print(f"\nENVOLVIDOS ({len(resultado['envolvidos'])}):")
        for env in resultado['envolvidos']:
            print(f"  - Empresa: {env['razao_social']}")
            print(f"    Representante: {env['representante']}")
        
        print(f"\nCPF/CNPJ ({len(resultado['cpf_cnpj'])}):")
        for item in resultado['cpf_cnpj']:
            if item['CPF']:
                print(f"  - CPF: {item['CPF']}")
            if item['CNPJ']:
                print(f"  - CNPJ: {item['CNPJ']}")
    else:
        print(f"Erro: {resultado['erro']}")
'''

if __name__ == "__main__":
    PASTA_PDF = r'documentos'
    
    resultados = processar_pasta(PASTA_PDF, limite=30)
'''
    # Exibe detalhes de TODOS
    for resultado in resultados:
        exibir_detalhes_resultado(resultado)
        input("Pressione ENTER para próximo...")    
'''
