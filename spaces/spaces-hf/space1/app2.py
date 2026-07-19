import os
import io
import requests
import gradio as gr
from pdf2image import convert_from_path
from PIL import Image
import base64
import json
import spaces

HF_TOKEN = os.getenv("HF_TOKEN")
API_URL = "https://api-inference.huggingface.co/models/Qwen/Qwen2.5-VL-7B-Instruct"

def invoquer_qwen_vision_internet(img_bytes):
    """
    Cette fonction N'EST PAS décorée par @spaces.GPU.
    Elle a donc un accès complet à Internet pour appeler l'API externe.
    """
    headers = {
        "Authorization": f"Bearer {HF_TOKEN}",
        "X-Wait-For-Model": "true"
    }
    
    prompt = (
        "Tu es un expert en extraction de documents dégradés ou raturés. "
        "Analyse cette image. Extrais tout le texte et toutes les lignes financières sans exception. "
        "Attention absolue : Ne saute aucune ligne manuscrite, même si elle semble raturée, "
        "gribouillée ou partiellement effacée (porte une attention critique aux termes comme 'praca' ou 'gotówka'). "
        "Retourne un résultat structuré proprement au format JSON avec les clés suivantes : "
        "'statut_document', 'donnees_financieres_identifiees', 'texte_brut_total'."
    )

    base64_image = base64.b64encode(img_bytes).decode('utf-8')
    
    data_payload = {
        "inputs": {
            "query": prompt,
            "image": base64_image
        }
    }

    response = requests.post(API_URL, headers=headers, json=data_payload)
    
    if response.status_code == 200:
        return response.json()
    else:
        return f"Erreur de l'API Hugging Face ({response.status_code}) : {response.text}"


@spaces.GPU
def traiter_document(pdf_file):
    """
    Cette fonction est vue par le validateur de Hugging Face (ZeroGPU décore l'entrée).
    Elle convertit le PDF en image isolée, puis passe les octets à la fonction Internet.
    """
    if pdf_file is None:
        return "Erreur : Aucun fichier n'a été chargé.", None
    
    try:
        # 1. Conversion locale du PDF en Image via Poppler
        pages = convert_from_path(pdf_file.name, first_page=1, last_page=1)
        if not pages:
            return "Échec de la conversion du PDF en image.", None
        
        premiere_page = pages[0]
        
        # Enregistrement en octets de l'image pour le payload
        img_byte_arr = io.BytesIO()
        premiere_page.save(img_byte_arr, format='JPEG')
        img_bytes = img_byte_arr.getvalue()
        
        # 2. Appel de la fonction de requêtage externe (qui a accès au réseau)
        resultat_extraction = invoquer_qwen_vision_internet(img_bytes)
        
        # 3. Formatage de la réponse pour l'affichage
        if isinstance(resultat_extraction, (dict, list)):
            texte_propre = json.dumps(resultat_extraction, indent=4, ensure_ascii=False)
        else:
            texte_propre = str(resultat_extraction)
            
        return texte_propre, premiere_page
        
    except Exception as e:
        return f"Erreur lors du traitement du fichier : {str(e)}", None

# Design de l'interface graphique Gradio
with gr.Blocks(title="Data Cleaner Vision Lab") as demo:
    gr.Markdown("# 🧼 Data Cleaner 2 - Vision Sandbox")
    gr.Markdown("Extraction sémantique par Vision (Qwen2.5-VL) pour contourner les OCR défectueux.")
    
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
