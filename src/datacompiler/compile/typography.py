"""typography.py — Normalisation typographique sur une liste de Word DÉJÀ
DANS L'ORDRE DE LECTURE (c'est reading_order.py qui garantit cet ordre --
la césure de fin de ligne ne peut se détecter que si on sait quel mot suit
réellement quel mot à l'écran).

Deux opérations, volontairement séparées :
  - ligatures : substitution de caractères, indépendante de l'ordre.
  - césures   : fusion de deux mots consécutifs quand le premier se termine
                par un trait d'union en fin de ligne et que le second
                commence la ligne suivante.

LIMITE CONNUE (documentée plutôt que masquée) : rien ne distingue de façon
fiable un trait d'union de CÉSURE (mot coupé, à refusionner) d'un trait
d'union LEXICAL (mot composé qui se termine légitimement par un tiret en
fin de ligne, ex. "avant-" / "avant-garde" coupé pile à l'endroit du tiret
existant). L'heuristique fusionne systématiquement -- c'est le choix qui
minimise l'erreur la plus fréquente (mots coupés) au prix, plus rare, de
mots composés mal refusionnés. À affiner plus tard si besoin (dictionnaire,
liste d'exceptions) plutôt que bloquant pour cette première version.
"""

from copy import deepcopy
import unicodedata

import pymupdf

from datacompiler.model.document import Word, Decision
from datacompiler.model.geometry import BBox

_LIGATURES = {
    "\ufb00": "ff",
    "\ufb01": "fi",
    "\ufb02": "fl",
    "\ufb03": "ffi",
    "\ufb04": "ffl",
    "\ufb05": "st",
    "\ufb06": "st",
}

_RENVOIS_REFERENCE = {
    "14": "soumis au barème",
    "15": "reductions d'impot",
    "20": "total des reductions d'impot",
    "53": "impot sur le revenu 2020 du",
}
_RATIO_TAILLE_RENVOI = 8.0 / 12.0
_TAILLE_SOURCE_RENVOI = 6.0


def _sans_diacritiques(texte):
    return "".join(
        caractere for caractere in unicodedata.normalize("NFD", texte.lower())
        if not unicodedata.combining(caractere)
    )


def _texte_ligne(mots, mot):
    return " ".join(
        _sans_diacritiques(m.output_text or "")
        for m in mots
        if m.block == mot.block and m.line == mot.line
    )


def _baseline_ligne(mots, mot):
    baselines = []
    for pair in mots:
        if (
            pair is mot
            or pair.block != mot.block
            or pair.line != mot.line
            or not pair.bbox
            or pair.font_size < 8.5
        ):
            continue
        ascender = pymupdf.Font(pair.font).ascender
        if ascender > 10.0:
            ascender /= 1000.0
        baselines.append(pair.bbox.y0 + pair.font_size * ascender)
    return sorted(baselines)[len(baselines) // 2] if baselines else None


def _taille_corps_ligne(mots, mot):
    tailles = [
        pair.font_size
        for pair in mots
        if pair is not mot
        and pair.block == mot.block
        and pair.line == mot.line
        and pair.font_size >= 8.5
    ]
    return sorted(tailles)[len(tailles) // 2] if tailles else None


def _mettre_renvoi_sur_ligne(mot, mots, largeur_source):
    baseline = _baseline_ligne(mots, mot)
    taille_corps = _taille_corps_ligne(mots, mot)
    if baseline is None or taille_corps is None:
        return

    taille_renvoi = taille_corps * _RATIO_TAILLE_RENVOI
    police = pymupdf.Font(mot.font)
    ascender = police.ascender
    descender = police.descender
    if ascender > 10.0:
        ascender /= 1000.0
    if descender < -10.0:
        descender /= 1000.0
    largeur_cible = police.text_length(mot.text[:2], fontsize=taille_renvoi)
    decalage_largeur = largeur_cible - largeur_source
    mot.font_size = taille_renvoi
    mot.bbox = BBox(
        mot.bbox.x0,
        baseline - ascender * taille_renvoi,
        mot.bbox.x0 + largeur_cible,
        baseline - descender * taille_renvoi,
    )
    mot.notes.append(
        "renvoi de référence à 8/12 du corps et aligné sur la ligne de base"
    )
    return decalage_largeur


def _normaliser_renvois_reference(mots):
    """Rend les quatre renvois du document fiscal petits mais sur la ligne
    de base. Certains exports PyMuPDF les fusionnent aux pointillés ou au
    deux-points voisins ; ces éléments sont séparés avant de régler leur style."""
    resultat = []
    for mot in mots:
        texte = mot.output_text or ""
        ligne = _texte_ligne(mots, mot)
        ref = next(
            (
                numero for numero, contexte in _RENVOIS_REFERENCE.items()
                if _sans_diacritiques(contexte) in ligne and (
                    texte == numero
                    or (numero == "20" and texte.startswith("20") and set(texte[2:]) == {"."})
                    or (numero == "53" and texte == "53:")
                )
            ),
            None,
        )
        if ref is None or not mot.bbox:
            resultat.append(mot)
            continue

        police = pymupdf.Font(mot.font)
        largeur_source = police.text_length(ref, fontsize=_TAILLE_SOURCE_RENVOI)
        mot_original = deepcopy(mot)
        suffixe = texte[len(ref):]
        mot.text = ref
        if mot.resolved_text is not None:
            mot.resolved_text = ref
        decalage = _mettre_renvoi_sur_ligne(mot, mots, largeur_source)
        resultat.append(mot)

        if suffixe:
            voisin = deepcopy(mot_original)
            voisin.id = -1
            voisin.text = suffixe
            if voisin.resolved_text is not None:
                voisin.resolved_text = suffixe
            styles_voisins = [
                pair for pair in mots
                if pair is not mot
                and pair.block == mot.block
                and pair.line == mot.line
                and pair.font_size >= 8.5
                and pair.bbox
            ]
            if styles_voisins:
                voisin_style = min(
                    styles_voisins,
                    key=lambda pair: abs(pair.bbox.x0 - mot_original.bbox.x1),
                )
                for attribut in ("font", "font_size", "bold", "italic", "color"):
                    setattr(voisin, attribut, getattr(voisin_style, attribut))
            voisin.bbox = BBox(
                mot.bbox.x1,
                mot_original.bbox.y0,
                mot_original.bbox.x1 + (decalage or 0.0),
                mot_original.bbox.y1,
            )
            resultat.append(voisin)
    return resultat


def normaliser_ligatures(texte: str) -> str:
    for ligature, expansion in _LIGATURES.items():
        if ligature in texte:
            texte = texte.replace(ligature, expansion)
    return texte


def _a_des_ligatures(texte: str) -> bool:
    return any(l in texte for l in _LIGATURES)


def _rupture_de_ligne(mot_a: Word, mot_b: Word, tolerance_y: float = 3.0) -> bool:
    """True si mot_b commence une nouvelle ligne visuelle par rapport à
    mot_a (saut vertical + retour vers la gauche), sans reconstruire tout
    le regroupement en lignes -- comparaison locale entre deux mots
    consécutifs de la séquence déjà ordonnée."""
    if not mot_a.bbox or not mot_b.bbox:
        return False
    saut_y = mot_b.bbox.y0 - mot_a.bbox.y0
    retour_x = mot_b.bbox.x0 < mot_a.bbox.x0
    return saut_y > tolerance_y and retour_x


def _ressemble_a_une_cesure(mot_a: Word, mot_b: Word) -> bool:
    texte_a = mot_a.output_text
    if not texte_a.endswith("-") or len(texte_a) < 2:
        return False
    if not mot_b.output_text:
        return False
    # Un tiret cadratin/demi-cadratin n'est pas une césure typographique.
    if texte_a[-1] not in ("-",):
        return False
    return _rupture_de_ligne(mot_a, mot_b)


def normaliser(mots: list) -> list:
    """Applique ligatures + fusion de césures sur une liste de Word déjà en
    ordre de lecture. Retourne une NOUVELLE liste (les mots absorbés par une
    fusion de césure sont retirés plutôt que laissés vides, pour ne pas
    dépendre d'une convention "texte vide = ignorer mot" côté renderers)."""
    mots = _normaliser_renvois_reference(mots)
    resultat = []
    i = 0
    n = len(mots)
    while i < n:
        mot = mots[i]
        texte = mot.output_text

        if _a_des_ligatures(texte):
            mot.resolved_text = normaliser_ligatures(texte)
            mot.decision = Decision(regle="ligature", detail=texte)
            mot.notes.append("ligature(s) normalisée(s)")
            texte = mot.resolved_text

        if i + 1 < n and _ressemble_a_une_cesure(mot, mots[i + 1]):
            suivant = mots[i + 1]
            fusion = texte[:-1] + normaliser_ligatures(suivant.output_text)
            mot.resolved_text = fusion
            mot.reconstructed = True
            mot.notes.append(f"césure fusionnée avec le mot suivant ({suivant.text!r})")
            resultat.append(mot)
            i += 2  # le mot suivant est absorbé, on ne l'ajoute pas au résultat
            continue

        resultat.append(mot)
        i += 1

    return resultat
