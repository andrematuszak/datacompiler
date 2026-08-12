#!/usr/bin/env python3
"""Diagnostic : affiche l'ordre réel des mots sur la page 2 après ordonner()."""

import sys
import json
from pathlib import Path

# Ajouter le chemin du projet
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from datacompiler.model.document import Document
from datacompiler.compile import reading_order as ro


def charger_document(json_path):
    """Charge un document depuis un fichier JSON."""
    doc = Document()
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        # Importer les pages (à adapter selon ton modèle)
        for page_data in data.get('pages', []):
            page = doc.add_page()
            page.number = page_data.get('number', 0)
            # Importer les mots natifs
            for word_data in page_data.get('native', {}).get('words', []):
                mot = page.add_word(
                    text=word_data.get('text', ''),
                    bbox=word_data.get('bbox', [0, 0, 0, 0]),
                    source=word_data.get('source', 'native')
                )
    return doc


def diagnostiquer_ordre(page):
    """Affiche l'ordre des mots sur une page après ordonner()."""
    print(f"\n=== Page {page.number} : {len(page.native.words)} mots natifs ===")
    
    # Appliquer reading_order
    mots_ordonnes = ro.ordonner(page)
    
    # Trouver l'index de "Détail"
    index_detail = None
    for i, mot in enumerate(mots_ordonnes):
        if "Détail" in mot.text or "Salaires" in mot.text:
            index_detail = i
            break
    
    if index_detail is None:
        print("  ❌ 'Détail' ou 'Salaires' non trouvé dans la page !")
        return
    
    # Afficher les 20 mots autour
    debut = max(0, index_detail - 10)
    fin = min(len(mots_ordonnes), index_detail + 20)
    
    print(f"\n  Mots autour de 'Détail' (index {index_detail}) :")
    print("  " + "-" * 60)
    for i in range(debut, fin):
        mot = mots_ordonnes[i]
        prefix = ">>>" if i == index_detail else "   "
        bbox = mot.bbox
        print(f"  {prefix} {i:3d} : {mot.text:20s}  ({bbox.x0:6.1f}, {bbox.y0:6.1f})  source={mot.source}")
    print("  " + "-" * 60)


if __name__ == "__main__":
    # Utiliser le fichier JSON généré par le pipeline
    json_path = Path("test-impots-revenu.document.json")
    if not json_path.exists():
        print(f"❌ Fichier JSON introuvable : {json_path}")
        print("   Exécute d'abord le pipeline avec --no-json pour le générer.")
        sys.exit(1)
    
    print(f"📄 Chargement du document : {json_path}")
    doc = Document.load(json_path)  # à adapter selon ta méthode de chargement
    
    # Diagnostiquer la page 2 (index 1)
    if len(doc.pages) > 1:
        diagnostiquer_ordre(doc.pages[1])
    else:
        print("❌ Document trop court (pas de page 2)")