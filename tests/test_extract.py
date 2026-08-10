# tests/test_extract.py
from datacompiler.frontend.extract import extraire

def test_extraire_pages_non_vides():
    # 1. ARRANGE : On pointe vers notre fixture
    pdf_path = "tests/fixtures/test1.pdf"
    
    # 2. ACT : On exécute la fonction
    donnees = extraire(pdf_path)
    
    # 3. ASSERT : On vérifie que le résultat est correct
    assert donnees is not None, "L'extraction a renvoyé None !"
    assert len(donnees) > 0, "Aucune page n'a été extraite du PDF !"
