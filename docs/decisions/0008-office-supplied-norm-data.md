# 0008: Norm tables are supplied by the office

Status: Accepted (storage and format in 0028)
Date: 2026-10-07

## Context

Most `norm` calculators need tables from their standard, not only formulas: cable sizing needs the current-carrying capacities of DIN VDE 0298-4, Heizlast needs the Norm-Außentemperaturen of DIN/TS 12831-1. These tables, and the standards' worked examples, are licensed by their publishers and cannot be part of an open-source repository. Every office that plans to these standards already owns licensed copies.

## Decision

- A `norm` calculator declares the tables it needs: standard, edition, table and schema.
- The office supplies them from its own licensed copy, once per machine (`uea data add`). They are stored outside project folders and never committed.
- Without the data, the calculator stops and names the missing table.
- The public tests use our own hand-computed data. The standard's worked examples run as a local test suite against the supplied data.
- Every result records which edition of each table it used.

## Alternatives

- **Ship the tables in the repo:** not allowed by the publishers' licences.
- **Derive the values from first principles** (for example a thermal model for cable capacity): the results differ from the tables the standard prescribes, so they would not be norm results.
- **Licence the tables for redistribution:** expensive and uncertain.

## Consequences

- Entering the tables is a setup step for each office.
- The table schemas must be documented well enough for an office, or its agent, to enter the data.
- Public CI cannot run the standards' worked examples; a private CI with licensed data can.
