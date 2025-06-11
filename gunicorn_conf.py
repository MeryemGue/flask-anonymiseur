# gunicorn_conf.py
sendfile = False  # Désactive l'utilisation système de sendfile
worker_class = "gthread"  # Meilleur pour téléchargement de fichiers
threads = 4
