from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Query, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional
from datetime import date, timedelta, datetime
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from sqlalchemy import distinct
import shutil
import os
import random
import string
import requests
import cv2
import numpy as np
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse, RedirectResponse
from PIL import Image, ImageEnhance, ImageOps
import re
import io
from io import BytesIO
import logging
import pandas as pd
from fpdf import FPDF
from mimetypes import guess_type
import pytesseract
import httpx
import uuid
from pyzbar.pyzbar import decode # type: ignore
from pyzxing import BarCodeReader # type: ignore
from . import crud, models, schemas, auth
from .database import engine, SessionLocal
from app.firebase_service import upload_file_to_firebase, download_file_from_firebase, upload_file_to_firebase_pdf
import cv2

app = FastAPI()

app.add_middleware(HTTPSRedirectMiddleware)

# Configuración de Tesseract-OCR
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

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
            raise HTTPException(status_code=response.status_code,
                                detail="Error al consultar el RUC")

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
            raise HTTPException(status_code=response.status_code,
                                detail="Error al consultar el tipo de cambio")


# Preprocesamiento de imagen para mejorar la lectura de códigos QR
def preprocess_image(image):
    # Convertir a escala de grises
    gray_image = ImageOps.grayscale(image)

    # Aumentar el contraste
    enhancer = ImageEnhance.Contrast(gray_image)
    contrast_image = enhancer.enhance(2)

    # Convertir a formato OpenCV para aplicar más preprocesamientos si es necesario
    open_cv_image = np.array(contrast_image)

    # Aplicar un umbral adaptativo
    processed_image = cv2.adaptiveThreshold(
        open_cv_image, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)

    return processed_image


@app.post("/decode-qr/")
async def decode_qr(file: UploadFile = File(...)):
    if file.content_type not in ['image/jpeg', 'image/png']:
        raise HTTPException(status_code=400, detail="Invalid file format")

    try:
        image_data = await file.read()
        image = Image.open(io.BytesIO(image_data))

        # Preprocesar la imagen para mejorar la posibilidad de lectura
        processed_image = preprocess_image(image)

        # Intentar la decodificación varias veces
        decoded_objects = decode(processed_image)

        if not decoded_objects:
            # Si no funciona con la imagen preprocesada, intentamos con la imagen original
            decoded_objects = decode(image)

        if not decoded_objects:
            return JSONResponse(content={"detail": "No QR code found in the image"})

        # Extraer la data del primer código QR encontrado
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
            # Dato con formato xxxx-aaaaaaaa (Serie-Número)
            elif re.match(r'^[A-Za-z0-9]{4}-\d{7,8}$', data):
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
        raise HTTPException(
            status_code=500, detail=f"Failed to decode QR code: {str(e)}")



    



@app.post("/token", response_model=dict)
async def login_for_access_token(form_data: schemas.UserLogin, db: AsyncSession = Depends(get_db)):
    user = await crud.get_user_by_email(db, email=form_data.email)
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=400, detail="Incorrect email or password")
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires)
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
        raise HTTPException(
            status_code=404, detail="No users found for the specified company_name and role")
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


@app.post("/documentos/", response_model=schemas.Documento)
async def create_documento(documento: schemas.DocumentoCreate, db: AsyncSession = Depends(get_db)):

    # Primera búsqueda: Verificar si existe un documento con el mismo usuario, fecha_solicitud y tipo_solicitud = 'GASTO'
    result = await db.execute(
        select(models.Documento)
        .filter(models.Documento.usuario == documento.usuario)
        .filter(models.Documento.fecha_solicitud == documento.fecha_solicitud)
        # Filtro adicional para 'GASTO'
        .filter(models.Documento.tipo_solicitud == 'GASTO')
        .limit(1)  # Solo necesitamos el primer resultado
    )

    documento_existente = result.scalar_one_or_none()

    if documento_existente:
        # Si existe un documento con el mismo usuario, fecha_solicitud y tipo_solicitud, usamos su numero_rendicion
        numero_rendicion = documento_existente.numero_rendicion
    else:
        # Segunda búsqueda: Buscar el mayor numero_rendicion para ese usuario y tipo_solicitud = 'GASTO'
        result = await db.execute(
            select(models.Documento.numero_rendicion)
            .filter(models.Documento.usuario == documento.usuario)
            # Filtro adicional para 'GASTO'
            .filter(models.Documento.tipo_solicitud == 'GASTO')
            .order_by(models.Documento.numero_rendicion.desc())
            .limit(1)  # Solo necesitamos el mayor valor
        )

        mayor_rendicion = result.scalar_one_or_none()

        if mayor_rendicion:
            # Incrementar el número de rendición si ya existe un mayor valor
            # Extraer el número de rendición, quitar el prefijo "rendicion_" y sumarle 1
            rendicion_num = int(mayor_rendicion.replace("rendicion_", "")) + 1
            numero_rendicion = f"rendicion_{rendicion_num}"
        else:
            # Si no existe ningún documento previo, comenzamos con rendicion_1
            numero_rendicion = "rendicion_1"

    # Crear el documento con el numero_rendicion generado
    db_documento = models.Documento(
        fecha_solicitud=documento.fecha_solicitud,
        fecha_rendicion=documento.fecha_rendicion,
        dni=documento.dni,
        usuario=documento.usuario,
        gerencia=documento.gerencia,
        ruc=documento.ruc,
        proveedor=documento.proveedor,
        fecha_emision=documento.fecha_emision,
        moneda=documento.moneda,
        tipo_documento=documento.tipo_documento,
        serie=documento.serie,
        correlativo=documento.correlativo,
        tipo_gasto=documento.tipo_gasto,
        sub_total=documento.sub_total,
        igv=documento.igv,
        no_gravadas=documento.no_gravadas,
        importe_facturado=documento.importe_facturado,
        tc=documento.tc,
        anticipo=documento.anticipo,
        total=documento.total,
        pago=documento.pago,
        detalle=documento.detalle,
        estado=documento.estado,
        empresa=documento.empresa,
        archivo=documento.archivo,
        tipo_solicitud=documento.tipo_solicitud,
        tipo_cambio=documento.tipo_cambio,
        afecto=documento.afecto,
        inafecto=documento.inafecto,
        rubro=documento.rubro,
        cuenta_contable=documento.cuenta_contable,
        responsable=documento.responsable,
        area=documento.area,
        ceco=documento.ceco,
        tipo_anticipo=documento.tipo_anticipo,
        motivo=documento.motivo,
        fecha_viaje=documento.fecha_viaje,
        dias=documento.dias,
        presupuesto=documento.presupuesto,
        banco=documento.banco,
        numero_cuenta=documento.numero_cuenta,
        destino=documento.destino,
        origen=documento.origen,
        numero_rendicion=numero_rendicion  # Aquí añadimos el número de rendición
    )

    db.add(db_documento)
    await db.commit()
    await db.refresh(db_documento)
    return db_documento


@app.get("/documentos/{documento_id}", response_model=schemas.Documento)
async def read_documento(documento_id: int, db: AsyncSession = Depends(get_db)):
    db_documento = await crud.get_documento(db, documento_id=documento_id)
    if db_documento is None:
        raise HTTPException(status_code=404, detail="Documento not found")
    return db_documento


@app.get("/documentos/", response_model=List[schemas.DocumentoBase])
async def read_documentos(
    empresa: str = Query(None, alias="company_name"),
    estado: str = Query(None),
    username: str = Query(None),
    tipo_solicitud: str = Query(None),
    tipo_anticipo: str = Query(None),
    numero_rendicion: str = Query(None),
    fecha_solicitud_from: Optional[str] = Query(None),
    fecha_solicitud_to: Optional[str] = Query(None),
    fecha_rendicion_from: Optional[str] = Query(None),
    fecha_rendicion_to: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    # Inicializar la consulta base
    query = select(models.Documento).where(models.Documento.empresa == empresa)

    # Filtros opcionales
    if estado:
        query = query.where(models.Documento.estado == estado)
    if username:
        query = query.where(models.Documento.usuario == username)
    if tipo_anticipo:
        query = query.where(models.Documento.tipo_anticipo == tipo_anticipo)
    if tipo_solicitud:
        query = query.where(models.Documento.tipo_solicitud == tipo_solicitud)
    if numero_rendicion:
        query = query.where(
            models.Documento.numero_rendicion == numero_rendicion)

    # Filtros de rango de fechas con conversión manual
    if fecha_solicitud_from:
        query = query.where(models.Documento.fecha_solicitud >= datetime.strptime(
            fecha_solicitud_from, "%Y-%m-%d").date())
    if fecha_solicitud_to:
        query = query.where(models.Documento.fecha_solicitud <= datetime.strptime(
            fecha_solicitud_to, "%Y-%m-%d").date())

    if fecha_rendicion_from:
        query = query.where(models.Documento.fecha_rendicion >= datetime.strptime(
            fecha_rendicion_from, "%Y-%m-%d").date())
    if fecha_rendicion_to:
        query = query.where(models.Documento.fecha_rendicion <= datetime.strptime(
            fecha_rendicion_to, "%Y-%m-%d").date())

    # Ejecutar la consulta
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
    try:
        # Solicitar el archivo desde la URL externa
        response = requests.get(file_location, stream=True)
        if response.status_code == 200:
            return StreamingResponse(response.raw, media_type="application/octet-stream")
        else:
            raise HTTPException(status_code=404, detail="File not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/documentos/view/")
async def view_file(file_location: str):
    # Verificamos si es una URL de Firebase (u otra URL remota) en lugar de una ruta local
    if file_location.startswith("http"):
        # Redirigimos al usuario a la URL del archivo en Firebase
        return RedirectResponse(url=file_location)

    # Si el archivo es local, verificamos si existe
    if not os.path.exists(file_location):
        raise HTTPException(status_code=404, detail="File not found")

    # Intentamos adivinar el tipo de archivo y devolverlo como una respuesta de archivo
    media_type, _ = guess_type(file_location)
    return FileResponse(path=file_location, media_type=media_type)


@app.get("/documentos/export/excel")
async def export_documentos_excel(
    empresa: str = Query(None, alias="company_name"),
    estado: str = Query(None),
    username: str = Query(None),
    db: AsyncSession = Depends(get_db)
):
    query = select(models.Documento).filter(
        models.Documento.empresa == empresa)
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
        # "Rubro": doc.rubro,
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
        self.cell(
            col_width, 10, f'Reembolsar / (-)Devolver: {reembolso}', border=1, ln=1, align='L')


@app.get("/documentos/export/pdf")
async def export_documentos_pdf(
    empresa: str = Query(..., alias="company_name"),  # Obligatorio
    estado: str = Query(None),  # Opcional
    username: str = Query(...),  # Obligatorio
    # Obligatorio
    numero_rendicion: str = Query(...,
                                  description="Número de rendición (obligatorio)"),
    db: AsyncSession = Depends(get_db)
):
    # Verificar que numero_rendicion no esté vacío
    if not numero_rendicion:
        raise HTTPException(
            status_code=400, detail="El campo 'numero_rendicion' es obligatorio.")

    # Construir la consulta base con el filtro de empresa y número de rendición obligatorio
    query = select(models.Documento).filter(
        models.Documento.empresa == empresa,
        models.Documento.numero_rendicion == numero_rendicion
    )

    # Filtros adicionales opcionales
    if estado:
        query = query.filter(models.Documento.estado == estado)
    if username:
        query = query.filter(models.Documento.usuario == username)

    # Ejecutar la consulta
    result = await db.execute(query)
    documentos = result.scalars().all()

    # Verificar si se encontraron documentos
    if not documentos:
        raise HTTPException(
            status_code=404, detail="No se encontraron documentos para la rendición proporcionada.")

    # Calcular el total de gastos
    total_gasto = sum(doc.total for doc in documentos)

    # Calcular el total de anticipo basado en tipo_solicitud=ANTICIPO, estado=APROBADO y username
    query_anticipo = select(models.Documento).filter(
        models.Documento.tipo_solicitud == "ANTICIPO",
        models.Documento.estado == "APROBADO",
        models.Documento.usuario == username,
        models.Documento.empresa == empresa
    )

    result_anticipo = await db.execute(query_anticipo)
    documentos_anticipo = result_anticipo.scalars().all()

    # total_anticipo = sum(doc.total for doc in documentos_anticipo)

    total_anticipo = sum(doc.total if doc.total is not None else 0 for doc in documentos_anticipo)


    reembolso = total_anticipo - total_gasto

    # Crear el PDF
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

    # Añadir una página al PDF
    pdf.add_page()

    # Definir el encabezado de la tabla
    table_header = ["Item", "Fecha", "RUC", "Tip. Doc", "Cta Contable", "Serie", "Correlativo",
                    "Moneda", "Tip. Cambio", "Afecto", "IGV", "Inafecto", "Total"]

    # Definir los datos de la tabla
    table_data = [
        [i + 1, doc.fecha_emision, doc.ruc, doc.tipo_documento, doc.cuenta_contable, doc.serie, doc.correlativo,
         doc.moneda, doc.tc, doc.afecto, doc.igv, doc.inafecto, doc.total]
        for i, doc in enumerate(documentos)
    ]
    pdf.add_table(table_header, table_data)

    # Añadir las firmas
    pdf.add_firmas(pdf.total_anticipo, pdf.total_gasto, pdf.reembolso)

    # Generar el archivo PDF
    pdf_file = f"documentos_{numero_rendicion}.pdf"
    pdf.output(pdf_file)

    return FileResponse(path=pdf_file, filename=f"documentos_{numero_rendicion}.pdf")


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

    # Crear un objeto BytesIO para almacenar el PDF
    pdf_data = BytesIO()

    try:
        # Guardar el contenido del PDF en el objeto BytesIO
        # El argumento 'S' devuelve el PDF como una cadena
        pdf_output = pdf.output(dest='S').encode('latin1')
        pdf_data.write(pdf_output)
        # Asegúrate de que el puntero esté al inicio del archivo
        pdf_data.seek(0)

        # Crear un nombre de archivo aleatorio usando UUID
        unique_filename = f"documento_{str(uuid.uuid4())}.pdf"

        # Subir el archivo PDF a Firebase
        public_url = upload_file_to_firebase_pdf(
            pdf_data, unique_filename, content_type="application/pdf")

    except Exception as e:
        logging.error(f"Error al generar o subir el PDF: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error al generar o subir el archivo a Firebase: {str(e)}")
    db_documento.archivo = public_url
    await db.commit()
    await db.refresh(db_documento)
    return db_documento

async def get_db():
    async with SessionLocal() as session:
        yield session

# Clase para generar el PDF personalizado para el modelo local
class DocumentoPDFLocal(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 14)
        self.cell(0, 10, 'Solicitud de Anticipo - Gasto Local', 0, 1, 'C')
        self.ln(10)

    def add_document_details(self, documento: schemas.DocumentoCreate):
        self.set_font('Arial', '', 10)

        # Cabecera del documento
        self.cell(40, 10, 'ANTICIPO', 1)
        self.cell(60, 10, '1', 1)
        self.cell(0, 10, 'OPEX READY SAC', 0, 1, 'R')
        self.ln(10)

        # Información del documento
        self.cell(40, 10, 'DNI:', 1)
        self.cell(60, 10, documento.dni if documento.dni else 'N/A', 1)
        self.cell(40, 10, 'Solicitado el:', 1)
        self.cell(60, 10, str(documento.fecha_solicitud)
                  if documento.fecha_solicitud else 'N/A', 1)
        self.ln(10)

        self.cell(40, 10, 'Responsable:', 1)
        self.cell(
            60, 10, documento.responsable if documento.responsable else 'N/A', 1)
        self.cell(40, 10, 'Gerencia:', 1)
        self.cell(60, 10, documento.gerencia if documento.gerencia else 'N/A', 1)
        self.ln(10)

        self.cell(40, 10, 'Área:', 1)
        self.cell(60, 10, documento.area if documento.area else 'N/A', 1)
        self.cell(40, 10, 'CeCo:', 1)
        self.cell(60, 10, documento.ceco if documento.ceco else 'N/A', 1)
        self.ln(10)

        self.cell(40, 10, 'Breve motivo:', 1)
        self.cell(60, 10, documento.motivo if documento.motivo else 'N/A', 1)
        self.ln(10)

        self.cell(40, 10, 'Moneda:', 1)
        self.cell(60, 10, documento.moneda if documento.moneda else 'N/A', 1)
        self.cell(40, 10, 'Presupuesto:', 1)
        self.cell(
            60, 10, f"{documento.presupuesto:.2f}" if documento.presupuesto else "0.00", 1)
        self.ln(10)

        self.cell(40, 10, 'Total:', 1)
        self.cell(
            60, 10, f"{documento.total:.2f}" if documento.total else "0.00", 1)
        self.cell(40, 10, 'Banco y N° de Cuenta:', 1)
        self.cell(
            60, 10, documento.numero_cuenta if documento.numero_cuenta else 'N/A', 1)
        self.ln(20)

        # Motivo del anticipo
        self.cell(40, 10, 'Motivo del Anticipo', 1, 1, 'L')
        self.cell(0, 10, documento.motivo if documento.motivo else 'N/A', 1)
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


@app.post("/documentos/crear-con-pdf-local/", response_model=schemas.Documento)
async def create_documento_con_pdf_local(
    documento: schemas.DocumentoCreate,
    db: AsyncSession = Depends(get_db)
):
    db_documento = await crud.create_documento(db=db, documento=documento)

    pdf = DocumentoPDFLocal()  # Instancia de la clase correctamente
    pdf.add_page()
    pdf.add_document_details(documento)  # Pasar el objeto documento

    pdf_data = BytesIO()

    try:
        pdf_output = pdf.output(dest='S').encode('latin1')
        pdf_data.write(pdf_output)
        pdf_data.seek(0)
        unique_filename = f"documento_local_{str(uuid.uuid4())}.pdf"
        public_url = upload_file_to_firebase_pdf(
            pdf_data, unique_filename, content_type="application/pdf")

    except Exception as e:
        logging.error(f"Error al generar o subir el PDF: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error al generar o subir el archivo a Firebase: {str(e)}")
    db_documento.archivo = public_url
    await db.commit()
    await db.refresh(db_documento)
    return db_documento


class DocumentoPDFMovilidad(FPDF):

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
        self.cell(0, 5, 'Solicitante: ' +
                  documento.get('usuario', 'N/A'), 0, 1, 'L')
        self.cell(0, 5, 'DNI: ' + str(documento.get('dni', 'N/A')), 0, 1, 'L')
        self.cell(0, 5, 'CeCo: ' + documento.get('ceco', 'N/A'), 0, 1, 'R')
        self.cell(0, 5, 'Gerencia: ' +
                  documento.get('gerencia', 'N/A'), 0, 1, 'R')
        self.cell(0, 5, 'Moneda: ' + documento.get('moneda', 'N/A'), 0, 1, 'R')
        # self.cell(0, 5, 'Correlativo: ' + str(documento.get('correlativo', 'N/A')), 0, 1, 'R')
        self.ln(10)

        # Título de la tabla
        self.set_font('Arial', 'B', 10)
        self.cell(
            0, 5, 'DETALLE DE GASTOS DE MOVILIDAD (en el lugar habitual del trabajo)', 0, 1, 'C')
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
        self.set_font('Arial', '', 8)
        self.cell(10, 6, '01', 1, 0, 'C')  # Número de la fila
        self.cell(30, 6, documento.get(
            'fecha_solicitud', 'N/A'), 1, 0, 'C')  # Fecha
        self.cell(30, 6, documento.get('origen', 'N/A'), 1, 0, 'C')  # Origen
        self.cell(30, 6, documento.get('destino', 'N/A'), 1, 0, 'C')  # Destino
        self.cell(50, 6, documento.get('motivo', 'N/A'), 1, 0, 'C')  # Motivo
        self.cell(30, 6, 'S/ ' + str(documento.get('gasto_deducible',
                  '0.00')), 1, 0, 'C')  
        self.cell(30, 6, 'S/ ' +
                  str(documento.get('gasto_no_deducible', '0.00')), 1, 0, 'C')
        self.cell(30, 6, 'S/ ' + str(documento.get('total', '0.00')),
                  1, 1, 'C')  
        self.set_font('Arial', 'B', 10)
        self.cell(210, 6, 'Total', 1, 0, 'R')
        self.cell(30, 6, 'S/ ' + str(documento.get('total', '0.00')), 1, 1, 'C')
        self.ln(10)
        self.cell(0, 5, 'Son: ' + documento.get('total_letras', 'N/A'), 0, 1, 'L')
        self.ln(5)
        self.cell(0, 5, 'Firmas electrónicas desde Plataforma', 0, 1, 'L')
        self.ln(10)
        self.cell(90, 6, 'Solicitante', 1, 0, 'C')
        self.cell(90, 6, 'Validado y Registrado', 1, 1, 'C')
        self.cell(90, 6, documento.get('usuario', 'N/A'), 1, 0, 'C')
        self.cell(90, 6, 'Gerencia de Adm. Y Finanzas', 1, 1, 'C')

@app.post("/generar-pdf-movilidad/")
async def generar_pdf(data: dict, db: AsyncSession = Depends(get_db)):

    pdf = DocumentoPDFMovilidad()
    pdf.add_page()
    pdf.add_document_details(data)

    pdf_data = BytesIO()

    try:
        pdf_output = pdf.output(dest='S').encode('latin1')
        pdf_data.write(pdf_output)
        pdf_data.seek(0)
        pdf_filename = f"reporte_movilidad_{str(uuid.uuid4())}.pdf"
        public_url = upload_file_to_firebase_pdf(
            pdf_data, pdf_filename, content_type="application/pdf")

    except Exception as e:
        logging.error(f"Error al generar o subir el PDF: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error al generar o subir el archivo a Firebase: {str(e)}")

    documento_data = schemas.DocumentoCreate(
        fecha_solicitud=data['fecha_solicitud'],
        fecha_emision=data['fecha_emision'],
        usuario=data['usuario'],
        dni=data['dni'],
        gerencia=data['gerencia'],
        archivo=public_url, 
        estado="PENDIENTE",
        empresa="innova",
        moneda="PEN",
        tipo_documento="Recibo de Movilidad",
        total=data['total'],  
        rubro=data['rubro'],
        cuenta_contable=data['cuenta_contable'],
        motivo=data['motivo'],
        origen=data['origen'],
        destino=data['destino'],
        tipo_solicitud="GASTO"
    )
    db_documento = await crud.create_documento(db=db, documento=documento_data)
    db_documento.archivo = public_url
    await db.commit()
    await db.refresh(db_documento)
    return {"file_url": public_url}

DOWNLOAD_DIRECTORY = "downloads"

if not os.path.exists(DOWNLOAD_DIRECTORY):
    os.makedirs(DOWNLOAD_DIRECTORY)


@app.post("/upload-file-firebase/")
async def upload_file(file: UploadFile = File(...)):
    allowed_content_types = ["image/jpeg", "image/png", "application/pdf"]
    if file.content_type not in allowed_content_types:
        raise HTTPException(
            status_code=400, detail="El tipo de archivo no está permitido. Sube JPG, PNG o PDF.")
    try:
        public_url = upload_file_to_firebase(file, file.filename)
        return {"file_url": public_url}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error al subir el archivo: {str(e)}")


@app.get("/download-file/")
async def download_file(filename: str):
    try:
        if filename.startswith("http"):
            return RedirectResponse(url=filename)
        local_path = os.path.join(DOWNLOAD_DIRECTORY, filename)
        download_file_from_firebase(filename, local_path)
        return FileResponse(path=local_path, filename=filename, media_type='application/octet-stream')
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error al descargar el archivo: {str(e)}")


@app.post("/decode-qr-opencv/")
async def decode_qr_opencv(file: UploadFile = File(...)):
    if file.content_type not in ['image/jpeg', 'image/png']:
        raise HTTPException(status_code=400, detail="Invalid file format")
    try:
        image_data = await file.read()
        image = np.array(Image.open(io.BytesIO(image_data)))
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        qr_detector = cv2.QRCodeDetector()
        data, points, _ = qr_detector.detectAndDecode(gray)
        if data:
            result = {"data": data}
            return JSONResponse(content=result)
        else:
            return JSONResponse(content={"detail": "No QR code found in the image"})
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to decode QR code using OpenCV: {str(e)}")

reader = BarCodeReader()
@app.post("/decode-qr-zxing/")
async def decode_qr_zxing(file: UploadFile = File(...)):
    if file.content_type not in ['image/jpeg', 'image/png']:
        raise HTTPException(status_code=400, detail="Invalid file format")
    try:
        image_data = await file.read()
        image = Image.open(io.BytesIO(image_data))
        image.save("temp_qr_image.png")
        result = reader.decode("temp_qr_image.png")
        if result and 'parsed' in result[0]:
            return JSONResponse(content={"data": result[0]['parsed']})
        else:
            return JSONResponse(content={"detail": "No QR code found in the image"})
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to decode QR code using ZXing: {str(e)}")

@app.get("/documentos/numero-rendicion/", response_model=List[str])
async def get_distinct_numero_rendicion(
    usuario: str = Query(..., description="Filtrar por usuario"),
    db: AsyncSession = Depends(get_db)
):
    try:
        query = select(distinct(models.Documento.numero_rendicion)).where(
            models.Documento.usuario == usuario
        )
        result = await db.execute(query)
        numeros_rendicion = result.scalars().all()
        numeros_rendicion = [str(num)
                             for num in numeros_rendicion if num is not None]
        return numeros_rendicion
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error al obtener los números de rendición: {str(e)}")
