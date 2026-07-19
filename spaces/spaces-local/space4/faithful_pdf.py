"""Renderer PDF fidèle: même apparence, couche texte résolue indépendante.

Le mode ``rasterized`` est le seul qui garantisse l'absence de l'ancienne
couche texte: il rend chaque page source en image haute définition puis pose
le texte résolu en mode invisible. Le mode ``overlay`` conserve le PDF source
vecteur mais ne doit être utilisé que pour compléter le texte, car sa couche
native reste présente.
"""

from pathlib import Path
import fitz
from document import Document


def _insert_invisible_words(page, words):
    for word in words:
        if not word.bbox or not word.output_text.strip():
            continue
        box = word.bbox
        size = word.font_size or max(4.0, box.y1 - box.y0)
        # render_mode=3 : texte présent dans le PDF, mais sans trace visuelle.
        page.insert_text((box.x0, box.y1), word.output_text, fontsize=size,
                         fontname="helv", render_mode=3, overlay=True)


def render_faithful_pdf(doc: Document, output_path: str, source_pdf: str = None,
                        strategy: str = "rasterized", dpi: int = 300) -> str:
    source_path = source_pdf or doc.metadata.source_pdf
    if not source_path:
        raise ValueError("Le chemin du PDF source est requis pour le rendu fidèle.")
    if strategy not in {"rasterized", "overlay"}:
        raise ValueError("strategy doit être 'rasterized' ou 'overlay'.")

    source = fitz.open(source_path)
    if len(source) != len(doc.pages):
        raise ValueError("Le PDF source et Document n'ont pas le même nombre de pages.")
    if strategy == "overlay":
        output = fitz.open(source_path)
        for page, model_page in zip(output, doc.pages):
            _insert_invisible_words(page, model_page.resolved.words)
    else:
        output = fitz.open()
        scale = dpi / 72.0
        matrix = fitz.Matrix(scale, scale)
        for source_page, model_page in zip(source, doc.pages):
            target = output.new_page(width=source_page.rect.width, height=source_page.rect.height)
            pix = source_page.get_pixmap(matrix=matrix, alpha=False)
            target.insert_image(target.rect, stream=pix.tobytes("png"))
            _insert_invisible_words(target, model_page.resolved.words)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    output.set_metadata({"producer": "DataCleaner faithful_pdf", "title": doc.metadata.filename})
    output.save(output_path, garbage=4, deflate=True)
    output.close()
    source.close()
    return output_path
