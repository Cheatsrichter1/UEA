# The line format

[Wiki home](README.md)

How a `.uea` file and a batch of operations are written, with examples. The rules are in [`ARCHITECTURE.md` §4 and §5](../../ARCHITECTURE.md#4-file-format); every kind with its fields is in [`docs/reference.md`](../reference.md); the reasons are in [0005](../decisions/0005-line-format.md), [0013](../decisions/0013-canonical-line-format.md) and [0014](../decisions/0014-operations-and-history.md).

## A line

One element per line:

```
kind  key  positional...  "label"  name=value...  flags   # comment
```

```
wall w5 EG IW-240 y=w1+4.51 x=w4..w2 lb
door d1 w2 1.135x2.26 y=w5+0.385 into=r5 hand=l type=TH-1
room r1 EG kitchen "Küche" at=w4+1,w1+1 floor=FB-fli
type AW-365 wall "Ziegel 36,5 verputzt" layers=putz-kalkgips:0.015,*ziegel-t9:0.365,putz-leicht:0.02
```

| Part | What it is |
|---|---|
| kind | The element kind: `wall`, `door`, `room`, `type` ... (`uea help <kind>`) |
| key | The id (`w5`) or, for a project, level, grid or type, its name (`EG`, `AW-365`) |
| positional | Fields the kind takes in a fixed order, without a name: a wall's storey and type, a door's host wall and size |
| `"label"` | Free text in quotes, in the language people use: `"Küche"`, `"Flst. 123/4"` |
| `name=value` | The other fields; a value with spaces is quoted: `plan="B-Plan Nr. 12"` |
| flags | Bare words: `lb` (load-bearing), `existing`, `demolish`, `default`; for some choice fields the value alone (`area`, an LV position's measure) |
| `#` | A comment, at the start of a line or after a space |

Fields at their default are left out. Units are fixed per field and never written: lengths in metres, angles in degrees (`uea help <kind>` names each unit).

## Ids and names

- **Ids** are a prefix and a number (`w12`, `d3`, `pl1`). UEA assigns them when an element is added and never reuses one, so an id in the history always means the same element.
- **Names** are what you choose for a project, a level, a grid or a type. They must not look like an id. Levels and grids take letters, digits and `_` but no `-`, because `W-1.2` means grid W minus 1.2. Types may use `-`: `AW-365`, `NYM-J3x1.5`.

## Values

| Value | Written | Example |
|---|---|---|
| Number | Decimal point, metres | `z=2.875`, `pitch=25` |
| Reference | An id or name | `type=TH-1`, `into=r5` |
| List of references | Joined by `,` | `via=ho1,ho2` |
| Size | Width `x` height | `1.135x2.26` |
| Layers | `material:thickness`, joined by `,`; `*` marks the core | `layers=plaster:0.015,*brick:0.365,render:0.02` |
| Position | An anchor, a sign and a distance (below) | `y=w1+4.51`, `x=E-` |
| Span | Two anchors joined by `..` | `x=W..E`, `y=w1..w3` |
| Point | Two anchors joined by `,`: x, then y | `at=w4+1,w1+1` |
| Outline | Points joined by `;`, in order round it | `outline=W-3,S-5;E+4,S-5;E+4,N+6;W-3,N+6` |
| Text | Quoted when it has spaces | `plan="§ 34 BauGB"` |

### Positions

Elements are placed relative to what is already there, like a dimension chain, so they move with it. Plan positions are the core faces of walls (Rohbau); heights count from the storey's finished floor.

```
x=w4+2.26     2.26 m past w4's +x face; the element extends in +x
x=E-          its +x side on grid E; it extends in -x
y=w5.n-       the north face of w5 named explicitly
y=f2+0.3      0.3 m past the edge of window f2 (a socket moves when the window moves)
y=f2.c        on the centre of f2
x=W..E        from grid W to grid E
x=3.2+        a raw coordinate, the escape hatch
```

The sign says which way the element extends from the anchor. The whole list is `uea help positions`, and the datums are [0012](../decisions/0012-datums-and-positions.md).

## Files

A project is a folder with one file per discipline: `project.uea`, `arch.uea`, `site.uea`, `struct.uea`, `light.uea`, `elec.uea`, `heat.uea`, `plumb.uea`, `vent.uea`, `lv.uea`, `bid.uea`, `issues.uea`, and the history `log.jsonl`. A file exists once its discipline has an element.

References only point upstream: electrical names architecture, architecture never names electrical ([`ARCHITECTURE.md` §2](../../ARCHITECTURE.md#reference-direction)). UEA writes every file in canonical order (kinds as the pack defines them, then ids in natural order: `w2` before `w10`), so a changed element is a one-line diff.

## Operations

Agents change the model with operations, the same lines with a prefix, sent as one batch:

```
+ wall @a EG IW-115 x=w6+1.385 y=w5..w3     add; @a names the new wall within the batch
+ door _ @a 0.76x2.01 y=w5+0.26 into=r5     add; _ when nothing refers to it
~ w9 type=IW-240 lb                         set fields and flags
~ w9 h=                                     reset a field to its default
~ d1 1.51x2.26                              a bare value sets the positional field it fits
- w9 d3                                     remove
> grid E x=10.74                            replace the whole element
~ q1 done                                   close a request
```

```bash
uea apply --by arch-agent -m "Küche größer" <<'EOF'
~ w5 y=w1+4.81
EOF
```

- Quote the heredoc (`<<'EOF'`), or the shell expands what it should not.
- A batch is atomic: it is rejected, and nothing changes, if it adds an error in a discipline it writes. Errors it causes downstream are reported (`affects ...`) and stay open there.
- The output names the ids UEA assigned: `ok batch 2 (arch): +5` and ` @s=w1 @n=w2 ...`.
- `--dry-run` checks without writing; `uea revert <n>` undoes a batch as a new one.
- Placeholders may be used before the line that defines them.

The whole syntax is `uea help ops`.

## A whole house

[Haus Müller](../prototype/haus-mueller/README.md) is the reference: every discipline of an Einfamilienhaus in this format, written by hand and loaded by UEA.
