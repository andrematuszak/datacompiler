#!/usr/bin/env python3
"""probe_pymupdf_api.py — À LANCER EN PREMIER, avant faithful_pdf_clean_overlay.py.

Pourquoi ce script existe : la forme exacte des tuples retournés par
page.get_fonts(), doc.extract_font() et doc.extract_image() a changé entre
versions de PyMuPDF, et je n'ai pas pu tester le code principal contre une
vraie installation ni un vrai PDF dans cette session (pas de réseau pour
installer `fitz`, pas de PDF source disponible). Plutôt que de te livrer du
code qui suppose une forme de tuple non vérifiée, ce script imprime la
forme RÉELLE sur ton environnement et ton document, pour que tu puisses
confirmer (ou corriger) les indices utilisés dans _extraire_polices() avant
de lancer quoi que ce soit sur le vrai pipeline.

USAGE
-----
    python probe_pymupdf_api.py chemin/vers/test-impots-revenu.pdf
"""

import sys

import fitz


def main():
    if len(sys.argv) < 2:
        print("Usage: python probe_pymupdf_api.py chemin/vers/document.pdf")
        return

    chemin = sys.argv[1]
    doc = fitz.open(chemin)
    print(f"PyMuPDF version : {fitz.version}\n")

    for i, page in enumerate(doc):
        print(f"=== Page {i + 1} ===")

        # --- Polices ---
        polices = page.get_fonts(full=True)
        print(f"{len(polices)} police(s) via get_fonts(full=True) :")
        for p in polices:
            print(f"  tuple brut ({len(p)} éléments) : {p}")
            xref = p[0]
            try:
                extrait = doc.extract_font(xref)
                print(f"    extract_font({xref}) -> type={type(extrait).__name__}, "
                      f"longueur={len(extrait) if hasattr(extrait, '__len__') else '?'}")
                if isinstance(extrait, (tuple, list)):
                    for j, champ in enumerate(extrait):
                        apercu = (repr(champ)[:80] + "...") if isinstance(champ, (bytes, str)) and len(repr(champ)) > 80 else repr(champ)
                        print(f"      [{j}] {type(champ).__name__} = {apercu}")
            except Exception as exc:
                print(f"    extract_font({xref}) a levé : {exc!r}")
        print()

        # --- Images ---
        images = page.get_images(full=True)
        print(f"{len(images)} image(s) via get_images(full=True) :")
        for im in images[:3]:  # 3 suffisent pour voir la forme
            print(f"  tuple brut ({len(im)} éléments) : {im}")
            xref = im[0]
            try:
                rects = page.get_image_rects(xref)
                print(f"    get_image_rects({xref}) -> {rects}")
            except Exception as exc:
                print(f"    get_image_rects({xref}) a levé : {exc!r}")
            try:
                extrait = doc.extract_image(xref)
                print(f"    extract_image({xref}) -> type={type(extrait).__name__}, "
                      f"clés={list(extrait.keys()) if isinstance(extrait, dict) else '?'}")
            except Exception as exc:
                print(f"    extract_image({xref}) a levé : {exc!r}")
        if len(images) > 3:
            print(f"  ... ({len(images) - 3} de plus, non affichées)")
        print()

        # --- Dessins vectoriels : types d'items rencontrés ---
        dessins = page.get_drawings()
        types_items = {}
        for d in dessins:
            for item in d.get("items", []):
                types_items[item[0]] = types_items.get(item[0], 0) + 1
        print(f"{len(dessins)} dessin(s) via get_drawings() -- types d'items rencontrés : {types_items}")
        if dessins:
            print(f"  clés d'un dessin type : {list(dessins[0].keys())}")
        print()

    doc.close()


if __name__ == "__main__":
    main()
