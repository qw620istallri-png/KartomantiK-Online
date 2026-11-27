"""Bug report 27/11: Gigabonblade paid its Reduce cost down to 0 Power and
stayed on the field. A Manifestation at 0 or less is destroyed as soon as it
gets there, including when a cost brought it there."""

from session import ADVANCED_PHASES
from test_game_state import RealCardRulesCase


GIGABONBLADE = "inner-deserts-062"
FRIENDLY_PRESENCE = "l6ragmkyw5oyued_en"
ABILITY_ID = "gigabonblade-gains-persist"


class ReduceCostToZeroPower(RealCardRulesCase):
    ALL = (GIGABONBLADE, FRIENDLY_PRESENCE)

    def started(self):
        session, p1, p2 = self.make_session()
        session.phase_tracker.update(
            index=ADVANCED_PHASES.index("confrontation_reaction"), turn=1,
        )
        session.rules_engine.update(
            readyPlayerIds=["p1", "p2"], firstManifestationComplete=True,
            firstManifestationTriggersQueued=True, priorityPlayerId="p1",
            priorityPasses=[], actionStack=[], pendingChoice=None,
        )
        return session, p1, p2

    def declare(self, session, giga):
        session.rules_engine["priorityPlayerId"] = "p1"
        return session.declare_rules_action(
            "p1", "Gigabonblade gains Persist", kind="activated_effect",
            source={"cardId": GIGABONBLADE, "zone": "battlefield", "itemId": giga["id"]},
            ability_id=ABILITY_ID,
            targets=[{"kind": "card", "itemId": giga["id"],
                      "cardId": GIGABONBLADE, "ownerId": "p1"}],
        )

    def weaken(self, session, item, value):
        session.rules_engine["ongoingEffects"].append({
            "id": f"weaken-{item['id']}", "kind": "power_modifier", "value": value,
            "duration": "until_end_of_turn", "startedTurn": 1, "controllerId": "p2",
            "source": {"cardId": FRIENDLY_PRESENCE},
            "target": {"kind": "card", "itemId": item["id"],
                       "cardId": item["cardId"], "ownerId": item["ownerId"]},
        })

    def test_reported_game_gigabonblade_dies_at_zero_and_weakens_the_field(self):
        session, p1, p2 = self.started()
        giga = self.field_item("giga", "p1", GIGABONBLADE)
        presence = self.field_item("presence", "p2", FRIENDLY_PRESENCE, isSupport=True)
        flower = self.field_item("flower", "p2", "m-3", isSupport=True, counters={"power": 1})
        julien = self.field_item("julien", "p2", "m-4", counters={"power": 2})
        session.battlefield = [giga, presence, flower, julien]
        self.weaken(session, giga, -2)
        self.assertEqual(self.power_of(session, "giga"), 4)
        self.assertIsNone(self.declare(session, giga)[0])
        self.assertEqual(self.power_of(session, "giga"), 2)
        self.assertIn(giga, session.battlefield)
        error, action = self.declare(session, giga)
        self.assertIsNone(error, error)
        self.assertEqual(action["cost"]["reducedSourcePower"], 2)
        # At 0 Power: destroyed at once, so its replacement exiles it and
        # every Manifestation on the field gets -2.
        self.assertNotIn(giga, session.battlefield)
        self.assertIn(GIGABONBLADE, p1["zones"]["exile"])
        self.assertNotIn(presence, session.battlefield)
        self.assertNotIn(flower, session.battlefield)
        self.assertIn(FRIENDLY_PRESENCE, p2["zones"]["graveyard"])
        self.assertIn(julien, session.battlefield)
        self.assertEqual(self.power_of(session, "julien"), 1)

    def test_reduce_cost_that_leaves_power_above_zero_destroys_nothing(self):
        session, _p1, _p2 = self.started()
        giga = self.field_item("giga", "p1", GIGABONBLADE)
        session.battlefield = [giga]
        self.assertIsNone(self.declare(session, giga)[0])
        self.assertIn(giga, session.battlefield)
        self.assertEqual(self.power_of(session, "giga"), 4)
