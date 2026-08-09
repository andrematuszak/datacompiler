"""simulate_reading_order.py — Réimplémentation FIDÈLE (même algorithme,
mêmes seuils) de datacompiler/frontend/resolve/reading_order.py, en pur
Python sur des dicts, instrumentée pour tracer :
  - chaque ligne : pleine largeur ou non, et pourquoi (largeur vs seuil)
  - chaque appel de vider_tampons() : ce qu'il émet, dans quel ordre
  - la séquence finale de sortie, comparée (si possible) à
    page.resolved.words du même document.json, pour vérifier qu'on a bien
    reproduit le même ordre bugué -- pas juste une théorie plausible.

Lecture seule, aucune dépendance à datacompiler. Opère sur page.native.words
(l'ENTRÉE réelle de reading_order.ordonner(), y compris les mots injectés
par vector_zones.py -- PAS page.resolved.words, qui est déjà la SORTIE).

Reproduit aussi l'exclusion/réintégration des mots de table (graphics.tables)
de reading_order.ordonner() : le tri par colonnes ne voit que les mots hors
table, les mots de table sont réintégrés triés (y,x) à la fin. Sans ce filtre,
le calcul des frontières de colonnes tourne sur un ensemble de mots différent
de celui du vrai pipeline -- deux entrées différentes pour un algorithme
sensible aux seuils statistiques, donc deux résultats différents, pris à tort
pour un bug de reading_order.py plutôt qu'une désynchronisation du simulateur.

USAGE
-----
    python simulate_reading_order.py fichier.document.json --page 1
"""

import argparse
import json
from collections import Counter, defaultdict

BANDE_TOLERANCE = 5.0  # pt -- seuil d'écart y séparant deux bandes dynamiques (miroir du 5.0 codé en dur dans reading_order.py)
COOCCURRENCE_RATIO = 0.3  # part de hauteur occupée devant être en co-occurrence -- miroir de min_cooccurrence_ratio dans reading_order.py (le VRAI critère du filtre)
COOCCURRENCE_MIN = 3   # bandes partagées minimum -- utilisé UNIQUEMENT par l'affichage diagnostique post-hoc en fin de page (comptage brut, pas le critère du filtre lui-même)
MAX_COLONNES_PLAUSIBLE = 5  # garde-fou -- au-delà, presque toujours une fuite de tableau
# NB : ce garde-fou existe ici mais PAS dans reading_order.py au moment de la
# rédaction de ce fichier -- désynchronisation distincte, sans impact sur le
# cas présent (page 1, 1-2 colonnes détectées, bien sous le seuil de 5).


# ---------------------------------------------------------------- chargement

def _bbox(word):
    b = word.get("bbox")
    if not b:
        return None
    if isinstance(b, dict):
        return b["x0"], b["y0"], b["x1"], b["y1"]
    return tuple(b[:4])


def _charger_page(doc, page_number):
    for page in doc.get("pages", []):
        if page.get("number") == page_number:
            return page
    return None


def _mots_natifs(page):
    bruts = (page.get("native") or {}).get("words") or page.get("words") or []
    mots = []
    for w in bruts:
        bbox = _bbox(w)
        if not bbox:
            continue
        mots.append({
            "text": (w.get("text") or "").strip(),
            "x0": bbox[0], "y0": bbox[1], "x1": bbox[2], "y1": bbox[3],
            "source": w.get("source", "?"),
        })
    return mots


def _mots_resolus(page):
    bruts = (page.get("resolved") or {}).get("words") or []
    return [(w.get("text") or "").strip() for w in bruts]


def _tables(page):
    """Charge graphics.tables -- même source que reading_order._dans_un_tableau.
    Sans ça, le simulateur tourne sur 317 mots quand le vrai pipeline en
    exclut 49 (mots de table) avant même de calculer les frontières de
    colonnes : deux entrées différentes pour le même algorithme sensible
    aux seuils statistiques, donc deux frontières différentes -- pas une
    divergence d'algorithme, une divergence d'entrée."""
    graphics = page.get("graphics") or {}
    bruts = graphics.get("tables") or []
    tables = []
    for t in bruts:
        bbox = _bbox(t)
        if bbox:
            tables.append(bbox)
    return tables


def _dans_un_tableau(mot, tables):
    """Copie fidèle de reading_order._dans_un_tableau (test au centre du
    mot, pas au chevauchement de bbox)."""
    cx = (mot["x0"] + mot["x1"]) / 2
    cy = (mot["y0"] + mot["y1"]) / 2
    for (x0, y0, x1, y1) in tables:
        if x0 <= cx <= x1 and y0 <= cy <= y1:
            return True
    return False


# --------------------------------------------------- algorithme reproduit
# (copie fidèle de reading_order.py, adaptée aux dicts + instrumentation)

def _grouper_lignes_brutes(mots, tolerance_y=3.0):
    mots_tries = sorted(mots, key=lambda w: (w["y0"], w["x0"]))
    lignes, ligne_courante, y_courant = [], [], None
    for mot in mots_tries:
        y = mot["y0"]
        if y_courant is None or abs(y - y_courant) <= tolerance_y:
            ligne_courante.append(mot)
            y_courant = y if y_courant is None else y_courant
        else:
            lignes.append(ligne_courante)
            ligne_courante = [mot]
            y_courant = y
    if ligne_courante:
        lignes.append(ligne_courante)
    return lignes


def _seuil_bimodal(ecarts, plancher=2.0, frequence_min=3, facteur_relatif=1.5):
    valeurs = sorted(e for e in ecarts if e > 0)
    if len(valeurs) < 2:
        return plancher
    compte = Counter(round(v, 1) for v in valeurs)
    for i in range(len(valeurs) - 1):
        if valeurs[i] < plancher:
            continue
        if compte[round(valeurs[i], 1)] < frequence_min:
            continue
        if valeurs[i + 1] >= valeurs[i] * facteur_relatif:
            return (valeurs[i] + valeurs[i + 1]) / 2
    return plancher


def _ecart_mot_normal(lignes):
    ecarts = []
    for ligne in lignes:
        mots_tries = sorted(ligne, key=lambda w: w["x0"])
        for i in range(len(mots_tries) - 1):
            ecarts.append(mots_tries[i + 1]["x0"] - mots_tries[i]["x1"])
    return _seuil_bimodal(ecarts)


def _scinder_ligne(ligne, seuil):
    mots_tries = sorted(ligne, key=lambda w: w["x0"])
    fragments = [[mots_tries[0]]]
    for i in range(1, len(mots_tries)):
        if mots_tries[i]["x0"] - mots_tries[i - 1]["x1"] > seuil:
            fragments.append([])
        fragments[-1].append(mots_tries[i])
    return fragments


def _est_pleine_largeur(ligne, largeur_max_observee, tolerance=0.9):
    x0 = min(w["x0"] for w in ligne)
    x1 = max(w["x1"] for w in ligne)
    return (x1 - x0) >= largeur_max_observee * tolerance, (x1 - x0)


def _colonnes_depuis_fragments(lignes, marge_min=2.0, frequence_min=3,
                                bande_tolerance=BANDE_TOLERANCE, cooccurrence_ratio=COOCCURRENCE_RATIO):
    """CORRECTIF 3 (co-occurrence par bande y, remplace le test de
    chevauchement de segments du correctif précédent -- trop faible en
    pratique). Une vraie colonne se lit LIGNE PAR LIGNE en même temps
    qu'une autre -- le signal, c'est du contenu sur les MÊMES bandes
    horizontales, À RÉPÉTITION (une part suffisante -- cooccurrence_ratio --
    de sa hauteur occupée en chevauchement avec une autre frontière), pas
    "leurs étendues se croisent quelque part".

    Le correctif précédent (segments fusionnés + 'un point de contact
    suffit') a été testé et a ÉCHOUÉ : sur un document à une seule vraie
    colonne, la marge de gauche (colonne 0) touche presque tout par
    construction (n'importe quel bloc qui commence flush-left chevauche
    forcément sa portée à un moment) -- donc presque tout passait le test
    à tort, 6 colonnes toujours détectées après filtrage (vérifié
    empiriquement, aucun changement de frontières observé).

    Bandes DYNAMIQUES (dérivées des vraies coordonnées y du document, pas
    un bucket fixe de bande_tolerance pt) + validation par RATIO de hauteur
    en co-occurrence (pas un comptage brut de bandes partagées) -- copie
    fidèle du filtre 2 de reading_order.py, remplace une première version
    de ce simulateur qui utilisait un bucket fixe + comptage brut : plus
    permissive, elle gardait des frontières que le vrai pipeline rejette."""
    if not lignes:
        return [0.0]
    debuts_bruts = [round(min(w["x0"] for w in l), 1) for l in lignes]
    debuts_uniques = sorted(set(debuts_bruts))
    if len(debuts_uniques) == 1:
        return debuts_uniques

    ecarts = [debuts_uniques[i + 1] - debuts_uniques[i] for i in range(len(debuts_uniques) - 1)]
    seuil = _seuil_bimodal(ecarts, plancher=marge_min, frequence_min=1)

    frontieres_candidates = [debuts_uniques[0]]
    for i in range(len(debuts_uniques) - 1):
        if debuts_uniques[i + 1] - debuts_uniques[i] > seuil:
            frontieres_candidates.append(debuts_uniques[i + 1])

    apres_frequence = [
        f for f in frontieres_candidates
        if sum(1 for d in debuts_bruts if abs(d - f) <= marge_min) >= frequence_min
    ]
    if not apres_frequence:
        return [frontieres_candidates[0]]
    if len(apres_frequence) == 1:
        return apres_frequence

    # Regroupe chaque LIGNE (pas chaque mot) sous la frontière la plus
    # proche par valeur inférieure -- même logique que _colonne_de_fragment,
    # copie fidèle de groupes_lignes dans reading_order.py.
    groupes_lignes = defaultdict(list)
    for l in lignes:
        idx = _colonne_de_fragment(l, apres_frequence)
        groupes_lignes[apres_frequence[idx]].append(l)

    y_coords = set()
    for l in lignes:
        for w in l:
            y_coords.add(w["y0"])
            y_coords.add(w["y1"])
    y_sorted = sorted(y_coords)
    bandes = [(y_sorted[i], y_sorted[i + 1])
              for i in range(len(y_sorted) - 1)
              if y_sorted[i + 1] - y_sorted[i] > bande_tolerance]
    if not bandes:
        return [apres_frequence[0]]

    presence_par_bande = []
    for y_start, y_end in bandes:
        mid_y = (y_start + y_end) / 2
        presents = set()
        for f, groupe in groupes_lignes.items():
            for l in groupe:
                if any(w["y0"] <= mid_y <= w["y1"] for w in l):
                    presents.add(f)
                    break
        presence_par_bande.append(presents)

    valides = []
    for f in apres_frequence:
        hauteur_totale = sum(
            (max(w["y1"] for w in l) - min(w["y0"] for w in l))
            for l in groupes_lignes.get(f, [])
        )
        if hauteur_totale == 0:
            continue
        hauteur_en_cooccurrence = sum(
            (bandes[i][1] - bandes[i][0])
            for i, presents in enumerate(presence_par_bande)
            if f in presents and len(presents) > 1
        )
        if hauteur_en_cooccurrence / hauteur_totale >= cooccurrence_ratio:
            valides.append(f)

    # GARDE-FOU (pas une correction) : au-delà de MAX_COLONNES_PLAUSIBLE,
    # ce n'est presque jamais un vrai document multi-colonnes -- c'est un
    # tableau sans bordures qui a échappé à _dans_un_tableau (confirmé sur
    # page 2 de test-impots-revenu : 23 "colonnes" détectées sur un tableau
    # financier à pointillés ; graphics.tables ne couvrait que 32 mots sur
    # 332, les 2 tables détectées par pdfplumber.find_tables() se limitant
    # à l'en-tête de page). La vraie correction est en amont (détection de
    # tableaux sans séparateurs verticaux) -- ceci n'est qu'un filet de
    # sécurité en attendant. Seuil non calibré sur un cas multi-colonnes
    # réel au-delà du papier IEEE -- à revoir si un document légitime en
    # a besoin de plus. NB : absent de reading_order.py au moment de la
    # rédaction de ce fichier -- voir remarque en tête de module.
    if len(valides) > MAX_COLONNES_PLAUSIBLE:
        return [apres_frequence[0]]

    return valides or [apres_frequence[0]]


def _colonne_de_fragment(fragment, frontieres):
    x0 = min(w["x0"] for w in fragment)
    meilleur = 0
    for i, f in enumerate(frontieres):
        if f <= x0 + 1:
            meilleur = i
    return meilleur


def ordonner_instrumente(mots, verbose=True):
    lignes_brutes = _grouper_lignes_brutes(mots)
    seuil_scission = _ecart_mot_normal(lignes_brutes)

    lignes = []
    for l in lignes_brutes:
        lignes.extend(_scinder_ligne(l, seuil_scission))

    largeur_max_observee = max(
        (max(w["x1"] for w in l) - min(w["x0"] for w in l) for l in lignes),
        default=0.0,
    )
    frontieres = _colonnes_depuis_fragments(
        [l for l in lignes if not _est_pleine_largeur(l, largeur_max_observee)[0]]
    )

    if verbose:
        print(f"Seuil de scission (espacement normal vs colonne) : {seuil_scission:.1f} pt")
        print(f"Largeur de ligne la plus large observée : {largeur_max_observee:.1f} pt")
        print(f"Frontières de colonnes : {[round(f, 1) for f in frontieres]}\n")

    resultat = []
    tampons = {i: [] for i in range(len(frontieres))}
    numero_flush = [0]
    # Stats CUMULÉES sur toute la page (pas remises à zéro au flush) --
    # sert à vérifier si une "colonne" détectée s'étend en PARALLÈLE d'une
    # autre (vraie colonne, plages y qui se chevauchent) ou si c'est en
    # fait un bloc séquentiel qui ne fait que partager une indentation avec
    # un autre bloc plus bas/haut (plages y disjointes -- pas une colonne).
    stats_colonnes = {i: {"y_min": None, "y_max": None, "n": 0} for i in range(len(frontieres))}

    def vider_tampons(raison):
        numero_flush[0] += 1
        if verbose:
            tailles = {i: len(tampons[i]) for i in range(len(frontieres))}
            print(f"--- FLUSH #{numero_flush[0]} ({raison}) --- tailles par colonne : {tailles}")
        for i in range(len(frontieres)):
            trie = sorted(tampons[i], key=lambda w: (round(w["y0"] / 3), w["x0"]))
            if trie:
                ys = [w["y0"] for w in trie]
                s = stats_colonnes[i]
                s["y_min"] = min(ys) if s["y_min"] is None else min(s["y_min"], min(ys))
                s["y_max"] = max(ys) if s["y_max"] is None else max(s["y_max"], max(ys))
                s["n"] += len(trie)
            if verbose and trie:
                apercu = " ".join(w["text"] for w in trie[:6])
                print(f"    colonne {i} ({len(trie)} mots) : {apercu}{' ...' if len(trie) > 6 else ''}")
            resultat.extend(trie)
            tampons[i] = []

    for ligne in lignes:
        pleine, largeur = _est_pleine_largeur(ligne, largeur_max_observee)
        if pleine:
            if verbose:
                print(f"[pleine largeur] y0~{ligne[0]['y0']:.0f} largeur={largeur:.1f} "
                      f"texte=\"{' '.join(w['text'] for w in ligne)[:60]}\"")
            vider_tampons(f"ligne pleine largeur y0~{ligne[0]['y0']:.0f}")
            resultat.extend(sorted(ligne, key=lambda w: w["x0"]))
        else:
            idx = _colonne_de_fragment(ligne, frontieres)
            tampons[idx].extend(ligne)

    vider_tampons("fin de page")

    if verbose:
        print("\n--- Co-occurrence par bande y entre colonnes retenues ---")
        print(f"(bandes de {BANDE_TOLERANCE:.0f}pt, comptage brut -- affichage informatif "
              f"uniquement ; le filtre réel utilise un ratio de hauteur en co-occurrence, "
              f"cf. _colonnes_depuis_fragments)\n")
        bandes_par_col = {i: set() for i in range(len(frontieres))}
        for l in lignes:
            x0 = round(min(w["x0"] for w in l), 1)
            idx = _colonne_de_fragment(l, frontieres)
            for w in l:
                bandes_par_col[idx].add(round(w["y0"] / BANDE_TOLERANCE))
        actives = {i: b for i, b in bandes_par_col.items() if b}
        for i, b in actives.items():
            print(f"  colonne {i} : {len(b)} bandes occupées, n={stats_colonnes[i]['n']} mots")
        print()
        indices = list(actives)
        for a in range(len(indices)):
            for b_i in range(a + 1, len(indices)):
                i, j = indices[a], indices[b_i]
                partagees = len(bandes_par_col[i] & bandes_par_col[j])
                verdict = "coexistence confirmée" if partagees >= COOCCURRENCE_MIN else \
                          "pas assez de bandes communes -> probablement séquentiel"
                print(f"  colonne {i} vs colonne {j} : {partagees} bande(s) partagée(s) -- {verdict}")

    return resultat


# --------------------------------------------------------------------- main

def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("json_path")
    parser.add_argument("--page", type=int, default=1)
    parser.add_argument("--quiet", action="store_true", help="N'affiche que le résultat final, sans le détail des flush")
    args = parser.parse_args()

    with open(args.json_path, encoding="utf-8") as f:
        doc = json.load(f)

    page = _charger_page(doc, args.page)
    if page is None:
        print(f"Page {args.page} introuvable.")
        return

    mots = _mots_natifs(page)
    if not mots:
        print(f"Aucun mot natif trouvé pour la page {args.page}.")
        return

    tables = _tables(page)
    mots_dans_table = [w for w in mots if _dans_un_tableau(w, tables)]
    mots_hors_table = [w for w in mots if not _dans_un_tableau(w, tables)]

    print(f"Page {args.page} — {len(mots)} mots en entrée (native.words, OCR vectoriel inclus)")
    if tables:
        print(f"  {len(tables)} table(s) dans graphics.tables -- "
              f"{len(mots_dans_table)} mot(s) exclus du tri par colonnes, "
              f"{len(mots_hors_table)} candidat(s) pour _colonnes_depuis_fragments")
    print()

    # 2. Tri par colonnes UNIQUEMENT sur les mots hors table -- même entrée
    # que le vrai reading_order.ordonner(), pas les 317 mots bruts.
    resultat = ordonner_instrumente(mots_hors_table, verbose=not args.quiet)

    # 3. Réintégration des mots de table à la suite, triés (y,x) -- miroir
    # exact du bloc RÉINTÉGRATION de reading_order.ordonner().
    if mots_dans_table:
        mots_dans_table_tries = sorted(mots_dans_table, key=lambda w: (w["y0"], w["x0"]))
        if not args.quiet:
            print(f"--- RÉINTÉGRATION : {len(mots_dans_table_tries)} mot(s) de table, triés (y,x) ---")
            apercu = " ".join(w["text"] for w in mots_dans_table_tries[:10])
            print(f"    {apercu}{' ...' if len(mots_dans_table_tries) > 10 else ''}\n")
        resultat.extend(mots_dans_table_tries)

    print(f"\n=== ORDRE SIMULÉ (par notre réimplémentation) — {len(resultat)} mots ===")
    print(" ".join(w["text"] for w in resultat[:200]))

    reel = _mots_resolus(page)
    if reel:
        print(f"\n=== ORDRE RÉEL (page.resolved.words du JSON) — {len(reel)} mots ===")
        print(" ".join(reel[:200]))
        simule_txt = [w["text"] for w in resultat]
        if simule_txt == reel:
            print("\n>>> IDENTIQUE : la simulation reproduit exactement l'ordre réel. Mécanisme confirmé.")
        else:
            premiere_diff = next((i for i, (a, b) in enumerate(zip(simule_txt, reel)) if a != b), min(len(simule_txt), len(reel)))
            print(f"\n>>> DIFFÉRENT à partir de la position {premiere_diff} :")
            print(f"    simulé : ...{simule_txt[max(0,premiere_diff-3):premiere_diff+5]}")
            print(f"    réel   : ...{reel[max(0,premiere_diff-3):premiere_diff+5]}")
            print("    -> le mécanisme n'est pas encore le bon, ou une autre étape (typography.normaliser,")
            print("       alignment/conflict_resolution) modifie l'ordre après reading_order.")
    else:
        print("\n(page.resolved.words absent du JSON -- comparaison impossible, seul l'ordre simulé est affiché)")


if __name__ == "__main__":
    main()