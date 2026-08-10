# tests/conftest.py
import pytest
from pathlib import Path
from datacompiler import Document
import sys

_PKG_ROOT = Path(__file__).resolve().parents[1] / "src" / "datacompiler"
if str(_PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(_PKG_ROOT))


@pytest.fixture
def fixture_dir():
    """Chemin vers tests/fixtures/"""
    return Path(__file__).parent / "fixtures"

@pytest.fixture
def test_pdf(fixture_dir):
    """Le PDF de test principal."""
    return fixture_dir / "test-propre.pdf"

@pytest.fixture
def doc_extracted(test_pdf):
    """Document après extraction (cached)."""
    from datacompiler.frontend.extract import extraire
    doc = Document()
    extraire(doc, str(test_pdf))
    return doc

@pytest.fixture
def mistral_api_key():
    """Ou skip si pas dispo."""
    import os
    key = os.getenv("MISTRAL_API_KEY")
    if not key:
        pytest.skip("MISTRAL_API_KEY not set")
    return key