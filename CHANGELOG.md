# Changelog

All notable changes to **DataCompiler** are documented in this file.

This changelog follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2026-11-05

### Added
- Automatic page-level OCR routing for native text, targeted OCR, and full-page scan transcription.
- Full-page OCR through OpenRouter-hosted NVIDIA models, with multiple model candidates available for review.
- Saved OCR review sessions and a browser-based interface for resolving disagreements between candidate transcriptions.
- Page-level language and OCR-routing information in processed documents.
- XLIFF line-aware translation units that preserve source line boundaries and geometry when translated text is rendered to PDF.

### Changed
- The default `auto` mode now selects full-page OCR for eligible scans while keeping native-text and vector-text processing on their specialized paths.
- Added the optional `openai` extra for OpenRouter OCR; Mistral and Qwen integrations remain optional.
- DeepL English targets use explicit locale codes such as `EN-US`.
- Prepared the release link for the CPython 3.12 Apple Silicon wheel targeting macOS 26.0 or later: [download](https://github.com/andrematuszak/datacompiler/releases/download/v0.3.0/datacompiler-0.3.0-cp312-cp312-macosx_26_0_arm64.whl).

### Fixed
- Improved handling of incomplete or provider-specific vision-model responses.
- Preserved XLIFF ordering and source geometry when importing reviewed translations.
- Corrected OCR routing and result normalization across supported backends.

## [0.2.0] - 2026-10-20

### Added
- **Reconstructed PDF workflow** as the default and recommended CLI behavior. Reconstructed text follows the resolved reading order, while unchanged vector glyphs, images, and non-text drawings are preserved.
- **Document editor** for reviewing and editing resolved text and its layout. Edits can include moving or resizing text, changing text and styles, adjusting colors, and splitting or merging segments. Supported edits can be saved in a layout sidecar for later rendering.
- **XLIFF 1.2 translation workflow** with export, import, segment identifiers, and PDF rendering. Alignment handles text spanning multiple detected table cells while preserving segment order and source content.
- **Human translation review through Matecat**, including project submission and reviewed XLIFF import.
- **Optional DeepL pre-translation** and **COMETKiwi translation quality estimation** for review prioritization.
- **Language detection** to guide targeted OCR, with a language override available for documents without usable native text.
- CLI and Python API entry points for document processing, editing, translation, and rendering.

### Changed
- `rebuilt` is the normal CLI strategy; `clean_overlay` is deprecated and falls back to `rebuilt` with a warning.
- Published the CPython 3.12 wheel for Apple Silicon on macOS 26.0 or later: [download](https://github.com/andrematuszak/datacompiler-core/releases/download/v0.2.0/datacompiler-0.2.0-cp312-cp312-macosx_26_0_arm64.whl).
- Improved reconstructed PDF rendering to preserve the appearance of vector glyphs and prevent glyphs from disappearing.
- Python support is declared as 3.11 or later; Python 3.12 is documented as tested.
- Development and test tools are provided through the `[dev]` optional dependency group rather than required runtime dependencies.
- The legacy `examples/basic_usage.py` script has been removed. The README and the sample PDF in `examples/` are the usage guide and input example.

### Notes
- PaddlePaddle and PaddleOCR are base dependencies for the normal reconstructed-PDF workflow. The published wheel is tagged `macosx_26_0_arm64`; no other platform wheel is listed in the release.
- Full-page Mistral OCR remains disabled in the documented active workflow because global OCR-to-native text alignment has not been validated.
- DeepL translation sends segment text to the DeepL service and requires a user-provided API key. COMETKiwi quality scores are not calibrated probabilities.
- GUI editing requires Tkinter and a graphical desktop session.

## [0.1.0] - 2026-10-07

### Added
- Initial six-stage PDF processing pipeline:
  1. Parallel text and document extraction using PyMuPDF and pdfplumber.
  2. Automatic analysis of native text quality and visual integrity.
  3. Mistral full-page OCR integration (disabled in the active workflow; see notes below).
  4. Targeted OCR for vectorized regions using PaddleOCR.
  5. Layout reconstruction, reading-order resolution, and conflict handling.
  6. Multiple rendering strategies, including faithful PDF, flow, rebuilt PDF, Markdown, HTML, and DOCX.
- Command-line interface via the `datacompiler` command.
- Installation and quickstart documentation for the published macOS wheel.
- Example PDF and CLI/Python usage instructions.
- Tests that depend on the reference PDF are skipped when that file is unavailable.
- Removed unused `.woff`/`.woff2` font variants and Marianne fonts; added font licensing documentation.
- Added generated outputs, tool caches, and the `private/` directory to `.gitignore`.

### Changed
- Python 3.11 or later is required; Python 3.12 is documented as tested.
- `pytest` was moved from required dependencies to the `[dev]` extra.

### Notes
- Full-page Mistral OCR is disabled because global alignment between OCR and native text has not been validated.
- The `0.1.0` CLI documentation says `--format` is accepted but ignored; use `--strategy`.
- One output format is produced per run, and output files are written next to the source PDF.

[0.2.0]: https://github.com/andrematuszak/datacompiler-core/releases/tag/v0.2.0
[0.3.0]: https://github.com/andrematuszak/datacompiler/releases/tag/v0.3.0
[0.1.0]: https://github.com/andrematuszak/datacompiler/releases/tag/v0.1.0
