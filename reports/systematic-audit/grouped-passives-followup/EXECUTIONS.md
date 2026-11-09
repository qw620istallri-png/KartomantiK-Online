# Grouped passives follow-up

- Strict family: **18/18 passed** (`tests/test_grouped_passives_family.py`).
- Adjacent regression: **500/500 passed** (`tests/test_game_state.py` plus the strict family).
- Clause proof: **5 cards / 7 printed paragraphs** (`clauses.json`).
- Diff whitespace gate: passed (`git diff --check`; the only output was the repository's existing LF/CRLF warning for `docs/SYSTEMATIC_CARD_AUDIT.md`).

The full discovery run is not counted for this follow-up. It stopped before
executing KKO test code while Python 3.12 was creating the Windows asyncio
event loop for
`test_atavic_end_integration.AtavicEndIntegration.test_introspection_reconnect_preserves_exact_top_bottom_choice_and_rejects_bad_order`.
A `faulthandler` dump located the wait in
`socket._fallback_socketpair -> asyncio.windows_events.ProactorEventLoop.__init__`.
The same wait reproduced with `WindowsSelectorEventLoopPolicy`, so no new full
unit evidence or formal coverage-status update was published from this run.
