# Tools

Scripts that are not part of UEA and not held to the code rules in `CLAUDE.md`.

## `fonts/`

`subset.py` cuts DejaVu Sans and its bold down to Latin, Greek and the signs the calculation reports use, for `src/uea/export/fonts/` (`docs/decisions/services.md#0036-heating-and-plumbing-sheets`). It needs fontTools, which UEA does not depend on:

```bash
uv run --no-project --with fonttools python tools/fonts/subset.py /usr/share/fonts/truetype/dejavu
```
