import os
import io
import tempfile
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from typing import Dict, Tuple, List

# Importa o objeto creds e service (se necessário) e folder_id do arquivo de configuração
# O módulo config_google deve definir 'creds', 'service' e 'folder_id'
from .config_google import creds, service, folder_id


def listar_ids_drive() -> List[str]:
    """
    Lista todos os IDs de arquivos PDF na pasta configurada do Google Drive.
    
    Returns:
        Lista de strings contendo os IDs dos arquivos.
    """
    print("Tentando listar arquivos do Drive...")
    try:
        # A pasta ID é importada do config_google.py
        if not folder_id:
            print("Erro: 'folder_id' não está definido em config_google.py.")
            return []
            
        # Consulta para buscar arquivos (não pastas) dentro da pasta especificada
        query = (
            f"'{folder_id}' in parents and trashed=false"
            # Adicione 'and mimeType='application/pdf'' se quiser filtrar apenas PDFs
        )
        
        results = service.files().list(
            q=query,
            fields="files(id)"
        ).execute()
        
        items = results.get('files', [])
        print(f"Lista concluída. {len(items)} IDs encontrados.")
        
        # Retorna apenas a lista de IDs
        return [item['id'] for item in items]
        
    except Exception as e:
        print(f"Erro ao listar IDs do Google Drive: {e}")
        return []


def baixar_arqdrive(file_id: str) -> Tuple[str, str]:
    """
    Baixa um arquivo do Google Drive mantendo o nome original.
    Retorna:
        caminho_completo (str), nome_original (str)
    """ 
    # Reconstruir o serviço localmente (boa prática em funções utilitárias)
    service_local = build("drive", "v3", credentials=creds)

    # --- 2. Obter metadados para pegar o nome original ---
    metadata = service_local.files().get(fileId=file_id, fields="name").execute()
    nome_arquivo = metadata["name"]

    # --- 3. Criar arquivo temporário preservando o nome ---
    temp_dir = tempfile.gettempdir()
    caminho_temp = os.path.join(temp_dir, nome_arquivo)

    # --- 4. Fazer download ---
    request = service_local.files().get_media(fileId=file_id)
    fh = io.FileIO(caminho_temp, "wb")
    downloader = MediaIoBaseDownload(fh, request)

    done = False
    while not done:
        status, done = downloader.next_chunk()

    return caminho_temp, nome_arquivo


def excluir_arqdrive(caminho_arquivo: str) -> bool:
    """
    Exclui o arquivo temporário baixado.
    """
    try:
        if os.path.exists(caminho_arquivo):
            os.remove(caminho_arquivo)
            return True
        return False 
    
    except Exception:
        return False