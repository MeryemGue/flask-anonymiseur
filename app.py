import os
import time
import fitz
import shutil
import openai
from dotenv import load_dotenv
from utils import anonymiser_pdf, anonymiser_fichier_fec, anonymiser_fichier_dsn, anonymiser_word_docx

from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from werkzeug.utils import secure_filename

load_dotenv()

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key='xpert-ia-secret')

UPLOAD_FOLDER = 'uploads'
RESULT_FOLDER = 'fichiers_anonymises'
ALLOWED_EXTENSIONS = {'.pdf', '.txt', '.edi', '.docx', '.doc'}
MAX_FILE_SIZE_MB = 10

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULT_FOLDER, exist_ok=True)

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

def allowed_file(filename):
    return os.path.splitext(filename)[1].lower() in ALLOWED_EXTENSIONS

def generer_synthese_llm(fichiers_anonymises, dossier="fichiers_anonymises"):
    contenu = ""
    for fichier in fichiers_anonymises:
        path = os.path.join(dossier, fichier)
        ext = os.path.splitext(fichier)[1].lower()
        if ext in {".txt", ".edi"}:
            with open(path, "r", encoding="utf-8") as f:
                contenu += f.read() + "\n\n"
        elif ext == ".pdf":
            doc = fitz.open(path)
            contenu += "\n".join([page.get_text() for page in doc]) + "\n\n"
            doc.close()

    prompt = f"""
{contenu[:3000]}

Tu es un expert-comptable spécialisé en analyse financière. Analyse le fichier FEC ci-joint (...)
Langue : Français
"""

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )

    return response.choices[0].message.content

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    fichiers_actuels = sorted(os.listdir(RESULT_FOLDER))
    return templates.TemplateResponse("index.html", {"request": request, "fichiers": fichiers_actuels, "synthese": ""})

@app.post("/", response_class=HTMLResponse)
async def upload_files(request: Request, files: list[UploadFile] = File(...)):
    nouveaux_fichiers = []

    for file in files:
        filename = secure_filename(file.filename)
        ext = os.path.splitext(filename)[1].lower()
        if not allowed_file(filename):
            continue

        input_path = os.path.join(UPLOAD_FOLDER, filename)
        with open(input_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        try:
            if ext == ".pdf":
                result_path = anonymiser_pdf(input_path)
            elif ext == ".txt":
                result_path = anonymiser_fichier_fec(input_path)
            elif ext == ".edi":
                result_path = anonymiser_fichier_dsn(input_path)
            elif ext in {".doc", ".docx"}:
                result_path = anonymiser_word_docx(input_path)
            else:
                result_path = None
        except Exception as e:
            print(f"❌ Erreur traitement fichier {filename} : {e}")
            result_path = None

        if result_path:
            nouveaux_fichiers.append(os.path.basename(result_path))

        time.sleep(2)

    fichiers_actuels = sorted(os.listdir(RESULT_FOLDER))
    return templates.TemplateResponse("index.html", {"request": request, "fichiers": fichiers_actuels, "synthese": ""})

@app.post("/analyse")
async def analyse_files(data: dict):
    fichiers = data.get("fichiers", [])
    try:
        synthese = generer_synthese_llm(fichiers)
        return JSONResponse({"success": True, "synthese": synthese})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)})

@app.get("/download/{filename}")
async def download_file(filename: str):
    file_path = os.path.join(RESULT_FOLDER, filename)
    if os.path.exists(file_path):
        return FileResponse(file_path, filename=filename)
    return RedirectResponse("/")

@app.get("/reset")
async def reset():
    for f in os.listdir(RESULT_FOLDER):
        os.remove(os.path.join(RESULT_FOLDER, f))
    return RedirectResponse("/", status_code=302)

@app.get("/delete/{filename}")
async def delete_file(filename: str):
    file_path = os.path.join(RESULT_FOLDER, filename)
    if os.path.exists(file_path):
        os.remove(file_path)
    return RedirectResponse("/", status_code=302)

@app.get("/api/google-credentials")
async def google_credentials():
    return {"client_id": os.getenv("GOOGLE_CLIENT_ID")}
