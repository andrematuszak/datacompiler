"""
diagnostic.py — Interprétation des métriques et prise de décision (Routing).
Génère le format JSON de contrôle et le verdict d'appel à l'OCR.
"""

import sys
import json
from metrics import extraire_metriques_brutes, taux_caracteres_suspects, taux_tokens_suspects


def calculer_scores(pdf_path, page_index=0):
    """Calcule le JSON de scores en s'appuyant sur les métriques brutes."""
    # 1. Récupération des données brutes
    m = extraire_metriques_brutes(pdf_path, page_index)
    texte_natif = m["texte_natif"]
    a_texte = m["a_texte"]
    
    pre_ocr_probable = m["couverture_image"] >= 0.85 and a_texte
    tableau_perdu = m["nb_segments_tableau"] > 10 and m["nb_cellules"] == 0

    # --- native_text : confiance dans le CONTENU du texte natif ---
    if not a_texte:
        native_text = 0.0
    else:
        taux_suspect = taux_caracteres_suspects(texte_natif) or 0.0
        taux_tokens = taux_tokens_suspects(texte_natif) or 0.0
        native_text = max(0.0, 1.0 - taux_suspect * 5 - taux_tokens * 3)
        if pre_ocr_probable:
            native_text = min(native_text, 0.4)

    # --- native_geometry : confiance dans les POSITIONS natives ---
    if not a_texte:
        native_geometry = None
    else:
        native_geometry = 1.0
        native_geometry -= m["divergence_ordre"]
        if tableau_perdu:
            native_geometry -= 0.2
        native_geometry = max(0.0, native_geometry)

    # --- embedded_ocr : qualité de l'OCR tiers déjà présent ---
    if not pre_ocr_probable:
        embedded_ocr = None
    else:
        taux_suspect = taux_caracteres_suspects(texte_natif) or 0.0
        taux_tokens = taux_tokens_suspects(texte_natif) or 0.0
        embedded_ocr = max(0.0, 1.0 - taux_suspect * 5 - taux_tokens * 3)

    return {
        "fichier": m["fichier"],
        "native_text": round(native_text, 3) if native_text is not None else None,
        "native_geometry": round(native_geometry, 3) if native_geometry is not None else None,
        "embedded_ocr": round(embedded_ocr, 3) if embedded_ocr is not None else None,
        "mistral": None,
        "images": m["images_presentes"],
        "_detail": {
            "a_texte_natif": a_texte,
            "longueur_texte": len(texte_natif),
            "couverture_image_max": round(m["couverture_image"], 3),
            "pre_ocr_probable": pre_ocr_probable,
            "divergence_ordre_lecture": round(m["divergence_ordre"], 3),
            "tableau_probablement_perdu": tableau_perdu,
        },
    }


def decision_mistral(scores, seuil_bas=0.6, seuil_haut=0.9):
    """Arbitrage sur la nécessité d'appeler l'OCR visuel."""
    nt = scores["native_text"]
    if nt is None or nt < seuil_bas:
        return True, "native_text trop faible ou absent"
    if nt < seuil_haut:
        return True, "native_text ambigu -- comparaison native/Mistral nécessaire"
    if scores["embedded_ocr"] is not None:
        return True, "OCR tiers détecté -- fiabilité inconnue, vérification nécessaire"
    return False, "native_text sufficiently fiable -- Mistral non nécessaire (économie)"


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