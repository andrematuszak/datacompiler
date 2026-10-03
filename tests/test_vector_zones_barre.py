"""Non-régression : la barre oblique « / » de « Feuillet n° : 1 / 2 » (page 2) garde sa bbox.

Elle est reconstruite par géométrie (pas d'OCR). Avant correctif, _ajuster_ligne_sur_traces la
recalait comme un mot OCR et l'écrasait contre le dernier tracé de la ligne (x≈510 au lieu de 530),
d'où l'ordre de lecture « / 1 2 » à la place de « 1 / 2 ».
"""
from pathlib import Path

import pymupdf
import pytest

from datacompiler.frontend.extract.extract_pymupdf import extraire_page_pymupdf
from datacompiler.frontend.ocr.vector_zones import recuperer_texte_vectorise
from datacompiler.model.document import Document, Word
from datacompiler.model.geometry import BBox

PDF = Path(__file__).parent / "fixtures" / "impots-revenu" / "impots-revenu-entier.pdf"


class _FauxBackend:
    """Un mot par zone, calé sur la zone : suffit à déclencher le recalage par lignes."""
    name = "faux"

    def ocraliser_zone(self, image, offset=(0.0, 0.0), dpi=300, lang=None, **kw):
        w_px, h_px = image.size if hasattr(image, "size") else (image.shape[1], image.shape[0])
        w, h = w_px * 72 / dpi, h_px * 72 / dpi
        return [Word(id=-1, text="X", resolved_text="X",
                     bbox=BBox(offset[0], offset[1], offset[0] + w, offset[1] + h),
                     source="faux", is_vectorized=True, confidence=0.9)]


def test_barre_oblique_garde_sa_position(tmp_path):
    pdf = pymupdf.open(str(PDF))
    page, _ = extraire_page_pymupdf(pdf[1], 2, 0)
    sous = pymupdf.open()
    sous.insert_pdf(pdf, from_page=1, to_page=1)
    chemin = tmp_path / "p2.pdf"
    sous.save(str(chemin))

    recuperer_texte_vectorise(Document(pages=[page]), str(chemin), {"faux": _FauxBackend()})

    barres = [w for w in page.native.words if w.text == "/" and w.source == "vector_geometry"]
    assert len(barres) == 1
    un = next(w for w in page.native.words if w.text == "1" and w.bbox.x0 > 500 and w.bbox.y0 < 50)
    deux = next(w for w in page.native.words if w.text == "2" and w.bbox.x0 > 500 and w.bbox.y0 < 50)
    assert un.bbox.x1 <= barres[0].bbox.x0 <= barres[0].bbox.x1 <= deux.bbox.x0
