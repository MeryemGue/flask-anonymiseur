# gunicorn_conf.py
sendfile = False
worker_class = "gthread"
threads = 4
