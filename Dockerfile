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

WORKDIR /app
COPY . /app

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8080

CMD ["gunicorn", "app:app", "--workers=1", "--threads=2", "--timeout=90", "--bind=0.0.0.0:8080"]
