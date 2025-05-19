import ocrmypdf
import shutil
import traceback
import os

# === TEST PRÉSENCE DES BINAIRES
print("🧪 Tesseract path :", shutil.which("tesseract"))
print("🧪 Ghostscript path :", shutil.which("gs"))

# === Vérifie que le fichier est présent
input_path = "Bulletin 02.25.pdf"
output_path = "output_ocr.pdf"

if not os.path.exists(input_path):
    print("❌ Le fichier input.pdf est manquant.")
    exit(1)

# === Essai de traitement OCR
try:
    ocrmypdf.ocr(input_path, output_path, language='fra', force_ocr=True)
    print("✅ OCR terminé avec succès.")
except Exception as e:
    print("❌ OCR échoué :", e)
    traceback.print_exc()
