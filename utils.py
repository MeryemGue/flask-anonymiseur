import os
import re
import fitz
import pandas as pd
from faker import Faker
import spacy
import ocrmypdf

import hashlib
from datetime import datetime


# === Configuration ===
fake = Faker("fr_FR")
DOSSIER_ANONYMISÉ = "fichiers_anonymises"
os.makedirs(DOSSIER_ANONYMISÉ, exist_ok=True)

# === Chargement modèle spaCy personnalisé ===
MODELE_PATH = os.path.join(os.path.dirname(__file__), "models", "model-best")
nlp = spacy.load(MODELE_PATH)

MODELE_PATH2 = os.path.join(os.path.dirname(__file__), "models", "model-best2")
nlp2 = spacy.load(MODELE_PATH2)

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
                # 🧪 Lire le contenu de la 1ère page
                texte_page1 = doc[0].get_text().lower()
                print("📝 Texte page 1 =", texte_page1[:200])  # Affiche les 200 premiers caractères

                # ✅ Test : est-ce un contrat ?
                if "contrat" in texte_page1 and "travail" in texte_page1:
                    print("📄 Contrat détecté dans PDF simple — anonymisation spéciale")
                    chemin_sortie = os.path.join(DOSSIER_ANONYMISÉ, f"anonymise_{os.path.basename(chemin_pdf)}")
                    anonymiser_Contrat(chemin_pdf, chemin_sortie)
                    return chemin_sortie

                print("📄 PDF simple détecté — Anonymisation bulletin")
                return anonymiser_pdf_simple(chemin_pdf)

            else:
                print("🖨️ PDF scanné détecté — OCR lancé")
                return anonymiser_pdf_ocr(chemin_pdf)

    except Exception as e:
        print("❌ Erreur lors de la détection du type de PDF :", str(e))
        return None



# === Utilitaires DSN ===
def hash_nir(nir):
    return hashlib.sha256(nir.encode()).hexdigest()[:12]

def tranche_age(date_str):
    try:
        jour, mois, annee = int(date_str[:2]), int(date_str[2:4]), int(date_str[4:8])
        age = datetime.now().year - annee
        if age < 25: return "'Moins de 25 ans'"
        elif age < 30: return "'25-29 ans'"
        elif age < 35: return "'30-34 ans'"
        elif age < 40: return "'35-39 ans'"
        elif age < 50: return "'40-49 ans'"
        else: return "'50 ans et plus'"
    except:
        return "'X'"

# === Codes sensibles DSN ===
codes_anonymisation_dsn = {
    "S10.G00.00.001": lambda val, i: "'ANON_APP'",
    "S10.G00.00.002": lambda val, i: "'ANON_APP'",
    "S10.G00.00.003": lambda val, i: "'XXXXXXXXX'",
    "S10.G00.01.001": lambda val, i: "'000000000'",
    "S10.G00.01.003": lambda val, i: "'ENTREPRISE_X'",
    "S10.G00.01.004": lambda val, i: "'X'",
    "S10.G00.01.005": lambda val, i: val,
    "S10.G00.01.006": lambda val, i: "'X'",
    "S10.G00.02.002": lambda val, i: "'DECLARANT_X'",
    "S10.G00.02.004": lambda val, i: "'dummy@email.com'",
    "S10.G00.02.005": lambda val, i: "'DUMMY_PHONE'",
    "S20.G00.05.004": lambda val, i: "'" + hash_nir(val.strip("'")) + "'",
    "S20.G00.07.002": lambda val, i: "'DUMMY_PHONE'",
    "S20.G00.07.003": lambda val, i: "'dummy@email.com'",
    "S21.G00.30.001": lambda val, i: "'" + hash_nir(val.strip("'")) + "'",
    "S21.G00.30.002": lambda val, i: f"'SAL_{i:04d}'",
    "S21.G00.30.003": lambda val, i: f"'SAL_{i:04d}'",
    "S20.G00.07.001": lambda val, i: f"'SAL_{i:04d}'",
    "S21.G00.30.004": lambda val, i: "'X'",
    "S21.G00.30.006": lambda val, i: tranche_age(val.strip("'")),
    "S21.G00.30.008": lambda val, i: "'X'",
    "S21.G00.30.010": lambda val, i: "'X'",
}

# === Regex génériques DSN ===
email_regex_dsn = re.compile(r"[\w\.-]+@[\w\.-]+")
phone_regex_dsn = re.compile(r"'\d{10}'")
siret_regex_dsn = re.compile(r"'\d{9}'|'\d{14}'")
date_naissance_regex_dsn = re.compile(r"'\d{8}'")

# === Fonction principale ===
def anonymiser_fichier_dsn(chemin_fichier):
    try:
        with open(chemin_fichier, 'r', encoding='utf-8') as f:
            lignes = f.readlines()

        lignes_anonymisees = []
        compteur_salarie = 1

        for ligne in lignes:
            ligne = ligne.strip()
            if not ligne or ',' not in ligne:
                lignes_anonymisees.append(ligne + "\n")
                continue

            code, val = map(str.strip, ligne.split(",", 1))
            valeur = val.strip()

            if code in codes_anonymisation_dsn:
                valeur_anonyme = codes_anonymisation_dsn[code](valeur, compteur_salarie)
                ligne_anonyme = f"{code},{valeur_anonyme}"
                if code == "S21.G00.30.001":
                    compteur_salarie += 1
            else:
                # Anonymisation générique
                if email_regex_dsn.search(valeur):
                    ligne_anonyme = f"{code},'dummy@email.com'"
                elif phone_regex_dsn.search(valeur):
                    ligne_anonyme = f"{code},'0000000000'"
                elif siret_regex_dsn.search(valeur):
                    ligne_anonyme = f"{code},'000000000'"
                elif date_naissance_regex_dsn.search(valeur):
                    ligne_anonyme = f"{code},'01011970'"
                else:
                    ligne_anonyme = ligne  # inchangé

            lignes_anonymisees.append(ligne_anonyme + "\n")

        # Enregistrement
        nom_fichier = os.path.basename(chemin_fichier)
        sortie = os.path.join(DOSSIER_ANONYMISÉ, f"anonymise_{nom_fichier}")
        with open(sortie, 'w', encoding='utf-8') as f_out:
            f_out.writelines(lignes_anonymisees)

        print(f"✅ Fichier DSN anonymisé : {sortie}")
        return sortie

    except Exception as e:
        print("Erreur d'anonymisation DSN :", str(e))
        return None


def anonymiser_Contrat(pdf_ocr_path, pdf_sortie_path):
    REGEX_NOM_MANUEL = re.compile(
        r'\b(Monsieur|M.|Madame|M\.?|Mr\.?)\s+(?:[A-Z][a-zéèêàîïç\-]+\s+)?[A-Z][A-Z\-]+\b',flags=re.IGNORECASE
    )
    REGEX_ENTREPRISE_MANUEL = re.compile(
        r'\b(la société|la sarl|l\'entreprise|le groupe|la sas|la sa)\s+([A-Z&\s\.\'\-]+)', flags=re.IGNORECASE
    )

    EXCLUSIONS = [
        "CONTRAT DE TRAVAIL", "A TEMPS COMPLET", "A DUREE INDETERMINEE", "CREATIONS DU SALARIE","DEPLACEMENTS",
        "ARTICLE", "REMUNERATION", "FONCTIONS", "Entre", "ABSENCES", "CONFIDENTIALITE", "NON-CONCURRENCE","NON - CONCURRENCE","CREATIONS DU SALARIE"
    ]
    LABELS_READABLE = {
        "NOM": "nom", "ADRESSE": "adresse", "SIRET": "siret", "NSS": "nss", "DATE": "date",
        "CODE_NAF": "code_naf", "ENTREPRISE": "entreprise", "MATRICULE": "matricule", "URSSAF": "urssaf"
    }

    doc = fitz.open(pdf_ocr_path)

    for page_number, page in enumerate(doc):
        print(f"\n📄 Traitement de la page {page_number + 1}")
        blocks = page.get_text("dict")["blocks"]
        modifications = []
        x_offset, y_offset = -2, 8

        for block in blocks:
            if block['type'] != 0:
                continue

            for line in block['lines']:
                spans = line['spans']
                full_line = "".join([s['text'] for s in spans])
                doc_spacy = nlp2(full_line)

                texte_anonymise = ""
                last_idx = 0
                used_spans = []

                for ent in doc_spacy.ents:
                    if ent.label_ in LABELS_READABLE and not any(ex in ent.text.upper() for ex in EXCLUSIONS):
                        texte_anonymise += full_line[last_idx:ent.start_char] + "*******"
                        last_idx = ent.end_char
                        used_spans.append((ent.start_char, ent.end_char))
                texte_anonymise += full_line[last_idx:]

                if not any(e.label_ == "NOM" for e in doc_spacy.ents):
                    for match in REGEX_NOM_MANUEL.finditer(full_line):
                        span_start, span_end = match.span()
                        if not any(s <= span_start < e or s < span_end <= e for s, e in used_spans):
                            texte_anonymise = texte_anonymise.replace(match.group(), "********")

                for match in REGEX_ENTREPRISE_MANUEL.finditer(full_line):
                    texte_anonymise = texte_anonymise.replace(match.group(), f"{match.group(1)} *********")

                if texte_anonymise != full_line:
                    print(f"🔒 Bloc anonymisé : {full_line.strip()} ➡️ {texte_anonymise.strip()}")
                    for s in spans:
                        page.add_redact_annot(s['bbox'], fill=(1, 1, 1))
                    x0, y0 = spans[0]['bbox'][:2]
                    font_size = spans[0]['size']
                    modifications.append((x0 + x_offset, y0 + y_offset, texte_anonymise, font_size))

        page.apply_redactions()
        for x0, y0, texte, font_size in modifications:
            page.insert_text((x0, y0), texte, fontsize=font_size, color=(0, 0, 0))

    doc.save(pdf_sortie_path)
    doc.close()
    print(f"\n✅ PDF anonymisé sauvegardé sous : {pdf_sortie_path}")



def anonymiser_fichier(chemin_fichier):
    ext = os.path.splitext(chemin_fichier)[1].lower()
    if ext == ".csv" or ext == ".txt":
        return anonymiser_fichier_fec(chemin_fichier)
    elif ext == ".pdf":
        return anonymiser_pdf(chemin_fichier)
    elif ext == ".edi":
        return anonymiser_fichier_dsn(chemin_fichier)
    else:
        print("❓ Format non pris en charge :", ext)
        return None
