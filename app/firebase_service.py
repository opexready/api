import os
import io
import json
import firebase_admin
from firebase_admin import credentials, storage
from fastapi import UploadFile
from io import BytesIO

# 1) Carga credenciales:
creds_json = os.getenv("FIREBASE_CREDENTIALS_JSON")
if creds_json:
    info = json.loads(creds_json)
    cred = credentials.Certificate(info)
else:
    # fallback a fichero local si vas a seguir usándolo en dev
    cred_path = os.getenv(
        "GOOGLE_APPLICATION_CREDENTIALS",
        "config/arendir-909a2-firebase-adminsdk-fbsvc-80cd4666e0.json"
    )
    cred = credentials.Certificate(cred_path)

# 2) Inicializa la app (solo una vez)
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred, {
        "storageBucket": "arendir-909a2.firebasestorage.app"
    })

bucket = storage.bucket()

def upload_file_to_firebase(file, filename):
    """
    Sube un archivo a Firebase Storage y retorna la URL pública.
    """
    blob = bucket.blob(filename)
    blob.upload_from_file(file.file, content_type=file.content_type)
    blob.make_public()  # Hace el archivo accesible públicamente
    return blob.public_url

def download_file_from_firebase(filename, local_path):
    """
    Descarga un archivo desde Firebase Storage y lo guarda localmente.
    """
    blob = bucket.blob(filename)
    blob.download_to_filename(local_path)
    return local_path


def upload_file_to_firebase_pdf(file_data: BytesIO, filename: str, content_type: str):
    """
    Sube un archivo a Firebase Storage desde un objeto BytesIO y retorna la URL pública.
    """
    try:
        blob = bucket.blob(filename)
        blob.upload_from_file(file_data, content_type=content_type)
        blob.make_public()  # Hace el archivo accesible públicamente
        return blob.public_url
    except Exception as e:
        raise Exception(f"Error al subir el archivo a Firebase: {str(e)}")


