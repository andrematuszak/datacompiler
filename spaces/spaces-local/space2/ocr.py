"""
ocr.py — Appelle Mistral OCR sur un PDF et traduit sa réponse vers le schéma
Document commun (document.py), pour que resolve.py puisse comparer native et
ocr sans se soucier du format brut de l'API.

Point important, déjà vérifié sur ce projet : Mistral ne fournit de bbox
qu'au niveau BLOC (paragraphe), jamais au niveau mot. Donc côté ocr :
  - Page.blocks porte bbox + contenu texte (granularité paragraphe)
  - Page.words porte le texte + la confiance par mot, mais bbox=None
    (l'information n'existe pas dans la réponse de l'API)
resolve.py devra donc aligner le texte de blocks/words avec les mots natifs
par comparaison textuelle (voir fusion.py de la session précédente), pas par
coordonnées, pour les zones où on n'a que la granularité bloc côté OCR.

Usage : python ocr.py fichier.pdf --api-key sk-... [-o ocr.json]
(clé API aussi lisible depuis la variable d'environnement MISTRAL_API_KEY)
"""

import os
import sys
import json
import base64
import argparse

from document import Document, Page, Word, Block


def _encoder_base64(pdf_path):
    with open(pdf_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _page_depuis_reponse(page_data, page_number):
    """Traduit UNE page de la réponse Mistral (objet SDK) vers notre Page.
    Isolé de l'appel réseau pour être testable avec un objet fabriqué --
    voir _page_depuis_reponse_test ci-dessous."""
    dimensions = getattr(page_data, "dimensions", None)
    largeur = getattr(dimensions, "width", None) if dimensions else None
    hauteur = getattr(dimensions, "height", None) if dimensions else None

    # --- mots : texte + confiance, PAS de bbox (absente de l'API) ---
    mots = []
    conf_scores = getattr(page_data, "confidence_scores", None)
    mots_confiance = getattr(conf_scores, "word_confidence_scores", None) if conf_scores else None
    if mots_confiance:
        for w in mots_confiance:
            mots.append(Word(text=w.text, bbox=None, confidence=w.confidence, source="mistral"))

    # --- blocs : bbox + contenu, granularité paragraphe ---
    blocs = []
    if getattr(page_data, "blocks", None):
        for b in page_data.blocks:
            blocs.append(Block(
                bbox=[b.top_left_x, b.top_left_y, b.bottom_right_x, b.bottom_right_y],
                type=b.type,
                content=b.content or "",
            ))

    confiance_moyenne = (
        sum(w.confidence for w in mots) / len(mots) if mots else None
    )

    return Page(
        page_number=page_number,
        width=largeur or 0,
        height=hauteur or 0,
        words=mots,
        blocks=blocs,
        metadata={
            "confiance_moyenne": round(confiance_moyenne, 4) if confiance_moyenne is not None else None,
            "nb_mots": len(mots),
            "nb_blocs": len(blocs),
        },
    )


def ocraliser(pdf_path, api_key):
    """Appelle l'API Mistral OCR sur le PDF entier et retourne list[Page]."""
    from mistralai import Mistral  # import ici : évite la dépendance quand ocr.py n'est pas utilisé

    client = Mistral(api_key=api_key)
    base64_data = _encoder_base64(pdf_path)

    reponse = client.ocr.process(
        model="mistral-ocr-latest",
        document={
            "type": "document_url",
            "document_url": f"data:application/pdf;base64,{base64_data}",
        },
        include_blocks=True,
        confidence_scores_granularity="word",
    )

    if not reponse.pages:
        raise RuntimeError("L'API Mistral n'a renvoyé aucune page.")

    return [_page_depuis_reponse(p, i + 1) for i, p in enumerate(reponse.pages)]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Appel Mistral OCR -> ocr.json (schéma Document commun)")
    parser.add_argument("pdf", help="Chemin du PDF à traiter")
    parser.add_argument("--api-key", default=None, help="Clé API Mistral (sinon variable MISTRAL_API_KEY)")
    parser.add_argument("-o", "--output", default=None, help="Chemin de sortie (défaut : <nom>.ocr.json)")
    args = parser.parse_args()

    api_key = args.api_key or os.getenv("MISTRAL_API_KEY")
    if not api_key:
        print("Erreur : clé API Mistral introuvable (--api-key ou variable MISTRAL_API_KEY).")
        sys.exit(1)

    pages = ocraliser(args.pdf, api_key)
    doc = Document(source_path=str(args.pdf), ocr=pages)

    sortie = args.output or (args.pdf.rsplit(".", 1)[0] + ".ocr.json")
    doc.save(sortie)

    for page in pages:
        print(f"Page {page.page_number} : {len(page.words)} mots (confiance moyenne "
              f"{page.metadata['confiance_moyenne']}), {len(page.blocks)} bloc(s)")
    print(f"\nÉcrit : {sortie}")
