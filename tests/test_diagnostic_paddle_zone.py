import argparse
import pymupdf
import numpy as np
from paddleocr import PaddleOCR


def main():
    parser = argparse.ArgumentParser(
        description="Diagnostic PaddleOCR sur une zone PDF."
    )
    parser.add_argument("pdf", help="Chemin du fichier PDF")
    parser.add_argument(
        "--page", type=int, default=0, help="Index de la page (0-based)"
    )
    parser.add_argument(
        "--bbox",
        type=float,
        nargs=4,
        required=True,
        metavar=("X0", "Y0", "X1", "Y1"),
        help="Zone cible en points PDF (x0 y0 x1 y1)",
    )
    parser.add_argument(
        "--dpi", type=int, default=300, help="DPI pour le rendu raster"
    )
    parser.add_argument(
        "--lang", default="fr", help="Langue pour PaddleOCR (ex: fr, en)"
    )
    args = parser.parse_args()

    doc = pymupdf.open(args.pdf)
    page = doc[args.page]
    rect = pymupdf.Rect(*args.bbox)

    scale = args.dpi / 72.0
    matrix = pymupdf.Matrix(scale, scale)
    pix = page.get_pixmap(matrix=matrix, clip=rect, alpha=False)

    crop_path = "_diag_paddle_crop.png"
    pix.save(crop_path)
    print(
        f"Crop sauvegardé : {crop_path} ({pix.width}x{pix.height}px à {args.dpi} DPI)"
    )

    print(f"\nInitialisation de PaddleOCR (lang='{args.lang}')...")
    ocr = PaddleOCR(
        use_textline_orientation=False,
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        lang=args.lang,
    )

    img_np = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
        (pix.height, pix.width, 3)
    )
    results = ocr.ocr(img_np)

    print("\n--- Détections PaddleOCR ---")
    if not results or not results[0]:
        print("❌ Aucun texte détecté dans cette zone.")
        return

    dx, dy = args.bbox[0], args.bbox[1]
    res = results[0]

    # Format PaddleOCR 3.x (Dictionnaire)
    if isinstance(res, dict):
        texts = res.get("rec_texts", [])
        scores = res.get("rec_scores", [])
        boxes = res.get("dt_polys", res.get("rec_polys", res.get("rec_boxes", [])))

        if not texts:
            print("❌ Aucun texte détecté dans ce dictionnaire.")
            return

        for box, text, score in zip(boxes, texts, scores):
            x_coords = [p[0] for p in box]
            y_coords = [p[1] for p in box]

            x0_pdf = dx + min(x_coords) / scale
            y0_pdf = dy + min(y_coords) / scale
            x1_pdf = dx + max(x_coords) / scale
            y1_pdf = dy + max(y_coords) / scale

            print(
                f"  Texte: {text!r:15s} | Confiance: {score:.2f} | "
                f"bbox PDF: ({x0_pdf:.2f}, {y0_pdf:.2f}, {x1_pdf:.2f}, {y1_pdf:.2f})"
            )

    # Format PaddleOCR 2.x (Liste de tuples)
    elif isinstance(res, list):
        for line in res:
            if not line:
                continue
            box, (text, confidence) = line
            x_coords = [p[0] for p in box]
            y_coords = [p[1] for p in box]

            x0_pdf = dx + min(x_coords) / scale
            y0_pdf = dy + min(y_coords) / scale
            x1_pdf = dx + max(x_coords) / scale
            y1_pdf = dy + max(y_coords) / scale

            print(
                f"  Texte: {text!r:15s} | Confiance: {confidence:.2f} | "
                f"bbox PDF: ({x0_pdf:.2f}, {y0_pdf:.2f}, {x1_pdf:.2f}, {y1_pdf:.2f})"
            )
            
if __name__ == "__main__":
    main()
