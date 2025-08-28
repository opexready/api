FROM python:3.10-slim
WORKDIR /app

# Sistema y pip - Sin wkhtmltopdf
RUN apt-get update && apt-get install -y \
    libzbar0 tesseract-ocr libtesseract-dev python3-dev build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip wheel setuptools \
  && pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]