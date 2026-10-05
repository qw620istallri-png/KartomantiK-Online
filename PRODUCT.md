# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

- KartomantiK players running casual online games.
- Tournament organizers who create and supervise a match without occupying a player seat.
- Tournament judges who follow a match, inspect all hidden information when necessary, and remain read-only.
- Spectators who follow only public game information.

## Product Purpose

Kartomantik Online (KKO) is a synchronized virtual table for remote KartomantiK games. It preserves the physical game's player-led rules while the server owns shared state, visibility permissions, random operations, and the action record.

Tournament mode adds role-separated match supervision: the organizer creates a lobby, distributes dedicated access codes, follows attendance and match state, reads and exports the live log, and never occupies a player seat.

## Positioning

KKO combines a free-form tabletop with server-filtered hidden information and an auditable match history. Tournament mode prioritizes trustworthy supervision without turning this delivery into a fully automated card-rules engine.

## Operating Context

- A casual match has two players and the existing observer access.
- A tournament match has dedicated Player 1, Player 2, spectator, judge, and organizer roles.
- The creator remains in an organizer console rather than entering the game table.
- A spectator sees the public board, revealed cards, public counts, phases, scores, and public activity, but never receives hands, deck contents, sideboards, or face-down identities.
- A judge is read-only, can inspect all hidden information, and can switch between the tournament follow-up console and a complete match view.
- An organizer can switch to the live public match view and return to monitoring, but does not receive hidden card data.
- No delayed spectator feed is required.
- Card-effect automation is a separate future project.

## Capabilities and Constraints

- Preserve the existing casual-game workflow and visual language.
- Tournament access codes are role-bound and player codes claim one fixed seat.
- Tournament decks may be imported while the lobby is waiting and are locked once the match begins.
- The organizer may edit banned cards and any number of restricted groups before the match. Bans and restricted groups apply to the combined main deck and sideboard.
- The proposed defaults ban Freenya (082), Ergorath (128), and Imitate (086). The first restricted group contains Ponder (267), Martyrize (284), and Pray the Ether (281).
- The tournament state is visible as lobby, active, or ended.
- Organizers and judges receive the live server log and can export it.
- A deck search is logged immediately. It remains a visible staff warning until the searched deck is shuffled, and becomes critical if the player continues first; the judge decides whether the sequence is acceptable.
- On-screen log text follows the interface language, while downloaded tournament logs remain English.
- Judges, spectators, and organizers cannot perform game actions.
- Sessions currently live in one Python process and are not database-persistent; durable multi-match tournament storage remains outside this delivery.

## Brand Commitments

- Preserve the existing Kartomantik Online name, visual identity, typography, board presentation, and EN/FR/IT interface support.

## Evidence on Hand

- Existing implementation: `public/index.html`, `public/style.css`, `public/app.js`, `public/i18n.js`.
- Server authority and role filtering: `server/main.py`, `server/session.py`.
- Existing regression coverage: `tests/test_game_state.py`, `tests/test_frontend.cjs`.

## Product Principles

- Hidden information is removed server-side, never merely concealed in the interface.
- Every role receives only the controls and data required for its job.
- Tournament supervision remains readable under live-match pressure.
- Casual play stays compatible while tournament rules become stricter.
- Card automation must not leak into the tournament-mode foundation.
