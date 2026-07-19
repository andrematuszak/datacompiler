"""
extract.py — Extrait les données d'un PDF pour initialiser l'objet Document.
Répartit les tâches de façon optimale entre PyMuPDF et pdfplumber.
"""

import sys
import argparse
from pathlib import Path
import fitz          # PyMuPDF
import pdfplumber

from document import (
    Document, Page, Word, Character, Font, BBox, 
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
    
    # 1. Ouverture simultanée avec les deux moteurs
    doc_fitz = fitz.open(pdf_path)
    pdf_plumb = pdfplumber.open(pdf_path)
    
    # --- A. Extraction des Métadonnées Globales (PyMuPDF) ---
    meta_fitz = doc_fitz.metadata
    doc_obj.metadata.filename = Path(pdf_path).name
    doc_obj.metadata.page_count = len(doc_fitz)
    doc_obj.metadata.producer = meta_fitz.get("producer", "")
    doc_obj.metadata.creator = meta_fitz.get("creator", "")
    doc_obj.metadata.creation_date = meta_fitz.get("creationDate", "")
    doc_obj.metadata.modification_date = meta_fitz.get("modDate", "")
    doc_obj.metadata.pdf_version = doc_fitz.pdf_version
    doc_obj.metadata.encrypted = doc_fitz.is_encrypted

    # --- B. Extraction par Page ---
    word_global_id = 1
    image_global_id = 1
    table_global_id = 1

    for idx in range(len(doc_fitz)):
        page_fitz = doc_fitz[idx]
        page_plumb = pdf_plumb.pages[idx]
        
        # Instanciation de notre objet Page
        page_obj = Page(
            number=idx + 1,
            width=float(page_fitz.rect.width),
            height=float(page_fitz.rect.height),
            rotation=float(page_fitz.rotation)
        )
        
        # ---------------------------------------------------------------------
        # MOTOR 1 : PyMuPDF (Texte, Glyphes, Polices, Blocs)
        # ---------------------------------------------------------------------
        # get_text("dict") offre une granularité totale (blocs -> lignes -> spans -> caractères)
        page_dict = page_fitz.get_text("dict")
        font_map = {} # Pour collecter les tailles rencontrées par police
        
        block_idx = 0
        for b in page_dict.get("blocks", []):
            if b.get("type") != 0:  # Ignorer les blocs d'images natifs PyMuPDF
                continue
            
            line_idx = 0
            for l in b.get("lines", []):
                word_idx = 0
                
                for s in l.get("spans", []):
                    font_name = s.get("font", "Unknown")
                    font_size = float(s.get("size", 0.0))
                    bold = bool(s.get("flags", 0) & 4) # Bit 4 des flags = Bold
                    italic = bool(s.get("flags", 0) & 2) # Bit 2 des flags = Italic
                    color_hex = _convertir_couleur(s.get("color"))
                    
                    # Enregistrement des informations de police
                    if font_name not in font_map:
                        font_map[font_name] = set()
                    font_map[font_name].add(round(font_size, 1))
                    
                    # PyMuPDF extrait au niveau caractère à l'intérieur du span si besoin
                    for ch in s.get("chars", []):
                        char_bbox = BBox(ch["bbox"][0], ch["bbox"][1], ch["bbox"][2], ch["bbox"][3])
                        page_obj.native.chars.append(Character(
                            char=ch["c"], bbox=char_bbox, font=font_name, font_size=font_size
                        ))
                
                # Récupération des mots pour conserver l'indexation de la ligne
                mots_ligne = l.get("spans", [])
                # Pour reconstruire les mots avec précision géométrique de gauche à droite
                words_fitz = page_fitz.get_text("words")
                # Filtrer les mots appartenant à la zone géométrique de la ligne courante
                for w in words_fitz:
                    # w = (x0, y0, x1, y1, "text", block_no, line_no, word_no)
                    if w[5] == block_idx and w[6] == line_idx:
                        word_bbox = BBox(w[0], w[1], w[2], w[3])
                        
                        # Retrouver les attributs du span correspondant à la zone du mot
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
                        word_idx += 1
                line_idx += 1
            block_idx += 1

        # Injection des polices uniques collectées
        for name, sizes in font_map.items():
            page_obj.native.fonts.append(Font(name=name, sizes=sorted(list(sizes))))

        # ---------------------------------------------------------------------
        # MOTOR 2 : pdfplumber (Images, Tableaux, Vecteurs)
        # ---------------------------------------------------------------------
        # Images
        for img in page_plumb.images:
            img_bbox = BBox(float(img["x0"]), float(img["top"]), float(img["x1"]), float(img["bottom"]))
            page_obj.graphics.images.append(ImageElement(
                id=image_global_id, bbox=img_bbox, 
                width=int(img.get("width", 0)), height=int(img.get("height", 0))
            ))
            image_global_id += 1
            
        # Tableaux
        for t in page_plumb.find_tables():
            t_bbox = BBox(float(t.bbox[0]), float(t.bbox[1]), float(t.bbox[2]), float(t.bbox[3]))
            page_obj.graphics.tables.append(TableElement(
                id=table_global_id, bbox=t_bbox, source="pdfplumber", rows=t.extract()
            ))
            table_global_id += 1
            
        # Vecteurs (Lines, Rects, Curves)
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
    
    # Rendu du JSON optionnel ou par défaut pour ton contrôle visuel
    chemin_json = args.output or (args.pdf.rsplit(".", 1)[0] + ".document.json")
    doc.save(chemin_json)
    
    print(f"✅ Extraction terminée avec succès !")
    print(f"   ↳ {doc.metadata.page_count} page(s) extraite(s).")
    print(f"   ↳ Fichier JSON généré pour vérification : {chemin_json}")