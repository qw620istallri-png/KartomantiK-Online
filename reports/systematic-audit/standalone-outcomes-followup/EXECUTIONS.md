# Standalone outcomes follow-up

- Strict family: **18/18 passed** (`tests/test_standalone_outcomes_family.py`).
- Core adjacent regression: **500/500 passed** (`tests/test_game_state.py` plus the strict family).
- Additional adjacent modules: **146/146 passed** across semantic batch 151-300, confirmation, release 139.2, reported-card bugs, card catalog, and the two Obelisk-relevant Stack-priority scenarios.
- Clause proof: **5 cards / 14 printed paragraphs** (`clauses.json`).
- Python compilation and diff whitespace gates: passed. The only diff output was the repository's existing LF/CRLF warning for `docs/SYSTEMATIC_CARD_AUDIT.md`.

The complete `test_stack_priority_audit` module is not counted because its
first test calls `asyncio.run`, which reaches the already documented Windows
`socket._fallback_socketpair` environment block. Its two scenarios relevant
to Obelisk were executed independently and both passed.

No production code changed in this follow-up: the existing implementations
met every selected strict oracle.
