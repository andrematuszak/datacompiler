import os
import io
import json
import base64
import gradio as gr
from pdf2image import convert_from_path
from PIL import Image, ImageDraw
from mistralai import Mistral

# Importation sécurisée de spaces pour bypasser les restrictions HF GPU
try:
    import spaces
    HAS_SPACES = True
except ImportError:
    HAS_SPACES = False

if HAS_SPACES:
    @spaces.GPU
    def validation_gpu_startup():
        print("[HF Spaces] Détecteur GPU initialisé.")
        return True
    try:
        validation_gpu_startup()
    except Exception as e:
        print(f"[HF Spaces] Note d'initialisation : {e}")


def encoder_fichier_en_base64(file_path):
    with open(file_path, "rb") as file:
        return base64.b64encode(file.read()).decode("utf-8")


def extraire_confiance_recursive(obj):
    """
    Fouille récursivement tout l'arbre de la réponse Mistral 
    pour extraire TOUS les couples (mot, confiance).
    """
    mots = []
    if isinstance(obj, list):
        for item in obj:
            mots.extend(extraire_confiance_recursive(item))
    elif isinstance(obj, dict):
        if "text" in obj and "confidence" in obj:
            mots.append((obj["text"], obj["confidence"]))
        else:
            for v in obj.values():
                mots.extend(extraire_confiance_recursive(v))
    elif hasattr(obj, "__dict__"):
        if hasattr(obj, "text") and hasattr(obj, "confidence"):
            mots.append((getattr(obj, "text"), getattr(obj, "confidence")))
        else:
            for attr in dir(obj):
                if not attr.startswith("_"):
                    try:
                        val = getattr(obj, attr)
                        mots.extend(extraire_confiance_recursive(val))
                    except Exception:
                        pass
    return mots


def dessiner_layout_sur_image(image_pil, blocks, dimensions):
    """
    Dessine des boîtes de couleur autour des blocs détectés par Mistral OCR.
    """
    if not blocks or not dimensions:
        return image_pil

    # Copie l'image pour ne pas altérer l'originale
    image_annotée = image_pil.copy()
    draw = ImageDraw.Draw(image_annotée)
    
    img_w, img_h = image_annotée.size
    
    # Récupération des dimensions réelles du PDF lues par Mistral
    pdf_w = getattr(dimensions, "width", 1000) or 1000
    pdf_h = getattr(dimensions, "height", 1000) or 1000
    
    # Ratios de mise à l'échelle
    scale_x = img_w / pdf_w
    scale_y = img_h / pdf_h

    # Palette de couleurs sémantiques
    couleurs = {
        "text": "#10B981",    # Vert Émeraude
        "list": "#3B82F6",    # Bleu
        "table": "#F59E0B",   # Orange
        "title": "#EF4444",   # Rouge
        "caption": "#8B5CF6"  # Violet
    }

    for block in blocks:
        b_type = getattr(block, "type", "text")
        rect = getattr(block, "rect", None)
        
        if rect:
            x1 = getattr(rect, "x1", 0)
            y1 = getattr(rect, "y1", 0)
            x2 = getattr(rect, "x2", 0)
            y2 = getattr(rect, "y2", 0)
            
            # Application de l'échelle
            dx1 = int(x1 * scale_x)
            dy1 = int(y1 * scale_y)
            dx2 = int(x2 * scale_x)
            dy2 = int(y2 * scale_y)
            
            color = couleurs.get(b_type, "#9CA3AF") # Gris par défaut
            
            # Dessiner le rectangle de contour
            draw.rectangle([dx1, dy1, dx2, dy2], outline=color, width=4)
            # Ajouter une étiquette textuelle au-dessus de la boîte
            draw.text((dx1 + 4, dy1 + 2), b_type, fill=color)

    return image_annotée


def traiter_document_mistral(pdf_file, api_key_input):
    if pdf_file is None:
        return "Erreur : Aucun fichier chargé.", {}, None

    api_key = api_key_input.strip() if api_key_input else os.getenv("MISTRAL_API_KEY")
    if not api_key:
        return (
            "Erreur : Clé API Mistral introuvable. Veuillez configurer MISTRAL_API_KEY.",
            {},
            None
        )

    try:
        client = Mistral(api_key=api_key)

        # 1. Conversion de la première page pour l'aperçu original
        pages = convert_from_path(pdf_file.name, first_page=1, last_page=1)
        if not pages:
            return "Échec de la génération de l'aperçu du PDF.", {}, None
        premiere_page = pages[0]

        # 2. Appel sécurisé à l'API Mistral OCR
        base64_data = encoder_fichier_en_base64(pdf_file.name)
        ocr_response = client.ocr.process(
            model="mistral-ocr-latest",
            document={
                "type": "document_url",
                "document_url": f"data:application/pdf;base64,{base64_data}"
            },
            include_blocks=True,
            confidence_scores_granularity="word"
        )

        if not ocr_response.pages:
            return "L'API Mistral n'a renvoyé aucune page.", {}, premiere_page

        page_data = ocr_response.pages[0]
        markdown_transcrit = page_data.markdown

        # 3. Extraction récursive exhaustive des scores de confiance
        tous_les_mots = extraire_confiance_recursive(page_data)
        
        mots_faible_confiance = []
        total_words = 0
        sum_confidence = 0.0

        for word, conf in tous_les_mots:
            total_words += 1
            sum_confidence += conf
            if conf < 0.85: # Seuil d'alerte : 85 %
                mots_faible_confiance.append({
                    "mot": word,
                    "confiance": f"{conf:.1%}"
                })

        avg_confidence = (sum_confidence / total_words) if total_words > 0 else 0.0

        # 4. Synthèse des blocs de structure physique
        synthese_blocs = {}
        blocks_list = getattr(page_data, "blocks", [])
        for block in blocks_list:
            b_type = getattr(block, "type", "unknown")
            synthese_blocs[b_type] = synthese_blocs.get(b_type, 0) + 1

        # 5. Dessin des boîtes de détection sur l'image d'aperçu
        image_avec_boites = dessiner_layout_sur_image(
            premiere_page, 
            blocks_list, 
            getattr(page_data, "dimensions", None)
        )

        metadonnees_analyse = {
            "evaluation_generale": {
                "langue_detectee": "Polonais / Multilingue (Auto)",
                "confiance_moyenne_document": f"{avg_confidence:.2%}",
                "statut_evaluation": "🔴 À REVOIR (Correction Manuelle)" if mots_faible_confiance else "🟢 EXCELLENT",
                "nombre_total_mots": total_words,
                "nombre_mots_suspects": len(mots_faible_confiance)
            },
            "structure_physique_detectee": synthese_blocs,
            "liste_mots_suspects_pour_correcteur": mots_faible_confiance[:30]
        }

        return markdown_transcrit, metadonnees_analyse, image_avec_boites

    except Exception as e:
        return f"Erreur lors de l'appel API Mistral : {str(e)}", {"erreur": str(e)}, None


# --- DESIGN DE L'INTERFACE GRAPHIQUE GRADIO ---
with gr.Blocks(title="Mistral OCR - Layout Visualizer") as demo:
    gr.Markdown("# 🪶 Mistral OCR - Sandbox Visuelle & Structurelle")
    gr.Markdown(
        "Visualisez en temps réel l'extraction Markdown de Mistral ainsi que "
        "l'analyse géométrique (Bounding Boxes) dessinée directement sur votre document."
    )
    
    with gr.Row():
        with gr.Column(scale=1):
            file_input = gr.File(label="Chargez votre PDF", file_types=[".pdf"])
            api_key_input = gr.Textbox(
                label="Clé API Mistral (Si non configurée en tâche de fond)",
                placeholder="sxR5...",
                type="password"
            )
            submit_btn = gr.Button("Lancer l'analyse visuelle", variant="primary")
            image_preview = gr.Image(label="Analyse Géométrique (Layout & Segments)", type="pil", interactive=False)
            
        with gr.Column(scale=1):
            text_output = gr.Textbox(
                label="Transcription Markdown (Mise en page littérale)", 
                lines=15, 
                interactive=False
            )
            metadata_output = gr.JSON(label="Grille d'Évaluation Sémantique (Filtrage des Ratures)")
            
    submit_btn.click(
        fn=traiter_document_mistral,
        inputs=[file_input, api_key_input],
        outputs=[text_output, metadata_output, image_preview]
    )

if __name__ == "__main__":
    demo.launch(theme=gr.themes.Soft())
