"""
document.py — Modèle objet unifié.
Remplace les dictionnaires volants par des objets typés et intelligents.
"""

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
    def from_dict(cls, d: Dict[str, Any]) -> Optional['BBox']:
        if not d: return None
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
    confidence: Optional[float] = None
    language: Optional[str] = None
    source: Optional[str] = None
    is_corrected: bool = False
    replacement: Optional[str] = None
    notes: List[str] = field(default_factory=list)

@dataclass
class Font:
    name: str
    sizes: List[float] = field(default_factory=list)

@dataclass
class NativeContainer:
    words: List[Word] = field(default_factory=list)
    fonts: List[Font] = field(default_factory=list)

@dataclass
class ImageElement:
    id: int
    bbox: Optional[BBox] = None
    width: Optional[int] = None
    height: Optional[int] = None

@dataclass
class TableElement:
    id: int
    bbox: Optional[BBox] = None
    source: str = "pdfplumber"
    rows: List[List[str]] = field(default_factory=list)

@dataclass
class GraphicVector:
    bbox: Optional[BBox] = None

@dataclass
class GraphicsContainer:
    images: List[ImageElement] = field(default_factory=list)
    tables: List[TableElement] = field(default_factory=list)
    lines: List[GraphicVector] = field(default_factory=list)
    rects: List[GraphicVector] = field(default_factory=list)
    curves: List[GraphicVector] = field(default_factory=list)

@dataclass
class OcrContainer:
    engine: Optional[str] = None
    words: List[Word] = field(default_factory=list)

@dataclass
class ResolvedContainer:
    words: List[Word] = field(default_factory=list)

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

@dataclass
class Diagnostic:
    recommend_ocr: bool = False
    notes: List[str] = field(default_factory=list)

@dataclass
class Document:
    metadata: Metadata = field(default_factory=Metadata)
    diagnostic: Diagnostic = field(default_factory=Diagnostic)
    pages: List[Page] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)

    def save(self, path: str):
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.to_json())