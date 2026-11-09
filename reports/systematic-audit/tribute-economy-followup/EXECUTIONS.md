# Tribute economy follow-up

- Strict family: **13/13 passed** (`tests/test_tribute_economy_family.py`).
- Core adjacent regression: **568/568 passed** across the general game state, special payments, special affordability, combined payments, replacement ordering, card catalog, and the strict family.
- Focused browser parity: **4/4 passed** (`tests/test_tribute_economy_ui.cjs`).
- Clause proof: **5 cards / 5 printed paragraphs** (`clauses.json`).
- Production fix: Cognitive Fog's added Hollow Tribute and Arcane Teapot's reduction now combine before the zero floor on both server and client. Distinct later surcharges such as Persuaded remain outside that reduction.

The broad `test_rules_parity.cjs` runner remains blocked before browser startup
because its Python fixture generator imports the unavailable `websockets`
package. The focused browser gate loads the shipped KKO client directly and
executes the four Teapot/Fog payment combinations without that network-server
dependency.

No commit or push was made.
