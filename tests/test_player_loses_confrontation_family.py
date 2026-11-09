"""Strict player-loss contracts for Grudge Weaver and Zborh."""

from session import ADVANCED_PHASES
from test_game_state import RealCardRulesCase


PLAYER_LOSES_CONFRONTATION_NAMES = (
    "Grudge Weaver",
    "Zborh, the Eternal",
)

GRUDGE = "2hszv736kwwmi7n_en"
ZBORH = "inner-deserts-015"

GRUDGE_TRIGGER = {
    "id": "grudge-counter-after-loss",
    "trigger": {
        "event": "player_loses_confrontation",
        "zone": "interzone",
        "eventController": "owner",
    },
    "result": {
        "kind": "add_counter_source",
        "counter": "Grudge",
        "value": 1,
    },
}

GRUDGE_ACTIVATION = {
    "id": "spend-grudges-for-support",
    "sourceZones": ["battlefield"],
    "removeCountersFromSource": {"name": "Grudge", "amount": 2},
    "targets": {"min": 0, "max": 0},
    "result": {"kind": "grant_source_support_until_end_turn"},
}

ZBORH_TRIGGER = {
    "id": "zborh-returns-after-controller-loses",
    "trigger": {
        "event": "player_loses_confrontation",
        "zone": "interzone",
        "eventController": "owner",
    },
    "result": {"kind": "move_source_to_owner_hand"},
}


class PlayerLosesConfrontationFamily(RealCardRulesCase):
    ALL = (GRUDGE, ZBORH)

    def started(self):
        session, p1, p2 = self.make_session()
        session.phase_tracker.update(
            index=ADVANCED_PHASES.index("confrontation_reaction"), turn=4,
        )
        session.rules_engine.update(
            readyPlayerIds=["p1", "p2"],
            firstManifestationComplete=True,
            firstManifestationTriggersQueued=True,
            priorityPlayerId="p1",
            priorityPasses=[],
            actionStack=[],
            pendingChoice=None,
        )
        return session, p1, p2

    def source(self, card_id, owner, item_id, controller=None, **extra):
        return self.field_item(
            item_id, owner, card_id, field_zone="interzone",
            controllerId=controller or owner, rotation=0.0, **extra,
        )

    def participants(self):
        return (
            self.field_item("loser", "p1", "m-1"),
            self.field_item("winner", "p2", "m-2"),
        )

    @staticmethod
    def set_outcome(session, winner="p2", loser="p1", stalemate=False):
        session.rules_engine["confrontationResult"] = {
            "turn": session.phase_tracker["turn"],
            "winnerId": None if stalemate else winner,
            "loserId": None if stalemate else loser,
            "stalemate": stalemate,
            "participantItemIds": ["loser", "winner"],
            "winnerItemIds": [] if stalemate else ["winner"],
            "loserItemIds": [] if stalemate else ["loser"],
        }

    def test_both_compile_the_exact_selected_contracts(self):
        rules = self.real_rules()
        self.assertEqual(set(rules), set(self.ALL))
        self.assertEqual(
            self.ABILITIES[GRUDGE], [GRUDGE_TRIGGER, GRUDGE_ACTIVATION],
        )
        self.assertEqual(self.ABILITIES[ZBORH], [ZBORH_TRIGGER])
        self.assertEqual(
            rules[GRUDGE]["triggeredAbilities"], [GRUDGE_TRIGGER],
        )
        self.assertEqual(
            rules[GRUDGE]["activatedAbilities"], [GRUDGE_ACTIVATION],
        )
        self.assertEqual(
            rules[ZBORH]["triggeredAbilities"], [ZBORH_TRIGGER],
        )
        self.assertTrue(rules[ZBORH]["adamant"])

    def test_real_loss_queues_both_global_interzone_triggers(self):
        session, _p1, _p2 = self.started()
        loser, winner = self.participants()
        grudge = self.source(GRUDGE, "p1", "grudge")
        zborh = self.source(ZBORH, "p1", "zborh")
        session.battlefield = [grudge, zborh, loser, winner]
        self.set_outcome(session)

        actions = session.queue_rules_confrontation_win_triggers(defer=True)
        selected = [
            entry for entry in actions
            if entry["ability"]["id"] in {
                GRUDGE_TRIGGER["id"], ZBORH_TRIGGER["id"],
            }
        ]
        self.assertEqual(
            [entry["ability"]["id"] for entry in selected],
            [GRUDGE_TRIGGER["id"], ZBORH_TRIGGER["id"]],
        )
        self.assertTrue(all(
            entry["ability"]["trigger"]["eventControllerId"] == "p1"
            and entry["controllerId"] == "p1"
            for entry in selected
        ))

    def test_wrong_outcome_zone_or_inactive_source_does_not_trigger(self):
        for mode in ("owner_wins", "stalemate", "wrong_zone", "disabled"):
            with self.subTest(mode=mode):
                session, _p1, _p2 = self.started()
                loser, winner = self.participants()
                grudge = self.source(GRUDGE, "p1", "grudge")
                zborh = self.source(ZBORH, "p1", "zborh")
                if mode == "wrong_zone":
                    grudge["fieldZone"] = "confrontation"
                    zborh["fieldZone"] = "confrontation"
                if mode == "disabled":
                    grudge["effectsDisabled"] = True
                    zborh["effectsDisabled"] = True
                session.battlefield = [grudge, zborh, loser, winner]
                if mode == "owner_wins":
                    self.set_outcome(session, winner="p1", loser="p2")
                else:
                    self.set_outcome(session, stalemate=mode == "stalemate")
                ids = [
                    entry["ability"]["id"]
                    for entry in session.queue_rules_confrontation_win_triggers(
                        defer=True,
                    )
                ]
                self.assertNotIn(GRUDGE_TRIGGER["id"], ids)
                self.assertNotIn(ZBORH_TRIGGER["id"], ids)

    def test_triggers_follow_current_controller_after_control_change(self):
        for loser_id, expected in (("p2", 2), ("p1", 0)):
            with self.subTest(loser_id=loser_id):
                session, _p1, _p2 = self.started()
                loser = self.field_item("loser", loser_id, "m-1")
                winner_id = "p1" if loser_id == "p2" else "p2"
                winner = self.field_item("winner", winner_id, "m-2")
                grudge = self.source(
                    GRUDGE, "p1", "grudge", controller="p2",
                )
                zborh = self.source(
                    ZBORH, "p1", "zborh", controller="p2",
                )
                session.battlefield = [grudge, zborh, loser, winner]
                self.set_outcome(
                    session, winner=winner_id, loser=loser_id,
                )
                selected = [
                    entry
                    for entry in session.queue_rules_confrontation_win_triggers(
                        defer=True,
                    )
                    if entry["ability"]["id"] in {
                        GRUDGE_TRIGGER["id"], ZBORH_TRIGGER["id"],
                    }
                ]
                self.assertEqual(len(selected), expected)
                self.assertTrue(all(
                    entry["controllerId"] == "p2" for entry in selected
                ))

    def test_grudge_adds_exactly_one_counter_per_loss(self):
        session, _p1, _p2 = self.started()
        grudge = self.source(GRUDGE, "p1", "grudge")
        loser, winner = self.participants()
        session.battlefield = [grudge, loser, winner]
        self.set_outcome(session)
        for expected in (1, 2):
            actions = session.queue_rules_confrontation_win_triggers(defer=True)
            action = next(
                entry for entry in actions
                if entry["ability"]["id"] == GRUDGE_TRIGGER["id"]
            )
            result = session.apply_rules_action_result(action)
            self.assertEqual(
                (result["status"], result["counter"], result["value"]),
                ("added", "Grudge", expected),
            )
            self.assertEqual(grudge["counters"], {"Grudge": expected})

    def test_grudge_spends_two_counters_for_support_this_turn_only(self):
        for zone in ("interzone", "confrontation"):
            with self.subTest(zone=zone):
                session, _p1, _p2 = self.started()
                grudge = self.source(GRUDGE, "p1", "grudge")
                grudge["fieldZone"] = zone
                session.battlefield = [grudge]
                grudge["counters"] = {"Grudge": 1}
                source = {
                    "cardId": GRUDGE,
                    "zone": "battlefield",
                    "itemId": "grudge",
                }
                error, action = session.declare_rules_action(
                    "p1", "Spend Grudges", kind="activated_effect",
                    source=source, ability_id=GRUDGE_ACTIVATION["id"],
                )
                self.assertIn("needs 2", error or "")
                self.assertIsNone(action)
                self.assertEqual(grudge["counters"], {"Grudge": 1})

                grudge["counters"] = {"Grudge": 2}
                error, action = session.declare_rules_action(
                    "p1", "Spend Grudges", kind="activated_effect",
                    source=source, ability_id=GRUDGE_ACTIVATION["id"],
                )
                self.assertIsNone(error, error)
                self.assertEqual(grudge["counters"], {"Grudge": 0})
                session.rules_engine["actionStack"].remove(action)
                result = session.apply_rules_action_result(action)
                self.assertEqual(result["status"], "granted")
                self.assertEqual(grudge["supportUntilTurn"], 4)
                self.assertTrue(session.rules_card_can_enter_support(grudge))
                session.phase_tracker["turn"] = 5
                self.assertFalse(session.rules_card_can_enter_support(grudge))

    def test_zborh_returns_to_immutable_owner_hand_after_controller_loses(self):
        session, p1, _p2 = self.started()
        loser = self.field_item("loser", "p2", "m-1")
        winner = self.field_item("winner", "p1", "m-2")
        zborh = self.source(ZBORH, "p1", "zborh", controller="p2")
        session.battlefield = [zborh, loser, winner]
        self.set_outcome(session, winner="p1", loser="p2")
        actions = session.queue_rules_confrontation_win_triggers(defer=True)
        action = next(
            entry for entry in actions
            if entry["ability"]["id"] == ZBORH_TRIGGER["id"]
        )
        self.assertEqual(action["controllerId"], "p2")
        result = session.apply_rules_action_result(action)
        self.assertEqual(
            (result["status"], result["toZone"], result["reason"]),
            ("moved", "hand", "return"),
        )
        self.assertEqual(p1["zones"]["hand"], [ZBORH])
        self.assertEqual(p1["zoneOwners"]["hand"], {ZBORH: "p1"})
        self.assertIsNone(session.find_battlefield_item("zborh"))
