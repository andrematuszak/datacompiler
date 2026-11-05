# DataCompiler

DataCompiler processes PDF documents and produces a reconstructed PDF. The published `0.3.0` wheel targets **Python 3.12 on Apple Silicon (ARM64) running macOS 26.0 or later**.

> This wheel is tagged `macosx_26_0_arm64`; it is not a universal wheel. The `0.3.0` release lists no wheel for Intel Macs, Windows, Linux, or earlier macOS versions. The `0.1.0` wheel remains available from the earlier [public-repository release](https://github.com/andrematuszak/datacompiler/releases/tag/v0.1.0).

## Requirements and installation

Check that Python 3.12 is available:

```bash
python3.12 --version
```

Create and activate a virtual environment, then install the published `0.3.0` wheel:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install  https://github.com/andrematuszak/datacompiler/releases/download/v0.3.0/datacompiler-0.3.0-cp312-cp312-macosx_26_0_arm64.whl
```

Verify the environment and that the command is available:

```bash
python --version
python -m pip show datacompiler
command -v datacompiler
```

`python --version` should report Python 3.12. `command -v datacompiler` should return the path to the command installed in the virtual environment.

PaddlePaddle and PaddleOCR are installed as base dependencies for the normal reconstruction workflow. The first OCR run may download model files and require an Internet connection.

## CLI quickstart

Download the sample, then run with or without an optional strategy. The default mode is compilation & transcription.

**Mixed document: glyphs and native text**

The default mode is a compilation and transcription into a file that is faithful to the source and rebuilt in the original format.

```bash
curl -L -o tax-notice.pdf https://raw.githubusercontent.com/andrematuszak/datacompiler/main/examples/tax-notice.pdf
datacompiler tax-notice.pdf
```

The command creates `tax-notice_rebuilt.pdf` next to the source file. See other formats and strategies below.


**Handwritten scan**

The default mode is a compilation and transcription into a text in the original format.

You need an active **OpenRouter API key** in your environment variables.
Step 1: Get an OpenRouter API Key

1. Go to [OpenRouter](https://openrouter.ai/).
2. Sign up for a free account or log in.
3. Navigate to your account settings or directly to the [API Keys dashboard](https://openrouter.ai/keys).
4. Click **Create Key**, give it a descriptive name (e.g., `datacompiler-key`), and generate it.
5. **Copy the key** immediately and store it securely (it will only be shown once).

---

Step 2: Set the Environment Variable and run the program

Before running the command, you need to expose your API key to your terminal session. Choose one of the methods below:

Run this command in your terminal, replacing `your_openrouter_api_key_here` with your actual key:
```bash
export OPENROUTER_API_KEY="your_openrouter_api_key_here"
curl -L -o polish.pdf https://raw.githubusercontent.com/andrematuszak/datacompiler/main/examples/polish.pdf
datacompiler polish.pdf
```

The command creates `polish_rebuilt.pdf` next to the source file. See other formats and strategies below.


## Other formats and strategies

Other output formats and strategies are available; for example, `--format faithful-pdf` requires an explicit `overlay` or `rasterized` strategy.


## Other modes

**Translation**

Use `--translate [language locale]` to translate the content of the file.


## Python usage

```python
from datacompiler import executer_pipeline

document = executer_pipeline("tax-notice.pdf", strategy="rebuilt")
print(f"Pages processed: {len(document.pages)}")
```

`executer_pipeline` writes a reconstructed PDF by default and returns the processed document.


## OCR

The default `auto` mode routes each page based on its diagnostic. Native text is retained when it is healthy, PaddleOCR handles targeted vector-text regions, and eligible full-page scans can use vision-language OCR through OpenRouter. Install the `openai` extra and configure `OPENROUTER_API_KEY` to enable that route.

| `ocr_mode` / `--ocr-mode` option | Behavior |
|---|---|
| `auto` (default) | Selects a per-page route, including full-page vision OCR for eligible scans |
| `vector` | Targeted vector-text OCR |
| `skip` | Disables OCR; not recommended for the normal reconstruction workflow |
| `force` | Not implemented |

`force` remains unimplemented; automatic routing is the supported full-page OCR path. One output format is produced per run.


## Sample files and license

The samples are available in the folder [`examples`]. Use the CLI or Python quickstart above to process it. The project is distributed under a proprietary license; see [`LICENSE`](LICENSE).
