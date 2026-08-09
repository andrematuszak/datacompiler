#!/usr/bin/env python3
"""Prototype : ordre de lecture par BOÎTES DÉLIMITÉES plutôt que par colonnes.

Principe :
1. Construire des "boîtes" (régions rectangulaires) :
   - natif : le champ `block` de pymupdf donne déjà un découpage gratuit,
     dérivé de la structure réelle du PDF source.
   - vectorisé/reconstruit : pas de `block` exploitable -> on cluster les
     mots par proximité géométrique (union-find sur chevauchement de bbox
     dilatée), à l'identique du principe déjà utilisé dans
     vector_text.py::_grouper_par_proximite pour fusionner les zones.
2. Regrouper les boîtes en RANGÉES par chevauchement vertical significatif
   (sweep trié par y0, extension de plage tant que le chevauchement dépasse
   un seuil) -- généralisation de grouper_par_ligne au niveau boîte plutôt
   que mot.
3. Trier chaque rangée par x0 croissant (gauche -> droite), concaténer les
   rangées dans l'ordre (haut -> bas).

Aucune notion de "colonne globale" : une rangée à 1 boîte = comportement
page normale ; une rangée à N boîtes = les N boîtes sont lues côte à côte
sur ce même palier vertical, peu importe qu'elles fassent partie d'un
"vrai" système de colonnes de texte ou soient juste deux encarts courts
positionnés l'un à côté de l'autre.
"""

import argparse
import json
from collections import defaultdict


SEUIL_CHEVAUCHEMENT_RANGEE = 0.3   # fraction de la + petite hauteur, pour dire "même rangée"
DILATATION_CLUSTERING_VECTO = 8.0  # pt, marge de tolérance pour fusionner des mots vectorisés proches
TOLERANCE_LIGNE = 3.5              # pt, écart de y0 toléré pour dire "même ligne" (bruit OCR)


def _grouper_lignes_par_tolerance(mots, tolerance):
    """Regroupe des mots en lignes (liste de LISTES, pas encore aplatie)
    par tolérance sur y0 -- coeur commun réutilisé à deux endroits :
    1. grouper_par_ligne_tolerant() : tri final à l'intérieur d'une boîte.
    2. construire_boites_natives() : découpage d'un bloc pymupdf en boîtes
       une-ligne AVANT le regroupement en rangées, pas seulement au moment
       du tri -- nécessaire depuis la découverte qu'un bloc pymupdf peut
       couvrir un paragraphe multi-lignes entier (ex. 90pt, 7 lignes), qui,
       laissé en une seule boîte, absorbe dans sa rangée plusieurs petites
       boîtes concurrentes en face (ex. une colonne de montants, une ligne
       par valeur) -- le tri par x0 à l'intérieur de la rangée n'a alors
       plus l'info verticale pour les remettre dans le bon ordre. Confirmé
       empiriquement sur N5 (paragraphe "Détail des revenus") vs
       N21..N26 (montants) : sortie N24|N21|N26|N22|N23|N25, alors que
       l'ordre vertical réel est N21->N22->N23->N24->N25->N26.
       (block, line) de pymupdf a été testé pour ce même besoin et écarté :
       line=0 uniforme même sur un bloc de taille normale (90pt, 30 mots)
       dès qu'il y a des pointillés de tabulation sur ce document -- pas
       fiable ici, d'où le repli sur la tolérance géométrique."""
    mots_tries = sorted(mots, key=lambda m: m["bbox"]["y0"])
    lignes = []
    ligne_courante = []
    y_ref = None
    for m in mots_tries:
        y0 = m["bbox"]["y0"]
        if ligne_courante and abs(y0 - y_ref) <= tolerance:
            ligne_courante.append(m)
        else:
            if ligne_courante:
                lignes.append(ligne_courante)
            ligne_courante = [m]
            y_ref = y0
    if ligne_courante:
        lignes.append(ligne_courante)
    return lignes


def grouper_par_ligne_tolerant(mots, tolerance=TOLERANCE_LIGNE):
    """Regroupe des mots en lignes par tolérance sur y0 (pas un tri brut sur
    y0), puis trie chaque ligne par x0. Évite qu'un micro-écart de y0
    (imprécision OCR sur des mots de la MÊME ligne visuelle, ex. 19.7 vs
    21.4) ne fasse passer un mot de droite avant un mot de gauche."""
    lignes = _grouper_lignes_par_tolerance(mots, tolerance)
    resultat = []
    for ligne in lignes:
        resultat.extend(sorted(ligne, key=lambda m: m["bbox"]["x0"]))
    return resultat


def texte_affiche(m):
    return m.get("resolved_text") or m.get("replacement") or m.get("text") or ""


def _charger_page(doc, page_number):
    """Recherche par champ `number` d'abord (cohérent avec
    simulate_reading_order.py), repli sur l'index de liste si absent."""
    for page in doc.get("pages", []):
        if page.get("number") == page_number:
            return page
    pages = doc.get("pages", [])
    idx = page_number - 1
    if 0 <= idx < len(pages):
        return pages[idx]
    return None


# ---------------------------------------------------------------------------
# 1. Construction des boîtes
# ---------------------------------------------------------------------------

class Boite:
    __slots__ = ("id", "x0", "y0", "x1", "y1", "mots", "origine")

    def __init__(self, id_, mots, origine):
        self.id = id_
        self.mots = mots
        self.origine = origine
        self.x0 = min(m["bbox"]["x0"] for m in mots)
        self.y0 = min(m["bbox"]["y0"] for m in mots)
        self.x1 = max(m["bbox"]["x1"] for m in mots)
        self.y1 = max(m["bbox"]["y1"] for m in mots)

    def __repr__(self):
        apercu = " ".join(texte_affiche(m) for m in self.mots[:5])
        return (f"Boite#{self.id} [{self.origine}] y=({self.y0:.1f}-{self.y1:.1f}) "
                f"x=({self.x0:.1f}-{self.x1:.1f}) n={len(self.mots)} \"{apercu}...\"")


def construire_boites_natives(mots_natifs, tolerance_ligne=TOLERANCE_LIGNE):
    """Une boîte par LIGNE physique à l'intérieur de chaque bloc pymupdf,
    pas une boîte par bloc entier -- voir le docstring de
    _grouper_lignes_par_tolerance pour le bug concret que ça corrige.
    Pour un paragraphe qui n'est en concurrence avec rien sur sa plage y
    (le cas normal), chaque ligne redevient sa propre rangée à une seule
    boîte, lue séquentiellement -- comportement inchangé. Le changement ne
    joue que là où un bloc large chevauche plusieurs petites boîtes
    concurrentes, exactement le cas qu'on veut corriger."""
    par_block = defaultdict(list)
    for m in mots_natifs:
        par_block[m["block"]].append(m)
    boites = []
    for bid, mots in par_block.items():
        lignes = _grouper_lignes_par_tolerance(mots, tolerance_ligne)
        for i, ligne in enumerate(lignes):
            boites.append(Boite(f"N{bid}L{i}", ligne, "native"))
    return boites


class UnionFind:
    def __init__(self, n):
        self.parent = list(range(n))

    def find(self, x):
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb


def chevauche_dilate(a, b, marge):
    return not (a["bbox"]["x1"] + marge < b["bbox"]["x0"] or
                a["bbox"]["x0"] - marge > b["bbox"]["x1"] or
                a["bbox"]["y1"] + marge < b["bbox"]["y0"] or
                a["bbox"]["y0"] - marge > b["bbox"]["y1"])


def construire_boites_vectorisees(mots_vecto, marge=DILATATION_CLUSTERING_VECTO, tolerance_ligne=TOLERANCE_LIGNE):
    """Le clustering union-find regroupe des mots proches en une même ZONE
    OCR (ex. un encart de 4 lignes de références empilées) -- légitime en
    soi, mais si on laisse la zone entière comme UNE boîte, elle subit le
    même problème que N5 côté natif : une boîte multi-lignes qui absorbe
    dans sa rangée plusieurs petites boîtes concurrentes en face, perdant
    l'info verticale pour les remettre dans le bon ordre. Confirmé
    empiriquement sur V12 (page 1, "Numéro FIP / Numéro rôle / Date
    d'établissement / Date mise en recouvrement" fusionnés en une seule
    boîte de 40pt, flaggé par diagnostiquer_absorption avec un ratio 3.2x
    face à N7L0). Donc : cluster par proximité pour DÉCIDER quels mots
    appartiennent à la même zone, puis redécoupe cette zone en lignes
    (même logique que côté natif) avant de créer les boîtes finales."""
    n = len(mots_vecto)
    if n == 0:
        return []
    uf = UnionFind(n)
    for i in range(n):
        for j in range(i + 1, n):
            if chevauche_dilate(mots_vecto[i], mots_vecto[j], marge):
                uf.union(i, j)

    groupes = defaultdict(list)
    for i in range(n):
        groupes[uf.find(i)].append(mots_vecto[i])

    boites = []
    for i, (racine, mots) in enumerate(groupes.items()):
        lignes = _grouper_lignes_par_tolerance(mots, tolerance_ligne)
        for j, ligne in enumerate(lignes):
            boites.append(Boite(f"V{i}L{j}", ligne, "vectorized"))
    return boites


# ---------------------------------------------------------------------------
# 2. Regroupement en rangées + tri gauche->droite
# ---------------------------------------------------------------------------

def chevauchement_vertical(a, b):
    inter = min(a.y1, b.y1) - max(a.y0, b.y0)
    if inter <= 0:
        return 0.0
    plus_petite_hauteur = min(a.y1 - a.y0, b.y1 - b.y0)
    if plus_petite_hauteur <= 0:
        return 0.0
    return inter / plus_petite_hauteur

def nombre_lignes_boite(boite, tolerance=TOLERANCE_LIGNE):
    lignes = _grouper_lignes_par_tolerance(boite.mots, tolerance)
    return len(lignes)

def diagnostiquer_absorption(
    rangees,
    seuil_ratio=3.0,
    tolerance_ligne=TOLERANCE_LIGNE,
):
    """
    Signale les différences de hauteur importantes dans une rangée.

    Une boîte multi-lignes est signalée comme candidat légitime plutôt que
    comme absorption certaine.
    """
    alertes = []

    for i, rangee in enumerate(rangees):
        if len(rangee) < 2:
            continue

        infos = []

        for boite in rangee:
            hauteur = hauteur_boite(boite)
            nb_lignes = nombre_lignes_boite(boite, tolerance_ligne)
            hauteur_moyenne = hauteur / max(nb_lignes, 1)

            infos.append({
                "boite": boite,
                "hauteur": hauteur,
                "nb_lignes": nb_lignes,
                "hauteur_moyenne": hauteur_moyenne,
            })

        h_max = max(info["hauteur"] for info in infos)
        h_min = min(info["hauteur"] for info in infos)

        if h_min <= 0 or h_max / h_min < seuil_ratio:
            continue

        grosse = max(infos, key=lambda info: info["hauteur"])
        petite = min(infos, key=lambda info: info["hauteur"])

        alertes.append({
            "rangee": i,
            "grosse": grosse,
            "petite": petite,
            "ratio": h_max / h_min,
            "multi_lignes": grosse["nb_lignes"] > 1,
        })

    return alertes

TOLERANCE_RANGEE = 4.0


def centre_vertical(boite):
    return (boite.y0 + boite.y1) / 2.0


def hauteur_boite(boite):
    return max(0.0, boite.y1 - boite.y0)


def meme_rangee(boite, rangee, tolerance=TOLERANCE_RANGEE):
    """
    Détermine si une boîte appartient à une rangée existante.

    On compare le centre vertical avec le centre représentatif de la rangée,
    au lieu d'utiliser un chevauchement transitif entre toutes les boîtes.
    """
    if not rangee:
        return False

    centres = [centre_vertical(b) for b in rangee]
    centre_rangee = sorted(centres)[len(centres) // 2]

    return abs(centre_vertical(boite) - centre_rangee) <= tolerance


def ordonner_par_boites(boites, tolerance=TOLERANCE_RANGEE):
    """
    Regroupe les boîtes par proximité de centre vertical.

    Contrairement à l'ancienne version, une boîte ne peut pas rejoindre une
    rangée uniquement parce qu'elle chevauche indirectement une autre boîte.
    """
    boites_triees = sorted(
        boites,
        key=lambda b: (centre_vertical(b), b.x0, b.id)
    )

    rangees = []

    for boite in boites_triees:
        candidates = [
            rangee for rangee in rangees
            if meme_rangee(boite, rangee, tolerance)
        ]

        if not candidates:
            rangees.append([boite])
            continue

        # Choisir la rangée dont le centre est le plus proche.
        rangee = min(
            candidates,
            key=lambda r: abs(
                centre_vertical(boite)
                - sorted(centre_vertical(b) for b in r)[len(r) // 2]
            )
        )
        rangee.append(boite)

    # Tri vertical strict des rangées.
    rangees.sort(
        key=lambda r: (
            sorted(centre_vertical(b) for b in r)[len(r) // 2],
            min(b.x0 for b in r),
        )
    )

    resultat = []
    trace = []

    for rangee in rangees:
        # x0 est prioritaire dans une vraie rangée horizontale.
        # y0 sert de tie-breaker pour deux boîtes presque alignées.
        rangee_triee = sorted(
            rangee,
            key=lambda b: (b.x0, b.y0, b.id)
        )

        trace.append(rangee_triee)
        resultat.extend(rangee_triee)

    return resultat, trace

# ---------------------------------------------------------------------------
# 3. Exécution + vérifications
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("json_path", nargs="?", default="test-impots-revenu.document.json")
    parser.add_argument("--page", type=int, default=2,
                         help="Page à traiter (1-indexé). Défaut : 2 -- le tableau financier "
                              "sans bordures qui échappe à find_tables() est page 2, pas page 1.")
    args = parser.parse_args()

    with open(args.json_path, encoding="utf-8") as f:
        doc = json.load(f)

    page = _charger_page(doc, args.page)
    if page is None:
        print(f"Page {args.page} introuvable.")
        return

    # native.words plutôt que resolved.words : c'est l'ENTRÉE de
    # reading_order.ordonner(), pas sa sortie déjà réordonnée -- et ça
    # évite de dépendre de la survie du champ `block` (spécifique pymupdf,
    # jamais mentionné dans le fix _word_from_dict) à travers un cycle
    # sérialisation/désérialisation dont on sait déjà qu'il a fait perdre
    # confidence/source une fois.
    mots = (page.get("native") or {}).get("words") or []
    if not mots:
        print(f"Aucun mot natif trouvé pour la page {args.page} (page['native']['words'] vide ou absent).")
        return

    natifs = [m for m in mots if (m.get("source") or "native") == "native"]
    vectos = [m for m in mots if m.get("source") == "ocr_vectoriel"]

    sans_block = [m for m in natifs if "block" not in m or m["block"] is None]
    if sans_block:
        print(f"ATTENTION : {len(sans_block)}/{len(natifs)} mot(s) natif(s) sans champ 'block' -- "
              f"le regroupement en boîtes natives sera incomplet ou plantera. Vérifier si 'block' "
              f"survit à la sérialisation JSON pour ce document (schema/modèle), avant de blâmer "
              f"la logique de clustering elle-même.")
        natifs = [m for m in natifs if "block" in m and m["block"] is not None]

    boites_n = construire_boites_natives(natifs)
    boites_v = construire_boites_vectorisees(vectos)
    print(f"Boîtes natives: {len(boites_n)}   Boîtes vectorisées (clustering): {len(boites_v)}")
    print()

    toutes = boites_n + boites_v
    ordre, rangees = ordonner_par_boites(toutes)

    print(f"=== {len(rangees)} rangées détectées ===")
    for i, rangee in enumerate(rangees):
        etiquette = " | ".join(f"{b.id}(x0={b.x0:.0f})" for b in rangee)
        print(f"Rangée {i}: {etiquette}")
    print()

    # --- Diagnostic d'absorption transitive : une rangée à N boîtes n'est
    # fiable que si ces boîtes sont de hauteur comparable. Une grosse boîte
    # qui n'a besoin de chevaucher que 30% de la hauteur d'une petite pour
    # l'absorber peut entraîner tout un tas d'éléments sans lien réel entre
    # eux dans la même rangée, avant de tout trier par x0.
    print(
        "=== Vérification anti-absorption "
        "(boîtes de hauteur très inégale dans une même rangée) ==="
    )

    alertes_absorption = diagnostiquer_absorption(rangees)

    if not alertes_absorption:
        print(
            "  Aucune différence de hauteur significative "
            "dans les rangées."
        )

    for alerte in alertes_absorption:
        grosse = alerte["grosse"]
        petite = alerte["petite"]

        boite_grosse = grosse["boite"]
        boite_petite = petite["boite"]

        if alerte["multi_lignes"]:
            niveau = "INFO"
            interpretation = (
                "boîte multi-lignes : différence probablement légitime, "
                "mais à vérifier visuellement"
            )
        else:
            niveau = "RISQUE"
            interpretation = (
                "boîte mono-ligne très haute : possible absorption incorrecte"
            )

        print(
            f"  {niveau} : rangée {alerte['rangee']} -- "
            f"{boite_grosse.id} "
            f"(hauteur={grosse['hauteur']:.1f}pt, "
            f"lignes={grosse['nb_lignes']}) vs "
            f"{boite_petite.id} "
            f"(hauteur={petite['hauteur']:.1f}pt, "
            f"lignes={petite['nb_lignes']}), "
            f"ratio={alerte['ratio']:.1f}x ; "
            f"{interpretation}."
        )

    print()

    # --- Vérification : saut arrière ENTRE RANGÉES (pas entre boîtes --
    # dans une même rangée, deux boîtes ont légitimement des plages y qui
    # se chevauchent, ce n'est pas un saut arrière).
    print("=== Vérification anti-saut-arrière (au niveau rangée) ===")
    y0_min_precedent = -1
    alertes = 0
    for i, rangee in enumerate(rangees):
        y0_min = min(b.y0 for b in rangee)
        if y0_min < y0_min_precedent - 5:
            print(f"  SAUT ARRIÈRE : rangée {i} (y0_min={y0_min:.1f}) "
                  f"après un y0_min déjà atteint de {y0_min_precedent:.1f}")
            alertes += 1
        y0_min_precedent = max(y0_min_precedent, y0_min)
    print(f"  -> {alertes} saut(s) arrière détecté(s) sur {len(rangees)} rangées"
          f"{' (AUCUN, séquence propre)' if alertes == 0 else ''}")
    print()

    # --- Garde-fou "ne jamais perdre, même mal placé" (même principe déjà
    # appliqué au stopgap de réintégration des mots de table dans
    # reading_order.py) : le nombre de mots en sortie doit égaler le nombre
    # en entrée. Une égalité de compte ne prouve pas une égalité de
    # contenu (piège déjà rencontré), mais une INégalité prouve à coup sûr
    # une perte, donc vaut la peine d'être vérifiée systématiquement.
    n_entree = len(natifs) + len(vectos)
    n_sortie = sum(len(b.mots) for b in ordre)
    print(f"=== Conservation du contenu : {n_entree} mot(s) en entrée, {n_sortie} en sortie ===")
    if n_entree != n_sortie:
        print(f"  ATTENTION : écart de {n_entree - n_sortie} mot(s) -- perte silencieuse à investiguer.")
    print()

    # --- Séquence de mots à plat, pour comparaison visuelle rapide ---
    print("=== Séquence de mots à plat (100 premiers tokens) ===")
    sequence = []
    for b in ordre:
        mots_boite_tries = grouper_par_ligne_tolerant(b.mots)
        sequence.extend(texte_affiche(m) for m in mots_boite_tries)
    print(" ".join(sequence[:100]))


if __name__ == "__main__":
    main()