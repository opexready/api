from pathlib import Path
from typing import List
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app import auth, crud, schemas
from app.database import get_db
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

router = APIRouter()

sender_email = "ychacon.opexready@gmail.com"  # Tu correo electrónico
sender_password = "ryqoyaslkxzmxysj"  # Tu contraseña de correo electrónico

def get_email_template(template_name: str, context: dict) -> str:
    """Carga un template de email y reemplaza las variables del contexto."""
    templates_dir = Path(__file__).parent.parent / "templates" / "email"
    template_path = templates_dir / f"{template_name}.html"
    
    with open(template_path, "r", encoding="utf-8") as file:
        html_content = file.read()
    
    for key, value in context.items():
        html_content = html_content.replace(f"{{{key}}}", str(value))
    
    return html_content

def send_welcome_email(user: schemas.User):
    """Envía un correo electrónico de bienvenida al usuario."""
    msg = MIMEMultipart('related')
    msg['From'] = sender_email
    msg['To'] = user.email
    msg['Subject'] = "Bienvenido a Arendir"

    context = {
        "username": user.full_name,
        "temp_password": "Xrosdh223i"  
    }
    html_content = get_email_template("welcome_email", context)
    msg.attach(MIMEText(html_content, 'html'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, user.email, msg.as_string())
        server.quit()
        print(f"Correo electrónico enviado a {user.email}")
    except Exception as e:
        print(f"Error al enviar el correo electrónico: {e}")


@router.post("/users/", response_model=schemas.User)
async def create_user(user: schemas.UserCreate, db: AsyncSession = Depends(get_db)):
    """Crea un nuevo usuario."""
    
    # Primero validamos que el username no exista
    db_user_by_username = await crud.get_user_by_username(db, username=user.username)
    if db_user_by_username:
        raise HTTPException(
            status_code=400, 
            detail="Username already registered"
        )
    

    # Valores por defecto
    if not hasattr(user, "id_empresa") or user.id_empresa is None:
        user.id_empresa = 1
    if not hasattr(user, "estado") or user.estado is None:
        user.estado = True
    
    # Crear el usuario
    created_user = await crud.create_user(db=db, user=user)

    # Enviar correo de bienvenida
    send_welcome_email(created_user)

    return created_user


@router.get("/users/me/", response_model=schemas.User)
async def read_users_me(current_user: schemas.User = Depends(auth.get_current_user)):
    return current_user

@router.get("/users/", response_model=List[schemas.User])
async def read_users(db: AsyncSession = Depends(get_db)):
    return await crud.get_users(db)

@router.get("/users/by-company-and-role/", response_model=List[schemas.User])
async def read_users_by_company_and_role(id_empresa: int = Query(...), role: str = Query(...), db: AsyncSession = Depends(get_db)):
    users = await crud.get_users_by_company_and_role(db, id_empresa, role)
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
    # Verificar permisos
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

# Añadir estos esquemas al inicio del archivo


# Añadir estas rutas al router
@router.post("/users/request-password-reset/")
async def request_password_reset(
    request: schemas.RequestPasswordReset,
    db: AsyncSession = Depends(get_db)
):
    """Solicita un restablecimiento de contraseña enviando un correo con token"""
    user = await crud.get_user_by_email(db, email=request.email)
    if not user:
        # No revelamos que el email no existe por seguridad
        return {"message": "Si el email existe, se ha enviado un correo con instrucciones"}

    # Generar token de restablecimiento
    reset_token = auth.create_reset_token(data={"sub": user.email})
    
    # Enviar correo con el token
    send_reset_email(user, reset_token)
    
    return {"message": "Si el email existe, se ha enviado un correo con instrucciones"}

@router.post("/users/reset-password/")
async def reset_password(
    reset_data: schemas.ResetPasswordRequest,
    db: AsyncSession = Depends(get_db)
):
    """Restablece la contraseña usando un token válido"""
    email = auth.verify_reset_token(reset_data.token)
    if not email:
        raise HTTPException(
            status_code=400,
            detail="Token inválido o expirado"
        )
        
    user = await crud.get_user_by_email(db, email=email)
    if not user:
        raise HTTPException(
            status_code=404,
            detail="Usuario no encontrado"
        )
        
    # Actualizar la contraseña
    hashed_password = auth.get_password_hash(reset_data.new_password)
    user.hashed_password = hashed_password
    db.add(user)
    await db.commit()
    
    return {"message": "Contraseña actualizada correctamente"}

# Añadir esta función auxiliar para enviar emails de restablecimiento
def send_reset_email(user: schemas.User, reset_token: str):
    """Envía un correo electrónico con el enlace para restablecer la contraseña"""
    msg = MIMEMultipart('related')
    msg['From'] = sender_email
    msg['To'] = user.email
    msg['Subject'] = "Restablecer tu contraseña en Arendir"

    reset_link = f"https://www.arendirperu.pe/#/login?token={reset_token}"
    
    context = {
        "username": user.full_name,
        "reset_link": reset_link
    }
    
    html_content = get_email_template("reset_password", context)
    msg.attach(MIMEText(html_content, 'html'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, user.email, msg.as_string())
        server.quit()
        print(f"Correo de restablecimiento enviado a {user.email}")
    except Exception as e:
        print(f"Error al enviar el correo de restablecimiento: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error al enviar el correo de restablecimiento"
        )