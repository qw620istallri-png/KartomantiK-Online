# Zone, Revelation, and threshold follow-up

- Strict family: **15/15 passed** (`tests/test_zone_revelation_threshold_family.py`).
- Accumulated adjacent regression: **712/712 passed** across the general game state, card catalog, zone-transition audit, and every strict family added in the current coverage series.
- Clause proof: **5 cards / 5 printed paragraphs** (`clauses.json`).
- Production fix: Bonzai no longer reveals the Empathic Vessel owner's private Hand while Unreachable Pillar disables that Vessel's effects.

The strict branches cover Dulfer's Revelation choice, Tuxnu's non-recursive
Persistent-Will copies, Quper's successful-Sacrifice threshold, Bonzai's
immutable-owner privacy window, and Spiked Pit's opponent Interzone entry
penalties for cards and Tokens.

No commit or push was made.
