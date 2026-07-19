"""
pipeline.py — Orchestrateur complet.
Fait circuler l'objet Document en mémoire et gère l'export (Markdown, HTML, PDF).
"""

import os
import argparse

from extract import extraire
from diagnostic import diagnostiquer
from ocr import ocraliser
from resolve import resoudre
from render import FORMATS, rendre_html


def executer_pipeline(pdf_path, format_sortie="markdown", sauver_json=True):
    # --- ÉTAPE 1 : Extraction (Conforme à ton script extract.py) ---
    print(f"[1/5] Extraction : {pdf_path}")
    doc = extraire(pdf_path)

    # --- ÉTAPE 2 : Diagnostic ---
    print("[2/5] Diagnostic...")
    diagnostiquer(doc)
    print(f"      recommend_ocr={doc.diagnostic.recommend_ocr} -- {doc.diagnostic.notes}")

    # --- ÉTAPE 3 : OCR (si recommandé) ---
    if doc.diagnostic.recommend_ocr:
        api_key = os.getenv("MISTRAL_API_KEY")
        if not api_key:
            print("[3/5] ⚠️ Enrichissement recommandé mais MISTRAL_API_KEY absent -- on continue sans OCR.")
        else:
            print("[3/5] Appel Mistral OCR...")
            ocraliser(doc, pdf_path, api_key)
    else:
        print("[3/5] OCR non nécessaire (économie).")

    # --- ÉTAPE 4 : Résolution ---
    print("[4/5] Résolution (passthrough natif pour l'instant)...")
    resoudre(doc)

    # --- ÉTAPE 5 : Rendu final ---
    print(f"[5/5] Rendu ({format_sortie})...")
    base = pdf_path.rsplit(".", 1)[0]

    if format_sortie in FORMATS:
        contenu = FORMATS[format_sortie](doc)
        extension = {"markdown": "md", "html": "html"}[format_sortie]
        fichier_sortie = f"{base}_propre.{extension}"
        with open(fichier_sortie, "w", encoding="utf-8") as f:
            f.write(contenu)
            
    elif format_sortie == "pdf":
        contenu_html = rendre_html(doc)
        fichier_sortie = f"{base}_propre.pdf"
        import weasyprint
        weasyprint.HTML(string=contenu_html).write_pdf(fichier_sortie)

    print(f"      ✅ Écrit : {fichier_sortie}")

    # --- Sauvegarde JSON de contrôle ---
    if sauver_json:
        json_path = base + ".document.json"
        doc.save(json_path)
        print(f"      📄 Document JSON (facultatif, pour inspection) : {json_path}")

    return doc


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pipeline complet de nettoyage de PDF")
    parser.add_argument("pdf", help="Chemin du PDF à traiter")
    parser.add_argument("--format", choices=["markdown", "html", "pdf"], default="markdown")
    parser.add_argument("--no-json", action="store_true", help="Ne pas écrire le document.json")
    args = parser.parse_args()

    executer_pipeline(args.pdf, args.format, sauver_json=not args.no_json)