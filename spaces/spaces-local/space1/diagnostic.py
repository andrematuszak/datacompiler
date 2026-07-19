"""
diagnostic.py — Calcule un score de confiance par SOURCE d'information
disponible pour reconstruire une page de PDF, plutôt qu'un verdict
catégoriel unique.

    {
      "native_text": 0.95,      # confiance dans le texte extrait nativement
      "native_geometry": 1.00,  # confiance dans les positions/bbox natives
      "embedded_ocr": 0.35,     # OCR tiers déjà appliqué en amont, si détecté
      "mistral": null,          # rempli après appel API (score moyen de la page)
      "images": true            # présence d'au moins une image sur la page
    }

Ce module réutilise les signaux déjà validés sur des cas réels (test1, test5,
test6, test7, test21) : présence de texte natif, taux de caractères suspects,
structure de tokens anormale, OCR pré-existant (image pleine page + texte),
instabilité de l'ordre de lecture. Voir chaque fonction pour le détail.

Usage : python diagnostic.py fichier1.pdf [fichier2.pdf ...]
"""

import sys
import json
import re
from pathlib import Path

import pdfplumber

SUSPECT_PATTERN = re.compile(r"[\ufffd\x00-\x08\x0b\x0c\x0e-\x1f]")
TOKEN_PATTERN = re.compile(r"\w+", re.UNICODE)


def _chiffre_dans_mot(tok):
    return any(c.isdigit() for c in tok) and any(c.isalpha() for c in tok)


def _casse_irreguliere(tok):
    return any(tok[i - 1].islower() and tok[i].isupper() for i in range(1, len(tok)))


def _taux_tokens_suspects(texte):
    tokens = TOKEN_PATTERN.findall(texte)
    if not tokens:
        return None
    suspects = [t for t in tokens if len(t) >= 2 and (_chiffre_dans_mot(t) or _casse_irreguliere(t))]
    return len(suspects) / len(tokens)


def _taux_caracteres_suspects(texte):
    if not texte:
        return None
    return len(SUSPECT_PATTERN.findall(texte)) / len(texte)


def _couverture_image_max(page_plumber):
    surface_page = page_plumber.width * page_plumber.height
    couverture = 0.0
    for img in page_plumber.images:
        largeur = img["x1"] - img["x0"]
        hauteur = img["bottom"] - img["top"]
        couverture = max(couverture, (largeur * hauteur) / surface_page)
    return couverture


def _ordre_lecture_divergence(page_plumber):
    t1 = page_plumber.extract_text() or ""
    t2 = page_plumber.extract_text(layout=True) or ""
    m1 = set(TOKEN_PATTERN.findall(t1.lower()))
    m2 = set(TOKEN_PATTERN.findall(t2.lower()))
    if not m1 or not m2:
        return 0.0
    union = m1 | m2
    inter = m1 & m2
    return 1 - (len(inter) / len(union)) if union else 0.0


def calculer_scores(pdf_path, page_index=0):
    """Calcule le JSON de scores pour une page. Chaque score est dans [0, 1]
    ou None quand la question ne se pose pas (ex. native_geometry sur une
    page 100% image, où il n'y a tout simplement pas de géométrie native)."""
    with pdfplumber.open(pdf_path) as pdf:
        page_plumber = pdf.pages[page_index]
        texte_natif = page_plumber.extract_text() or ""
        a_texte = len(texte_natif.strip()) > 20
        couverture_image = _couverture_image_max(page_plumber)
        images_presentes = len(page_plumber.images) > 0
        divergence_ordre = _ordre_lecture_divergence(page_plumber) if a_texte else 0.0
        nb_segments_tableau = len(page_plumber.lines) + len(page_plumber.rects)
        tableaux_extraits = page_plumber.extract_tables()
        nb_cellules = sum(len(t) * len(t[0]) for t in tableaux_extraits if t and t[0])
        tableau_perdu = nb_segments_tableau > 10 and nb_cellules == 0

    pre_ocr_probable = couverture_image >= 0.85 and a_texte

    # --- native_text : confiance dans le CONTENU du texte natif ---
    if not a_texte:
        native_text = 0.0  # pas de texte natif du tout -> Mistral obligatoire
    else:
        taux_suspect = _taux_caracteres_suspects(texte_natif) or 0.0
        taux_tokens = _taux_tokens_suspects(texte_natif) or 0.0
        native_text = max(0.0, 1.0 - taux_suspect * 5 - taux_tokens * 3)
        # un OCR tiers déjà appliqué en amont rend le texte natif non fiable
        # PAR PRINCIPE, même si aucun caractère individuel ne paraît suspect
        # (cas test7 : 0% de caractères suspects, pourtant "Vergteich" pour
        # "Vergleich") -> pénalité forte indépendante des autres signaux
        if pre_ocr_probable:
            native_text = min(native_text, 0.4)

    # --- native_geometry : confiance dans les POSITIONS natives ---
    if not a_texte:
        native_geometry = None  # la question ne se pose pas : pas de texte -> pas de bbox de texte
    else:
        native_geometry = 1.0
        native_geometry -= divergence_ordre  # colonnes mélangées / ordre instable
        if tableau_perdu:
            native_geometry -= 0.2
        native_geometry = max(0.0, native_geometry)

    # --- embedded_ocr : un OCR tiers est-il déjà présent, et de quelle qualité ? ---
    if not pre_ocr_probable:
        embedded_ocr = None  # signal non applicable, pas de couche OCR tierce détectée
    else:
        # même formule que native_text mais sans re-pénaliser pour pre_ocr
        # (on VEUT ici mesurer la qualité de cet OCR tiers, pas juste sa présence)
        taux_suspect = _taux_caracteres_suspects(texte_natif) or 0.0
        taux_tokens = _taux_tokens_suspects(texte_natif) or 0.0
        embedded_ocr = max(0.0, 1.0 - taux_suspect * 5 - taux_tokens * 3)

    return {
        "fichier": Path(pdf_path).name,
        "native_text": round(native_text, 3) if native_text is not None else None,
        "native_geometry": round(native_geometry, 3) if native_geometry is not None else None,
        "embedded_ocr": round(embedded_ocr, 3) if embedded_ocr is not None else None,
        "mistral": None,  # rempli après appel API (mistral_client.py)
        "images": images_presentes,
        # détail utile pour déboguer/comprendre la décision, pas juste le verdict
        "_detail": {
            "a_texte_natif": a_texte,
            "longueur_texte": len(texte_natif),
            "couverture_image_max": round(couverture_image, 3),
            "pre_ocr_probable": pre_ocr_probable,
            "divergence_ordre_lecture": round(divergence_ordre, 3),
            "tableau_probablement_perdu": tableau_perdu,
        },
    }


def decision_mistral(scores, seuil_bas=0.6, seuil_haut=0.9):
    """Faut-il appeler Mistral ? Sert à arbitrer la dépense (temps/argent),
    pas à décider de la stratégie de reconstruction -- une fois qu'on a
    décidé d'appeler Mistral, la fusion se comporte identiquement quelle que
    soit la raison du déclenchement (scan, OCR tiers, texte ambigu)."""
    nt = scores["native_text"]
    if nt is None or nt < seuil_bas:
        return True, "native_text trop faible ou absent"
    if nt < seuil_haut:
        return True, "native_text ambigu -- comparaison native/Mistral nécessaire"
    if scores["embedded_ocr"] is not None:
        return True, "OCR tiers détecté -- fiabilité inconnue, vérification nécessaire"
    return False, "native_text suffisamment fiable -- Mistral non nécessaire (économie)"


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage : python diagnostic.py fichier1.pdf [fichier2.pdf ...]")
        sys.exit(1)

    for fichier in sys.argv[1:]:
        scores = calculer_scores(fichier)
        appel, raison = decision_mistral(scores)
        print(f"\n=== {scores['fichier']} ===")
        print(json.dumps({k: v for k, v in scores.items() if not k.startswith("_")}, indent=2, ensure_ascii=False))
        print(f"Appeler Mistral ? {appel} ({raison})")
        print(f"Détail : {scores['_detail']}")
