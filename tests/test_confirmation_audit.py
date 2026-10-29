"""Regression cases from the 139.2.1 trigger/confirmation audit."""
import copy
import itertools

import test_game_state as game_tests
from session import ADVANCED_PHASES


class ConfirmationAuditTests(game_tests.RealCardRulesCase):
    INTROSPECTION = "265f4wdooq43pjn_en"
    TUT = "inner-deserts-037"
    MEMENTO = "inner-deserts-063"
    REFEREN = "inner-deserts-038"
    ZOMBIE = "bu1y6jwy7iaywqu_en"
    SHABABBA = "i7h2c7ku2gt1yvg_en"
    LOOP = "1a8wzhi7xhbcenj_en"
    CORAL = "qn8r98kyqqma972_en"
    CARCASS = "zh4rjhzon9qes6m_en"
    NUMBI = "wer3o71zo9myece_en"
    FREENYA = "b6ebpyb30urtas2_en"
    # Resource is the minimum useful input for the optional effect.
    OPTIONALS = (
        ("wx7y64eaa0wlvuk_en", "ready"),       # Melancholic Mirror
        ("ze99bj8uw2oisfx_en", "hand"),        # Alchemical Press
        ("ydijk2x1ne8w93g_en", "limbo"),       # Mind Parasite
        ("a058t24med4h5nx_en", "hand"),        # Atavic Oppression
        (CARCASS, "limbo"),                    # Carcass Devourer
        ("inner-deserts-111", "manifestation"),
        ("201ug66mqu6gslx_en", "will"),        # Quorum
        ("nt0bixroxp0ftnk_en", "manifestation"),
        ("inner-deserts-061", "chain_vessel"),
        ("qapv47r7rz6gqah_en", "will"),        # Ju Lien
        ("fw18tebi26jwiqb_en", "two_manifestations"),
        ("gz2zjrxqc2rbcwq_en", "will"),        # Bullyboo
        ("hcgvp7lbadlng1h_en", "vessel"),      # Gummo
        ("9bkn03sc9veaa88_en", "manifestation"),
        ("inner-deserts-083", "manifestation"),
    )
    ALL = (INTROSPECTION, TUT, MEMENTO, REFEREN, ZOMBIE, SHABABBA, LOOP, CORAL, CARCASS, NUMBI, FREENYA) + tuple(
        cid for cid, _ in OPTIONALS
    )

    def started(self, phase="confrontation_reaction"):
        session, p1, p2 = self.make_session()
        session.rules_engine.update(readyPlayerIds=["p1", "p2"], firstManifestationComplete=True,
                                    priorityPlayerId="p1", actionStack=[], pendingChoice=None)
        session.phase_tracker["index"] = ADVANCED_PHASES.index(phase)
        return session, p1, p2

    def prepare_trigger(self, card_id, ability_id=None):
        session, p1, p2 = self.started()
        ability = next(a for a in self.ABILITIES[card_id]
                       if a.get("optional") and (ability_id is None or a["id"] == ability_id))
        trigger = ability["trigger"]
        event = trigger["event"]
        phase = {"end_of_turn": "end_triggers", "beginning_of_turn": "recovery_start",
                 "reaction": "confrontation_reaction"}.get(event, "resolution_effects" if "confrontation" in event else "confrontation_reaction")
        session.phase_tracker["index"] = ADVANCED_PHASES.index(phase)
        source = self.field_item("source", "p1", card_id, trigger.get("zone") or "confrontation", rotation=0)
        for constraint, bound in [("sourceCounterMin", "min"), ("sourceCounterMax", "max")]:
            if trigger.get(constraint):
                gate = trigger[constraint]
                source["counters"][gate["name"]] = gate.get(bound, 0)
        session.battlefield = [source, self.field_item("target", "p2", "m-5")]
        session.rules_engine["confrontationResult"] = {
            "turn": session.phase_tracker["turn"], "winnerId": "p1", "loserId": "p2",
            "participantItemIds": ["source", "target"],
        }
        return session, p1, p2, source, ability

    def queue(self, session, source, ability):
        trigger = ability["trigger"]
        event = trigger["event"]
        zone = source["fieldZone"]
        if event in {"enters_limbo", "discarded"}:
            session.battlefield.remove(source)
            session.put_zone_card("p1", "graveyard", source["cardId"], "p1", "top")
            zone = "graveyard"
        return session.queue_rules_triggers(
            source["cardId"], "p1", event, zone=zone,
            item_id="source" if source in session.battlefield else None,
            controller_id="p1", container_id="p1", face_up=True,
            event_item_id="source", event_controller_id="p2" if trigger.get("eventController") == "opponent" else "p1",
            related_action={"id": "related", "source": {"cardId": "m-0", "ownerId": "p1", "zone": "hand"}},
            event_card_id="m-0", event_source_zone="hand", played=True, first_will_of_turn=True,
            abilities_override=[ability],
        )

    def accept(self, session):
        choice = session.rules_engine["pendingChoice"]
        self.assertEqual(choice["kind"], "optional_stack_action")
        error, _ = session.resolve_rules_choice("p1", choice["id"], option="accept")
        self.assertIsNone(error)

    def select(self, session, cards):
        choice = session.rules_engine["pendingChoice"]
        self.assertEqual(choice["kind"], "trigger_targets")
        error, _ = session.resolve_rules_choice("p1", choice["id"], targets=[{
            "kind": "zone_card", "containerId": "p1", "zone": "graveyard", "cardId": cid,
        } for cid in cards])
        self.assertIsNone(error)

    def test_optional_effects_skip_empty_inputs_but_keep_real_choices(self):
        for card_id, resource in self.OPTIONALS:
            for available in [False, True]:
                with self.subTest(card=card_id, available=available):
                    session, p1, p2, source, ability = self.prepare_trigger(card_id)
                    if resource == "ready":
                        source["rotation"] = 0 if available else 90
                    elif resource in {"will", "hand"}:
                        self.put(p1, "hand", ["will-x"] if available else ([] if resource == "hand" else ["m-0"]))
                    elif resource in {"manifestation", "two_manifestations"}:
                        self.put(p1, "hand", (["m-0", "m-1"] if resource == "two_manifestations" else ["m-0"]) if available
                                 else (["m-0"] if resource == "two_manifestations" else ["will-x"]))
                    elif resource == "limbo":
                        self.put(p1, "graveyard", ["m-0"] if available else ["will-x"])
                    elif resource in {"vessel", "chain_vessel"}:
                        # Dol may Chain an owned card even in the other player's Vessel.
                        vessel = p2 if resource == "chain_vessel" else p1
                        self.put(vessel, "receptacle", {"m-0": "p1"} if available else {"will-x": "p1"})
                    self.queue(session, source, ability)
                    if not available:
                        self.assertIsNone(session.rules_engine["pendingChoice"])
                        self.assertFalse(session.rules_engine["actionStack"])
                        continue
                    self.accept(session)
                    choice = session.rules_engine["pendingChoice"]
                    if choice:
                        self.assertEqual(choice["kind"], "trigger_targets")
                        targets = ([{"kind": "zone_card", "containerId": "p1", "zone": "graveyard", "cardId": "m-0"}]
                                   if card_id == self.CARCASS else [{"kind": "card", "itemId": "target", "cardId": "m-5"}])
                        error, _ = session.resolve_rules_choice("p1", choice["id"], targets=targets)
                        self.assertIsNone(error)
                    effect = session.resolve_rules_top_action()["action"]["effectResult"]
                    self.assertNotIn(effect.get("status"), {"no_hand_card", "no_vessel_card", "no_eligible_card", "unavailable", "nothing"})

    def test_introspection_requires_two_available_limbo_cards(self):
        for count in [0, 1, 2]:
            with self.subTest(count=count):
                session, p1, _, source, ability = self.prepare_trigger(self.INTROSPECTION)
                self.put(p1, "graveyard", ["m-0", "will-x"][:count])
                self.queue(session, source, ability)
                if count < 2:
                    self.assertIsNone(session.rules_engine["pendingChoice"])
                    self.assertFalse(session.rules_engine["actionStack"])
                else:
                    self.accept(session)
                    self.select(session, ["m-0", "will-x"])
                    session.resolve_rules_top_action()
                    choice = session.rules_engine["pendingChoice"]
                    self.assertEqual(choice["kind"], "deck_reorder")
                    error, _ = session.resolve_rules_choice("p1", choice["id"], option={"groups": [{
                        "playerId": "p1", "top": ["m-0"], "bottom": ["will-x"],
                    }]})
                    self.assertIsNone(error)
                    self.assertEqual(p1["zones"]["deck"], ["m-0", "will-x"])

    def test_numbi_keeps_opponent_chain_and_hand_reveal_with_empty_controller_hand(self):
        for hand in [[], ["will-x"], ["m-0"]]:
            with self.subTest(hand=hand):
                session, p1, p2, source, ability = self.prepare_trigger(self.NUMBI)
                session.phase_tracker["index"] = ADVANCED_PHASES.index("confrontation_reveal")
                self.put(p2, "hand", hand)
                self.queue(session, source, ability)
                if not hand:
                    self.assertIsNone(session.rules_engine["pendingChoice"])
                    self.assertFalse(session.rules_engine["actionStack"])
                    continue
                self.accept(session)
                effect = session.resolve_rules_top_action()["action"]["effectResult"]
                choice = session.rules_engine["pendingChoice"]
                if hand == ["m-0"]:
                    self.assertEqual(choice["kind"], "chain_manifestation")
                    self.assertEqual(choice["playerId"], "p2")
                else:
                    self.assertIsNone(choice)
                    self.assertEqual(effect["handProof"], ["will-x"])

    def test_freenya_can_grant_a_later_permission_with_empty_limbo(self):
        session, p1, _, source, ability = self.prepare_trigger(self.FREENYA)
        source["fieldZone"] = "field"
        queued = session.queue_rules_triggers(self.FREENYA, "p1", "card_played", zone="field", item_id="source",
            controller_id="p1", event_controller_id="p1", event_card_id="will-x", event_source_zone="hand",
            played=True, abilities_override=[ability])
        self.assertEqual(len(queued), 1)
        self.accept(session)
        effect = session.resolve_rules_top_action()["action"]["effectResult"]
        self.assertEqual(effect["kind"], "grant_limbo_will_play")
        self.assertTrue(session.rules_engine["playPermissions"])

    def test_optional_limbo_targets_are_selected_before_stack_and_resolve(self):
        for card_id, candidates in [(self.MEMENTO, ["m-0", "will-x"]), (self.REFEREN, ["will-x"])]:
            for selected in [[], candidates[:1], candidates]:
                with self.subTest(card=card_id, selected=selected):
                    session, p1, _, source, ability = self.prepare_trigger(card_id)
                    self.put(p1, "graveyard", ["m-0", "will-x"])
                    self.queue(session, source, ability)
                    self.accept(session)
                    self.assertFalse(session.rules_engine["actionStack"])
                    self.select(session, selected)
                    self.assertIsNone(session.rules_engine["pendingChoice"])
                    self.assertEqual(session.rules_engine["priorityPlayerId"], "p2")
                    effect = session.resolve_rules_top_action()["action"]["effectResult"]
                    self.assertEqual(set(effect["cardIds"]), set(selected))
                    self.assertEqual(set(p1["zones"]["deck" if card_id == self.MEMENTO else "exile"]), set(selected))
                    if card_id == self.REFEREN and selected:
                        self.assertEqual(self.power_of(session, "source"), 1 + session.card_rules[card_id]["power"])

    def test_optional_limbo_targets_skip_when_no_eligible_card_and_reject_invalid_targets(self):
        for card_id in [self.MEMENTO, self.REFEREN, self.ZOMBIE]:
            session, p1, p2, source, ability = self.prepare_trigger(card_id)
            # An owned card in the opponent's Limbo is not in "your Limbo".
            self.put(p2, "graveyard", {"m-1": "p1", "will-x": "p1"})
            self.queue(session, source, ability)
            self.assertIsNone(session.rules_engine["pendingChoice"])
            self.assertFalse(session.rules_engine["actionStack"])
            # Wrong type for Referen; source itself for Memento and Zombieswing.
            invalid = "m-0" if card_id == self.REFEREN else card_id
            if card_id == self.REFEREN:
                self.put(p1, "graveyard", [invalid])
            error, clean = session.rules_action_targets([{
                "kind": "zone_card", "containerId": "p1", "zone": "graveyard", "cardId": invalid,
            }], "p1")
            self.assertIsNone(error)
            self.assertIsNotNone(session.rules_ability_targets_error(
                {**ability["targets"], "min": 1}, clean, "p1", source_card_id=card_id,
            ))

    def test_zombieswing_returns_another_manifestation(self):
        session, p1, _, source, ability = self.prepare_trigger(self.ZOMBIE)
        self.put(p1, "graveyard", ["m-0"])
        self.queue(session, source, ability)
        self.accept(session)
        choice = session.rules_engine["pendingChoice"]
        error, _ = session.resolve_rules_choice("p1", choice["id"], targets=[{
            "kind": "zone_card", "containerId": "p1", "zone": "graveyard", "cardId": self.ZOMBIE,
        }])
        self.assertIsNotNone(error)
        self.select(session, ["m-0"])
        self.assertEqual(session.resolve_rules_top_action()["action"]["effectResult"]["status"], "returned")
        self.assertIn("m-0", p1["zones"]["hand"])
        self.assertIn(self.ZOMBIE, p1["zones"]["graveyard"])

    def test_delayed_returns_skip_cards_that_already_left_limbo(self):
        for source_card in [self.LOOP, self.CORAL]:
            for zone in ["hand", "deck", "exile", "graveyard"]:
                with self.subTest(source=source_card, zone=zone):
                    session, p1, _ = self.started("end_triggers")
                    self.put(p1, zone, ["will-x"])
                    session.rules_engine["confrontationLosses"] = {str(session.phase_tracker["turn"]): "p1"}
                    session.create_rules_effect_memory("p1", "will-x", "return_from_limbo_end_turn", controller_id="p1",
                                                       data={"optional": True, "effectSourceCardId": source_card,
                                                             "requireLostConfrontation": source_card == self.LOOP})
                    queued = session.queue_rules_end_turn_memory_triggers()
                    if zone == "graveyard":
                        self.assertEqual(len(queued), 1)
                        self.accept(session)
                        session.resolve_rules_top_action()
                        self.assertIn("will-x", p1["zones"]["hand"])
                    else:
                        self.assertFalse(queued)
                        self.assertIsNone(session.rules_engine["pendingChoice"])
                        self.assertFalse(session.rules_engine["effectMemories"])

    def test_tut_reorder_remains_payable_and_valid_with_short_decks(self):
        for count in [0, 1, 2, 3]:
            with self.subTest(count=count):
                session, p1, _ = self.started()
                session.battlefield = [self.field_item("tut", "p1", self.TUT)]
                cards = ["m-0", "m-1", "m-2"][:count]
                self.put(p1, "deck", cards)
                session.add_rules_excess_essence("p1", [{"temperament": "hollow", "amount": 1}])
                error, action = session.declare_rules_action("p1", "Tut", kind="activated_effect",
                    source={"cardId": self.TUT, "zone": "battlefield", "itemId": "tut"}, ability_id=self.ABILITIES[self.TUT][0]["id"])
                self.assertIsNone(error)
                self.assertEqual(sum(t["amount"] for t in action["cost"]["essenceSpent"]), 1)
                session.resolve_rules_top_action()
                choice = session.rules_engine["pendingChoice"]
                if count < 2:
                    self.assertIsNone(choice)
                    self.assertEqual(p1["zones"]["deck"], cards)
                    continue
                group = choice["_groups"][0]
                self.assertEqual((group["topCount"], group["bottomCount"]), (count - 1, 1))
                valid = 0
                for order in itertools.permutations(cards):
                    clone = copy.deepcopy(session)
                    error, _ = clone.resolve_rules_choice("p1", choice["id"], option={"groups": [{
                        "playerId": "p1", "top": list(order[:-1]), "bottom": [order[-1]],
                    }]})
                    self.assertIsNone(error)
                    self.assertEqual(clone.players["p1"]["zones"]["deck"], list(order))
                    valid += 1
                self.assertEqual(valid, 2 if count == 2 else 6)

    def test_shababba_only_asks_when_the_deck_order_can_change(self):
        for count in [0, 1, 2, 4]:
            session, p1, _ = self.started("end_triggers")
            self.put(p1, "deck", [f"m-{i}" for i in range(count)])
            source = self.field_item("sh", "p1", self.SHABABBA, "interzone")
            session.battlefield = [source]
            session.queue_rules_triggers(self.SHABABBA, "p1", "end_of_turn", zone="interzone", item_id="sh", controller_id="p1")
            session.resolve_rules_top_action()
            choice = session.rules_engine["pendingChoice"]
            if count <= 1:
                self.assertIsNone(choice)
            else:
                self.assertEqual(choice["kind"], "deck_reorder")
