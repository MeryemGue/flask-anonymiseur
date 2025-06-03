import os
from flask import Blueprint, redirect, url_for, session, request, flash
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


import pathlib

bp_google = Blueprint('google_oauth', __name__)

# === Configuration ===
CLIENT_SECRETS_FILE = "credentials.json"
SCOPES = ["https://www.googleapis.com/auth/drive.file"]
REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://127.0.0.1:8080/oauth2callback")
print("Redirect URI utilisé :", REDIRECT_URI)


# === Lancer l'authentification Google ===
@bp_google.route("/authorize")
def authorize():
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )
    auth_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true'
    )
    session["state"] = state
    print("👉 URL de redirection générée :", auth_url)
    return redirect(auth_url)


# === Callback après authentification ===
@bp_google.route("/oauth2callback")
def oauth2callback():
    state = session["state"]
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )
    flow.fetch_token(authorization_response=request.url)
    credentials = flow.credentials
    session["credentials"] = {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": credentials.scopes
    }
    flash("✅ Connecté à Google Drive avec succès !", "success")
    return redirect(url_for("index"))


# === Fonction pour envoyer un fichier sur Drive ===
def upload_to_drive(filepath):
    from google.oauth2.credentials import Credentials

    creds_info = session.get("credentials")
    if not creds_info:
        return None

    creds = Credentials(**creds_info)
    service = build("drive", "v3", credentials=creds)
    file_metadata = {"name": os.path.basename(filepath)}
    media = MediaFileUpload(filepath, resumable=True)
    uploaded_file = service.files().create(body=file_metadata, media_body=media, fields="id").execute()

    return uploaded_file.get("id")
