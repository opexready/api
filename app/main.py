from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Query, APIRouter, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional, Union
from datetime import date, timedelta, datetime
from sqlalchemy import distinct
import shutil
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
from num2words import num2words # type: ignore
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registrar los routers
app.include_router(company_api.router, prefix="/api", tags=["Companies"])
app.include_router(qr_processing_api.router, prefix="/api", tags=["QR Processing"])
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
            # Detectar serie con guion (formato BEW3-00425292)
            elif re.match(r'^[A-Za-z0-9]{4}-\d{7,8}$', data):
                serie, numero = data.split('-')
                result["serie"] = serie
                # Rellena con ceros si es necesario
                result["numero"] = numero.zfill(8)
            # Detectar serie (alfanumérico sin guion como BL22) seguida de un número
            # Detectar serie alfanumérica
            elif re.match(r'^[A-Za-z0-9]{2,4}$', data):
                result["serie"] = data
            elif re.match(r'^\d+$', data) and 3 < len(data) < 9:  # Detectar número (sin guion)
                # Rellenar con ceros si es necesario
                result["numero"] = data.zfill(8)
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

# @app.post("/users/", response_model=schemas.User)
# async def create_user(user: schemas.UserCreate, db: AsyncSession = Depends(get_db)):
#     db_user = await crud.get_user_by_email(db, email=user.email)
#     if db_user:
#         raise HTTPException(status_code=400, detail="Email already registered")
#     if not hasattr(user, "id_empresa") or user.id_empresa is None:
#         user.id_empresa = 2
#     if not hasattr(user, "estado") or user.estado is None:
#         user.estado = True
#     return await crud.create_user(db=db, user=user)

# @app.get("/users/", response_model=List[schemas.User])
# async def read_users(db: AsyncSession = Depends(get_db)):
#     return await crud.get_users(db)

# @app.get("/users/by-company-and-role/", response_model=List[schemas.User])
# async def read_users_by_company_and_role(company_name: str = Query(...), role: str = Query(...), db: AsyncSession = Depends(get_db)):
#     users = await crud.get_users_by_company_and_role(db, company_name, role)
#     if not users:
#         raise HTTPException(
#             status_code=404, detail="No users found for the specified company_name and role")
#     return users

# @app.get("/users/with-pending-documents/", response_model=List[schemas.UserWithPendingDocuments])
# async def read_users_with_pending_documents(empresa: str = Query(...), db: AsyncSession = Depends(get_db)):
#     return await crud.get_users_with_pending_documents(db, empresa)

# @app.get("/users/by-email/", response_model=schemas.User)
# async def read_user_by_email(email: str = Query(...), db: AsyncSession = Depends(get_db)):
#     user = await crud.get_user_by_email(db, email=email)
#     if not user:
#         raise HTTPException(status_code=404, detail="User not found")
#     return user

@app.post("/documentos/", response_model=schemas.Documento)
async def create_documento(documento: schemas.DocumentoCreate, db: AsyncSession = Depends(get_db)):
    # Log para verificar los datos recibidos
    print(f"Datos recibidos en el request2222222222: {documento}")

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
        id_numero_rendicion=documento.id_numero_rendicion

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
    username: str = Query(None),
    fecha_desde: date = Query(None),
    fecha_hasta: date = Query(None),
    db: AsyncSession = Depends(get_db)
):

    # Construir la consulta base sin filtros obligatorios
    query = select(models.Documento)

    # Filtros opcionales
    if empresa:
        logger.info(f"Filtrando por empresa: {empresa}")
        query = query.filter(models.Documento.empresa == empresa)
    if estado:
        logger.info(f"Filtrando por estado: {estado}")
        query = query.filter(models.Documento.estado == estado)
    if username:
        logger.info(f"Filtrando por usuario: {username}")
        query = query.filter(models.Documento.usuario == username)
    if fecha_desde:
        logger.info(f"Filtrando por fecha desde: {fecha_desde}")
        query = query.filter(models.Documento.fecha_solicitud >= fecha_desde)
    if fecha_hasta:
        logger.info(f"Filtrando por fecha hasta: {fecha_hasta}")
        query = query.filter(models.Documento.fecha_solicitud <= fecha_hasta)

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
        "Fecha": doc.fecha_emision,
        "RUC": doc.ruc,
        "TipoDoc": doc.tipo_documento,
        "Cuenta Contable": doc.cuenta_contable,
        "Serie": doc.serie,
        "Correlativo": doc.correlativo,
        "Moneda": doc.moneda,
        "Tipo de Cambio": doc.tc,
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

        self.ln(20)

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
    id_rendicion: int = Query(..., description="ID de rendición (obligatorio)"),
    id_usuario: int = Query(..., description="ID del usuario (obligatorio)"),
    db: AsyncSession = Depends(get_db)
):

    query_usuario = select(User).filter(User.id == id_usuario)
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

    # Obtener los documentos de la rendición
    query = select(models.Documento).filter(
        models.Documento.id_numero_rendicion == id_rendicion
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
            models.Documento.tipo_solicitud == "ANTICIPO"
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
    pdf = PDF(orientation='L')
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
        [i + 1, doc.fecha_emision, doc.ruc, doc.tipo_documento, doc.cuenta_contable, doc.serie, doc.correlativo, doc.moneda, doc.tc, doc.afecto, doc.igv, doc.inafecto, doc.total]
        for i, doc in enumerate(documentos)
    ]
    pdf.add_table(table_header, table_data)

    # Agregar las firmas
    pdf.add_firmas(pdf.total_anticipo, pdf.total_gasto, pdf.reembolso)

    # Guardar el PDF generado
    pdf_file = f"documentos_{id_rendicion}.pdf"
    pdf.output(pdf_file)

    return FileResponse(path=pdf_file, filename=f"documentos_{id_rendicion}.pdf")

class DocumentoPDFCustom(FPDF):
    def __init__(self):
        super().__init__()
        # Márgenes (izquierdo, superior, derecho)
        self.set_margins(15, 15, 15)  # Márgenes más amplios
        self.set_auto_page_break(auto=True, margin=15)  # Salto automático de página con margen inferior

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
    def __init__(self):
        super().__init__()
        # Establece márgenes (izquierdo, superior, derecho)
        self.set_margins(15, 15, 15)  # Márgenes de 15 mm en todos los lados
        self.set_auto_page_break(auto=True, margin=15)  # Salto automático de página con margen inferior

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
        self.cell(ancho_celda2, 10, str(documento.fecha_emision) if documento.fecha_emision else 'N/A', 1)
        self.ln(10)

        self.cell(ancho_celda1, 10, 'Responsable:', 1)
        self.cell(ancho_celda2, 10, documento.responsable if documento.responsable else 'N/A', 1)
        self.cell(ancho_celda1, 10, 'Gerencia:', 1)
        self.cell(ancho_celda2, 10, documento.gerencia if documento.gerencia else 'N/A', 1)
        self.ln(10)

        self.cell(ancho_celda1, 10, 'Área:', 1)
        self.cell(ancho_celda2, 10, documento.area if documento.area else 'N/A', 1)
        self.cell(ancho_celda1, 10, 'CeCo:', 1)
        self.cell(ancho_celda2, 10, documento.ceco if documento.ceco else 'N/A', 1)
        self.ln(10)

        self.cell(ancho_celda1, 10, 'Breve motivo:', 1)
        self.cell(ancho_celda2, 10, documento.motivo if documento.motivo else 'N/A', 1)
        self.cell(ancho_celda1, 10, 'Banco y N° de Cuenta:', 1)
        self.cell(ancho_celda2, 10, documento.numero_cuenta if documento.numero_cuenta else 'N/A', 1)
        self.ln(10)

        self.cell(ancho_celda1, 10, 'Moneda:', 1)
        self.cell(ancho_celda2, 10, documento.moneda if documento.moneda else 'N/A', 1)
        self.cell(ancho_celda1, 10, 'Presupuesto:', 1)
        self.cell(ancho_celda2, 10, f"{documento.total:.2f}" if documento.total else "0.00", 1)
        self.ln(10)

        # Firmas
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, 'Firmas electrónicas desde la Plataforma', 0, 1, 'C')
        self.set_font('Arial', '', 10)
        self.cell(ancho_celda1, 10, 'Usuario Responsable:', 1)
        self.cell(ancho_celda2, 10, documento.responsable if documento.responsable else 'N/A', 1)
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
#     db_documento.archivo = public_url
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

    # Asignar la URL del PDF generado
    db_documento.archivo = public_url
    db_documento.numero_rendicion = documento.numero_rendicion  # Guardar numero_rendicion
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
        self.cell(0, 5, 'Solicitante: ' + documento.get('full_name', 'N/A'), 0, 1, 'L')
        self.cell(0, 5, 'DNI: ' + str(documento.get('dni', 'N/A')), 0, 1, 'L')
        self.cell(0, 5, 'CeCo: ' + documento.get('ceco', 'N/A'), 0, 1, 'R')
        self.cell(0, 5, 'Gerencia: ' + documento.get('gerencia', 'N/A'), 0, 1, 'R')
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
        self.cell(30, 6, 'S/ ' + str(documento.get('gasto_no_deducible', '0.00')), 1, 0, 'C')
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
        self.cell(90, 6, 'Aprobador', 1, 0, 'C')
        self.cell(90, 6, 'Administrador/Contabilidad', 1, 1, 'C')
        self.cell(90, 6, documento.get('full_name', 'N/A'), 1, 0, 'C')
        self.cell(90, 6, '', 1, 1, 'C')


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
        correlativo=data['correlativo'],
        ruc=data['ruc'],
        dni=data['dni'],
        tipo_cambio=data['tipo_cambio'],
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
        numeros_rendicion = [str(num) for num in numeros_rendicion if num is not None]
        return numeros_rendicion
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error al obtener los números de rendición: {str(e)}")

@app.get("/rendiciones/", response_model=list[schemas.Rendicion])
async def read_rendiciones(db: AsyncSession = Depends(get_db)):
    return await crud.get_rendiciones(db)


@app.post("/rendicion/", response_model=RendicionCreateResponse)
async def create_rendicion(rendicion_request: RendicionCreateRequest, db: AsyncSession = Depends(get_db)):
    try:
        id_user = rendicion_request.id_user
        new_rendicion = await create_rendicion_with_increment(db, id_user)
        return new_rendicion
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Método para obtener el último registro de rendición por id_user


@app.post("/solicitud/", response_model=SolicitudCreateResponse)
async def create_solicitud(solicitud_request: SolicitudCreateRequest, db: AsyncSession = Depends(get_db)):
    try:
        id_user = solicitud_request.id_user
        new_solicitud = await create_solicitud_with_increment(db, id_user)
        return new_solicitud
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/rendicion/last", response_model=RendicionCreateResponse)
async def get_last_rendicion(id_user: int, tipo: str, db: AsyncSession = Depends(get_db)):
    try:
        # Consulta para obtener la última rendición por id de usuario
        result = await db.execute(
            select(models.Rendicion)
            .where(models.Rendicion.id_user == id_user)
            .where(models.Rendicion.tipo == tipo)
            .order_by(models.Rendicion.id.desc())
            .limit(1)
        )

        last_rendicion = result.scalars().first()

        if not last_rendicion:
            raise HTTPException(
                status_code=404, detail="No se encontró ninguna rendición para este usuario")

        return last_rendicion
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


@app.get("/rendicion/nombres", response_model=list[str])
async def get_unique_rendicion_names(id_user: int, tipo: str, db: AsyncSession = Depends(get_db)):
    try:
        # Consulta para obtener los nombres de las rendiciones sin repetir, filtradas por id_user y tipo
        result = await db.execute(
            select(distinct(models.Rendicion.nombre))
            .where(models.Rendicion.id_user == id_user, models.Rendicion.tipo == tipo)
        )

        # Obtener todos los nombres únicos de la consulta
        nombres_rendicion = result.scalars().all()

        if not nombres_rendicion:
            raise HTTPException(
                status_code=404, detail="No se encontraron rendiciones para este usuario con el tipo especificado")

        return nombres_rendicion

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/rendiciones/nombres", response_model=list[RendicionResponse])
async def get_unique_rendicion_names(id_user: int, tipo: str, db: AsyncSession = Depends(get_db)):
    try:
        # Consulta para obtener los nombres de las rendiciones sin repetir, filtradas por id_user y tipo
        result = await db.execute(
            select(models.Rendicion)
            .where(models.Rendicion.id_user == id_user, models.Rendicion.tipo == tipo)
        )

        # Obtener todos los nombres únicos de la consulta
        nombres_rendicion = result.scalars().all()

        if not nombres_rendicion:
            raise HTTPException(
                status_code=404, detail="No se encontraron rendiciones para este usuario con el tipo especificado")

        return nombres_rendicion

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class RendicionUpdate(BaseModel):
    nombre: Optional[str] = None
    tipo: Optional[str] = None
    estado: Optional[str] = None


@app.put("/rendicion/{rendicion_id}", response_model=dict)
async def update_rendicion(
    rendicion_id: int,
    rendicion_data: RendicionUpdate,
    db: AsyncSession = Depends(get_db)
):
    # Buscar la rendición por ID
    result = await db.execute(select(Rendicion).where(Rendicion.id == rendicion_id))
    db_rendicion = result.scalars().first()

    if not db_rendicion:
        raise HTTPException(status_code=404, detail="Rendición no encontrada")

    # Actualizar solo los campos proporcionados
    update_data = rendicion_data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_rendicion, key, value)

    # Guardar cambios
    await db.commit()
    await db.refresh(db_rendicion)

    return {"detail": "Rendición actualizada exitosamente"}

###################


# @app.get("/rendiciones/con-documentos/", response_model=list[dict])
# async def get_rendiciones_con_documentos_filtradas(
#     tipo: Optional[str] = Query(None, description="Filtrar por tipo de rendición"),
#     estado: Optional[str] = Query(None, description="Filtrar por estado de la rendición"),
#     fecha_registro_from: Optional[date] = Query(None, description="Filtrar desde esta fecha de registro"),
#     fecha_registro_to: Optional[date] = Query(None, description="Filtrar hasta esta fecha de registro"),
#     fecha_actualizacion_from: Optional[date] = Query(None, description="Filtrar desde esta fecha de actualización"),
#     fecha_actualizacion_to: Optional[date] = Query(None, description="Filtrar hasta esta fecha de actualización"),
#     id_user: Optional[int] = Query(None, description="Filtrar por ID de usuario"),
#     db: AsyncSession = Depends(get_db)
# ):
#     """
#     Devuelve una lista de rendiciones que tienen documentos asociados, aplicando filtros opcionales.
#     """
#     try:
#         # Construir la consulta base para las rendiciones
#         query = (
#             select(models.Rendicion)
#             .join(models.Documento, models.Documento.numero_rendicion == models.Rendicion.nombre)
#             .distinct()
#         )

#         if tipo:
#             query = query.where(models.Rendicion.tipo == tipo)
#         if estado:
#             query = query.where(models.Rendicion.estado == estado)
#         if fecha_registro_from:
#             query = query.where(models.Rendicion.fecha_registro >= fecha_registro_from)
#         if fecha_registro_to:
#             query = query.where(models.Rendicion.fecha_registro <= fecha_registro_to)
#         if fecha_actualizacion_from:
#             query = query.where(models.Rendicion.fecha_actualizacion >= fecha_actualizacion_from)
#         if fecha_actualizacion_to:
#             query = query.where(models.Rendicion.fecha_actualizacion <= fecha_actualizacion_to)
#         if id_user:
#             query = query.where(models.Rendicion.idUser == id_user)

#         # Ejecutar la consulta para rendiciones
#         rendiciones_query = await db.execute(query)
#         rendiciones = rendiciones_query.scalars().all()

#         # Crear la respuesta con los documentos relacionados
#         resultado = []
#         for rendicion in rendiciones:
#             # Buscar documentos relacionados con el nombre de la rendición (numero_rendicion)
#             documentos_query = await db.execute(
#                 select(models.Documento).where(models.Documento.numero_rendicion == rendicion.nombre)
#             )
#             documentos = documentos_query.scalars().all()

#             # Solo agregar rendiciones con documentos asociados
#             if documentos:
#                 resultado.append({
#                     "rendicion": {
#                         "id": rendicion.id,
#                         "idUser": rendicion.idUser,
#                         "nombre": rendicion.nombre,
#                         "tipo": rendicion.tipo,
#                         "estado": rendicion.estado,
#                         "fecha_registro": rendicion.fecha_registro,
#                         "fecha_actualizacion": rendicion.fecha_actualizacion,
#                     },
#                     "documentos": [
#                         {
#                             "id": doc.id,
#                             "fecha_solicitud": doc.fecha_solicitud,
#                             "fecha_rendicion": doc.fecha_rendicion,
#                             "dni": doc.dni,
#                             "usuario": doc.usuario,
#                             "gerencia": doc.gerencia,
#                             "ruc": doc.ruc,
#                             "proveedor": doc.proveedor,
#                             "fecha_emision": doc.fecha_emision,
#                             "moneda": doc.moneda,
#                             "tipo_documento": doc.tipo_documento,
#                             "serie": doc.serie,
#                             "correlativo": doc.correlativo,
#                             "tipo_gasto": doc.tipo_gasto,
#                             "sub_total": doc.sub_total,
#                             "igv": doc.igv,
#                             "no_gravadas": doc.no_gravadas,
#                             "importe_facturado": doc.importe_facturado,
#                             "tc": doc.tc,
#                             "anticipo": doc.anticipo,
#                             "total": doc.total,
#                             "pago": doc.pago,
#                             "detalle": doc.detalle,
#                             "estado": doc.estado,
#                             "empresa": doc.empresa,
#                             "archivo": doc.archivo,
#                             "tipo_solicitud": doc.tipo_solicitud,
#                             "tipo_cambio": doc.tipo_cambio,
#                             "afecto": doc.afecto,
#                             "inafecto": doc.inafecto,
#                             "rubro": doc.rubro,
#                             "cuenta_contable": doc.cuenta_contable,
#                             "responsable": doc.responsable,
#                             "area": doc.area,
#                             "ceco": doc.ceco,
#                             "tipo_anticipo": doc.tipo_anticipo,
#                             "motivo": doc.motivo,
#                             "fecha_viaje": doc.fecha_viaje,
#                             "dias": doc.dias,
#                             "presupuesto": doc.presupuesto,
#                             "banco": doc.banco,
#                             "numero_cuenta": doc.numero_cuenta,
#                             "origen": doc.origen,
#                             "destino": doc.destino,
#                             "numero_rendicion": doc.numero_rendicion,
#                             "tipo_viaje": doc.tipo_viaje,
#                         }
#                         for doc in documentos
#                     ]
#                 })

#         return resultado

#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Error al obtener rendiciones con documentos: {str(e)}")

# @app.get("/rendiciones-solicitudes/con-documentos/", response_model=List[dict])
# async def get_rendiciones_y_solicitudes_con_documentos(
#     tipo: Optional[str] = Query(None, description="Filtrar por tipo"),
#     estado: Optional[str] = Query(None, description="Filtrar por estado"),
#     fecha_registro_from: Optional[date] = Query(None, description="Filtrar desde esta fecha de registro"),
#     fecha_registro_to: Optional[date] = Query(None, description="Filtrar hasta esta fecha de registro"),
#     fecha_actualizacion_from: Optional[date] = Query(None, description="Filtrar desde esta fecha de actualización"),
#     fecha_actualizacion_to: Optional[date] = Query(None, description="Filtrar hasta esta fecha de actualización"),
#     id_user: Optional[int] = Query(None, description="Filtrar por ID de usuario"),
#     db: AsyncSession = Depends(get_db)
# ):
#     """
#     Devuelve una lista combinada de rendiciones y solicitudes con sus documentos asociados, aplicando filtros opcionales.
#     """
#     try:
#         # Consultas base para rendiciones y solicitudes
#         query_rendiciones = (
#             select(models.Rendicion)
#             .join(models.Documento, models.Documento.numero_rendicion == models.Rendicion.nombre)
#             .distinct()
#         )
#         query_solicitudes = (
#             select(models.Solicitud)
#             .join(models.Documento, models.Documento.numero_rendicion == models.Solicitud.nombre)
#             .distinct()
#         )

#         # Aplicar filtros a las consultas
#         if tipo:
#             query_rendiciones = query_rendiciones.where(models.Rendicion.tipo == tipo)
#             query_solicitudes = query_solicitudes.where(models.Solicitud.tipo == tipo)
#         if estado:
#             query_rendiciones = query_rendiciones.where(models.Rendicion.estado == estado)
#             query_solicitudes = query_solicitudes.where(models.Solicitud.estado == estado)
#         if fecha_registro_from:
#             query_rendiciones = query_rendiciones.where(models.Rendicion.fecha_registro >= fecha_registro_from)
#             query_solicitudes = query_solicitudes.where(models.Solicitud.fecha_registro >= fecha_registro_from)
#         if fecha_registro_to:
#             query_rendiciones = query_rendiciones.where(models.Rendicion.fecha_registro <= fecha_registro_to)
#             query_solicitudes = query_solicitudes.where(models.Solicitud.fecha_registro <= fecha_registro_to)
#         if fecha_actualizacion_from:
#             query_rendiciones = query_rendiciones.where(models.Rendicion.fecha_actualizacion >= fecha_actualizacion_from)
#             query_solicitudes = query_solicitudes.where(models.Solicitud.fecha_actualizacion >= fecha_actualizacion_from)
#         if fecha_actualizacion_to:
#             query_rendiciones = query_rendiciones.where(models.Rendicion.fecha_actualizacion <= fecha_actualizacion_to)
#             query_solicitudes = query_solicitudes.where(models.Solicitud.fecha_actualizacion <= fecha_actualizacion_to)
#         if id_user:
#             query_rendiciones = query_rendiciones.where(models.Rendicion.idUser == id_user)
#             query_solicitudes = query_solicitudes.where(models.Solicitud.idUser == id_user)

#         # Ejecutar las consultas
#         rendiciones_query = await db.execute(query_rendiciones)
#         solicitudes_query = await db.execute(query_solicitudes)

#         rendiciones = rendiciones_query.scalars().all()
#         solicitudes = solicitudes_query.scalars().all()

#         # Combinar resultados y transformar al formato esperado
#         resultado = []

#         # Procesar rendiciones
#         for rendicion in rendiciones:
#             documentos_query = await db.execute(
#                 select(models.Documento).where(models.Documento.numero_rendicion == rendicion.nombre)
#             )
#             documentos = documentos_query.scalars().all()

#             if documentos:
#                 resultado.append({
#                     "rendicion": {
#                         "id": rendicion.id,
#                         "idUser": rendicion.idUser,
#                         "nombre": rendicion.nombre,
#                         "tipo": rendicion.tipo,
#                         "estado": rendicion.estado,
#                         "fecha_registro": rendicion.fecha_registro,
#                         "fecha_actualizacion": rendicion.fecha_actualizacion,
#                     },
#                     "documentos": [
#                         {
#                             "id": doc.id,
#                             "fecha_solicitud": doc.fecha_solicitud,
#                             "fecha_rendicion": doc.fecha_rendicion,
#                             "dni": doc.dni,
#                             "usuario": doc.usuario,
#                             "gerencia": doc.gerencia,
#                             "ruc": doc.ruc,
#                             "proveedor": doc.proveedor,
#                             "fecha_emision": doc.fecha_emision,
#                             "moneda": doc.moneda,
#                             "tipo_documento": doc.tipo_documento,
#                             "serie": doc.serie,
#                             "correlativo": doc.correlativo,
#                             "tipo_gasto": doc.tipo_gasto,
#                             "sub_total": doc.sub_total,
#                             "igv": doc.igv,
#                             "no_gravadas": doc.no_gravadas,
#                             "importe_facturado": doc.importe_facturado,
#                             "tc": doc.tc,
#                             "anticipo": doc.anticipo,
#                             "total": doc.total,
#                             "pago": doc.pago,
#                             "detalle": doc.detalle,
#                             "estado": doc.estado,
#                             "empresa": doc.empresa,
#                             "archivo": doc.archivo,
#                             "tipo_solicitud": doc.tipo_solicitud,
#                             "tipo_cambio": doc.tipo_cambio,
#                             "afecto": doc.afecto,
#                             "inafecto": doc.inafecto,
#                             "rubro": doc.rubro,
#                             "cuenta_contable": doc.cuenta_contable,
#                             "responsable": doc.responsable,
#                             "area": doc.area,
#                             "ceco": doc.ceco,
#                             "tipo_anticipo": doc.tipo_anticipo,
#                             "motivo": doc.motivo,
#                             "fecha_viaje": doc.fecha_viaje,
#                             "dias": doc.dias,
#                             "presupuesto": doc.presupuesto,
#                             "banco": doc.banco,
#                             "numero_cuenta": doc.numero_cuenta,
#                             "origen": doc.origen,
#                             "destino": doc.destino,
#                             "numero_rendicion": doc.numero_rendicion,
#                             "tipo_viaje": doc.tipo_viaje,
#                         }
#                         for doc in documentos
#                     ]
#                 })

#         # Procesar solicitudes
#         for solicitud in solicitudes:
#             documentos_query = await db.execute(
#                 select(models.Documento).where(models.Documento.numero_rendicion == solicitud.nombre)
#             )
#             documentos = documentos_query.scalars().all()

#             if documentos:
#                 resultado.append({
#                     "rendicion": {
#                         "id": solicitud.id,
#                         "idUser": solicitud.idUser,
#                         "nombre": solicitud.nombre,
#                         "tipo": solicitud.tipo,
#                         "estado": solicitud.estado,
#                         "fecha_registro": solicitud.fecha_registro,
#                         "fecha_actualizacion": solicitud.fecha_actualizacion,
#                     },
#                     "documentos": [
#                         {
#                             "id": doc.id,
#                             "fecha_solicitud": doc.fecha_solicitud,
#                             "fecha_rendicion": doc.fecha_rendicion,
#                             "dni": doc.dni,
#                             "usuario": doc.usuario,
#                             "gerencia": doc.gerencia,
#                             "ruc": doc.ruc,
#                             "proveedor": doc.proveedor,
#                             "fecha_emision": doc.fecha_emision,
#                             "moneda": doc.moneda,
#                             "tipo_documento": doc.tipo_documento,
#                             "serie": doc.serie,
#                             "correlativo": doc.correlativo,
#                             "tipo_gasto": doc.tipo_gasto,
#                             "sub_total": doc.sub_total,
#                             "igv": doc.igv,
#                             "no_gravadas": doc.no_gravadas,
#                             "importe_facturado": doc.importe_facturado,
#                             "tc": doc.tc,
#                             "anticipo": doc.anticipo,
#                             "total": doc.total,
#                             "pago": doc.pago,
#                             "detalle": doc.detalle,
#                             "estado": doc.estado,
#                             "empresa": doc.empresa,
#                             "archivo": doc.archivo,
#                             "tipo_solicitud": doc.tipo_solicitud,
#                             "tipo_cambio": doc.tipo_cambio,
#                             "afecto": doc.afecto,
#                             "inafecto": doc.inafecto,
#                             "rubro": doc.rubro,
#                             "cuenta_contable": doc.cuenta_contable,
#                             "responsable": doc.responsable,
#                             "area": doc.area,
#                             "ceco": doc.ceco,
#                             "tipo_anticipo": doc.tipo_anticipo,
#                             "motivo": doc.motivo,
#                             "fecha_viaje": doc.fecha_viaje,
#                             "dias": doc.dias,
#                             "presupuesto": doc.presupuesto,
#                             "banco": doc.banco,
#                             "numero_cuenta": doc.numero_cuenta,
#                             "origen": doc.origen,
#                             "destino": doc.destino,
#                             "numero_rendicion": doc.numero_rendicion,
#                             "tipo_viaje": doc.tipo_viaje,
#                         }
#                         for doc in documentos
#                     ]
#                 })

#         return resultado

#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.get("/rendiciones-solicitudes/con-documentos/", response_model=List[dict])
async def get_rendiciones_y_solicitudes_con_documentos(
    tipo: Optional[str] = Query(None, description="Filtrar por tipo"),
    estado: Optional[str] = Query(None, description="Filtrar por estado"),
    fecha_registro_from: Optional[date] = Query(
        None, description="Filtrar desde esta fecha de registro"),
    fecha_registro_to: Optional[date] = Query(
        None, description="Filtrar hasta esta fecha de registro"),
    fecha_actualizacion_from: Optional[date] = Query(
        None, description="Filtrar desde esta fecha de actualización"),
    fecha_actualizacion_to: Optional[date] = Query(
        None, description="Filtrar hasta esta fecha de actualización"),
    id_user: Optional[int] = Query(
        None, description="Filtrar por ID de usuario"),
    db: AsyncSession = Depends(get_db)
):
    """
    Devuelve una lista combinada de rendiciones y solicitudes con sus documentos asociados, aplicando filtros opcionales.
    """
    try:
        # Consultas base para rendiciones y solicitudes
        query_rendiciones = (
            select(models.Rendicion, models.User.full_name)
            .join(models.User, models.Rendicion.id_user == models.User.id)
            .join(models.Documento, models.Documento.numero_rendicion == models.Rendicion.nombre)
            .where(models.Rendicion.estado != "NUEVO")
            .distinct()
        )
        query_solicitudes = (
            select(models.Solicitud, models.User.full_name)
            .join(models.User, models.Solicitud.id_user == models.User.id)
            .join(models.Documento, models.Documento.numero_rendicion == models.Solicitud.nombre)
            .where(models.Solicitud.estado != "NUEVO")
            .distinct()
        )

        # Aplicar filtros a las consultas
        if tipo:
            query_rendiciones = query_rendiciones.where(
                models.Rendicion.tipo == tipo)
            query_solicitudes = query_solicitudes.where(
                models.Solicitud.tipo == tipo)
        if estado:
            query_rendiciones = query_rendiciones.where(
                models.Rendicion.estado == estado)
            query_solicitudes = query_solicitudes.where(
                models.Solicitud.estado == estado)
        if fecha_registro_from:
            query_rendiciones = query_rendiciones.where(
                models.Rendicion.fecha_registro >= fecha_registro_from)
            query_solicitudes = query_solicitudes.where(
                models.Solicitud.fecha_registro >= fecha_registro_from)
        if fecha_registro_to:
            query_rendiciones = query_rendiciones.where(
                models.Rendicion.fecha_registro <= fecha_registro_to)
            query_solicitudes = query_solicitudes.where(
                models.Solicitud.fecha_registro <= fecha_registro_to)
        if fecha_actualizacion_from:
            query_rendiciones = query_rendiciones.where(
                models.Rendicion.fecha_actualizacion >= fecha_actualizacion_from)
            query_solicitudes = query_solicitudes.where(
                models.Solicitud.fecha_actualizacion >= fecha_actualizacion_from)
        if fecha_actualizacion_to:
            query_rendiciones = query_rendiciones.where(
                models.Rendicion.fecha_actualizacion <= fecha_actualizacion_to)
            query_solicitudes = query_solicitudes.where(
                models.Solicitud.fecha_actualizacion <= fecha_actualizacion_to)
        if id_user:
            query_rendiciones = query_rendiciones.where(
                models.Rendicion.id_user == id_user)
            query_solicitudes = query_solicitudes.where(
                models.Solicitud.id_user == id_user)

        # Ejecutar las consultas
        rendiciones_query = await db.execute(query_rendiciones)
        solicitudes_query = await db.execute(query_solicitudes)

        rendiciones = rendiciones_query.all()  # Incluye (Rendicion, full_name)
        solicitudes = solicitudes_query.all()  # Incluye (Solicitud, full_name)

        # Combinar resultados y transformar al formato esperado
        resultado = []

        # Procesar rendiciones
        for rendicion, full_name in rendiciones:
            documentos_query = await db.execute(
                select(models.Documento).where(
                    models.Documento.numero_rendicion == rendicion.nombre)
            )
            documentos = documentos_query.scalars().all()

            if documentos:
                resultado.append({
                    "rendicion": {
                        "id": rendicion.id,
                        "id_user": rendicion.id_user,
                        "nombre": rendicion.nombre,
                        "tipo": rendicion.tipo,
                        "estado": rendicion.estado,
                        "fecha_registro": rendicion.fecha_registro,
                        "fecha_actualizacion": rendicion.fecha_actualizacion,
                        "nombre_usuario": full_name,
                    },
                    "documentos": [
                        {
                            "id": doc.id,
                            "fecha_solicitud": doc.fecha_solicitud,
                            "fecha_rendicion": doc.fecha_rendicion,
                            "dni": doc.dni,
                            "usuario": doc.usuario,
                            "gerencia": doc.gerencia,
                            "ruc": doc.ruc,
                            "proveedor": doc.proveedor,
                            "fecha_emision": doc.fecha_emision,
                            "moneda": doc.moneda,
                            "tipo_documento": doc.tipo_documento,
                            "serie": doc.serie,
                            "correlativo": doc.correlativo,
                            "tipo_gasto": doc.tipo_gasto,
                            "sub_total": doc.sub_total,
                            "igv": doc.igv,
                            "no_gravadas": doc.no_gravadas,
                            "importe_facturado": doc.importe_facturado,
                            "tc": doc.tc,
                            "anticipo": doc.anticipo,
                            "total": doc.total,
                            "pago": doc.pago,
                            "detalle": doc.detalle,
                            "estado": doc.estado,
                            "empresa": doc.empresa,
                            "archivo": doc.archivo,
                            "tipo_solicitud": doc.tipo_solicitud,
                            "tipo_cambio": doc.tipo_cambio,
                            "afecto": doc.afecto,
                            "inafecto": doc.inafecto,
                            "rubro": doc.rubro,
                            "cuenta_contable": doc.cuenta_contable,
                            "responsable": doc.responsable,
                            "area": doc.area,
                            "ceco": doc.ceco,
                            "tipo_anticipo": doc.tipo_anticipo,
                            "motivo": doc.motivo,
                            "fecha_viaje": doc.fecha_viaje,
                            "dias": doc.dias,
                            "presupuesto": doc.presupuesto,
                            "banco": doc.banco,
                            "numero_cuenta": doc.numero_cuenta,
                            "origen": doc.origen,
                            "destino": doc.destino,
                            "numero_rendicion": doc.numero_rendicion,
                            "tipo_viaje": doc.tipo_viaje,
                        }
                        for doc in documentos
                    ]
                })

        # Procesar solicitudes
        for solicitud, full_name in solicitudes:
            documentos_query = await db.execute(
                select(models.Documento).where(
                    models.Documento.numero_rendicion == solicitud.nombre)
            )
            documentos = documentos_query.scalars().all()

            if documentos:
                resultado.append({
                    "rendicion": {
                        "id": solicitud.id,
                        "id_user": solicitud.id_user,
                        "nombre": solicitud.nombre,
                        "tipo": solicitud.tipo,
                        "estado": solicitud.estado,
                        "fecha_registro": solicitud.fecha_registro,
                        "fecha_actualizacion": solicitud.fecha_actualizacion,
                        "nombre_usuario": full_name,
                    },
                    "documentos": [
                        {
                            "id": doc.id,
                            **{key: getattr(doc, key) for key in models.Documento.__table__.columns.keys()}
                        }
                        for doc in documentos
                    ]
                })

        return resultado

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


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
