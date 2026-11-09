# Protection, timing, and distribution follow-up

- Strict family: **16/16 passed** (`tests/test_protection_timing_distribution_family.py`).
- Core adjacent regression: **545/545 passed** across `test_game_state`, zone-transition audit, card catalog, and the strict family.
- Additional adjacent regression: **31/31 passed** across choice atomicity, First restrictions, revealed-hand behavior, player-loss triggers, and confrontation-win behavior.
- Clause proof: **5 cards / 9 printed paragraphs** (`clauses.json`).
- Production fixes: Caress the Dawn now routes each selected Limbo card to its physical owner's Deck; Palm Coercer now opens overflow immediately after an actual draw and uses normal Deck-entry replacement handling.

The private-hand, semantic-batch, draw-integration, and transport-integration
modules could not be collected in this Python installation because importing
the network server fails on the absent `websockets` package. This is an
environment/dependency block before test execution, not a KKO assertion
failure. The strict family includes direct privacy, ordered multi-player draw,
replacement, Revelation, and zone-lock regression coverage for the changed
paths.

No commit or push was made.
