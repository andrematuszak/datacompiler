from pathlib import Path

import pymupdf
import pytest

from datacompiler.backend.rebuilt_pdf import _calibrer_lignes
from datacompiler.backend.rebuilt_pdf import render_rebuilt_pdf
from datacompiler.compile.reading_order import ordonner
from datacompiler.frontend.diagnostic.vector_text import zones_texte_vectorise_probable
from datacompiler.frontend.extract import extraire
from datacompiler.frontend.ocr.vector_zones import (
    _barre_oblique_entre_nombres,
    _clipper_marge_sur_natifs,
    recuperer_texte_vectorise,
)
from datacompiler.model.document import BBox, Document, Word


PAGE_2_FIXTURE = (
    Path(__file__).parent / "fixtures" / "impots-revenu" / "impots-revenu.pdf"
)
FULL_FIXTURE = (
    Path(__file__).parent / "fixtures" / "impots-revenu" / "impots-revenu-entier.pdf"
)


def _page_2():
    return extraire(Document(), str(PAGE_2_FIXTURE)).pages[0]


def test_ponctuation_vectorielle_du_bandeau_est_preservee_en_zone_ocr():
    page = _page_2()
    zones = zones_texte_vectorise_probable(page)

    def zone_couvre(bbox):
        x0, y0, x1, y1 = bbox
        return any(
            zone[0] <= x0 + 0.1
            and zone[1] <= y0 + 0.1
            and zone[2] >= x1 - 0.1
            and zone[3] >= y1 - 0.1
            for zone in zones
        )

    # Les deux points de « N° fiscal : » et « Feuillet n° : » sont des
    # groupes vectoriels trop petits pour franchir le seuil de densité seul.
    assert zone_couvre((51.86, 46.91, 52.86, 47.91))
    assert zone_couvre((51.86, 51.09, 52.86, 52.09))
    assert zone_couvre((511.93, 46.91, 512.93, 47.91))
    assert zone_couvre((511.93, 51.09, 512.93, 52.09))
    # La barre oblique est séparée des mots « 1 » et « 2 », qui sont natifs.
    assert zone_couvre((530.47, 44.81, 533.25, 52.21))
    slash = BBox(530.47, 44.81, 533.25, 52.21)
    crop = _clipper_marge_sur_natifs(slash, 8.0, page.native.words)
    assert crop.x1 - crop.x0 >= 12.0
    assert crop.y1 - crop.y0 >= 20.0


def test_entete_page_2_melange_natif_vectoriel_trie_gauche_a_droite():
    page = _page_2()
    page.native.words.extend([
        Word(
            id=900, text="N°", bbox=BBox(14.93, 44.81, 28.52, 52.21),
            is_vectorized=True, reconstructed=True, font_size=8.0,
        ),
        Word(
            id=901, text="fiscal", bbox=BBox(30.70, 44.81, 47.47, 52.21),
            is_vectorized=True, reconstructed=True, font_size=8.0,
        ),
        Word(
            id=902, text=":", bbox=BBox(51.86, 46.91, 52.86, 52.09),
            is_vectorized=True, reconstructed=True, font_size=8.0,
        ),
        Word(
            id=903, text="Feuillet", bbox=BBox(464.49, 44.81, 492.71, 52.21),
            is_vectorized=True, reconstructed=True, font_size=8.0,
        ),
        Word(
            id=904, text="n°", bbox=BBox(499.34, 44.81, 507.58, 52.21),
            is_vectorized=True, reconstructed=True, font_size=8.0,
        ),
        Word(
            id=905, text=":", bbox=BBox(511.93, 46.91, 512.93, 52.09),
            is_vectorized=True, reconstructed=True, font_size=8.0,
        ),
        Word(
            id=906, text="/", bbox=BBox(530.47, 44.81, 533.25, 52.21),
            is_vectorized=True, reconstructed=True, font_size=8.0,
        ),
    ])

    entete = [word for word in ordonner(page) if word.bbox.y0 < 60]
    textes = [word.text for word in entete]

    assert textes.index("N°") < textes.index("fiscal") < textes.index(":")
    assert textes.index(":") < textes.index("13")
    assert textes.index("261") < textes.index("Feuillet")
    colon_feuillet = textes.index(":", textes.index("Feuillet"))
    assert textes.index("Feuillet") < textes.index("n°") < colon_feuillet
    assert colon_feuillet < textes.index("1")
    assert textes.index("1") < textes.index("/") < textes.index("2")


def test_references_page_2_gardent_taille_et_position_exposant():
    page = _page_2()
    references = {
        mot.text: mot
        for mot in page.native.words
        if mot.text in {"14", "15", "20", "53"}
    }
    assert set(references) == {"14", "15", "20", "53"}

    baselines = _calibrer_lignes(page.native.words)
    for numero, reference in references.items():
        assert reference.font_size == 6.0, numero
        texte_principal = [
            mot for mot in page.native.words
            if abs(mot.bbox.y0 - reference.bbox.y0) <= 3.5
            and mot.bbox.x0 < reference.bbox.x0
            and mot.font_size > reference.font_size
        ]
        assert texte_principal, numero
        principal = max(texte_principal, key=lambda mot: mot.bbox.x1)
        assert baselines[id(reference)] < baselines[id(principal)] - 1.0, numero


def test_barre_oblique_vectorielle_est_reconstruite_entre_nombres_natifs():
    page = _page_2()

    class BackendSansReconnaissance:
        def ocraliser_zone(self, image, **kwargs):
            return []

    recuperer_texte_vectorise(
        Document(pages=[page]), str(PAGE_2_FIXTURE), BackendSansReconnaissance()
    )
    slashes = [
        mot for mot in page.native.words
        if mot.text == "/" and mot.source == "vector_geometry"
    ]

    assert len(slashes) == 1
    slash = slashes[0]
    assert slash.bbox.x0 == pytest.approx(530.47, abs=0.01)
    assert slash.bbox.x1 == pytest.approx(533.25, abs=0.01)
    entete = [mot.text for mot in ordonner(page) if mot.bbox.y0 < 60]
    assert entete.index("1") < entete.index("/") < entete.index("2")


def test_reconstruction_de_barre_ne_change_pas_la_reference_2_sur_2_page_3():
    page_3 = extraire(Document(), str(FULL_FIXTURE)).pages[2]
    zones = zones_texte_vectorise_probable(page_3)

    assert not any(
        _barre_oblique_entre_nombres(BBox(*zone), page_3.native.words)
        for zone in zones
    )


def test_mots_detectes_dans_les_tableaux_restent_dans_ordre_page():
    page = _page_2()
    mots_table = [
        Word(id=910, text="situation", bbox=BBox(65, 88, 110, 99),
             is_vectorized=True, reconstructed=True),
        Word(id=911, text="foyer", bbox=BBox(120, 88, 160, 99),
             is_vectorized=True, reconstructed=True),
        Word(id=912, text="majeurs", bbox=BBox(235, 88, 290, 99),
             is_vectorized=True, reconstructed=True),
        Word(id=913, text="RÉSIDENCE", bbox=BBox(65, 128, 130, 139),
             is_vectorized=True, reconstructed=True),
    ]
    page.native.words.extend(mots_table)

    resultat = ordonner(page)
    positions = {
        mot.text: next(i for i, item in enumerate(resultat) if item.text == mot.text)
        for mot in mots_table
    }
    indice_c = next(i for i, mot in enumerate(resultat) if mot.text == "C")
    indice_titre = next(i for i, mot in enumerate(resultat) if mot.text == "Détail")
    indice_nombre_de_parts = next(
        i for i, mot in enumerate(resultat)
        if mot.text == "2,50" and mot.bbox.y0 > 150
    )

    assert positions["situation"] < positions["foyer"] < positions["majeurs"]
    assert positions["majeurs"] < indice_c < positions["RÉSIDENCE"]
    assert positions["RÉSIDENCE"] < indice_nombre_de_parts < indice_titre


def test_ordre_exporte_page_2_avec_ocr_vectoriel_simule(tmp_path):
    page = _page_2()

    class BackendOcrDeTest:
        def ocraliser_zone(self, image, offset=(0.0, 0.0), **kwargs):
            if offset[1] < 80 or offset[1] > 110:
                return []
            return [
                Word(
                    id=-1, text=texte, resolved_text=texte,
                    bbox=BBox(*bbox), source="ocr_vectoriel",
                    is_vectorized=True, reconstructed=True, font_size=9.5,
                )
                for texte, bbox in (
                    ("situation", (65, 88, 112, 99)),
                    ("majeurs", (235, 88, 290, 99)),
                )
            ]

    document = Document(pages=[page])
    recuperer_texte_vectorise(
        document, str(PAGE_2_FIXTURE), BackendOcrDeTest()
    )
    page.resolved.words = ordonner(page)
    output_path = tmp_path / "page-2-rebuilt.pdf"
    render_rebuilt_pdf(
        document, str(output_path), source_pdf=str(PAGE_2_FIXTURE)
    )

    with pymupdf.open(output_path) as output:
        texte = " ".join(output[0].get_text().split())

    assert "1 / 2" in texte
    assert texte.index("situation") < texte.index("C") < texte.index("Détail")
    assert texte.index("majeurs") < texte.index("C")
