"""diagnostiquer_tounicode.py -- LECTURE SEULE, sur le PDF SOURCE (pas la
sortie). Vérifie si des mots manquants dans le JSON s'expliquent par un
/ToUnicode absent ou corrompu sur certaines polices -- pathologie
documentée par PyMuPDF lui-même : un glyphe peut s'afficher parfaitement
(le rendu ne dépend pas d'Unicode) tout en étant invisible à get_text()
(qui EN dépend entièrement). Dans ce cas, le mot n'existe nulle part dans
words_fitz = get_text("words") -- _ligne_correspondante ne peut rien y
faire, elle n'agit que sur des mots déjà trouvés par get_text("words").

Usage : python diagnostiquer_tounicode.py chemin/vers/fichier.pdf --page 1
"""
import argparse
import fitz


def main():
    p = argparse.ArgumentParser()
    p.add_argument("pdf_path")
    p.add_argument("--page", type=int, default=1)
    args = p.parse_args()

    doc = fitz.open(args.pdf_path)
    page = doc[args.page - 1]

    print(f"=== Polices de la page {args.page} ===")
    for font in page.get_fonts(full=True):
        xref, ext, ftype, basefont, name = font[0], font[1], font[2], font[3], font[4]
        encoding = font[5] if len(font) > 5 else "?"
        prefixe = basefont.split("+")[0] if "+" in basefont else ""
        sous_ensemble = len(prefixe) == 6 and prefixe.isupper()
        suspect = ftype == "Type0" and "Identity" in str(encoding)
        marqueur = ""
        if suspect:
            marqueur = "  <-- SUSPECTE (CID Identity-H" + (", sous-ensemble)" if sous_ensemble else ")")
        print(f"  xref={xref} basefont={basefont!r} type={ftype} encoding={encoding}{marqueur}")

    texte = page.get_text("text")
    n_casses = texte.count("\ufffd")
    print(f"\n=== Caractères U+FFFD (mapping Unicode cassé) dans get_text('text') ===")
    print(f"{n_casses} occurrence(s) trouvée(s)")

    if n_casses:
        idx, compte = 0, 0
        while compte < 10:
            idx = texte.find("\ufffd", idx)
            if idx == -1:
                break
            debut, fin = max(0, idx - 20), min(len(texte), idx + 20)
            print(f"  ...{texte[debut:idx]!r} [U+FFFD] {texte[idx + 1:fin]!r}...")
            idx += 1
            compte += 1
        print("\n-> Confirmé : au moins une police de ce PDF n'a pas de /ToUnicode exploitable.")
        print("   Le rendu visuel n'est PAS affecté -- seule l'extraction échoue. Ce n'est pas")
        print("   un bug de pymupdf.py, c'est une limite du PDF source lui-même (confirmé par")
        print("   la doc officielle PyMuPDF). Seule solution : OCR ciblé sur cette zone -- mais")
        print("   vector_text.py ne la détectera JAMAIS, il ne regarde que les tracés dessinés")
        print("   (lignes/courbes/rects), pas les échecs de mapping sur du vrai texte de police.")
    else:
        print("\n-> Aucun U+FFFD détecté sur cette page en mode 'text'.")
        print("   Si get_text('words') omet quand même des mots que 'text' contient, la cause")
        print("   est probablement un filtrage propre au mode 'words' (jetons jugés invalides),")
        print("   pas un /ToUnicode cassé -- à creuser séparément si ce cas se présente.")

    doc.close()


if __name__ == "__main__":
    main()
