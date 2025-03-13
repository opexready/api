from datetime import date
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, desc
from . import models, schemas
from . import auth
from datetime import datetime

# CRUD for User


async def get_user_by_email(db: AsyncSession, email: str):
    result = await db.execute(select(models.User).filter(models.User.email == email))
    return result.scalars().first()


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
        banco=user.banco,  # Banco asociado a la cuenta bancaria
        id_empresa=user.id_empresa,
        estado=user.estado,
        id_user = user.id_user
    )

    # Guardar el nuevo usuario en la base de datos
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user


async def get_users(db: AsyncSession):
    result = await db.execute(select(models.User))
    return result.scalars().all()

async def get_users_by_id_user(db: AsyncSession, id_user: int):
    result = await db.execute(select(models.User).where(models.User.id_user == id_user)) #Asumiendo que tienes un campo id en tu modelo User.
    users = result.scalars().all()
    return users


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
            func.count(models.Documento.usuario).label(
                'cantidad_documentos_pendientes')
        )
        .join(models.Documento, models.User.email == models.Documento.usuario)
        .where(
            models.Documento.estado == 'POR APROBAR',
            models.User.company_name == models.Documento.empresa,
            models.Documento.empresa == empresa
        )
        .group_by(models.User.username, models.User.full_name, models.User.email, models.User.company_name)
    )
    return result.all()

async def update_user(db: AsyncSession, user_id: int, user: schemas.UserUpdate):
    # Obtener el usuario de la base de datos
    db_user = await db.execute(select(models.User).filter(models.User.id == user_id))
    db_user = db_user.scalars().first()

    if not db_user:
        return None  # Si el usuario no existe, retornar None

    # Actualizar los campos proporcionados
    for key, value in user.dict().items():
        if value is not None:  # Solo actualizar si el valor no es None
            setattr(db_user, key, value)

    # Guardar los cambios en la base de datos
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


async def create_rendicion(db: AsyncSession, rendicion: schemas.RendicionCreate):
    db_rendicion = models.Rendicion(
        id_user=rendicion.id_user, nombre=rendicion.nombre)
    db.add(db_rendicion)
    await db.commit()
    await db.refresh(db_rendicion)
    return db_rendicion


async def get_rendiciones(db: AsyncSession):
    result = await db.execute(select(models.Rendicion))
    return result.scalars().all()


# Método para crear una rendición con incremento en el nombre

async def create_rendicion_with_increment(db: AsyncSession, id_user: int) -> models.Rendicion:
    # Buscar el último registro de rendición del usuario
    result = await db.execute(
        select(models.Rendicion)
        .filter(models.Rendicion.id_user == id_user, models.Rendicion.nombre.like("R%"))
        .order_by(desc(models.Rendicion.id))
    )

    last_rendicion = result.scalars().first()

    # Si no existe ningún registro previo, el primer valor será R00001
    if not last_rendicion:
        new_nombre = "R00001"
    else:
        # Extraer el número del último 'nombre' y sumarle 1
        last_number = int(last_rendicion.nombre[1:])  # Ignorar la letra 'R'
        new_number = last_number + 1
        # Formatear con 5 dígitos, ejemplo: R00002
        new_nombre = f"R{new_number:05d}"

    # Crear una nueva rendición
    new_rendicion = models.Rendicion(
        id_user=id_user,
        nombre=new_nombre,
        estado="NUEVO",
        tipo="RENDICION",
        fecha_registro=date.today()  # Inserta la fecha actual
    )

    # Guardar en la base de datos
    db.add(new_rendicion)
    await db.commit()
    await db.refresh(new_rendicion)

    return new_rendicion


# Método para crear una rendición con incremento en el nombre
async def create_solicitud_with_increment(db: AsyncSession, id_user: int) -> models.Solicitud:
    # Buscar el último registro de rendición del usuario
    result = await db.execute(
        select(models.Solicitud)
        .filter(models.Solicitud.id_user == id_user, models.Solicitud.nombre.like("S%"))
        .order_by(desc(models.Solicitud.id))
    )

    last_solicitud = result.scalars().first()

    # Si no existe ningún registro previo, el primer valor será R00001
    if not last_solicitud:
        new_nombre = "S00001"
    else:
        # Extraer el número del último 'nombre' y sumarle 1
        last_number = int(last_solicitud.nombre[1:])  # Ignorar la letra 'R'
        new_number = last_number + 1
        # Formatear con 5 dígitos, ejemplo: R00002
        new_nombre = f"S{new_number:05d}"

    # Crear una nueva rendición
    fecha_actual = datetime.now().date()
    new_solicitud = models.Solicitud(
        id_user=id_user,
        nombre=new_nombre,
        fecha_registro=fecha_actual,
        estado="NUEVO",
        tipo="ANTICIPO"
    )

    # Guardar en la base de datos
    db.add(new_solicitud)
    await db.commit()
    await db.refresh(new_solicitud)

    return new_solicitud


async def create_rendicion(db: AsyncSession, id_user: int) -> models.Rendicion:
    new_rendicion = models.Rendicion(
        id_user=id_user,
        nombre="R00001",
        estado="NUEVO",
        tipo="RENDICION",
        fecha_registro=date.today()
    )
    db.add(new_rendicion)
    await db.commit()
    await db.refresh(new_rendicion)
    return new_rendicion


async def create_solicitud(db: AsyncSession, id_user: int) -> models.Solicitud:
    fecha_actual = datetime.now().date()
    new_solicitud = models.Solicitud(
        id_user=id_user,
        nombre="S00001",
        estado="NUEVO",
        tipo="ANTICIPO",
        fecha_registro=fecha_actual
    )

    db.add(new_solicitud)
    await db.commit()
    await db.refresh(new_solicitud)
    return new_solicitud

