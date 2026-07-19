"""
pipeline.py — Point d'entrée principal.
Fait circuler l'objet Document à travers les différentes étapes.
"""

import argparse
from document import Document
from extract import extraire

def run_pipeline(pdf_path: str):
    print(f"🚀 Démarrage du pipeline sur : {pdf_path}")
    
    # 1. Création de l'objet métier vierge
    doc = Document()
    
    # 2. Remplissage natif
    print("🔍 Extraction native en cours...")
    extraire(doc, pdf_path)
    
    # 3. Sauvegarde de contrôle (qui sera retirée en production)
    output_json = pdf_path.rsplit(".", 1)[0] + ".document.json"
    doc.save(output_json)
    
    print(f"✅ Extraction terminée ! ({doc.metadata.page_count} pages traitées)")
    print(f"📄 Contrôle JSON sauvegardé dans : {output_json}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DataCleaner Pipeline")
    parser.add_argument("pdf", help="Fichier PDF à analyser")
    args = parser.parse_args()
    
    run_pipeline(args.pdf)