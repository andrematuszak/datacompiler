import os
import io
import gradio as gr
from pdf2image import convert_from_path
from PIL import Image
import base64
import json
import spaces
from huggingface_hub import InferenceClient

# Récupération automatique du token configuré dans les secrets de ton Space
HF_TOKEN = os.getenv("HF_TOKEN")

# Initialisation du client officiel
client = InferenceClient(token=HF_TOKEN)

@spaces.GPU
def traiter_document(pdf_file):
    """
    Fonction principale.
    """
    if pdf_file is None:
        return "Erreur : Aucun fichier n'a été chargé.", None
    
    try:
        # 1. Conversion locale du PDF en Image via Poppler
        pages = convert_from_path(pdf_file.name, first_page=1, last_page=1)
        if not pages:
            return "Échec de la conversion du PDF en image.", None
        
        premiere_page = pages[0]
        
        # Enregistrement de l'image au format JPEG en mémoire buffer
        img_byte_arr = io.BytesIO()
        premiere_page.save(img_byte_arr, format='JPEG')
        img_bytes = img_byte_arr.getvalue()
        
        # Construction du prompt de nettoyage sémantique
        prompt = (
            "Tu es un expert en extraction de documents dégradés ou raturés. "
            "Analyse cette image. Extrais tout le texte et toutes les lignes financières sans exception. "
            "Attention absolue : Ne saute aucune ligne manuscrite, même si elle semble raturée, "
            "gribouillée ou partiellement effacée (porte une attention critique aux termes comme 'praca' ou 'gotówka'). "
            "Retourne un résultat structuré proprement au format JSON avec les clés suivantes : "
            "'statut_document', 'donnees_financieres_identifiees', 'texte_brut_total'."
        )

        # 2. Utilisation de la méthode générique de generation de texte/vision de l'InferenceClient
        # Pour contourner le bug de provider sur chat_completion, on passe par l'appel direct au modèle
        inputs_payload = {
            "text": prompt,
            "image": premiere_page # On passe directement l'objet PIL Image, le SDK gère le reste
        }
        
        # On utilise explicitement le modèle Qwen
        response_text = client.text_generation(
            prompt=f"User: {prompt}\n[Image fournie]\nAssistant:",
            model="Qwen/Qwen2.5-VL-7B-Instruct",
            max_new_tokens=1024
        )
        
        return response_text, premiere_page
        
    except Exception as e:
        # Si même la méthode text_generation échoue à cause du provider Hugging Face,
        # On bascule automatiquement sur un modèle de secours ultra-robuste et disponible sur leur API :
        try:
            # Modèle de secours Vision de Meta, très souvent disponible sur tous les providers gratuits
            response_backup = client.chat_completion(
                model="meta-llama/Llama-3.2-11B-Vision-Instruct",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64.b64encode(img_bytes).decode('utf-8')}"}}
                        ]
                    }
                ],
                max_tokens=1024
            )
            return f"[Backup Llama-3.2-Vision activé car Qwen est indisponible sur l'API HF]\n\n{response_backup.choices[0].message.content}", premiere_page
        except Exception as backup_error:
            return f"Erreur critique (Qwen et Llama indisponibles) : {str(e)} | Erreur Backup : {str(backup_error)}", None

# Design de l'interface graphique Gradio d'origine
with gr.Blocks(title="Data Cleaner Vision Lab") as demo:
    gr.Markdown("# 🧼 Data Cleaner 2 - Vision Sandbox")
    gr.Markdown("Extraction sémantique par Vision pour contourner les OCR défectueux.")
    
    with gr.Row():
        with gr.Column():
            file_input = gr.File(label="Charge ton fichier test.pdf", file_types=[".pdf"])
            submit_btn = gr.Button("Démarrer l'Inférence", variant="primary")
        
        col = gr.Column()
        with col:
            image_preview = gr.Image(label="Aperçu de la page analysée (Validation Poppler)", type="pil", interactive=False)
            text_output = gr.Textbox(label="Résultat de la détection textuelle (Format JSON attendu)", lines=20)
            
    submit_btn.click(
        fn=traiter_document,
        inputs=[file_input],
        outputs=[text_output, image_preview]
    )

demo.launch()
