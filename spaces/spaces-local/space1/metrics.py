"""
metrics.py — Extraction et calcul des scores bruts à partir du PDF.
Ce module ne prend aucune décision métier, il quantifie les signaux.
"""

import re
from pathlib import Path
import pdfplumber

SUSPECT_PATTERN = re.compile(r"[\ufffd\x00-\x08\x0b\x0c\x0e-\x1f]")
TOKEN_PATTERN = re.compile(r"\w+", re.UNICODE)


def chiffre_dans_mot(tok):
    return any(c.isdigit() for c in tok) and any(c.isalpha() for c in tok)


def casse_irreguliere(tok):
    return any(tok[i - 1].islower() and tok[i].isupper() for i in range(1, len(tok)))


def taux_tokens_suspects(texte):
    tokens = TOKEN_PATTERN.findall(texte)
    if not tokens:
        return None
    suspects = [t for t in tokens if len(t) >= 2 and (chiffre_dans_mot(t) or casse_irreguliere(t))]
    return len(suspects) / len(tokens)


def taux_caracteres_suspects(texte):
    if not texte:
        return None
    return len(SUSPECT_PATTERN.findall(texte)) / len(texte)


def couverture_image_max(page_plumber):
    surface_page = page_plumber.width * page_plumber.height
    couverture = 0.0
    for img in page_plumber.images:
        largeur = img["x1"] - img["x0"]
        hauteur = img["bottom"] - img["top"]
        couverture = max(couverture, (largeur * hauteur) / surface_page)
    return couverture


def ordre_lecture_divergence(page_plumber):
    t1 = page_plumber.extract_text() or ""
    t2 = page_plumber.extract_text(layout=True) or ""
    m1 = set(TOKEN_PATTERN.findall(t1.lower()))
    m2 = set(TOKEN_PATTERN.findall(t2.lower()))
    if not m1 or not m2:
        return 0.0
    union = m1 | m2
    inter = m1 & m2
    return 1 - (len(inter) / len(union)) if union else 0.0


def extraire_metriques_brutes(pdf_path, page_index=0):
    """Ouvre le PDF et extrait les indicateurs physiques et textuels bruts."""
    with pdfplumber.open(pdf_path) as pdf:
        page_plumber = pdf.pages[page_index]
        texte_natif = page_plumber.extract_text() or ""
        
        a_texte = len(texte_natif.strip()) > 20
        couverture_image = couverture_image_max(page_plumber)
        images_presentes = len(page_plumber.images) > 0
        divergence_ordre = ordre_lecture_divergence(page_plumber) if a_texte else 0.0
        
        nb_segments_tableau = len(page_plumber.lines) + len(page_plumber.rects)
        tableaux_extraits = page_plumber.extract_tables()
        nb_cellules = sum(len(t) * len(t[0]) for t in tableaux_extraits if t and t[0])
        
    return {
        "fichier": Path(pdf_path).name,
        "texte_natif": texte_natif,
        "a_texte": a_texte,
        "couverture_image": couverture_image,
        "images_presentes": images_presentes,
        "divergence_ordre": divergence_ordre,
        "nb_segments_tableau": nb_segments_tableau,
        "nb_cellules": nb_cellules
    }