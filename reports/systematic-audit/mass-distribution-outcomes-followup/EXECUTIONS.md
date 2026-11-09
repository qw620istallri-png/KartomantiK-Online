# Mass and distribution outcomes follow-up

- Strict family: **14/14 passed** (`tests/test_mass_distribution_outcomes_family.py`).
- Accumulated adjacent regression: **683/683 passed** across the general game state, card catalog, zone-transition audit, and every strict family added in the current coverage series.
- Clause proof: **5 cards / 5 printed paragraphs** (`clauses.json`).
- Production fix: Recall the Consumed and Extinguish Nostalgia now send each physical Limbo card to its immutable owner's Exile, including cards held in another player's Limbo. Recall still creates the Hollow copy under the Limbo container player's control.

The strict branches cover repeated base-power doubling, confrontation-winner
destruction, exact weakness distribution, Limbo-wide copy creation, Immediate
resolution, replacement effects, target atomicity, persistent modifiers, and
foreign-owned card routing.
