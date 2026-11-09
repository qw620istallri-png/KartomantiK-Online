# Reactive passives follow-up

- Strict family: **14/14 passed** (`tests/test_reactive_passives_family.py`).
- Accumulated adjacent regression: **697/697 passed** across the general game state, card catalog, zone-transition audit, and every strict family added in the current coverage series.
- Clause proof: **5 cards / 5 printed paragraphs** (`clauses.json`).
- Production fix: Obtrusive Mass now redirects only opposing effects targeting allied Manifestations. Effects targeting allied Wills keep their original target.

The strict branches cover Wandering Outcast's optional atomic swap, Soup's
Persistent-Will response timing, Obtrusive Mass target redirection, Honor and
Respect's exact-one winner condition, and Life Sustainer's exact-zero state
replacement for ordinary Manifestations and Tokens.

No commit or push was made.
