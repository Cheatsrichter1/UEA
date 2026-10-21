# 0048: The Leistungsverzeichnis from the model

Status: Accepted (built)
Date: 2026-10-16

## Context

Version 2 goes from the model to the tender (`FUTURE.md`). A Leistungsverzeichnis (LV) is a list of positions under titles: each position has its Ordnungszahl (OZ), a short and a long text, a unit and a quantity, and in the priced LV a unit price. It goes out to bidders as GAEB DA XML (phase 83, Angebotsaufforderung) and in print, and the bids come back as GAEB 84.

The model already holds the quantities: net wall areas and core volumes per type, slab and floor areas, sloped roof areas, openings, cable, pipe and duct lengths (`uea export xlsx`, sheet Mengen and the services' quantity sheets). What it lacks is the LV's structure: which positions there are, under which titles, with which texts, and which elements each one counts. That is a decision (agents decide), the quantities are calculation (code calculates).

Standard texts (STLB-Bau) are licensed, and offices keep their own position texts.

## Decision

**The LV lives in the model,** in a new discipline file `lv.uea`, downstream of all others (it may reference every discipline, none references it). Batches, history, revert, views and requests work on it unchanged.

```
title T01 "Mauerarbeiten"
pos p1 T01 area sel="wall type=AW-365" "Außenmauerwerk Ziegel 36,5 cm" kg=331
pos p2 T01 n sel="win" "Fenster liefern und einbauen" text=FE-01 kg=334
pos p3 T02 len sel="circ cable=NYM-J3x1.5" "Mantelleitung NYM-J 3x1,5" kg=444
pos p4 T02 fix=1 unit=psch "Baustelleneinrichtung" kg=391
```

- **`title`**, named by the agent: an LV title (a trade or a part of one), with its text.
- **`pos`**: a position under a title. Its measure, a bare word, is `n` (count, unit St), `len` (m), `area` (m²), `vol` (m³), or one of the networks `heat`, `water`, `drain`, `duct` (m); or it has `fix=<number>` with `unit=` (`psch`, `h`, `St`). `sel=` names the elements it counts in the grammar of `uea find` (a kind and its filters). The label is the short text.
- **What a measure means per kind** is fixed by code and documented in the help (`uea help lv`): a wall's `len` is its length, `area` its net elevation area and `vol` its core volume; a slab's `area` and `vol` its net area and core volume; a room's `area` its finished floor area and `vol` its volume; a roof's `area` its sloped area; a door's or window's `area` its structural opening area; a circuit's `len` its cable length, a data outlet's its cable times its ports, an underfloor loop's its pipe. The networks are measured from their root, since one element can be the root of two (a tank heats water for the heating and for the taps): `heat` on a generator, tank or manifold counts the heating pipes from it, flow and return; `water` on the meter the cold, on a tank the hot drinking-water pipes; `drain` on the sewer connection the waste-water pipes; `duct` on a ventilation unit or fan its ducts. A measure a kind does not have is an error with the list of those it has. Pipe and duct sizes come from the office's tables through the calculators, so the LV counts lengths per network, not per size, for now.
- **Quantities are derived,** never stored: `uea get p1` shows the quantity and the elements it counts.
- **Long texts and unit prices are the office's.** `text=<key>` takes the long text from the office's table `lv-texts` (key, long text), installed like a norm table (`uea data add`); without it the position has only its short text. `ep=<price>` is an optional unit price in euros; with prices the LV is priced and the totals per title and per cost group come out.
- **`kg=`** is the DIN 276 cost group of the position, so the priced LV sums up per cost group: the start of the Kostenberechnung.
- **OZ** are derived from the order of titles and positions by id: `01.0010`, `01.0020`. Once an LV went out, `oz=` pins a position's or title's number so later positions do not renumber it.
- **Checks:** a selector or measure that cannot be used (E-LV-001), a position that counts nothing (W-LV-002), an element counted by two positions with the same measure (W-LV-003, double counting), two titles or positions with the same number (E-LV-004), selected elements the measure gives nothing for yet, such as a wall with no height (W-LV-005).
- **Exports:** `uea export gaeb` writes GAEB DA XML 3.3, phase 83, with titles, positions, short and long texts, units and quantities (prices left out, for bidders); `uea export xlsx` gets a sheet LV, priced if prices are given; the calculation report for humans is German.
- **Not yet:** the GAEB phases 81 and 86, pipe lengths per size, STLB-Bau texts, and a Kostenschätzung per DIN 276 by reference quantities (BGF, BRI from `din277`) before there is an LV.
- **The bids** (GAEB 84) are read and compared since `0051-bids.md`.
- **Built as decided,** with these details: the measure is a bare word at the end of the canonical line; a batch lists the positions whose quantity it changed (`follows`); `uea get` on a title gives its positions and its priced sum.

## Alternatives

- **The LV as an export only,** generated from types: every wall type a position, every window type a position. Cheap, but the LV's structure is the planner's decision: positions combine and split types, include work no element carries (site setup, scaffolding), and the texts are the office's.
- **The LV as a separate file outside the model** (a YAML or CSV): it would need its own history and its own references into the model, which go stale when an element is removed.
- **Quantities stored on the position:** the LV would drift from the model. Derived quantities follow every change, and a revert of the model reverts the quantities.
- **A rule language for quantities** (formulas over fields): more powerful, but agents would compute quantities in it. The fixed measures per kind keep the calculation in tested code; a quantity no measure covers is `fix=` with the agent's reason in the label, or a `custom` calculator.

## Consequences

- A new pack `lv` with the kinds `title` and `pos`, a file `lv.uea`, help (`uea help lv`), checks with codes, `docs/reference.md`, a bench task.
- `uea export gaeb`, and the sheet LV in `uea export xlsx`.
- The office's table `lv-texts` beside the norm tables; it holds the office's own texts, not a standard's.
- The cost estimate per DIN 276 can sum the priced LV by `kg=`; a Kostenschätzung before an LV exists needs reference prices per BGF or BRI, which is a later decision.
