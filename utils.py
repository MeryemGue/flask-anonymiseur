import os
import re
import fitz
import pandas as pd
from faker import Faker
import spacy
import ocrmypdf

# === Configuration ===
fake = Faker("fr_FR")
DOSSIER_ANONYMISÉ = "fichiers_anonymises"
os.makedirs(DOSSIER_ANONYMISÉ, exist_ok=True)

# === Chargement modèle spaCy personnalisé ===
MODELE_PATH = os.path.join(os.path.dirname(__file__), "models", "model-best")
nlp = spacy.load(MODELE_PATH)

# === FEC ===
# --- Compteurs pour générer des identifiants anonymes ---
compteur_personne = 1
compteur_client = 1

# --- Fonctions RGPD conformes ---
def anonymiser_compte(val):
    return "XXXXXXXXXX" if pd.notna(val) else val

def anonymiser_piece(val):
    return "REF-" + str(fake.random_int(min=10000, max=99999)) if pd.notna(val) else val

def anonymiser_nom_generique(prefixe):
    global compteur_personne
    identifiant = f"{prefixe}{str(compteur_personne).zfill(3)}"
    compteur_personne += 1
    return identifiant

def anonymiser_client_generique():
    global compteur_client
    identifiant = f"Client{str(compteur_client).zfill(3)}"
    compteur_client += 1
    return identifiant

def detecter_separateur(chemin_fichier):
    with open(chemin_fichier, 'r', encoding='utf-8') as f:
        ligne = f.readline()
        return "|" if ligne.count("|") > ligne.count("\t") else "\t"

def anonymiser_fichier_fec(chemin_fichier):
    try:
        sep = detecter_separateur(chemin_fichier)
        df = pd.read_csv(chemin_fichier, sep=sep, dtype=str)

        # Vérification des colonnes
        colonnes_requises = ["CompteNum", "CompteLib", "CompAuxNum", "CompAuxLib", "PieceRef", "EcritureLib"]
        for col in colonnes_requises:
            if col not in df.columns:
                print(f"Colonne manquante : {col}")
                return None

        # Anonymisation conforme RGPD
        df["CompteNum"] = df["CompteNum"].apply(anonymiser_compte)
        df["CompAuxNum"] = df["CompAuxNum"].apply(anonymiser_compte)
        df["CompteLib"] = df["CompteLib"].apply(lambda x: anonymiser_nom_generique("Client") if pd.notna(x) else x)
        df["CompAuxLib"] = df["CompAuxLib"].apply(lambda x: anonymiser_client_generique() if pd.notna(x) else x)
        df["PieceRef"] = df["PieceRef"].apply(anonymiser_piece)
        df["EcritureLib"] = df["EcritureLib"].apply(lambda x: "Libellé anonymisé" if pd.notna(x) else x)

        # Enregistrement
        nom_fichier = os.path.basename(chemin_fichier)
        sortie = os.path.join(DOSSIER_ANONYMISÉ, f"anonymise_{nom_fichier}")
        df.to_csv(sortie, sep=sep, index=False)
        return sortie
    except Exception as e:
        print("Erreur d'anonymisation FEC :", str(e))
        return None

# === PDF OCR ===

def anonymiser_pdf_ocr(chemin_pdf):
    try:
        PDF_OCR = chemin_pdf.replace(".pdf", "_OCR.pdf")
        PDF_SORTIE = os.path.join(DOSSIER_ANONYMISÉ, "anonymise_" + os.path.basename(chemin_pdf))

        ocrmypdf.ocr(
            chemin_pdf,
            PDF_OCR,
            language='fra',
            deskew=True,
            force_ocr=True,
            rotate_pages=True,
            remove_background=True,
            optimize=1
        )
        print("✅ OCR terminé :", PDF_OCR)

        # === Règles
        LABELS_SENSIBLES = {"NOM", "ADRESSE", "SIRET", "NSS", "DATE", "CODE_NAF", "URSSAF", "MATRICULE"}

        def est_montant(text):
            return bool(re.fullmatch(r"[\d\s.,-]+", text) and not re.fullmatch(r"\d{5,}", text)) or \
                re.search(r"(euros?|net|brut|montant|versé|payer|rémunération|salaire)", text.lower())

        def est_vrai_matricule(text):
            return bool(re.fullmatch(r"[A-Z]{2,}[0-9]{2,}", text.strip()))

        def est_vraie_adresse(text):
            return any(m in text.lower() for m in ["rue", "avenue", "boulevard", "chemin", "impasse", "allée", "place"])

        def est_info_non_sensible(text):
            return "xpert-ia" in text.lower() or "avenue magellan" in text.lower()

        # === Anonymisation du PDF
        doc = fitz.open(PDF_OCR)
        total_anonymise = 0

        for page_num, page in enumerate(doc):
            print(f"\n📄 Traitement page {page_num + 1}")
            blocks = page.get_text("dict")["blocks"]
            modifications = []
            x_offset, y_offset = -2, 8

            for block in blocks:
                if block["type"] != 0:
                    continue
                for line in block["lines"]:
                    line_text = " ".join(span["text"].strip() for span in line["spans"]).strip()

                    # Détection NOM
                    regex_nom = r"(Madame|Monsieur|M\.|Mme)\s+([A-Z][a-zéèêëàâäîïôöûüç'’\-]+\s+){0,3}[A-Z]{2,}(?:\s+[A-Z]{2,})*"
                    match_nom = re.search(regex_nom, line_text)
                    nom_detecte = match_nom.group() if match_nom else None
                    nom_remplace = False

                    # ✅ Correction ici : regex_adresse
                    regex_adresse = r"\b\d{1,4}\s+(rue|avenue|boulevard|chemin|impasse|allée|place)\s+[A-ZÉÈA-Za-zàâäéèêëïîôöùûüç'’\-]+"
                    match_adresse = re.search(regex_adresse, line_text, re.IGNORECASE)
                    adresse_detectee = match_adresse.group() if match_adresse else None
                    adresse_remplacee = False

                    for span in line["spans"]:
                        text = span["text"].strip()
                        x0, y0 = span["bbox"][:2]
                        font_size = span["size"]
                        texte_anonymise = text

                        # Détection NLP
                        doc_spacy = nlp(text)
                        for ent in doc_spacy.ents:
                            val = ent.text.strip()
                            label = ent.label_.upper()
                            if (
                                    est_info_non_sensible(val)
                                    or (label == "ADRESSE" and not est_vraie_adresse(val))
                                    or (label == "MATRICULE" and not est_vrai_matricule(val))
                                    or est_montant(val)
                            ):
                                continue
                            if label in LABELS_SENSIBLES and val in texte_anonymise:
                                texte_anonymise = texte_anonymise.replace(val, "*" * len(val))


                        # Si nom détecté, anonymiser ses spans
                        if nom_detecte and text in nom_detecte:
                            print(f"🔒 Partie du NOM détectée : {text}")
                            texte_anonymise = ""

                        # Si adresse détectée, anonymiser ses spans
                        if adresse_detectee and text in adresse_detectee:
                            print(f"🔒 Partie de l'ADRESSE détectée : {text}")
                            texte_anonymise = ""

                        # Appliquer la modification visuelle
                        if texte_anonymise != text:
                            page.add_redact_annot(span["bbox"], fill=(1, 1, 1))
                            modifications.append((x0 + x_offset, y0 + y_offset, texte_anonymise, font_size))
                            total_anonymise += 1

            page.apply_redactions()
            for x, y, txt, size in modifications:
                page.insert_text((x, y), txt, fontsize=size, color=(0, 0, 0))

        doc.save(PDF_SORTIE)
        doc.close()
        print(f"\n✅ PDF anonymisé généré : {PDF_SORTIE} — Total : {total_anonymise} éléments remplacés.")
        return PDF_SORTIE

    except Exception as e:
        print("Erreur PDF OCR :", e)
        return None
# === PDF simple ===
def anonymiser_pdf_simple(chemin_pdf):
    try:
        PDF_SORTIE = os.path.join(DOSSIER_ANONYMISÉ, "anonymise_" + os.path.basename(chemin_pdf))
        doc = fitz.open(chemin_pdf)
        modifications = []
        x_offset, y_offset = -2, 8
        LABELS_SENSIBLES = ["NOM", "ADRESSE", "SIRET", "NSS", "DATE", "CODE_NAF", "URSSAF", "MATRICULE"]

        def est_montant(text):
            text = text.strip()
            return bool(
                re.fullmatch(r"[\d\s.,-]+", text) and not re.fullmatch(r"\d{5,}", text)
            ) or re.search(r"(euros?|net|brut|montant|versé|payer|rémunération|salaire)", text.lower())

        def est_vrai_matricule(text):
            return bool(re.fullmatch(r"[A-Z]{2,}[0-9]{2,}", text.strip()))

        def est_vraie_adresse(text):
            mots_adresse = ["rue", "avenue", "bd", "boulevard", "impasse", "chemin", "allée"]
            return any(mot in text.lower() for mot in mots_adresse) or bool(re.fullmatch(r"\d{5} [A-ZÉÈÀ\- ]+", text))

        def est_info_non_sensible(text):
            if "XPERT-IA" in text:
                return True
            if re.search(r"\d{1,3} avenue magellan", text.lower()):
                return True
            return False

        for page_number, page in enumerate(doc):
            print(f"\n📄 Traitement de la page {page_number + 1}")
            blocks = page.get_text("dict")["blocks"]
            for block in blocks:
                if block['type'] == 0:
                    for line in block['lines']:
                        for span in line['spans']:
                            text = span['text']
                            x0, y0 = span['bbox'][:2]
                            font_size = span['size']
                            doc_spacy = nlp(text)
                            texte_anonymise = text
                            for ent in doc_spacy.ents:
                                label, val = ent.label_, ent.text.strip()
                                if (
                                    est_info_non_sensible(val) or
                                    (label == "ADRESSE" and not est_vraie_adresse(val)) or
                                    (label == "MATRICULE" and not est_vrai_matricule(val)) or
                                    est_montant(val)
                                ):
                                    print(f"⛔ Ignoré : {val} ({label})")
                                    continue
                                if label in LABELS_SENSIBLES:
                                    texte_anonymise = texte_anonymise.replace(val, "*" * len(val))
                            if texte_anonymise != text:
                                print(f"🔒 Bloc anonymisé : {text.strip()} ➡️ {texte_anonymise.strip()}")
                                page.add_redact_annot(span['bbox'], fill=(1, 1, 1))
                                modifications.append((x0 + x_offset, y0 + y_offset, texte_anonymise, font_size))
            page.apply_redactions()
            for x0, y0, texte, font_size in modifications:
                page.insert_text((x0, y0), texte, fontsize=font_size, color=(0, 0, 0))

        doc.save(PDF_SORTIE)
        doc.close()
        print(f"\n✅ PDF anonymisé sauvegardé sous : {PDF_SORTIE}")
        return PDF_SORTIE

    except Exception as e:
        print("Erreur PDF simple :", str(e))
        return None
# === Détection type PDF ===
def anonymiser_pdf(chemin_pdf):
    try:
        with fitz.open(chemin_pdf) as doc:
            has_text = any(page.get_text().strip() for page in doc)
        if has_text:
            print("📄 PDF simple détecté — Anonymisation directe")
            return anonymiser_pdf_simple(chemin_pdf)
        else:
            print("🖨️ PDF scanné détecté — OCR lancé")
            return anonymiser_pdf_ocr(chemin_pdf)
    except Exception as e:
        print("❌ Erreur lors de la détection du type de PDF :", str(e))
        return None