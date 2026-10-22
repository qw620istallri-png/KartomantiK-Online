# Beta 139.2

Asset version: `20261021-rules-beta-139-2`.

## Rules and card fixes

- Reaction waits for a player holding an Ephemeral Will, including when they
  have no Support. An affordability estimate no longer passes that decision
  for them. The explicit pass-all control still applies.
- Immediate actions resolve before normal triggers are offered or placed on
  the Stack. Normal entry triggers are checked again after the immediate
  effects, so an inactive or removed source does not trigger afterward.
- Obelisk of Friendship offers its optional trigger at Reaction. Accepting
  puts the effect on the Stack; gift selection happens during resolution,
  and the exchange continues without a response window inside it.
- Playing a Will attached to a Grimoire uses that Will's encoded ability,
  rather than the Grimoire's. Attached Wills remain listed even when not
  currently playable. Recover from the Abyss and Reforging Fate use a Limbo
  card picker with explicit confirmation and the selected player's cards.
- Juggernut is free to play as a Persistent Will; the cost belongs to its
  field ability. Its automatic and client affordability checks now agree.
- Multicastigate lets its player confirm one target, or choose two and finish
  paying. A larger Tribute, additional Tribute cards and existing Essences
  can together cover the second target. White Essence allocation includes
  that extra cost, and only the final surplus remains as floating Essence.
- A Manifestation moving from Interzone to Support stays visible while the
  movement effect is on the Stack. Countering it leaves the card in Interzone;
  destroying the source does not cause the resolution to resurrect it.
- Temperamental Splendor offers colour symbols when choosing its temperament.
  During payment, the player can explicitly convert each Gem into Essence or
  retain it and use Tribute. Removing the last Gem exiles Splendor.

The order of Revelation and Reaction follows the official rulebook,
section 4.3 (page 29): immediate effects, entry effects, then Reaction and
“after the Revelation” effects. See the
[official rulebook](https://www.kartomantik.com/files/en/kartomantik_Rulebook.pdf).

## Table changes

- Manual mode totals the Confrontation Zone from the displayed card positions,
  including Power counters, and lights the player with priority when phases
  are enabled.
- Suspension has a dedicated card viewer. Cards hidden from the viewer stay
  hidden. Existing Suspend, source-linked release and timed-return mechanics
  remain covered by engine tests.
- Three Persistent Wills can use the available column height on desktop when
  the hand does not overlap that column.
- The defeat dialog's close symbol is centred in its button.

## Regression checks

The special-payment audit also fixes hand highlighting to use the same payment
draft as the picker, including Limbo/Interzone/Vessel Tributes and cost reductions.
Inactive sources no longer grant payment permissions or reductions. Arcane
Teapot does not reduce the cost of activating a field ability. Conditional field
Tribute values use the server's snapshot.

Drildrill's activation explicitly costs two Essences and cannot be paid by
discarding a Tribute card in place of those Essences. Subjugate includes its
target's Point-based supplement in the payment flow and can use Tribute surplus
for it. Gem conversion is available for Essence-only abilities and the player's
own requested payments, without opening a response window during a resolution.
Other pending choices still block conversion.

`tests/test_special_payments.py` checks all printed Interzone Tribute sources,
all encoded Tribute/Essence costs with sufficient and insufficient resources,
Drildrill, Subjugate and ownership/timing of requested Gem payments. Browser
checks cover the matching availability and payment paths on PC and phone.

`tests/test_release_139_2.py` exercises the shipped card encodings, combined
payments, immediate ordering, source removal and Suspension privacy.
`tests/test_release_139_2.cjs` checks the actual UI interactions at desktop and
landscape phone sizes. The WebSocket suite checks Gem conversion and state
broadcasts to both players; the existing engine, catalogue, certification,
auto-pass and frontend suites cover surrounding behavior.
