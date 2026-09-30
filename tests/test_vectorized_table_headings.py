from datacompiler.frontend.diagnostic.vector_text import zones_texte_vectorise_probable
from datacompiler.model.document import BBox, GraphicVector, GraphicsContainer, Page


def _page_with_heading_rows(backgrounds=False):
    graphics = GraphicsContainer()
    for row_top, row_bottom, count in ((12.0, 18.0, 8), (24.0, 32.0, 9)):
        for i in range(count):
            x0 = 30.0 + i * 4.0
            graphics.curves.append(
                GraphicVector(bbox=BBox(x0, row_top, x0 + 3.0, row_bottom))
            )

    if backgrounds:
        graphics.rects.extend([
            GraphicVector(bbox=BBox(15.0, 10.0, 180.0, 20.0), color="#b4c5e3"),
            GraphicVector(bbox=BBox(15.0, 20.0, 180.0, 38.0), color="#5d90c7"),
        ])
        graphics.lines.extend([
            GraphicVector(bbox=BBox(15.0, 10.0, 180.0, 10.0), color="#b4c5e3"),
            GraphicVector(bbox=BBox(15.0, 20.0, 180.0, 20.0), color="#5d90c7"),
            GraphicVector(bbox=BBox(15.0, 38.0, 180.0, 38.0), color="#5d90c7"),
        ])

    return Page(
        number=1,
        width=595.0,
        height=842.0,
        graphics=graphics,
    )


def test_table_backgrounds_do_not_merge_adjacent_heading_rows():
    zones = zones_texte_vectorise_probable(_page_with_heading_rows(backgrounds=True))

    assert len(zones) == 2
    assert [zone[1] for zone in zones] == [12.0, 24.0]


def test_uncolored_heading_rows_remain_detectable_without_backgrounds():
    zones = zones_texte_vectorise_probable(_page_with_heading_rows())

    assert len(zones) == 2
    assert [zone[1] for zone in zones] == [12.0, 24.0]
