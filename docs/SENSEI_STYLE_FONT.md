# Sensei Style

Sensei Style is a compact, slightly forward-leaning Cyrillic and Latin font for the Dojo UI. It is derived from the open-source Exo 2 font by the Exo 2 Project Authors, not an entirely original typeface. The supplied regular and bold WOFF2 files are static 400 and 700 weight instances, subset to Latin, Cyrillic and common punctuation; their outlines are horizontally condensed to 96% with a 2.5% forward shear and the metrics adjusted. Emoji and unsupported glyphs use system fallbacks.

Source: https://github.com/google/fonts/tree/main/ofl/exo2. The derivative retains the copyright notice and SIL Open Font License 1.1 in `src/web/dojo/assets/SENSEI_FONT_OFL.txt`.

To rebuild, obtain the upstream `Exo2[wght].ttf`, install `fonttools` and `brotli`, and run `python scripts/build_sensei_font.py /path/to/Exo2[wght].ttf` from the repository root.
