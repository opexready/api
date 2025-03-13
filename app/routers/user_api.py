from typing import List
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app import auth, crud, schemas
from app.database import get_db
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

router = APIRouter()

# Configuración del correo electrónico
sender_email = "ychacon.opexready@gmail.com"  # Tu correo electrónico
sender_password = "ryqoyaslkxzmxysj"  # Tu contraseña de correo electrónico

def send_welcome_email(user: schemas.User):
    """Envía un correo electrónico de bienvenida al usuario."""

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = user.email
    msg['Subject'] = "Bienvenido a Arendir"

    body = f"""
    Hola {user.username},

    ¡Bienvenido a Arendir!

    Gracias por registrarte. 
    Para poder continuar ingrese a https://arendir.onrender.com/

    Atentamente,
    El equipo de Arendir
    """
    msg.attach(MIMEText(body, 'plain'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        text = msg.as_string()
        server.sendmail(sender_email, user.email, text)
        server.quit()
        print(f"Correo electrónico enviado a {user.email}")
    except Exception as e:
        print(f"Error al enviar el correo electrónico: {e}")


@router.post("/users/", response_model=schemas.User)
async def create_user(user: schemas.UserCreate, db: AsyncSession = Depends(get_db)):
    """Crea un nuevo usuario."""

    db_user = await crud.get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    if not hasattr(user, "id_empresa") or user.id_empresa is None:
        user.id_empresa = 1
    if not hasattr(user, "estado") or user.estado is None:
        user.estado = True
    
    created_user = await crud.create_user(db=db, user=user)  # Guarda el usuario creado

    # Envía el correo electrónico de bienvenida
    send_welcome_email(created_user)  # Llama a la función para enviar el correo

    return created_user


@router.get("/users/me/", response_model=schemas.User)
async def read_users_me(current_user: schemas.User = Depends(auth.get_current_user)):
    return current_user

@router.get("/users/", response_model=List[schemas.User])
async def read_users(db: AsyncSession = Depends(get_db)):
    return await crud.get_users(db)

@router.get("/users/by-company-and-role/", response_model=List[schemas.User])
async def read_users_by_company_and_role(company_name: str = Query(...), role: str = Query(...), db: AsyncSession = Depends(get_db)):
    users = await crud.get_users_by_company_and_role(db, company_name, role)
    if not users:
        raise HTTPException(
            status_code=404, detail="No users found for the specified company_name and role")
    return users

@router.get("/users/by-id-user/", response_model=List[schemas.User])
async def read_users_by_id_user(id_user: int = Query(...), db: AsyncSession = Depends(get_db)):
    users = await crud.get_users_by_id_user(db, id_user)
    if not users:
        raise HTTPException(
            status_code=404, detail=f"No users found with id_user: {id_user}")
    return users

@router.get("/users/with-pending-documents/", response_model=List[schemas.UserWithPendingDocuments])
async def read_users_with_pending_documents(empresa: str = Query(...), db: AsyncSession = Depends(get_db)):
    return await crud.get_users_with_pending_documents(db, empresa)

@router.get("/users/by-email/", response_model=schemas.User)
async def read_user_by_email(email: str = Query(...), db: AsyncSession = Depends(get_db)):
    user = await crud.get_user_by_email(db, email=email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.put("/users/{user_id}", response_model=schemas.User)
async def update_user(
    user_id: int,
    user: schemas.UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: schemas.User = Depends(auth.get_current_user)
):
    # Verificar si el usuario actual tiene permisos para actualizar
    if current_user.id != user_id and current_user.role != "ADMIN":
        raise HTTPException(
            status_code=403,
            detail="No tienes permisos para actualizar este usuario"
        )

    # Actualizar el usuario
    updated_user = await crud.update_user(db, user_id, user)
    if not updated_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    return updated_user