from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Query, APIRouter, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional, Union
from datetime import date, timedelta, datetime
from sqlalchemy import distinct
import shutil
import json
from google.cloud import vision
from google.oauth2 import service_account
import os
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
from pyzbar.pyzbar import decode  # type: ignore
from num2words import num2words  # type: ignore
from pyzxing import BarCodeReader  # type: ignore
from . import crud, models, schemas, auth
from .database import engine, SessionLocal
from app.firebase_service import upload_file_to_firebase, download_file_from_firebase, upload_file_to_firebase_pdf
import cv2
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from .database import get_db
from .crud import create_rendicion_with_increment, create_solicitud_with_increment
from .schemas import RendicionCreateRequest, RendicionCreateResponse, RendicionUpdate, SolicitudCreateRequest, SolicitudCreateResponse, SolicitudUpdate, SolicitudResponse, RendicionSolicitudResponse, RendicionSolicitudCreate, RendicionResponse, ErrorResponse
from .models import Rendicion, Solicitud, RendicionSolicitud, User
from app.routers import company_api, qr_processing_api, solicitud_api, rendicion_api, user_api
from dotenv import load_dotenv
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


app = FastAPI()

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://www.arendirperu.pe",
        "https://arendirperu.pe",
    ],
    allow_credentials=True,    # Solo si necesitas enviar cookies o auth
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registrar los routers
app.include_router(company_api.router, prefix="/api", tags=["Companies"])
app.include_router(qr_processing_api.router,
                   prefix="/api", tags=["QR Processing"])
app.include_router(solicitud_api.router, prefix="/api", tags=["Solicitud"])
app.include_router(rendicion_api.router, prefix="/api", tags=["Rendicion"])
app.include_router(user_api.router, prefix="/api", tags=["User"])


@app.middleware("http")
async def https_redirect(request: Request, call_next):
    if request.headers.get("X-Forwarded-Proto") == "http":
        https_url = request.url.replace(scheme="https")
        return RedirectResponse(url=str(https_url))
    return await call_next(request)


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


def preprocess_image(image):
    gray_image = ImageOps.grayscale(image)
    enhancer = ImageEnhance.Contrast(gray_image)
    contrast_image = enhancer.enhance(2)
    open_cv_image = np.array(contrast_image)
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
        processed_image = preprocess_image(image)
        decoded_objects = decode(processed_image)
        if not decoded_objects:
            decoded_objects = decode(image)
        if not decoded_objects:
            print("No se encontró ningún código QR en la imagen")
            return JSONResponse(content={"detail": "No QR code found in the image"})

        raw_qr_data = decoded_objects[0].data.decode("utf-8")
        print("\nDatos crudos del QR:", raw_qr_data)

        # qr_data = raw_qr_data.split("|")
        qr_data = [data.strip() for data in raw_qr_data.split("|")]
        result = {}
        monetary_values = []  # Lista para almacenar todos los valores monetarios
        has_serie = False  # Bandera para indicar si ya se detectó la serie

        # El primer elemento es siempre el RUC
        if len(qr_data) > 0 and re.match(r'^\d{11}$', qr_data[0]):
            result["ruc"] = qr_data[0]
            print(f"RUC detectado (primer elemento): {qr_data[0]}")

        # Procesamos desde el segundo elemento
        for i, data in enumerate(qr_data[1:]):
            if re.match(r'^\d{8}$', data) and not has_serie and 'numero' not in result:
                # Si es un número de 8 dígitos y aún no se ha detectado serie ni número,
                # podría ser el número de documento (no necesariamente DNI)
                result["numero"] = data.zfill(8)
                print(f"Número detectado: {data.zfill(8)}")
            elif re.match(r'^\d{8}$', data) and 'numero' in result:
                # Si ya tenemos un número y aparece otro de 8 dígitos, es el DNI
                result["dni"] = data
                print(f"DNI detectado: {data}")
            elif re.match(r'^\d{2}$', data):  # Tipo de Documento
                tipo_doc_map = {
                    "01": "Factura", "02": "Recibo por Honorarios", "03": "Boleta de Venta",
                    "05": "Boleto Aéreo", "07": "Nota de Crédito", "08": "Nota de Débito",
                    "12": "Ticket", "14": "Recibo Servicio Público"
                }
                result["tipo"] = tipo_doc_map.get(data, "Desconocido")
                print(
                    f"Tipo de documento detectado: {result['tipo']} ({data})")
            elif re.match(r'^[A-Za-z0-9]{4}-\d{7,8}$', data):  # Serie con guión
                serie, numero = data.split('-')
                result["serie"] = serie
                result["numero"] = numero.zfill(8)
                has_serie = True
                print(f"Serie y número detectados: {serie}-{numero.zfill(8)}")
            # Serie sin guión (formato B205, B003, etc.)
            elif re.match(r'^[A-Za-z]{1,3}\d{1,3}$', data):
                result["serie"] = data
                has_serie = True
                print(f"Serie detectada: {data}")
            elif re.match(r'^\d+$', data) and 4 <= len(data) <= 8 and 'numero' not in result:
                # Número sin guión (solo si no hemos detectado número antes)
                # Solo si tiene entre 4 y 8 dígitos
                result["numero"] = data.zfill(8)
                print(f"Número detectado: {data.zfill(8)}")
            # Valor monetario (1 o 2 decimales)
            elif re.match(r'^\d+\.\d{1,2}$', data):
                monetary_values.append(data)
                print(f"Valor monetario detectado: {data}")
            elif re.match(r'^\d{4}-\d{2}-\d{2}$', data) or re.match(r'^\d{2}/\d{2}/\d{4}$', data):  # Fecha
                result["fecha"] = data
                print(f"Fecha detectada: {data}")

        # Asignación inteligente de valores monetarios
        if monetary_values:
            monetary_values_sorted = sorted(
                monetary_values, key=lambda x: float(x), reverse=True)
            result["total"] = monetary_values_sorted[0]

            if len(monetary_values_sorted) > 1:
                result["igv"] = monetary_values_sorted[1]

            if len(monetary_values_sorted) > 2:
                result["sub_total"] = monetary_values_sorted[2]

        print("\nResultado final procesado:", result)
        return JSONResponse(content=result)
    except Exception as e:
        print(f"\nError al decodificar QR: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to decode QR code: {str(e)}")


@app.post("/token_mail", response_model=dict)
async def login_for_access_token(form_data: schemas.UserLogin, db: AsyncSession = Depends(get_db)):
    user = await crud.get_user_by_email(db, email=form_data.email)
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=400, detail="Incorrect email or password")
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires)
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/token", response_model=dict)
async def login_for_access_token(form_data: schemas.UserLogin, db: AsyncSession = Depends(get_db)):
    # Cambiar esta línea
    user = await crud.get_user_by_username(db, username=form_data.username)
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            # Actualizar mensaje de error
            status_code=400, detail="Incorrect username or password")
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        # Usar username en el token
        data={"sub": user.username}, expires_delta=access_token_expires)
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/documentos/", response_model=schemas.Documento)
async def create_documento(documento: schemas.DocumentoCreate, db: AsyncSession = Depends(get_db)):
    # Log para verificar los datos recibidos
    print(f"Datos recibidos en el request2222222222: {documento}")

    # Verificar si ya existe un documento con los mismos campos clave
    existing_document = await db.execute(
        select(models.Documento)
        .where(models.Documento.fecha_emision == documento.fecha_emision)
        .where(models.Documento.serie == documento.serie)
        .where(models.Documento.correlativo == documento.correlativo)
        .where(models.Documento.total == documento.total)
        .limit(1)
    )

    if existing_document.scalars().first():
        raise HTTPException(
            status_code=400,
            detail="Ya existe un documento con la misma fecha de emisión, serie, correlativo y total"
        )

    result = await db.execute(
        select(models.Documento)
        .filter(models.Documento.usuario == documento.usuario)
        .filter(models.Documento.fecha_solicitud == documento.fecha_solicitud)
        .filter(models.Documento.tipo_solicitud == 'RENDICION')
        .limit(1)
    )

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
        numero_rendicion=documento.numero_rendicion,
        id_user=documento.id_user,
        id_numero_rendicion=documento.id_numero_rendicion,
        id_empresa=documento.id_empresa

    )

    print(f"Guardando el documento en la base de datos: {db_documento}")

    db.add(db_documento)
    await db.commit()
    await db.refresh(db_documento)

    print(f"Documento guardado exitosamente con ID: {db_documento.id}")

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

    query = select(models.Documento).where(models.Documento.empresa == empresa)

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

    result = await db.execute(query)
    return result.scalars().all()


# @app.put("/documentos/{documento_id}", response_model=schemas.Documento)
# async def update_documento(documento_id: int, documento: schemas.DocumentoUpdate, db: AsyncSession = Depends(get_db)):
#     db_documento = await crud.get_documento(db, documento_id=documento_id)
#     if not db_documento:
#         raise HTTPException(status_code=404, detail="Documento not found")

#     update_data = documento.dict(exclude_unset=True)
#     for key, value in update_data.items():
#         setattr(db_documento, key, value)

#     await db.commit()
#     await db.refresh(db_documento)
#     return db_documento

@app.put("/documentos/{documento_id}", response_model=schemas.Documento)
async def update_documento(
    documento_id: int,
    documento: schemas.DocumentoUpdate,
    db: AsyncSession = Depends(get_db)
):
    db_documento = await crud.get_documento(db, documento_id=documento_id)
    if not db_documento:
        raise HTTPException(status_code=404, detail="Documento not found")

    update_data = documento.dict(exclude_unset=True)
    nuevo_estado = update_data.get("estado")

    # Aplica los cambios enviados en el body
    for key, value in update_data.items():
        setattr(db_documento, key, value)

    # Si el estado queda en ABONADO o RECHAZADO, fijamos la fecha de rendición
    if nuevo_estado in ("ABONADO", "RECHAZADO"):
        db_documento.fecha_rendicion = date.today()

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


@app.get("/documentos/view/")
async def view_file(file_location: str):
    if file_location.startswith("http"):
        return RedirectResponse(url=file_location)
    if not os.path.exists(file_location):
        raise HTTPException(status_code=404, detail="File not found")
    media_type, _ = guess_type(file_location)
    return FileResponse(path=file_location, media_type=media_type)

# Configurar el logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@app.get("/documentos/export/excel")
async def export_documentos_excel(
    empresa: str = Query(None, alias="company_name"),
    estado: str = Query(None),
    username: Optional[str] = Query(None, alias="username"),  # Cambiado a str
    id_empresa: int = Query(None),
    fecha_desde: date = Query(None),
    fecha_hasta: date = Query(None),
    tipo_solicitud: str = Query(None),
    db: AsyncSession = Depends(get_db)
):
    # Convertir username a int si no está vacío
    user_id = int(username) if username and username.strip() else None

    # Construir la consulta base sin filtros obligatorios
    query = select(models.Documento)

    # Filtros opcionales
    if id_empresa:
        logger.info(f"Filtrando por empresa: {id_empresa}")
        query = query.filter(models.Documento.id_empresa == id_empresa)
    if empresa:
        logger.info(f"Filtrando por empresa: {empresa}")
        query = query.filter(models.Documento.empresa == empresa)
    if estado:
        logger.info(f"Filtrando por estado: {estado}")
        query = query.filter(models.Documento.estado == estado)
    if user_id:  # Usar el user_id convertido
        query = query.filter(models.Documento.id_user == user_id)
    if fecha_desde:
        logger.info(f"Filtrando por fecha desde: {fecha_desde}")
        query = query.filter(models.Documento.fecha_solicitud >= fecha_desde)
    if fecha_hasta:
        logger.info(f"Filtrando por fecha hasta: {fecha_hasta}")
        query = query.filter(models.Documento.fecha_solicitud <= fecha_hasta)
    if tipo_solicitud:  # Nuevo filtro por tipo_solicitud
        logger.info(f"Filtrando por tipo_solicitud: {tipo_solicitud}")
        query = query.filter(models.Documento.tipo_solicitud == tipo_solicitud)

    # Ejecutar la consulta
    result = await db.execute(query)
    documentos = result.scalars().all()

    # Log de documentos obtenidos
    logger.info(f"Cantidad de documentos obtenidos: {len(documentos)}")
    if documentos:
        logger.info(f"Primer documento: {documentos[0]}")

    # Generar el archivo Excel
    df = pd.DataFrame([{
        "Item": i + 1,
        "Codigo": doc.numero_rendicion,
        "Empresa": doc.empresa,
        "Usuario": doc.usuario,
        "Dni": doc.dni,
        "Estado": doc.estado,
        "Fecha Emision": doc.fecha_emision,
        "Fecha Rendicion": doc.fecha_rendicion,
        "RUC": doc.ruc,
        "TipoDoc": doc.tipo_documento,
        "Tipo Solicitud": doc.tipo_solicitud,
        "Cuenta Contable": doc.cuenta_contable,
        "Serie": doc.serie,
        "Correlativo": doc.correlativo,
        "Moneda": doc.moneda,
        "Tipo de Cambio": doc.tipo_cambio,
        "Afecto": doc.afecto,
        "IGV": doc.igv,
        "Inafecto": doc.inafecto,
        "Total": doc.total
    } for i, doc in enumerate(documentos)])

    logger.info(f"Archivo Excel generado con {len(df)} filas")

    excel_file = f"documentos.xlsx"
    df.to_excel(excel_file, index=False)

    return FileResponse(path=excel_file, filename="documentos.xlsx")


class PDF(FPDF):
    def __init__(self, orientation='P', company_name="ARENDIR"):
        super().__init__(orientation=orientation)  # Pasar orientation al padre
        self.company_name = company_name

    def header(self):
        # URL del logo
        logo_url = 'https://firebasestorage.googleapis.com/v0/b/hawejin-files.appspot.com/o/logo.png?alt=media&token=a58583c4-fed3-468d-abe6-92252a1c1fff'

        response = requests.get(logo_url)
        if response.status_code == 200:
            logo_path = 'temp_logo.png'
            with open(logo_path, 'wb') as f:
                f.write(response.content)
            self.image(logo_path, 10, 8, 33)
            os.remove(logo_path)
        else:
            print("No se pudo descargar la imagen.")

        # self.ln(20)

# Agregar la cabecera central "XXXXXXXXXXXX"
        self.set_font('Arial', 'B', 14)  # Fuente en negrita y tamaño 14
        self.cell(0, 10, self.company_name, 0, 1,
                  'C')  # Usar self.company_name
        self.ln(10)  # Espacio después de la cabecera

        self.set_font('Arial', '', 8)
        self.set_xy(10, 30)
        self.cell(0, 10, f'Usuario: {self.usuario}', 0, 1, 'L')
        self.set_xy(10, 40)
        self.cell(0, 10, f'DNI: {self.dni}', 0, 1, 'L')
        self.set_xy(10, 50)
        self.cell(0, 10, f'Cargo: {self.cargo}', 0, 1, 'L')
        self.set_xy(10, 60)
        self.cell(0, 10, f'Zona: {self.zona}', 0, 1, 'L')
        self.set_xy(-95, 30)
        self.cell(
            0, 10, f'Área responsable: {self.area_responsable}', 0, 1, 'R')
        self.set_xy(-95, 40)
        self.cell(
            0, 10, f'Fecha de solicitud: {self.fecha_solicitud}', 0, 1, 'R')
        self.set_xy(-95, 50)
        self.cell(
            0, 10, f'Fecha de rendición: {self.fecha_rendicion}', 0, 1, 'R')
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

    def add_firmas(self, total_anticipo, total_gasto, reembolso, nombre_solicitante, nombre_aprobador, nombre_contador):
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
        self.cell(
            col_width, 10, f'Total Anticipo: {total_anticipo}', border=1, ln=1, align='L')
        self.cell(col_width, 10, nombre_solicitante, border=1, ln=0, align='R')
        self.cell(spacing, 10, '', border=0, ln=0)
        self.cell(col_width, 10, nombre_aprobador, border=1, ln=0, align='R')
        self.cell(spacing, 10, '', border=0, ln=0)
        self.cell(col_width, 10, nombre_contador, border=1, ln=0, align='R')
        self.cell(spacing, 10, '', border=0, ln=0)
        self.cell(col_width, 10,
                  f'Total Gasto: {total_gasto}', border=1, ln=1, align='L')
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
    id_rendicion: int = Query(...,
                              description="ID de rendición (obligatorio)"),
    id_usuario: int = Query(..., description="ID del usuario (obligatorio)"),
    db: AsyncSession = Depends(get_db)
):

   # Primero obtener la rendición para extraer el id_user
    query_rendicion = select(Rendicion).filter(Rendicion.id == id_rendicion)
    result_rendicion = await db.execute(query_rendicion)
    rendicion = result_rendicion.scalar_one_or_none()

    if not rendicion:
        raise HTTPException(
            status_code=404,
            detail="No se encontró la rendición con el ID proporcionado."
        )

    # Ahora obtener el usuario asociado a la rendición
    query_usuario = select(User).filter(User.id == rendicion.id_user)
    result_usuario = await db.execute(query_usuario)
    usuario = result_usuario.scalar_one_or_none()

    if not usuario:
        raise HTTPException(
            status_code=404,
            detail="No se encontró el usuario con el ID proporcionado."
        )

    if not id_rendicion:
        raise HTTPException(
            status_code=400, detail="El campo 'id_rendicion' es obligatorio."
        )

     # Obtener información de la rendición
    query_rendicion = select(Rendicion).filter(Rendicion.id == id_rendicion)
    result_rendicion = await db.execute(query_rendicion)
    rendicion = result_rendicion.scalar_one_or_none()
    # Obtener el company_name del usuario (asumiendo que existe este campo en el modelo User)
    company_name = usuario.company_name if usuario.company_name else "ARENDIR"  # Valor por defe

    if not rendicion:
        raise HTTPException(
            status_code=404,
            detail="No se encontró la rendición con el ID proporcionado."
        )

    # Obtener los documentos de la rendición
    query = select(models.Documento).filter(
        models.Documento.id_numero_rendicion == id_rendicion,
        models.Documento.tipo_solicitud == 'RENDICION',
        models.Documento.estado != "RECHAZADO"  # Excluir documentos rechazados
    )
    result = await db.execute(query)
    documentos = result.scalars().all()

    if not documentos:
        raise HTTPException(
            status_code=404,
            detail="No se encontraron documentos para la rendición proporcionada."
        )

    # Calcular el total de gastos de los documentos obtenidos
    total_gasto = sum(doc.total for doc in documentos)

    # Obtener los `solicitud_id` asociados al `id_rendicion`
    query_solicitudes = select(models.RendicionSolicitud.solicitud_id).filter(
        models.RendicionSolicitud.rendicion_id == id_rendicion
    )
    result_solicitudes = await db.execute(query_solicitudes)
    solicitud_ids = [row[0] for row in result_solicitudes]

    # Si no hay solicitudes asociadas, establecer total_anticipo en 0
    if not solicitud_ids:
        total_anticipo = 0
    else:
        # Consultar documentos basados en los valores de `solicitud_id`
        query_documentos = select(models.Documento).filter(
            models.Documento.id_numero_rendicion.in_(solicitud_ids),
            models.Documento.tipo_solicitud == "ANTICIPO",
            models.Documento.estado != "RECHAZADO"  # Excluir documentos rechazados
        )
        result_documentos = await db.execute(query_documentos)
        documentos_anticipo = result_documentos.scalars().all()

        # Calcular el total de anticipos de los documentos obtenidos
        total_anticipo = sum(
            doc.total if doc.total is not None else 0 for doc in documentos_anticipo
        )

    # Calcular el reembolso
    reembolso = total_gasto - total_anticipo

    fecha_actual = datetime.now().strftime("%d-%m-%Y")
    # Crear el PDF
    pdf = PDF(orientation='L', company_name=company_name)
    pdf.usuario = usuario.full_name
    pdf.dni = usuario.dni
    pdf.cargo = usuario.cargo
    pdf.zona = usuario.zona_venta
    pdf.area_responsable = usuario.area
    pdf.fecha_solicitud = fecha_actual
    pdf.fecha_rendicion = fecha_actual
    pdf.tipo_gasto = "Rendición de Gastos"
    pdf.total_anticipo = total_anticipo
    pdf.total_gasto = total_gasto
    pdf.reembolso = reembolso
    pdf.add_page()

    # Agregar encabezado de la tabla
    table_header = ["Item", "Fecha", "RUC", "Tip. Doc", "Cta Contable", "Serie", "Correlativo",
                    "Moneda", "Tip. Cambio", "Afecto", "IGV", "Inafecto", "Total"]

    # Agregar datos de la tabla
    table_data = [
        [i + 1, doc.fecha_emision, doc.ruc, doc.tipo_documento, doc.cuenta_contable, doc.serie,
            doc.correlativo, doc.moneda, doc.tc, doc.afecto, doc.igv, doc.inafecto, doc.total]
        for i, doc in enumerate(documentos)
    ]
    pdf.add_table(table_header, table_data)

    # Obtener nombres para las firmas
    nombre_solicitante = usuario.full_name
    nombre_aprobador = rendicion.nom_aprobador or "Por firmar"
    nombre_contador = rendicion.nom_contador or "Por firmar"

   # Agregar las firmas con los nombres reales
    pdf.add_firmas(pdf.total_anticipo, pdf.total_gasto, pdf.reembolso,
                   nombre_solicitante, nombre_aprobador, nombre_contador)

    # Guardar el PDF generado
    pdf_file = f"documentos_{id_rendicion}.pdf"
    pdf.output(pdf_file)

    return FileResponse(path=pdf_file, filename=f"documentos_{id_rendicion}.pdf")


class DocumentoPDFCustom(FPDF):
    def __init__(self):
        super().__init__()
        # Márgenes (izquierdo, superior, derecho)
        self.set_margins(15, 15, 15)  # Márgenes más amplios
        # Salto automático de página con margen inferior
        self.set_auto_page_break(auto=True, margin=15)

    def header(self):
        self.set_font('Arial', 'B', 14)
        self.cell(0, 10, 'Solicitud de Anticipo - Viajes', 0, 1, 'C')
        self.ln(10)

    def add_document_details(self, documento):
        self.set_font('Arial', '', 10)

        # Ajustar ancho de las celdas
        ancho_celda1 = 40  # Ancho de la primera columna
        ancho_celda2 = 50  # Ancho de la segunda columna

        # Añadir información general
        self.cell(ancho_celda1, 10, 'DNI:', 1)
        self.cell(ancho_celda2, 10, documento.dni, 1)
        self.cell(ancho_celda1, 10, 'Solicitado el:', 1)
        self.cell(ancho_celda2, 10, str(documento.fecha_solicitud), 1)
        self.ln(10)

        self.cell(ancho_celda1, 10, 'Responsable:', 1)
        self.cell(ancho_celda2, 10, documento.responsable, 1)
        self.cell(ancho_celda1, 10, 'Gerencia:', 1)
        self.cell(ancho_celda2, 10, documento.gerencia, 1)
        self.ln(10)

        self.cell(ancho_celda1, 10, 'Área:', 1)
        self.cell(ancho_celda2, 10, documento.area, 1)
        self.cell(ancho_celda1, 10, 'CeCo:', 1)
        self.cell(ancho_celda2, 10, documento.ceco, 1)
        self.ln(10)

        self.cell(ancho_celda1, 10, 'Tipo de Anticipo:', 1)
        self.cell(ancho_celda2, 10, documento.tipo_anticipo, 1)
        self.cell(ancho_celda1, 10, 'Destino:', 1)
        self.cell(ancho_celda2, 10, documento.destino, 1)
        self.ln(10)

        self.cell(ancho_celda1, 10, 'Fecha de Viaje:', 1)
        self.cell(ancho_celda2, 10, str(documento.fecha_emision), 1)
        self.cell(ancho_celda1, 10, 'Días:', 1)
        self.cell(ancho_celda2, 10, str(documento.dias), 1)
        self.ln(10)

        self.cell(ancho_celda1, 10, 'Presupuesto:', 1)
        self.cell(ancho_celda2, 10, f"{documento.presupuesto:.2f}", 1)
        self.cell(ancho_celda1, 10, 'Banco:', 1)
        self.cell(ancho_celda2, 10, documento.banco, 1)
        self.ln(10)

        self.cell(ancho_celda1, 10, 'N° de Cuenta:', 1)
        self.cell(ancho_celda2, 10, documento.numero_cuenta, 1)
        self.cell(ancho_celda1, 10, 'Motivo:', 1)
        self.cell(ancho_celda2, 10, documento.motivo, 1)
        self.ln(10)

        self.cell(ancho_celda1, 10, 'Tipo Viaje:', 1)
        self.cell(ancho_celda2, 10, documento.tipo_viaje, 1)
        self.cell(ancho_celda1, 10, 'Moneda:', 1)
        self.cell(ancho_celda2, 10, documento.moneda, 1)
        self.ln(10)

        self.cell(ancho_celda1, 10, 'Total:', 1)
        self.cell(ancho_celda2, 10, f"{documento.total:.2f}", 1)
        self.ln(20)

        # Añadir sección de firmas
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, 'Firmas', 0, 1, 'C')
        self.set_font('Arial', '', 10)
        self.cell(ancho_celda1, 10, 'Usuario Responsable:', 1)
        self.cell(ancho_celda2, 10, documento.responsable, 1)
        self.cell(ancho_celda1, 10, 'Aprobado por:', 1)
        self.cell(ancho_celda2, 10, '', 1)
        self.ln(10)

        self.cell(ancho_celda1, 10, 'Administracion / Contabilidad:', 1)
        self.cell(ancho_celda2, 10, '', 1)
        self.cell(ancho_celda1, 10, 'Ejecutado por:', 1)
        self.cell(ancho_celda2, 10, '', 1)
        self.ln(10)


# @app.post("/documentos/crear-con-pdf-custom/", response_model=schemas.Documento)
# async def create_documento_con_pdf_custom(
#     documento: schemas.DocumentoCreate,
#     db: AsyncSession = Depends(get_db)
# ):
#     # Crear el documento en la base de datos
#     db_documento = await crud.create_documento(db=db, documento=documento)

#     # Generar el PDF con los detalles del documento
#     pdf = DocumentoPDFCustom()
#     pdf.add_page()
#     pdf.add_document_details(documento)

#     # Crear un objeto BytesIO para almacenar el PDF
#     pdf_data = BytesIO()

#     try:
#         # Guardar el contenido del PDF en el objeto BytesIO
#         # El argumento 'S' devuelve el PDF como una cadena
#         pdf_output = pdf.output(dest='S').encode('latin1')
#         pdf_data.write(pdf_output)
#         # Asegúrate de que el puntero esté al inicio del archivo
#         pdf_data.seek(0)

#         # Crear un nombre de archivo aleatorio usando UUID
#         unique_filename = f"documento_{str(uuid.uuid4())}.pdf"

#         # Subir el archivo PDF a Firebase
#         public_url = upload_file_to_firebase_pdf(
#             pdf_data, unique_filename, content_type="application/pdf")

#     except Exception as e:
#         logging.error(f"Error al generar o subir el PDF: {str(e)}")
#         raise HTTPException(
#             status_code=500, detail=f"Error al generar o subir el archivo a Firebase: {str(e)}")
#     db_documento.archivo = public_url
#     await db.commit()
#     await db.refresh(db_documento)
#     return db_documento

@app.post("/documentos/crear-con-pdf-custom/", response_model=schemas.Documento)
async def create_documento_con_pdf_custom(
    documento: schemas.DocumentoCreate,
    db: AsyncSession = Depends(get_db)
):
    # 1) Crear el documento en la base de datos
    db_documento = await crud.create_documento(db=db, documento=documento)

    # 2) Generar el PDF
    pdf = DocumentoPDFCustom()
    pdf.add_page()
    pdf.add_document_details(documento)

    pdf_data = BytesIO()
    try:
        # 3) Obtener la salida del PDF en memoria
        pdf_output = pdf.output(dest='S')
        if isinstance(pdf_output, str):
            # cuando es str, lo codificamos
            output_bytes = pdf_output.encode('latin1')
        else:
            # cuando es bytearray o bytes, lo usamos directamente
            output_bytes = bytes(pdf_output)
        pdf_data.write(output_bytes)
        pdf_data.seek(0)

        # 4) Subir a Firebase con un nombre único
        unique_filename = f"documento_{uuid.uuid4()}.pdf"
        public_url = upload_file_to_firebase_pdf(
            pdf_data, unique_filename, content_type="application/pdf"
        )

    except Exception as e:
        logging.error(f"Error al generar o subir el PDF: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error al generar o subir el archivo a Firebase: {e}"
        )

    # 5) Guardar la URL en la base y devolver
    db_documento.archivo = public_url
    await db.commit()
    await db.refresh(db_documento)
    return db_documento

async def get_db():
    async with SessionLocal() as session:
        yield session

# Clase para generar el PDF personalizado para el modelo local


class DocumentoPDFLocal(FPDF):
    def __init__(self):
        super().__init__()
        # Establece márgenes (izquierdo, superior, derecho)
        self.set_margins(15, 15, 15)  # Márgenes de 15 mm en todos los lados
        # Salto automático de página con margen inferior
        self.set_auto_page_break(auto=True, margin=15)

    def header(self):
        self.set_font('Arial', 'B', 14)
        self.cell(0, 10, 'Solicitud de Anticipo - Gasto Local', 0, 1, 'C')
        self.ln(10)

    def add_document_details(self, documento: schemas.DocumentoCreate):
        self.set_font('Arial', '', 10)

        # Configuración del ancho de las celdas
        ancho_celda1 = 40  # Ancho de la primera columna
        ancho_celda2 = 50  # Ancho de la segunda columna

        # Cabecera del documento
        self.cell(ancho_celda1, 10, 'ANTICIPO', 1)
        self.cell(ancho_celda2, 10, '1', 1)
        self.cell(0, 10, 'OPEX READY SAC', 0, 1, 'R')
        self.ln(10)

        # Información del documento
        self.cell(ancho_celda1, 10, 'DNI:', 1)
        self.cell(ancho_celda2, 10, documento.dni if documento.dni else 'N/A', 1)
        self.cell(ancho_celda1, 10, 'Solicitado el:', 1)
        self.cell(ancho_celda2, 10, str(documento.fecha_emision)
                  if documento.fecha_emision else 'N/A', 1)
        self.ln(10)

        self.cell(ancho_celda1, 10, 'Responsable:', 1)
        self.cell(ancho_celda2, 10,
                  documento.responsable if documento.responsable else 'N/A', 1)
        self.cell(ancho_celda1, 10, 'Gerencia:', 1)
        self.cell(ancho_celda2, 10,
                  documento.gerencia if documento.gerencia else 'N/A', 1)
        self.ln(10)

        self.cell(ancho_celda1, 10, 'Área:', 1)
        self.cell(ancho_celda2, 10,
                  documento.area if documento.area else 'N/A', 1)
        self.cell(ancho_celda1, 10, 'CeCo:', 1)
        self.cell(ancho_celda2, 10,
                  documento.ceco if documento.ceco else 'N/A', 1)
        self.ln(10)

        self.cell(ancho_celda1, 10, 'Breve motivo:', 1)
        self.cell(ancho_celda2, 10,
                  documento.motivo if documento.motivo else 'N/A', 1)
        self.cell(ancho_celda1, 10, 'Banco y N° de Cuenta:', 1)
        self.cell(ancho_celda2, 10,
                  documento.numero_cuenta if documento.numero_cuenta else 'N/A', 1)
        self.ln(10)

        self.cell(ancho_celda1, 10, 'Moneda:', 1)
        self.cell(ancho_celda2, 10,
                  documento.moneda if documento.moneda else 'N/A', 1)
        self.cell(ancho_celda1, 10, 'Presupuesto:', 1)
        self.cell(ancho_celda2, 10,
                  f"{documento.total:.2f}" if documento.total else "0.00", 1)
        self.ln(10)

        # Firmas
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, 'Firmas electrónicas desde la Plataforma', 0, 1, 'C')
        self.set_font('Arial', '', 10)
        self.cell(ancho_celda1, 10, 'Usuario Responsable:', 1)
        self.cell(ancho_celda2, 10,
                  documento.responsable if documento.responsable else 'N/A', 1)
        self.cell(ancho_celda1, 10, 'Aprobado por:', 1)
        self.cell(ancho_celda2, 10, '', 1)
        self.ln(10)

        self.cell(ancho_celda1, 10, 'Administracion / Contabilidad:', 1)
        self.cell(ancho_celda2, 10, '', 1)
        self.cell(ancho_celda1, 10, 'Ejecutado por:', 1)
        self.cell(ancho_celda2, 10, '', 1)
        self.ln(10)


# @app.post("/documentos/crear-con-pdf-local/", response_model=schemas.Documento)
# async def create_documento_con_pdf_local(
#     documento: schemas.DocumentoCreate,
#     db: AsyncSession = Depends(get_db)
# ):
#     # Crear el documento en la base de datos
#     db_documento = await crud.create_documento(db=db, documento=documento)

#     pdf = DocumentoPDFLocal()  # Instancia de la clase correctamente
#     pdf.add_page()
#     pdf.add_document_details(documento)  # Pasar el objeto documento

#     pdf_data = BytesIO()

#     try:
#         pdf_output = pdf.output(dest='S').encode('latin1')
#         pdf_data.write(pdf_output)
#         pdf_data.seek(0)
#         unique_filename = f"documento_local_{str(uuid.uuid4())}.pdf"
#         public_url = upload_file_to_firebase_pdf(
#             pdf_data, unique_filename, content_type="application/pdf")

#     except Exception as e:
#         logging.error(f"Error al generar o subir el PDF: {str(e)}")
#         raise HTTPException(
#             status_code=500, detail=f"Error al generar o subir el archivo a Firebase: {str(e)}")

#     # Asignar la URL del PDF generado
#     db_documento.archivo = public_url
#     db_documento.numero_rendicion = documento.numero_rendicion  # Guardar numero_rendicion
#     await db.commit()
#     await db.refresh(db_documento)

#     return db_documento

@app.post("/documentos/crear-con-pdf-local/", response_model=schemas.Documento)
async def create_documento_con_pdf_local(
    documento: schemas.DocumentoCreate,
    db: AsyncSession = Depends(get_db)
):
    # Crear el documento en la base de datos
    db_documento = await crud.create_documento(db=db, documento=documento)

    pdf = DocumentoPDFLocal()
    pdf.add_page()
    pdf.add_document_details(documento)

    pdf_data = BytesIO()

    try:
        # Modificación aquí - manejar ambos casos (str y bytearray)
        pdf_output = pdf.output(dest='S')
        if isinstance(pdf_output, str):
            pdf_data.write(pdf_output.encode('latin1'))
        else:  # Si es bytearray o bytes
            pdf_data.write(pdf_output)
            
        pdf_data.seek(0)
        unique_filename = f"documento_local_{str(uuid.uuid4())}.pdf"
        public_url = upload_file_to_firebase_pdf(
            pdf_data, unique_filename, content_type="application/pdf")

    except Exception as e:
        logging.error(f"Error al generar o subir el PDF: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error al generar o subir el archivo a Firebase: {str(e)}")

    # Asignar la URL del PDF generado
    db_documento.archivo = public_url
    db_documento.numero_rendicion = documento.numero_rendicion
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
        self.cell(0, 5, '20612958271', 0, 1, 'L')
        self.ln(5)

    def add_document_details(self, documento):
        self.set_font('Arial', '', 10)

        # Información principal
        self.cell(0, 5, 'Solicitante: ' +
                  documento.get('full_name', 'N/A'), 0, 1, 'L')
        self.cell(0, 5, 'DNI: ' + str(documento.get('dni', 'N/A')), 0, 1, 'L')
        self.cell(0, 5, 'CeCo: ' + documento.get('ceco', 'N/A'), 0, 1, 'R')
        gerencia = documento.get('gerencia', '')
        self.cell(0, 5, 'Gerencia: ' +
                  gerencia if gerencia else 'Gerencia: N/A', 0, 1, 'R')
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
        self.cell(30, 6, 'S/ ' + str(documento.get('total', '0.00')), 1, 0, 'C')
        self.cell(30, 6, 'S/ ' +
                  str(documento.get('gasto_no_deducible', '0.00')), 1, 0, 'C')
        self.cell(30, 6, 'S/ ' + str(documento.get('total', '0.00')), 1, 1, 'C')
        self.set_font('Arial', 'B', 10)
        self.cell(210, 6, 'Total', 1, 0, 'R')
        self.cell(30, 6, 'S/ ' + str(documento.get('total', '0.00')), 1, 1, 'C')
        self.ln(10)

        # Convertir el total a texto
        total = documento.get('total', 0)
        if total:
            entero = int(total)
            decimal = int(round((total - entero) * 100))
            total_text = f"{num2words(entero, lang='es')} y {decimal}/100"
        else:
            total_text = 'N/A'

        self.cell(0, 5, 'Son: ' + total_text + ' Soles', 0, 1, 'L')
        self.ln(5)
        self.cell(0, 5, 'Firmas electrónicas desde Plataforma', 0, 1, 'L')
        self.ln(10)
        self.cell(90, 6, 'Colaborador', 1, 0, 'C')
        self.cell(90, 6, 'Aprobador', 1, 0, 'C')
        self.cell(90, 6, 'Administrador/Contabilidad', 1, 1, 'C')

        self.cell(90, 6, documento.get('full_name', 'N/A'), 1, 0, 'C')
        self.cell(90, 6, '', 1, 0, 'C')  # Celda en blanco
        self.cell(90, 6, '', 1, 1, 'C')


@app.post("/generar-pdf-movilidad/")
async def generar_pdf(data: dict, db: AsyncSession = Depends(get_db)):

    pdf = DocumentoPDFMovilidad()
    pdf.add_page()
    pdf.add_document_details(data)

    pdf_data = BytesIO()

    try:
        # pdf_output = pdf.output(dest='S').encode('latin1')
        # pdf_data.write(pdf_output)
        # pdf_data.seek(0)
        # pdf_filename = f"reporte_movilidad_{str(uuid.uuid4())}.pdf"
        # public_url = upload_file_to_firebase_pdf(
        #     pdf_data, pdf_filename, content_type="application/pdf")

        # Generar el PDF en memoria
        pdf_output = pdf.output(dest='S')
        # Si es str, lo codificamos; si es bytes/bytearray, lo usamos directamente
        if isinstance(pdf_output, str):
            pdf_bytes = pdf_output.encode('latin-1')
        else:
            pdf_bytes = bytes(pdf_output)
        pdf_data.write(pdf_bytes)
        pdf_data.seek(0)

        # Subir a Firebase
        pdf_filename = f"reporte_movilidad_{uuid.uuid4()}.pdf"
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
        correlativo=data['correlativo'],
        ruc=data['ruc'],
        dni=data['dni'],
        tipo_cambio=data['tipo_cambio'],
        tc=data['tipo_cambio'],
        afecto=data['afecto'],
        inafecto=data['inafecto'],
        igv=data['igv'],
        serie=data['serie'],
        gerencia=data['gerencia'],
        archivo=public_url,
        estado="POR APROBAR",
        empresa=data['empresa'],
        moneda="PEN",
        tipo_documento="Recibo de Movilidad",
        total=data['total'],
        rubro=data['rubro'],
        cuenta_contable=data['cuenta_contable'],
        motivo=data['motivo'],
        origen=data['origen'],
        destino=data['destino'],
        tipo_solicitud="RENDICION",
        numero_rendicion=data['numero_rendicion'],
        id_numero_rendicion=data['id_numero_rendicion'],
        id_user=data['id_user'],
        id_empresa=data['id_empresa'],
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


@app.post("/solicitud/", response_model=SolicitudCreateResponse)
async def create_solicitud(solicitud_request: SolicitudCreateRequest, db: AsyncSession = Depends(get_db)):
    try:
        id_user = solicitud_request.id_user
        id_empresa = solicitud_request.id_empresa
        new_solicitud = await create_solicitud_with_increment(db, id_user, id_empresa)
        return new_solicitud
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/solicitud/last", response_model=Union[SolicitudCreateResponse, ErrorResponse])
async def get_last_solicitud(id_user: int, tipo: str, db: AsyncSession = Depends(get_db)):
    try:
        # Consulta para obtener la última solicitud
        result = await db.execute(
            select(models.Solicitud)
            .where(models.Solicitud.id_user == id_user)
            .where(models.Solicitud.tipo == tipo)
            .order_by(models.Solicitud.id.desc())
            .limit(1)
        )

        last_solicitud = result.scalars().first()

        # Si no se encuentra ninguna solicitud, devolver un mensaje
        if not last_solicitud:
            return ErrorResponse(detail="Aún no se han creado solicitudes para este usuario con este tipo.")

        # Si se encuentra, devolver la solicitud
        return last_solicitud
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error interno del servidor: {str(e)}")


@app.post("/rendicion_solicitud", response_model=RendicionSolicitudResponse)
async def create_rendicion_solicitud(
    rendicion_solicitud: RendicionSolicitudCreate, db: AsyncSession = Depends(get_db)
):
    try:
        # Verificar si la relación ya existe
        existing = await db.execute(
            select(RendicionSolicitud)
            .where(
                RendicionSolicitud.rendicion_id == rendicion_solicitud.rendicion_id,
                RendicionSolicitud.solicitud_id == rendicion_solicitud.solicitud_id,
            )
        )
        if existing.scalars().first():
            raise HTTPException(
                status_code=400, detail="La relación entre rendición y solicitud ya existe."
            )

        # Crear nueva relación
        nueva_rendicion_solicitud = RendicionSolicitud(
            rendicion_id=rendicion_solicitud.rendicion_id,
            solicitud_id=rendicion_solicitud.solicitud_id,
            estado=rendicion_solicitud.estado,
            fecha_creacion=datetime.now()
        )
        db.add(nueva_rendicion_solicitud)
        await db.commit()
        await db.refresh(nueva_rendicion_solicitud)

        return nueva_rendicion_solicitud

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error al crear la relación: {str(e)}")
    

# CREDENTIALS_PATH = "credentials/google-vision.json"  

# credentials = service_account.Credentials.from_service_account_file(CREDENTIALS_PATH)
# client = vision.ImageAnnotatorClient(credentials=credentials)

# Cargar credenciales desde variable de entorno
credentials_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
if not credentials_json:
    raise RuntimeError("La variable de entorno GOOGLE_CREDENTIALS_JSON no está definida")

credentials_info = json.loads(credentials_json)
credentials = service_account.Credentials.from_service_account_info(credentials_info)

@app.post("/extract-ticket/")
async def extract_ticket_google(file: UploadFile = File(...)):
    if file.content_type not in ['image/jpeg', 'image/png']:
        raise HTTPException(status_code=400, detail="Archivo no compatible")

    try:
        image_data = await file.read()
        image = vision.Image(content=image_data)

        response = client.text_detection(image=image)
        texts = response.text_annotations

        if not texts:
            return {"message": "No se encontró texto"}

        full_text = texts[0].description
        lines = [line.strip() for line in full_text.split("\n") if line.strip()]

        result = {
            "ruc": None,
            "empresa": None,
            "fecha": None,
            "hora": None,
            "habitacion": None,
            "total": None
        }

        for line in lines:
            if not result["ruc"]:
                match = re.search(r'\b\d{11}\b', line)
                if match:
                    result["ruc"] = match.group()

            if not result["fecha"]:
                match = re.search(r'\d{2}[-/]\d{2}[-/]\d{4}', line)
                if match:
                    result["fecha"] = match.group()

            if not result["hora"]:
                match = re.search(r'\d{1,2}:\d{2}\s*(am|pm)', line.lower())
                if match:
                    result["hora"] = match.group()

            if not result["total"] and "total" in line.lower():
                match = re.search(r'(\d+\.\d{2})', line)
                if match:
                    result["total"] = match.group()

            if not result["empresa"] and "SAC" in line:
                result["empresa"] = line

            if not result["habitacion"] and "habitacion" in line.lower():
                match = re.search(r'\b\d+\b', line)
                if match:
                    result["habitacion"] = match.group()

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al usar Google Vision: {str(e)}")