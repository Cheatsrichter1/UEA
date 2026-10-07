# 0002: Open source under Apache-2.0

Status: Accepted
Date: 2026-10-07

## Context

UEA does not depend on licence sales. In the age of AI, closed software is copied or rebuilt anyway. Offices are more likely to trust software they can inspect, and an open project can attract contributed exports, calculators and domain packs.

## Decision

UEA is fully open source under Apache-2.0.

## Alternatives

- **MIT:** equally permissive, but without Apache's explicit patent grant.
- **AGPL / GPL:** forces derivatives to stay open, but scares off offices and companies that want to build on it, and UEA does not depend on preventing that.
- **Open core (paid packs):** possible later for single packs, but not planned.

## Consequences

- Dependencies must be compatible with Apache-2.0. Permissive licences and LGPL libraries are fine.
- GPL programs (Blender, LibreDWG) are only called as separate processes, never imported.
- Norm texts and tables stay out of the repo regardless of licence, because they are licensed by their publishers.
