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
- Full card-text automation is a separate, incremental project built on the
  optional assisted-rules beta rather than the tournament transport itself.
- Casual games may opt into the assisted-rules beta before creation. Its
  server-authoritative foundation locks the detailed phase tracker, manages
  player priority and LIFO Stack order, resolves both Recovery draws together,
  and calculates the end-game deck bonus only after both decks have been
  consumed by that draw. The primary play path is board-first: dragging a
  playable Manifestation places it at the drop position, while dragging a Will
  stages it at the right edge, shows compatible Essences above the Hand, lets
  the player pay with highlighted Manifestations, then draws a curved pointer
  to legal targets on the table. The detailed declaration form remains a debug
  fallback. For a played Will, the server reads the
  printed Tribute, spends compatible excess Essences first, enforces both the
  required Temperaments and rejects only Manifestations that are superfluous
  inside the selected payment,
  creates any resulting excess Essence, and moves paid Manifestations from Hand
  to their owner's Limbo before adding the action to the Stack. The played
  source leaves its controller's Hand immediately and becomes the public card
  represented in the Stack; no other hidden Hand card is disclosed. A resolved
  Ephemeral Will then moves from the Stack to its owner's Limbo automatically.
  A Persistent Will dragged from Hand now remembers its intended board position,
  remains publicly visible in the Stack while pending, then enters the
  battlefield there automatically when it resolves; any encoded face-up entry
  trigger is queued above the remaining Stack. Unencoded activated-effect costs and
  effect resolution remain manual until each reusable mechanic is modelled. A first
  source-bound Persistent Will pilot covers Flaying Jaw: its target is locked while
  the card is played, its -2 Power is applied by the confrontation engine after the
  Will enters the field, and the relationship disappears with either card. A first
  encoded-ability pilot covers Nullifying Hat, Mimer, and Bolbakazim: the
  server owns their target count/type constraints, printed Tribute,
  and source exhaustion before the effect enters the Stack. The effect's
  outcome remains player-applied. Sacrificing an encoded source is now paid
  immediately and shown moving to its owner's Limbo. Named-counter, discard,
  exile, and once-per-turn costs remain outside this pilot.
- Server-confirmed assisted-rules actions produce synchronized, non-blocking
  visual feedback: paid Tribute cards and Essence converge toward the Stack,
  an exhausted source receives a brief field marker, and resolution gets a
  distinct confirmation. Reconnects never replay old effects, motion is capped
  to a few short transform/opacity animations, and reduced-motion users keep
  only localized confirmations.
- Assisted-rules matches begin with a server-owned opening sequence. As soon as
  both decks are validated, both seven-card hands are drawn and checked
  automatically. A valid hand waits for an explicit choice: keep it, or use the
  single voluntary Mulligan for a 10-point penalty. If either hand has no
  playable Manifestation, both players are frozen and the affected player must
  use that same one-time Mulligan. A valid redraw must be kept explicitly; an
  invalid redraw loses the game (two simultaneous failures are a draw). The
  match begins only after both players keep a valid hand. Normal board actions remain
  locked throughout this check; the first playable Recovery step then gives
  priority to the first player seat. From turn two onward, beginning and draw
  Recovery steps advance automatically while no encoded beginning-of-turn
  trigger exists: both hands refill to their effective limits before either
  deck shortage is evaluated. A hand without a playable Manifestation freezes
  both players for its mandatory, cost-free Mulligan. A valid redraw resumes
  at the End of Recovery with priority held by the previous Confrontation winner;
  an invalid redraw loses the game. During every Confrontation step, priority
  belongs to the player who would lose if the Confrontation resolved at that
  moment, including the Temperament tiebreak. While the Stack is non-empty,
  priority instead follows the controller of its current top action.
- The assisted-rules play surface keeps the board dominant. The application
  header retracts until the pointer reaches the top edge. A compact phase and
  priority instrument sits at the bottom right, with the live Stack directly
  above it. Stack entries show their source card and inherit their controller's
  colour; phase detail appears on hover instead of remaining permanently
  visible. Hand commands open from a stacked bottom-left menu.
- The reference inspector is left-docked so it does not compete with the
  bottom-right phase/priority instrument. Games without assisted rules still
  surface the deck-import setup when the seated player has not selected a deck;
  importing a deck dismisses that setup without enabling rules automation.
- Player cards form a partially off-screen bottom fan and the opponent's
  privacy-filtered cards form a mirrored top fan. Legal Hand cards receive a
  blue aura only where the current beta rules can prove they are playable:
  Ephemeral Wills during Reaction, Resolution effects, or End actions;
  Persistent Wills only during End actions on an empty Stack; and
  Manifestations during the correct Confrontation step. Ongoing-effect markers
  sit on the bottom-left of affected battlefield cards. The server repeats the
  timing check so a forged client cannot bypass the visual gate.
- Assisted confrontation resolution follows the rulebook's three Resolution
  steps. The server destroys participating Manifestations at zero Power,
  compares current Power totals and then the Temperament of the last
  Manifestation each player added, fixes the outcome before triggered effects,
  and owns final movement. A compact score/outcome line appears only during
  Resolution. The winner captures opposing Confrontation and Stalemate cards,
  then receives a focused Interzone/Deck-bottom choice for each own card; a
  full Interzone prompts a specific replacement. Equal Power and equal last
  Temperament move all participants into Stalemate instead. Small authored
  markers distinguish Confrontation, Interzone, and Stalemate without adding a
  permanent explanatory panel to the board.
- Encoded abilities with a continuing result now create public ongoing-effect
  state on resolution. The board gives the affected card a persistent marker
  and traces its relationship back to the source. End-of-turn effects expire
  when the next turn begins; source-bound effects are removed when their source
  or target leaves the battlefield. The marker tracks the relationship while
  players still apply the printed power and temperament result manually.
- A first automatic trigger pilot covers Graceful Petal entering an opponent's
  Empathic Vessel. The server places its effect on the Stack, gives the opponent
  the normal reaction window, and awards 20 points to the card's owner only
  when that trigger resolves. The trigger remains valid if its source moves
  after entering the Vessel.
- A second automatic trigger pilot covers Keen-eyed Seeker entering the field
  face up. Its draw enters the same reaction cycle and moves one card from its
  owner's Deck to their private Hand only when the trigger resolves. A face-down
  placement never announces or queues the effect, preventing an identity leak.
- Reliable Ammonite now connects the automatic cost and trigger pipelines: when
  it is paid as a revealed Tribute, its draw trigger and the paid action are
  treated as simultaneous. Their controller chooses their order before the
  complete batch enters the Stack and receives the normal reaction window.
- Half Han now exercises negative score resolution: entering the field face up
  queues its 20-point loss, leaves the normal response window intact, and only
  changes its owner's score when the trigger resolves. Its alternate end-game
  victory condition remains manual until alternate outcomes are modelled.
- Dark Apparition pilots targeted automatic triggers and mandatory private
  choices. Its controller chooses a player before the face-up placement is
  sent, the public target travels with the effect through the Stack, and the
  targeted player privately chooses the card to discard only after resolution.
  Priority pauses until that required choice is complete; only the discarded
  card's now-public identity is written to the shared log.
- Strengthen, Oppress, Weaken, and Accentuate pilot encoded effects for cards
  played from Hand. The server validates their Manifestation target, pays the
  printed Tribute through the existing payment engine, moves the Ephemeral
  Will to its owner's Limbo on resolution, and attaches a stacking public
  power modifier to the target until the turn ends.
- Banish and Defer pilot automatic battlefield movement. Their targets and
  allowed card types are locked when declared; on resolution the server moves
  a still-present target to the correct top or bottom of its owner's Deck. A
  target that left in response causes a clearly logged no-target resolution,
  while a targeted copy simply ceases to exist.
- Exile pilots structured targets in public zones. Its declaration offers legal
  Manifestations both on the field and in either player's Limbo, records the
  chosen zone in the Stack, and moves a still-present card to its owner's Exile
  on resolution. This extends the reusable target model without exposing Hands
  or Deck contents.
- Disfigure pilots automatic destruction. The server only offers Manifestations
  on the field or in an Empathic Vessel whose printed value is 20 points or
  less, rechecks that limit before payment, then destroys a still-present target
  into its owner's Limbo. Destruction has its own public log wording and visual
  feedback rather than appearing as an unexplained generic move.
- Remove by Chance pilots server-owned random selection. Its controller locks a
  player target in the Stack; only on resolution does the server choose one of
  that player's eligible Manifestations in the Empathic Vessel, reveal the
  result in the log, and destroy it into its owner's Limbo. An empty eligible
  set resolves explicitly without a card instead of asking either player to
  simulate randomness.
- Eliminate the Profane reuses the same destruction pipeline for an explicitly
  selected Manifestation in any Empathic Vessel. Battlefield cards are not
  offered as candidates, and ownership is preserved when the target moves from
  another player's Vessel to its owner's Limbo.
- Neutralize pilots direct Stack interaction. It receives a playable aura only
  while a played card remains on the Stack, lets its controller select that
  visible card through the same board-first target flow, and revalidates the
  exact action on the server. On resolution the target card leaves the Stack
  for its owner's Limbo without applying its effect; already paid costs remain
  paid. A target removed by an earlier response produces an explicit no-target
  resolution instead of affecting a different Stack entry.
- Deny and Ignore extend Stack interaction through one server-owned conditional
  payment flow. Deny targets only played cards and asks their owner for two
  Hollow Tribute; Ignore targets only activated or triggered effects and asks
  their controller for the same payment. While that decision is pending, the
  target remains visibly marked in the Stack and all other actions are frozen.
  The responding player pays from highlighted Hand Manifestations after excess
  Essences are reserved automatically, or explicitly lets the card be
  neutralized / the effect be cancelled. Paid costs remain spent, Tribute
  triggers still enter the Stack, and every outcome is named in the public and
  tournament logs.
- Imitate pilots reusable Stack copies. It targets only a played Ephemeral or
  Persistent Will, resolves into a cost-free virtual copy, and never moves a
  second physical card. If the copied effect has a target, its controller uses
  the board-first arrow to keep the original target or select another legal
  one. The copy is visibly labelled in the Stack, gives the opponent priority,
  and records linked card names in both player and tournament logs.
- Pluff pilots automatic discard from the top of a Deck. Its face-up field-entry
  trigger receives the normal response window, then reveals and moves the top
  card to its owner's Limbo only on resolution. The public log names the card,
  an empty Deck resolves explicitly, and this discard does not itself invoke the
  incomplete-Recovery-hand end condition.
- Beginning-of-turn automation readies all exhausted battlefield cards before
  permissions and triggers are evaluated, then pauses the automatic Recovery draw whenever
  an encoded effect enters the Stack. Spontaneous Incubator awards its points
  only while it begins the turn in the Interzone. Soul-devouring Dunes gives
  each player, in seat order, the server-validated choice between losing 10
  points and moving the bottom three cards of their Deck to Limbo; short Decks
  cannot choose the impossible discard.
- Wandering Veteran is deliberately modelled as a conditional play permission,
  not as a beginning-of-turn trigger. If it is in its owner's Limbo when the
  turn begins, it remains there and appears beside that pile as an available
  Support card. During Confrontation Reaction, while its owner has priority, it
  can be dragged directly onto the battlefield; the server consumes the
  permission, marks it as Support, and treats its Temperament as Hollow. If it
  wins that confrontation, it is exiled automatically instead of receiving the
  normal winner destination choice.
- Support is now a server-owned reusable play state rather than a visual label
  specific to one card. Printed “Support from hand” Manifestations are playable
  from Hand only during Reaction with priority; printed Support cards can enter
  from the Interzone under the same timing and priority checks. Cards explicitly
  forbidden as First Manifestations are excluded from the opening aura and
  rejected again by the server. Every accepted Support entry is marked on the
  battlefield and in the log. The shared winner cleanup also recognizes the
  printed “win as Support: exile it” destination used by Jondo, Inert Anchorstone,
  Tenebro, and Wandering Veteran once those cards have legally entered Support.
  Merciful Pago now uses the same cleanup seam: after winning in Support it
  enters the opposing player's Empathic Vessel and awards that player 10 points,
  with the movement and score change exposed in the public log and board VFX.
  A shared continuous-power evaluator also covers the public Support modifiers
  printed on Sprawling Tentacle, Herbaceous Whisperer, Gargullo, Cimba, and
  Skapus; these modifiers feed both live priority totals and final resolution.
  Support entry is now a first-class public trigger event. Mazzolong watches
  legally played Support Manifestations while it is in the Interzone and draws
  for its owner on resolution; Wheel of Retribution watches every Support entry
  and makes that Manifestation's controller discard through the existing private
  choice flow. Both effects use the normal Stack and priority response window.
  Targeted entry triggers reuse the board-first arrow instead of opening another
  form: Flower Tender selects another Confrontation Manifestation with current
  Power 2 or less and grants +2 until end of turn; Chitinous Repeller returns a
  friendly Confrontation Manifestation; and Chiff and Chaff returns an opposing
  Support Manifestation. Returned targets cannot be replayed that turn. Chiff
  and Chaff gains its conditional Support-from-Hand timing only after an opponent
  has moved a Manifestation from their Interzone into Support during that turn.
- Ponder pilots a direct encoded result for an Ephemeral Will played from Hand.
  Its Hollow Tribute is paid when declared, the card and Deck remain otherwise
  unchanged through the response window; when the action resolves, Ponder enters
  Limbo and exactly three available cards are drawn privately.
- Pray the Ether pilots conditional hand payment as a reusable private-choice
  result. After the Will resolves into Limbo, its controller privately chooses
  1 card to discard; only a completed discard draws up to 2 available cards.
  If no card remains to pay, the effect records an unpaid result and draws none.
- Urocione pilots Chain as a reusable post-resolution choice. Its face-up field
  entry uses the normal Stack and response window; after resolution, only its
  controller sees eligible Manifestations highlighted in the required private
  zone. Dragging one onto the table moves it into Support, marks it as played,
  and queues its normal field/Support entry triggers. The optional choice may be
  declined. If Urocione's Chained Manifestation wins in Support, it enters the
  opposing player's Empathic Vessel as if it had lost, with the movement exposed
  in the public log and board feedback without revealing the rest of the Hand.

## Capabilities and Constraints

- Preserve the existing casual-game workflow and visual language.
- Keep keyboard accessibility, locale-completeness cleanup, and assisted-mode
  onboarding as explicit follow-up work; they are not part of the current
  Stack/layout implementation pass.
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
