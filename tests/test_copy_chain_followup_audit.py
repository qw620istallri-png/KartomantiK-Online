import copy
import test_game_state as game_tests


class CopyChainFollowupAuditTests(game_tests.RealCardRulesCase):
    MIRROR = "0e7afy7zmyhbfal_en"
    SLUMBER = "nlbgn1ranlrd09r_en"
    JUGGERNUT = "inner-deserts-100"
    UROLONG = "pekwxpsy3c0ro3l_en"
    MECHANISM = "inner-deserts-093"
    ALL = (MIRROR, SLUMBER, JUGGERNUT, UROLONG, MECHANISM)

    def started(self):
        session, p1, p2 = self.make_session()
        session.phase_tracker["index"] = game_tests.ADVANCED_PHASES.index("confrontation_reaction")
        session.rules_engine.update(readyPlayerIds=["p1", "p2"], firstManifestationComplete=True, priorityPlayerId="p1")
        return session, p1, p2

    def mirror(self):
        session, _, _ = self.started()
        session.card_rules["m-0"].update(power=4, float=True, activatedAbilities=[{
            "id": "copied-activation", "targets": {"min": 0, "max": 0},
            "result": {"kind": "score_owner", "value": 1},
        }])
        mirror = self.field_item("mirror", "p1", self.MIRROR)
        target = self.field_item("original", "p2", "m-0")
        session.battlefield = [mirror, target]
        session.create_rules_ongoing_effects({
            "id": "copy", "controllerId": "p1", "source": {"cardId": self.MIRROR, "itemId": "mirror"},
            "targets": [{"kind": "card", "itemId": "original", "cardId": "m-0"}],
            "ability": self.ability(self.MIRROR, "mirrorbeast-copy-power-and-effects"),
        })
        return session, mirror, target

    def test_mirrorbeast_freezes_power_and_copied_effects_when_copy_resolves(self):
        session, mirror, target = self.mirror()
        target["counters"]["power"] = 3
        session.card_rules["m-1"]["activatedAbilities"] = [{"id": "later-activation"}]
        target["gummoCopy"] = "m-1"
        self.assertEqual(session.rules_manifestation_characteristics(mirror)["power"], 4)
        self.assertEqual([a["id"] for a in session.rules_item_card_rules(mirror)["activatedAbilities"]], ["copied-activation"])

    def test_mirrorbeast_keeps_copy_after_original_leaves_and_expires_at_resolution(self):
        session, mirror, target = self.mirror()
        session._rules_remove_field_item(target, "p2", "graveyard")
        session.prune_rules_ongoing_effects()
        self.assertEqual(session.rules_manifestation_characteristics(mirror)["power"], 4)
        self.assertTrue(session.rules_item_has_float(mirror))
        self.assertEqual(session.rules_item_card_rules(mirror)["activatedAbilities"][0]["id"], "copied-activation")
        session.phase_tracker["index"] = game_tests.ADVANCED_PHASES.index("end_actions")
        session.prune_rules_ongoing_effects()
        self.assertFalse(session.rules_item_card_rules(mirror).get("activatedAbilities"))

    def test_persistent_only_manifestations_are_not_chain_candidates_in_any_zone(self):
        for cid in (self.SLUMBER, self.JUGGERNUT):
            for zone in ("hand", "deck", "graveyard", "receptacle"):
                with self.subTest(card=cid, zone=zone):
                    session, p1, p2 = self.started()
                    container = p2 if zone == "receptacle" else p1
                    self.put(container, zone, {cid: "p1", "m-0": "p1"})
                    self.assertEqual(session.rules_chain_candidates("p1", zone), {"m-0": container["id"]})
                    before = copy.deepcopy(container["zones"])
                    error, _ = session.chain_rules_manifestation("p1", zone, cid, container_id=container["id"])
                    self.assertIsNotNone(error)
                    self.assertEqual(container["zones"], before)
                    self.assertFalse(session.battlefield)

    def test_rejected_chain_choice_does_not_discard_the_pending_choice(self):
        session, p1, _ = self.started()
        self.put(p1, "hand", [self.SLUMBER])
        choice = {"id": "chain", "kind": "chain_manifestation", "playerId": "p1", "controllerId": "p1",
                  "fromZone": "hand", "_cardIds": [self.SLUMBER]}
        session.rules_engine["pendingChoice"] = choice
        error, _ = session.resolve_rules_choice("p1", "chain", card_ids=[self.SLUMBER])
        self.assertIsNotNone(error)
        self.assertEqual(session.rules_engine["pendingChoice"], choice)
        self.assertEqual(p1["zones"]["hand"], [self.SLUMBER])

    def test_womb_uses_its_fallback_when_the_revealed_hand_cannot_chain(self):
        session, _, p2 = self.started()
        self.put(p2, "hand", [self.SLUMBER, self.JUGGERNUT])
        session.rules_engine["pendingChoice"] = {
            "id": "show", "kind": "binary_choice", "purpose": "womb_show",
            "playerId": "p2", "controllerId": "p1", "options": ["yes", "no"],
        }
        error, result = session.resolve_rules_choice("p2", "show", option="yes")
        self.assertIsNone(error)
        self.assertEqual(result["status"], "tokens")
        self.assertEqual(len(session.battlefield), 2)
        self.assertTrue(all(item.get("isTokenCard") for item in session.battlefield))
        self.assertIsNone(session.rules_engine["pendingChoice"])
        self.assertEqual(p2["zones"]["hand"], [self.SLUMBER, self.JUGGERNUT])

    def test_urolong_still_puts_persistent_only_manifestations_into_support(self):
        for cid in (self.SLUMBER, self.JUGGERNUT):
            with self.subTest(card=cid):
                session, p1, _ = self.started()
                self.put(p1, "graveyard", [cid])
                session.battlefield = [self.field_item("urolong", "p1", self.UROLONG, "interzone")]
                session.add_rules_excess_essence("p1", [{"temperament": "hollow", "amount": 2}])
                error, _ = session.declare_rules_action(
                    "p1", "Urolong", kind="activated_effect", source={"cardId": self.UROLONG, "zone": "battlefield", "itemId": "urolong"},
                    ability_id=self.ABILITIES[self.UROLONG][0]["id"],
                    targets=[{"kind": "zone_card", "containerId": "p1", "ownerId": "p1", "zone": "graveyard", "cardId": cid}],
                )
                self.assertIsNone(error)
                session.resolve_rules_top_action()
                placed = next(item for item in session.battlefield if item["cardId"] == cid)
                self.assertTrue(placed["isSupport"])
                self.assertTrue(placed["effectsDisabled"])
                self.assertFalse(session.rules_engine["actionStack"])

    def test_mechanism_counter_condition_controls_usable_activations(self):
        for count in range(5):
            with self.subTest(count=count):
                session, p1, _ = self.started()
                self.put(p1, "hand", ["m-0"])
                item = self.field_item("mechanism", "p1", self.MECHANISM, "field", counters={"Enigma": count})
                session.battlefield = [item]
                usable = [a["id"] for a in session.card_rules[self.MECHANISM]["activatedAbilities"]
                          if session.rules_field_ability_usable(item, a, "field", "confrontation_reaction")]
                expected = [] if count in (0, 4) else [self.ABILITIES[self.MECHANISM][count]["id"]]
                self.assertEqual(usable, expected)
