from pathlib import Path
import statistics

import pymupdf
import pytest

from datacompiler.backend.rebuilt_pdf import (
    _ascender_police_source,
    _calibrer_lignes,
    render_rebuilt_pdf,
)
from datacompiler.backend import rebuilt_pdf
from datacompiler.compile import resoudre
from datacompiler import Document
from datacompiler.frontend.extract import extraire
from datacompiler.frontend.ocr.vector_zones import _assigner_taille_lissee
from datacompiler.model.document import BBox, Word
from datacompiler.utils.font_metrics import ratio_encre_em


_SOURCE_PDF = Path(__file__).parent / "fixtures" / "impots-revenu" / "impots-revenu.pdf"


def _mot(id_, texte, bbox):
    return Word(
        id=id_,
        text=texte,
        resolved_text=texte,
        bbox=BBox(*bbox),
        is_vectorized=True,
        bold=True,
        reconstructed=True,
    )


def test_titre_vectorise_retrouve_taille_et_bbox_depuis_les_traces_source():
    page = pymupdf.open(_SOURCE_PDF)[0]
    dessins = page.get_drawings()
    mots = [
        _mot(1, "DIRECTION", (126.5, 21.4, 160.0, 28.7)),
        _mot(2, "GÉNÉRALE", (162.0, 19.6, 203.0, 28.7)),
        _mot(3, "DES", (205.0, 21.4, 220.0, 28.7)),
        _mot(4, "FINANCES", (222.0, 21.4, 263.0, 28.7)),
        _mot(5, "PUBLIQUES", (266.0, 21.4, 323.5, 28.7)),
    ]
    zone = (120.0, 18.0, 380.0, 31.0)
    zones_par_mot = {id(m): zone for m in mots}

    _assigner_taille_lissee(mots, dessins, zones_par_mot)

    tailles = [m.font_size for m in mots]
    assert max(tailles) - min(tailles) < 1e-6
    assert 9.5 <= tailles[0] <= 11.0
    assert ratio_encre_em("GÉNÉRALE", True) > ratio_encre_em("DIRECTION", True)

    glyphes = [
        d["rect"] for d in dessins
        if 120 < d["rect"].x0 < 380
        and 18 < d["rect"].y0 < 31
        and d["rect"].width <= 30
        and d["rect"].height <= 30
    ]
    assert min(m.bbox.x0 for m in mots) == pytest.approx(min(r.x0 for r in glyphes), abs=0.02)
    assert max(m.bbox.x1 for m in mots) == pytest.approx(max(r.x1 for r in glyphes), abs=0.02)

    baselines = _calibrer_lignes(mots)
    assert max(baselines.values()) - min(baselines.values()) < 0.02
    assert next(iter(baselines.values())) == pytest.approx(
        sorted(r.y1 for r in glyphes)[len(glyphes) // 2], abs=0.15
    )


def test_libelles_date_conservent_l_interligne_vectoriel_source():
    page = pymupdf.open(_SOURCE_PDF)[0]
    dessins = page.get_drawings()
    mots = [
        _mot(1, "Date", (21.12, 303.8, 39.6, 310.28)),
        _mot(2, "d’établissement", (42.96, 303.56, 110.4, 310.28)),
        _mot(3, ":", (114.0, 305.48, 114.72, 310.04)),
        _mot(4, "Date", (19.42, 310.4, 38.48, 320.22)),
        _mot(5, "de", (41.0, 310.4, 51.0, 320.22)),
        _mot(6, "mise", (53.0, 310.4, 73.0, 320.22)),
        _mot(7, "en", (76.0, 312.0, 86.0, 320.22)),
        _mot(8, "recouvrement", (88.0, 310.4, 147.0, 320.22)),
        _mot(9, ":", (149.0, 312.0, 151.0, 320.22)),
    ]
    zone = (14.0, 300.0, 213.0, 325.0)
    zones_par_mot = {id(m): zone for m in mots}

    _assigner_taille_lissee(mots, dessins, zones_par_mot)
    baselines = _calibrer_lignes(mots)
    first_line = [baselines[id(m)] for m in mots[:3]]
    second_line = [baselines[id(m)] for m in mots[3:]]

    assert max(first_line) - min(first_line) < 0.02
    assert max(second_line) - min(second_line) < 0.02
    assert statistics.median(second_line) - statistics.median(first_line) == pytest.approx(11.0, abs=0.25)
    assert statistics.median(m.font_size for m in mots[:3]) == pytest.approx(
        statistics.median(m.font_size for m in mots[3:]), abs=0.4
    )


def test_baseline_native_uses_metric_ascender_source():
    mot = Word(
        id=1,
        text="Impôt",
        bbox=BBox(128.0, 27.91, 166.1, 47.19),
        font="Helvetica-Bold",
        font_size=14.0,
    )
    baseline = _calibrer_lignes([mot])[id(mot)]

    assert _ascender_police_source("Helvetica-Bold", True, False) == pytest.approx(1.07, abs=0.01)
    assert baseline == pytest.approx(42.89, abs=0.15)


def test_texte_vectorise_inchange_garde_le_rendu_vectoriel_source(tmp_path, monkeypatch):
    monkeypatch.setattr(rebuilt_pdf, "_polices", {})
    doc = extraire(Document(), str(_SOURCE_PDF))
    source_page = pymupdf.open(_SOURCE_PDF)[0]
    lignes = [
        (
            "DIRECTION GÉNÉRALE DES FINANCES PUBLIQUES",
            (126.57, 20.23, 323.52, 29.07),
            (120.0, 18.0, 380.0, 31.0),
            False,
        ),
        (
            "Date d'établissement :",
            (19.92, 302.84, 111.21, 312.49),
            (14.0, 300.0, 213.0, 325.0),
            True,
        ),
        (
            "Date de mise en recouvrement :",
            (19.42, 310.4, 154.71, 320.22),
            (14.0, 300.0, 213.0, 325.0),
            True,
        ),
    ]
    mots = [
        Word(
            id=max(w.id for w in doc.pages[0].native.words) + i,
            text=texte,
            resolved_text=texte,
            bbox=BBox(*bbox),
            source="ocr_vectoriel",
            is_vectorized=True,
            reconstructed=True,
            bold=gras,
        )
        for i, (texte, bbox, _, gras) in enumerate(lignes, start=1)
    ]
    _assigner_taille_lissee(
        mots,
        source_page.get_drawings(),
        {id(mot): zone for mot, (_, _, zone, _) in zip(mots, lignes)},
    )
    doc.pages[0].native.words.extend(mots)
    resoudre(doc)

    output_path = tmp_path / "rebuilt.pdf"
    render_rebuilt_pdf(doc, str(output_path), source_pdf=str(_SOURCE_PDF))

    rendered_page = pymupdf.open(output_path)[0]
    matrix = pymupdf.Matrix(2, 2)
    def ink_bbox(pix):
        coords = []
        for y in range(pix.height):
            for x in range(pix.width):
                offset = (y * pix.width + x) * pix.n
                if max(pix.samples[offset:offset + 3]) < 128:
                    coords.append((x, y))
        return (
            min(x for x, _ in coords),
            min(y for _, y in coords),
            max(x for x, _ in coords),
            max(y for _, y in coords),
        )

    for clip in (
        pymupdf.Rect(120, 18, 380, 29.5),
        pymupdf.Rect(14, 301, 156, 311),
        pymupdf.Rect(14, 313, 156, 322),
    ):
        source_pixels = source_page.get_pixmap(matrix=matrix, clip=clip, alpha=False)
        output_pixels = rendered_page.get_pixmap(matrix=matrix, clip=clip, alpha=False)
        assert ink_bbox(output_pixels) == ink_bbox(source_pixels)
    extracted = rendered_page.get_text("text")
    for texte, _, _, _ in lignes:
        assert texte in extracted
