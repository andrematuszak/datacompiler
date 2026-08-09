"""verifier_mot_perdu.py -- LECTURE SEULE. Teste l'hypothèse : un mot
existe dans native.words mais disparaît de resolved.words parce que
_dans_un_tableau (reading_order.py) l'exclut comme appartenant à une
table détectée -- sans qu'aucun mécanisme de structuration de tableau
(resolved.tables) ne le récupère ensuite (cf. docstring de
reading_order.py : suppose ce relais déjà construit, ce qui n'est pas
encore le cas -- "tables structurées" reste une piste roadmap).

Usage : python verifier_mot_perdu.py fichier.document.json --page 1 --texte "virement"
"""
import argparse
import json


def _bbox(o):
    b = o.get("bbox")
    if not b:
        return None
    if isinstance(b, dict):
        return b["x0"], b["y0"], b["x1"], b["y1"]
    return tuple(b[:4])


def _centre(b):
    return (b[0] + b[2]) / 2, (b[1] + b[3]) / 2


def main():
    p = argparse.ArgumentParser()
    p.add_argument("json_path")
    p.add_argument("--page", type=int, default=1)
    p.add_argument("--texte", required=True)
    args = p.parse_args()

    with open(args.json_path, encoding="utf-8") as f:
        doc = json.load(f)

    page = next((pg for pg in doc["pages"] if pg.get("number") == args.page), None)
    if page is None:
        print(f"Page {args.page} introuvable.")
        return

    native = (page.get("native") or {}).get("words", [])
    resolved = (page.get("resolved") or {}).get("words", [])
    tables = (page.get("graphics") or {}).get("tables", [])

    natif_trouve = [w for w in native if args.texte.lower() in (w.get("text") or "").lower()]
    resolu_trouve = [w for w in resolved if args.texte.lower() in (w.get("output_text") or w.get("text") or "").lower()]

    print(f"'{args.texte}' dans native.words   : {len(natif_trouve)} occurrence(s)")
    print(f"'{args.texte}' dans resolved.words : {len(resolu_trouve)} occurrence(s)")
    print(f"{len(tables)} table(s) détectée(s) sur cette page\n")

    if natif_trouve and not resolu_trouve:
        print(">>> CONFIRMÉ : présent en natif, absent du résolu -- perdu quelque part entre les deux.\n")

    for w in natif_trouve:
        b = _bbox(w)
        print(f"  natif : \"{w.get('text')}\" bbox={b}")
        if not b:
            continue
        cx, cy = _centre(b)
        for i, t in enumerate(tables):
            tb = _bbox(t)
            if tb and tb[0] <= cx <= tb[2] and tb[1] <= cy <= tb[3]:
                print(f"    -> tombe DANS la table {i} (bbox={tb}) -- probablement exclu par "
                      f"_dans_un_tableau dans reading_order.py, sans relais resolved.tables")


if __name__ == "__main__":
    main()
