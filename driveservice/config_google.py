from google.oauth2 import service_account
from googleapiclient.discovery import build
import os

# --- Configurações ---
SCOPES = ["https://www.googleapis.com/auth/drive"]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

KEY_FILENAME = 'prjbuscadocs-cc2989266215.json'

SERVICE_ACCOUNT_FILE = os.path.join(BASE_DIR, KEY_FILENAME)

# -------------------------------------------------------------

creds = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE,
    scopes=SCOPES
)

service = build("drive", "v3", credentials=creds)

folder_id = "1gTI7UgoNAB3AGoJaM58lJzi-f99_gFz9"

'''
results = service.files().list(
     q=f"'{folder_id}' in parents and trashed=false",
     fields="files(id, name)"
).execute()
print(results)
'''