# Getting started

[Wiki home](README.md)

## Install

Needs Python 3.12+ and [uv](https://docs.astral.sh/uv/). The install command for the current release is in the README's [Try it](../../README.md#try-it) section. From a clone:

```bash
uv sync --all-extras
uv run uea help
```

The extras are `ifc` (IFC import and export, IfcOpenShell) and `struct` (the structural solver, PyNite).

## A first project

```bash
uea init haus && cd haus
uea apply --by arch-agent -m "Geschosse und Achsen" <<'EOF'
+ project haus "EFH"
+ level EG z=0 fb=0.15 head=2.26
+ grid W x=0
+ grid E x=10.49
+ grid S y=0
+ grid N y=8.49
+ type AW-365 wall layers=plaster:0.015,*brick:0.365,render:0.02
EOF
uea apply --by arch-agent -m "Außenwände" <<'EOF'
+ wall @s EG AW-365 y=S+ x=W..E lb
+ wall @n EG AW-365 y=N- x=W..E lb
+ wall @w EG AW-365 x=W+ y=@s..@n lb
+ wall @o EG AW-365 x=E- y=@s..@n lb
+ room _ EG living at=@w+1,@s+1
EOF
uea get r1        # the room with its derived sizes
uea check         # open issues: here, the walls have no height yet (no storey above, no roof)
uea render EG     # a plan image to look at
```

Quote the heredoc (`<<'EOF'`) so the shell leaves the `@` placeholders alone. How lines, positions and operations are written is on [The line format](format.md); what each command does is on [Commands by task](commands.md).

## Reading on, as an agent

The help is layered so an agent loads only what it needs:

```
uea help                 overview and commands
uea help start           how a project begins
uea help ops             operations and batches
uea help positions       how elements are placed
uea help arch            a discipline: arch, site, elec, heat, plumb, vent, struct, lv, bid
uea help wall            one element kind
uea help codes           every issue code
uea help calc            calculators and norm tables
uea help export          exports for humans
uea help import          importing an architect's IFC or a bid
```

## Reading on, as a person

1. [`VISION.md`](../../VISION.md) for the idea.
2. [`ARCHITECTURE.md`](../../ARCHITECTURE.md) §3 to §6 for the model, the format and the batches.
3. [Haus Müller](../prototype/haus-mueller/README.md) for a whole house with all disciplines.
4. [The line format](format.md) and [Commands by task](commands.md) for the details.
5. [Concepts](concepts.md) when a word is unclear.
