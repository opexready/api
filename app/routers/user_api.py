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

# Configuración del correo electrónico
sender_email = "ychacon.opexready@gmail.com"  # Tu correo electrónico
sender_password = "ryqoyaslkxzmxysj"  # Tu contraseña de correo electrónico

# def send_welcome_email(user: schemas.User):
#     """Envía un correo electrónico de bienvenida al usuario."""

#     msg = MIMEMultipart()
#     msg['From'] = sender_email
#     msg['To'] = user.email
#     msg['Subject'] = "Bienvenido a Arendir"

#     body = f"""
#     Hola {user.username},

#     ¡Esperamos que te encuentres muy bien! Nos emociona presentarte Arendir, una herramienta revolucionaria diseñada para facilitar la gestión por rendición de gastos de tu empresa y optimizar el trabajo en equipo.

#     Con Arendir, puedes olvidarte del tedioso proceso de registrar y controlar los gastos manualmente.

#     Para que puedas aprovechar al máximo Arendir, aquí tienes tres simples pasos que te serán muy útiles.

#     Su contraseña temporal es: Xrosdh223i, ¡No olvide cambiarla!

#    **1. Ingresar desde cualquier dispositivo:**
#        ¡Accede a Arendir desde tu computadora o dispositivo móvil, ya sea con iOS o Android!

#     **2. Trabajo en Conjunto:**
#        ¡El máximo potencial de Arendir se alcanza cuando todos colaboran! Invitar a tu equipo es muy fácil.

#     **3. ¿Dudas?**
#        [Reserva un espacio en mi calendario] o [envíame un Whatsapp](https://wa.me/51946643795) si prefieres una respuesta rápida.
#     ¡Mucho éxito!

#     Atentamente,
#     El equipo de Arendir
#     """
#     msg.attach(MIMEText(body, 'plain'))

#     try:
#         server = smtplib.SMTP('smtp.gmail.com', 587)
#         server.starttls()
#         server.login(sender_email, sender_password)
#         text = msg.as_string()
#         server.sendmail(sender_email, user.email, text)
#         server.quit()
#         print(f"Correo electrónico enviado a {user.email}")
#     except Exception as e:
#         print(f"Error al enviar el correo electrónico: {e}")

def get_email_template(template_name: str, context: dict) -> str:
    """Carga un template de email y reemplaza las variables del contexto."""
    templates_dir = Path(__file__).parent.parent / "templates" / "email"
    template_path = templates_dir / f"{template_name}.html"
    
    with open(template_path, "r", encoding="utf-8") as file:
        html_content = file.read()
    
    # Reemplazar variables en el template
    for key, value in context.items():
        html_content = html_content.replace(f"{{{key}}}", str(value))
    
    return html_content

def send_welcome_email(user: schemas.User):
    """Envía un correo electrónico de bienvenida al usuario."""
    msg = MIMEMultipart('related')
    msg['From'] = sender_email
    msg['To'] = user.email
    msg['Subject'] = "Bienvenido a Arendir"

    # Contexto para el template
    context = {
        "username": user.username,
        "temp_password": "Xrosdh223i"  # Esto debería venir del usuario o generarse
    }

    # Obtener el template HTML
    html_content = get_email_template("welcome_email", context)
    
    # Adjuntar HTML
    msg.attach(MIMEText(html_content, 'html'))

    # Adjuntar imágenes (opcional)
    # logo_path = Path(__file__).parent.parent / "static" / "images" / "logo.png"
    # with open(logo_path, 'rb') as img:
    #     logo = MIMEImage(img.read())
    #     logo.add_header('Content-ID', '<logo>')
    #     msg.attach(logo)

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