import firebase_admin
from firebase_admin import credentials, storage
import os
from io import BytesIO

# Inicializa Firebase con las credenciales y el bucket de almacenamiento
cred = credentials.Certificate("config/hawejin-files-firebase-adminsdk-ladhr-3d648e3e69.json")
firebase_admin.initialize_app(cred, {
    'storageBucket': 'hawejin-files.appspot.com'
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


