import time
import fitz
from flask import Flask, render_template, request, send_file, flash, url_for, session, redirect
import os
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from utils import anonymiser_pdf, anonymiser_fichier_fec, anonymiser_fichier_dsn, anonymiser_word_docx
from google_oauth import bp_google
from flask import jsonify

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

@app.route("/analyse-avancee", methods=["POST"])
def analyse_avancee():
    data = request.json
    fichiers = data.get("fichiers", [])
    llm_type = data.get("llm", "gpt-3.5-turbo")  # Par défaut OpenAI
    prompt_template = data.get("prompt", "Analyse par défaut...")

    # Concatène le contenu des fichiers
    contenu = ""
    for fichier in fichiers:
        path = os.path.join(RESULT_FOLDER, fichier)
        ext = os.path.splitext(fichier)[1].lower()

        if ext in {".txt", ".edi"}:
            with open(path, "r", encoding="utf-8") as f:
                contenu += f.read() + "\n\n"
        elif ext == ".pdf":
            doc = fitz.open(path)
            contenu += "\n".join([page.get_text() for page in doc]) + "\n\n"
            doc.close()

    prompt_final = f"{prompt_template.strip()}\n\n---\n\n{contenu[:3000]}"

    if llm_type == "gpt-3.5-turbo":
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt_final}],
            temperature=0.7
        )
        output = response.choices[0].message.content
    else:
        return jsonify({"success": False, "error": "LLM non supporté pour l’instant."})

    # Sauvegarde temporaire en .txt
    timestamp = int(time.time())
    nom_base = f"synthese_{timestamp}"
    txt_path = os.path.join("static", f"{nom_base}.txt")
    pdf_path = os.path.join("static", f"{nom_base}.pdf")

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(output)

    # Convertit en PDF

    from fpdf import FPDF

    class PDF(FPDF):
        def header(self):
            # Centrer le logo
            self.image("static/logo.png", x=75, y=10, w=60)  # adapte si nécessaire
            self.ln(45)  # espace après le logo
            self.set_font("Times", "B", 18)
            self.set_text_color(126, 63, 242)
            self.cell(0, 10, "Synthèse générée par Xpert-IA", ln=True, align="C")
            self.ln(10)

        def footer(self):
            self.set_y(-15)
            self.set_font("Times", "I", 10)
            self.set_text_color(160)
            self.cell(0, 10, f"Page {self.page_no()}", align="C")

    # Création du PDF
    pdf = PDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.set_font("Times", "", 12)
    pdf.set_text_color(33, 33, 33)

    # Texte multiligne propre
    for line in output.strip().splitlines():
        pdf.multi_cell(0, 8, line)
        pdf.ln(1)

    pdf.output(pdf_path)

    return jsonify({
        "success": True,
        "synthese": output,
        "pdf_url": url_for('static', filename=f"{nom_base}.pdf"),
        "txt_url": url_for('static', filename=f"{nom_base}.txt")
    })

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

@app.route("/api/google-credentials")
def google_credentials():
    return {
        "client_id": os.getenv("GOOGLE_CLIENT_ID")
    }




if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
