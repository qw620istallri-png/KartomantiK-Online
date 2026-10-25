"""Independent, printed-text oracles for the first150 catalog entries.

Actual actions use shipped definitions. Assertions below are handwritten from
English card text / creator rulings, never calculated from ability metadata.
These focused cases are not a certification of every clause in the batch.
"""
import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))
import main
from session import Session, ADVANCED_PHASES


class SemanticBatch001150(unittest.TestCase):
    @staticmethod
    def cid(name):
        return next(c["id"] for c in main.CARD_DATA if c["name"] == name)

    def world(self):
        rules = copy.deepcopy(main.CARD_RULES)
        for cid, power in (("m2", 2), ("m3", 3), ("m4", 4)):
            rules[cid] = {"type": "manifestation", "power": power,
                          "temperaments": ["phlegmatic"], "powerCost": "{G}" * power}
        rules["w2"] = {"type": "ephemeral_will", "cost": 2, "powerCost": "{H}{H}"}
        rules["pw3"] = {"type": "persistent_will", "cost": 3, "powerCost": "{H}{H}{H}"}
        session = Session(card_rules=rules, rules_beta=True,
                          card_points={c["id"]: c.get("points") or 0 for c in main.CARD_DATA},
                          manifestation_ids={cid for cid, rule in rules.items()
                                             if rule.get("type") == "manifestation"})
        for seat, pid in enumerate(("p1", "p2")):
            p = session.get_or_create_player(pid, pid.upper(), seat=seat)
            p["score"] = 50
        session.phase_tracker.update(enabled=True, advanced=True, turn=2,
                                     index=ADVANCED_PHASES.index("confrontation_reaction"))
        session.rules_engine.update(firstManifestationComplete=True,
                                    firstManifestationTriggersQueued=True,
                                    readyPlayerIds=["p1", "p2"], deckConfirmedPlayerIds=["p1", "p2"])
        return session

    @staticmethod
    def field(session, cid, item="source", owner="p1", controller=None,
              zone="confrontation", support=False, power_bonus=0):
        obj = {"id": item, "cardId": cid, "ownerId": owner,
               "controllerId": controller or owner, "faceUp": True,
               "fieldZone": zone, "isSupport": support,
               "x": 0, "y": 0, "rotation": 0, "counters": {}}
        if power_bonus:
            obj["counters"]["power"] = power_bonus
        session.battlefield.append(obj)
        return obj

    @staticmethod
    def put(session, pid, zone, cards):
        session.players[pid]["zones"][zone] = list(cards)
        session.players[pid]["zoneOwners"][zone] = {c: pid for c in cards}

    @staticmethod
    def target(item):
        return {"kind": "card", "itemId": item["id"], "cardId": item["cardId"],
                "ownerId": item["ownerId"], "controllerId": item["controllerId"]}

    def action(self, name, item=None, targets=(), ability_id=None, controller="p1"):
        cid = self.cid(name)
        abilities = main.CARD_ABILITIES[cid]
        ability = next(a for a in abilities if a.get("id") == ability_id) if ability_id else abilities[0]
        return {"id": "semantic-action", "controllerId": controller,
                "kind": "triggered_effect" if ability.get("trigger") else "play_card",
                "source": {"cardId": cid, "itemId": (item or {}).get("id"),
                           "ownerId": (item or {}).get("ownerId", controller), "zone": "battlefield"},
                "targets": list(targets), "ability": copy.deepcopy(ability), "optionalAccepted": True}

    def test_bottom_shuffle_clause_covers_on_and_at_wording(self):
        # Each printed clause says to shuffle after bottom placement. Top is negative branch.
        for name in ("Agrupol, Ponderer of Fields", "Gomeran, Echo Mistress", "Carcass Devourer"):
            for position, expected_calls in (("bottom", 1), ("top", 0)):
                with self.subTest(card=name, position=position):
                    s = self.world()
                    self.put(s, "p1", "deck", ["m2", "m3"])
                    with patch("game.zones.random.shuffle") as shuffle:
                        s.put_zone_card("p1", "deck", self.cid(name), "p1", position)
                    self.assertEqual(shuffle.call_count, expected_calls)

    def test_blossom_tracks_current_controller_after_control_change(self):
        for owner, controller, entrant, expected in (
                ("p1", "p1", "p1", 1), ("p1", "p1", "p2", 0),
                ("p1", "p2", "p2", 1), ("p1", "p2", "p1", 0)):
            with self.subTest(owner=owner, controller=controller, entrant=entrant):
                s = self.world()
                blossom = self.field(s, self.cid("Intoxicating Blossom"), owner=owner,
                                     controller=controller, zone="field")
                entered = self.field(s, "m2", "new", owner=entrant)
                actions = s.queue_rules_manifestation_entry_watchers(entered, defer=True)
                self.assertEqual(len(actions), expected)
                for action in actions:
                    s.apply_rules_action_result(action)
                self.assertEqual(blossom["counters"].get("Petal", 0), expected)

    def test_pago_win_as_support_waits_on_stack_then_moves_and_pays_ten(self):
        s = self.world()
        pago = self.field(s, self.cid("Merciful Pago"), support=True)
        s.rules_engine["confrontationResult"] = {
            "turn": 2, "winnerId": "p1", "loserId": "p2", "stalemate": False,
            "participantItemIds": ["source"], "winnerItemIds": ["source"], "loserItemIds": []}
        actions = s.queue_rules_confrontation_win_triggers(defer=True)
        self.assertEqual(len(actions), 1, "Printed When...wins...as Support is a triggered effect")
        self.assertIn(pago, s.battlefield)
        self.assertEqual(s.players["p2"]["score"], 50)
        action = actions[0]
        action["targets"] = [{"kind": "player", "playerId": "p2"}]
        s.apply_rules_action_result(action)
        self.assertNotIn(pago, s.battlefield)
        self.assertIn(pago["cardId"], s.players["p2"]["zones"]["receptacle"])
        self.assertEqual(s.players["p2"]["score"], 60)
        self.assertEqual(s.players["p1"]["score"], 50)

    def test_pago_first_winner_and_losing_support_have_no_win_trigger(self):
        for support, winner in ((False, "p1"), (True, "p2")):
            with self.subTest(support=support, winner=winner):
                s = self.world()
                self.field(s, self.cid("Merciful Pago"), support=support)
                s.rules_engine["confrontationResult"] = {
                    "turn": 2, "winnerId": winner, "loserId": "p2" if winner == "p1" else "p1",
                    "stalemate": False, "participantItemIds": ["source"]}
                self.assertEqual(s.queue_rules_confrontation_win_triggers(defer=True), [])

    def test_prospero_counts_own_interzone_including_source_and_tokens(self):
        s = self.world()
        first = self.field(s, "m2", "first")
        prospero = self.field(s, self.cid("Prospero of the Bushes"), zone="interzone")
        self.field(s, "m3", "ally", zone="interzone")
        token = self.field(s, "m2", "token", zone="interzone")
        token.update(isTokenCard=True, power=1, temperament="phlegmatic")
        self.field(s, "m4", "enemy", owner="p2", zone="interzone")
        s.rules_engine["firstManifestationItemIds"] = {"p1": "first"}
        self.assertEqual(s.rules_manifestation_characteristics(first)["power"], 5)
        prospero["fieldZone"] = "confrontation"
        self.assertEqual(s.rules_manifestation_characteristics(first)["power"], 2)

    def test_sprawling_threshold_is_four_manifestations_across_both_players(self):
        for count, expected_bonus in ((3, 0), (4, 1), (5, 1)):
            with self.subTest(count=count):
                s = self.world()
                source = self.field(s, self.cid("Sprawling Tentacle"), support=True)
                printed = 1  # English catalog printed power, independent of encoded continuous rule.
                for n in range(count - 1):
                    self.field(s, "m2", f"other-{n}", owner="p1" if n % 2 else "p2")
                self.assertEqual(s.rules_manifestation_characteristics(source)["power"], printed + expected_bonus)

    def test_tipson_and_urn_count_their_respective_zones(self):
        for name, expected in (("Tipson, the Mediator", 4), ("Repelling Urn", 4)):
            with self.subTest(card=name):
                s = self.world()
                source = self.field(s, self.cid(name))
                self.put(s, "p1", "hand", ["m2", "w2", "m3"])
                self.put(s, "p1", "graveyard", ["m2", "m3", "m4", "w2"])
                self.assertEqual(s.rules_manifestation_characteristics(source)["power"], expected)
                source["fieldZone"] = "interzone"
                self.assertEqual(s.rules_manifestation_characteristics(source)["power"], 1)

    def test_entrust_doubles_base_without_doubling_additive_bonus(self):
        s = self.world()
        item = self.field(s, "m3", "target", power_bonus=2)
        action = self.action("Entrust", targets=[self.target(item)])
        s.apply_rules_action_result(action)
        self.assertEqual(s.rules_manifestation_characteristics(item)["power"], 8)
        action["id"] = "second-entrust"
        s.apply_rules_action_result(action)
        self.assertEqual(s.rules_manifestation_characteristics(item)["power"], 14)

    def test_carcass_exiles_two_printed_bases_for_exact_five_power(self):
        s = self.world()
        item = self.field(s, self.cid("Carcass Devourer"))
        self.put(s, "p1", "graveyard", ["m2", "m3", "w2"])
        targets = [{"kind": "zone_card", "containerId": "p1", "ownerId": "p1",
                    "zone": "graveyard", "cardId": cid} for cid in ("m2", "m3")]
        s.apply_rules_action_result(self.action("Carcass Devourer", item, targets))
        self.assertEqual(item["counters"].get("power"), 5)
        self.assertEqual(s.players["p1"]["zones"]["graveyard"], ["w2"])
        self.assertCountEqual(s.players["p1"]["zones"]["exile"], ["m2", "m3"])

    def test_floating_dancer_scores_five_per_own_interzone_not_stalemate(self):
        s = self.world()
        item = self.field(s, self.cid("Floating Dancer"))
        for n in range(3):
            self.field(s, "m2", f"own-{n}", zone="interzone")
        self.field(s, "m4", "enemy", owner="p2", zone="interzone")
        self.field(s, "m2", "stale", zone="stalemate")
        s.apply_rules_action_result(self.action("Floating Dancer", item))
        self.assertEqual(s.players["p1"]["score"], 65)
        self.assertEqual(s.players["p2"]["score"], 50)

    def test_petal_payment_bonus_uses_removed_count_not_current_count(self):
        s = self.world()
        item = self.field(s, self.cid("Intoxicating Blossom"), zone="field")
        target = self.field(s, "m2", "target")
        action = self.action("Intoxicating Blossom", item, [self.target(target)],
                             ability_id="spend-petals-for-power")
        action["cost"] = {"removedCounters": [{"name": "Petal", "amount": 3}]}
        # Cost already removed all counters. The effect uses the captured paid amount.
        s.create_rules_ongoing_effects(action)
        self.assertEqual(s.rules_manifestation_characteristics(target)["power"], 5)

    def test_suspend_judgment_holds_current_controllers_winners_not_original_owners(self):
        s = self.world()
        stolen = self.field(s, "m3", "stolen-winner", owner="p2", controller="p1")
        losing = self.field(s, "m2", "stolen-loser", owner="p1", controller="p2")
        s.rules_engine["confrontationResult"] = {"turn": 2, "winnerId": "p1", "loserId": "p2",
                                                       "stalemate": False}
        s.apply_rules_action_result(self.action("Suspend Judgment", targets=[{"kind": "player", "playerId": "p1"}]))
        self.assertEqual(stolen.get("holdUntilResolution"), 3)
        self.assertNotIn("holdUntilResolution", losing)

    def test_revive_put_queues_the_returning_manifestations_enter_field_effect(self):
        s = self.world()
        seeker = self.cid("Keen-eyed Seeker")
        self.put(s, "p1", "graveyard", [seeker])
        self.put(s, "p1", "deck", ["m2"])
        action = self.action("Revive", targets=[{
            "kind": "zone_card", "containerId": "p1", "ownerId": "p1",
            "zone": "graveyard", "cardId": seeker}])
        action.update(sourceOnStack=True, kind="play_card")
        action["source"].update(zone="hand", cardType="ephemeral_will")
        s.rules_engine["actionStack"] = [action]
        s.resolve_rules_top_action()
        self.assertEqual(len(s.battlefield), 1)
        self.assertEqual(s.battlefield[0]["fieldZone"], "interzone")
        self.assertEqual(len(s.rules_engine["actionStack"]), 1,
                         "Putting Seeker from Limbo onto field must queue its draw ETB")
        s.resolve_rules_top_action()
        self.assertEqual(s.players["p1"]["zones"]["hand"], ["m2"])

    def test_revive_entry_watchers_fire_once_and_put_is_not_a_card_play(self):
        s = self.world()
        blossom = self.field(s, self.cid("Intoxicating Blossom"), "blossom", zone="field")
        welcome = self.field(s, self.cid("Atavic Welcome"), "welcome", zone="field")
        self.field(s, self.cid("Callus, the Thought-stirrer"), "callus", zone="interzone")
        seeker = self.cid("Keen-eyed Seeker")
        self.put(s, "p1", "graveyard", [seeker])
        self.put(s, "p1", "deck", ["m2", "m3"])
        action = self.action("Revive", targets=[{
            "kind": "zone_card", "containerId": "p1", "ownerId": "p1",
            "zone": "graveyard", "cardId": seeker}])
        action.update(sourceOnStack=True, kind="play_card")
        action["source"].update(zone="hand", cardType="ephemeral_will")
        s.rules_engine["actionStack"] = [action]
        s.resolve_rules_top_action()
        pending = s.rules_engine["pendingChoice"]
        self.assertEqual(pending["kind"], "simultaneous_stack_order")
        self.assertEqual(len(pending["_group"]), 2, "one Seeker ETB and one Blossom watcher")
        error, _ = s.resolve_rules_choice("p1", pending["id"],
            card_ids=[a["id"] for a in pending["_group"]])
        self.assertIsNone(error)
        while s.rules_engine["actionStack"]:
            s.resolve_rules_top_action()
        self.assertEqual(s.players["p1"]["zones"]["hand"], ["m2"])
        self.assertEqual(blossom["counters"].get("Petal"), 1)
        self.assertEqual(welcome["counters"].get("Union", 0), 0)

    def test_chabak_owner_chooses_bottom_order_without_top_destination(self):
        s = self.world()
        host = self.field(s, self.cid("Chabak, the Ungrateful"))
        self.field(s, "m2", "enemy-a", owner="p2")
        self.field(s, "m3", "enemy-b", owner="p2", support=True)
        self.put(s, "p2", "deck", ["m4"])
        s.apply_rules_action_result(self.action("Chabak, the Ungrateful", host,
            ability_id="chabak-returns-opposing-manifestations-and-exiles-itself"))
        pending = s.rules_engine["pendingChoice"]
        self.assertEqual(pending["playerId"], "p2")
        bad = {"groups": [{"playerId": "p2", "top": ["m3"], "bottom": ["m2"]}]}
        self.assertIsNotNone(s.resolve_rules_choice("p2", pending["id"], option=bad)[0])
        good = {"groups": [{"playerId": "p2", "top": [], "bottom": ["m3", "m2"]}]}
        error, _ = s.resolve_rules_choice("p2", pending["id"], option=good)
        self.assertIsNone(error)
        self.assertEqual(s.players["p2"]["zones"]["deck"], ["m4", "m3", "m2"])
        self.assertIn(host["cardId"], s.players["p1"]["zones"]["exile"])

    def test_jurat_end_turn_return_includes_tributes_paid_after_its_win_effect(self):
        s = self.world()
        jurat = self.field(s, self.cid("Jurat, the Strategist"))
        self.put(s, "p1", "graveyard", ["m2", "m3"])
        s.rules_engine["tributeLog"] = [
            {"turn": 2, "playerId": "p1", "ownerId": "p1", "cardId": "m2"}]
        s.apply_rules_action_result(self.action("Jurat, the Strategist", jurat))
        # The End Phase permits more Wills/tributes after the on-win effect resolved.
        s.rules_engine["tributeLog"].append(
            {"turn": 2, "playerId": "p1", "ownerId": "p1", "cardId": "m3"})
        s.phase_tracker["index"] = ADVANCED_PHASES.index("end_actions")
        actions = s.queue_rules_end_turn_memory_triggers(defer=True)
        returned = set()
        for action in actions:
            result = s.apply_rules_action_result(action)
            returned.update(s.players["p1"]["zones"]["hand"])
        self.assertEqual(returned, {"m2", "m3"})

    def test_advocate_simultaneous_chain_keeps_first_choice_hidden_until_second_choice(self):
        s = self.world()
        advocate = self.field(s, self.cid("Advocate of Catharsis"))
        self.put(s, "p1", "hand", ["m2"])
        self.put(s, "p2", "hand", ["m3"])
        s.apply_rules_action_result(self.action("Advocate of Catharsis", advocate))
        choice = s.rules_engine["pendingChoice"]
        self.assertEqual(choice["playerId"], "p1")
        error, result = s.resolve_rules_choice("p1", choice["id"], card_ids=["m2"])
        self.assertIsNone(error)
        self.assertNotIn("cardId", result)
        self.assertEqual(s.players["p1"]["zones"]["hand"], ["m2"])
        self.assertNotIn("'m2'", repr(s.serialize_for("p2", "player")))
        s.resolve_rules_chain_sequences()
        # A face-up field entry reveals p1's selection before p2 commits.
        self.assertFalse(any(i.get("cardId") == "m2" and i.get("faceUp")
                             for i in s.battlefield))
        choice = s.rules_engine["pendingChoice"]
        self.assertEqual(choice["playerId"], "p2")
        error, _result = s.resolve_rules_choice("p2", choice["id"], card_ids=["m3"])
        self.assertIsNone(error)
        self.assertCountEqual([i["cardId"] for i in s.battlefield if i is not advocate], ["m2", "m3"])
        # Before either entry, p2 has zero CZ power versus Advocate's five.
        # The captured losing player's Chain enters first, irrespective chooser order.
        self.assertEqual([i["cardId"] for i in s.battlefield if i is not advocate], ["m3", "m2"])

    def test_advocate_queues_both_enter_field_effects_after_both_commitments(self):
        s = self.world()
        source = self.field(s, self.cid("Advocate of Catharsis"))
        seeker = self.cid("Keen-eyed Seeker")
        self.put(s, "p1", "hand", [seeker])
        self.put(s, "p2", "hand", [seeker])
        s.apply_rules_action_result(self.action("Advocate of Catharsis", source))
        first = s.rules_engine["pendingChoice"]
        self.assertIsNone(s.resolve_rules_choice("p1", first["id"], card_ids=[seeker])[0])
        self.assertEqual(s.rules_engine["actionStack"], [])
        self.assertEqual(s.battlefield, [source])
        second = s.rules_engine["pendingChoice"]
        self.assertIsNone(s.resolve_rules_choice("p2", second["id"], card_ids=[seeker])[0])
        self.assertEqual(len(s.battlefield), 3)
        self.assertEqual(len(s.rules_engine["actionStack"]), 2)
        self.assertEqual({a["controllerId"] for a in s.rules_engine["actionStack"]}, {"p1", "p2"})

    def test_advocate_delays_unable_hand_proof_until_able_player_commits(self):
        s = self.world()
        source = self.field(s, self.cid("Advocate of Catharsis"))
        self.put(s, "p1", "hand", ["m2"])
        self.put(s, "p2", "hand", ["w2"])
        result = s.apply_rules_action_result(self.action("Advocate of Catharsis", source))
        self.assertNotIn("handProofs", result)
        choice = s.rules_engine["pendingChoice"]
        error, result = s.resolve_rules_choice("p1", choice["id"], card_ids=["m2"])
        self.assertIsNone(error)
        self.assertEqual(result["handProofs"], [{"playerId": "p2", "cardIds": ["w2"]}])

    def test_ordinary_first_stone_chain_still_enters_on_single_selection(self):
        s = self.world()
        source = self.field(s, self.cid("First Stone"))
        self.put(s, "p2", "hand", ["m3"])
        s.apply_rules_action_result(self.action("First Stone", source))
        choice = s.rules_engine["pendingChoice"]
        self.assertEqual(choice["playerId"], "p2")
        error, result = s.resolve_rules_choice("p2", choice["id"], card_ids=["m3"])
        self.assertIsNone(error)
        self.assertEqual(result["status"], "chained")
        self.assertEqual(s.battlefield[-1]["cardId"], "m3")

    def test_pinpia_and_gar_fild_create_exact_retained_white_essence(self):
        for name, expected in (("Pinpia Psychobulb", 3), ("Gar Fild, the Malleable", 4)):
            with self.subTest(card=name):
                s = self.world()
                source = self.field(s, self.cid(name))
                for n in range(3):
                    self.field(s, "m2", f"inter-{n}", zone="interzone")
                s.apply_rules_action_result(self.action(name, source))
                self.assertEqual(sum(t["counters"]["essence"] for t in s.tokens), expected)
                self.assertTrue(all(t["temperament"] == "transcendent" and t["expiresTurn"] == 0 for t in s.tokens))
                s.expire_rules_excess_essence(2)
                self.assertEqual(sum(t["counters"]["essence"] for t in s.tokens), expected)

    def test_incubator_counts_current_controller_and_requires_interzone(self):
        for zone, expected in (("interzone", 1), ("confrontation", 0)):
            with self.subTest(zone=zone):
                s = self.world()
                self.field(s, self.cid("Spontaneous Incubator"), owner="p1", controller="p2", zone=zone)
                actions = s.queue_rules_beginning_turn_triggers(defer=True)
                self.assertEqual(len(actions), expected)
                for action in actions:
                    s.apply_rules_action_result(action)
                self.assertEqual(s.players["p2"]["score"], 60 if expected else 50)
                self.assertEqual(s.players["p1"]["score"], 50)

    def test_reap_counts_shared_manifestations_but_occupied_spaces_once(self):
        s = self.world()
        self.field(s, "m2", "slot-one", zone="interzone")
        shared = self.field(s, "m3", "shared", zone="interzone")
        shared["stackedOn"] = "slot-one"
        self.field(s, "m4", "slot-two", zone="interzone")
        self.put(s, "p1", "deck", ["m2", "m3", "m4"])
        s.apply_rules_action_result(self.action("Reap What You\u2019ve Sown"))
        self.assertEqual(s.players["p1"]["score"], 65)
        self.assertEqual(s.players["p1"]["zones"]["hand"], ["m2"])

    def test_shattering_counts_only_manifestations_actually_discarded(self):
        s = self.world()
        target = self.field(s, "m4", "victim", owner="p2")
        self.put(s, "p1", "deck", ["m2", "w2", "m3", "m4"])
        s.apply_rules_action_result(self.action("Shattering the Self", targets=[
            {"kind": "player", "playerId": "p1"}, self.target(target)]))
        self.assertEqual(s.rules_manifestation_characteristics(target)["power"], 2)
        self.assertEqual(s.players["p1"]["zones"]["deck"], ["m4"])
        self.assertCountEqual(s.players["p1"]["zones"]["graveyard"], ["m2", "w2", "m3"])

    def test_tong_and_cozy_bunk_add_capacity_and_stop_after_leaving(self):
        for name, expected in (("Tong, the Expansive", 6), ("Cozy Bunk", 4)):
            with self.subTest(card=name):
                s = self.world()
                source = self.field(s, self.cid(name),
                    zone="interzone" if name == "Tong, the Expansive" else "field")
                self.assertEqual(s.rules_interzone_capacity("p1"), expected)
                self.assertEqual(s.rules_interzone_capacity("p2"), 3)
                s.battlefield.remove(source)
                self.assertEqual(s.rules_interzone_capacity("p1"), 3)

    def test_consult_puts_slumberer_without_chaining_and_discards_prior_wills(self):
        s = self.world()
        slumberer = self.cid("The Slumberer")
        self.put(s, "p2", "deck", ["w2", "pw3", slumberer, "m2"])
        s.apply_rules_action_result(self.action("Consult", targets=[{"kind": "player", "playerId": "p2"}]))
        self.assertCountEqual(s.players["p2"]["zones"]["graveyard"], ["w2", "pw3"])
        self.assertEqual(s.players["p2"]["zones"]["deck"], ["m2"])
        self.assertEqual(len(s.battlefield), 1)
        entered = s.battlefield[0]
        self.assertEqual((entered["cardId"], entered["controllerId"], entered["isSupport"]),
                         (slumberer, "p2", True))

    def test_yzzit_d6_parity_replaces_vessel_entry_before_scoring(self):
        for roll in range(1, 7):
            with self.subTest(roll=roll):
                s = self.world()
                yzzit = self.field(s, self.cid("Yzzit, the Gambler"), support=True)
                with patch("game.confrontation.random.randint", return_value=roll):
                    s._rules_remove_field_item(yzzit, "p2", "receptacle", "top")
                if roll % 2:
                    self.assertEqual(s.players["p1"]["zones"]["hand"], [yzzit["cardId"]])
                    self.assertEqual(s.players["p2"]["zones"]["receptacle"], [])
                else:
                    self.assertEqual(s.players["p2"]["zones"]["receptacle"], [yzzit["cardId"]])
                    self.assertEqual(s.players["p1"]["zones"]["hand"], [])

    def test_field_watchers_enforce_printed_event_player_and_zone_conditions(self):
        # Table entries are original-text conditions, not enumerated encoded triggers.
        cases = [
            ("Callus, the Thought-stirrer", "will_played", "interzone", "p1", 1),
            ("Callus, the Thought-stirrer", "will_played", "interzone", "p2", 0),
            ("Callus, the Thought-stirrer", "will_played", "confrontation", "p1", 0),
            ("Shuk, the Bile-filled", "points_lost", "interzone", "p1", 1),
            ("Shuk, the Bile-filled", "points_lost", "interzone", "p2", 0),
            ("Shuk, the Bile-filled", "points_lost", "confrontation", "p1", 0),
            ("Forfog, the Hanged", "cards_discarded", "interzone", "p2", 1),
            ("Forfog, the Hanged", "cards_discarded", "interzone", "p1", 0),
            ("Forfog, the Hanged", "cards_discarded", "confrontation", "p2", 0),
            ("Pale Entity", "points_lost", "interzone", "p1", 1),
            ("Pale Entity", "points_lost", "interzone", "p2", 1),
            ("Pale Entity", "cards_discarded", "interzone", "p1", 1),
            ("Pale Entity", "cards_discarded", "interzone", "p2", 1),
            ("Pale Entity", "cards_discarded", "confrontation", "p2", 0),
            ("Blue Entity", "will_played", "confrontation", "p1", 1),
            ("Blue Entity", "will_played", "confrontation", "p2", 0),
            ("Blue Entity", "will_played", "interzone", "p1", 0),
        ]
        for name, event, zone, event_controller, expected in cases:
            with self.subTest(card=name, event=event, zone=zone, player=event_controller):
                s = self.world()
                source = self.field(s, self.cid(name), zone=zone)
                actions = s.queue_rules_triggers(source["cardId"], "p1", event,
                    item_id="source", zone=zone, face_up=True, controller_id="p1",
                    event_controller_id=event_controller, defer=True)
                self.assertEqual(len(actions), expected)

    def test_pale_shuk_and_forfog_have_exact_five_point_outputs(self):
        for name, event, event_controller, expected_p1, expected_p2 in (
                ("Pale Entity", "cards_discarded", "p2", 55, 50),
                ("Pale Entity", "points_lost", "p1", 55, 50),
                ("Shuk, the Bile-filled", "points_lost", "p1", 50, 45),
                ("Forfog, the Hanged", "cards_discarded", "p2", 50, 45)):
            with self.subTest(card=name, event=event):
                s = self.world()
                source = self.field(s, self.cid(name), zone="interzone")
                actions = s.queue_rules_triggers(source["cardId"], "p1", event,
                    item_id="source", zone="interzone", face_up=True,
                    controller_id="p1", event_controller_id=event_controller, defer=True)
                self.assertEqual(len(actions), 1)
                s.apply_rules_action_result(actions[0])
                self.assertEqual((s.players["p1"]["score"], s.players["p2"]["score"]),
                                 (expected_p1, expected_p2))

    def test_flower_tender_requires_another_current_power_two_or_less_in_cz(self):
        s = self.world()
        flower = self.field(s, self.cid("Flower Tender"))
        target = self.field(s, "m2", "target")
        action = self.action("Flower Tender", flower, [self.target(target)])
        contract = action["ability"]["targets"]
        self.assertIsNone(s.rules_ability_targets_error(contract, action["targets"], "p1", event_item_id="source"))
        target["counters"]["power"] = 1
        self.assertIsNotNone(s.rules_ability_targets_error(contract, action["targets"], "p1", event_item_id="source"))
        target["counters"] = {}
        s.create_rules_ongoing_effects(action)
        self.assertEqual(s.rules_manifestation_characteristics(target)["power"], 4)
        self.assertIsNotNone(s.rules_ability_targets_error(contract, [self.target(flower)], "p1", event_item_id="source"))

    def test_mobile_sanctuary_does_not_protect_itself_or_interzone(self):
        s = self.world()
        source = self.field(s, self.cid("Mobile Sanctuary"))
        own = self.field(s, "m2", "own")
        inter = self.field(s, "m3", "inter", zone="interzone")
        self.assertFalse(s.rules_item_is_protected(source, "p2"))
        self.assertTrue(s.rules_item_is_protected(own, "p2"))
        self.assertFalse(s.rules_item_is_protected(inter, "p2"))
        self.assertFalse(s.rules_item_is_protected(own, "p1"))
        s.battlefield.remove(source)
        self.assertFalse(s.rules_item_is_protected(own, "p2"))

    def test_gargullo_non_token_support_bonus_excludes_tokens_from_both_sides(self):
        s = self.world()
        self.field(s, self.cid("Gargullo, King of the Woods"), "first")
        a = self.field(s, "m2", "a", support=True)
        self.field(s, "m3", "b", support=True)
        token = self.field(s, "m2", "token", support=True)
        token.update(isTokenCard=True, power=1, temperament="phlegmatic")
        self.field(s, "m4", "enemy", owner="p2", support=True)
        self.assertEqual(s.rules_manifestation_characteristics(a)["power"], 4)
        self.assertEqual(s.rules_manifestation_characteristics(token)["power"], 1)

    def test_heartening_and_herbaceous_aura_scope_and_removal(self):
        for name, expected_first, expected_support in (
                ("Heartening Monument", 3, 4), ("Herbaceous Whisperer", 2, 4)):
            with self.subTest(card=name):
                s = self.world()
                source = self.field(s, self.cid(name),
                    zone="interzone" if name == "Herbaceous Whisperer" else "field")
                first = self.field(s, "m2", "first")
                support = self.field(s, "m3", "support", support=True)
                enemy = self.field(s, "m4", "enemy", owner="p2", support=True)
                self.assertEqual(s.rules_manifestation_characteristics(first)["power"], expected_first)
                self.assertEqual(s.rules_manifestation_characteristics(support)["power"], expected_support)
                self.assertEqual(s.rules_manifestation_characteristics(enemy)["power"], 4)
                s.battlefield.remove(source)
                self.assertEqual(s.rules_manifestation_characteristics(support)["power"], 3)

    def test_timid_brain_paid_discard_plays_it_as_support_without_stale_permission(self):
        s = self.world()
        brain = self.cid("Timid Brain")
        self.put(s, "p1", "hand", [brain, "w2"])
        s.rules_engine["priorityPlayerId"] = "p1"
        error, _ = s.declare_rules_action("p1", "Timid Brain", kind="activated_effect",
            source={"cardId": brain, "zone": "hand"},
            ability_id="timid-brain-discard-will-for-support", cost_card_id="w2")
        self.assertIsNone(error)
        self.assertEqual(s.players["p1"]["zones"]["graveyard"], ["w2"])
        self.assertEqual(len(s.resolve_rules_immediate_actions()), 1)
        self.assertNotIn(brain, s.players["p1"]["zones"]["hand"])
        self.assertEqual(s.rules_engine["playPermissions"], [])
        self.assertEqual(len(s.rules_engine["actionStack"]), 1)
        play = s.rules_engine["actionStack"][0]
        self.assertEqual((play["kind"], play["asSupport"], play["source"]["cardId"]),
                         ("play_card", True, brain))
        self.assertEqual(play["cost"]["tributeCardIds"], [])
        self.assertEqual(play["cost"]["essenceSpent"], [])
        self.assertEqual(s.rules_engine["priorityPlayerId"], "p2")
        s.resolve_rules_top_action()
        entered = next(i for i in s.battlefield if i["cardId"] == brain)
        self.assertTrue(entered["isSupport"])
        self.assertEqual(entered["fieldZone"], "confrontation")
        self.assertEqual(s.players["p1"]["score"], 50)

    def test_timid_brain_respects_support_play_lock_and_leaves_no_permission(self):
        s = self.world()
        brain = self.cid("Timid Brain")
        self.put(s, "p1", "hand", [brain, "w2"])
        s.rules_engine["supportLocks"] = [{"turn": 2, "playerId": None, "playOnly": True}]
        s.rules_engine["priorityPlayerId"] = "p1"
        error, _ = s.declare_rules_action("p1", "Timid Brain", kind="activated_effect",
            source={"cardId": brain, "zone": "hand"},
            ability_id="timid-brain-discard-will-for-support", cost_card_id="w2")
        self.assertIsNone(error)
        resolved = s.resolve_rules_immediate_actions()
        self.assertEqual(resolved[0]["action"]["effectResult"]["status"], "prevented")
        self.assertIn(brain, s.players["p1"]["zones"]["hand"])
        self.assertEqual(s.rules_engine["playPermissions"], [])
        self.assertEqual(s.rules_engine["actionStack"], [])
        self.assertEqual(s.battlefield, [])

    def test_timid_brain_source_must_still_be_in_hand_at_resolution(self):
        s = self.world()
        brain = self.cid("Timid Brain")
        self.put(s, "p1", "hand", [brain])
        action = self.action("Timid Brain")
        action["source"]["zone"] = "hand"
        s.take_zone_card("p1", "hand", brain)
        s.put_zone_card("p1", "graveyard", brain, "p1")
        result = s.apply_rules_action_result(action)
        self.assertEqual(result["status"], "source_missing")
        self.assertEqual(s.rules_engine["playPermissions"], [])
        self.assertEqual(s.rules_engine["actionStack"], [])


if __name__ == "__main__":
    unittest.main()
