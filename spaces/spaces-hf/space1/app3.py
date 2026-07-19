import os
import io
import gradio as gr
from pdf2image import convert_from_path
from PIL import Image
import base64
import json
import spaces
# On utilise le client officiel de Hugging Face, mieux toléré par l'infrastructure réseau ZeroGPU
from huggingface_hub import InferenceClient

# Récupération automatique du token configuré dans les secrets de ton Space
HF_TOKEN = os.getenv("HF_TOKEN")

# Initialisation du client officiel pour le modèle Qwen
client = InferenceClient(model="Qwen/Qwen2.5-VL-7B-Instruct", token=HF_TOKEN)

@spaces.GPU
def traiter_document(pdf_file):
    """
    Fonction principale avec le décorateur obligatoire pour éviter le RuntimeError.
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
        
        # Encodage de l'image en base64 pour l'envoi multimodal propre
        base64_image = base64.b64encode(img_bytes).decode('utf-8')
        data_url = f"data:image/jpeg;base64,{base64_image}"
        
        # 2. Construction du prompt de nettoyage sémantique
        prompt = (
            "Tu es un expert en extraction de documents dégradés ou raturés. "
            "Analyse cette image. Extrais tout le texte et toutes les lignes financières sans exception. "
            "Attention absolue : Ne saute aucune ligne manuscrite, même si elle semble raturée, "
            "gribouillée ou partiellement effacée (porte une attention critique aux termes comme 'praca' ou 'gotówka'). "
            "Retourne un résultat structuré proprement au format JSON avec les clés suivantes : "
            "'statut_document', 'donnees_financieres_identifiees', 'texte_brut_total'."
        )

        # 3. Appel via l'InferenceClient officiel (structure de Chat Completion)
        # Cette syntaxe standardisée est le moyen le plus sûr de franchir le proxy ZeroGPU
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_url}}
                ]
            }
        ]
        
        response = client.chat_completion(
            messages=messages,
            max_tokens=1024
        )
        
        # Extraction du texte de la réponse
        resultat_texte = response.choices[0].message.content
        
        return resultat_texte, premiere_page
        
    except Exception as e:
        return f"Erreur lors du traitement du document : {str(e)}", None

# Design de l'interface graphique Gradio d'origine
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
