FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias del sistema requeridas para visión, pdf y compilación
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libgl1 \
    libglib2.0-0 \
    tesseract-ocr \
    tesseract-ocr-spa \
    poppler-utils \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copiar configuración y código para instalación de paquete
COPY pyproject.toml /app/pyproject.toml
COPY backend/app /app/app

# Instalar dependencias Python
RUN pip install --no-cache-dir pip setuptools wheel && \
    pip install --no-cache-dir .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
