# Usa una imagen base oficial de Python con la versión necesaria
FROM python:3.10-slim

# Establecer el directorio de trabajo
WORKDIR /app

# Copiar los archivos de requerimientos para instalar las dependencias
COPY requirements.txt .

# Actualizar pip a la última versión
RUN pip install --upgrade pip

# Instalar las dependencias de Python (usando psycopg2-binary para evitar problemas con pg_config)
RUN pip install --no-cache-dir -r requirements.txt

# Instalar las librerías del sistema necesarias para pyzbar (zbar)
RUN apt-get update && apt-get install -y libzbar0

# Copiar todo el contenido de la carpeta actual al contenedor
COPY . .

# Exponer el puerto en el que correrá FastAPI (por defecto 8000)
EXPOSE 8000

# Comando para iniciar la aplicación FastAPI usando uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
