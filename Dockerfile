FROM python:3.10-slim

# === Install dependencies for OCR ===
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    ghostscript \
    unpaper \
    libjpeg-dev \
    zlib1g-dev \
    libpng-dev \
    libtiff-dev \
    libopenjp2-7-dev \
    poppler-utils \
    curl \
    && rm -rf /var/lib/apt/lists/*

# === Crée un dossier de travail ===
WORKDIR /app

# === Copier les fichiers de l'app ===
COPY . /app

# === Installer les dépendances Python ===
RUN pip install --no-cache-dir -r requirements.txt

# === Port d’écoute Railway (PORT fourni en env) ===
EXPOSE 8080

# === Commande pour lancer Flask (tu peux adapter) ===
CMD ["python", "app.py"]
