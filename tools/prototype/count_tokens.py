"""Prototype token count: a hand-written UEA project in the line format against the same data as JSON and YAML.

Not UEA code. Needs tiktoken (OpenAI's tokenizer, so an approximation for other models).
Usage: python3 count_tokens.py MODEL_DIR [SESSION_MD]
"""
import contextlib, io, json, re, runpy, sys
from pathlib import Path

import tiktoken

SCR = Path(__file__).resolve().parent
MODEL = Path(sys.argv[1])
_argv = sys.argv
sys.argv = ["check_model.py", str(MODEL)]
with contextlib.redirect_stdout(io.StringIO()):
    G = runpy.run_path(str(SCR / "check_model.py"))
sys.argv = _argv
assert not G["problems"], G["problems"]

ENCODINGS = ["o200k_base", "cl100k_base"]
enc = {name: tiktoken.get_encoding(name) for name in ENCODINGS}


def count(text):
    return [len(enc[name].encode(text)) for name in ENCODINGS]


def yaml(objs):
    out = []
    for o in objs:
        first = True
        for k, v in o.items():
            if isinstance(v, str) and (v == "" or re.search(r"[:#\-\s,\[\]{}\"']", v) or v[0] in "*&!|>%@`"):
                v = json.dumps(v, ensure_ascii=False)
            elif v is True:
                v = "true"
            out.append(f"{'- ' if first else '  '}{k}: {v}")
            first = False
    return "\n".join(out) + "\n"


objs = [G["to_obj"](G["els"][k]) for k in G["order"]]
n = len(objs)
rows = []
for f in G["FILES"]:
    rows.append((f"{f}.uea", (MODEL / f"{f}.uea").read_text(encoding="utf-8")))
line_text = "".join(t for _, t in rows)
variants = [
    ("line format (all .uea files)", line_text),
    ("JSON, minified", json.dumps(objs, ensure_ascii=False, separators=(",", ":"))),
    ("JSON, indented", json.dumps(objs, ensure_ascii=False, indent=2)),
    ("YAML", yaml(objs)),
]

print(f"{n} elements · encodings: {', '.join(ENCODINGS)}\n")
print("| File | Lines | Characters | " + " | ".join(ENCODINGS) + " |")
print("|---|---|---|" + "---|" * len(ENCODINGS))
for name, text in rows:
    print(f"| `{name}` | {len(text.splitlines())} | {len(text):,} | " + " | ".join(f"{c:,}" for c in count(text)) + " |")
print()
base = count(line_text)
print("| Format | Characters | " + " | ".join(ENCODINGS) + f" | Tokens per element ({ENCODINGS[0]}) | vs. line format |")
print("|---|---|" + "---|" * len(ENCODINGS) + "---|---|")
for name, text in variants:
    c = count(text)
    print(f"| {name} | {len(text):,} | " + " | ".join(f"{x:,}" for x in c) + f" | {c[0] / n:.1f} | {c[0] / base[0]:.2f}× |")

if len(sys.argv) > 2:
    md = Path(sys.argv[2]).read_text(encoding="utf-8")
    blocks = re.findall(r"```[a-z]*\n(.*?)```", md, flags=re.S)
    ops = [l for b in blocks for l in b.splitlines() if re.match(r"^[+~\->] ", l)]
    cli = "\n".join(blocks)
    print(f"\nsession: {len(ops)} operation lines shown, {count(chr(10).join(ops))[0]:,} tokens; "
          f"all CLI blocks (commands and output) {count(cli)[0]:,} tokens ({ENCODINGS[0]})")
