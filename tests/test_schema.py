import sys, json
sys.path.insert(0, ".")

from datacompiler.model.document import Document, Page, Word, BBox
from datacompiler.frontend.diagnostic import diagnostiquer, pages_a_ocriser
from datacompiler.compile import resoudre


def w(id, text, x0, y0, x1, y1):
    return Word(id=id, text=text, bbox=BBox(x0, y0, x1, y1), font_size=10.0)


def ocr_w(id, text, confidence):
    return Word(id=id, text=text, bbox=None, confidence=confidence, source="mistral")


print("=== Test A : diagnostic par page (page 1 propre et assez longue, page 2 sans texte natif) ===")
doc = Document()
doc.metadata.filename = "test.pdf"

page1 = Page(number=1, width=600, height=800)
# 40 mots propres -- assez pour dépasser SEUIL_MOTS_FIABLE (30) et isoler le
# test de la propreté du texte de celui de la confiance liée à l'échantillon
# (cf. Test A2 plus bas, qui teste spécifiquement le cas court).
texte_propre = ("Ceci est un texte tout à fait normal et suffisamment long pour "
                "que le diagnostic de qualité dispose d un échantillon fiable et "
                "ne bascule pas vers une recommandation OCR par précaution ici").split()
page1.native.words = [w(i + 1, mot, 50 + i * 10, 100, 60 + i * 10, 110) for i, mot in enumerate(texte_propre)]

page2 = Page(number=2, width=600, height=800)
# aucun mot natif -> diagnostic doit forcer recommend_ocr=True pour CETTE page seulement
page2.native.words = []

doc.pages = [page1, page2]
diagnostiquer(doc)

print("  page1.diagnostic.recommend_ocr =", doc.pages[0].diagnostic.recommend_ocr, "(attendu False)")
print("  page2.diagnostic.recommend_ocr =", doc.pages[1].diagnostic.recommend_ocr, "(attendu True)")
print("  pages_a_ocriser(doc) =", pages_a_ocriser(doc), "(attendu [2])")


print("\n=== Test A2 : angle mort -- page trop courte, confiance insuffisante ===")
page_courte = Page(number=1, width=600, height=800)
page_courte.native.words = [w(1, "Texte", 50, 100, 100, 110), w(2, "propre", 105, 100, 150, 110)]
doc_court = Document()
doc_court.pages = [page_courte]
diagnostiquer(doc_court)
diag = doc_court.pages[0].diagnostic
print("  2 mots seulement -> confiance_suffisante =", diag.confiance_suffisante, "(attendu False)")
print("  -> recommend_ocr =", diag.recommend_ocr, "(attendu True, par précaution)")


print("\n=== Test A3 : angle mort -- symbole corrompu détecté (indépendant de la longueur) ===")
page_symbole = Page(number=1, width=600, height=800)
texte_avec_symbole = "Montant de 8.68 e et de 1.73 e et de 10.41 e pour ce document assez long merci".split()
page_symbole.native.words = [w(i + 1, mot, 50 + i * 10, 100, 60 + i * 10, 110) for i, mot in enumerate(texte_avec_symbole)]
doc_symbole = Document()
doc_symbole.pages = [page_symbole]
diagnostiquer(doc_symbole)
diag2 = doc_symbole.pages[0].diagnostic
print("  symboles_suspects =", diag2.symboles_suspects, "(attendu {'e': 3})")
print("  -> recommend_ocr =", diag2.recommend_ocr, "(attendu True, malgré un texte par ailleurs long et propre)")


print("\n=== Test B : l'OCR est ignoré sur une page propre même si des données OCR existent ===")
# Simule le cas réel : l'API Mistral tourne sur tout le PDF, donc page1 (propre,
# recommend_ocr=False) reçoit quand même des données OCR -- resolve/ ne doit
# PAS les utiliser pour cette page.
page1.ocr.words = [ocr_w(1, "Texte", 0.9), ocr_w(2, "PROPRE_OCR_DIFFERENT", 0.99)]
resoudre(doc)
sortie_page1 = [m.output_text for m in doc.pages[0].resolved.words]
print("  resolved page1 :", sortie_page1)
print("  OCR bien ignoré sur page propre :", "PROPRE_OCR_DIFFERENT" not in sortie_page1)


print("\n=== Test C : Decision peuplé sur un conflit natif/OCR ===")
page3 = Page(number=1, width=600, height=800)
page3.native.words = [w(1, "monta1t", 50, 100, 100, 110)]
page3.ocr.words = [ocr_w(1, "montant", 0.97)]
doc3 = Document()
doc3.pages = [page3]
diagnostiquer(doc3)
resoudre(doc3)
mot = doc3.pages[0].resolved.words[0]
print("  output_text:", mot.output_text)
print("  decision:", mot.decision)


print("\n=== Test D : round-trip JSON (to_dict/from_dict) avec Decision + diagnostic par page ===")
brut = json.loads(doc3.to_json())
print("  'diagnostic' absent au niveau document :", "diagnostic" not in brut)
print("  'diagnostic' présent au niveau page :", "diagnostic" in brut["pages"][0])
print("  'decision' présent sur le mot corrigé :", brut["pages"][0]["resolved"]["words"][0]["decision"] is not None)

doc3_reload = Document.from_dict(brut)
mot_reload = doc3_reload.pages[0].resolved.words[0]
print("  après reload -- output_text:", mot_reload.output_text)
print("  après reload -- decision.regle:", mot_reload.decision.regle)
print("  après reload -- page.diagnostic.recommend_ocr:", doc3_reload.pages[0].diagnostic.recommend_ocr)


print("\n=== Test E : Decision peuplé sur une ligature (pas de conflit OCR) ===")
page4 = Page(number=1, width=600, height=800)
page4.native.words = [w(1, "e\ufb03cace", 50, 100, 100, 110)]
doc4 = Document()
doc4.pages = [page4]
diagnostiquer(doc4)
resoudre(doc4)
mot4 = doc4.pages[0].resolved.words[0]
print("  output_text:", mot4.output_text, "| decision:", mot4.decision)
