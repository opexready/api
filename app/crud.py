# app/crud.py

from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from . import models, schemas

# CRUD for User (existing code)
async def get_user_by_email(db: AsyncSession, email: str):
    result = await db.execute(select(models.User).filter(models.User.email == email))
    return result.scalars().first()

async def create_user(db: AsyncSession, user: schemas.UserCreate):
    db_user = models.User(
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        hashed_password=user.hashed_password,
        role=user.role,
        company_name=user.company_name,
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user

# CRUD for Documento
async def get_documento(db: AsyncSession, documento_id: int):
    result = await db.execute(select(models.Documento).filter(models.Documento.id == documento_id))
    return result.scalars().first()

async def get_documentos_by_empresa(db: AsyncSession, empresa: str):
    result = await db.execute(select(models.Documento).filter(models.Documento.empresa == empresa))
    return result.scalars().all()

async def create_documento(db: AsyncSession, documento: schemas.DocumentoCreate):
    db_documento = models.Documento(**documento.dict())
    db.add(db_documento)
    await db.commit()
    await db.refresh(db_documento)
    return db_documento

async def update_documento(db: AsyncSession, documento_id: int, documento: schemas.DocumentoCreate):
    db_documento = await get_documento(db, documento_id)
    for key, value in documento.dict().items():
        setattr(db_documento, key, value)
    await db.commit()
    await db.refresh(db_documento)
    return db_documento

async def delete_documento(db: AsyncSession, documento_id: int):
    db_documento = await get_documento(db, documento_id)
    await db.delete(db_documento)
    await db.commit()
    return db_documento
