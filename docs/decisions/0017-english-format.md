# 0017: The format is English; exports for humans stay German

Status: Accepted
Date: 2026-10-07

## Context

UEA's users are agents, and its first human users are German offices. Until now the format mixed English kinds and fields (`wall`, `door`, `room`, `head=`) with German abbreviations: `kn=` for Kniestock, `din=` for DIN links/rechts, `plz=` for Postleitzahl, `typ=`. The CLI output mixed in German words: Rohbau, Fertig, Traufe, First, `rd=` for OK Rohdecke. The docs did the same with plain building words.

The first agent test (`bench/agent/results.md`) showed agents guessing names: one wrote `din=links`, two tried `terrain=` for the terrain height. Nobody can predict which words of a mixed vocabulary are German. German compounds also cost more tokens: `Sturzhöhe` is 5 tokens in o200k_base and "head height" 2, `Kniestock` 3 and "knee" 1.

## Decision

- Everything UEA defines is English: kinds, fields, values, flags, CLI output, help, issue messages, code and docs.
- Renamed fields: `kn` → `knee`, `din` → `hand`, `plz` → `postcode`, `typ` → `type` on doors and windows. `fb` stays: it reads as "floor build-up" in English too.
- Renamed in output and help:

  | Was | Now |
  |---|---|
  | `rd=` (OK Rohdecke) | `ssl=` (structural slab level) |
  | OKFF | FFL (finished floor level) |
  | Rohbau, Fertig | `shell`, `fin` |
  | Traufe, First | eaves, ridge |
  | Sturzhöhe, Fußbodenaufbau | head height, floor build-up |

- The help names the German term once where a German brief would use it, for example `knee: ... (Kniestock)`. An agent can then map a brief to a field without guessing.
- What people write stays in their language: labels, the names of levels, grids and types, request texts and batch messages.
- Exports for humans stay German: drawings follow German drafting conventions, and calculation reports are read by German offices and Prüfingenieure.
- Docs keep German only for legal, norm and role terms without an exact English equivalent (Wohnfläche, WoFlV, Haftung, Prüfingenieur, Fachplaner, Landesbauordnung, Bestand, Heizlast), and in names (Haus Müller, the Einfamilienhaus demo).

## Alternatives

- **German format, since German offices use it:** agents work best in English, and the IFC vocabulary the format follows (`ARCHITECTURE.md` §3) is English.
- **Mixed, as before:** no work, but agents cannot predict which words are German.
- **Output in English or German by setting:** two vocabularies to test and to learn. The reader of the format is the agent, not the human.

## Consequences

- Project files with `kn=`, `din=`, `plz=` or `typ=` no longer parse; the error lists the new fields. There are no users yet, so there is no migration.
- The token task set was not rerun with this change; `bench/results.md` holds the numbers from before it.
- `docs/reference.md` lists every command, kind, field and issue code, generated from the code, so the English names are checked in one place.
