"""Build the SIL-OFL Sensei Style derivative from a local Exo2[wght].ttf.

Usage: python scripts/build_sensei_font.py /path/to/Exo2[wght].ttf
Requires fonttools and brotli. See docs/SENSEI_STYLE_FONT.md for attribution.
"""
import sys
from pathlib import Path

if len(sys.argv) != 2:
    raise SystemExit(__doc__)
source_path = Path(sys.argv[1])

from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from fontTools.subset import Subsetter, Options
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.recordingPen import DecomposingRecordingPen

for weight,label in [(400,'Regular'),(700,'Bold')]:
    font=instantiateVariableFont(TTFont(source_path),{'wght':weight},inplace=True)
    options=Options(); options.layout_features=['*']; options.name_IDs=['*']; options.name_languages=['*']
    subsetter=Subsetter(options=options)
    subsetter.populate(unicodes=list(range(0x20,0x250))+list(range(0x400,0x530))+list(range(0x2000,0x2070))+[0x20AC,0x2116,0x2212])
    subsetter.subset(font)
    # Compact, slightly forward-leaning letterforms; preserve component transforms.
    glyphset=font.getGlyphSet(); rebuilt={}
    for name in font.getGlyphOrder():
        pen=TTGlyphPen(glyphset)
        source=DecomposingRecordingPen(glyphset)
        glyphset[name].draw(source)
        source.replay(TransformPen(pen,(0.96,0,0.025,1,0,0)))
        rebuilt[name]=pen.glyph()
    for name,glyph in rebuilt.items():
        font['glyf'][name]=glyph
        advance,bearing=font['hmtx'][name]
        font['hmtx'][name]=(round(advance*.96),round(bearing*.96))
    names=font['name']
    for record in names.names:
        values={1:'Sensei Style',2:label,4:f'Sensei Style {label}',6:f'SenseiStyle-{label}',16:'Sensei Style',17:label}
        if record.nameID in values:
            record.string=values[record.nameID].encode(record.getEncoding(),errors='replace')
    font.flavor='woff2'
    font.save(f'src/web/dojo/assets/sensei-style-{weight}.woff2')
