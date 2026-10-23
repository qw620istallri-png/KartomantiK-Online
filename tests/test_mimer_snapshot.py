import test_game_state as game_tests


class MimerSnapshotTests(game_tests.RealCardRulesCase):
    MIMER = "pwsjhnw4vpvqgkv_en"
    MASK = "1ixfmjkfewc0o42_en"
    BOB = "inner-deserts-134"
    ALL = (MIMER, MASK, BOB)

    def started(self):
        session, _, _ = self.make_session()
        session.rules_engine.update(readyPlayerIds=["p1", "p2"], firstManifestationComplete=True, priorityPlayerId="p1")
        session.phase_tracker["index"] = game_tests.ADVANCED_PHASES.index("confrontation_reaction")
        session.card_rules["m-0"].update(power=3, temperaments=["choleric"])
        mimer = self.field_item("mimer", "p1", self.MIMER, x=0, y=0, rotation=0)
        foe = self.field_item("foe", "p2", "m-0", x=200, y=0, rotation=0)
        session.battlefield = [mimer, foe]
        session.rules_engine["firstManifestationItemIds"] = {"p1": "mimer", "p2": "foe"}
        session.add_rules_excess_essence("p1", [{"temperament": "hollow", "amount": 3}])
        return session, mimer, foe

    def activate(self, session):
        session.rules_engine["priorityPlayerId"] = "p1"
        error, action = session.declare_rules_action(
            "p1", "Mimer", kind="activated_effect",
            source={"cardId": self.MIMER, "zone": "battlefield", "itemId": "mimer"},
            targets=[{"kind": "card", "itemId": "foe", "cardId": "m-0"}],
            ability_id="copy-first-manifestation",
        )
        self.assertIsNone(error)
        return action

    def mask(self, session, temperament):
        ability = self.ability(self.MASK, f"mask-becomes-{temperament}")
        session.create_rules_ongoing_effects({
            "id": f"mask-{temperament}", "controllerId": "p2", "source": {"cardId": self.MASK},
            "targets": [{"kind": "card", "itemId": "foe", "cardId": "m-0"}], "ability": ability,
        })

    def test_copies_at_resolution_then_ignores_later_mask_and_power_changes(self):
        session, mimer, foe = self.started()
        original = session.rules_manifestation_characteristics(mimer)
        self.activate(session)
        self.assertEqual(session.rules_manifestation_characteristics(mimer), original)
        self.mask(session, "vitreous")
        foe["counters"]["power"] = 2
        session.resolve_rules_top_action()
        expected = {"power": 5, "temperament": "vitreous"}
        self.assertEqual(session.rules_manifestation_characteristics(mimer), expected)
        self.mask(session, "melancholic")
        foe["counters"]["power"] = 6
        foe["baseDoublings"] = 1
        for _ in range(2):
            session.serialize_for("p1", "player")
            self.assertEqual(session.rules_manifestation_characteristics(mimer), expected)
            self.assertEqual(session.rules_manifestation_base_power(mimer), 3)
        view = session.serialize_for("p2", "player")
        copied_view = next(item for item in view["battlefield"] if item["id"] == "mimer")
        self.assertEqual(copied_view["effectiveTemperament"], "vitreous")

    def test_departure_cannot_refresh_copy_even_without_an_intermediate_view(self):
        for removal in ("graveyard", "suspend"):
            with self.subTest(removal=removal):
                session, mimer, foe = self.started()
                self.activate(session)
                session.resolve_rules_top_action()
                foe["counters"]["power"] = 5
                foe["temperamentOverride"] = "melancholic"
                if removal == "graveyard":
                    session._rules_remove_field_item(foe, "p2", "graveyard")
                else:
                    # Both ordinary exits and effect-driven suspension used to
                    # overwrite the copy with the target's departure values.
                    session.battlefield.append(self.field_item("bob", "p1", self.BOB, counters={"power": 3}))
                    session._rules_remove_field_item_by_effect(foe, "p2", "graveyard")
                    self.assertEqual(len(session.rules_engine["suspendedCards"]), 1)
                session.prune_rules_ongoing_effects()
                self.assertEqual(session.rules_manifestation_characteristics(mimer), {"power": 3, "temperament": "choleric"})

    def test_reactivation_takes_a_new_snapshot_and_own_modifiers_still_apply(self):
        session, mimer, foe = self.started()
        self.activate(session)
        session.resolve_rules_top_action()
        foe["temperamentOverride"] = "phlegmatic"
        foe["counters"]["power"] = 1
        mimer["counters"]["power"] = 2
        self.assertEqual(session.rules_manifestation_characteristics(mimer), {"power": 5, "temperament": "choleric"})
        self.activate(session)
        session.resolve_rules_top_action()
        self.assertEqual(session.rules_manifestation_characteristics(mimer), {"power": 6, "temperament": "phlegmatic"})
        copies = [effect for effect in session.rules_engine["ongoingEffects"] if effect["kind"] == "copy_power_temperament"]
        self.assertEqual(len(copies), 1)

    def test_cleansing_the_original_does_not_undo_mimers_copy(self):
        session, mimer, foe = self.started()
        self.mask(session, "vitreous")
        self.activate(session)
        session.resolve_rules_top_action()
        session.apply_rules_action_result({
            "controllerId": "p2", "source": {"cardId": "cleanse"},
            "targets": [{"kind": "card", "itemId": "foe", "cardId": "m-0"}],
            "ability": {"result": {"kind": "cleanse_target"}},
        })
        self.assertEqual(session.rules_manifestation_characteristics(foe)["temperament"], "choleric")
        self.assertEqual(session.rules_manifestation_characteristics(mimer), {"power": 3, "temperament": "vitreous"})
