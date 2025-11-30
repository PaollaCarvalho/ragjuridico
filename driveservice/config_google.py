from google.oauth2 import service_account
from googleapiclient.discovery import build
import os

# --- Configurações de Escopo ---
SCOPES = ["https://www.googleapis.com/auth/drive"]

# -------------------------------------------------------------
# 🚀 CORREÇÃO DO CAMINHO ABSOLUTO PARA A CHAVE DE SERVIÇO
# -------------------------------------------------------------

# 1. Obter o caminho absoluto do diretório onde este arquivo (config_google.py) está.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 2. Definir o nome do arquivo da chave
KEY_FILENAME = 'prjbuscadocs-a970e51aa880.json'

# 3. Construir o caminho completo e absoluto para o arquivo JSON
SERVICE_ACCOUNT_FILE = os.path.join(BASE_DIR, KEY_FILENAME)

# -------------------------------------------------------------

# --- Configuração de Credenciais e Serviço ---
creds = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE,
    scopes=SCOPES
)

# O objeto 'service' pode ser importado por outros módulos para listar arquivos
service = build("drive", "v3", credentials=creds)


folder_id = "1gTI7UgoNAB3AGoJaM58lJzi-f99_gFz9"
results = service.files().list(
     q=f"'{folder_id}' in parents and trashed=false",
     fields="files(id, name)"
).execute()
print(results)