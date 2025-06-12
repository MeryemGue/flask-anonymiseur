FROM python:3.10

# Installer les dépendances système
RUN apt-get update && apt-get install -y \
    libreoffice \
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

# Installer les dépendances Python (ajoute gevent ici)
RUN pip install --no-cache-dir -r requirements.txt

# Exposer le port
EXPOSE 8080

# 💡 Utilisation de Gunicorn avec worker gevent
CMD ["gunicorn", "--timeout=300", "--workers=1", "--worker-class=gevent", "--bind=0.0.0.0:8080", "app:app"]
