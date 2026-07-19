import os
import io
import json
import gradio as gr
import torch
import spaces
from pdf2image import convert_from_path
from PIL import Image
from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor
from qwen_vl_utils import process_vision_info

# Chargement global du modèle et du processeur
MODEL_ID = "Qwen/Qwen2.5-VL-7B-Instruct"

print("Chargement du processeur...")
processor = AutoProcessor.from_pretrained(MODEL_ID)

print("Chargement du modèle...")
model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
    MODEL_ID,
    torch_dtype=torch.float16,
    device_map="cpu"
)

@spaces.GPU
def traiter_document(pdf_file):
    if pdf_file is None:
        return "Erreur : Aucun fichier chargé.", {}, None

    try:
        device = "cuda"
        model.to(device)

        # 1. Conversion PDF en Image
        pages = convert_from_path(pdf_file.name, first_page=1, last_page=1)
        if not pages:
            return "Échec de la conversion du PDF.", {}, None
        
        premiere_page = pages[0]
        premiere_page.thumbnail((1024, 1024))

        # PROMPT AGNOSTIQUE : Aucune triche, transcription littérale stricte
        prompt = (
            "Tu es un transcripteur de documents de haute précision. "
            "Analyse cette image sans aucun a priori sémantique ou contextuel.\n\n"
            "Consignes strictes :\n"
            "1. Transcris TOUT le texte visible, qu'il soit imprimé, dactylographié ou manuscrit.\n"
            "2. Respecte scrupuleusement la mise en page originale : fais des sauts de ligne là où ils apparaissent sur l'image.\n"
            "3. Ne corrige pas les fautes d'orthographe ou les ratures. Transcris ce qui est écrit de la manière la plus fidèle possible.\n"
            "4. Si un élément est raturé mais reste lisible, transcris-le.\n\n"
            "Retourne ta réponse sous la forme d'un JSON strict avec les clés suivantes :\n"
            "{\n"
            "  \"langue_detectee\": \"La langue principale estimée du document\",\n"
            "  \"texte_transcrit\": \"La transcription exacte ligne par ligne, avec sauts de ligne \\n\",\n"
            "  \"evaluation_lisibilite\": \"Facile, Moyenne ou Difficile\"\n"
            "}"
        )

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": premiere_page},
                    {"type": "text", "text": prompt},
                ],
            }
        ]

        # Préparation et exécution
        text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        image_inputs, video_inputs = process_vision_info(messages)
        
        inputs = processor(
            text=[text],
            images=image_inputs,
            videos=video_inputs,
            padding=True,
            return_tensors="pt"
        ).to(device)

        with torch.no_grad():
            generated_ids = model.generate(**inputs, max_new_tokens=1024)
            
        generated_ids_trimmed = [
            out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
        ]
        
        raw_output = processor.batch_decode(
            generated_ids_trimmed, 
            skip_special_tokens=True, 
            clean_up_tokenization_spaces=False
        )[0]

        # Nettoyage de la réponse pour isoler le JSON
        raw_output = raw_output.strip()
        if "```json" in raw_output:
            raw_output = raw_output.split("```json")[1].split("```")[0].strip()
        elif "```" in raw_output:
            raw_output = raw_output.split("```")[1].split("```")[0].strip()

        # Parsing
        try:
            json_data = json.loads(raw_output)
            texte_brut = json_data.get("texte_transcrit", "Clé 'texte_transcrit' manquante dans la réponse.")
            # On retire la clé de transcription du JSON pour ne pas faire doublon à l'affichage
            meta_json = {k: v for k, v in json_data.items() if k != "texte_transcrit"}
        except Exception:
            texte_brut = f"Erreur de formatage JSON par le modèle. Voici le retour brut :\n\n{raw_output}"
            meta_json = {"erreur": "Le modèle n'a pas renvoyé un JSON valide."}

        return texte_brut, meta_json, premiere_page

    except Exception as e:
        return f"Erreur de traitement : {str(e)}", {"erreur": str(e)}, None

# --- DESIGN DE L'INTERFACE (Gradio 6.0) ---
with gr.Blocks(title="Data Cleaner Vision Lab") as demo:
    gr.Markdown("# 🧼 Data Cleaner 2 - Vision Sandbox (Agnostique)")
    gr.Markdown("Extraction brute et analyse de documents complexes sans biais ni indices préalables.")
    
    with gr.Row():
        # Colonne de gauche : Entrée et Aperçu de l'image
        with gr.Column(scale=1):
            file_input = gr.File(label="Charge ton fichier test.pdf", file_types=[".pdf"])
            image_preview = gr.Image(label="Aperçu de la page analysée (Poppler)", type="pil", interactive=False)
            submit_btn = gr.Button("Démarrer la transcription", variant="primary")
            
# Colonne de droite : Transcription brute géante et Métadonnées
        with gr.Column(scale=1):
            text_output = gr.Textbox(
                label="Transcription Textuelle Brute (Respect des lignes original)", 
                lines=18, 
                interactive=False
                # On a simplement retiré : show_copy_button=True
            )
            metadata_output = gr.JSON(label="Métadonnées d'analyse")
            
    submit_btn.click(
        fn=traiter_document,
        inputs=[file_input],
        outputs=[text_output, metadata_output, image_preview]
    )

if __name__ == "__main__":
    demo.launch(theme=gr.themes.Soft())
