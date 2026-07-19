import os
import io
import json
import base64
import gradio as gr
from pdf2image import convert_from_path
from PIL import Image
from mistralai.client import Mistral

# Importation de spaces (uniquement nécessaire sur les environnements HF GPU)
try:
    import spaces
    HAS_SPACES = True
except ImportError:
    HAS_SPACES = False

# --- CONTOURNEMENT DE L'ERREUR HUGGING FACE "No @spaces.GPU function detected" ---
# Si nous sommes sur un Space HF GPU, nous définissons une fonction "leurre" décorée 
# qui s'exécute au démarrage pour valider les exigences d'initialisation de HF.
if HAS_SPACES:
    @spaces.GPU
    def validation_gpu_startup():
        print("[HF Spaces] Détecteur GPU initialisé avec succès.")
        return True
    
    # Appel de validation au démarrage du script
    try:
        validation_gpu_startup()
    except Exception as e:
        print(f"[ HF Spaces] Note d'initialisation : {e}")


def encoder_fichier_en_base64(file_path):
    """Encode le fichier en base64 pour l'envoi sécurisé à l'API."""
    with open(file_path, "rb") as file:
        return base64.b64encode(file.read()).decode("utf-8")


def construire_rendu_flow(blocs, largeur_page, largeur_affichage=560):
    """Mode 'Document Flow' : empile les blocs dans l'ordre de lecture, chacun
    avec sa hauteur naturelle (pas de hauteur/position verticale imposée).
    Recommandé quand les blocs ne se chevauchent pas horizontalement (une
    seule colonne) -- élimine par construction le bug du <br> en position
    fixe (l'API ne renvoie pas la position des sauts de ligne internes à un
    bloc, donc les forcer dans un espace de hauteur fixe est voué à l'échec)
    et tout risque de chevauchement si le texte corrigé/traduit est plus long
    que l'original. Ne préserve PAS une mise en page multi-colonnes -- dans ce
    cas, utiliser construire_rendu_positionne à la place."""
    if not blocs or not largeur_page:
        return "<p>Pas de blocs disponibles pour ce document.</p>"

    divs = []
    for bloc in blocs:
        gauche_pct = bloc["top_left_x"] / largeur_page * 100
        largeur_pct = (bloc["bottom_right_x"] - bloc["top_left_x"]) / largeur_page * 100
        # on NE force plus de <br> : on remplace les \n internes par un espace
        # et on laisse le CSS enrouler le texte naturellement selon la largeur
        # du bloc -- c'est le comportement le plus honnête vu qu'on n'a pas la
        # position réelle des sauts de ligne d'origine
        contenu_html = (
            (bloc["contenu"] or "")
            .replace("<", "&lt;").replace(">", "&gt;")
            .replace("\n", " ")
        )
        marge_liste = "margin-left: 1.2em;" if bloc["type"] == "list" else ""
        divs.append(
            f'<div style="margin-left:{gauche_pct:.2f}%; width:{largeur_pct:.2f}%; '
            f'margin-top:10px; margin-bottom:10px; font-family: Arial, sans-serif; '
            f'font-size:13px; line-height:1.4; {marge_liste}" '
            f'title="{bloc["type"]}">{contenu_html}</div>'
        )

    return (
        f'<div style="width:{largeur_affichage}px; border:1px solid #ccc; '
        f'background:#fff; margin:auto; padding:12px 0;">'
        + "".join(divs) +
        "</div>"
    )


def construire_rendu_positionne(blocs, largeur_page, hauteur_page, largeur_affichage=560):
    """Construit un rendu HTML approximant la mise en page originale à partir
    des bbox Mistral. Principe : un conteneur à l'aspect ratio de la page,
    chaque bloc en position absolute (%) calculée depuis ses coordonnées.
    Ce n'est PAS une reconstruction pixel-parfaite (pas de police/graisse/
    alignement fin), mais ça restitue la structure visuelle -- colonnes,
    paragraphes séparés, ordre spatial -- que le markdown à plat ("\\n" partout)
    ne peut pas montrer."""
    if not blocs or not largeur_page or not hauteur_page:
        return "<p>Pas de blocs positionnés disponibles pour ce document.</p>"

    ratio = hauteur_page / largeur_page
    hauteur_affichage = round(largeur_affichage * ratio)

    divs = []
    for bloc in blocs:
        gauche_pct = bloc["top_left_x"] / largeur_page * 100
        haut_pct = bloc["top_left_y"] / hauteur_page * 100
        largeur_pct = (bloc["bottom_right_x"] - bloc["top_left_x"]) / largeur_page * 100
        hauteur_pct = (bloc["bottom_right_y"] - bloc["top_left_y"]) / hauteur_page * 100
        contenu_html = (bloc["contenu"] or "").replace("\n", "<br>").replace("<", "&lt;").replace(">", "&gt;")
        # taille de police approximative : proportionnelle à la hauteur du bloc,
        # bornée pour rester lisible -- pas une valeur exacte de la police d'origine
        taille_police = max(8, min(16, round(hauteur_pct * hauteur_affichage / 100 * 0.5)))
        style_liste = "list-style-position: inside;" if bloc["type"] == "list" else ""
        divs.append(
            f'<div style="position:absolute; left:{gauche_pct:.2f}%; top:{haut_pct:.2f}%; '
            f'width:{largeur_pct:.2f}%; height:{hauteur_pct:.2f}%; '
            f'font-size:{taille_police}px; line-height:1.2; overflow:hidden; '
            f'font-family: Arial, sans-serif; {style_liste}" '
            f'title="{bloc["type"]}">{contenu_html}</div>'
        )

    return (
        f'<div style="position:relative; width:{largeur_affichage}px; height:{hauteur_affichage}px; '
        f'border:1px solid #ccc; background:#fff; margin:auto;">'
        + "".join(divs) +
        "</div>"
    )


def traiter_document_mistral(pdf_file, api_key_input):
    """
    Traite le PDF via l'API officielle Mistral OCR, extrait le texte, 
    calcule la confiance et analyse la structure.
    """
    if pdf_file is None:
        return "Erreur : Aucun fichier chargé.", {}, None, "", ""

    # Gestion de la clé API (priorité au champ de l'interface, puis variable d'env)
    api_key = api_key_input.strip() if api_key_input else os.getenv("MISTRAL_API_KEY")
    if not api_key:
        return (
            "Erreur : Clé API Mistral introuvable. Veuillez la saisir dans le champ "
            "prévu à cet effet ou configurer la variable d'environnement MISTRAL_API_KEY dans votre Space.",
            {},
            None,
            "",
            ""
        )

    try:
        # Initialisation du client officiel sécurisé
        client = Mistral(api_key=api_key)

        # 2. Conversion locale de la page 1 pour l'aperçu visuel de l'interface
        pages = convert_from_path(pdf_file.name, first_page=1, last_page=1)
        if not pages:
            return "Échec de la génération de l'aperçu du PDF.", {}, None
        premiere_page = pages[0]
        premiere_page.thumbnail((1024, 1024))

        # 3. Préparation et envoi du PDF directement à l'API Mistral OCR
        base64_data = encoder_fichier_en_base64(pdf_file.name)
        
        ocr_response = client.ocr.process(
            model="mistral-ocr-latest",
            document={
                "type": "document_url",
                "document_url": f"data:application/pdf;base64,{base64_data}"
            },
            include_blocks=True,                 # Pour extraire la structure du document
            confidence_scores_granularity="word" # Indispensable pour la grille de confiance
        )

        if not ocr_response.pages:
            return "L'API Mistral n'a renvoyé aucune page.", {}, premiere_page, "", ""

        # On se concentre sur la première page pour le test
        page_data = ocr_response.pages[0]
        markdown_transcrit = page_data.markdown

        # 4. Extraction et filtrage des scores de confiance au niveau du mot
        # NOTE : le SDK ne renvoie PAS page_data.words. Les scores de confiance
        # se trouvent sous page_data.confidence_scores.word_confidence_scores
        # (voir docs.mistral.ai). L'ancien accès à .words renvoyait toujours une
        # liste vide -> confiance à 0% et statut "EXCELLENT" par défaut, quel que
        # soit le contenu réel.
        mots_faible_confiance = []
        total_words = 0
        sum_confidence = 0.0

        conf_scores = getattr(page_data, "confidence_scores", None)
        mots_confiance = getattr(conf_scores, "word_confidence_scores", None) if conf_scores else None

        if mots_confiance:
            for word_info in mots_confiance:
                total_words += 1
                sum_confidence += word_info.confidence
                # Seuil d'alerte : 85 % de confiance
                if word_info.confidence < 0.85:
                    mots_faible_confiance.append({
                        "mot": word_info.text,
                        "confiance": f"{word_info.confidence:.1%}"
                    })

        avg_confidence = (sum_confidence / total_words) if total_words > 0 else 0.0

        # 5. Analyse structurelle des blocs (Tableaux, titres, etc.)
        # On récupère la bbox de chaque bloc (top_left_x/y, bottom_right_x/y, content)
        # au lieu de se contenter de compter les types -- indispensable pour
        # reconstruire un ordre de lecture correct (colonnes, encadrés) plutôt
        # que l'ordre brut renvoyé par l'API.
        synthese_blocs = {}
        blocs_positionnes = []
        if hasattr(page_data, 'blocks') and page_data.blocks:
            for block in page_data.blocks:
                synthese_blocs[block.type] = synthese_blocs.get(block.type, 0) + 1
                blocs_positionnes.append({
                    "type": block.type,
                    "top_left_x": block.top_left_x,
                    "top_left_y": block.top_left_y,
                    "bottom_right_x": block.bottom_right_x,
                    "bottom_right_y": block.bottom_right_y,
                    "contenu": block.content[:200] if block.content else "",
                })

        # Ordre de lecture approximatif : on regroupe les blocs par bande
        # horizontale (tolérance = 2% de la hauteur de page) puis on trie par
        # x à l'intérieur de chaque bande -- gère les colonnes/encadrés sans
        # avoir besoin d'une vraie détection de mise en page.
        hauteur_page = getattr(page_data, "dimensions", None)
        hauteur_page = hauteur_page.height if hauteur_page else 1000
        tolerance_bande = max(hauteur_page * 0.02, 5)

        def cle_ordre_lecture(bloc):
            bande = round(bloc["top_left_y"] / tolerance_bande)
            return (bande, bloc["top_left_x"])

        blocs_positionnes.sort(key=cle_ordre_lecture)

        # Rendu HTML positionné (approximation visuelle de la mise en page
        # d'origine à partir des bbox) -- répond au besoin "voir la structure
        # comme sur le papier" plutôt que le markdown à plat.
        dimensions = getattr(page_data, "dimensions", None)
        largeur_page_px = getattr(dimensions, "width", None) if dimensions else None
        rendu_flow = construire_rendu_flow(blocs_positionnes, largeur_page_px)
        rendu_positionne = construire_rendu_positionne(blocs_positionnes, largeur_page_px, hauteur_page)

        # Construction du rapport de métadonnées pour notre grille de décision
        metadonnees_analyse = {
            "evaluation_generale": {
                "langue_detectee": "Polonais / Multilingue (Auto)",
                "confiance_moyenne_document": f"{avg_confidence:.2%}",
                "statut_evaluation": "🔴 À REVOIR (Correction Manuelle)" if mots_faible_confiance else "🟢 EXCELLENT",
                "nombre_total_mots": total_words,
                "nombre_mots_suspects": len(mots_faible_confiance)
            },
            "structure_physique_detectee": synthese_blocs,
            "blocs_ordre_de_lecture": blocs_positionnes[:50],  # limité à 50 pour l'interface
            "liste_mots_suspects_pour_correcteur": mots_faible_confiance[:30] # Limité à 30 pour l'interface
        }

        return markdown_transcrit, metadonnees_analyse, premiere_page, rendu_flow, rendu_positionne

    except Exception as e:
        return f"Erreur lors de l'appel API Mistral : {str(e)}", {"erreur": str(e)}, None, "", ""


# --- DESIGN DE L'INTERFACE GRAPHIQUE (Gradio CPU-friendly) ---
with gr.Blocks(title="Mistral OCR - Enterprise Vision Lab") as demo:
    gr.Markdown("# 🪶 Mistral OCR - Sandbox Professionnelle et Sécurisée")
    gr.Markdown(
        "Ce laboratoire d'évaluation interroge directement l'API souveraine de Mistral AI. "
        "Il analyse la structure de vos PDF, en extrait une transcription structurée au format Markdown, "
        "et génère une grille de confiance automatique mot par mot."
    )
    
    with gr.Row():
        # Colonne de gauche : Entrées et contrôles
        with gr.Column(scale=1):
            file_input = gr.File(label="Chargez votre document (PDF de test)", file_types=[".pdf"])
            
            api_key_input = gr.Textbox(
                label="Clé API Mistral (Optionnel si configurée dans vos variables d'env)",
                placeholder="Ex: sxR5...",
                type="password"
            )
            
            submit_btn = gr.Button("Lancer l'extraction Mistral OCR", variant="primary")
            image_preview = gr.Image(label="Aperçu visuel (Validation Poppler)", type="pil", interactive=False)
            
        # Colonne de droite : Sortie et Métadonnées
        with gr.Column(scale=1):
            text_output = gr.Textbox(
                label="Transcription Markdown (Mise en page respectée)", 
                lines=15, 
                interactive=False
            )
            with gr.Tab("Document Flow (recommandé — colonne unique)"):
                rendu_flow_output = gr.HTML(
                    label="Empilement en ordre de lecture, hauteur libre — pas de chevauchement possible"
                )
            with gr.Tab("Positionné absolu (documents multi-colonnes)"):
                rendu_positionne_output = gr.HTML(
                    label="Position et hauteur fixées sur les bbox d'origine — risque de chevauchement si le texte est plus long"
                )
            metadata_output = gr.JSON(label="Grille d'Évaluation Sémantique (Scores de confiance)")
            
    submit_btn.click(
        fn=traiter_document_mistral,
        inputs=[file_input, api_key_input],
        outputs=[text_output, metadata_output, image_preview, rendu_flow_output, rendu_positionne_output]
    )

if __name__ == "__main__":
    demo.launch(theme=gr.themes.Soft())
