FROM python:3.10

# Installer Tesseract + OCRmyPDF deps + outils d’optimisation
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-fra \
    ghostscript \
    unpaper \
    libjpeg-dev \
    zlib1g-dev \
    libpng-dev \
    libtiff-dev \
    libopenjp2-7-dev \
    poppler-utils \
    curl \
    pngquant \
    libjbig2dec0 \
    && rm -rf /var/lib/apt/lists/*

# Afficher les langues tesseract installées (debug)
RUN tesseract --list-langs

# === Dossier de travail
WORKDIR /app
COPY . /app

# === Dépendances Python
RUN pip install --no-cache-dir -r requirements.txt

# === Permettre les gros fichiers sans crash de Gunicorn
ENV GUNICORN_CMD_ARGS="--workers=2 --threads=4 --timeout=300 --bind=0.0.0.0:8080 --no-sendfile"

# === Exposition du port
EXPOSE 8080

# === Lancer l'app
CMD ["gunicorn", "app:app", "--workers=1", "--threads=1", "--timeout=180", "--bind=0.0.0.0:8080"]
