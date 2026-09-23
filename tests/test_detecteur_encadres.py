"""test_detecteur_encadres.py — Test isolé de detecter_boites_encadres
(frontend/layout/detectors.py) sur le document fiscal réel.

Vérifie UNIQUEMENT la détection géométrique (bbox + couleur) des encadrés
bleus -- pas encore leur intégration dans layout_root ni dans
reading_order.py (étape suivante, volontairement séparée).
"""

import pytest

from datacompiler import Document
from datacompiler.frontend.extract import extraire
from datacompiler.frontend.layout.detectors import detecter_boites_encadres


def test_detecte_encadre_vos_references(sample_pdf):
    """L'encadré "Vos références" (valeurs) doit être détecté avec sa bbox
    réelle, couleur bleue -- bbox de référence obtenue par inspection directe
    de page.get_drawings() sur le document de test (cf. session de
    diagnostic)."""
    doc = Document()
    extraire(doc, str(sample_pdf))
    page = doc.pages[0]

    encadres = detecter_boites_encadres(page)

    assert len(encadres) > 0, "Aucun encadré détecté -- couleur ou seuil de taille à revérifier"

    cibles = [
        e for e in encadres
        if abs(e["bbox"].x0 - 14.2) < 1 and abs(e["bbox"].y0 - 167.2) < 1
    ]
    # Le PDF source dessine ce contour deux fois (double trait) -- confirmé
    # par inspection directe des 13 quads bruts (cf. session de
    # diagnostic) ; >= 1, pas == 1. Le dédoublonnage par bbox arrondie est
    # vérifié séparément par test_detecte_les_neuf_encadres_bleus.
    assert len(cibles) >= 1, f"Encadré 'Vos références' non trouvé parmi {[e['bbox'] for e in encadres]}"

    bbox = cibles[0]["bbox"]
    assert bbox.x1 == pytest.approx(212.6, abs=1.0)
    assert bbox.y1 == pytest.approx(357.2, abs=1.0)
    assert cibles[0]["color"] == "#5d90c7"


def test_detecte_les_neuf_encadres_bleus(sample_pdf):
    """Décompte de contrôle : 9 encadrés bleus distincts attendus sur la
    page 1 (valeur observée par inspection directe des drawings, cf.
    session de diagnostic) -- alerte si un futur changement (extraction,
    seuil de tolérance couleur) en fait apparaître ou disparaître."""
    doc = Document()
    extraire(doc, str(sample_pdf))
    page = doc.pages[0]

    encadres = detecter_boites_encadres(page)
    bboxes_uniques = {
        (round(e["bbox"].x0, 1), round(e["bbox"].y0, 1),
         round(e["bbox"].x1, 1), round(e["bbox"].y1, 1))
        for e in encadres
    }
    assert len(bboxes_uniques) == 9, bboxes_uniques
