# Areas, tender, costs and fees

From the model to the tender, the bids, the costs and the office's fee. Index in [README.md](README.md).

## 0047 DIN 277 areas

- `uea calc din277 [level]`, a `norm` calculator in the architecture pack: BGF, NRF, KGF and BRI per storey and in total, with a German report.
- The office's table `din277-uses` maps each UEA room use to a usage group (1–7 NUF, 8 TF, 9 VF). Without it only the totals come out; a use without a row stops the split.
- **BGF outline:** the storey's cores and slabs, filled, grown by the thinnest exterior finish, mitred.
- **BRI** storey by storey on the BGF outline, FFL to FFL; the lowest from the underside of its slab, the top up to the roof covering, integrated over the planes.
- **KGF = BGF − NRF**; floor without a room lands there and is reported. Stairs are VF on their starting storey.

Why: DIN 277 and its table of uses are licensed, so the mapping is the office's; summing wall footprints double-counts joins; room volumes leave out walls, slabs and roof.

## 0048 Leistungsverzeichnis

The LV lives in the model, in `lv.uea`, downstream of every discipline.

```
title T01 "Mauerarbeiten"
pos p1 T01 area sel="wall type=AW-365" "Außenmauerwerk Ziegel 36,5 cm" kg=331
pos p2 T01 n sel="win" "Fenster liefern und einbauen" text=FE-01 kg=334
pos p3 T02 len sel="circ cable=NYM-J3x1.5" "Mantelleitung NYM-J 3x1,5" kg=444
pos p4 T02 fix=1 unit=psch "Baustelleneinrichtung" kg=391
```

- `title`: named by the agent. `pos`: a measure (`n`, `len`, `area`, `vol`, or a network `heat`, `water`, `drain`, `duct` measured from its root) or `fix=` with `unit=`; `sel=` in the grammar of `uea find`; the label is the short text.
- What each measure means per kind is fixed in code and in `uea help lv` (a wall's `area` is its net elevation area, a roof's its sloped area, a circuit's `len` its cable). Quantities are derived, never stored; `uea get p1` shows them and what they count.
- `text=<key>` takes the long text from the office's `lv-texts`; `ep=` is an optional unit price; `kg=` the DIN 276 cost group. OZ derive from the order (`01.0010`); `oz=` pins one after the LV went out.
- Checks `E-LV-001`, `W-LV-002`, `W-LV-003` (double counting), `E-LV-004`, `W-LV-005`.
- `uea export gaeb` writes GAEB DA XML 3.3 phase 83 without prices; `uea export xlsx` adds a sheet LV.

Why: the LV's structure is the planner's decision, not one position per type; a file outside the model would go stale; stored quantities would drift; a formula language would make agents compute.

## 0049 Costs and HOAI fee

- **`uea calc costs`** (DIN 276:2018-12): the office's `cost-ref` gives per cost group the DIN 277 quantity and a net price; rows sum to the first level and the total, net and with VAT (`ust=`, 19 %). `stand=` records the price level.
- **Kostenberechnung** (`stage=calculation`): the priced LV per cost group, with `cost-ref` rows where no priced position falls; what is left out is listed.
- **`uea calc hoai`** (HOAI 2021, an amtliches Werk): `service=building|services|structure`, `zone=`, `rate=`, `lph=`, `kosten=`, `umbau=`, `nk=`, `ust=`. Chargeable costs from the estimate's KG 300 and 400 (§ 33 Abs. 2), KG 400 (§ 54), or `kosten=` (§ 50); per § 6 Abs. 1 from the cost calculation where the LV is priced, else the estimate (`costs=auto|estimate|calculation`); `groups=410,420` per group of systems. Linear interpolation (§ 13); outside the table the calculator stops (§ 7 Abs. 2). Phase shares in code with their clauses.
- The fee tables come from the office (`hoai-fees`): free to ship, but not typed from memory, since one wrong value is worse than none.

Why: offices need the estimate long before an LV; the model already knows the chargeable costs.

## 0051 Bids

```
bid bd1 "Muster Bau GmbH" date=2026-11-02 total=23820.96 disc=2 file=muster.x84
price pr1 bd1 p1 ep=110 qty=90.51
price pr6 bd2 p1 ep=100 qty=90.51 gp=9100
```

- Bids live in `bid.uea`, downstream of the LV. `uea import gaeb <file.x84>` matches items by the ID UEA wrote (`UEA_p3`), else the OZ; keeps the bidder's `qty=` and its GP only where it is not `qty × ep`. Unknown items are listed; the same file twice is refused.
- **Derived per bid:** titles covered, unpriced positions, checked sums per title and total (EP counts, VOB/A § 16c Abs. 2 Nr. 1), the sum after discount.
- Checks `E-BID-001`, `W-BID-002`, `W-BID-003` (LV quantities changed), `W-BID-004`, `W-BID-005`.
- **`uea calc bids [title] dev=30`:** checked sums, ranks among complete bids, sums beside the office's prices, unit prices more than `dev` % from the median. The report is the Preisspiegel. It never awards.
- **`uea calc costs stage=offer bid=bd2`:** the Kostenanschlag from awarded bids' EPs less discount, the LV's prices and the estimate for the rest.

Why: files beside the model would escape checks and history; all prices on one line would hide references in a string; awarding is the client's legal decision, not the agent's.

## 0054 Offer export

- `hoai` writes one result per service (`out/hoai-building.md`, `hoai-services.md`, `hoai-structure.md`, per group `hoai-services-410-420.md`) through a calculator `suffix`, and records its cost basis as numbers.
- **`uea export offer [results] [-o file]`** sets the `hoai` results into a German Honorarangebot: letterhead, client, per service zone, rate, chargeable costs, phases with shares and fees, surcharges, net fee; net, VAT and gross; terms, a note on the HOAI's guidance values since 2021, a signature line. It writes `out/offer.md` and a PDF, "ENTWURF – nicht unterzeichnet". It computes only phase fees and sums.
- Office texts come from the office table `offer` (`office` required; `sender`, `place`, `intro`, `terms`, `closing`, `signer`). The client is `project client="Familie Müller|Hauptstr. 1|64283 Darmstadt"`.
- Refused when the model changed since a result. UEA sends nothing.

Why: an agent copying amounts into a letter is where typos get past the signer; office texts belong to the office, the client to the project; recomputing in the export would bypass the results the agent checked.
