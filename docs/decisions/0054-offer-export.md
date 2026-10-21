# 0054: The fee offer as a document to sign

Status: Accepted (built)
Date: 2026-10-21

## Context

An office's business side is how its agent behaves, so it belongs in the instructions the office gives its agent (`FUTURE.md`, Office workflows; `docs/templates/AGENTS.md`). One part is not behaviour: the offer itself (Honorarangebot). It is a letter with numbers, and those numbers must come from code. `uea calc hoai` computes the fee for one service at a time (`0049-cost-estimate-and-hoai-fee.md`), but a German report per service is no offer. The agent would have to copy every amount into a letter, and that is where a typo gets past the person who signs.

Up to `hoai` 0.2.0 every run also wrote `out/hoai.md`, so the fee for the building, the technical equipment and the structure replaced each other.

## Decision

- **One result per service:** `hoai` 0.2.1 writes `out/hoai-building.md`, `out/hoai-services.md`, `out/hoai-structure.md`, and per group of systems `out/hoai-services-410-420.md`. A calculator may name a `suffix` from its settings that tells its results apart; `hoai` is the first to use it. `uea export pdf hoai` lists the results instead of failing. The fee is unchanged. The result also records where its chargeable costs come from as numbers (`basis`), and its German report gives that basis in German, where it was English before.
- **`uea export offer [results] [-o file]`** builds the offer from the `hoai` results in `out/`, all of them or those named (`hoai-building,hoai-structure`). It writes `out/offer.md`, which the agent can read before it hands the offer over, and the PDF to sign. In German:
  - the letterhead, the return address, the client, place and date;
  - per service: its fee zone and rate, the chargeable costs and where they come from, a table of the service phases with their names, shares and fees, the conversion surcharge and the incidental costs, the net fee and its clause;
  - a summary with the net sum, VAT and the gross sum;
  - the office's terms, a note that the fees come from the model at a given batch and that the HOAI's table values are guidance since 2021, the closing and a signature line.

  Every amount is the result's. The offer computes only the fee of each phase (the full fee times the share, as the report does) and the sums. "ENTWURF – nicht unterzeichnet" is on every page, and amounts carry thousands separators, since the client reads them.
- **The office's texts are an office table, `offer`** (`uea data add offer <file.csv>`), with the keys `office` (letterhead, required), `sender`, `place`, `intro`, `terms`, `closing` and `signer`, installed once per machine like `lv-texts`. Without it the offer still builds and says what it lacks; `intro` and `closing` have a German default.
- **The client is a field of the project:** `~ <project> client="Familie Müller|Hauptstr. 1|64283 Darmstadt"`, with `|` between lines. The project folder is the office's own, so the client's address stays where the office's data already is.
- **Refused when the model has changed** since a result was computed, as a calculation report is (`0036`), with the command that computes each result again. Setting the client changes the model too, so the agent sets it before computing the fees.
- **UEA sends nothing.** The office signs the PDF and sends it, or its agent does, after the approval its `AGENTS.md` asks for.

## Alternatives

- **The offer as a calculator** (`uea calc offer`). It calculates nothing of its own; it sets results into a letter, which is what an export does.
- **Office texts in the project.** Letterhead and terms are the same for every project of an office. As an office table they are written once and are not copied into each project's git history.
- **The client in the office table, or on the command line.** The client belongs to the project, not to the office, and a command-line argument would be gone after the run.
- **A letter template the office writes in Word.** Offices could keep their own layout, but UEA would have to fill a binary document. The office table covers the texts; the layout is UEA's A4 report style.
- **Keep one `hoai` result and run the offer from settings** (`uea export offer service=building,...`). The offer would recompute the fees, and the results on file would no longer be what the agent checked.

## Consequences

- New: `src/uea/export/offer.py`, the format `offer` of `uea export`, the office table `offer`, the field `client` on `project`.
- `hoai` 0.2.1 (`docs/validation/hoai.md`): result names per service, the basis as numbers and in German. Scripts that read `out/hoai.json` must read `out/hoai-<service>.json`.
- The offer has no number, no validity date of its own and no acceptance block for the client; an office puts what it needs into its `terms`.
- Special services (besondere Leistungen), hourly fees and lump sums are not in the offer, since `hoai` does not compute them (`docs/validation/hoai.md`, Not implemented).
- `uea help calc` now lists `din277`, `costs` and `hoai`, which it had left out.
