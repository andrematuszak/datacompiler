"""
document.py — Modèle objet unifié pour l'ensemble du pipeline.
Gère la structure en mémoire et la sérialisation/désérialisation JSON.
"""

from __future__ import annotations
import json
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any


@dataclass
class BBox:
    x0: float
    y0: float
    x1: float
    y1: float

    def to_dict(self) -> Dict[str, float]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> Optional[BBox]:
        if not d:
            return None
        return cls(x0=float(d["x0"]), y0=float(d["y0"]), x1=float(d["x1"]), y1=float(d["y1"]))


@dataclass
class Word:
    id: int
    text: str
    bbox: Optional[BBox] = None
    block: int = 0
    line: int = 0
    word: int = 0
    font: str = "Unknown"
    font_size: float = 0.0
    bold: bool = False
    italic: bool = False
    color: str = "#000000"
    rotation: float = 0.0
    
    # Paramètres d'extensibilité futurs pour l'OCR et le Résolveur
    confidence: Optional[float] = None
    language: Optional[str] = None
    source: Optional[str] = None  # "native" | "mistral"
    is_corrected: bool = False
    replacement: Optional[str] = None
    notes: List[str] = field(default_factory=list)


@dataclass
class Character:
    char: str
    bbox: Optional[BBox] = None
    font: str = "Unknown"
    font_size: float = 0.0


@dataclass
class Font:
    name: str
    sizes: List[float] = field(default_factory=list)


@dataclass
class NativeContainer:
    words: List[Word] = field(default_factory=list)
    chars: List[Character] = field(default_factory=list)
    fonts: List[Font] = field(default_factory=list)


@dataclass
class ImageElement:
    id: int
    bbox: Optional[BBox] = None
    width: Optional[int] = None
    height: Optional[int] = None
    dpi: Optional[int] = None
    contains_text: Optional[bool] = None
    ocr_needed: Optional[bool] = None
    description: Optional[str] = None


@dataclass
class TableElement:
    id: int
    bbox: Optional[BBox] = None
    source: str = "pdfplumber"
    confidence: Optional[float] = None
    rows: List[List[str]] = field(default_factory=list)  # Stockage des données extraites


@dataclass
class GraphicVector:
    bbox: Optional[BBox] = None
    pts: List[tuple] = field(default_factory=list)  # Pour stocker les points complexes si besoin


@dataclass
class GraphicsContainer:
    images: List[ImageElement] = field(default_factory=list)
    tables: List[TableElement] = field(default_factory=list)
    lines: List[GraphicVector] = field(default_factory=list)
    rects: List[GraphicVector] = field(default_factory=list)
    curves: List[GraphicVector] = field(default_factory=list)


@dataclass
class OcrBlock:
    bbox: Optional[BBox] = None
    type: str = "paragraph"
    content: str = ""


@dataclass
class OcrContainer:
    engine: Optional[str] = None
    words: List[Word] = field(default_factory=list)
    blocks: List[OcrBlock] = field(default_factory=list)


@dataclass
class ResolvedContainer:
    words: List[Word] = field(default_factory=list)
    tables: List[TableElement] = field(default_factory=list)
    images: List[ImageElement] = field(default_factory=list)


@dataclass
class Page:
    number: int
    width: float
    height: float
    rotation: float = 0.0
    native: NativeContainer = field(default_factory=NativeContainer)
    graphics: GraphicsContainer = field(default_factory=GraphicsContainer)
    ocr: OcrContainer = field(default_factory=OcrContainer)
    resolved: ResolvedContainer = field(default_factory=ResolvedContainer)


@dataclass
class Metadata:
    filename: str = ""
    page_count: int = 0
    producer: str = ""
    creator: str = ""
    creation_date: str = ""
    modification_date: str = ""
    pdf_version: str = ""
    encrypted: bool = False


@dataclass
class Diagnostic:
    has_native_text: bool = False
    has_images: bool = False
    has_tables: bool = False
    has_full_page_images: bool = False
    embedded_ocr_detected: bool = False
    reading_order_score: Optional[float] = None
    native_text_quality: Optional[float] = None
    image_quality: Optional[float] = None
    recommend_ocr: bool = False
    notes: List[str] = field(default_factory=list)


@dataclass
class Document:
    metadata: Metadata = field(default_factory=Metadata)
    diagnostic: Diagnostic = field(default_factory=Diagnostic)
    pages: List[Page] = field(default_factory=list)

    # --- Méthodes de Sérialisation ---

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)

    def save(self, path: str):
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.to_json())

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> Document:
        doc = cls()
        
        # Metadata
        if "metadata" in d:
            doc.metadata = Metadata(**d["metadata"])
            
        # Diagnostic
        if "diagnostic" in d:
            doc.diagnostic = Diagnostic(**d["diagnostic"])
            
        # Pages
        if "pages" in d:
            for p in d["pages"]:
                page_obj = Page(
                    number=p["number"], width=p["width"], height=p["height"], rotation=p.get("rotation", 0.0)
                )
                
                # Native
                if "native" in p:
                    nat = p["native"]
                    page_obj.native.fonts = [Font(**f) for f in nat.get("fonts", [])]
                    page_obj.native.chars = [
                        Character(char=c["char"], bbox=BBox.from_dict(c.get("bbox", {})), font=c.get("font", ""), font_size=c.get("font_size", 0.0))
                        for c in nat.get("chars", [])
                    ]
                    page_obj.native.words = [
                        Word(
                            id=w["id"], text=w["text"], bbox=BBox.from_dict(w.get("bbox", {})),
                            block=w.get("block", 0), line=w.get("line", 0), word=w.get("word", 0),
                            font=w.get("font", ""), font_size=w.get("font_size", 0.0),
                            bold=w.get("bold", False), italic=w.get("italic", False),
                            color=w.get("color", ""), rotation=w.get("rotation", 0.0),
                            confidence=w.get("confidence"), language=w.get("language"), source=w.get("source"),
                            is_corrected=w.get("is_corrected", False), replacement=w.get("replacement"), notes=w.get("notes", [])
                        )
                        for w in nat.get("words", [])
                    ]
                
                # Graphics
                if "graphics" in p:
                    g = p["graphics"]
                    page_obj.graphics.images = [
                        ImageElement(
                            id=img["id"], bbox=BBox.from_dict(img.get("bbox", {})),
                            width=img.get("width"), height=img.get("height"), dpi=img.get("dpi"),
                            contains_text=img.get("contains_text"), ocr_needed=img.get("ocr_needed"), description=img.get("description")
                        ) for img in g.get("images", [])
                    ]
                    page_obj.graphics.tables = [
                        TableElement(
                            id=t["id"], bbox=BBox.from_dict(t.get("bbox", {})),
                            source=t.get("source", "pdfplumber"), confidence=t.get("confidence"), rows=t.get("rows", [])
                        ) for t in g.get("tables", [])
                    ]
                    page_obj.graphics.lines = [GraphicVector(bbox=BBox.from_dict(v.get("bbox", {}))) for v in g.get("lines", [])]
                    page_obj.graphics.rects = [GraphicVector(bbox=BBox.from_dict(v.get("bbox", {}))) for v in g.get("rects", [])]
                    page_obj.graphics.curves = [GraphicVector(bbox=BBox.from_dict(v.get("bbox", {}))) for v in g.get("curves", [])]

                # OCR
                if "ocr" in p:
                    ocr = p["ocr"]
                    page_obj.ocr.engine = ocr.get("engine")
                    page_obj.ocr.blocks = [
                        OcrBlock(bbox=BBox.from_dict(b.get("bbox", {})), type=b.get("type", ""), content=b.get("content", ""))
                        for b in ocr.get("blocks", [])
                    ]
                    page_obj.ocr.words = [
                        Word(id=w["id"], text=w["text"], bbox=BBox.from_dict(w.get("bbox", {})))
                        for w in ocr.get("words", [])
                    ]

                # Resolved
                if "resolved" in p:
                    res = p["resolved"]
                    page_obj.resolved.words = [
                        Word(id=w["id"], text=w["text"], bbox=BBox.from_dict(w.get("bbox", {})))
                        for w in res.get("words", [])
                    ]
                    # Deserialisation basique tables/images si presents
                    page_obj.resolved.tables = [
                        TableElement(id=t["id"], bbox=BBox.from_dict(t.get("bbox", {}))) for t in res.get("tables", [])
                    ]
                    page_obj.resolved.images = [
                        ImageElement(id=img["id"], bbox=BBox.from_dict(img.get("bbox", {}))) for img in res.get("images", [])
                    ]

                doc.pages.append(page_obj)
        return doc

    @classmethod
    def load(cls, path: str) -> Document:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)