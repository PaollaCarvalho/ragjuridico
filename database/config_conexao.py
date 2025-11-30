import mysql.connector
from typing import List, Optional
from mysql.connector import Error
from dotenv import load_dotenv
import os

load_dotenv() 

DB_CONFIG = {
    'host': '127.0.0.1',
    'database': 'banco',
    'user': os.getenv('DB_USER'), 
    'password': os.getenv('DB_PASSWORD'),
    'charset': 'utf8mb4',
    'collation': 'utf8mb4_unicode_ci'
}

ID_EMPRESA_BIOPARK = 1

def conectar_banco():
    try:
        conexao = mysql.connector.connect(**DB_CONFIG)
        if conexao.is_connected():
            return conexao
    except Error as e:
        print(f"Erro ao conectar ao bd: {e}")
        return None

def executar_query(query: str, params: tuple = None) -> List[dict]:
    """Executa query e retorna resultados como lista de dicts"""
    conexao = conectar_banco()
    if not conexao:
        return []
    
    try:
        cursor = conexao.cursor(dictionary=True)
        cursor.execute(query, params or ())
        resultados = cursor.fetchall()
        cursor.close()
        conexao.close()
        return resultados
    except Error as e:
        print(f"Erro na query: {e}")
        if conexao:
            conexao.close()
        return []

def fechar_conexao(conexao, cursor=None):
    if cursor:
        cursor.close()
    if conexao and conexao.is_connected():
        conexao.close()
        
        