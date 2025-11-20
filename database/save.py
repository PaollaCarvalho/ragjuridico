from insercao import inserir_documento, inserir_cpf_cnpj, inserir_envolvido, inserir_relacionamento_cpf_cnpj, inserir_relacionamento_envolvido
from config_conexao import conectar_banco, fechar_conexao
from typing import Dict, List, Optional
from mysql.connector import Error
from recon.main_extrc import processar_pdf


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
        print("❌ Não foi possível conectar ao banco de dados")
        return False
    
    try:
        # Inicia transação
        conexao.start_transaction()
        
        doc = resultado['documento']
        
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
        # OTIMIZAÇÃO: Junta CPF e CNPJ na mesma linha quando possível
        cpfs = [item['CPF'] for item in resultado['cpf_cnpj'] if item.get('CPF')]
        cnpjs = [item['CNPJ'] for item in resultado['cpf_cnpj'] if item.get('CNPJ')]
        
        # Determina quantas linhas serão necessárias
        max_linhas = max(len(cpfs), len(cnpjs))
        
        for i in range(max_linhas):
            cpf = cpfs[i] if i < len(cpfs) else None
            cnpj = cnpjs[i] if i < len(cnpjs) else None
            
            id_pjpf = inserir_cpf_cnpj(conexao, cpf, cnpj)
            
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
        # Desfaz tudo em caso de erro
        print(f"❌ Erro ao salvar no banco: {e}")
        conexao.rollback()
        fechar_conexao(conexao)
        return False


# ============================================================================
# FUNÇÃO DE PROCESSAMENTO EM LOTE
# ============================================================================

def processar_e_salvar_pasta(pasta_pdfs: str, limite: int = None) -> Dict:
    """
    Processa PDFs e salva no banco de dados.
    Retorna estatísticas do processamento.
    """
    from pathlib import Path
    
    # Busca todos os PDFs
    pasta = Path(pasta_pdfs)
    arquivos_pdf = list(pasta.glob('*.pdf'))
    
    if limite:
        arquivos_pdf = arquivos_pdf[:limite]
    
    total = len(arquivos_pdf)
    
    print(f"\n{'='*70}")
    print(f"PROCESSAMENTO E SALVAMENTO NO BANCO")
    print(f"{'='*70}")
    print(f"Total de PDFs: {total}\n")
    
    estatisticas = {
        'total': total,
        'extraidos_sucesso': 0,
        'salvos_banco': 0,
        'erros_extracao': 0,
        'erros_banco': 0
    }
    
    for i, caminho_pdf in enumerate(arquivos_pdf, 1):
        print(f"[{i}/{total}] {caminho_pdf.name}")
        
        # Extrai dados do PDF (usa função do outro código)
        resultado = processar_pdf(str(caminho_pdf))
        
        if resultado['status'] == 'sucesso':
            estatisticas['extraidos_sucesso'] += 1
            
            # Tenta salvar no banco
            if salvar_no_banco(resultado):
                estatisticas['salvos_banco'] += 1
            else:
                estatisticas['erros_banco'] += 1
        else:
            estatisticas['erros_extracao'] += 1
            print(f"  ❌ Erro na extração: {resultado['erro']}\n")
    
    # Relatório final
    print(f"\n{'='*70}")
    print(f"RELATÓRIO FINAL")
    print(f"{'='*70}")
    print(f"Total processados: {estatisticas['total']}")
    print(f"Extraídos com sucesso: {estatisticas['extraidos_sucesso']}")
    print(f"Salvos no banco: {estatisticas['salvos_banco']}")
    print(f"Erros na extração: {estatisticas['erros_extracao']}")
    print(f"Erros ao salvar: {estatisticas['erros_banco']}")
    print(f"{'='*70}\n")
    
    return estatisticas