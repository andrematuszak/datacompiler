"""
document.py — L'objet central qui circule dans tout le pipeline.

    Document
    ├── native    : grille extraite directement du PDF (extract.py)
    ├── ocr       : grille issue de Mistral OCR, si enrichissement jugé
    │               nécessaire (ocr.py) -- None sinon
    ├── resolved  : grille après arbitrage native/ocr (resolve.py) -- None
    │               tant que resolve.py n'existe pas encore
    └── final     : document prêt pour l'export (render.py part de resolved
                    si disponible, sinon de native directement)

Chaque étage (native, ocr, resolved) partage la MÊME forme de grille --
une liste de pages, chacune avec words/images/tables/fonts/metadata -- pour
que resolve.py puisse comparer native et ocr terme à terme sans conversion.
C'est important : mieux vaut que ocr.py "traduise" la sortie Mistral vers ce
schéma commun plutôt que de garder le format natif de l'API partout.

Le tout est sérialisable en JSON pour correspondre au schéma en diagramme
(document.json, ocr.json, repaired_document.json) -- chaque script peut soit
recevoir un objet Document en mémoire (usage en pipeline), soit lire/écrire
le JSON correspondant (usage en ligne de commande, un script à la fois).
"""

from __future__ import annotations
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


@dataclass
class Word:
    text: str
    bbox: list  # [x0, top, x1, bottom]
    fontname: Optional[str] = None
    size: Optional[float] = None
    confidence: Optional[float] = None  # renseigné par ocr.py, absent pour le natif
    source: Optional[str] = None  # "native" | "mistral" -- renseigné par resolve.py plus tard


@dataclass
class Image:
    bbox: list
    coverage_ratio: Optional[float] = None  # part de la page couverte par cette image


@dataclass
class Table:
    bbox: list
    rows: list  # liste de listes de cellules (texte), telles qu'extraites


@dataclass
class Block:
    """Bloc au sens Mistral : bbox + contenu texte, granularité paragraphe --
    PAS le niveau mot (l'API ne fournit jamais de bbox par mot, vérifié)."""
    bbox: list  # [top_left_x, top_left_y, bottom_right_x, bottom_right_y]
    type: str
    content: str


@dataclass
class Page:
    page_number: int
    width: float
    height: float
    words: list = field(default_factory=list)     # list[Word] -- bbox toujours présente côté natif ; côté OCR, bbox=None (seule la confiance est connue au niveau mot)
    blocks: list = field(default_factory=list)     # list[Block] -- granularité bloc, utilisé surtout côté OCR (et plus tard pour regrouper le natif)
    images: list = field(default_factory=list)     # list[Image]
    tables: list = field(default_factory=list)     # list[Table]
    fonts: list = field(default_factory=list)      # noms de police rencontrés sur la page
    metadata: dict = field(default_factory=dict)   # scores de diagnostic, décision d'enrichissement, etc.


@dataclass
class Document:
    source_path: str
    native: Optional[list] = None    # list[Page]
    ocr: Optional[list] = None       # list[Page] (même forme, rempli par ocr.py)
    resolved: Optional[list] = None  # list[Page] (rempli par resolve.py, plus tard)
    final: Optional[dict] = None     # sortie de render.py (contenu + format)

    # --- (dé)sérialisation --------------------------------------------------

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        def _pages(raw_pages):
            if raw_pages is None:
                return None
            pages = []
            for p in raw_pages:
                p = dict(p)
                p["words"] = [Word(**w) for w in p.get("words", [])]
                p["blocks"] = [Block(**b) for b in p.get("blocks", [])]
                p["images"] = [Image(**i) for i in p.get("images", [])]
                p["tables"] = [Table(**t) for t in p.get("tables", [])]
                pages.append(Page(**p))
            return pages

        return cls(
            source_path=data["source_path"],
            native=_pages(data.get("native")),
            ocr=_pages(data.get("ocr")),
            resolved=_pages(data.get("resolved")),
            final=data.get("final"),
        )

    def save(self, path):
        Path(path).write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, path):
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(data)

    # --- confort --------------------------------------------------------

    def needs_enrichment(self):
        """True si au moins une page natif signale un besoin d'enrichissement
        (metadata['needs_enrichment'], posé par extract.py via diagnostic.py)."""
        if not self.native:
            return True
        return any(p.metadata.get("needs_enrichment") for p in self.native)
