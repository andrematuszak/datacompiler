# tests/test_regression_word_count.py
import pytest
import json
import fitz  # PyMuPDF
from pathlib import Path

def test_word_count_consistency():
    """
    Vérifie que le nombre de mots dans le PDF rendu correspond exactement
    au nombre de mots dans page.resolved.words du JSON.
    """
    fixture_dir = Path(__file__).parent / "fixtures"
    pdf_propre = fixture_dir / "test-impots-revenu_propre.pdf"
    json_doc = fixture_dir / "test-impots-revenu.document.json"

    if not pdf_propre.exists() or not json_doc.exists():
        pytest.skip("Fichiers de sortie manquants. Lancez d'abord le pipeline.")

    # Charger le JSON
    with open(json_doc, "r", encoding="utf-8") as f:
        doc_data = json.load(f)

    # Ouvrir le PDF rendu
    doc_pdf = fitz.open(pdf_propre)

    try:
        assert len(doc_pdf) == len(doc_data["pages"]), "Nombre de pages incohérent entre JSON et PDF"

        for i, page_data in enumerate(doc_data["pages"]):
            page_pdf = doc_pdf[i]
            
            # Compter les mots résolus dans le JSON
            resolved_words = page_data.get("resolved", {}).get("words", [])
            count_json = len(resolved_words)

            # Compter les mots extractibles dans le PDF
            words_in_pdf = page_pdf.get_text("words")
            count_pdf = len(words_in_pdf)

            # Assertion stricte
            assert count_pdf == count_json, (
                f"Mismatch Page {i+1}: JSON={count_json} mots, PDF={count_pdf} mots. "
                f"Difference: {count_pdf - count_json}"
            )

    finally:
        doc_pdf.close()

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
