import json

from datacompiler.model import BBox, Document, Page, Word
from datacompiler.frontend.diagnostic import diagnostiquer, pages_a_ocriser
from datacompiler.compile import resoudre


def w(id, text, x0, y0, x1, y1):
    return Word(id=id, text=text, bbox=BBox(x0, y0, x1, y1), font_size=10.0)


def ocr_w(id, text, confidence):
    return Word(id=id, text=text, bbox=None, confidence=confidence, source="mistral")


def test_diagnostic_par_page():
    doc = Document()
    doc.metadata.filename = "test.pdf"

    page1 = Page(number=1, width=600, height=800)
    texte_propre = (
        "Ceci est un texte tout à fait normal et suffisamment long pour "
        "que le diagnostic de qualité dispose d un échantillon fiable et "
        "ne bascule pas vers une recommandation OCR par précaution ici"
    ).split()
    page1.native.words = [
        w(i + 1, mot, 50 + i * 10, 100, 60 + i * 10, 110) for i, mot in enumerate(texte_propre)
    ]

    page2 = Page(number=2, width=600, height=800)
    page2.native.words = []

    doc.pages = [page1, page2]
    diagnostiquer(doc)

    assert doc.pages[0].diagnostic.recommend_ocr is False
    assert doc.pages[1].diagnostic.recommend_ocr is True
    assert pages_a_ocriser(doc) == [2]


def test_echantillon_court_recommande_ocr():
    page_courte = Page(number=1, width=600, height=800)
    page_courte.native.words = [w(1, "Texte", 50, 100, 100, 110), w(2, "propre", 105, 100, 150, 110)]
    doc_court = Document()
    doc_court.pages = [page_courte]
    diagnostiquer(doc_court)
    diag = doc_court.pages[0].diagnostic

    assert diag.confiance_suffisante is False
    assert diag.recommend_ocr is True


def test_symboles_corrompus_recommandent_ocr():
    page_symbole = Page(number=1, width=600, height=800)
    texte_avec_symbole = (
        "Montant de 8.68 e et de 1.73 e et de 10.41 e pour ce document assez long merci"
    ).split()
    page_symbole.native.words = [
        w(i + 1, mot, 50 + i * 10, 100, 60 + i * 10, 110) for i, mot in enumerate(texte_avec_symbole)
    ]
    doc_symbole = Document()
    doc_symbole.pages = [page_symbole]
    diagnostiquer(doc_symbole)
    diag = doc_symbole.pages[0].diagnostic

    assert diag.symboles_suspects == {"e": 3}
    assert diag.recommend_ocr is True


def test_ocr_ignore_sur_page_propre():
    doc = Document()
    doc.metadata.filename = "test.pdf"

    page1 = Page(number=1, width=600, height=800)
    texte_propre = (
        "Ceci est un texte tout à fait normal et suffisamment long pour "
        "que le diagnostic de qualité dispose d un échantillon fiable et "
        "ne bascule pas vers une recommandation OCR par précaution ici"
    ).split()
    page1.native.words = [
        w(i + 1, mot, 50 + i * 10, 100, 60 + i * 10, 110) for i, mot in enumerate(texte_propre)
    ]
    page2 = Page(number=2, width=600, height=800)
    page2.native.words = []
    doc.pages = [page1, page2]
    diagnostiquer(doc)

    page1.ocr.words = [ocr_w(1, "Texte", 0.9), ocr_w(2, "PROPRE_OCR_DIFFERENT", 0.99)]
    resoudre(doc)
    sortie_page1 = [m.output_text for m in doc.pages[0].resolved.words]

    assert "PROPRE_OCR_DIFFERENT" not in sortie_page1


def test_decision_sur_conflit_natif_ocr():
    page3 = Page(number=1, width=600, height=800)
    page3.native.words = [w(1, "monta1t", 50, 100, 100, 110)]
    page3.ocr.words = [ocr_w(1, "montant", 0.97)]
    doc3 = Document()
    doc3.pages = [page3]
    diagnostiquer(doc3)
    resoudre(doc3)
    mot = doc3.pages[0].resolved.words[0]

    assert mot.output_text == "montant"
    assert mot.decision is not None
    assert mot.decision.regle == "conflit_ocr_corrige"


def test_round_trip_json():
    page3 = Page(number=1, width=600, height=800)
    page3.native.words = [w(1, "monta1t", 50, 100, 100, 110)]
    page3.ocr.words = [ocr_w(1, "montant", 0.97)]
    doc3 = Document()
    doc3.pages = [page3]
    diagnostiquer(doc3)
    resoudre(doc3)

    brut = json.loads(doc3.to_json())
    assert "diagnostic" not in brut
    assert "diagnostic" in brut["pages"][0]
    assert brut["pages"][0]["resolved"]["words"][0]["decision"] is not None

    doc3_reload = Document.from_dict(brut)
    mot_reload = doc3_reload.pages[0].resolved.words[0]
    assert mot_reload.output_text == "montant"
    assert mot_reload.decision.regle == "conflit_ocr_corrige"
    assert doc3_reload.pages[0].diagnostic.recommend_ocr is True


def test_decision_sur_ligature():
    page4 = Page(number=1, width=600, height=800)
    page4.native.words = [w(1, "e\ufb03cace", 50, 100, 100, 110)]
    doc4 = Document()
    doc4.pages = [page4]
    diagnostiquer(doc4)
    resoudre(doc4)
    mot4 = doc4.pages[0].resolved.words[0]

    assert mot4.output_text == "efficace"
    assert mot4.decision is not None
    assert mot4.decision.regle == "ligature"
