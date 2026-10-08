# 0021: Half-hip, mansard and flat roofs

Status: Accepted
Date: 2026-10-08

## Context

`0016-roofs.md` had three shapes: gable, shed and hip. A German brief also names the Krüppelwalmdach (a gable roof with hipped ends), the Mansarddach, the Flachdach and the Zeltdach. Every one of them is the lowest of a few planes over a rectangle, which is what a roof already is (`0016-roofs.md`, `0020-roof-parts.md`). Nothing in the walls, rooms, WoFlV zones, plan or IFC needs to change for them.

## Decision

- **Zeltdach** is a `hip` roof on a square. It needs nothing new; the help says so.
- **Krüppelwalmdach** is a gable roof with `halfhip=<run>`: the horizontal run of the hipped ends. The ridge is shortened by `run` at both ends, and the hip plane has the pitch of the roof, so it meets the end wall tan(pitch) x (half width − run) above the eaves line. A run of half the width is a hip roof. The gable wall gets a flat top at that height. The run must be less than the half width and less than half the ridge length (E-ARCH-043).
- **Mansarddach** is `mansard` with `pitch=` below the break, `upper=` above it, and `rise=` the height of the break above the eaves line. Without `ridge=` all four sides are mansard sides; with `ridge=x|y` the two ends are gables (a gambrel roof). The upper pitch must be less than the lower one, so the roof is the lowest of the two planes per side. If the break lies at or above the ridge, E-ARCH-043 names the largest `rise=`.
- **Flachdach** is `flat` with `knee=` as the height of its underside above the SSL. It has no pitch. A roof with a fall is a `shed` with a small pitch. All four edges take `eave=`.
- **Layer thickness is square to the roof.** The vertical thickness of the roof skin and the lining is the thickness times √(1 + a² + b²) of the plane, per plane. Before, one number per roof was used, which is wrong as soon as a roof has two pitches. For the old shapes the numbers are the same.
- IFC: `HIPPED_GABLE_ROOF`, `MANSARD_ROOF`, `GAMBREL_ROOF` and `FLAT_ROOF`.

## Alternatives

- **A steeper pitch for the hipped ends** (`halfhip=` with its own pitch): common for the Krüppelwalm. It needs a second pitch field and the same plane arithmetic; it can follow if a project needs it.
- **A break given as a horizontal run** instead of a height: the same, but a brief says "Aufbau 2.40 m hoch". The height is what is drawn.
- **A butterfly roof** (Schmetterlingsdach) and **sawtooth** roofs as shapes: not needed. A roof is the lowest of its planes, but two roofs on one storey are combined by the highest (`0020-roof-parts.md`), so two shed roofs on the two halves, each rising to the outside, are a butterfly roof (tested), and a sawtooth roof is several sheds.
- **Barrel roofs** (curved) and **dormers**: open, see `ROADMAP.md`.

## Consequences

- The five shapes (gable, shed, hip, mansard, flat) and `halfhip=` cover the usual roofs of a house. A new shape that is the lowest of planes over a rectangle costs a branch in `make_roof` and a line in the IFC mapping.
- `pitch` is no longer required in the file format: it is required for every shape but `flat`.
