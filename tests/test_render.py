# tests/test_render.py
import os
from datacompiler.frontend.extract import extraire
from datacompiler.model.document import Document
from datacompiler.backend.faithful_pdf import reconstruire_pdf_direct

def test_generation_pdf_depuis_fixture(tmp_path):
    """
    Vérifie qu'un PDF est bien généré en sortie à partir de test1.pdf.
    `tmp_path` est un dossier temporaire créé automatiquement par pytest.
    """
    # 1. Emplacement du PDF de test d'entrée
    pdf_input = "tests/fixtures/test1.pdf"
    
    # On définit un chemin pour le PDF de sortie temporaire
    pdf_output = tmp_path / "test1_output.pdf"
    
    # 2. Chaîne d'exécution
    donnees = extraire(pdf_input)
    doc = Document(donnees)
    reconstruire_pdf_direct(doc, str(pdf_output))
    
    # 3. Assertions (Vérifications)
    # A) Le fichier de sortie existe-t-il ?
    assert os.path.exists(pdf_output), "Le fichier PDF de sortie n'a pas été créé !"
    
    # B) Le fichier généré est-il non vide ?
    assert os.path.getsize(pdf_output) > 0, "Le PDF généré est vide (0 octets) !"
