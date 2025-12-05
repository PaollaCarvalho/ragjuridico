from typing import Dict, Optional
from config_conexao import ID_EMPRESA_BIOPARK, conectar_banco, fechar_conexao
from mysql.connector import Error


def inserir_documento(conexao, dados: Dict) -> Optional[int]:
    try:
        cursor = conexao.cursor()
            
        query = """
            INSERT INTO documento (nm_arquivo, emissao_doc, tipo_doc, id_empresa, drive_id)
            VALUES (%s, %s, %s, %s, %s)
        """
        
        valores = (
            dados['nm_arquivo'],
            dados['dt_cntr'] if dados['dt_cntr'] else None,  
            dados['tipo_doc'],
            ID_EMPRESA_BIOPARK,
            dados.get('drive_id') 
        )
        
        cursor.execute(query, valores)
        id_doc = cursor.lastrowid
        cursor.close()
        
        return id_doc
        
    except Error as e:
        print(f"❌ Erro ao inserir documento: {e}")
        return None


def inserir_envolvido(conexao, razao_social: str, representante: str) -> Optional[int]:
    try:
        cursor = conexao.cursor()
        
        query = """
            INSERT INTO prt_envolvida (empresa_assoc, titular)
            VALUES (%s, %s)
        """
        
        cursor.execute(query, (razao_social, representante))
        id_prt = cursor.lastrowid
        cursor.close()
        
        return id_prt
        
    except Error as e:
        print(f"❌ Erro ao inserir envolvido: {e}")
        return None


def inserir_cpf_cnpj(conexao, cpf: Optional[str], cnpj: Optional[str], cpf2: None, cnpj2: None) -> Optional[int]:
    try:
        cursor = conexao.cursor()
        
        query = """
            INSERT INTO cpf_cnpj (CPF, CNPJ, CPF2, CNPJ2)
            VALUES (%s, %s, %s, %s)
        """
        
        cursor.execute(query, (cpf, cnpj, cpf2, cnpj2))
        id_pjpf = cursor.lastrowid
        cursor.close()
        
        return id_pjpf
        
    except Error as e:
        print(f"❌ Erro ao inserir CPF/CNPJ: {e}")
        return None


def inserir_relacionamento_envolvido(conexao, id_doc: int, id_prt: int) -> bool:
    try:
        cursor = conexao.cursor()
        
        query = """
            INSERT INTO doc_prt_envolvida (id_doc, id_prt)
            VALUES (%s, %s)
        """
        
        cursor.execute(query, (id_doc, id_prt))
        cursor.close()
        
        return True
        
    except Error as e:
        print(f"❌ Erro ao inserir relacionamento envolvido: {e}")
        return False


def inserir_relacionamento_cpf_cnpj(conexao, id_doc: int, id_pjpf: int) -> bool:
    try:
        cursor = conexao.cursor()
        
        query = """
            INSERT INTO doc_pf_pj (id_doc, id_pjpf)
            VALUES (%s, %s)
        """
        
        cursor.execute(query, (id_doc, id_pjpf))
        cursor.close()
        
        return True
        
    except Error as e:
        print(f"❌ Erro ao inserir relacionamento CPF/CNPJ: {e}")
        return False