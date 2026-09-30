import pymupdf
import pytest

from datacompiler.compile.typography import normaliser
from datacompiler.backend.rebuilt_pdf import _grouper_en_spans
from datacompiler.model.document import BBox, Word


def _word(id_, text, bbox, *, block, line, font_size=9.5, font="Helvetica", bold=False):
    return Word(
        id=id_,
        text=text,
        bbox=BBox(*bbox),
        block=block,
        line=line,
        font=font,
        font_size=font_size,
        bold=bold,
    )


def test_renvoi_14_est_petit_et_aligne_sur_la_ligne_de_base():
    mots = [
        _word(1, "soumis", (0, 10, 30, 23), block=1, line=0),
        _word(2, "au", (33, 10, 44, 23), block=1, line=0),
        _word(3, "barème", (47, 10, 79, 23), block=1, line=0),
        _word(4, "14", (82, 10.76, 88.67, 19), block=1, line=0, font_size=6),
    ]

    resultat = normaliser(mots)
    reference = resultat[-1]
    baseline_ligne = mots[0].bbox.y0 + 9.5 * pymupdf.Font("Helvetica").ascender
    baseline_reference = (
        reference.bbox.y0
        + reference.font_size * pymupdf.Font("Helvetica").ascender
    )

    assert reference.text == "14"
    assert reference.font_size == pytest.approx(9.5 * 8 / 12)
    assert baseline_reference == pytest.approx(baseline_ligne)
    assert reference.notes[-1].endswith("aligné sur la ligne de base")
    spans = _grouper_en_spans(resultat)
    assert [(span["textes"], span["size"]) for span in spans] == [
        (["soumis", "au", "barème"], 9.5),
        (["14"], pytest.approx(9.5 * 8 / 12)),
    ]


def test_renvoi_20_est_separe_des_pointilles_et_elargi_sans_decalage_vertical():
    mots = [
        _word(1, "Total", (0, 10, 22, 23), block=2, line=0, font="Helvetica-Bold", bold=True),
        _word(2, "des", (25, 10, 42, 23), block=2, line=0, font="Helvetica-Bold", bold=True),
        _word(3, "réductions", (45, 10, 94, 23), block=2, line=0, font="Helvetica-Bold", bold=True),
        _word(4, "d'impôt", (97, 10, 130, 23), block=2, line=0, font="Helvetica-Bold", bold=True),
        _word(
            5, "20..........................", (133, 10, 208, 23),
            block=2, line=0, font="Helvetica-Bold", bold=True,
        ),
    ]

    resultat = normaliser(mots)
    reference, pointilles = resultat[-2:]

    assert reference.text == "20"
    assert reference.font_size == pytest.approx(9.5 * 8 / 12)
    assert pointilles.text == ".........................."
    assert pointilles.font_size == 9.5
    assert pointilles.bbox.x0 == pytest.approx(reference.bbox.x1)
    assert pointilles.bbox.x1 > 208
    assert pointilles.bbox.y0 == 10


def test_renvoi_53_est_separe_de_deux_points_et_aligne_sur_la_ligne():
    mots = [
        _word(1, "Impôt", (0, 10, 24, 23), block=3, line=0),
        _word(2, "sur", (27, 10, 40, 23), block=3, line=0),
        _word(3, "le", (43, 10, 50, 23), block=3, line=0),
        _word(4, "revenu", (53, 10, 82, 23), block=3, line=0),
        _word(5, "2020", (85, 10, 107, 23), block=3, line=0),
        _word(6, "dû", (110, 10, 130, 23), block=3, line=0),
        _word(7, "53:", (131, 10, 140.31, 23), block=3, line=0, font_size=6),
    ]

    resultat = normaliser(mots)
    reference, deux_points = resultat[-2:]

    assert reference.text == "53"
    assert reference.font_size == pytest.approx(9.5 * 8 / 12)
    assert deux_points.text == ":"
    assert deux_points.font_size == 9.5
    assert deux_points.bbox.x0 == pytest.approx(reference.bbox.x1)
    assert deux_points.bbox.x1 > 30


def test_autres_occurrences_des_nombres_ne_sont_pas_modifiees():
    mots = [
        _word(1, "14", (0, 10, 13, 23), block=4, line=0),
        _word(2, "texte", (15, 10, 40, 23), block=4, line=0),
    ]

    resultat = normaliser(mots)

    assert resultat[0].font_size == 9.5
    assert resultat[0].bbox == BBox(0, 10, 13, 23)
