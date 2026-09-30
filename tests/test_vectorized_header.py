import pymupdf
import pytest
from PIL import Image

from datacompiler.compile import reading_order
from datacompiler.frontend.ocr import paddle
from datacompiler.frontend.ocr import tesseract
from datacompiler.frontend.ocr.vector_zones import _candidats_ponctuation
from datacompiler.model.document import BBox, GraphicsContainer, NativeContainer, Page, Word


def test_ocr_ponctuation_vectorielle_isolee(monkeypatch):
    donnees = {
        "text": [":", "/"],
        "conf": ["0", "0"],
        "left": [17, 18],
        "top": [17, 17],
        "width": [8, 22],
        "height": [43, 62],
    }
    monkeypatch.setattr(
        tesseract.pytesseract,
        "image_to_data",
        lambda *args, **kwargs: donnees,
    )

    mots = tesseract._ocraliser_ponctuation_zone_image(
        object(), ":", lang="fra", dpi=600, offset=(50.0, 45.0)
    )

    assert [mot.text for mot in mots] == [":"]
    assert (
        mots[0].bbox.x0,
        mots[0].bbox.y0,
        mots[0].bbox.x1,
        mots[0].bbox.y1,
    ) == pytest.approx((52.04, 47.04, 53.0, 52.2))
    assert mots[0].confidence == 0.0
    assert mots[0].is_vectorized


def test_paddle_ocr_ponctuation_vecteur_agrandie(monkeypatch):
    backend = paddle.PaddleOcrBackend.__new__(paddle.PaddleOcrBackend)
    backend.dpi = 600
    monkeypatch.setattr(
        backend,
        "_extraire",
        lambda image: [{
            "text": "/",
            "x0": 30,
            "y0": 45,
            "x1": 60,
            "y1": 105,
            "confidence": 0.95,
        }],
    )

    mots = backend.ocraliser_ponctuation(
        Image.new("RGB", (50, 80)), "/", offset=(528.5, 42.8),
    )

    assert [mot.text for mot in mots] == ["/"]
    assert (
        mots[0].bbox.x0,
        mots[0].bbox.y0,
        mots[0].bbox.x1,
        mots[0].bbox.y1,
    ) == pytest.approx((529.7, 44.6, 530.9, 47.0))


def test_candidats_ponctuation_limites_aux_voisinages_texte():
    dessins = [
        {"rect": pymupdf.Rect(51.859, 46.907, 52.86, 52.093)},
        {"rect": pymupdf.Rect(530.472, 44.813, 533.25, 52.215)},
        {"rect": pymupdf.Rect(511.859, 46.907, 512.86, 52.093)},
        {"rect": pymupdf.Rect(10, 10, 11, 15)},
    ]
    mots_natifs = [
        Word(id=1, text="13", bbox=BBox(58, 42, 67, 55)),
        Word(id=2, text="Feuillet n°", bbox=BBox(464, 42, 508, 55), is_vectorized=True),
        Word(id=3, text="1", bbox=BBox(520, 42, 525, 55)),
        Word(id=4, text="2", bbox=BBox(538, 42, 543, 55)),
    ]

    candidats = _candidats_ponctuation(
        dessins, [(14, 44, 47.5, 52)], mots_natifs
    )

    candidats.sort(key=lambda candidat: candidat[1].x0)
    assert [symbole for symbole, _ in candidats] == [":", ":", "/"]


def test_entete_conserve_ordre_gauche_droite_sur_ligne(monkeypatch):
    monkeypatch.setattr(reading_order, "detecter_boites_encadres", lambda page: [])
    mots = [
        Word(
            id=1, text="N°fiscal", bbox=BBox(14.93, 44.81, 47.47, 52.19),
            is_vectorized=True,
        ),
        Word(
            id=2, text=":", bbox=BBox(51.86, 46.91, 52.86, 52.09),
            is_vectorized=True,
        ),
        Word(id=3, text="13", bbox=BBox(58, 42.22, 67, 54.58), block=1),
        Word(id=4, text="86", bbox=BBox(71, 42.22, 80, 54.58), block=1),
        Word(id=5, text="581", bbox=BBox(84, 42.22, 101, 54.58), block=1),
        Word(id=6, text="387", bbox=BBox(105, 42.22, 122, 54.58), block=1),
        Word(id=7, text="261", bbox=BBox(124, 42.22, 141, 54.58), block=1),
        Word(
            id=8, text="Feuillet", bbox=BBox(464.38, 44.81, 497.5, 52.28),
            is_vectorized=True,
        ),
        Word(
            id=12, text="n°", bbox=BBox(499.34, 44.81, 507.58, 52.09),
            is_vectorized=True,
        ),
        Word(
            id=13, text=":", bbox=BBox(511.86, 46.91, 512.86, 52.09),
            is_vectorized=True,
        ),
        Word(id=9, text="1", bbox=BBox(520, 42.22, 525, 54.58), block=1),
        Word(
            id=10, text="/", bbox=BBox(530.47, 44.81, 533.25, 52.22),
            is_vectorized=True,
        ),
        Word(id=11, text="2", bbox=BBox(538, 42.22, 543, 54.58), block=1),
    ]
    page = Page(
        number=2,
        width=595,
        height=842,
        native=NativeContainer(words=mots),
        graphics=GraphicsContainer(tables=[]),
    )

    resultat = reading_order.ordonner(page)

    assert [mot.text for mot in resultat] == [
        "N°fiscal", ":", "13", "86", "581", "387", "261",
        "Feuillet", "n°", ":", "1", "/", "2",
    ]
