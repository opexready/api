from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List
from datetime import timedelta
import shutil
import os
import pandas as pd
from fpdf import FPDF
from fastapi.responses import FileResponse, StreamingResponse
from mimetypes import guess_type
from . import crud, models, schemas, auth
from .database import engine, SessionLocal
import pytesseract
import io
from fastapi.responses import JSONResponse
from PIL import Image, ImageOps
from pyzbar.pyzbar import decode
from datetime import datetime
import re
import cv2
import numpy as np
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
import cv2
import numpy as np
from pyzbar.pyzbar import decode
from PIL import Image
import io
import httpx

app = FastAPI()

# Configuración de Tesseract-OCR
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

async def init_models():
    async with engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.create_all)

@app.on_event("startup")
async def on_startup():
    await init_models()

async def get_db():
    async with SessionLocal() as session:
        yield session

API_SUNAT_URL = "https://api.apis.net.pe/v2/sunat/ruc"
API_TOKEN = "apis-token-9806.XVdywB8B1e4rdsDlPuTSZZ6D9RLx2sBX"

@app.get("/consulta-ruc/")
async def consulta_ruc(ruc: str = Query(..., min_length=11, max_length=11)):
    headers = {
        "Authorization": f"Bearer {API_TOKEN}"
    }
    params = {
        "numero": ruc
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(API_SUNAT_URL, headers=headers, params=params)
        
        if response.status_code == 200:
            return response.json()
        else:
            raise HTTPException(status_code=response.status_code, detail="Error al consultar el RUC")

# Aquí añadimos el nuevo endpoint para OCR
@app.post("/extract-text/")
async def extract_text(file: UploadFile = File(...)):
    if file.content_type not in ['image/jpeg', 'image/png']:
        raise HTTPException(status_code=400, detail="Invalid file format")
    
    try:
        image_data = await file.read()
        image = Image.open(io.BytesIO(image_data))
        text = pytesseract.image_to_string(image)
    
        return JSONResponse(content={"extracted_text": text})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to extract text: {str(e)}")
    
@app.post("/extract-text6/")
async def extract_text(file: UploadFile = File(...)):
    if file.content_type not in ['image/jpeg', 'image/png']:
        raise HTTPException(status_code=400, detail="Invalid file format")
    
    try:
        image_data = await file.read()
        np_arr = np.frombuffer(image_data, np.uint8)
        image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        if image is None:
            raise ValueError("Error al leer la imagen")

        # Convertir la imagen a escala de grises (opcional pero recomendado para OCR)
        gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        text = pytesseract.image_to_string(gray_image)

        return JSONResponse(content={"extracted_text": text})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to extract text: {str(e)}")
    
#extrae tipo de moneda
# Expresión regular para encontrar tipos de moneda
# Expresión regular para encontrar tipos de moneda
currency_pattern = re.compile(
    r'(\bS\./|\bS/|\bS\s\./|\bS\s/|\$|\$/|\$\s/|\$\s)'
)

@app.post("/extract-dates-and-currencies/")
async def extract_dates_and_currencies(file: UploadFile = File(...)):
    if file.content_type not in ['image/jpeg', 'image/png']:
        raise HTTPException(status_code=400, detail="Invalid file format")
    
    try:
        image = Image.open(file.file)
        text = pytesseract.image_to_string(image)
        
        # Buscar la primera fecha
        date_match = date_pattern.search(text)
        date = date_match.group(0) if date_match else "No encontrado"
        
        # Buscar la primera moneda
        currency_match = currency_pattern.search(text)
        if currency_match:
            currency = currency_match.group(0)
            if 'S' in currency:
                currency = "PEN"
            elif '$' in currency:
                currency = "DOL"
        else:
            currency = "No encontrado"
        
        return JSONResponse(content={"date": date, "currency": currency})
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)
    
#extrae fechas
# Expresión regular para encontrar fechas (formato dd/mm/yyyy, dd-mm-yyyy, yyyy/mm/dd, yyyy-mm-dd)
date_pattern = re.compile(
    r'(\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b|\b\d{2,4}[-/]\d{1,2}[-/]\d{1,2}\b)'
)

@app.post("/extract-dates/")
async def extract_dates(file: UploadFile = File(...)):
    try:
        image = Image.open(file.file)
        text = pytesseract.image_to_string(image)
        dates = date_pattern.findall(text)
        return JSONResponse(content={"dates": dates})
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

# def preprocess_for_ocr(image):
#     # Convertir a escala de grises
#     image = image.convert('L')
#     # Aplicar binarización adaptativa
#     image = ImageOps.autocontrast(image)
#     # Escalar la imagen para mejorar la legibilidad
#     base_width = 600
#     w_percent = (base_width / float(image.size[0]))
#     h_size = int((float(image.size[1]) * float(w_percent)))
#     image = image.resize((base_width, h_size), Image.ANTIALIAS)
#     return image

# @app.post("/extract-text/")
# async def extract_text(file: UploadFile = File(...)):
#     if file.content_type not in ['image/jpeg', 'image/png']:
#         raise HTTPException(status_code=400, detail="Invalid file format")
    
#     try:
#         image_data = await file.read()
#         image = Image.open(io.BytesIO(image_data))
#         processed_image = preprocess_for_ocr(image)
#         text = pytesseract.image_to_string(processed_image, config='--psm 4') # Utilizando el modo PSM 4 para OCR
#         return JSONResponse(content={"extracted_text": text})
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Failed to extract text: {str(e)}")

@app.post("/decode-qr/")
async def decode_qr(file: UploadFile = File(...)):
    if not file.content_type in ['image/jpeg', 'image/png']:
        raise HTTPException(status_code=400, detail="Invalid file format. Please upload a JPEG or PNG image.")
    
    try:
        # Leer los datos de la imagen desde el archivo subido
        contents = await file.read()
        # Convertir los bytes de la imagen a un array numpy
        nparr = np.frombuffer(contents, np.uint8)
        # Decodificar la imagen
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img is None:
            raise HTTPException(status_code=400, detail="Failed to decode image")
        
        # Convertir la imagen a escala de grises
        gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Aplicar umbralización adaptativa
        thresh_img = cv2.adaptiveThreshold(gray_img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)

        # Intentar detectar el QR en la imagen umbralizada
        decoded_objects = decode(thresh_img)
        
        if not decoded_objects:
            # Intentar detectar el QR en la imagen original en escala de grises
            decoded_objects = decode(gray_img)
        
        if not decoded_objects:
            return JSONResponse(content={"detail": "No QR code found in the image"}, status_code=404)
        
        # Extraer y retornar la información del QR code
        qr_data = [obj.data.decode("utf-8") for obj in decoded_objects]
        return JSONResponse(content={"qr_data": qr_data})
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to decode QR code: {str(e)}")

# El resto de tu código permanece igual

# @app.post("/decode-qr/")
# async def decode_qr(file: UploadFile = File(...)):
#     if not file.content_type in ['image/jpeg', 'image/png']:
#         raise HTTPException(status_code=400, detail="Invalid file format. Please upload a JPEG or PNG image.")
    
#     try:
#         # Leer los datos de la imagen desde el archivo subido
#         contents = await file.read()
#         # Convertir los bytes de la imagen a un array numpy
#         nparr = np.fromstring(contents, np.uint8)
#         # Decodificar la imagen
#         img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
#         # Usar QRCodeDetector de OpenCV
#         detector = cv2.QRCodeDetector()
#         data, bbox, straight_qrcode = detector.detectAndDecode(img)
        
#         if not data:
#             return JSONResponse(content={"detail": "No QR code found in the image"}, status_code=404)
        
#         return JSONResponse(content={"qr_data": data})
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Failed to decode QR code: {str(e)}")


#api1
def preprocess_for_ocr2(image):
    # Convertir a escala de grises
    image = image.convert('L')
    # Aplicar binarización adaptativa
    image = ImageOps.autocontrast(image)
    # Escalar la imagen para mejorar la legibilidad
    base_width = 600
    w_percent = (base_width / float(image.size[0]))
    h_size = int((float(image.size[1]) * float(w_percent)))
    image = image.resize((base_width, h_size), Image.Resampling.LANCZOS)  # Usar Image.Resampling.LANCZOS en lugar de ANTIALIAS
    return image

@app.post("/extract-text3/")
async def extract_text(file: UploadFile = File(...)):
    if file.content_type not in ['image/jpeg', 'image/png']:
        raise HTTPException(status_code=400, detail="Invalid file format")
    
    try:
        image_data = await file.read()
        image = Image.open(io.BytesIO(image_data))
        processed_image = preprocess_for_ocr2(image)
        text = pytesseract.image_to_string(processed_image, config='--psm 4')  # Utilizando el modo PSM 4 para OCR
        return JSONResponse(content={"extracted_text": text})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to extract text: {str(e)}")
    
@app.post("/extract-finance-details/")
async def extract_finance_details(file: UploadFile = File(...)):
    if file.content_type not in ['image/jpeg', 'image/png']:
        raise HTTPException(status_code=400, detail="Invalid file format")
    
    try:
        image_data = await file.read()
        image = Image.open(io.BytesIO(image_data))
        processed_image = preprocess_for_ocr2(image)
        text = pytesseract.image_to_string(processed_image, config='--psm 4')

        # Extracción de RUC
        ruc_match = re.search(r'RUC\s*:\s*([\d\s]+)', text)
        ruc = ''.join(ruc_match.group(1).split()) if ruc_match else "No encontrado"

        # Extracción de la fecha de emisión
        fecha_emision_match = re.search(r'F\.Emision:(\d{2}/\d{2}/\d{2})', text)
        fecha_emision = fecha_emision_match.group(1) if fecha_emision_match else "No encontrado"

        # Extracción del número de boleta
        numero_boleta_match = re.search(r'BOLETA DE[\w\s]*\nNumeros”\s*([\w\s\-]+)', text)
        numero_boleta = numero_boleta_match.group(1).strip() if numero_boleta_match else "No encontrado"

        # Extracción del importe total y moneda
        importe_total_match = re.search(r'IMPORTE TOTAL S/\s*(\d+\.\d{2})', text)
        total = importe_total_match.group(1) if importe_total_match else "No encontrado"
        moneda = "PEN" if importe_total_match else "No encontrado"

        return JSONResponse(content={
            "ruc": ruc,
            "fechaEmision": fecha_emision,
            "numeroBoleta": numero_boleta,
            "total": total,
            "moneda": moneda
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to extract financial details: {str(e)}")


def preprocess_for_ocr(image):
    # Convertir a escala de grises
    image = image.convert('L')
    # Aplicar binarización adaptativa
    image = ImageOps.autocontrast(image)
    # Escalar la imagen para mejorar la legibilidad
    base_width = 600
    w_percent = (base_width / float(image.size[0]))
    h_size = int((float(image.size[1]) * float(w_percent)))
    image = image.resize((base_width, h_size), Image.Resampling.LANCZOS)
    return image

@app.post("/extract-finance-data/")
async def extract_finance_data(file: UploadFile = File(...)):
    if file.content_type not in ['image/jpeg', 'image/png']:
        raise HTTPException(status_code=400, detail="Invalid file format")
    
    try:
        image_data = await file.read()
        image = Image.open(io.BytesIO(image_data))
        processed_image = preprocess_for_ocr(image)
        text = pytesseract.image_to_string(processed_image, config='--psm 4')
        
        # Utilizando expresiones regulares para extraer la información necesaria
        ruc = re.search(r'RUC:\s*(\d{11})', text)
        fecha_emision = re.search(r'Fecha Emisión:\s*(\d{2}/\d{2}/\d{4})', text)
        moneda_match = re.search(r'\b(S/|PEN|\$|DOL)', text)
        
        # Determinar la moneda
        if moneda_match:
            if 'S/' in moneda_match.group() or 'PEN' in moneda_match.group():
                moneda = 'PEN'
            elif '$' in moneda_match.group() or 'DOL' in moneda_match.group():
                moneda = 'DOL'
        else:
            moneda = "No encontrado"
        
        response_content = {
            "fecha_solicitud": str(datetime.now().date()),
            "dni": "",
            "usuario": "",
            "gerencia": "",
            "ruc": ruc.group(1) if ruc else "No encontrado",
            "proveedor": "",
            "fecha_emision": fecha_emision.group(1) if fecha_emision else "No encontrado",
            "moneda": moneda,
            "tipo_documento": "",
            "serie": "03",
            "correlativo": "",
            "tipo_gasto": "",
            "sub_total": 0,
            "igv": 0,
            "no_gravadas": 0,
            "importe_facturado": 0,
            "tc": 0,
            "anticipo": 0,
            "total": 200,
            "pago": 0,
            "detalle": "",
            "estado": "",
            "empresa": "",
            "archivo": ""
        }
        
        return JSONResponse(content=response_content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to extract financial data: {str(e)}")
    
@app.post("/decode-qr/")
async def decode_qr(file: UploadFile = File(...)):
    if file.content_type not in ['image/jpeg', 'image/png']:
        raise HTTPException(status_code=400, detail="Invalid file format")
    
    try:
        # Leer la imagen desde el archivo subido
        image_data = await file.read()
        image = Image.open(io.BytesIO(image_data))
        
        # Decodificar QR codes
        decoded_objects = decode(image)
        if not decoded_objects:
            return JSONResponse(content={"detail": "No QR code found in the image"})
        
        # Extraer y retornar la información de todos los QR codes encontrados
        qr_data = [obj.data.decode("utf-8") for obj in decoded_objects]
        return {"qr_data": qr_data}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to decode QR code: {str(e)}")



@app.post("/token", response_model=dict)
async def login_for_access_token(form_data: schemas.UserLogin, db: AsyncSession = Depends(get_db)):
    user = await crud.get_user_by_email(db, email=form_data.email)
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(data={"sub": user.email}, expires_delta=access_token_expires)
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/users/me/", response_model=schemas.User)
async def read_users_me(current_user: schemas.User = Depends(auth.get_current_user)):
    return current_user

@app.post("/users/", response_model=schemas.User)
async def create_user(user: schemas.UserCreate, db: AsyncSession = Depends(get_db)):
    db_user = await crud.get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    return await crud.create_user(db=db, user=user)


@app.get("/users/", response_model=List[schemas.User])
async def read_users(db: AsyncSession = Depends(get_db)):
    return await crud.get_users(db)

@app.get("/users/by-company-and-role/", response_model=List[schemas.User])
async def read_users_by_company_and_role(company_name: str = Query(...), role: str = Query(...), db: AsyncSession = Depends(get_db)):
    users = await crud.get_users_by_company_and_role(db, company_name, role)
    if not users:
        raise HTTPException(status_code=404, detail="No users found for the specified company_name and role")
    return users

@app.get("/users/with-pending-documents/", response_model=List[schemas.UserWithPendingDocuments])
async def read_users_with_pending_documents(empresa: str = Query(...), db: AsyncSession = Depends(get_db)):
    return await crud.get_users_with_pending_documents(db, empresa)

@app.get("/users/by-email/", response_model=schemas.User)
async def read_user_by_email(email: str = Query(...), db: AsyncSession = Depends(get_db)):
    user = await crud.get_user_by_email(db, email=email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

# CRUD para documentos
@app.post("/documentos/", response_model=schemas.Documento)
async def create_documento(documento: schemas.DocumentoCreate, db: AsyncSession = Depends(get_db)):
    return await crud.create_documento(db=db, documento=documento)

@app.get("/documentos/{documento_id}", response_model=schemas.Documento)
async def read_documento(documento_id: int, db: AsyncSession = Depends(get_db)):
    db_documento = await crud.get_documento(db, documento_id=documento_id)
    if db_documento is None:
        raise HTTPException(status_code=404, detail="Documento not found")
    return db_documento

@app.get("/documentos/", response_model=List[schemas.Documento])
async def read_documentos(
    empresa: str = Query(None, alias="company_name"),
    estado: str = Query(None),
    username: str = Query(None),
    db: AsyncSession = Depends(get_db)
):
    query = select(models.Documento).filter(models.Documento.empresa == empresa)
    if estado:
        query = query.filter(models.Documento.estado == estado)
    if username:
        query = query.filter(models.Documento.usuario == username)
    result = await db.execute(query)
    return result.scalars().all()

@app.put("/documentos/{documento_id}", response_model=schemas.Documento)
async def update_documento(documento_id: int, documento: schemas.DocumentoUpdate, db: AsyncSession = Depends(get_db)):
    db_documento = await crud.get_documento(db, documento_id=documento_id)
    if not db_documento:
        raise HTTPException(status_code=404, detail="Documento not found")
    
    update_data = documento.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_documento, key, value)
    
    await db.commit()
    await db.refresh(db_documento)
    return db_documento

@app.delete("/documentos/{documento_id}", response_model=schemas.Documento)
async def delete_documento(documento_id: int, db: AsyncSession = Depends(get_db)):
    return await crud.delete_documento(db=db, documento_id=documento_id)

@app.post("/documentos/{documento_id}/upload", response_model=schemas.Documento)
async def upload_file(documento_id: int, file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    file_location = f"C:/archivos/{file.filename}"
    with open(file_location, "wb") as f:
        shutil.copyfileobj(file.file, f)
    
    documento = await crud.get_documento(db, documento_id=documento_id)
    documento.archivo = file_location
    await db.commit()
    await db.refresh(documento)
    return documento

@app.get("/documentos/download/")
async def download_file(file_location: str):
    if not os.path.exists(file_location):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path=file_location, filename=os.path.basename(file_location), media_type='application/octet-stream')

@app.get("/documentos/view/")
async def view_file(file_location: str):
    if not os.path.exists(file_location):
        raise HTTPException(status_code=404, detail="File not found")
    media_type, _ = guess_type(file_location)
    return FileResponse(path=file_location, media_type=media_type)

# @app.get("/documentos/export/excel")
# async def export_documentos_excel(
#     empresa: str = Query(None, alias="company_name"),
#     estado: str = Query(None),
#     username: str = Query(None),
#     db: AsyncSession = Depends(get_db)
# ):
#     query = select(models.Documento).filter(models.Documento.empresa == empresa)
#     if estado:
#         query = query.filter(models.Documento.estado == estado)
#     if username:
#         query = query.filter(models.Documento.usuario == username)
    
#     result = await db.execute(query)
#     documentos = result.scalars().all()

#     df = pd.DataFrame([doc.__dict__ for doc in documentos])
#     df.drop(columns=['_sa_instance_state', 'archivo', 'estado'], inplace=True)

#     excel_file = f"documentos.xlsx"
#     df.to_excel(excel_file, index=False)
#     return FileResponse(path=excel_file, filename="documentos.xlsx")

@app.get("/documentos/export/excel")
async def export_documentos_excel(
    empresa: str = Query(None, alias="company_name"),
    estado: str = Query(None),
    username: str = Query(None),
    db: AsyncSession = Depends(get_db)
):
    query = select(models.Documento).filter(models.Documento.empresa == empresa)
    if estado:
        query = query.filter(models.Documento.estado == estado)
    if username:
        query = query.filter(models.Documento.usuario == username)
    
    result = await db.execute(query)
    documentos = result.scalars().all()

    # Crear DataFrame con las columnas necesarias
    df = pd.DataFrame([{
        "Item": i + 1,
        "Fecha": doc.fecha_emision,
        "RUC": doc.ruc,
        "TipoDoc": doc.tipo_documento,
        "Cuenta Contable": doc.cuenta_contable,
        "Serie": doc.serie,
        "Correlativo": doc.correlativo,
        "Rubro": doc.rubro,
        "Moneda": doc.moneda,
        "Tipo de Cambio": doc.tc,
        "Afecto": doc.afecto,
        "IGV": doc.igv,
        "Inafecto": doc.inafecto,
        "Total": doc.total
    } for i, doc in enumerate(documentos)])

    excel_file = f"documentos.xlsx"
    df.to_excel(excel_file, index=False)
    return FileResponse(path=excel_file, filename="documentos.xlsx")


# @app.get("/documentos/export/pdf")
# async def export_documentos_pdf(
#     empresa: str = Query(None, alias="company_name"),
#     estado: str = Query(None),
#     username: str = Query(None),
#     db: AsyncSession = Depends(get_db)
# ):
#     query = select(models.Documento).filter(models.Documento.empresa == empresa)
#     if estado:
#         query = query.filter(models.Documento.estado == estado)
#     if username:
#         query = query.filter(models.Documento.usuario == username)
    
#     result = await db.execute(query)
#     documentos = result.scalars().all()

#     pdf = FPDF(orientation='L')
#     pdf.add_page()
#     pdf.set_font("Arial", size=8)

#     # Define the table header
#     table_header = ["RUC", "Proveedor", "Fecha Emisión", "Moneda", "Tipo Documento", 
#                     "Serie", "Correlativo", "Tipo Gasto", "Sub Total", "IGV", 
#                     "No Gravadas", "Importe Facturado", "TC"]

#     col_width = pdf.w / len(table_header)  # Distribute the width evenly
#     row_height = pdf.font_size * 1.5

#     # Add the table header
#     for header in table_header:
#         pdf.cell(col_width, row_height, header, border=1)
#     pdf.ln(row_height)

#     # Add the table data
#     for doc in documentos:
#         pdf.cell(col_width, row_height, doc.ruc, border=1)
#         pdf.cell(col_width, row_height, doc.proveedor, border=1)
#         pdf.cell(col_width, row_height, str(doc.fecha_emision), border=1)
#         pdf.cell(col_width, row_height, doc.moneda, border=1)
#         pdf.cell(col_width, row_height, doc.tipo_documento, border=1)
#         pdf.cell(col_width, row_height, doc.serie, border=1)
#         pdf.cell(col_width, row_height, doc.correlativo, border=1)
#         pdf.cell(col_width, row_height, doc.tipo_gasto, border=1)
#         pdf.cell(col_width, row_height, str(doc.sub_total), border=1)
#         pdf.cell(col_width, row_height, str(doc.igv), border=1)
#         pdf.cell(col_width, row_height, str(doc.no_gravadas), border=1)
#         pdf.cell(col_width, row_height, str(doc.importe_facturado), border=1)
#         pdf.cell(col_width, row_height, str(doc.tc), border=1)
#         pdf.ln(row_height)

#     pdf_file = f"documentos.pdf"
#     pdf.output(pdf_file)
#     return FileResponse(path=pdf_file, filename="documentos.pdf")

#este ok
# @app.get("/documentos/export/pdf")
# async def export_documentos_pdf(
#     empresa: str = Query(None, alias="company_name"),
#     estado: str = Query(None),
#     username: str = Query(None),
#     db: AsyncSession = Depends(get_db)
# ):
#     query = select(models.Documento).filter(models.Documento.empresa == empresa)
#     if estado:
#         query = query.filter(models.Documento.estado == estado)
#     if username:
#         query = query.filter(models.Documento.usuario == username)
    
#     result = await db.execute(query)
#     documentos = result.scalars().all()

#     pdf = FPDF(orientation='L')
#     pdf.add_page()
#     pdf.set_font("Arial", size=8)

#     # Define the table header
#     table_header = ["Item", "Fecha", "RUC", "TipoDoc", "Cuenta Contable", "Serie", "Correlativo", 
#                     "Rubro", "Moneda", "Tipo de Cambio", "Afecto", "IGV", "Inafecto", "Total"]

#     col_width = pdf.w / len(table_header)  # Distribute the width evenly
#     row_height = pdf.font_size * 1.5

#     # Add the table header
#     for header in table_header:
#         pdf.cell(col_width, row_height, header, border=1)
#     pdf.ln(row_height)

#     # Add the table data
#     for i, doc in enumerate(documentos):
#         pdf.cell(col_width, row_height, str(i + 1), border=1)
#         pdf.cell(col_width, row_height, str(doc.fecha_emision), border=1)
#         pdf.cell(col_width, row_height, doc.ruc, border=1)
#         pdf.cell(col_width, row_height, doc.tipo_documento, border=1)
#         pdf.cell(col_width, row_height, str(doc.cuenta_contable), border=1)
#         pdf.cell(col_width, row_height, doc.serie, border=1)
#         pdf.cell(col_width, row_height, doc.correlativo, border=1)
#         pdf.cell(col_width, row_height, doc.rubro, border=1)
#         pdf.cell(col_width, row_height, doc.moneda, border=1)
#         pdf.cell(col_width, row_height, str(doc.tc), border=1)
#         pdf.cell(col_width, row_height, str(doc.afecto), border=1)
#         pdf.cell(col_width, row_height, str(doc.igv), border=1)
#         pdf.cell(col_width, row_height, str(doc.inafecto), border=1)
#         pdf.cell(col_width, row_height, str(doc.total), border=1)
#         pdf.ln(row_height)

#     pdf_file = f"documentos.pdf"
#     pdf.output(pdf_file)
#     return FileResponse(path=pdf_file, filename="documentos.pdf")



# @app.get("/documentos/export/pdf")
# async def export_documentos_pdf(
#     empresa: str = Query(None, alias="company_name"),
#     estado: str = Query(None),
#     username: str = Query(None),
#     db: AsyncSession = Depends(get_db)
# ):
#     query = select(models.Documento).filter(models.Documento.empresa == empresa)
#     if estado:
#         query = query.filter(models.Documento.estado == estado)
#     if username:
#         query = query.filter(models.Documento.usuario == username)
    
#     result = await db.execute(query)
#     documentos = result.scalars().all()

#     pdf = FPDF()
#     pdf.add_page()
#     pdf.set_font("Arial", size=12)

#     # Define the table header
#     table_header = ["RUC", "Proveedor", "Fecha Emisión", "Moneda", "Tipo Documento", 
#                     "Serie", "Correlativo", "Tipo Gasto", "Sub Total", "IGV", 
#                     "No Gravadas", "Importe Facturado", "TC"]

#     col_width = pdf.w / len(table_header)  # Distribute the width evenly
#     row_height = pdf.font_size * 1.5

#     # Add the table header
#     for header in table_header:
#         pdf.cell(col_width, row_height, header, border=1)
#     pdf.ln(row_height)

#     # Add the table data
#     for doc in documentos:
#         pdf.cell(col_width, row_height, doc.ruc, border=1)
#         pdf.cell(col_width, row_height, doc.proveedor, border=1)
#         pdf.cell(col_width, row_height, str(doc.fecha_emision), border=1)
#         pdf.cell(col_width, row_height, doc.moneda, border=1)
#         pdf.cell(col_width, row_height, doc.tipo_documento, border=1)
#         pdf.cell(col_width, row_height, doc.serie, border=1)
#         pdf.cell(col_width, row_height, doc.correlativo, border=1)
#         pdf.cell(col_width, row_height, doc.tipo_gasto, border=1)
#         pdf.cell(col_width, row_height, str(doc.sub_total), border=1)
#         pdf.cell(col_width, row_height, str(doc.igv), border=1)
#         pdf.cell(col_width, row_height, str(doc.no_gravadas), border=1)
#         pdf.cell(col_width, row_height, str(doc.importe_facturado), border=1)
#         pdf.cell(col_width, row_height, str(doc.tc), border=1)
#         pdf.ln(row_height)

#     pdf_file = f"documentos.pdf"
#     pdf.output(pdf_file)
#     return FileResponse(path=pdf_file, filename="documentos.pdf")

@app.delete("/documentos/{documento_id}/file", response_model=schemas.Documento)
async def delete_documento_file(documento_id: int, db: AsyncSession = Depends(get_db)):
    documento = await crud.get_documento(db, documento_id=documento_id)
    if os.path.exists(documento.archivo):
        os.remove(documento.archivo)
    documento.archivo = None
    await db.commit()
    await db.refresh(documento)
    return documento

@app.get("/companies/", response_model=List[schemas.Company])
async def read_companies(db: AsyncSession = Depends(get_db)):
    return await crud.get_companies(db)

@app.post("/companies/", response_model=schemas.Company)
async def create_company(company: schemas.CompanyCreate, db: AsyncSession = Depends(get_db)):
    return await crud.create_company(db=db, company=company)

@app.put("/companies/{company_id}", response_model=schemas.Company)
async def update_company(company_id: int, company: schemas.CompanyCreate, db: AsyncSession = Depends(get_db)):
    db_company = await crud.update_company(db, company_id, company)
    if not db_company:
        raise HTTPException(status_code=404, detail="Company not found")
    return db_company

@app.delete("/companies/{company_id}", response_model=schemas.Company)
async def delete_company(company_id: int, db: AsyncSession = Depends(get_db)):
    db_company = await crud.delete_company(db, company_id)
    if not db_company:
        raise HTTPException(status_code=404, detail="Company not found")
    return db_company

###################################pdf
# class PDF(FPDF):
#     def header(self):
#         self.set_font('Arial', 'B', 12)
#         self.cell(0, 10, 'RENDICION DE GASTOS', 0, 1, 'C')

#     def chapter_title(self, title):
#         self.set_font('Arial', 'B', 12)
#         self.cell(0, 10, title, 0, 1, 'L')
#         self.ln(5)

#     def chapter_body(self, body):
#         self.set_font('Arial', '', 12)
#         self.multi_cell(0, 10, body)
#         self.ln()

#     def add_table(self, header, data):
#         self.set_font('Arial', 'B', 12)
#         col_width = self.w / len(header)  # Distribute the width evenly
#         row_height = self.font_size * 1.5
        
#         for item in header:
#             self.cell(col_width, row_height, item, border=1)
#         self.ln(row_height)

#         self.set_font('Arial', '', 12)
#         for row in data:
#             for item in row:
#                 self.cell(col_width, row_height, str(item), border=1)
#             self.ln(row_height)

#     def add_totals(self, total_fondo_fijo, total_gasto, reembolso):
#         self.set_font('Arial', 'B', 12)
#         self.cell(0, 10, f'Total Fondo Fijo: {total_fondo_fijo}', 0, 1, 'L')
#         self.cell(0, 10, f'Total Gasto: {total_gasto}', 0, 1, 'L')
#         self.cell(0, 10, f'Reembolsar / (-)Devolver: {reembolso}', 0, 1, 'L')
#         self.ln()

#     def add_firmas(self):
#         self.set_font('Arial', '', 12)
#         self.cell(0, 10, 'Solicitado por:_________________', 0, 1, 'L')
#         self.cell(0, 10, 'Autorizado por:_________________', 0, 1, 'L')
#         self.cell(0, 10, 'Recibido por:___________________', 0, 1, 'L')

# @app.get("/documentos/export/pdf4")
# async def export_documentos_pdf(
#     empresa: str = Query(None, alias="company_name"),
#     estado: str = Query(None),
#     username: str = Query(None),
#     db: AsyncSession = Depends(get_db)
# ):
#     query = select(models.Documento).filter(models.Documento.empresa == empresa)
#     if estado:
#         query = query.filter(models.Documento.estado == estado)
#     if username:
#         query = query.filter(models.Documento.usuario == username)
    
#     result = await db.execute(query)
#     documentos = result.scalars().all()

#     pdf = PDF(orientation='L')
#     pdf.add_page()
    
#     # Header information
#     pdf.chapter_title('Usuario Yerson Chacon Saenz')
#     pdf.chapter_body('''
#     Area Responsable: Area Comercial
#     DNI: 465XXXXX
#     Fecha de Solicitud: 25/06/2024
#     Cargo: Vendedor de Norte
#     Fecha de Rendicion: 1/07/2024
#     CECO / Zona de Venta: PE1000010
#     Tipo de Gasto: Local
#     ''')

#     # Table
#     table_header = ["Fecha", "RUC", "Tipo de Doc", "Serie", "Número", "Rubro", "Moneda", "Tipo de cambio", "Afecto IGV", "Inafecto", "Total"]
#     table_data = [
#         [doc.fecha_emision, doc.ruc, doc.tipo_documento, doc.serie, doc.correlativo, doc.tipo_gasto, doc.moneda, doc.tc, doc.igv, doc.no_gravadas, doc.total]
#         for doc in documentos
#     ]
#     pdf.add_table(table_header, table_data)

#     # Totals and signatures
#     total_fondo_fijo = 3000.00  # Se asume que es una cantidad fija
#     total_gasto = sum(doc.total for doc in documentos)
#     reembolso = total_fondo_fijo - total_gasto
#     pdf.add_totals(total_fondo_fijo, total_gasto, reembolso)
#     pdf.add_firmas()

#     pdf_file = f"documentos.pdf"
#     pdf.output(pdf_file)
#     return FileResponse(path=pdf_file, filename="documentos.pdf")

class PDF(FPDF):
    def header(self):
        # Logo
        logo_path = 'C:\\logo\\logo.png'
        self.image(logo_path, 10, 8, 33)  # Ajusta la ruta y el tamaño del logo
        self.ln(20)  # Espacio debajo del logo para separarlo del contenido

        # Usuario y datos asociados
        self.set_font('Arial', '', 8)  # Cambiar el tamaño de la fuente a 8 puntos
        self.set_xy(10, 30)  # Ajustar la posición del contenido debajo del logo
        self.cell(0, 10, f'Usuario: {self.usuario}', 0, 1, 'L')
        self.set_xy(10, 40)
        self.cell(0, 10, f'DNI: {self.dni}', 0, 1, 'L')
        self.set_xy(10, 50)
        self.cell(0, 10, f'Cargo: {self.cargo}', 0, 1, 'L')
        self.set_xy(10, 60)
        self.cell(0, 10, f'Zona: {self.zona}', 0, 1, 'L')

        # Área responsable y otros datos
        self.set_xy(-95, 30)
        self.cell(0, 10, f'Área responsable: {self.area_responsable}', 0, 1, 'R')
        self.set_xy(-95, 40)
        self.cell(0, 10, f'Fecha de solicitud: {self.fecha_solicitud}', 0, 1, 'R')
        self.set_xy(-95, 50)
        self.cell(0, 10, f'Fecha de rendición: {self.fecha_rendicion}', 0, 1, 'R')
        self.set_xy(-95, 60)
        self.cell(0, 10, f'Tipo de gasto: {self.tipo_gasto}', 0, 1, 'R')

        self.ln(20)

    def add_table(self, header, data):
        self.set_font('Arial', 'B', 8)  # Cambiar el tamaño de la fuente a 8 puntos
        col_width = (self.w - 20) / len(header)  # Ajustar el ancho de las columnas, con un margen de 10 unidades en cada lado
        row_height = self.font_size * 1.5
        
        # Header with background color
        self.set_fill_color(0, 0, 139)  # Azul
        self.set_text_color(255, 255, 255)  # Blanco
        for item in header:
            self.cell(col_width, row_height, item, border=1, fill=True)
        self.ln(row_height)

        self.set_font('Arial', '', 8)  # Cambiar el tamaño de la fuente a 8 puntos
        self.set_text_color(0, 0, 0)  # Negro para el texto de los datos
        for row in data:
            for item in row:
                self.cell(col_width, row_height, str(item), border=1)
            self.ln(row_height)

    def add_firmas(self, total_anticipo, total_gasto, reembolso):
        col_width = (self.w - 30) / 4  # Ancho dividido en 4 partes con margen
        spacing = 5  # Espaciado entre los cuadros

        self.set_font('Arial', '', 8)  # Cambiar el tamaño de la fuente a 8 puntos

        # Añadir separación antes del bloque de firmas
        self.ln(10)

        # Primera fila de cuadros
        self.cell(col_width, 10, 'Solicitado por:', border=1, ln=0, align='L')
        self.cell(spacing, 10, '', border=0, ln=0)  # Espacio
        self.cell(col_width, 10, 'Autorizado por:', border=1, ln=0, align='L')
        self.cell(spacing, 10, '', border=0, ln=0)  # Espacio
        self.cell(col_width, 10, 'Recibido por:', border=1, ln=0, align='L')
        self.cell(spacing, 10, '', border=0, ln=0)  # Espacio
        self.cell(col_width, 10, f'Total Anticipo: {total_anticipo}', border=1, ln=1, align='L')

        # Segunda fila de cuadros con "Nombre" alineado a la derecha
        self.cell(col_width, 10, 'Nombre', border=1, ln=0, align='R')
        self.cell(spacing, 10, '', border=0, ln=0)  # Espacio
        self.cell(col_width, 10, 'Nombre', border=1, ln=0, align='R')
        self.cell(spacing, 10, '', border=0, ln=0)  # Espacio
        self.cell(col_width, 10, 'Nombre', border=1, ln=0, align='R')
        self.cell(spacing, 10, '', border=0, ln=0)  # Espacio
        self.cell(col_width, 10, f'Total Gasto: {total_gasto}', border=1, ln=1, align='L')

        # Tercera fila de cuadros para el reembolso
        self.cell(col_width, 10, ' ', border=0, ln=0, align='L')  # Espacio en blanco
        self.cell(spacing, 10, '', border=0, ln=0)  # Espacio
        self.cell(col_width, 10, ' ', border=0, ln=0, align='L')  # Espacio en blanco
        self.cell(spacing, 10, '', border=0, ln=0)  # Espacio
        self.cell(col_width, 10, ' ', border=0, ln=0, align='L')  # Espacio en blanco
        self.cell(spacing, 10, '', border=0, ln=0)  # Espacio
        self.cell(col_width, 10, f'Reembolsar / (-)Devolver: {reembolso}', border=1, ln=1, align='L')

@app.get("/documentos/export/pdf")
async def export_documentos_pdf(
    empresa: str = Query(None, alias="company_name"),
    estado: str = Query(None),
    username: str = Query(None),
    db: AsyncSession = Depends(get_db)
):
    query = select(models.Documento).filter(models.Documento.empresa == empresa)
    if estado:
        query = query.filter(models.Documento.estado == estado)
    if username:
        query = query.filter(models.Documento.usuario == username)
    
    result = await db.execute(query)
    documentos = result.scalars().all()

    total_gasto = sum(doc.total for doc in documentos)
    total_anticipo = 3000.00  # Puedes ajustar este valor según sea necesario
    reembolso = total_anticipo - total_gasto

    pdf = PDF(orientation='L')
    pdf.usuario = "Nombre del usuario"
    pdf.dni = "DNI del usuario"
    pdf.cargo = "Cargo del usuario"
    pdf.zona = "Zona del usuario"
    pdf.area_responsable = "Área Responsable"
    pdf.fecha_solicitud = "Fecha de Solicitud"
    pdf.fecha_rendicion = "Fecha de Rendición"
    pdf.tipo_gasto = "Tipo de Gasto"
    pdf.total_anticipo = total_anticipo
    pdf.total_gasto = total_gasto
    pdf.reembolso = reembolso

    pdf.add_page()

    # Table
    table_header = ["Item", "Fecha", "RUC", "TipoDoc", "Cuenta Contable", "Serie", "Correlativo", 
                    "Rubro", "Moneda", "Tipo de Cambio", "Afecto", "IGV", "Inafecto", "Total"]
    table_data = [
        [i + 1, doc.fecha_emision, doc.ruc, doc.tipo_documento, doc.cuenta_contable, doc.serie, doc.correlativo, 
         doc.rubro, doc.moneda, doc.tc, doc.afecto, doc.igv, doc.inafecto, doc.total]
        for i, doc in enumerate(documentos)
    ]
    pdf.add_table(table_header, table_data)

    # Totals and signatures
    pdf.add_firmas(pdf.total_anticipo, pdf.total_gasto, pdf.reembolso)

    pdf_file = f"documentos.pdf"
    pdf.output(pdf_file)
    return FileResponse(path=pdf_file, filename="documentos.pdf")

