# 0006: v1 scope and order of the domain packs

Status: Accepted
Date: 2026-10-07

## Context

v1 covers architecture, electrical, plumbing, heating, ventilation and structural: everything a normal Einfamilienhaus needs. They cannot all be built at once.

## Decision

1. Core + architecture: everything else references it.
2. Electrical: few open-source tools cover it, and it shows the design side (placing and connecting devices), not only calculation.
3. IFC import of architecture, so electrical and building services offices can try UEA on real projects (`0011-ifc-import.md`).
4. Plumbing + heating, including Heizlast per DIN EN 12831-1.
5. Ventilation.
6. Structural, only with a licensed engineer partner reviewing the validation.

After v1, lighting grows into a full pack: design-led (atmosphere, luminaire choice), suited to a lighting design agent with a feel for it, plus photometric calculation. In v1 the light pack only holds the luminaires, which the Elektro work places and wires (`ARCHITECTURE.md` §2). An Einfamilienhaus can be finished that way.

## Alternatives

- **Heizlast first:** the earlier plan. Very testable, but it shows only calculation, while electrical also shows the design side.
- **Structural early:** highest value per project, but also the highest liability; needs outside expertise first.
- **Lighting in v1:** not needed to finish an Einfamilienhaus, and lighting design deserves its own pack rather than a minimal one.
- **IFC import after v1:** electrical and building services offices could then not try UEA on real projects until the demo is finished.

## Consequences

- The benchmark runs on architecture and electrical tasks.
- Structural is part of v1, so the engineer partner is needed before the demo can be complete.
- Conversations with offices may reorder packs 2–5; structural stays last.
