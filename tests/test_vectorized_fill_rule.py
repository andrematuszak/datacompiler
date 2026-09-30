import numpy as np
import pymupdf

from datacompiler.backend.rebuilt_pdf import _copier_images_et_dessins


def test_reconstruire_conserve_le_remplissage_even_odd():
    source_doc = pymupdf.open()
    source_page = source_doc.new_page(width=40, height=40)
    shape = source_page.new_shape()
    shape.draw_rect(pymupdf.Rect(5, 5, 35, 35))
    shape.draw_rect(pymupdf.Rect(15, 15, 25, 25))
    shape.finish(fill=(0, 0, 0), even_odd=True)
    shape.commit()

    output_doc = pymupdf.open()
    output_page = output_doc.new_page(width=40, height=40)
    _copier_images_et_dessins(source_page, output_page, {})

    assert output_page.get_drawings()[0]["even_odd"] is True
    source_pixels = np.frombuffer(source_page.get_pixmap(alpha=False).samples, dtype=np.uint8)
    output_pixels = np.frombuffer(output_page.get_pixmap(alpha=False).samples, dtype=np.uint8)
    assert np.array_equal(source_pixels, output_pixels)

    output_doc.close()
    source_doc.close()
