FROM python:3.10-slim

WORKDIR /app

# Dependencias del sistema
RUN apt-get update && apt-get install -y \
    libzbar0 tesseract-ocr libtesseract-dev wkhtmltopdf python3-dev build-essential \
  && rm -rf /var/lib/apt/lists/*

# Instala dependencias de Python
COPY requirements.txt .
RUN pip install --upgrade pip wheel setuptools \
  && pip install --no-cache-dir -r requirements.txt

# Copia TODO el proyecto (incluye config/)
COPY . .

# Define la variable de entorno para Firebase
ENV GOOGLE_APPLICATION_CREDENTIALS=/app/config/arendir-909a2-firebase-adminsdk-fbsvc-80cd4666e0.json

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
