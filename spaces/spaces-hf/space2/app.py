import os
import io
import gradio as gr
import torch
import spaces
from pdf2image import convert_from_path
from PIL import Image
from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor
from qwen_vl_utils import process_vision_info

# 1. Chargement global du modèle et du processeur sur CPU au démarrage
# (Zero-GPU d'Hugging Face se chargera de le basculer sur la carte graphique)
MODEL_ID = "Qwen/Qwen2.5-VL-7B-Instruct"

print("Chargement du processeur...")
processor = AutoProcessor.from_pretrained(MODEL_ID)

print("Chargement du modèle (peut prendre 1 à 2 minutes)...")
model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
    MODEL_ID,
    torch_dtype=torch.float16,  # Utilisation de float16 pour optimiser la mémoire GPU
    device_map="cpu"            # Chargé sur CPU au départ pour Zero-GPU
)

@spaces.GPU
def traiter_document(pdf_file):
    """
    Fonction locale d'extraction sémantique exécutée sur le GPU du Space.
    """
    if pdf_file is None:
        return "Erreur : Aucun fichier n'a été chargé.", None

    try:
        # Envoi du modèle sur le GPU alloué dynamiquement
        device = "cuda"
        model.to(device)

        # 1. Conversion locale du PDF en Image via Poppler
        pages = convert_from_path(pdf_file.name, first_page=1, last_page=1)
        if not pages:
            return "Échec de la conversion du PDF en image.", None
        
        premiere_page = pages[0]

        # Redimensionnement optionnel pour éviter d'exploser la mémoire GPU
        premiere_page.thumbnail((1024, 1024))

        # Prompt de nettoyage sémantique
        prompt = (
            "Tu es un expert en extraction de documents dégradés ou raturés. "
            "Analyse cette image. Extrais tout le texte et toutes les lignes financières sans exception. "
            "Attention absolue : Ne saute aucune ligne manuscrite, même si elle semble raturée, "
            "gribouillée ou partiellement effacée (porte une attention critique aux termes comme 'praca' ou 'gotówka'). "
            "Retourne un résultat structuré proprement au format JSON avec les clés suivantes : "
            "'statut_document', 'donnees_financieres_identifiees', 'texte_brut_total'."
        )

        # Formatage de la requête requis par le processeur Qwen2.5-VL
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": premiere_page},
                    {"type": "text", "text": prompt},
                ],
            }
        ]

        # Préparation des inputs pour le modèle
        text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        image_inputs, video_inputs = process_vision_info(messages)
        
        inputs = processor(
            text=[text],
            images=image_inputs,
            videos=video_inputs,
            padding=True,
            return_tensors="pt"
        )
        inputs = inputs.to(device)

        # Génération locale par le GPU
        with torch.no_grad():
            generated_ids = model.generate(**inputs, max_new_tokens=1024)
            
        generated_ids_trimmed = [
            out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
        ]
        
        output_text = processor.batch_decode(
            generated_ids_trimmed, 
            skip_special_tokens=True, 
            clean_up_tokenization_spaces=False
        )[0]

        return output_text, premiere_page

    except Exception as e:
        return f"Erreur lors du traitement local sur GPU : {str(e)}", None

# Design de l'interface graphique Gradio (Compatible v6)
with gr.Blocks(title="Data Cleaner Vision Lab") as demo:
    gr.Markdown("# 🧼 Data Cleaner 2 - Vision Sandbox (Local GPU)")
    gr.Markdown("Extraction sémantique par Vision exécutée directement sur le GPU de ton Space.")
    
    with gr.Row():
        with gr.Column():
            file_input = gr.File(label="Charge ton fichier test.pdf", file_types=[".pdf"])
            submit_btn = gr.Button("Démarrer l'Inférence locale", variant="primary")
            
        with gr.Column():
            image_preview = gr.Image(label="Aperçu de la page analysée", type="pil", interactive=False)
            text_output = gr.Textbox(label="Résultat de la détection textuelle (Format JSON attendu)", lines=20)
            
    submit_btn.click(
        fn=traiter_document,
        inputs=[file_input],
        outputs=[text_output, image_preview]
    )

if __name__ == "__main__":
    demo.launch(theme=gr.themes.Soft())
