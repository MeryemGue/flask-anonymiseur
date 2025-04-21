import fitz
from flask import Flask, render_template, request, redirect, send_from_directory, flash, url_for
import os

from openai import OpenAI
from werkzeug.utils import secure_filename
from utils import anonymiser_pdf, anonymiser_fichier_fec
import openai
from dotenv import load_dotenv
load_dotenv()


# --- Config ---
app = Flask(__name__)
app.secret_key = 'xpert-ia-secret'
UPLOAD_FOLDER = 'uploads'
RESULT_FOLDER = 'fichiers_anonymises'
ALLOWED_EXTENSIONS = {'.pdf', '.txt'}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULT_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['RESULT_FOLDER'] = RESULT_FOLDER

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

def allowed_file(filename):
    return os.path.splitext(filename)[1].lower() in ALLOWED_EXTENSIONS

# ✅ Fonction de synthèse automatique
def generer_synthese_llm(fichiers_anonymises, dossier="fichiers_anonymises"):
    contenu = ""

    for fichier in fichiers_anonymises:
        path = os.path.join(dossier, fichier)
        if path.endswith(".txt"):
            with open(path, "r", encoding="utf-8") as f:
                contenu += f.read() + "\n\n"
        elif path.endswith(".pdf"):
            doc = fitz.open(path)
            contenu += "\n".join([page.get_text() for page in doc]) + "\n\n"
            doc.close()

    prompt = f"""
Voici des documents anonymisés :

{contenu[:3000]}

Génère une synthèse professionnelle et structurée comportant :
- ✅ Les informations essentielles extraites
- 🚨 Toute irrégularité ou point sensible
- 📌 Les points à surveiller ou analyser
- 📝 Présentation claire avec titres ou bullet points si pertinent

Langue : Français
"""

    completion = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )

    return completion.choices[0].message.content

@app.route("/", methods=["GET", "POST"])
def index():
    fichiers_traites = []
    synthese = ""

    if request.method == "POST":
        files = request.files.getlist("files")
        for file in files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                path = os.path.join(UPLOAD_FOLDER, filename)
                file.save(path)

                ext = os.path.splitext(filename)[1].lower()
                if ext == ".pdf":
                    result = anonymiser_pdf(path)
                elif ext == ".txt":
                    result = anonymiser_fichier_fec(path)
                else:
                    result = None

                if result:
                    fichiers_traites.append(os.path.basename(result))

        if fichiers_traites:
            try:
                synthese = generer_synthese_llm(fichiers_traites)
            except Exception as e:
                synthese = "Erreur lors de la synthèse IA : " + str(e)

    return render_template("index.html", fichiers=fichiers_traites, synthese=synthese)

@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(RESULT_FOLDER, filename, as_attachment=True)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))


