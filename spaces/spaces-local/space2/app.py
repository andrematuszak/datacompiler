"""
pipeline.py — Le chef d'orchestre mis à jour.
Il prend désormais en charge l'export direct au format PDF propre.
"""

import os
import sys
import argparse
from pathlib import Path

from extract import extraire
from ocr import ocraliser
from render import rendre_html, rendre_markdown

def executer_pipeline(pdf_path, format_sortie="html"):
    print(f"🚀 [DEBUT] Traitement du fichier : {pdf_path}")
    
    # -------------------------------------------------------------------------
    # ÉTAPE 1 : Extraction Native & Diagnostic
    # -------------------------------------------------------------------------
    print("\n🔍 [ÉTAPE 1] Extraction des données natives et diagnostic...")
    doc = extraire(pdf_path)
    
    json_native = pdf_path.rsplit(".", 1)[0] + ".document.json"
    doc.save(json_native)
    print(f"   ↳ Grille native sauvegardée dans : {json_native}")
    
    # -------------------------------------------------------------------------
    # ÉTAPE 2 : Décision d'aiguillage & OCR optionnel
    # -------------------------------------------------------------------------
    if doc.needs_enrichment():
        print("\n🤖 [ÉTAPE 2] Le diagnostic demande un enrichissement. Appel à Mistral OCR...")
        
        api_key = os.getenv("MISTRAL_API_KEY")
        if not api_key:
            print("❌ Erreur : La variable d'environnement MISTRAL_API_KEY n'est pas configurée.")
            return
            
        pages_ocr = ocraliser(pdf_path, api_key)
        doc.ocr = pages_ocr
        
        json_ocr = pdf_path.rsplit(".", 1)[0] + ".ocr.json"
        doc.save(json_ocr)
        print(f"   ↳ Grille OCR sauvegardée dans : {json_ocr}")
    else:
        print("\n✅ [ÉTAPE 2] Le texte natif est fiable. Économie d'API : Mistral n'est pas appelé.")

    # -------------------------------------------------------------------------
    # ÉTAPE 3 : Rendu final (Génération du livrable)
    # -------------------------------------------------------------------------
    print(f"\n🎨 [ÉTAPE 3] Génération du rendu final au format : {format_sortie}...")
    
    fichier_sortie_base = pdf_path.rsplit(".", 1)[0] + "_propre"
    
    if format_sortie == "markdown":
        contenu = rendre_markdown(doc)
        fichier_sortie = f"{fichier_sortie_base}.md"
        with open(fichier_sortie, "w", encoding="utf-8") as f:
            f.write(contenu)
            
    elif format_sortie == "html":
        contenu = rendre_html(doc)
        fichier_sortie = f"{fichier_sortie_base}.html"
        with open(fichier_sortie, "w", encoding="utf-8") as f:
            f.write(contenu)
            
    elif format_sortie == "pdf":
        # 1. On génère d'abord le HTML en mémoire
        contenu_html = rendre_html(doc)
        fichier_sortie = f"{fichier_sortie_base}.pdf"
        
        # 2. On utilise WeasyPrint pour compiler le HTML en un vrai fichier PDF binaire
        import weasyprint
        print("   ↳ Compilation du HTML en PDF binaire...")
        weasyprint.HTML(string=contenu_html).write_pdf(fichier_sortie)
        
    print(f"💾 [FIN] Fichier final écrit avec succès : {fichier_sortie}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pipeline complet de nettoyage de PDF")
    parser.add_argument("pdf", help="Chemin du PDF à traiter")
    # Ajout de "pdf" dans les choix possibles
    parser.add_argument("--format", choices=["html", "markdown", "pdf"], default="html", help="Format du livrable")
    args = parser.parse_args()
    
    executer_pipeline(args.pdf, args.format)