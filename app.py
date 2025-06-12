import time
import fitz
from flask import Flask, render_template, request, send_file, flash, url_for, session, redirect, jsonify
import os
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from utils import anonymiser_pdf, anonymiser_fichier_fec, anonymiser_fichier_dsn, anonymiser_word_docx
from google_oauth import bp_google
import openai
import uuid
import shutil

load_dotenv()

app = Flask(__name__)
app.secret_key = 'xpert-ia-secret'
app.register_blueprint(bp_google)

ALLOWED_EXTENSIONS = {'.pdf', '.txt', '.edi', '.docx','.doc'}
MAX_FILE_SIZE_MB = 10

client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

def allowed_file(filename):
    return os.path.splitext(filename)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/analyse-avancee", methods=["POST"])
def analyse_avancee():
    if "session_id" not in session:
        session["session_id"] = str(uuid.uuid4())

    session_id = session["session_id"]
    RESULT_FOLDER_USER = os.path.join("fichiers_anonymises", session_id)

    data = request.json
    fichiers = data.get("fichiers", [])
    llm_type = data.get("llm", "gpt-3.5-turbo")
    prompt_template = data.get("prompt", "Analyse par défaut...")

    contenu = ""
    for fichier in fichiers:
        path = os.path.join(RESULT_FOLDER_USER, fichier)
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

    timestamp = int(time.time())
    nom_base = f"synthese_{timestamp}"
    txt_path = os.path.join(RESULT_FOLDER_USER, f"{nom_base}.txt")
    pdf_path = os.path.join(RESULT_FOLDER_USER, f"{nom_base}.pdf")

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(output)

    from fpdf import FPDF

    class PDF(FPDF):
        def header(self):
            self.image("static/logo.png", x=75, y=10, w=60)
            self.ln(45)
            self.set_font("Times", "B", 18)
            self.set_text_color(126, 63, 242)
            self.cell(0, 10, "Synthèse générée par Xpert-IA", ln=True, align="C")
            self.ln(10)

        def footer(self):
            self.set_y(-15)
            self.set_font("Times", "I", 10)
            self.set_text_color(160)
            self.cell(0, 10, f"Page {self.page_no()}", align="C")

    pdf = PDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.set_font("Times", "", 12)
    pdf.set_text_color(33, 33, 33)

    for line in output.strip().splitlines():
        pdf.multi_cell(0, 8, line)
        pdf.ln(1)

    pdf.output(pdf_path)

    return jsonify({
        "success": True,
        "synthese": output,
        "pdf_url": url_for('download_file', filename=f"{session_id}/{nom_base}.pdf"),
        "txt_url": url_for('download_file', filename=f"{session_id}/{nom_base}.txt")
    })

@app.route("/", methods=["GET", "POST"])
def index():
    if "session_id" not in session:
        session["session_id"] = str(uuid.uuid4())

    session_id = session["session_id"]
    UPLOAD_FOLDER_USER = os.path.join("uploads", session_id)
    RESULT_FOLDER_USER = os.path.join("fichiers_anonymises", session_id)

    os.makedirs(UPLOAD_FOLDER_USER, exist_ok=True)
    os.makedirs(RESULT_FOLDER_USER, exist_ok=True)

    if "historique_fichiers" not in session:
        session["historique_fichiers"] = []

    nouveaux_fichiers = []
    synthese = ""

    if request.method == "POST":
        files = request.files.getlist("files[]")
        for i, file in enumerate(files):
            filename = secure_filename(file.filename)
            ext = os.path.splitext(filename)[1].lower()

            if not allowed_file(filename):
                flash(f"❌ Format non pris en charge : {filename}", "danger")
                continue

            input_path = os.path.join(UPLOAD_FOLDER_USER, filename)
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

            if result_path:
                output_path = os.path.join(RESULT_FOLDER_USER, os.path.basename(result_path))
                shutil.move(result_path, output_path)
                nouveaux_fichiers.append(os.path.basename(output_path))
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

    fichiers_actuels = sorted(os.listdir(RESULT_FOLDER_USER)) if os.path.exists(RESULT_FOLDER_USER) else []
    return render_template("index.html", fichiers=fichiers_actuels, synthese=synthese)

@app.route("/download/<path:filename>")
def download_file(filename):
    file_path = os.path.join("fichiers_anonymises", filename)
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    flash("Fichier introuvable", "danger")
    return redirect(url_for("index"))

@app.route("/reset")
def reset():
    session_id = session.get("session_id")
    if session_id:
        shutil.rmtree(os.path.join("uploads", session_id), ignore_errors=True)
        shutil.rmtree(os.path.join("fichiers_anonymises", session_id), ignore_errors=True)
    session.clear()
    flash("Historique réinitialisé avec succès.", "info")
    return redirect(url_for("index"))

@app.route("/delete/<filename>")
def delete_file(filename):
    session_id = session.get("session_id")
    file_path = os.path.join("fichiers_anonymises", session_id, filename)
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
