from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List
from datetime import date, timedelta
import shutil
import os
import pandas as pd
from fpdf import FPDF
from fastapi.responses import FileResponse, JSONResponse
from mimetypes import guess_type
from . import crud, models, schemas, auth
from .database import engine, SessionLocal
import pytesseract
import io
from PIL import Image, ImageOps
from pyzbar.pyzbar import decode
from datetime import datetime
import re
import cv2
import numpy as np
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
API_URL = "https://api.apis.net.pe/v2/sunat/tipo-cambio"

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
        
# Aquí añadimos el nuevo endpoint para obtener el tipo de cambio
@app.get("/tipo-cambio/", response_model=schemas.TipoCambioResponse)
async def obtener_tipo_cambio(fecha: str):
    headers = {
        "Authorization": f"Bearer {API_TOKEN}"
    }
    params = {
        "date": fecha
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(API_URL, headers=headers, params=params)
        
        if response.status_code == 200:
            return response.json()
        else:
            raise HTTPException(status_code=response.status_code, detail="Error al consultar el tipo de cambio")


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
async def extract_text6(file: UploadFile = File(...)):
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

# RegEx para encontrar tipos de moneda
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
    
# RegEx para encontrar fechas (formato dd/mm/yyyy, dd-mm-yyyy, yyyy/mm/dd, yyyy-mm-dd)
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

# Decodificación de QR
@app.post("/decode-qr-other/")
async def decode_qr_other(file: UploadFile = File(...)):
    if not file.content_type in ['image/jpeg', 'image/png']:
        raise HTTPException(status_code=400, detail="Invalid file format. Please upload a JPEG or PNG image.")
    
    try:
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img is None:
            raise HTTPException(status_code=400, detail="Failed to decode image")
        
        gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        thresh_img = cv2.adaptiveThreshold(gray_img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
        decoded_objects = decode(thresh_img)
        
        if not decoded_objects:
            decoded_objects = decode(gray_img)
        
        if not decoded_objects:
            return JSONResponse(content={"detail": "No QR code found in the image"}, status_code=404)
        
        qr_data = [obj.data.decode("utf-8") for obj in decoded_objects]
        return JSONResponse(content={"qr_data": qr_data})
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to decode QR code: {str(e)}")

def preprocess_for_ocr2(image):
    image = image.convert('L')
    image = ImageOps.autocontrast(image)
    base_width = 600
    w_percent = (base_width / float(image.size[0]))
    h_size = int((float(image.size[1]) * float(w_percent)))
    image = image.resize((base_width, h_size), Image.Resampling.LANCZOS)
    return image

@app.post("/extract-finance-details/")
async def extract_finance_details(file: UploadFile = File(...)):
    if file.content_type not in ['image/jpeg', 'image/png']:
        raise HTTPException(status_code=400, detail="Invalid file format")
    
    try:
        image_data = await file.read()
        image = Image.open(io.BytesIO(image_data))
        processed_image = preprocess_for_ocr2(image)
        text = pytesseract.image_to_string(processed_image, config='--psm 4')

        ruc_match = re.search(r'RUC\s*:\s*([\d\s]+)', text)
        ruc = ''.join(ruc_match.group(1).split()) if ruc_match else "No encontrado"

        fecha_emision_match = re.search(r'F\.Emision:(\d{2}/\d{2}/\d{2})', text)
        fecha_emision = fecha_emision_match.group(1) if fecha_emision_match else "No encontrado"

        numero_boleta_match = re.search(r'BOLETA DE[\w\s]*\nNumeros”\s*([\w\s\-]+)', text)
        numero_boleta = numero_boleta_match.group(1).strip() if numero_boleta_match else "No encontrado"

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

@app.post("/extract-finance-data/")
async def extract_finance_data(file: UploadFile = File(...)):
    if file.content_type not in ['image/jpeg', 'image/png']:
        raise HTTPException(status_code=400, detail="Invalid file format")
    
    try:
        image_data = await file.read()
        image = Image.open(io.BytesIO(image_data))
        processed_image = preprocess_for_ocr2(image)
        text = pytesseract.image_to_string(processed_image, config='--psm 4')
        
        ruc = re.search(r'RUC:\s*(\d{11})', text)
        fecha_emision = re.search(r'Fecha Emisión:\s*(\d{2}/\d{2}/\d{4})', text)
        moneda_match = re.search(r'\b(S/|PEN|\$|DOL)', text)
        
        if moneda_match:
            if 'S/' in moneda_match.group() or 'PEN' in moneda_match.group():
                moneda = 'PEN'
            elif '$' in moneda_match.group() or 'DOL' in moneda_match.group():
                moneda = 'USD'
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
        image_data = await file.read()
        image = Image.open(io.BytesIO(image_data))
        
        decoded_objects = decode(image)
        if not decoded_objects:
            return JSONResponse(content={"detail": "No QR code found in the image"})

        qr_data = decoded_objects[0].data.decode("utf-8").split("|")
        
        result = {}

        for data in qr_data:
            if re.match(r'^\d{8}$', data):  # Dato de 8 dígitos (DNI)
                result["dni"] = data
            elif re.match(r'^\d{11}$', data):  # Dato de 11 dígitos (RUC)
                result["ruc"] = data
            elif re.match(r'^\d{2}$', data):  # Dato de 2 dígitos (Tipo de Documento)
                tipo_doc_map = {
                    "01": "Factura",
                    "02": "Recibo por Honorarios",
                    "03": "Boleta de Venta",
                    "05": "Boleto Aéreo",
                    "07": "Nota de Crédito",
                    "08": "Nota de Débito",
                    "12": "Ticket o cinta emitido por máquina registradora",
                    "14": "Recibo Servicio Público"
                }
                result["tipo"] = tipo_doc_map.get(data, "Desconocido")
            elif re.match(r'^[A-Za-z0-9]{4}-\d{7,8}$', data):  # Dato con formato xxxx-aaaaaaaa (Serie-Número)
                serie, numero = data.split('-')
                result["serie"] = serie
                result["numero"] = numero
            elif re.match(r'^\d+\.\d{2}$', data):  # Dato de valor decimal
                if "total" not in result or float(data) > float(result["total"]):
                    if "total" in result:
                        result["igv"] = result["total"]
                    result["total"] = data
                else:
                    result["igv"] = data
            elif re.match(r'^\d{4}-\d{2}-\d{2}$', data) or re.match(r'^\d{2}/\d{2}/\d{4}$', data):  # Fecha
                result["fecha"] = data

        return JSONResponse(content=result)
    
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

# @app.get("/documentos/", response_model=List[schemas.Documento])
# async def read_documentos(
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
#     return result.scalars().all()

@app.get("/documentos/", response_model=List[schemas.DocumentoBase])
async def read_documentos(
    empresa: str = Query(None, alias="company_name"),
    estado: str = Query(None),
    username: str = Query(None),
    tipo_gasto: str = Query(None, description="Filtrar por tipo de gasto"),
    tipo_solicitud: str = Query(None, description="Filtrar por tipo de documento"),
    tipo_anticipo: str = Query(None, description="Filtrar por tipo de anticipo"),
    fecha_solicitud_from: date = Query(None, description="Fecha de solicitud desde"),
    fecha_solicitud_to: date = Query(None, description="Fecha de solicitud hasta"),
    db: AsyncSession = Depends(get_db)
):
    query = select(models.Documento).where(models.Documento.empresa == empresa)
    if estado:
        query = query.where(models.Documento.estado == estado)
    if username:
        query = query.where(models.Documento.usuario == username)
    if tipo_gasto:
        query = query.where(models.Documento.tipo_gasto == tipo_gasto)
    if tipo_solicitud:
        query = query.where(models.Documento.tipo_solicitud == tipo_solicitud)
    if tipo_anticipo:
        query = query.where(models.Documento.tipo_anticipo == tipo_anticipo)
    if fecha_solicitud_from:
        query = query.where(models.Documento.fecha_solicitud >= fecha_solicitud_from)
    if fecha_solicitud_to:
        query = query.where(models.Documento.fecha_solicitud <= fecha_solicitud_to)

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

@app.post("/documentos/con-archivo", response_model=schemas.Documento)
async def create_documento_con_archivo(
    documento: schemas.DocumentoCreate, 
    file: UploadFile = File(...), 
    db: AsyncSession = Depends(get_db)
):
    db_documento = await crud.create_documento(db=db, documento=documento)
    
    file_location = f"C:/archivos/{file.filename}"
    with open(file_location, "wb") as f:
        shutil.copyfileobj(file.file, f)
    
    db_documento.archivo = file_location
    await db.commit()
    await db.refresh(db_documento)
    
    return db_documento

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

    df = pd.DataFrame([{
        "Item": i + 1,
        "Fecha": doc.fecha_emision,
        "RUC": doc.ruc,
        "TipoDoc": doc.tipo_documento,
        "Cuenta Contable": doc.cuenta_contable,
        "Serie": doc.serie,
        "Correlativo": doc.correlativo,
        #"Rubro": doc.rubro,
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

class PDF(FPDF):
    def header(self):
        # Logo
        logo_path = 'C:\\logo\\logo.png'
        self.image(logo_path, 10, 8, 33)
        self.ln(20)

        # Usuario y datos asociados
        self.set_font('Arial', '', 8)
        self.set_xy(10, 30)
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
        self.set_font('Arial', 'B', 8)
        col_width = (self.w - 20) / len(header)
        row_height = self.font_size * 1.5
        
        self.set_fill_color(0, 0, 139)
        self.set_text_color(255, 255, 255)
        for item in header:
            self.cell(col_width, row_height, item, border=1, fill=True)
        self.ln(row_height)

        self.set_font('Arial', '', 8)
        self.set_text_color(0, 0, 0)
        for row in data:
            for item in row:
                self.cell(col_width, row_height, str(item), border=1)
            self.ln(row_height)

    def add_firmas(self, total_anticipo, total_gasto, reembolso):
        col_width = (self.w - 30) / 4
        spacing = 5

        self.set_font('Arial', '', 8)

        self.ln(10)

        self.cell(col_width, 10, 'Solicitado por:', border=1, ln=0, align='L')
        self.cell(spacing, 10, '', border=0, ln=0)
        self.cell(col_width, 10, 'Autorizado por:', border=1, ln=0, align='L')
        self.cell(spacing, 10, '', border=0, ln=0)
        self.cell(col_width, 10, 'Recibido por:', border=1, ln=0, align='L')
        self.cell(spacing, 10, '', border=0, ln=0)
        self.cell(col_width, 10, f'Total Anticipo: {total_anticipo}', border=1, ln=1, align='L')

        self.cell(col_width, 10, 'Nombre', border=1, ln=0, align='R')
        self.cell(spacing, 10, '', border=0, ln=0)
        self.cell(col_width, 10, 'Nombre', border=1, ln=0, align='R')
        self.cell(spacing, 10, '', border=0, ln=0)
        self.cell(col_width, 10, 'Nombre', border=1, ln=0, align='R')
        self.cell(spacing, 10, '', border=0, ln=0)
        self.cell(col_width, 10, f'Total Gasto: {total_gasto}', border=1, ln=1, align='L')

        self.cell(col_width, 10, ' ', border=0, ln=0, align='L')
        self.cell(spacing, 10, '', border=0, ln=0)
        self.cell(col_width, 10, ' ', border=0, ln=0, align='L')
        self.cell(spacing, 10, '', border=0, ln=0)
        self.cell(col_width, 10, ' ', border=0, ln=0, align='L')
        self.cell(spacing, 10, '', border=0, ln=0)
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
    total_anticipo = 3000.00
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

    table_header = ["Item", "Fecha", "RUC", "Tip. Doc", "Cta Contable", "Serie", "Correlativo", 
                    "Moneda", "Tip. Cambio", "Afecto", "IGV", "Inafecto", "Total"]
    table_data = [
        [i + 1, doc.fecha_emision, doc.ruc, doc.tipo_documento, doc.cuenta_contable, doc.serie, doc.correlativo, 
          doc.moneda, doc.tc, doc.afecto, doc.igv, doc.inafecto, doc.total]
        for i, doc in enumerate(documentos)
    ]
    pdf.add_table(table_header, table_data)

    pdf.add_firmas(pdf.total_anticipo, pdf.total_gasto, pdf.reembolso)

    pdf_file = f"documentos.pdf"
    pdf.output(pdf_file)
    return FileResponse(path=pdf_file, filename="documentos.pdf")


#guardar archivo 
# Asegúrate de que la ruta de destino exista
UPLOAD_DIRECTORY = "C:\\archivos"
if not os.path.exists(UPLOAD_DIRECTORY):
    os.makedirs(UPLOAD_DIRECTORY)

@app.post("/upload-file/")
async def upload_file(file: UploadFile = File(...)):
    try:
        # Define la ruta completa del archivo
        file_location = os.path.join(UPLOAD_DIRECTORY, file.filename)
        
        # Guarda el archivo en la ruta especificada
        with open(file_location, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Normaliza la ruta para Windows
        normalized_path = file_location.replace("\\", "/")

        # Devuelve la ruta del archivo guardado
        return {"file_location": normalized_path}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al guardar el archivo: {str(e)}")
    
 # Definir la ruta de almacenamiento de los PDFs
PDF_DIRECTORY = "C:\\boleta"
if not os.path.exists(PDF_DIRECTORY):
    os.makedirs(PDF_DIRECTORY)

async def get_db():
    async with SessionLocal() as session:
        yield session

# Clase para generar el PDF
class DocumentoPDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, 'Detalles del Documento', 0, 1, 'C')

    def add_document_details(self, documento: schemas.DocumentoCreate):
        self.set_font('Arial', '', 10)
        for field, value in documento.dict().items():
            self.cell(0, 10, f'{field}: {value}', 0, 1)

# Endpoint para crear un nuevo documento y generar un PDF
@app.post("/documentos/crear-con-pdf/", response_model=schemas.Documento)
async def create_documento_con_pdf(
    documento: schemas.DocumentoCreate,
    db: AsyncSession = Depends(get_db)
):
    # Crear el documento en la base de datos
    db_documento = await crud.create_documento(db=db, documento=documento)

    # Generar el PDF con los detalles del documento
    pdf = DocumentoPDF()
    pdf.add_page()
    pdf.add_document_details(documento)

    # Definir la ruta del archivo PDF
    pdf_filename = f"documento_{db_documento.id}.pdf"
    pdf_filepath = os.path.join(PDF_DIRECTORY, pdf_filename)

    # Guardar el PDF en la ruta especificada
    pdf.output(pdf_filepath)

    # Actualizar la ruta del archivo PDF en el documento
    db_documento.archivo = pdf_filepath
    await db.commit()
    await db.refresh(db_documento)

    return db_documento   




# Definir la ruta de almacenamiento de los PDFs
PDF_DIRECTORY = "C:\\boleta"
if not os.path.exists(PDF_DIRECTORY):
    os.makedirs(PDF_DIRECTORY)

async def get_db():
    async with SessionLocal() as session:
        yield session

# Clase para generar el PDF personalizado
class DocumentoPDFCustom(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 14)
        self.cell(0, 10, 'Solicitud de Anticipo - Viajes', 0, 1, 'C')
        self.ln(10)

    def add_document_details(self, documento):
        self.set_font('Arial', '', 10)

        # Añadir información general
        self.cell(40, 10, 'DNI:', 1)
        self.cell(60, 10, documento.dni, 1)
        self.cell(40, 10, 'Solicitado el:', 1)
        self.cell(60, 10, str(documento.fecha_solicitud), 1)
        self.ln(10)

        self.cell(40, 10, 'Responsable:', 1)
        self.cell(60, 10, documento.responsable, 1)
        self.cell(40, 10, 'Gerencia:', 1)
        self.cell(60, 10, documento.gerencia, 1)
        self.ln(10)

        self.cell(40, 10, 'Área:', 1)
        self.cell(60, 10, documento.area, 1)
        self.cell(40, 10, 'CeCo:', 1)
        self.cell(60, 10, documento.ceco, 1)
        self.ln(10)

        self.cell(40, 10, 'Tipo de Anticipo:', 1)
        self.cell(60, 10, documento.tipo_anticipo, 1)
        self.cell(40, 10, 'Destino:', 1)
        self.cell(60, 10, documento.destino, 1)
        self.ln(10)

        self.cell(40, 10, 'Fecha de Viaje:', 1)
        self.cell(60, 10, str(documento.fecha_viaje), 1)
        self.cell(40, 10, 'Días:', 1)
        self.cell(60, 10, str(documento.dias), 1)
        self.ln(10)

        self.cell(40, 10, 'Presupuesto:', 1)
        self.cell(60, 10, f"{documento.presupuesto:.2f}", 1)
        self.cell(40, 10, 'Banco:', 1)
        self.cell(60, 10, documento.banco, 1)
        self.ln(10)

        self.cell(40, 10, 'N° de Cuenta:', 1)
        self.cell(60, 10, documento.numero_cuenta, 1)
        self.cell(40, 10, 'Motivo:', 1)
        self.cell(60, 10, documento.motivo, 1)
        self.ln(10)

        self.cell(40, 10, 'Total:', 1)
        self.cell(60, 10, f"{documento.total:.2f}", 1)
        self.ln(20)

        # Añadir sección de firmas
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, 'Firmas', 0, 1, 'C')
        self.set_font('Arial', '', 10)
        self.cell(40, 10, 'Usuario Responsable:', 1)
        self.cell(60, 10, '', 1)
        self.cell(40, 10, 'Aprobado por:', 1)
        self.cell(60, 10, '', 1)
        self.ln(10)

        self.cell(40, 10, 'Recibido por:', 1)
        self.cell(60, 10, '', 1)
        self.cell(40, 10, 'Ejecutado por:', 1)
        self.cell(60, 10, '', 1)
        self.ln(10)

# Endpoint para crear un nuevo documento y generar un PDF
@app.post("/documentos/crear-con-pdf-custom/", response_model=schemas.Documento)
async def create_documento_con_pdf_custom(
    documento: schemas.DocumentoCreate,
    db: AsyncSession = Depends(get_db)
):
    # Crear el documento en la base de datos
    db_documento = await crud.create_documento(db=db, documento=documento)

    # Generar el PDF con los detalles del documento
    pdf = DocumentoPDFCustom()
    pdf.add_page()
    pdf.add_document_details(documento)

    # Definir la ruta del archivo PDF
    pdf_filename = f"documento_{db_documento.id}.pdf"
    pdf_filepath = os.path.join(PDF_DIRECTORY, pdf_filename)

    # Guardar el PDF en la ruta especificada
    pdf.output(pdf_filepath)

    # Actualizar la ruta del archivo PDF en el documento
    db_documento.archivo = pdf_filepath
    await db.commit()
    await db.refresh(db_documento)

    return db_documento


# Definir la ruta de almacenamiento de los PDFs
PDF_DIRECTORY = "C:\\boleta"
if not os.path.exists(PDF_DIRECTORY):
    os.makedirs(PDF_DIRECTORY)

async def get_db():
    async with SessionLocal() as session:
        yield session

# Clase para generar el PDF personalizado basado en el diseño HTML proporcionado
class DocumentoPDFLocal(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 14)
        self.cell(0, 10, 'Solicitud de Anticipo - Gasto Local', 0, 1, 'C')
        self.ln(10)

    def add_document_details(self, documento):
        self.set_font('Arial', '', 10)
        
        # Cabecera del documento
        self.cell(40, 10, 'ANTICIPO', 1)
        self.cell(60, 10, '1', 1)
        self.cell(0, 10, 'OPEX READY SAC', 0, 1, 'R')
        self.ln(10)
        
        # Información del documento
        self.cell(40, 10, 'DNI:', 1)
        self.cell(60, 10, documento.dni, 1)
        self.cell(40, 10, 'Solicitado el:', 1)
        self.cell(60, 10, str(documento.fecha_solicitud), 1)
        self.ln(10)

        self.cell(40, 10, 'Responsable:', 1)
        self.cell(60, 10, documento.responsable, 1)
        self.cell(40, 10, 'Gerencia:', 1)
        self.cell(60, 10, documento.gerencia, 1)
        self.ln(10)

        self.cell(40, 10, 'Área:', 1)
        self.cell(60, 10, documento.area, 1)
        self.cell(40, 10, 'CeCo:', 1)
        self.cell(60, 10, documento.ceco, 1)
        self.ln(10)

        self.cell(40, 10, 'Breve motivo:', 1)
        self.cell(60, 10, documento.motivo, 1)
        self.ln(10)

        self.cell(40, 10, 'Moneda:', 1)
        self.cell(60, 10, documento.moneda, 1)
        self.cell(40, 10, 'Presupuesto:', 1)
        self.cell(60, 10, f"{documento.presupuesto:.2f}" if documento.presupuesto is not None else "0.00", 1)
        self.ln(10)

        self.cell(40, 10, 'Total:', 1)
        self.cell(60, 10, f"{documento.total:.2f}" if documento.total is not None else "0.00", 1)
        self.cell(40, 10, 'Banco y N° de Cuenta:', 1)
        self.cell(60, 10, documento.numero_cuenta, 1)
        self.ln(20)

        # Motivo del anticipo
        self.cell(40, 10, 'Motivo del Anticipo', 1, 1, 'L')
        self.cell(0, 10, documento.motivo, 1)
        self.ln(20)

        # Firmas
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, 'Firmas electrónicas desde la Plataforma', 0, 1, 'C')
        self.set_font('Arial', '', 10)
        self.cell(40, 10, 'Usuario Responsable:', 1)
        self.cell(60, 10, '', 1)
        self.cell(40, 10, 'Aprobado por:', 1)
        self.cell(60, 10, '', 1)
        self.ln(10)

        self.cell(40, 10, 'Recibido por:', 1)
        self.cell(60, 10, '', 1)
        self.cell(40, 10, 'Ejecutado por:', 1)
        self.cell(60, 10, '', 1)
        self.ln(10)

# Endpoint para crear un nuevo documento y generar un PDF con el formato local
@app.post("/documentos/crear-con-pdf-local/", response_model=schemas.Documento)
async def create_documento_con_pdf_local(
    documento: schemas.DocumentoCreate,
    db: AsyncSession = Depends(get_db)
):
    # Crear el documento en la base de datos
    db_documento = await crud.create_documento(db=db, documento=documento)

    # Generar el PDF con los detalles del documento
    pdf = DocumentoPDFLocal()
    pdf.add_page()
    pdf.add_document_details(documento)

    # Definir la ruta del archivo PDF
    pdf_filename = f"documento_local_{db_documento.id}.pdf"
    pdf_filepath = os.path.join(PDF_DIRECTORY, pdf_filename)

    # Guardar el PDF en la ruta especificada
    pdf.output(pdf_filepath)

    # Actualizar la ruta del archivo PDF en el documento
    db_documento.archivo = pdf_filepath
    await db.commit()
    await db.refresh(db_documento)

    return db_documento




PDF_DIRECTORY = "C:\\boleta"
if not os.path.exists(PDF_DIRECTORY):
    os.makedirs(PDF_DIRECTORY)

# Función para obtener la sesión de la base de datos
# async def get_db():
#     async with SessionLocal() as session:
#         yield session

# # Clase para generar el PDF personalizado
# class DocumentoPDFLocal(FPDF):
#     def header(self):
#         self.set_font('Arial', 'B', 14)
#         self.cell(0, 10, 'Solicitud de Anticipo - Gasto Local', 0, 1, 'C')
#         self.ln(10)

#     def add_document_details(self, documento):
#         self.set_font('Arial', '', 10)
        
#         # Cabecera del documento
#         self.cell(40, 10, 'DNI:', 1)
#         self.cell(60, 10, str(documento.get('dni', 'N/A')), 1)  # Convertir a cadena y verificar existencia
#         self.cell(40, 10, 'Solicitado el:', 1)
#         self.cell(60, 10, documento.get('fecha_solicitud', 'N/A'), 1)  # Verificar existencia
#         self.ln(10)

#         # Detalles adicionales
#         self.cell(40, 10, 'Responsable:', 1)
#         self.cell(60, 10, documento.get('usuario', 'N/A'), 1)  # Verificar existencia
#         self.cell(40, 10, 'Gerencia:', 1)
#         self.cell(60, 10, documento.get('gerencia', 'N/A'), 1)  # Verificar existencia
#         self.ln(10)

#         # Más detalles
#         self.cell(40, 10, 'Área:', 1)
#         self.cell(60, 10, documento.get('rubro', 'N/A'), 1)  # Verificar existencia
#         self.cell(40, 10, 'CeCo:', 1)
#         self.cell(60, 10, str(documento.get('cuenta_contable', 'N/A')), 1)  # Convertir a cadena y verificar existencia
#         self.ln(10)

#         # Motivo
#         self.cell(40, 10, 'Motivo del Anticipo:', 1)
#         self.cell(0, 10, documento.get('motivo', 'N/A'), 1)  # Verificar existencia
#         self.ln(20)

# # Endpoint para generar el PDF y guardar la ruta en la base de datos
# @app.post("/generar-pdf-movilidad/")
# async def generar_pdf(data: dict, db: AsyncSession = Depends(get_db)):

#     # Verificar si el directorio PDF existe
#     if not os.path.exists(PDF_DIRECTORY):
#         os.makedirs(PDF_DIRECTORY)

#     # Crear el nombre del archivo PDF
#     pdf_filename = os.path.join(PDF_DIRECTORY, f"reporte_movilidad_{data['correlativo']}.pdf")

#     # Generar el PDF
#     pdf = DocumentoPDFLocal()
#     pdf.add_page()
#     pdf.add_document_details(data)
#     pdf.output(pdf_filename)

#     # Crear el documento en la base de datos
#     documento_data = schemas.DocumentoCreate(
#         usuario=data['usuario'],
#         dni=data['dni'],
#         # ceco=data['cuenta_contable'],
#         gerencia=data['gerencia'],
#         # moneda=data['moneda'],
#         # correlativo=data['correlativo'],
#         archivo=pdf_filename,  # Guardar la ruta del archivo PDF
#         estado="GENERADO"
#     )

#     # Guardar el documento en la base de datos
#     db_documento = await crud.create_documento(db=db, documento=documento_data)

#     # Actualizar el campo 'archivo' con la ruta del archivo PDF generado
#     db_documento.archivo = pdf_filename
#     await db.commit()
#     await db.refresh(db_documento)

#     # Retornar el archivo generado como respuesta
#     return FileResponse(pdf_filename, media_type='application/pdf', filename=f"reporte_movilidad_{data['correlativo']}.pdf")



# class DocumentoPDFLocal(FPDF):
#     def header(self):
#         self.set_font('Arial', 'B', 12)
#         self.cell(0, 10, 'Reporte de Gastos movilidad / Local', 0, 1, 'L')
#         self.set_font('Arial', '', 10)
#         self.cell(0, 5, 'OPEX READY SAC', 0, 1, 'L')
#         self.cell(0, 5, '20XXXXXXXXX', 0, 1, 'L')
#         self.ln(5)

#     def add_document_details(self, documento):
#         self.set_font('Arial', '', 10)

#         # Información principal
#         self.cell(0, 5, 'Solicitante: ' + documento.get('usuario', 'N/A'), 0, 1, 'L')
#         self.cell(0, 5, 'DNI: ' + str(documento.get('dni', 'N/A')), 0, 1, 'L')
#         self.cell(0, 5, 'CeCo: ' + documento.get('ceco', 'N/A'), 0, 1, 'R')
#         self.cell(0, 5, 'Gerencia: ' + documento.get('gerencia', 'N/A'), 0, 1, 'R')
#         self.cell(0, 5, 'Moneda: ' + documento.get('moneda', 'N/A'), 0, 1, 'R')
#         self.cell(0, 5, 'Correlativo: ' + str(documento.get('correlativo', 'N/A')), 0, 1, 'R')
#         self.ln(10)

#         # Título de la tabla
#         self.set_font('Arial', 'B', 10)
#         self.cell(0, 5, 'DETALLE DE GASTOS DE MOVILIDAD (en el lugar habitual del trabajo)', 0, 1, 'C')
#         self.ln(5)

#         # Cabecera de la tabla
#         self.set_font('Arial', 'B', 8)
#         self.cell(10, 6, 'N°', 1, 0, 'C')
#         self.cell(30, 6, 'FECHA', 1, 0, 'C')
#         self.cell(30, 6, 'ORIGEN', 1, 0, 'C')
#         self.cell(30, 6, 'DESTINO', 1, 0, 'C')
#         self.cell(50, 6, 'MOTIVO', 1, 0, 'C')
#         self.cell(30, 6, 'GASTO DEDUCIBLE', 1, 0, 'C')
#         self.cell(30, 6, 'NO DEDUCIBLE', 1, 0, 'C')
#         self.cell(30, 6, 'TOTAL', 1, 1, 'C')

#         # Detalle de gastos
#         self.set_font('Arial', '', 8)
#         for idx, item in enumerate(documento.get('gastos', []), start=1):
#             self.cell(10, 6, str(idx), 1, 0, 'C')
#             self.cell(30, 6, item.get('fecha', 'N/A'), 1, 0, 'C')
#             self.cell(30, 6, item.get('origen', 'N/A'), 1, 0, 'C')
#             self.cell(30, 6, item.get('destino', 'N/A'), 1, 0, 'C')
#             self.cell(50, 6, item.get('motivo', 'N/A'), 1, 0, 'C')
#             self.cell(30, 6, 'S/ ' + str(item.get('gasto_deducible', '0.00')), 1, 0, 'C')
#             self.cell(30, 6, 'S/ ' + str(item.get('gasto_no_deducible', '0.00')), 1, 0, 'C')
#             self.cell(30, 6, 'S/ ' + str(item.get('total', '0.00')), 1, 1, 'C')

#         # Resumen de total
#         self.set_font('Arial', 'B', 10)
#         self.cell(210, 6, 'Total', 1, 0, 'R')
#         self.cell(30, 6, 'S/ ' + str(documento.get('total', '0.00')), 1, 1, 'C')

#         # Pie de página
#         self.ln(10)
#         self.cell(0, 5, 'Son: ' + documento.get('total_letras', 'N/A'), 0, 1, 'L')
#         self.ln(5)
#         self.cell(0, 5, 'Firmas electrónicas desde Plataforma', 0, 1, 'L')
#         self.ln(10)

#         # Firmas
#         self.cell(90, 6, 'Solicitante', 1, 0, 'C')
#         self.cell(90, 6, 'Validado y Registrado', 1, 1, 'C')
#         self.cell(90, 6, documento.get('usuario', 'N/A'), 1, 0, 'C')
#         self.cell(90, 6, 'Gerencia de Adm. Y Finanzas', 1, 1, 'C')

# # Endpoint para generar el PDF y guardar la ruta en la base de datos
# @app.post("/generar-pdf-movilidad/")
# async def generar_pdf(data: dict, db: AsyncSession = Depends(get_db)):

#     # Verificar si el directorio PDF existe
#     if not os.path.exists(PDF_DIRECTORY):
#         os.makedirs(PDF_DIRECTORY)

#     # Crear el nombre del archivo PDF
#     pdf_filename = os.path.join(PDF_DIRECTORY, f"reporte_movilidad_{data['correlativo']}.pdf")

#     # Generar el PDF
#     pdf = DocumentoPDFLocal()
#     pdf.add_page()
#     pdf.add_document_details(data)
#     pdf.output(pdf_filename)

#     # Crear el documento en la base de datos
#     documento_data = schemas.DocumentoCreate(
#         usuario=data['usuario'],
#         dni=data['dni'],
#         gerencia=data['gerencia'],
#         archivo=pdf_filename,  # Guardar la ruta del archivo PDF
#         estado="GENERADO"
#     )

#     # Guardar el documento en la base de datos
#     db_documento = await crud.create_documento(db=db, documento=documento_data)

#     # Actualizar el campo 'archivo' con la ruta del archivo PDF generado
#     db_documento.archivo = pdf_filename
#     await db.commit()
#     await db.refresh(db_documento)

#     # Retornar el archivo generado como respuesta
#     return FileResponse(pdf_filename, media_type='application/pdf', filename=f"reporte_movilidad_{data['correlativo']}.pdf")




class DocumentoPDFLocal(FPDF):

    def __init__(self):
        super().__init__('L')

    def header(self):
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, 'Reporte de Gastos movilidad / Local', 0, 1, 'L')
        self.set_font('Arial', '', 10)
        self.cell(0, 5, 'OPEX READY SAC', 0, 1, 'L')
        self.cell(0, 5, '20XXXXXXXXX', 0, 1, 'L')
        self.ln(5)

    def add_document_details(self, documento):
        self.set_font('Arial', '', 10)

        # Información principal
        self.cell(0, 5, 'Solicitante: ' + documento.get('usuario', 'N/A'), 0, 1, 'L')
        self.cell(0, 5, 'DNI: ' + str(documento.get('dni', 'N/A')), 0, 1, 'L')
        self.cell(0, 5, 'CeCo: ' + documento.get('ceco', 'N/A'), 0, 1, 'R')
        self.cell(0, 5, 'Gerencia: ' + documento.get('gerencia', 'N/A'), 0, 1, 'R')
        self.cell(0, 5, 'Moneda: ' + documento.get('moneda', 'N/A'), 0, 1, 'R')
        # self.cell(0, 5, 'Correlativo: ' + str(documento.get('correlativo', 'N/A')), 0, 1, 'R')
        self.ln(10)

        # Título de la tabla
        self.set_font('Arial', 'B', 10)
        self.cell(0, 5, 'DETALLE DE GASTOS DE MOVILIDAD (en el lugar habitual del trabajo)', 0, 1, 'C')
        self.ln(5)

        # Cabecera de la tabla
        self.set_font('Arial', 'B', 8)
        self.cell(10, 6, 'N°', 1, 0, 'C')
        self.cell(30, 6, 'FECHA', 1, 0, 'C')
        self.cell(30, 6, 'ORIGEN', 1, 0, 'C')
        self.cell(30, 6, 'DESTINO', 1, 0, 'C')
        self.cell(50, 6, 'MOTIVO', 1, 0, 'C')
        self.cell(30, 6, 'GASTO DEDUCIBLE', 1, 0, 'C')
        self.cell(30, 6, 'NO DEDUCIBLE', 1, 0, 'C')
        self.cell(30, 6, 'TOTAL', 1, 1, 'C')

        # Detalle de gastos: Aquí se añaden los datos del request
        self.set_font('Arial', '', 8)
        self.cell(10, 6, '01', 1, 0, 'C')  # Número de la fila
        self.cell(30, 6, documento.get('fecha_solicitud', 'N/A'), 1, 0, 'C')  # Fecha
        self.cell(30, 6, documento.get('origen', 'N/A'), 1, 0, 'C')  # Origen
        self.cell(30, 6, documento.get('destino', 'N/A'), 1, 0, 'C')  # Destino
        self.cell(50, 6, documento.get('motivo', 'N/A'), 1, 0, 'C')  # Motivo
        self.cell(30, 6, 'S/ ' + str(documento.get('gasto_deducible', '0.00')), 1, 0, 'C')  # Gasto deducible
        self.cell(30, 6, 'S/ ' + str(documento.get('gasto_no_deducible', '0.00')), 1, 0, 'C')  # Gasto no deducible (en este caso no hay datos)
        self.cell(30, 6, 'S/ ' + str(documento.get('total', '0.00')), 1, 1, 'C')  # Total

        # Resumen de total
        self.set_font('Arial', 'B', 10)
        self.cell(210, 6, 'Total', 1, 0, 'R')
        self.cell(30, 6, 'S/ ' + str(documento.get('total', '0.00')), 1, 1, 'C')

        # Pie de página
        self.ln(10)
        self.cell(0, 5, 'Son: ' + documento.get('total_letras', 'N/A'), 0, 1, 'L')
        self.ln(5)
        self.cell(0, 5, 'Firmas electrónicas desde Plataforma', 0, 1, 'L')
        self.ln(10)

        # Firmas
        self.cell(90, 6, 'Solicitante', 1, 0, 'C')
        self.cell(90, 6, 'Validado y Registrado', 1, 1, 'C')
        self.cell(90, 6, documento.get('usuario', 'N/A'), 1, 0, 'C')
        self.cell(90, 6, 'Gerencia de Adm. Y Finanzas', 1, 1, 'C')

# Endpoint para generar el PDF y guardar la ruta en la base de datos
# @app.post("/generar-pdf-movilidad/")
# async def generar_pdf(data: dict, db: AsyncSession = Depends(get_db)):

#     # Verificar si el directorio PDF existe
#     if not os.path.exists(PDF_DIRECTORY):
#         os.makedirs(PDF_DIRECTORY)

#     # Crear el nombre del archivo PDF
#     pdf_filename = os.path.join(PDF_DIRECTORY, f"reporte_movilidad_{data['1']}.pdf")

#     # Generar el PDF
#     pdf = DocumentoPDFLocal()
#     pdf.add_page()
#     pdf.add_document_details(data)
#     pdf.output(pdf_filename)

#     # Crear el documento en la base de datos
#     documento_data = schemas.DocumentoCreate(
#         # usuario=data['usuario'],
#         # dni=data['dni'],
#         # gerencia=data['gerencia'],
#         archivo=pdf_filename,  # Guardar la ruta del archivo PDF
#         estado="GENERADO"
#     )

#     # Guardar el documento en la base de datos
#     db_documento = await crud.create_documento(db=db, documento=documento_data)

#     # Actualizar el campo 'archivo' con la ruta del archivo PDF generado
#     db_documento.archivo = pdf_filename
#     await db.commit()
#     await db.refresh(db_documento)

#     # Retornar el archivo generado como respuesta
#     return FileResponse(pdf_filename, media_type='application/pdf', filename=f"reporte_movilidad_{data['1']}.pdf")

@app.post("/generar-pdf-movilidad/")
async def generar_pdf(data: dict, db: AsyncSession = Depends(get_db)):

    # # Validar que 'correlativo' esté presente en los datos
    # if 'correlativo' not in data:
    #     raise HTTPException(status_code=400, detail="El campo 'correlativo' es obligatorio")

    # Verificar si el directorio PDF existe
    if not os.path.exists(PDF_DIRECTORY):
        os.makedirs(PDF_DIRECTORY)
    correlativo = "eee"
    # Crear el nombre del archivo PDF usando el campo 'correlativo'
    pdf_filename = os.path.join(PDF_DIRECTORY, f"reporte_movilidad_{data['correlativo']}.pdf")

    # Generar el PDF
    pdf = DocumentoPDFLocal()
    pdf.add_page()
    pdf.add_document_details(data)
    pdf.output(pdf_filename)

    documento_data = schemas.DocumentoCreate(
        fecha_solicitud = data['fecha_solicitud'],
        fecha_emision = data['fecha_emision'],
        usuario=data['usuario'],
        dni=data['dni'],
        gerencia=data['gerencia'],
        correlativo=data['correlativo'],  
        archivo=pdf_filename,  
        estado="PENDIENTE2",
        empresa = "innova",
        moneda = "PEN",
        tipo_documento = "Boleta de Venta",
      
    )

    # Guardar el documento en la base de datos
    db_documento = await crud.create_documento(db=db, documento=documento_data)

    # Actualizar el campo 'archivo' con la ruta del archivo PDF generado
    db_documento.archivo = pdf_filename
    await db.commit()
    await db.refresh(db_documento)

    # Retornar el archivo generado como respuesta
    return FileResponse(pdf_filename, media_type='application/pdf', filename=f"reporte_movilidad_{data['correlativo']}.pdf")




