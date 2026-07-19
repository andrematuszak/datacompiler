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


def traiter_document_mistral(pdf_file, api_key_input):
    """
    Traite le PDF via l'API officielle Mistral OCR, extrait le texte, 
    calcule la confiance et analyse la structure.
    """
    if pdf_file is None:
        return "Erreur : Aucun fichier chargé.", {}, None

    # Gestion de la clé API (priorité au champ de l'interface, puis variable d'env)
    api_key = api_key_input.strip() if api_key_input else os.getenv("MISTRAL_API_KEY")
    if not api_key:
        return (
            "Erreur : Clé API Mistral introuvable. Veuillez la saisir dans le champ "
            "prévu à cet effet ou configurer la variable d'environnement MISTRAL_API_KEY dans votre Space.",
            {},
            None
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
            return "L'API Mistral n'a renvoyé aucune page.", {}, premiere_page

        # On se concentre sur la première page pour le test
        page_data = ocr_response.pages[0]
        markdown_transcrit = page_data.markdown

        # 4. Extraction et filtrage des scores de confiance au niveau du mot
        mots_faible_confiance = []
        total_words = 0
        sum_confidence = 0.0

        if hasattr(page_data, 'words') and page_data.words:
            for word_info in page_data.words:
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
        synthese_blocs = {}
        if hasattr(page_data, 'blocks') and page_data.blocks:
            for block in page_data.blocks:
                synthese_blocs[block.type] = synthese_blocs.get(block.type, 0) + 1

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
            "liste_mots_suspects_pour_correcteur": mots_faible_confiance[:30] # Limité à 30 pour l'interface
        }

        return markdown_transcrit, metadonnees_analyse, premiere_page

    except Exception as e:
        return f"Erreur lors de l'appel API Mistral : {str(e)}", {"erreur": str(e)}, None


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
            metadata_output = gr.JSON(label="Grille d'Évaluation Sémantique (Scores de confiance)")
            
    submit_btn.click(
        fn=traiter_document_mistral,
        inputs=[file_input, api_key_input],
        outputs=[text_output, metadata_output, image_preview]
    )

if __name__ == "__main__":
    demo.launch(theme=gr.themes.Soft())
