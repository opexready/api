from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func
from . import models, schemas
from . import auth

# CRUD for User
async def get_user_by_email(db: AsyncSession, email: str):
    result = await db.execute(select(models.User).filter(models.User.email == email))
    return result.scalars().first()

# async def create_user(db: AsyncSession, user: schemas.UserCreate):
#     hashed_password = auth.get_password_hash(user.password)
#     db_user = models.User(
#         email=user.email,
#         username=user.username,
#         full_name=user.full_name,
#         hashed_password=hashed_password,
#         role=user.role,
#         company_name=user.company_name,
#         cargo=user.cargo,  # Agregando campo cargo
#         dni=user.dni,
#         zona_venta=user.zona_venta  # Agregando campo dni
        
#     )
#     db.add(db_user)
#     await db.commit()
#     await db.refresh(db_user)
#     return db_user

async def create_user(db: AsyncSession, user: schemas.UserCreate):
    # Hash de la contraseña
    hashed_password = auth.get_password_hash(user.password)
    
    # Crear el objeto del nuevo usuario con todos los campos
    db_user = models.User(
        email=user.email,  # Email (único)
        username=user.username,  # Nombre de usuario (único)
        full_name=user.full_name,  # Nombre completo
        hashed_password=hashed_password,  # Contraseña hasheada
        role=user.role,  # Rol del usuario
        company_name=user.company_name,  # Nombre de la empresa
        cargo=user.cargo,  # Cargo del usuario
        dni=user.dni,  # DNI del usuario
        zona_venta=user.zona_venta,  # Zona de ventas
        area=user.area,  # Área del usuario
        ceco=user.ceco,  # Centro de costos (CeCo)
        gerencia=user.gerencia,  # Gerencia del usuario
        jefe_id=user.jefe_id,  # Relación con el jefe (ForeignKey)
        cuenta_bancaria=user.cuenta_bancaria,  # Cuenta bancaria
        banco=user.banco  # Banco asociado a la cuenta bancaria
    )
    
    # Guardar el nuevo usuario en la base de datos
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user

async def get_users(db: AsyncSession):
    result = await db.execute(select(models.User))
    return result.scalars().all()

# CRUD for User
async def get_users_by_company_and_role(db: AsyncSession, company_name: str, role: str):
    result = await db.execute(select(models.User).filter(models.User.company_name == company_name, models.User.role == role))
    return result.scalars().all()

async def get_user_by_email(db: AsyncSession, email: str):
    result = await db.execute(select(models.User).filter(models.User.email == email))
    return result.scalars().first()



# Nueva función para obtener usuarios con documentos pendientes
async def get_users_with_pending_documents(db: AsyncSession, empresa: str):
    result = await db.execute(
        select(
            models.User.username,
            models.User.full_name,
            models.User.email,
            models.User.company_name,
            func.count(models.Documento.usuario).label('cantidad_documentos_pendientes')
        )
        .join(models.Documento, models.User.email == models.Documento.usuario)
        .where(
            models.Documento.estado == 'PENDIENTE',
            models.User.company_name == models.Documento.empresa,
            models.Documento.empresa == empresa
        )
        .group_by(models.User.username, models.User.full_name, models.User.email, models.User.company_name)
    )
    return result.all()

# CRUD for Documento
async def get_documento(db: AsyncSession, documento_id: int):
    result = await db.execute(select(models.Documento).filter(models.Documento.id == documento_id))
    return result.scalars().first()

async def get_documentos_by_empresa(db: AsyncSession, empresa: str):
    result = await db.execute(select(models.Documento).filter(models.Documento.empresa == empresa))
    return result.scalars().all()

async def get_documentos_by_empresa_estado(db: AsyncSession, empresa: str, estado: str):
    result = await db.execute(select(models.Documento).filter(models.Documento.empresa == empresa, models.Documento.estado == estado))
    return result.scalars().all()

async def get_documentos_by_username_estado(db: AsyncSession, username: str, estado: str):
    result = await db.execute(select(models.Documento).filter(models.Documento.usuario == username, models.Documento.estado == estado))
    return result.scalars().all()

async def create_documento(db: AsyncSession, documento: schemas.DocumentoCreate):
    db_documento = models.Documento(**documento.dict())
    db.add(db_documento)
    await db.commit()
    await db.refresh(db_documento)
    return db_documento

async def update_documento(db: AsyncSession, documento_id: int, documento: schemas.DocumentoUpdate):
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

async def update_documento_file(db: AsyncSession, documento_id: int, file_location: str):
    db_documento = await get_documento(db, documento_id)
    db_documento.archivo = file_location
    await db.commit()
    await db.refresh(db_documento)
    return db_documento

# CRUD for Company
async def get_companies(db: AsyncSession):
    result = await db.execute(select(models.Company))
    return result.scalars().all()

async def create_company(db: AsyncSession, company: schemas.CompanyCreate):
    db_company = models.Company(**company.dict())
    db.add(db_company)
    await db.commit()
    await db.refresh(db_company)
    return db_company

async def update_company(db: AsyncSession, company_id: int, company: schemas.CompanyCreate):
    db_company = await get_company_by_id(db, company_id)
    if not db_company:
        return None
    for key, value in company.dict().items():
        setattr(db_company, key, value)
    await db.commit()
    await db.refresh(db_company)
    return db_company

async def delete_company(db: AsyncSession, company_id: int):
    db_company = await get_company_by_id(db, company_id)
    if not db_company:
        return None
    await db.delete(db_company)
    await db.commit()
    return db_company

async def get_company_by_id(db: AsyncSession, company_id: int):
    result = await db.execute(select(models.Company).filter(models.Company.id == company_id))
    return result.scalars().first()
