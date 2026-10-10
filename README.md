# Kartomantik Online

A minimal online game table for Kartomantik. Two players (+ observers) join a
session with a code and share zones (deck/hand/Limbo/exile/Empathic Vessel),
a free-form battlefield, counters, tokens and score. An optional beta rules
assistant manages the turn flow, priority, stack, costs and reusable card
mechanics while leaving unsupported card text under player control.

## Run locally

```
py -m pip install -r requirements.txt
py server/main.py
```

Then open `http://localhost:8787/` in a browser. Set `HOST`/`PORT` env vars
to change the bind address (defaults to `0.0.0.0:8787`).

## Deploy

Single process serves both the static client and the WebSocket relay on one
port, so any host that runs a long-lived Python process works (Render,
Fly.io, Railway, etc.). Start command:

```
py server/main.py
```

No database, no persistence — sessions live in memory and expire after 6h
of inactivity once a cleanup loop calls the existing expiration predicate.
They are always lost when the process restarts.

Static client assets use versioned URLs and long-lived browser/CDN caching.
Current assisted-rules asset version: `20261009-rules-beta-100`.
When replacing a local asset, bump `20261009-rules-beta-100` in `public/index.html`
and `public/app.js` together.

## Assisted-rules documentation

- [Engine architecture and handoff](docs/ASSISTED_RULES_ENGINE.md)
- [Adding card automation](docs/ADDING_CARD_AUTOMATION.md)
- `public/automation-coverage.json` is the generated per-card coverage registry.

## How it works

- **Session codes**: creating a session yields a player code and a separate
  observer code. Anyone with the player code can play; the observer code is
  read-only.
- **Tournament sessions**: creating a tournament opens a control room instead
  of taking a player seat. It produces fixed Player 1 and Player 2 codes, a
  redacted spectator code, and a judge code. The organizer can verify both
  30-card decks, start/end the match, follow the live audit trail, and export
  the full log. Judges begin in the control room and can switch to a read-only
  full-information table view, then return to monitoring. The organizer can
  also open the live table from the control room without gaining access to
  hidden information.
- **Tournament privacy**: spectator payloads are filtered on the server. They
  receive counts for hands/decks/sideboards, no deck definitions or rarity
  maps, no face-down identities, and redacted log card IDs. Judge access is
  read-only but includes all hidden information. There is no spectator delay.
- **Tournament deck lock**: before the match, the server validates 30 unique
  known cards, a maximum of 500 points, and a sideboard of at most 6 unique
  cards. It also applies the organizer's editable banned-card list and
  restricted groups across the main deck and sideboard. The proposed defaults
  ban Freenya (082), Ergorath (128), and Imitate (086); the first restricted
  group contains Ponder (267), Martyrize (284), and Pray the Ether (281).
  Imports and restrictions lock when the organizer starts the match.
- **Zone permissions** (enforced server-side, not just hidden in the UI):
  `deck`, `hand` and `exile` are private to their owner — opponents only see
  a card count. Judges retain full information; spectators follow the role
  configured by the tournament organizer.
- **Battlefield**: cards are placed face up or face down; face-down cards
  show only the owner's color to everyone except the owner, who can flip
  them at any time.
- **Deck import**: paste either DeckomantiK format ("Copy list" or "Copy for
  KKO") or a JSON export; `maybeboard` groups are excluded automatically. The 5
  official mono-temperament starter decks (30 cards / 400 points each, from
  the rulebook) are offered as one-click presets, and every deck you import
  is kept in a local library (this browser only) so you can reload it next
  time without re-pasting. There's no way to read DeckomantiK's own saved
  decks directly — browsers isolate storage per site, so the two apps can't
  share it; the "Copy list" export plus this local library is the practical
  bridge between them.
- **Pregame**: with rules assistance enabled, both players first select and
  validate a legal deck. They can still edit its sideboard or cancel their
  validation until both decks lock. Only then do they draw seven cards,
  optionally mulligan for 10 points, and mark themselves ready.
- **First Manifestation**: both players place it face down without priority,
  then validate simultaneously. After both choices lock, a dedicated
  Before-Revelation priority window opens while both cards remain face down.
  The two cards reveal together only after that window closes, then their
  simultaneous entry effects are queued. This choice reopens every turn except
  for a player whose winning Manifestation remained through Persist.
- **Confrontation resolution**: the assisted beta totals current Power,
  applies the last-entered Temperament tiebreak, fixes the winner before
  win/loss effects, and then performs the official movement. Opposing
  Manifestations enter the winner's Empathic Vessel; the winner chooses
  Interzone or Deck bottom for each of their own cards, including a guided
  replacement when the Interzone is full. A true tie creates a Stalemate.
  Voluntary Will/effect actions are accepted only during their legal response
  windows, and the Hand aura uses the same phase, payment, and target checks.
  Neutralize is the first encoded Stack interaction: it can be dragged only
  while another played card is a legal Stack target, then sends that card to
  its owner's Limbo without resolving it. Deny and Ignore extend that model to
  conditional counters: the affected owner/controller may pay the requested
  Hollow Tribute directly from their Hand and excess Essences, or let the card
  be neutralized / the effect be cancelled. Imitate can copy a played Will in
  the Stack without paying its cost again; its controller may keep the locked
  target or select a new legal one before the virtual copy is added on top.
  At the start of a new turn, Recovery also readies every exhausted battlefield
  card before beginning-of-turn effects are queued.
- **Action log**: every validated action is recorded server-side with a
  sequence number, turn, and phase. During a tournament, the complete log is
  available live only to organizers and judges; spectators get a redacted
  feed and players can export the full log once the match has ended. Searching
  a deck creates a visible staff alert until that same deck is shuffled; play
  continuing first escalates the alert for a human ruling. Downloaded logs are
  always written in English for consistent tournament records.

## Not in scope (yet)

Complete card-specific automation. The beta now provides a rules engine and a
growing library of encoded reusable mechanics, but unsupported card text can
still require player-applied movement, costs, or results.
