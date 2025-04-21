import os, re, fitz, pandas as pd
from faker import Faker

fake = Faker("fr_FR")

DOSSIER_ANONYMISÉ = "fichiers_anonymises"
os.makedirs(DOSSIER_ANONYMISÉ, exist_ok=True)

def anonymiser_texte_lettre_mission(text):
    text = re.sub(r"\b(Cher(?:e)?)\s+(Monsieur|Madame)\s+[A-Z\-]{2,}(?=,)", r"\1 \2 ********", text)
    text = re.sub(r"\b(Monsieur|Madame|M\.?|M )\s+[A-ZÉÈÙÂÊÎÔÛ][a-zéèêëîïôöûüàäç\-]+\s+[A-Z\-]{2,}\b", r"\1 ********", text)
    text = re.sub(r"\b(M\.?|M |Mme\.?|Madame)\s+[A-Z\-]{2,}\b", r"\1 ********", text)
    text = re.sub(r"[A-Z]{2,} Consulting\b", "********", text)
    text = re.sub(r"\d{1,3}\s+[^,\n]+(?:Avenue|Rue|Boulevard|Allée|Impasse)\s+[^,\n]+\d{5}\s+[A-ZÉ\- ]+", "********", text)
    text = re.sub(r"\b\d{5}\s+[A-Z\- ]{2,}\b", "********", text)
    text = re.sub(r"\b(Fait le|Daté du)\s+\d{1,2}\s+\w+\s+\d{4}", r"\1 ********", text, flags=re.IGNORECASE)
    text = re.sub(r"\u00e0\s+[A-ZÉÈÙÂÊÎÔÛ][a-zéèêëîïôöûüàäç\-]+", "à ********", text)
    text = re.sub(r"\b(Monsieur|Cher|Madame|M\.?|M )\s+[A-ZÉÈÙÂÊÎÔÛ][a-zéèêëîïôöûüàäç\-]+\s+[A-Z\-]{2,}\b", r"\1 ********",
                  text)
    text = re.sub(r"\b(M\.?|M |Madame)\s+[A-Z\-]{2,}\b", r"\1 ********", text)
    text = re.sub(r"(Nom\s+de\s+facturation\s*:?)\s*.*", r"\1 ********", text, flags=re.IGNORECASE)
    text = re.sub(r"(Coordonnées\s+de\s+l[’']entreprise\s*:?)\s*.*", r"\1 ********", text, flags=re.IGNORECASE)

    text = re.sub(r"\b[A-ZÉÈÙÂÊÎÔÛ][a-zéèêëîïôöûüàäç\-]+\s+[A-Z\-]{2,}\b", "********", text)

    text = re.sub(r"(Numéro\s+de\s+confirmation\s+Hotels\.com\s*:?)\s*\d{10,}", r"\1 ********", text,
                  flags=re.IGNORECASE)

    # Autres informations personnelles
    text = re.sub(r"\b\d{13,16}\b", "*************", text)  # numéros longs type carte ou confirmation
    text = re.sub(r"\+33\s?\d{9}", "+33 *********", text)  # téléphone
    text = re.sub(r"\b[A-ZÉÈÙÂÊÎÔÛ][a-zéèêëîïôöûüàäç\-]+ [A-ZÉÈÙÂÊÎÔÛ\-]{2,}\b", "********", text)  # noms composés

    return text

def anonymiser_texte_contrat(text):
    if "##CONTRAT##" in text:
        return ""
    text = re.sub(r"(Numéro de sécurité sociale\s*:\s*)[12] ?\d{2} ?\d{2} ?\d{2} ?\d{3} ?\d{2}", r"\1***************", text, flags=re.IGNORECASE)
    text = re.sub(r"(Demeurant\s*:?\s*)(.*?\d{5}\s+[A-Z\- ]+)", r"\1********", text)
    text = re.sub(r"\b(Monsieur|Madame|M\.?|M )\s+[A-ZÉÈÙÂÊÎÔÛ][a-zéèêëîïôöûüàäç\-]+\s+[A-Z\-]{2,}\b", r"\1 ********", text)
    text = re.sub(r"\b(M\.?|M |Madame)\s+[A-Z\-]{2,}\b", r"\1 ********", text)
    text = re.sub(r"\b(?:N°\s*|SIRET\s*[:\-]?)\d{9}\s?\d{5}\b", "SIRET : **************", text)
    text = re.sub(r"\b(SIRET\s*[:\-]?\s*)?\d{3}\s?\d{3}\s?\d{3}\s?\d{5}\b", "SIRET : ***************", text, flags=re.IGNORECASE)
    text = re.sub(r"(?:Code\s*APE\s*[:\-]?)\d{3,4}[A-Z]", "Code APE : ********", text, flags=re.IGNORECASE)
    text = re.sub(r"(?:CODE\s*APE\s*[:\-]?)\s*\d{4}[A-Z]", "CODE APE : ********", text, flags=re.IGNORECASE)  # 👈 ajout important
    text = re.sub(r"à\s+[A-ZÉÈÙÂÊÎÔÛ][a-zéèêëîïôöûüàäç\-]+\s*\(\d{2,3}\)", "à ******** (**)", text)
    text = re.sub(r"(immatriculée sous le numéro\s+)(\d{3})\s?\d{5,}", r"\1\2 ********", text, flags=re.IGNORECASE)
    return text


def anonymiser_texte_reservation(text):
    text = re.sub(r"(Numéro de carte\s*:?)[^\n]+", r"\1 ************", text, flags=re.IGNORECASE)
    text = re.sub(r"(Nom\s+de\s+facturation\s*:?)\s*[A-ZÉÈÙÂÊÎÔÛa-zéèêëîïôöûüàäç\- ]+", r"\1 ********", text,
                  flags=re.IGNORECASE)
    text = re.sub(r"(Coordonnées de l’entreprise\s*:?)\s*.+", r"\1 ********", text, flags=re.IGNORECASE)
    text = re.sub(r"(Numéro de confirmation Hotels\.com\s*:?)\s*\d{10,}", r"\1 ********", text, flags=re.IGNORECASE)
    text = re.sub(r"\b\d{13}\b", "*************", text)
    text = re.sub(r"\b[A-ZÉÈÙÂÊÎÔÛ][a-zéèêëîïôöûüàäç\-]+ [A-ZÉÈÙÂÊÎÔÛ\-]{2,}\b", "********", text)
    #text = re.sub(r"RCA\s+Consulting", "********", text, flags=re.IGNORECASE)
    text = re.sub(r"\d{1,3}\s+rue\s+du\s+[^,\n]+,\s+[A-Za-zéèêîï\- ]+,\s+[A-Za-zéèêîï\- ]+,\s+\d{5},\s+France",
                  "********", text)
    text = re.sub(r"\+33\s?\d{9}", "+33 *********", text)
    # Gestion des espaces insécables et irréguliers pour RCA Consulting et noms
    text = re.sub(r"Nom\s+de\s+facturation\s*:?\s*[\w\s\u00A0\-]+", "Nom de facturation ********", text, flags=re.IGNORECASE)
    text = re.sub(r"Coordonnées\s+de\s+l[’']entreprise\s*:?\s*[\w\s\u00A0\-]+", "Coordonnées de l’entreprise ********", text, flags=re.IGNORECASE)
    #text = re.sub(r"RCA[\s\u00A0]+Consulting", "********", text, flags=re.IGNORECASE)

    return text


def anonymiser_nom(nom): return fake.company() if pd.notna(nom) else nom

def anonymiser_compte(num): return re.sub(r"\d", "X", num) if pd.notna(num) else num

def anonymiser_piece(piece): return "REF-" + str(fake.random_int(min=10000, max=99999)) if pd.notna(piece) else piece

def detecter_separateur(chemin_fichier):
    with open(chemin_fichier, 'r', encoding='utf-8') as f:
        ligne = f.readline()
        return "|" if ligne.count("|") > ligne.count("\t") else "\t"

def anonymiser_nom_fec(nom):
    if pd.notna(nom):
        return fake.name()
    return nom

def anonymiser_fichier_fec(chemin_fichier):
    try:
        sep = detecter_separateur(chemin_fichier)
        df = pd.read_csv(chemin_fichier, sep=sep, dtype=str)
        colonnes_requises = ["CompteNum", "CompteLib", "CompAuxNum", "CompAuxLib", "PieceRef"]

        for col in colonnes_requises:
            if col not in df.columns:
                print(f"Colonne manquante : {col}")
                return None

        df["CompteLib"] = df["CompteLib"].apply(anonymiser_nom_fec)
        df["CompteNum"] = df["CompteNum"].apply(anonymiser_compte)
        df["CompAuxNum"] = df["CompAuxNum"].apply(anonymiser_compte)
        df["CompAuxLib"] = df["CompAuxLib"].apply(anonymiser_nom)
        df["PieceRef"] = df["PieceRef"].apply(anonymiser_piece)

        nom_fichier = os.path.basename(chemin_fichier)
        sortie = os.path.join(DOSSIER_ANONYMISÉ, f"anonymise_{nom_fichier}")
        df.to_csv(sortie, sep=sep, index=False)
        return sortie
    except Exception as e:
        print("Erreur d'anonymisation :", str(e))
        return None

def anonymiser_texte_pdf(text):
    text = anonymiser_texte_contrat(text)
    text = anonymiser_texte_lettre_mission(text)
    text = anonymiser_texte_reservation(text)
    text = re.sub(r"\b[A-Z][a-z]+ [A-Z]{2,}\b", "********", text)
    text = re.sub(r"\d{13}", "*************", text)
    text = re.sub(r"\d{2}\*{5}\d{2}", "***********", text)
    text = re.sub(r"Code\s*Naf\s*[:：]?\s*\d{4}[A-Z]?", "Code Naf : *****", text, flags=re.IGNORECASE)
    text = re.sub(r"Urssaf/Msa\s*:\s*\w+", "Urssaf/Msa : ********", text)
    text = re.sub(r"Matricule\s*:\s*[A-Z0-9]+", "Matricule : ********", text)
    text = re.sub(r"\b[A-Z]{2,4}\d{1,4}\b", "********", text)
    text = re.sub(r"N° SS\s*:\s*\d{15}", "N° SS : ***************", text)
    text = re.sub(r"Emploi\s*:\s*.+", "Emploi : ********", text)
    text = re.sub(r"Statut professionnel\s*:\s*\w+", "Statut professionnel : ********", text)
    text = re.sub(r"Position\s*:\s*\d\.\d", "Position : **.*", text)
    text = re.sub(r"Coefficient\s*:\s*\d+", "Coefficient : ***", text)
    text = re.sub(r"Convention collective\s*:\s*.+", "Convention collective : ********", text)
    text = re.sub(r"\d{2}/\d{2}/\d{4}", "**/**/****", text)
    text = re.sub(r'\b\d{4}[A-Za-z]\b', '*****', text)
    return text

def anonymiser_pdf(chemin_pdf):
    try:
        doc = fitz.open(chemin_pdf)
        texte_total = "\n".join([page.get_text() for page in doc])
        texte_lower = texte_total.lower()

        is_contrat = "contrat" in texte_lower
        is_lettre_mission = "cher monsieur" in texte_lower or "lettre de mission" in texte_lower
        is_reservation = "hotels.com" in texte_lower or "numéro de confirmation" in texte_lower

        for page in doc:
            blocks = page.get_text("dict")["blocks"]
            modifications = []
            for block in blocks:
                if block["type"] == 0:
                    for line in block["lines"]:
                        for span in line["spans"]:
                            text = span["text"]
                            x0, y0 = span["bbox"][:2]
                            font_size = span["size"]

                            if is_contrat:
                                texte_anonymise = anonymiser_texte_contrat(text)
                            elif is_lettre_mission:
                                texte_anonymise = anonymiser_texte_lettre_mission(text)
                            elif is_reservation:
                                texte_anonymise = anonymiser_texte_reservation(text)
                            else:
                                texte_anonymise = anonymiser_texte_pdf(text)

                            if texte_anonymise != text:
                                page.add_redact_annot(span["bbox"], fill=(1, 1, 1))
                                modifications.append((x0 - 2, y0 + 6, texte_anonymise, font_size))

            page.apply_redactions()
            for x0, y0, texte, font_size in modifications:
                page.insert_text((x0, y0), texte, fontsize=font_size, color=(0, 0, 0))

        nom_fichier = os.path.basename(chemin_pdf)
        sortie = os.path.join(DOSSIER_ANONYMISÉ, f"anonymise_{nom_fichier}")
        doc.save(sortie)
        doc.close()
        return sortie
    except Exception as e:
        print("Erreur PDF :", str(e))
        return None