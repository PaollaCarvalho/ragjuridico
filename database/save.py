import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from extraction.main_extrc import processar_pdf
from insercao import inserir_documento, inserir_cpf_cnpj, inserir_envolvido, inserir_relacionamento_cpf_cnpj, inserir_relacionamento_envolvido
from config_conexao import conectar_banco, fechar_conexao
<<<<<<< HEAD
from typing import Dict, List, Optional
from mysql.connector import Error
from recon.main_extrc import processar_pdf
=======
from typing import Dict

>>>>>>> 956673175342fd5f3b4874e600070ee10c9aef7c


def salvar_no_banco(resultado: Dict) -> bool:
    """
    Salva resultado da extração no banco de dados.
    Usa transações para garantir consistência.
    
    Args:
        resultado: Dicionário retornado por processar_pdf()
    
    Returns:
        True se salvou com sucesso, False caso contrário
    """
    # Valida se a extração foi bem-sucedida
    if resultado['status'] != 'sucesso':
        print(f"⏭️  Pulando: {resultado['documento']['nm_arquivo']} (status: {resultado['status']})")
        return False
    
    conexao = conectar_banco()
    
    if not conexao:
        print("Não foi possível conectar ao banco de dados")
        return False
    
    try:
        # Inicia transação
        conexao.start_transaction()
        
        doc = resultado['documento']
        
        if not doc['dt_cntr']:
            print(f"Emissão de documento não encontrada para {doc['nm_arquivo']}")
        

        # Verifica duplicata (atualmente desativado)
        '''id_doc_existente = verificar_duplicata(conexao, doc['nm_arquivo'], doc['tipo_doc'])
        
        if id_doc_existente:
            print(f"⚠️  Documento duplicado encontrado (id={id_doc_existente}): {doc['nm_arquivo']}")
            # TODO: Implementar lógica de atualização aqui se necessário
            conexao.rollback()
            fechar_conexao(conexao)
            return False
        '''
        # 1. Insere documento
        id_doc = inserir_documento(conexao, doc)
        
        if not id_doc:
            raise Exception("Falha ao inserir documento")
        
        print(f"✓ Documento inserido (id={id_doc}): {doc['nm_arquivo']}")
        
        for envolvido in resultado['envolvidos']:
            id_prt = inserir_envolvido(
                conexao,
                envolvido['razao_social'],
                envolvido['representante']
            )
            
            if id_prt:
                inserir_relacionamento_envolvido(conexao, id_doc, id_prt)
                print(f"  ✓ Envolvido inserido: {envolvido['razao_social']}")
            else:
                raise Exception(f"Falha ao inserir envolvido: {envolvido['razao_social']}")
        
        # 3. Insere CPF/CNPJ e relacionamentos
        cpfs = resultado['cpf_cnpj']['cpf']
        cnpjs = resultado['cpf_cnpj']['cnpj']
        
        cpf = cpfs[0] if len(cpfs) >= 1 else None
        cpf2 = cpfs[1] if len(cpfs) >= 2 else None
        
        cnpj= cnpjs[0] if len(cnpjs) >= 1 else None
        cnpj2 = cnpjs[1] if len(cnpjs) >= 2 else None

        id_pjpf = inserir_cpf_cnpj(conexao, cpf, cnpj, cpf2, cnpj2)   
            
        if id_pjpf:
            inserir_relacionamento_cpf_cnpj(conexao, id_doc, id_pjpf)
                
                # Monta string para log
            valores = []
            if cpf:
                valores.append(f"CPF: {cpf}")
            if cnpj:
                valores.append(f"CNPJ: {cnpj}")
                
            print(f"  ✓ Inserido: {' | '.join(valores)}")
        else:
            raise Exception(f"Falha ao inserir CPF/CNPJ")
        
        conexao.commit()
        print(f"✅ Documento salvo com sucesso!\n")
        
        fechar_conexao(conexao)
        return True
        
    except Exception as e:
        print(f"❌ Erro ao salvar no banco: {e}")
        conexao.rollback()
        fechar_conexao(conexao)
        return False

''' CARLOS AQ TESTAR INSERIR DOCUMENTO NO BANCO 
caminho_pdf = r"documentos\ALVARO VINICIUS FERRARI - Contrato de Empresa Associada.pdf"

resultado = processar_pdf(caminho_pdf)

if salvar_no_banco(resultado):
    print("Salvo no banco")
else:
    print("Erro ao salvar")
'''