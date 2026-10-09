# 📊 DataCompiler

**DataCompiler** est un pipeline complet de compilation, de traitement et de reconstruction de documents PDF. Il combine une extraction multi-moteurs, un diagnostic de la qualité native du texte, des étapes d'OCR intelligentes (globales ou ciblées) ainsi qu'un moteur d'arbitrage et de rendu dynamique multi-format.

🌐 **Site web officiel :** [https://data-compiler.com](https://data-compiler.com) *(en cours de construction)*

---

## ⚠️ Prérequis : version de Python

DataCompiler requiert :
- **macOS 12+** (Apple Silicon / ARM64)
- **Python 3.12**

> ⚠️ v0.1.0 : wheel binaire **macOS Apple Silicon uniquement**, Python 3.12 uniquement.
> Les versions x86_64 et Python 3.11 ne sont pas encore fournies.

PaddleOCR / PaddlePaddle sont installés automatiquement comme dépendances ; le premier lancement de l'OCR ciblé peut télécharger les modèles Paddle (connexion Internet requise).

---

### Installation

**macOS Apple Silicon, Python 3.12 :**

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install https://github.com/andrematuszak/datacompiler/releases/download/v0.1.0/datacompiler-0.1.0-cp312-cp312-macosx_12_0_arm64.whl
```

---

## 🚀 Quickstart (Démarrage Rapide)

### En ligne de commande

```bash
curl -O https://raw.githubusercontent.com/andrematuszak/datacompiler/main/examples/impots-revenu.pdf
```


```bash
datacompiler impots-revenu.pdf --strategy overlay
```

OU

```bash
datacompiler impots-revenu.pdf --strategy rebuilt
```

Les fichiers de sortie sont écrits **à côté du PDF source** (voir « Formats de sortie »).

> **Note v0.1.0 :** le format de sortie est choisi par `--strategy`.
> - **En ligne de commande** : `overlay` (défaut), `clean_overlay`, `rasterized`, `flow`, `rebuilt`.
> - **En Python** : les mêmes, plus `markdown`, `html` et `docx`.
>
> L'option `--format` est acceptée mais **n'est pas prise en compte** : utilisez `--strategy`.

### En Python

```python
from datacompiler import executer_pipeline

# Un appel = un format de sortie, choisi par `strategy`
doc = executer_pipeline(
    "mon_document.pdf",
    strategy="overlay",      # overlay | clean_overlay | rasterized | flow | rebuilt | markdown | html | docx
    ocr_mode="auto",         # auto | vector | skip  (force : voir « Étape 3 »)
)

print(f"Document traité avec succès ! Nombre de pages : {len(doc.pages)}")
```

`executer_pipeline` retourne un objet `Document` (`doc.pages`, `doc.metadata`, `doc.diagnostic`, `doc.to_json()`).
Pour produire plusieurs formats, appelez-la une fois par `strategy`.
Un exemple exécutable est fourni dans [`examples/basic_usage.py`](examples/basic_usage.py) : sans argument, il génère un petit PDF d'exemple puis le traite ; avec un chemin en argument, il traite votre PDF.

---

## ⚙️ Architecture & Pipeline de Fonctionnement

Le pipeline se déroule en **6 étapes** (les logs affichent `[1/6]` … `[6/6]`) :

```
📄 PDF Source ➔ [1. Extraction] ➔ [2. Diagnostic] ➔ [3. OCR ciblé] ➔ [4. Segmentation] ➔ [5. Compilation] ➔ [6. Rendu] ➔ 📁 Fichiers Sortie
```

### 🔍 1. Extraction (`frontend/extract`)
Ouverture parallèle du PDF via **PyMuPDF** et **pdfplumber**. Extraction native du texte, des polices, des images, des éléments vectoriels et reconstruction des tableaux dans le modèle standardisé `Document`.

### 🩺 2. Diagnostic (`frontend/diagnostic`)
Analyse de l'intégrité du texte nativement extrait (score de qualité, symboles corrompus, couverture visuelle, détection de texte vectorisé/dessiné). Décide automatiquement si un OCR est nécessaire (`recommend_ocr = True`).

### 🤖 3. Traitement OCR (`frontend/ocr`)
En v0.1.0, seul l'**OCR ciblé** est actif : il vise les zones de texte vectorisées ou masquées et comble les trous géométriques à l'aide de **PaddleOCR**. Les modèles Paddle sont téléchargés au premier lancement (connexion Internet requise).

L'**OCR pleine page** est **désactivé** dans cette version : l'alignement global OCR ↔ texte natif n'est pas encore validé sans régression (duplication de mots). Le diagnostic peut le recommander, mais il n'est pas exécuté.

| `ocr_mode` / `--ocr-mode` | Comportement en v0.1.0 |
|---|---|
| `auto` (défaut) | OCR ciblé des zones vectorisées |
| `vector` | OCR ciblé des zones vectorisées uniquement |
| `skip` | Aucun OCR |
| `force` | Sans effet pour l'instant (OCR pleine page désactivé) |

### ⚙️ 4. Segmentation (`layout/`)
Suite au diagnostic de segmentation nécessaire (pages complexes), déclenchement de l'outil de segmentation (sections, tableaux, etc.) pour simuler un ordre de lecture naturel.

### ⚙️ 5. Compilation & Arbitrage (`compile/`)
* Reconstitution de l'ordre de lecture et de l'arbre de mise en page (`LayoutBox`).
* Normalisation typographique (ligatures, césures).
* Alignement géométrique natif ↔ OCR.
* Résolution des conflits et évaluation de confiance QA.

### 📦 6. Backend de Rendu (`backend/`)
Génération des fichiers de sortie nettoyés dans les formats demandés.

---

## 📁 Formats de Sortie Générés

Un fichier par exécution, selon `strategy` (`--strategy` en CLI), écrit à côté du PDF source :

| `strategy` | Fichier produit | Disponible en |
|---|---|---|
| `overlay`, `clean_overlay`, `rasterized` | `<nom>_propre.pdf` | CLI et Python |
| `flow` | `<nom>_flow.pdf` | CLI et Python |
| `rebuilt` | `<nom>_rebuilt.pdf` | CLI et Python |
| `markdown` | `<nom>_propre.md` | Python uniquement |
| `html` | `<nom>_propre.html` | Python uniquement |
| `docx` | `<nom>_propre.docx` | Python uniquement |

Sauf avec `--no-json`, un `<nom>.document.json` (arbre de données et métadonnées) est aussi écrit.

---

## 📜 Licence

Projet sous licence propriétaire — tous droits réservés. Voir le fichier [LICENSE](LICENSE).