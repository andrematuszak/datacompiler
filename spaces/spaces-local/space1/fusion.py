"""
fusion.py — Aligne le texte natif (PyMuPDF/pdfplumber) et le texte Mistral OCR
au niveau MOT pour une même zone de page, et applique la règle de
convergence : les deux sources s'accordent -> confiance maximale ; elles
divergent légèrement (typique d'une confusion OCR : t/l, s/8, etc.) -> on
choisit la source la plus fiable pour CE mot précis ; elles divergent
fortement -> aucune des deux n'est fiable seule, le mot est marqué pour
relecture humaine plutôt que deviné.

Nécessaire car Mistral ne fournit de bbox qu'au niveau bloc/paragraphe,
jamais au niveau mot (vérifié sur la documentation officielle) -- on ne peut
donc PAS faire correspondre natif et Mistral par coordonnées, seulement par
alignement de séquences textuelles au sein d'un même bloc.
"""

import difflib


def distance_edition(a, b):
    """Distance de Levenshtein (implémentation simple, suffisante pour des
    mots courts -- pas besoin d'une lib externe pour ça)."""
    if a == b:
        return 0
    m, n = len(a), len(b)
    prev = list(range(n + 1))
    for i in range(1, m + 1):
        curr = [i] + [0] * n
        for j in range(1, n + 1):
            cout = 0 if a[i - 1] == b[j - 1] else 1
            curr[j] = min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cout)
        prev = curr
    return prev[n]


def aligner_mots(texte_natif, texte_mistral, confiances_mistral=None, seuil_divergence_mineure=2):
    """
    Aligne deux séquences de mots sur la même zone de texte (typiquement : le
    contenu natif et le contenu Mistral d'un même bloc/bbox) et retourne,
    mot par mot, la source à retenir.

    confiances_mistral : dict optionnel {mot: score} -- l'API Mistral renvoie
    ceci via confidence_scores.word_confidence_scores quand demandé.

    Retourne une liste d'éléments au format demandé :
    {"id", "native_text", "mistral_text", "distance_edition", "source", "confidence"}
    où source ∈ {"convergence", "mistral", "natif_only", "mistral_only", "a_relire"}
    """
    mots_natif = texte_natif.split()
    mots_mistral = texte_mistral.split()
    confiances_mistral = confiances_mistral or {}

    sm = difflib.SequenceMatcher(a=mots_natif, b=mots_mistral, autojunk=False)
    elements = []
    id_compteur = 0

    def _ajouter(natif, mistral, source, confiance=None, dist=None):
        nonlocal id_compteur
        id_compteur += 1
        elements.append({
            "id": id_compteur,
            "native_text": natif,
            "mistral_text": mistral,
            "distance_edition": dist,
            "source": source,
            "confidence": confiance,
        })

    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                mot = mots_natif[i1 + k]
                _ajouter(mot, mot, "convergence", confiance=1.0, dist=0)

        elif tag == "replace":
            seg_natif = mots_natif[i1:i2]
            seg_mistral = mots_mistral[j1:j2]
            if len(seg_natif) == len(seg_mistral):
                paires = list(zip(seg_natif, seg_mistral))
            else:
                # nombre de mots différent des deux côtés (mot fusionné/coupé) :
                # pas d'alignement 1-pour-1 fiable, on les liste séparément
                # plutôt que de deviner une correspondance arbitraire
                paires = [(n, None) for n in seg_natif] + [(None, m) for m in seg_mistral]

            for natif, mistral in paires:
                if natif is None:
                    _ajouter(None, mistral, "mistral_only", confiances_mistral.get(mistral))
                    continue
                if mistral is None:
                    _ajouter(natif, None, "natif_only", None)
                    continue

                dist = distance_edition(natif.lower(), mistral.lower())
                conf_mistral = confiances_mistral.get(mistral)

                if dist <= seuil_divergence_mineure:
                    # divergence mineure -> probable confusion OCR/police sur
                    # un seul mot par ailleurs correctement isolé
                    if conf_mistral is not None and conf_mistral >= 0.85:
                        _ajouter(natif, mistral, "mistral", conf_mistral, dist)
                    else:
                        # Mistral lui-même n'est pas sûr (ou score inconnu) ->
                        # ne pas deviner, marquer pour relecture humaine
                        _ajouter(natif, mistral, "a_relire", conf_mistral, dist)
                else:
                    # divergence forte -> aucune des deux sources n'est
                    # fiable seule pour ce mot
                    _ajouter(natif, mistral, "a_relire", conf_mistral, dist)

        elif tag == "delete":
            for k in range(i1, i2):
                _ajouter(mots_natif[k], None, "natif_only")

        elif tag == "insert":
            for k in range(j1, j2):
                mot = mots_mistral[k]
                _ajouter(None, mot, "mistral_only", confiances_mistral.get(mot))

    return elements


def resumer(elements):
    """Petit résumé utile pour vérifier rapidement le résultat d'une fusion."""
    compteurs = {}
    for e in elements:
        compteurs[e["source"]] = compteurs.get(e["source"], 0) + 1
    a_relire = [e for e in elements if e["source"] == "a_relire"]
    return {
        "total_mots": len(elements),
        "repartition": compteurs,
        "mots_a_relire": [(e["native_text"], e["mistral_text"]) for e in a_relire],
    }


if __name__ == "__main__":
    # --- Démonstration sur test7.pdf ---
    # texte_natif : EXTRAIT RÉEL de test7.pdf (vérifié via pdfplumber)
    # texte_reference : PAS un vrai appel Mistral -- c'est la vérité terrain
    # (le texte correct, lisible sur l'image du contrat) utilisée ici pour
    # DÉMONTRER l'algorithme. À remplacer par la vraie sortie de l'API une
    # fois mistral_client.py branché.
    print("=== Démo sur un extrait de test7.pdf (texte natif réel) ===")
    natif_test7 = "Vergleichsverei nbaru ng zwischen den Beteitigten"
    reference_test7 = "Vergleichsvereinbarung zwischen den Beteiligten"
    elements = aligner_mots(natif_test7, reference_test7)
    for e in elements:
        print(e)
    print(resumer(elements))

    print("\n=== Démo sur un extrait de test21.pdf (texte natif réel) ===")
    natif_test21 = "que nous possédons de Hegel"
    # Ici on simule un score de confiance Mistral comme celui vu sur le
    # document polonais (39.8% pour un mot suspect) pour montrer la logique
    # de la règle de relecture
    natif_test21_corrompu = "que nOU8 possédon de Hegel"
    reference_test21 = "que nous possédons de Hegel"
    confiances_demo = {"nous": 0.42, "possédons": 0.91}  # exemple illustratif
    elements2 = aligner_mots(natif_test21_corrompu, reference_test21, confiances_demo)
    for e in elements2:
        print(e)
    print(resumer(elements2))
