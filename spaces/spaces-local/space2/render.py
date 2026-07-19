"""
render.py — Reconstruit un document lisible à partir d'un Document.

Aujourd'hui (pas encore de resolve.py) : passthrough pur.
  - Si doc.resolved existe (plus tard), on part de là.
  - Sinon, si doc.ocr existe (enrichissement effectué), on rend depuis l'OCR.
  - Sinon, on rend depuis doc.native directement.

Deux formats pour l'instant : markdown (le plus simple, robuste, sans
dépendance) et html (mode "Document Flow" déjà validé en session précédente :
empilement en ordre de lecture, hauteur libre -- pas de position absolue tant
que resolve.py ne fournit pas d'arbitrage sur la fiabilité des bbox).

Usage : python render.py document.json [--format markdown|html] [-o sortie]
"""

import sys
import argparse

from document import Document


def _choisir_source(doc):
    if doc.resolved is not None:
        return doc.resolved, "resolved"
    if doc.ocr is not None:
        return doc.ocr, "ocr"
    if doc.native is not None:
        return doc.native, "native"
    raise ValueError("Document vide : aucune source (native/ocr/resolved) disponible.")


def _grouper_mots_en_lignes(mots, tolerance_y=3):
    """Regroupe une liste de Word (avec bbox) en lignes selon leur position
    verticale, puis trie chaque ligne par x -- reconstruit un ordre de
    lecture raisonnable à partir de mots isolés (cas native, où on a une
    bbox par mot mais pas de bloc pré-formé)."""
    mots_avec_bbox = [w for w in mots if w.bbox]
    mots_tries = sorted(mots_avec_bbox, key=lambda w: (w.bbox[1], w.bbox[0]))

    lignes = []
    ligne_courante = []
    y_courant = None
    for mot in mots_tries:
        y = mot.bbox[1]
        if y_courant is None or abs(y - y_courant) <= tolerance_y:
            ligne_courante.append(mot)
            y_courant = y if y_courant is None else y_courant
        else:
            lignes.append(sorted(ligne_courante, key=lambda w: w.bbox[0]))
            ligne_courante = [mot]
            y_courant = y
    if ligne_courante:
        lignes.append(sorted(ligne_courante, key=lambda w: w.bbox[0]))
    return lignes


def rendre_markdown(doc):
    pages, source = _choisir_source(doc)
    morceaux = [f"<!-- rendu depuis : {source} -->\n"]

    for page in pages:
        morceaux.append(f"\n## Page {page.page_number}\n")
        if page.blocks:
            # granularité bloc disponible (typiquement : ocr) -> un paragraphe par bloc
            for bloc in page.blocks:
                texte = " ".join(bloc.content.split())  # aplati, pas de \n mal placés (cf. session précédente)
                morceaux.append(texte + "\n")
        elif page.words:
            # granularité mot seule (typiquement : native) -> reconstruction par lignes
            lignes = _grouper_mots_en_lignes(page.words)
            for ligne in lignes:
                morceaux.append(" ".join(w.text for w in ligne))
            morceaux.append("")
        else:
            morceaux.append("*(page vide)*\n")

    return "\n".join(morceaux)


def rendre_html(doc, largeur_affichage=700):
    """Mode Document Flow (validé en session précédente) : empilement en
    ordre de lecture, hauteur libre -- pas de position absolue, donc aucun
    risque de chevauchement même si le texte source est corrompu/mal formaté."""
    pages, source = _choisir_source(doc)
    morceaux = [f'<div style="font-family:Arial,sans-serif;max-width:{largeur_affichage}px;margin:auto;">']
    morceaux.append(f'<p style="color:#888;font-size:11px;">rendu depuis : {source}</p>')

    for page in pages:
        morceaux.append(
            f'<h3 style="border-bottom:1px solid #ccc;">Page {page.page_number}</h3>'
        )
        if page.blocks:
            for bloc in page.blocks:
                largeur_page = page.width or 1
                gauche_pct = (bloc.bbox[0] / largeur_page * 100) if bloc.bbox else 0
                largeur_pct = ((bloc.bbox[2] - bloc.bbox[0]) / largeur_page * 100) if bloc.bbox else 100
                texte = (
                    " ".join(bloc.content.split())
                    .replace("<", "&lt;").replace(">", "&gt;")
                )
                morceaux.append(
                    f'<div style="margin-left:{gauche_pct:.1f}%; width:{largeur_pct:.1f}%; '
                    f'margin-top:8px; margin-bottom:8px; font-size:13px; line-height:1.4;" '
                    f'title="{bloc.type}">{texte}</div>'
                )
        elif page.words:
            lignes = _grouper_mots_en_lignes(page.words)
            for ligne in lignes:
                texte = " ".join(w.text for w in ligne).replace("<", "&lt;").replace(">", "&gt;")
                morceaux.append(f'<div style="margin:2px 0; font-size:13px;">{texte}</div>')
        else:
            morceaux.append("<p><em>(page vide)</em></p>")

    morceaux.append("</div>")
    return "\n".join(morceaux)


FORMATS = {
    "markdown": rendre_markdown,
    "html": rendre_html,
}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Rendu d'un Document (JSON) vers markdown/html")
    parser.add_argument("document_json", help="Chemin du document.json (ou .ocr.json) à rendre")
    parser.add_argument("--format", choices=list(FORMATS.keys()), default="markdown")
    parser.add_argument("-o", "--output", default=None, help="Chemin de sortie (défaut : <nom>.<format>)")
    args = parser.parse_args()

    doc = Document.load(args.document_json)
    fonction_rendu = FORMATS[args.format]
    resultat = fonction_rendu(doc)

    extension = {"markdown": "md", "html": "html"}[args.format]
    sortie = args.output or (args.document_json.rsplit(".", 1)[0] + f".{extension}")
    with open(sortie, "w", encoding="utf-8") as f:
        f.write(resultat)

    print(f"Écrit : {sortie}")
