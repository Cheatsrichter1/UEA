# Future directions

Ideas beyond the first scope in `VISION.md`. Nothing here is planned or scheduled. These are written down so the core can be designed not to block them.

## More engineering domains

The core is domain-neutral, so new domain packs can be added on top of it:

- **Steel and timber construction:** members, connections, cutting lists.
- **Mechanical parts:** this needs real solid geometry (B-rep), which the building model avoids. It would be a separate pack built on an existing kernel, never our own.
- **Civil engineering (Tiefbau, Verkehrswegebau):** roads, earthworks, drainage. Alignment-based geometry (axis, gradient line, cross sections) instead of storeys.

## From model to tender

- **Cost estimation:** Kostenschätzung and Kostenberechnung structured per DIN 276, with quantities taken from the model.
- **Leistungsverzeichnis and Ausschreibung:** generate the LV from the model and export it as GAEB, for public Vergabe (VOB/A, VgV) and private tenders. Compare the bids that come back.
- **Fees:** an Honorar calculation per HOAI for the offer.

## Autonomous office workflows

An agent works the business side, with a human approving every outgoing step:

1. It watches public tender platforms (for example TED for the EU and the German Vergabeplattformen) for planning jobs that fit the office.
2. It summarizes a matching job for the senior engineer: scope, deadlines, requirements, rough effort.
3. When the senior engineer approves, it prepares the offer, the fee calculation and a first draft of the plan.
4. The senior engineer checks it and signs. Nothing goes out without that signature.

## Agent dashboard

A small, friendly dashboard for the senior engineer, a cherry on top. It is not a viewer and does not show the model one-to-one. It shows the state of the work:

- What each agent is doing right now ("planning the electrics on the EG", "running Heizlast"), with a simple animation.
- How far along each project is.
- Open questions from the agents that are waiting for a human answer.
- Drafts that are ready for review, and approvals that are pending.

Much of this UEA records anyway: the history, open issues, requests and waivers. What each agent is doing right now, and the questions waiting for a human, would need status and question events that UEA deliberately does not have today (`docs/decisions/0001-no-own-agent.md`). Building the dashboard means revisiting that decision. Either way, it only reads, so it never slows the agents down.

## Plot evaluation

Given an open plot (for example one a city offers), an agent evaluates what could be built there:

- What the Bebauungsplan, BauNVO (GRZ, GFZ, storeys) or §34 BauGB and the Landesbauordnung allow.
- Building options: social housing, regular apartments, single-family houses, mixed use.
- A first massing model, rough costs and a profitability estimate for each option.

The result is a decision basis for a human, not a decision.
