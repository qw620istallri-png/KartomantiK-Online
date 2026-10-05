# Kartomantik Online

A minimal online game table for Kartomantik. Two players (+ observers) join a
session with a code and share zones (deck/hand/Limbo/exile/Empathic Vessel),
a free-form battlefield, counters, tokens and score. The app enforces no card
rules — players manage those themselves; it only handles state sync,
visibility permissions, and an anti-cheat action log.

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
of inactivity.

Static client assets use versioned URLs and long-lived browser/CDN caching.
When replacing a local asset, bump `20261005-tournament-2` in `public/index.html`,
`public/app.js`, and `public/style.css` together.

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
  `deck` and `hand` are private to their owner — others only see a card
  count. Limbo, Exile and the Empathic Vessel are shared — any player can
  view and act on anyone's.
- **Battlefield**: cards are placed face up or face down; face-down cards
  show only the owner's color to everyone except the owner, who can flip
  them at any time.
- **Deck import**: paste a deck list copied from DeckomantiK ("Copy list") or
  a JSON export; `maybeboard` groups are excluded automatically. The 5
  official mono-temperament starter decks (30 cards / 400 points each, from
  the rulebook) are offered as one-click presets, and every deck you import
  is kept in a local library (this browser only) so you can reload it next
  time without re-pasting. There's no way to read DeckomantiK's own saved
  decks directly — browsers isolate storage per site, so the two apps can't
  share it; the "Copy list" export plus this local library is the practical
  bridge between them.
- **Drawing**: draw one card, or use "Draw hand (7)" to top up to the
  7-card hand limit from the Recovery Phase rule in one click (also the way
  to deal your opening hand right after importing a deck).
- **Action log**: every validated action is recorded server-side with a
  sequence number, turn, and phase. During a tournament, the complete log is
  available live only to organizers and judges; spectators get a redacted
  feed and players can export the full log once the match has ended. Searching
  a deck creates a visible staff alert until that same deck is shuffled; play
  continuing first escalates the alert for a human ruling. Downloaded logs are
  always written in English for consistent tournament records.

## Not in scope (yet)

Card-specific mechanics/automation — this is a generic table, not a rules
engine. A later pass will look at whether any of the 300 cards need
dedicated primitives beyond draw/shuffle/reorder/reveal/counters/tokens.
