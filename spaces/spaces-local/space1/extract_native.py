"""
extract_native.py — Extraction hybride unifiée.
- PyMuPDF extrait les mots et leurs coordonnées au pixel près.
- pdfplumber extrait les métadonnées géométriques des tableaux, lignes et images.
"""

import sys
import json
from pathlib import Path
import fitz          # PyMuPDF
import pdfplumber

def extraire_hybride_native(pdf_path):
    donnees_extraction = {
        "fichier": Path(pdf_path).name,
        "pages": []
    }
    
    # 1. Ouverture simultanée avec les deux outils
    doc_fitz = fitz.open(pdf_path)
    pdf_plumber = pdfplumber.open(pdf_path)
    
    for idx_page in range(len(doc_fitz)):
        page_fitz = doc_fitz[idx_page]
        page_plumber = pdf_plumber.pages[idx_page]
        
        # --- A. Extraction des Mots par PyMuPDF (Ultra Rapide & Précis) ---
        # extractWORDS() renvoie des tuples : (x0, y0, x1, y1, "mot", block_no, line_no, word_no)
        mots_fitz = page_fitz.get_text("words")
        liste_tokens = []
        
        for m in mots_fitz:
            token = {
                "texte": m[4],
                "x0": round(m[0], 2),
                "y0": round(m[1], 2),
                "x1": round(m[2], 2),
                "y1": round(m[3], 2),
                "block_idx": m[5],
                "line_idx": m[6]
            }
            liste_tokens.append(token)
            
        # --- B. Extraction des structures graphiques par pdfplumber ---
        # On extrait les frontières physiques des tableaux (lignes vectorielles)
        lignes_vectorielles = []
        for l in page_plumber.lines:
            lignes_vectorielles.append({
                "x0": round(l["x0"], 2),
                "y0": round(l["top"], 2),
                "x1": round(l["x1"], 2),
                "y1": round(l["bottom"], 2)
            })
            
        rectangles = []
        for r in page_plumber.rects:
            rectangles.append({
                "x0": round(r["x0"], 2),
                "y0": round(r["top"], 2),
                "x1": round(r["x1"], 2),
                "y1": round(r["bottom"], 2)
            })
            
        # Obtenir les zones d'images pour savoir où se situent les masques visuels
        zones_images = []
        for img in page_plumber.images:
            zones_images.append({
                "x0": round(img["x0"], 2),
                "y0": round(img["top"], 2),
                "x1": round(img["x1"], 2),
                "y1": round(img["bottom"], 2)
            })

        # --- C. Unification dans le rapport de la page ---
        donnees_page = {
            "page_index": idx_page,
            "largeur": round(page_plumber.width, 2),
            "hauteur": round(page_plumber.height, 2),
            "structures": {
                "nombre_tokens": len(liste_tokens),
                "nombre_lignes": len(lignes_vectorielles),
                "nombre_rectangles": len(rectangles),
                "nombre_images": len(zones_images)
            },
            "tokens": liste_tokens,
            "geometrie_graphique": {
                "lignes": lignes_vectorielles,
                "rectangles": rectangles,
                "images": zones_images
            }
        }
        donnees_extraction["pages"].append(donnees_page)
        
    # Fermeture des flux
    pdf_plumber.close()
    doc_fitz.close()
    
    return donnees_extraction

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage : python extract_native.py mon_fichier.pdf")
        sys.exit(1)
        
    fichier_cible = sys.argv[1]
    
    try:
        print(f"Extraction hybride en cours pour : {fichier_cible}...")
        resultat = extraire_hybride_native(fichier_cible)
        
        nom_sortie = Path(fichier_cible).stem + "_native_hybrid.json"
        with open(nom_sortie, "w", encoding="utf-8") as f:
            json.dump(resultat, f, indent=2, ensure_ascii=False)
            
        print(f"Succès ! Fichier structurel généré : {nom_sortie}")
        
    except Exception as e:
        print(f"Erreur lors de l'extraction : {e}")