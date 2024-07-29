# app/main.py

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from datetime import timedelta
import shutil
import os
import pandas as pd
from fpdf import FPDF
from . import crud, models, schemas, auth
from .database import engine, SessionLocal

app = FastAPI()

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

# Ejecutar la creación de tablas asíncronamente
@app.on_event("startup")
async def on_startup():
    await init_models()

async def get_db():
    async with SessionLocal() as session:
        yield session

@app.post("/users/", response_model=schemas.User)
async def create_user(user: schemas.UserCreate, db: AsyncSession = Depends(get_db)):
    db_user = await crud.get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    return await crud.create_user(db=db, user=user)

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
async def read_documentos(empresa: str, db: AsyncSession = Depends(get_db)):
    documentos = await crud.get_documentos_by_empresa(db, empresa=empresa)
    return documentos

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

# API para subir archivos
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

# API para descargar un documento en Excel por ID
@app.get("/documentos/{documento_id}/export/excel")
async def export_documento_to_excel(documento_id: int, db: AsyncSession = Depends(get_db)):
    documento = await crud.get_documento(db, documento_id=documento_id)
    if not documento:
        raise HTTPException(status_code=404, detail="Documento not found")
    
    df = pd.DataFrame([documento.__dict__])
    excel_file = f"C:/archivos/documento_{documento_id}.xlsx"
    df.to_excel(excel_file, index=False)
    return {"file_location": excel_file}

# API para descargar un documento en PDF por ID
@app.get("/documentos/{documento_id}/export/pdf")
async def export_documento_to_pdf(documento_id: int, db: AsyncSession = Depends(get_db)):
    documento = await crud.get_documento(db, documento_id=documento_id)
    if not documento:
        raise HTTPException(status_code=404, detail="Documento not found")
    
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    
    for key, value in documento.__dict__.items():
        pdf.cell(200, 10, txt=f"{key}: {value}", ln=True)
    
    pdf_file = f"C:/archivos/documento_{documento_id}.pdf"
    pdf.output(pdf_file)
    return {"file_location": pdf_file}

# API para eliminar un archivo asociado a un documento
@app.delete("/documentos/{documento_id}/file", response_model=schemas.Documento)
async def delete_documento_file(documento_id: int, db: AsyncSession = Depends(get_db)):
    documento = await crud.get_documento(db, documento_id=documento_id)
    if os.path.exists(documento.archivo):
        os.remove(documento.archivo)
    documento.archivo = None
    await db.commit()
    await db.refresh(documento)
    return documento
