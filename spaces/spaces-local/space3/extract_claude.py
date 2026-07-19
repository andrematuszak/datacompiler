"""
extract.py — Extrait les données d'un PDF pour initialiser l'objet Document.
Répartit les tâches de façon optimale entre PyMuPDF et pdfplumber.

CORRECTIFS apportés à la version précédente (voir session) :
1. Indexation bloc/ligne : remplacée par enumerate() sur les blocs/lignes
   RÉELS de page_dict, au lieu d'un compteur manuel qui sautait son
   incrément sur les blocs image (via `continue` avant `block_idx += 1`).
   Confirmé sur la doc PyMuPDF : la numérotation block_no de get_text("words")
   compte les blocs image au même titre que le texte -- donc le compteur
   manuel se désynchronisait dès qu'une page contenait une image avant ou
   entre des blocs de texte (le cas de test1.pdf, 4 images), et les mots des
   blocs suivants disparaissaient silencieusement du filtre.
2. get_text("words") hoisté HORS de la boucle par ligne (il était rappelé à
   chaque ligne, donc autant de fois que de lignes sur la page -- coûteux et
   inutile, un seul appel par page suffit).
3. Extraction de native.chars retirée : get_text("dict") ne fournit PAS de
   clé "chars" dans les spans (seulement "text", une chaîne) -- confirmé sur
   la doc PyMuPDF, ça n'existe qu'en mode "rawdict". Le code précédent
   produisait donc toujours une liste vide, silencieusement. À réactiver
   plus tard via get_text("rawdict") si le niveau caractère devient
   nécessaire (coût : rawdict est significativement plus lent que dict).

NOTE HONNÊTE : je n'ai pas pu exécuter ce fichier moi-même (PyMuPDF n'est
pas installé dans mon environnement, pas d'accès réseau pour l'installer).
Les corrections ci-dessus sont établies par lecture de la documentation
officielle PyMuPDF, pas par test réel -- à vérifier de ton côté en premier.
"""

import sys
import argparse
from pathlib import Path
import fitz          # PyMuPDF
import pdfplumber

from document import (
    Document, Page, Word, Font, BBox,
    ImageElement, TableElement, GraphicVector
)


def _convertir_couleur(srgb_int):
    """Convertit l'entier sRGB de PyMuPDF en couleur hexadécimale CSS (#RRGGBB)."""
    if srgb_int is None:
        return "#000000"
    r = (srgb_int >> 16) & 255
    g = (srgb_int >> 8) & 255
    b = srgb_int & 255
    return f"#{r:02x}{g:02x}{b:02x}"


def extraire(pdf_path: str) -> Document:
    doc_obj = Document()

    doc_fitz = fitz.open(pdf_path)
    pdf_plumb = pdfplumber.open(pdf_path)

    # --- A. Métadonnées globales (PyMuPDF) ---
    meta_fitz = doc_fitz.metadata
    doc_obj.metadata.filename = Path(pdf_path).name
    doc_obj.metadata.page_count = len(doc_fitz)
    doc_obj.metadata.producer = meta_fitz.get("producer", "")
    doc_obj.metadata.creator = meta_fitz.get("creator", "")
    doc_obj.metadata.creation_date = meta_fitz.get("creationDate", "")
    doc_obj.metadata.modification_date = meta_fitz.get("modDate", "")
    doc_obj.metadata.pdf_version = doc_fitz.pdf_version
    doc_obj.metadata.encrypted = doc_fitz.is_encrypted

    word_global_id = 1
    image_global_id = 1
    table_global_id = 1

    for idx in range(len(doc_fitz)):
        page_fitz = doc_fitz[idx]
        page_plumb = pdf_plumb.pages[idx]

        page_obj = Page(
            number=idx + 1,
            width=float(page_fitz.rect.width),
            height=float(page_fitz.rect.height),
            rotation=float(page_fitz.rotation)
        )

        # ---------------------------------------------------------------
        # MOTEUR 1 : PyMuPDF (texte, polices, mots)
        # ---------------------------------------------------------------
        page_dict = page_fitz.get_text("dict")
        # un seul appel par page (au lieu d'un appel par ligne) --
        # words_fitz est indexé (block_no, line_no, word_no) selon la MÊME
        # numérotation que page_dict (mêmes flags par défaut pour les deux
        # appels), donc enumerate() ci-dessous doit compter EXACTEMENT les
        # mêmes blocs/lignes, images comprises.
        words_fitz = page_fitz.get_text("words")
        font_map = {}

        for block_idx, b in enumerate(page_dict.get("blocks", [])):
            if b.get("type") != 0:
                continue  # bloc image : on ignore le contenu texte, mais
                          # block_idx reste correctement incrémenté par
                          # enumerate() -- c'est ça qui corrige le bug

            for line_idx, l in enumerate(b.get("lines", [])):
                for s in l.get("spans", []):
                    font_name = s.get("font", "Unknown")
                    font_size = float(s.get("size", 0.0))
                    bold = bool(s.get("flags", 0) & 4)
                    italic = bool(s.get("flags", 0) & 2)
                    color_hex = _convertir_couleur(s.get("color"))

                    if font_name not in font_map:
                        font_map[font_name] = set()
                    font_map[font_name].add(round(font_size, 1))

                # attributs de police du DERNIER span de la ligne -- même
                # logique que la version précédente (une ligne peut mélanger
                # plusieurs spans/polices ; limite connue, pas corrigée ici,
                # à traiter plus tard si un mot doit porter SA police à lui
                # plutôt que celle du dernier span croisé)
                for w in words_fitz:
                    if w[5] == block_idx and w[6] == line_idx:
                        word_bbox = BBox(w[0], w[1], w[2], w[3])
                        page_obj.native.words.append(Word(
                            id=word_global_id,
                            text=w[4],
                            bbox=word_bbox,
                            block=int(w[5]),
                            line=int(w[6]),
                            word=int(w[7]),
                            font=font_name,
                            font_size=font_size,
                            bold=bold,
                            italic=italic,
                            color=color_hex,
                            rotation=float(page_fitz.rotation)
                        ))
                        word_global_id += 1

        for name, sizes in font_map.items():
            page_obj.native.fonts.append(Font(name=name, sizes=sorted(list(sizes))))

        # ---------------------------------------------------------------
        # MOTEUR 2 : pdfplumber (images, tableaux, vecteurs)
        # ---------------------------------------------------------------
        for img in page_plumb.images:
            img_bbox = BBox(float(img["x0"]), float(img["top"]), float(img["x1"]), float(img["bottom"]))
            page_obj.graphics.images.append(ImageElement(
                id=image_global_id, bbox=img_bbox,
                width=int(img.get("width", 0)), height=int(img.get("height", 0))
            ))
            image_global_id += 1

        for t in page_plumb.find_tables():
            t_bbox = BBox(float(t.bbox[0]), float(t.bbox[1]), float(t.bbox[2]), float(t.bbox[3]))
            page_obj.graphics.tables.append(TableElement(
                id=table_global_id, bbox=t_bbox, source="pdfplumber", rows=t.extract()
            ))
            table_global_id += 1

        for line in page_plumb.lines:
            v_bbox = BBox(float(line["x0"]), float(line["top"]), float(line["x1"]), float(line["bottom"]))
            page_obj.graphics.lines.append(GraphicVector(bbox=v_bbox))

        for rect in page_plumb.rects:
            v_bbox = BBox(float(rect["x0"]), float(rect["top"]), float(rect["x1"]), float(rect["bottom"]))
            page_obj.graphics.rects.append(GraphicVector(bbox=v_bbox))

        for curve in page_plumb.curves:
            v_bbox = BBox(float(curve["x0"]), float(curve["top"]), float(curve["x1"]), float(curve["bottom"]))
            page_obj.graphics.curves.append(GraphicVector(bbox=v_bbox))

        doc_obj.pages.append(page_obj)

    doc_fitz.close()
    pdf_plumb.close()
    return doc_obj


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extraction double-moteur d'un PDF vers Document Object")
    parser.add_argument("pdf", help="Chemin du fichier PDF")
    parser.add_argument("-o", "--output", default=None, help="Chemin du JSON de sortie (optionnel)")
    args = parser.parse_args()

    print(f"⌛ Extraction hybride en cours pour : {args.pdf}")
    doc = extraire(args.pdf)

    chemin_json = args.output or (args.pdf.rsplit(".", 1)[0] + ".document.json")
    doc.save(chemin_json)

    print(f"✅ Extraction terminée avec succès !")
    print(f"   ↳ {doc.metadata.page_count} page(s) extraite(s).")
    print(f"   ↳ Fichier JSON généré pour vérification : {chemin_json}")
