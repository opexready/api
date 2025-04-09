# Usa una imagen base oficial de Python con la versión necesaria
FROM python:3.10-slim

# Establecer el directorio de trabajo
WORKDIR /app

# Instalar dependencias del sistema primero (para optimizar las capas de Docker)
RUN apt-get update && apt-get install -y \
    libzbar0 \
    tesseract-ocr \
    libtesseract-dev \
    wkhtmltopdf \
    python3-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copiar los archivos de requerimientos para instalar las dependencias
COPY requirements.txt .

# Instalar dependencias de Python optimizado
RUN pip install --upgrade pip wheel setuptools && \
    pip install --no-cache-dir -r requirements.txt

# Copiar el resto de la aplicación (esto va después para aprovechar el cache de Docker)
COPY . .

# Exponer el puerto en el que correrá FastAPI (por defecto 8000)
EXPOSE 8000

# Comando para iniciar la aplicación FastAPI usando uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]