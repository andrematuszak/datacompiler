"""verifier_couverture_tables.py -- Lecture seule. Vérifie si les tables
détectées (page.graphics.tables) couvrent réellement le contenu dense
qui fuit dans reading_order.py en tant que fausses "colonnes" (cas page 2
de test-impots-revenu : 23 colonnes détectées, alors que c'est un tableau
"Détail des revenus", pas une mise en page multi-colonnes).

Reproduit EXACTEMENT la logique de _dans_un_tableau (test au centre) pour
voir combien de mots natifs elle exclut réellement -- avant de blâmer
_colonnes_depuis_fragments pour un problème qui vient peut-être d'ici.

Usage : python verifier_couverture_tables.py fichier.document.json --page 2
"""
import argparse
import json


def _bbox(obj):
    b = obj.get("bbox")
    if not b:
        return None
    if isinstance(b, dict):
        return b["x0"], b["y0"], b["x1"], b["y1"]
    return tuple(b[:4])


def _dans_une_table(bbox, tables):
    if not bbox:
        return False
    x0, y0, x1, y1 = bbox
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    for t in tables:
        tb = _bbox(t)
        if tb and tb[0] <= cx <= tb[2] and tb[1] <= cy <= tb[3]:
            return True
    return False


def main():
    p = argparse.ArgumentParser()
    p.add_argument("json_path")
    p.add_argument("--page", type=int, default=1)
    args = p.parse_args()

    with open(args.json_path, encoding="utf-8") as f:
        doc = json.load(f)

    page = next((pg for pg in doc["pages"] if pg.get("number") == args.page), None)
    if page is None:
        print(f"Page {args.page} introuvable.")
        return

    tables = (page.get("graphics") or {}).get("tables", [])
    print(f"Page {args.page} -- {len(tables)} table(s) dans graphics.tables")
    for i, t in enumerate(tables):
        print(f"  table {i} : bbox={_bbox(t)}")

    mots = (page.get("native") or {}).get("words", [])
    dedans = sum(1 for w in mots if _dans_une_table(_bbox(w), tables))
    dehors = len(mots) - dedans
    print(f"\n{len(mots)} mots natifs au total")
    print(f"  {dedans} dans une table détectée (exclus par _dans_un_tableau)")
    print(f"  {dehors} hors table (candidats pour _colonnes_depuis_fragments)")

    if tables and dehors > 100:
        print("\n-> Des tables existent mais beaucoup de mots restent hors-table :")
        print("   la couverture des bbox est probablement insuffisante.")
    elif not tables:
        print("\n-> Aucune table dans graphics.tables malgré has_tables=True au diagnostic :")
        print("   la détection de table (pdfplumber.find_tables ou équivalent) a probablement")
        print("   échoué sur ce tableau précis (cf. limite connue : colonnes sans séparateurs")
        print("   verticaux). Piste : reading_order.py reçoit une grille de tableau comme du")
        print("   texte ordinaire, et _colonnes_depuis_fragments la lit -- à raison -- comme")
        print("   un vrai cas multi-colonnes.")


if __name__ == "__main__":
    main()
