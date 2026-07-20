# tests/test_diagnostic.py
from datacleaner.core.diagnostic import analyser_qualite

def test_analyser_qualite_texte_valide():
    """Vérifie que la fonction renvoie un statut OK pour un texte propre."""
    # 1. Données de test (mock)
    texte_clean = "Ceci est un texte parfaitement lisible sans anomalie."
    
    # 2. Exécution
    rapport = analyser_qualite(texte_clean)
    
    # 3. Vérifications (Assertions)
    assert rapport["statut"] == "OK"
    assert rapport["score"] > 80

def test_analyser_qualite_texte_corrompu():
    """Vérifie que la fonction détecte le texte Garbled/OCR défaillant."""
    texte_bruite = "C€c! e$t un t3xt3 #%&@! d3f3ctu3ux"
    
    rapport = analyser_qualite(texte_bruite)
    
    assert rapport["statut"] == "ANOMALIE"
    assert "ocr_noise" in rapport["erreurs"]
