import os
import io
import requests
import gradio as gr
from pdf2image import convert_from_path
from PIL import Image
import spaces

HF_TOKEN = os.getenv("HF_TOKEN")
API_URL = "https://api-inference.huggingface.co/models/Qwen/Qwen2.5-VL-7B-Instruct"

def invoquer_qwen_vision(image):
    """Envoie l'image et le prompt à l'API d'Inference de Hugging Face"""
    # 1. Conversion de l'image PIL en octets JPEG
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format='JPEG')
    img_bytes = img_byte_arr.getvalue()

    # 2. Configuration des headers
    headers = {
        "Authorization": f"Bearer {HF_TOKEN}",
    }
    
    # 3. Prompt de nettoyage sémantique (Phase déductive)
    prompt = (
        "Tu es un expert en extraction de documents dégradés ou raturés. "
        "Analyse cette image. Extrais tout le texte et toutes les lignes financières sans exception. "
        "Attention absolue : Ne saute aucune ligne manuscrite, même si elle semble raturée, "
        "gribouillée ou partiellement effacée (porte une attention critique aux termes comme 'praca' ou 'gotówka'). "
        "Retourne un résultat structuré proprement au format JSON avec les clés suivantes : "
        "'statut_document', 'donnees_financieres_identifiees', 'texte_brut_total'."
    )

    # Pour l'API d'Inference de Hugging Face (Modèles Multimodaux), on envoie 
    # l'image en binaire et on passe les paramètres textuels dans les headers ou via une structure dédiée
    # Alternative standard et robuste pour l'API publique :
    payload = {
        "inputs": prompt,
        "parameters": {"max_new_tokens": 1024}
    }
    
    # Afin de passer l'image et le texte proprement à l'API d'Inference,
    # on utilise le format multipart/form-data ou l'envoi direct si l'API le supporte.
    # Pour Qwen2.5-VL sur l'API Serverless, l'envoi se fait ainsi :
    try:
        # On passe l'image directement dans 'data' et on peut ajouter le prompt si nécessaire,
        # ou utiliser l'API de chat de Hugging Face. Testons la méthode directe par fichier :
        response = requests.post(
            API_URL, 
            headers=headers, 
            json={"inputs": prompt, "image": img_bytes.decode('latin-1', errors='ignore')} # Astuce d'encodage textuel si JSON requis
        )
        
        # Si l'API préfère le format binaire brut (Binary payload) :
        if response.status_code != 200:
            # Deuxième approche standard de l'Inference API pour les images : envoyer les bytes directement
            # et laisser le modèle générer à partir du prompt par défaut, ou configurer l'en-tête X-Prompt
            headers["X-Wait-For-Model"] = "true"
            # Configuration de secours pour la transmission d'images multimodales
            # (Note : Qwen2.5-VL sur l'API publique utilise souvent l'encodage base64 dans le JSON)
            import base64
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
            
    except Exception as e:
        return f"Erreur lors de la requête : {str(e)}"

@spaces.GPU
def traiter_document(pdf_file):
    """Prend le PDF, extrait la première page et lance l'analyse"""
    if pdf_file is None:
        return "Erreur : Aucun fichier n'a été chargé.", None
    
    try:
        pages = convert_from_path(pdf_file.name, first_page=1, last_page=1)
        if not pages:
            return "Échec de la conversion du PDF en image.", None
        
        premiere_page = pages[0]
        resultat_extraction = invoquer_qwen_vision(premiere_page)
        
        # On s'assure de renvoyer le résultat sous forme de chaîne textuelle propre pour le Textbox
        import json
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
