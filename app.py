import time
import fitz
from flask import Flask, render_template, request, send_file, flash, url_for, session, redirect
import os
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from utils import anonymiser_pdf, anonymiser_fichier_fec, anonymiser_fichier_dsn, anonymiser_word_docx
from google_oauth import bp_google



import openai

load_dotenv()

app = Flask(__name__)
app.secret_key = 'xpert-ia-secret'
app.register_blueprint(bp_google)
UPLOAD_FOLDER = 'uploads'
RESULT_FOLDER = 'fichiers_anonymises'
ALLOWED_EXTENSIONS = {'.pdf', '.txt', '.edi', '.docx','.doc'}


os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULT_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['RESULT_FOLDER'] = RESULT_FOLDER

MAX_FILE_SIZE_MB = 10

def allowed_file(filename):
    return os.path.splitext(filename)[1].lower() in ALLOWED_EXTENSIONS

client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

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

Tu es un expert-comptable spécialisé en analyse financière. Analyse le fichier FEC ci-joint (Fichier des Écritures Comptables) et génère un rapport clair et structuré. Commence par donner un résumé global de l’activité comptable : période couverte, nombre d’écritures, types de journaux et principales classes comptables utilisées.

Détaille ensuite les principales charges et produits en identifiant les comptes les plus fréquents et les variations importantes. Analyse les flux de trésorerie à partir des comptes bancaires : montants entrants et sortants, soldes par compte.

Repère les anomalies ou irrégularités potentielles comme les doublons, les incohérences de dates, ou les écritures comptables anormales. Si les données le permettent, propose des indicateurs financiers simples comme le taux de marge brute, la part des charges fixes ou variables, ou la concentration des ventes.

Termine par des recommandations ou des axes d’amélioration pour la gestion comptable de l’entreprise. Présente le tout de manière claire, synthétique, avec des tableaux ou graphiques si utile, en t’adressant à un lecteur non expert.

Langue : Français
"""

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )

    return response.choices[0].message.content


@app.route("/", methods=["GET", "POST"])
def index():
    if "historique_fichiers" not in session:
        session["historique_fichiers"] = []

    nouveaux_fichiers = []
    synthese = ""

    if request.method == "POST":
        files = request.files.getlist("files[]")
        for i, file in enumerate(files):
            filename = secure_filename(file.filename)
            ext = os.path.splitext(filename)[1].lower()

            # Format non supporté
            if not allowed_file(filename):
                flash(f"❌ Format non pris en charge : {filename}", "danger")
                continue

            # Taille trop grande
            # file.seek(0, os.SEEK_END)
            # file_size_mb = file.tell() / (1024 * 1024)
            # file.seek(0)
            # if file_size_mb > MAX_FILE_SIZE_MB:
            #     flash(f"❌ Fichier trop volumineux (> {MAX_FILE_SIZE_MB} Mo) : {filename}", "danger")
            #     continue

            # Sauvegarde uniquement si tout est valide
            input_path = os.path.join(UPLOAD_FOLDER, filename)
            file.save(input_path)

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

            # ✅ Affichage d'une alerte si le traitement échoue
            if result_path:
                nouveaux_fichiers.append(os.path.basename(result_path))
            else:
                flash(
                    f"⚠️ Impossible d’anonymiser le fichier {filename} : format scanné ou contenu non exploitable.",
                    "warning"
                )

            if i < len(files) - 1:
                time.sleep(2)

        historique = set(session.get("historique_fichiers", []))
        historique.update(nouveaux_fichiers)
        session["historique_fichiers"] = list(historique)


    fichiers_actuels = sorted(os.listdir(app.config["RESULT_FOLDER"]))
    return render_template("index.html", fichiers=fichiers_actuels, synthese=synthese)
from flask import jsonify

@app.route("/analyse", methods=["POST"])
def analyse_files():
    data = request.json
    fichiers = data.get("fichiers", [])

    try:
        synthese = generer_synthese_llm(fichiers)
        return jsonify({"success": True, "synthese": synthese})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/download/<filename>")
def download_file(filename):
    file_path = os.path.join(RESULT_FOLDER, filename)
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    flash("Fichier introuvable", "danger")
    return redirect(url_for("index"))


@app.route("/reset")
def reset():
    for f in os.listdir(RESULT_FOLDER):
        os.remove(os.path.join(RESULT_FOLDER, f))
    session["historique_fichiers"] = []
    flash("Historique réinitialisé avec succès.", "info")
    return redirect(url_for("index"))


@app.route("/delete/<filename>")
def delete_file(filename):
    file_path = os.path.join(RESULT_FOLDER, filename)
    if os.path.exists(file_path):
        os.remove(file_path)
        flash(f"Le fichier '{filename}' a été supprimé.", "success")
    else:
        flash(f"Le fichier '{filename}' est introuvable.", "danger")

    if "historique_fichiers" in session and filename in session["historique_fichiers"]:
        session["historique_fichiers"].remove(filename)

    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
