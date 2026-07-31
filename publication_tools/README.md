# Paper 10 visual and presentation tools

Run from the repository root:

```bash
python3 publication_tools/generate_publication_and_presentation.py
python3 publication_tools/validate_publication_and_presentation.py
```

Runtime dependencies are Python 3.11+, Pillow, python-pptx, and the system
`pdftoppm`. `ffmpeg` is optional; when installed it creates MP4/GIF animation.

The generator reads committed source CSVs in `data/publication/`, the
controlled scheduler CSV, and bounded native KiCad reports. It writes all
rendered assets to `build/publication_assets/` and `build/presentation/`.
Those generated files are intentionally ignored by Git. The generator does
not invent Gemma, energy, cost, synthesis, or physical-measurement data.
