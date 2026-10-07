# Tools

## `prototype/`

Throwaway scripts that work on the hand-written prototype in `docs/prototype/haus-mueller/`. They exist to test the draft format and to show what the model must be able to deliver. They are not UEA: untyped, untested, written fast, and not held to the code rules in `CLAUDE.md`. Real code replaces them from phase 1 on.

| Script | What it does |
|---|---|
| `check_model.py MODEL_DIR [OUT_DIR]` | Parses the `.uea` files, checks ids, prefixes and references, resolves every position to coordinates, runs the first validator rules (devices in openings, back-to-back boxes, switches on the hinge side) and prints rooms and areas. With `OUT_DIR` it also draws `grundriss-EG.svg` and `grundriss-OG.svg`. |
| `make_exports.py MODEL_DIR OUT_DIR` | Ansichten, Elektro-Installationspläne, Verteilungsplan, Heizungsschema and the `custom` lighting calculation for r2, as SVG and Markdown. Stops if `check_model.py` finds a problem. |
| `svg_to_png.sh DIR` | Renders every SVG in `DIR` to PNG with headless Firefox. |
| `count_tokens.py MODEL_DIR [SESSION_MD]` | Counts tokens of the model in the line format and of the same data as JSON and YAML. Needs `tiktoken`. |

Only `count_tokens.py` needs a package. Set it up once in a virtual environment (`.venv/` is ignored by git):

```bash
python3 -m venv .venv && .venv/bin/pip install -r tools/prototype/requirements.txt
```

Count tokens:

```bash
.venv/bin/python tools/prototype/count_tokens.py docs/prototype/haus-mueller docs/prototype/haus-mueller/session.md
```

Regenerate the prototype's exports:

```bash
python3 tools/prototype/make_exports.py docs/prototype/haus-mueller docs/prototype/haus-mueller/exports && tools/prototype/svg_to_png.sh docs/prototype/haus-mueller/exports
```

`tiktoken` is OpenAI's tokenizer. Claude tokenizes differently, so its counts are an approximation; the ratios between formats are the useful part.
