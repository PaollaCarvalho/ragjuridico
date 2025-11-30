from typing import List
from datetime import date
from database.config_conexao import executar_query

def buscar_documentos_mysql(termo_busca: str = None, tipo_doc: str = None, 
                           data_inicio: date = None, data_fim: date = None) -> List[dict]:
    """
    Busca documentos no MySQL filtrando pelo termo de busca e metadados.
    (Versão compatível com banco sem CPF2/CNPJ2)
    """
    
    # 1. Query ajustada: Removidos c.CPF2 e c.CNPJ2 que não existem no banco
    query = """
        SELECT
            d.id_doc,
            d.nm_arquivo,
            d.tipo_doc,
            d.emissao_doc,
            p.empresa_assoc,
            p.titular,
            c.CPF,
            c.CNPJ
        FROM documento d
        LEFT JOIN doc_prt_envolvida de ON d.id_doc = de.id_doc
        LEFT JOIN prt_envolvida p ON de.id_prt = p.id_prt
        LEFT JOIN doc_pf_pj dpf ON d.id_doc = dpf.id_doc
        LEFT JOIN cpf_cnpj c ON dpf.id_pjpf = c.id_pjpf
        WHERE 1=1 
    """
        
    params = []
    
    # 2. Lógica de busca textual
    if termo_busca:
        termo_like = f"%{termo_busca}%"
        # Removemos também a busca em CPF2/CNPJ2 aqui para evitar erros
        query += """ 
            AND (
                d.nm_arquivo LIKE %s OR 
                p.empresa_assoc LIKE %s OR 
                p.titular LIKE %s OR
                c.CPF LIKE %s OR
                c.CNPJ LIKE %s
            )
        """
        params.extend([termo_like] * 5)

    if tipo_doc:
        query += " AND d.tipo_doc LIKE %s"
        params.append(f"%{tipo_doc}%")
    
    if data_inicio:
        query += " AND d.emissao_doc >= %s"
        params.append(data_inicio)
    
    if data_fim:
        query += " AND d.emissao_doc <= %s"
        params.append(data_fim)
    
    query += " ORDER BY d.id_doc DESC LIMIT 100"
    
    return executar_query(query, tuple(params))

def agrupar_documentos(resultados_mysql: List[dict]) -> List[dict]:
    """
    Agrupa resultados por documento.
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
        
        # Adiciona envolvido
        if row.get('empresa_assoc'):
            envolvido = {
                'empresa': row['empresa_assoc'],
                'representante': row['titular'] or ''
            }
            if envolvido not in documentos_agrupados[id_doc]['envolvidos']:
                documentos_agrupados[id_doc]['envolvidos'].append(envolvido)
        
        # Adiciona CPF/CNPJ (Sem lógica de CPF2/CNPJ2)
        if row.get('CPF') or row.get('CNPJ'):
            dados_cpf = {
                'cpf': row['CPF'],
                'cnpj': row['CNPJ']
            }
            if dados_cpf not in documentos_agrupados[id_doc]['cpf_cnpj']:
                documentos_agrupados[id_doc]['cpf_cnpj'].append(dados_cpf)

    return list(documentos_agrupados.values())