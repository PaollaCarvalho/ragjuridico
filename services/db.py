from typing import List
from datetime import date
from database.config_conexao import DB_CONFIG, conectar_banco, fechar_conexao, executar_query
from mysql.connector import connect, Error



def buscar_documentos_mysql(tipo_doc: str = None, 
                           data_inicio: date = None, data_fim: date = None) -> List[dict]:
    """
    Busca documentos no MySQL usando palavras-chave.
    Retorna lista de documentos com informações completas.
    """
    
    # Query base com JOINs
    query = """
        SELECT
            d.id_doc,
            d.nm_arquivo,
            d.tipo_doc,
            d.emissao_doc,
            p.empresa_assoc,
            p.titular,
            c.CPF,
            c.CPF2,
            c.CNPJ,
            c.CNPJ2
        FROM documento d
        LEFT JOIN doc_prt_envolvida de ON d.id_doc = de.id_doc
        LEFT JOIN prt_envolvida p ON de.id_prt = p.id_prt
        LEFT JOIN doc_pf_pj dpf ON d.id_doc = dpf.id_doc
        LEFT JOIN cpf_cnpj c ON dpf.id_pjpf = c.id_pjpf
        LIMIT 50;
    """
        
    params = []
    
    if tipo_doc:
        query += " AND d.tipo_doc LIKE %s"
        params.append(f"%{tipo_doc}%")
    
    if data_inicio:
        query += " AND d.emissao_doc >= %s"
        params.append(data_inicio)
    
    if data_fim:
        query += " AND d.emissao_doc <= %s"
        params.append(data_fim)
    
    query += " ORDER BY d.emissao_doc DESC LIMIT 100"
    
    return executar_query(query, tuple(params))

def agrupar_documentos(resultados_mysql: List[dict]) -> List[dict]:
    """
    Agrupa resultados por documento (um documento pode ter múltiplos envolvidos/CPFs).
    """
    documentos_agrupados = {}
    
    for row in resultados_mysql:
        id_doc = row['id_doc']
        
        if id_doc not in documentos_agrupados:
            documentos_agrupados[id_doc] = {
                'id_doc': id_doc,
                'nome_arquivo': row['nm_arquivo'],
                'tipo_doc': row['tipo_doc'],
                'data_assinatura': row['emissao_doc'],
                'envolvidos': [],
                'cpf_cnpj': []
            }
        
        # Adiciona envolvido (se não for duplicado)
        if row.get('empresa_assoc'):
            envolvido = {
                'empresa': row['empresa_assoc'],
                'representante': row['titular'] or ''
            }
            if envolvido not in documentos_agrupados[id_doc]['envolvidos']:
                documentos_agrupados[id_doc]['envolvidos'].append(envolvido)
        
        # Adiciona CPF/CNPJ (se não for duplicado)
        if row.get('CPF'):
            documentos_agrupados[id_doc]['cpf_cnpj'].append({
                'cpf': row['CPF'],
                'cnpj': row['CNPJ']
            })

        # caso existam CPF2 CNPJ2 
        if row.get('CPF2') or row.get('CNPJ2'):
            documentos_agrupados[id_doc]['cpf_cnpj'].append({
                'cpf': row['CPF2'] if row.get('CPF2') else None,
                'cnpj': row['CNPJ2'] if row.get('CNPJ2') else None
            })

    return list(documentos_agrupados.values())