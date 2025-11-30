import sys
import os
from typing import Dict

# ⚠️ Adiciona o caminho pai para os imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 🔄 Imports das funções de extração
from extraction.main_extrc import processar_pdf, processar_arquivo_drive 
# 🚀 NOVO IMPORT: Função para listar IDs do Drive
from driveservice.driveservice_util import listar_ids_drive 

from insercao import inserir_documento, inserir_cpf_cnpj, inserir_envolvido, inserir_relacionamento_cpf_cnpj, inserir_relacionamento_envolvido
from config_conexao import conectar_banco, fechar_conexao


def salvar_no_banco(resultado: Dict) -> bool:
    """
    Salva resultado da extração no banco de dados.
    Usa transações para garantir consistência.
    
    Args:
        resultado: Dicionário retornado por processar_pdf() ou processar_arquivo_drive()
    
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
        
        # 2. Processa Envolvidos (Lógica de combinação)
        
        # Lista para armazenar todos os envolvidos que serão inseridos
        envolvidos_para_inserir = []
        
        # Adiciona resultados da extração por Regex
        envolvidos_para_inserir.extend(resultado.get('envolvidos_regex', []))
        
        # Adiciona resultados da extração por IA
        dados_ia = resultado.get('envolvidos_ia', {})
        
        for empresa_ia in dados_ia.get('empresas', []):
            envolvidos_para_inserir.append({
                'razao_social': empresa_ia,
                'representante': 'Não Extraído (IA)'
            })

        for pessoa_ia in dados_ia.get('pessoas', []):
             envolvidos_para_inserir.append({
                'razao_social': pessoa_ia,
                'representante': 'Não Extraído (IA)' 
            })

        # Adiciona envolvidos que podem vir na chave 'envolvidos'
        envolvidos_para_inserir.extend(resultado.get('envolvidos', []))
        
        # Processa a lista final de envolvidos
        for envolvido in envolvidos_para_inserir:
            razao_social = envolvido.get('razao_social')
            representante = envolvido.get('representante')

            if not razao_social:
                continue 

            id_prt = inserir_envolvido(
                conexao,
                razao_social,
                representante
            )
            
            if id_prt:
                inserir_relacionamento_envolvido(conexao, id_doc, id_prt)
                print(f"  ✓ Envolvido inserido: {razao_social}")
            else:
                raise Exception(f"Falha ao inserir envolvido: {razao_social}")
        
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


# --- Novo Fluxo de Processamento de Múltiplos Arquivos do Drive ---
def processar_todos_documentos():
    print("--- ☁️ Iniciando Processamento de Múltiplos Arquivos do Drive ---")
    
    try:
        # 1. Lista todos os IDs de arquivos na pasta do Drive
        file_ids = listar_ids_drive()
        
        if not file_ids:
            print("Nenhum arquivo encontrado na pasta do Drive configurada.")
            return

        print(f"Total de {len(file_ids)} documentos encontrados. Processando...")

        # 2. Itera e processa cada arquivo
        for i, file_id in enumerate(file_ids):
            print(f"\n[DOCUMENTO {i+1}/{len(file_ids)}] ID: {file_id}")
            
            try:
                # Processa o arquivo (Baixa, Extrai, Deleta temporário)
                resultado_drive = processar_arquivo_drive(file_id) 
                
                # Salva o resultado no banco
                if salvar_no_banco(resultado_drive):
                    pass # O log de sucesso está em salvar_no_banco
                else:
                    print(f"❌ Falha ao salvar documento {file_id} no banco.")
            
            except Exception as e:
                print(f"❌ Erro INESPERADO ao processar o arquivo {file_id}: {e}")
                
    except Exception as e:
        print(f"❌ Erro fatal ao listar ou iniciar o processamento: {e}")


if __name__ == '__main__':
    # ⚠️ Executa o novo fluxo de processamento para todos os documentos
    processar_todos_documentos()