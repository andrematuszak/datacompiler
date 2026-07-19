"""
extract.py — Construit la grille NATIVE d'un PDF (Document.native) : mots
avec bbox/police/taille, images, tableaux, et pour chaque page le diagnostic
qui dira à app.py/pipeline.py si un enrichissement (ocr.py) est nécessaire.

Ne fait AUCUN choix de reconstruction ici -- extract.py se contente
d'extraire et de poser un diagnostic, resolve.py (plus tard) arbitrera.

Usage : python extract.py fichier.pdf [-o document.json]
"""

import sys
import argparse

import pdfplumber

from document import Document, Page, Word, Image, Table
from diagnostic import calculer_scores, decision_mistral


def _extraire_images(page_plumber):
    surface_page = page_plumber.width * page_plumber.height
    images = []
    for img in page_plumber.images:
        bbox = [img["x0"], img["top"], img["x1"], img["bottom"]]
        largeur = img["x1"] - img["x0"]
        hauteur = img["bottom"] - img["top"]
        ratio = (largeur * hauteur) / surface_page if surface_page else 0.0
        images.append(Image(bbox=bbox, coverage_ratio=round(ratio, 4)))
    return images


def _extraire_tableaux(page_plumber):
    tables = []
    for t in page_plumber.find_tables():
        tables.append(Table(bbox=list(t.bbox), rows=t.extract()))
    return tables


def _extraire_mots(page_plumber):
    bruts = page_plumber.extract_words(extra_attrs=["fontname", "size"])
    return [
        Word(
            text=w["text"],
            bbox=[round(w["x0"], 2), round(w["top"], 2), round(w["x1"], 2), round(w["bottom"], 2)],
            fontname=w.get("fontname"),
            size=round(w["size"], 2) if w.get("size") is not None else None,
            source="native",
        )
        for w in bruts
    ]


def extraire(pdf_path):
    """Construit un Document avec sa grille native complète, page par page."""
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for index, page_plumber in enumerate(pdf.pages):
            mots = _extraire_mots(page_plumber)
            images = _extraire_images(page_plumber)
            tables = _extraire_tableaux(page_plumber)
            polices = sorted({m.fontname for m in mots if m.fontname})

            scores = calculer_scores(pdf_path, page_index=index)
            appel_mistral, raison = decision_mistral(scores)

            page = Page(
                page_number=index + 1,
                width=page_plumber.width,
                height=page_plumber.height,
                words=mots,
                images=images,
                tables=tables,
                fonts=polices,
                metadata={
                    "scores": {k: v for k, v in scores.items() if not k.startswith("_")},
                    "needs_enrichment": appel_mistral,
                    "enrichment_reason": raison,
                },
            )
            pages.append(page)

    return Document(source_path=str(pdf_path), native=pages)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extraction native d'un PDF vers document.json")
    parser.add_argument("pdf", help="Chemin du PDF à traiter")
    parser.add_argument("-o", "--output", default=None, help="Chemin de sortie (défaut : <nom>.document.json)")
    args = parser.parse_args()

    doc = extraire(args.pdf)
    sortie = args.output or (args.pdf.rsplit(".", 1)[0] + ".document.json")
    doc.save(sortie)

    for page in doc.native:
        print(f"Page {page.page_number} : {len(page.words)} mots, {len(page.images)} image(s), "
              f"{len(page.tables)} tableau(x) -- enrichissement nécessaire : "
              f"{page.metadata['needs_enrichment']} ({page.metadata['enrichment_reason']})")
    print(f"\nÉcrit : {sortie}")
