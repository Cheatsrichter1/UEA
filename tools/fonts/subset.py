"""Make the report font: DejaVu Sans cut down to Latin, Greek and the signs the reports use.

Run with fontTools, which UEA does not depend on:

    uv run --no-project --with fonttools python tools/fonts/subset.py /usr/share/fonts/truetype/dejavu

The output goes to src/uea/export/fonts/. DejaVu's licence allows modified copies as long as
the name contains neither "Bitstream" nor "Vera" (src/uea/export/fonts/LICENSE-DejaVu.txt).
"""

import sys
from pathlib import Path

from fontTools import subset

RANGES = [
    (0x20, 0x7E),  # ASCII
    (0xA0, 0x17F),  # Latin-1, Latin Extended-A: ä ö ü ß ² ³ · × °
    (0x300, 0x36F),  # combining marks: the dot of V̇
    (0x370, 0x3FF),  # Greek
    (0x2010, 0x2044),  # dashes, quotes, bullet, ‰
    (0x2070, 0x209F),  # super- and subscripts
    (0x20AC, 0x20AC),  # €
    (0x2190, 0x21FF),  # arrows
    (0x2200, 0x22FF),  # mathematical operators: √ ≤ ≥ ≈ ∑
    (0x2300, 0x2300),  # ⌀
    (0x25A0, 0x25CF),  # squares, circles
]

src = Path(sys.argv[1])
out = Path(__file__).resolve().parents[2] / "src/uea/export/fonts"
codes = [c for a, b in RANGES for c in range(a, b + 1)]
for name in ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf"):
    opts = subset.Options()
    opts.layout_features = ["*"]
    opts.name_IDs = ["*"]
    opts.notdef_outline = True
    font = subset.load_font(str(src / name), opts)
    s = subset.Subsetter(opts)
    s.populate(unicodes=codes)
    s.subset(font)
    subset.save_font(font, str(out / name), opts)
    print(name, (out / name).stat().st_size)
