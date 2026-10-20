# DataCompiler

DataCompiler processes PDF documents and produces a reconstructed PDF. The public `0.1.0` release includes a wheel for **macOS 12+ on Apple Silicon (ARM64) with Python 3.12**.

> This wheel does not support Intel Macs, Windows, or Linux. Installation instructions for those platforms are not provided here.
>
> The `0.1.0` wheel is the only published artifact verified here. The current code and packaging in `datacompiler-core` (0.2.0) are separate; its instructions should not be taken as verified documentation for this wheel.

## Requirements and installation

Check that Python 3.12 is available:

```bash
python3.12 --version
```

Create and activate a virtual environment, then install the published `0.1.0` wheel:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install https://github.com/andrematuszak/datacompiler/releases/download/v0.1.0/datacompiler-0.1.0-cp312-cp312-macosx_12_0_arm64.whl
```

Verify the environment and that the command is available:

```bash
python --version
python -m pip show datacompiler
command -v datacompiler
```

`python --version` should report Python 3.12. `command -v datacompiler` should return the path to the command installed in the virtual environment.

For the `0.1.0` wheel, its release documentation says PaddleOCR and PaddlePaddle are installed automatically as dependencies. This public repository does not include a `pyproject.toml` or the package source, so its dependency metadata cannot be checked here. For `datacompiler-core` 0.2.0, Paddle is required for the normal reconstruction workflow; the current manifest places it in the `[ocr]` extra, and its default installation is being aligned with that use. This source-code configuration is not a verified installation command for the `0.1.0` wheel.

## CLI quickstart

Download the sample PDF, then explicitly run the `rebuilt` strategy:

```bash
curl -L -o impots-revenu.pdf https://raw.githubusercontent.com/andrematuszak/datacompiler/main/examples/impots-revenu.pdf
datacompiler impots-revenu.pdf --strategy rebuilt
```

The `0.1.0` release README documents the output of this strategy as `impots-revenu_rebuilt.pdf`, next to the source file. It also says that an `impots-revenu.document.json` file containing the document and its metadata is written, unless `--no-json` is used. These filenames are documented for `0.1.0`, but could not be verified by running the wheel. Paddle is required for the reconstruction workflow; the models may be downloaded during the first targeted OCR run, which requires an Internet connection.

`rebuilt` is the recommended workflow. In the current `datacompiler-core` 0.2.0 README, it is also the default CLI strategy: running without options is documented to produce `document_rebuilt.pdf`. Use `--strategy rebuilt` to make the choice explicit and consistent regardless of the default.

> The `0.1.0` documentation in this repository also lists `overlay`, `clean_overlay`, `rasterized`, and `flow`. They are not described here because reconstruction is the intended workflow. That documentation says `--format` is accepted but ignored; use `--strategy`.

## Python usage

```python
from datacompiler.pipeline import executer_pipeline

doc = executer_pipeline("impots-revenu.pdf", strategy="rebuilt", ocr_mode="auto")
print(f"Pages processed: {len(doc.pages)}")
```

Each call to `executer_pipeline` produces one format, selected by `strategy`. The current `datacompiler-core` README documents `strategy="rebuilt"` and the public import `from datacompiler import executer_pipeline`. The import used by the `0.1.0` wheel cannot be independently confirmed because the wheel source is not present here. This repository's README describes the returned object as a `Document` with `pages`, `metadata`, `diagnostic`, and `to_json()`.

## OCR and version differences

The `0.1.0` release README in this repository says that only **targeted OCR** is active: it processes vectorized or hidden text regions. Full-page OCR is not run; according to that documentation, `force` does not enable full-page OCR. PaddleOCR/PaddlePaddle are required for the normal reconstruction workflow in `datacompiler-core` 0.2.0; the models may need to be downloaded on first use. Do not apply `datacompiler-core` packaging options to the `0.1.0` wheel without checking its dependencies.

| `ocr_mode` / `--ocr-mode` option in the `0.1.0` documentation | Documented behavior |
|---|---|
| `auto` (default) | Targeted OCR on vectorized regions |
| `vector` | Targeted OCR on vectorized regions |
| `skip` | No OCR |
| `force` | No effect on full-page OCR, which is disabled |

The options and OCR behavior in this table come from earlier `0.1.0` documentation; they could not be compared with the wheel implementation, which is not included in this repository. The current `datacompiler-core` README describes newer code and does not verify the wheel's behavior. The documentation describes one output format per run; to generate multiple formats, make one Python call per strategy.

## Sample PDF and license

The sample input PDF is available at [`examples/impots-revenu.pdf`](examples/impots-revenu.pdf). Use the CLI or Python quickstart above to process it. The project is distributed under a proprietary license; see [`LICENSE`](LICENSE).
