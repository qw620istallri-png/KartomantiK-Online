"""Multi-step rules transitions that primitive-level tests cannot certify."""
import unittest

import test_distribution_token_clauses as distribution_fixtures
import test_semantic_batch_001_150 as semantic_fixtures


class RulesTransitionMatrix(unittest.TestCase):
    cid = staticmethod(semantic_fixtures.SemanticBatch001150.cid)
    world = semantic_fixtures.SemanticBatch001150.world
    field = staticmethod(semantic_fixtures.SemanticBatch001150.field)
    put = staticmethod(semantic_fixtures.SemanticBatch001150.put)

    def assert_unique_physical_cards(self, session):
        locations = []
        for container_id, player in session.players.items():
            for zone, cards in player["zones"].items():
                locations.extend(
                    (card_id, f"{container_id}:{zone}") for card_id in cards
                )
        locations.extend(
            (item["cardId"], f"battlefield:{item['id']}")
            for item in session.battlefield
            if item.get("cardId")
            and not item.get("isCopy")
            and not item.get("isTokenCard")
        )
        locations.extend(
            ((action.get("source") or {}).get("cardId"), f"stack:{action['id']}")
            for action in session.rules_engine["actionStack"]
            if action.get("sourceOnStack")
            and (action.get("source") or {}).get("cardId")
        )
        by_card = {}
        for card_id, location in locations:
            by_card.setdefault(card_id, []).append(location)
        duplicates = {
            card_id: entries
            for card_id, entries in by_card.items()
            if len(entries) > 1
        }
        self.assertEqual(duplicates, {})

    def brood_token(self, session):
        helper = distribution_fixtures.DistributionTokenClauses()
        helper.brood(session)
        helper.choose_count(session, 1)
        return session.battlefield[0]

    def test_token_support_cancel_retry_resolve_return_and_next_turn(self):
        session = self.world()
        token = self.brood_token(session)
        self.field(
            session, self.cid("Herbaceous Whisperer"),
            "whisperer", zone="interzone",
        )
        self.assertEqual(
            session.rules_manifestation_characteristics(token)["power"], 1
        )
        session.rules_engine["priorityPlayerId"] = "p1"
        error, support = session.declare_rules_action(
            "p1", "Stampeding Brood Token",
            kind="play_card", as_support=True,
            source={
                "cardId": None, "zone": "battlefield",
                "itemId": token["id"],
            },
        )
        self.assertIsNone(error)
        self.assertEqual(token["pendingSupportActionId"], support["id"])

        ignore_id = self.cid("Ignore")
        self.put(session, "p2", "hand", [ignore_id])
        error, _ignore = session.declare_rules_action(
            "p2", "Ignore", kind="play_card",
            source={"cardId": ignore_id, "zone": "hand"},
            ability_id="ignore-stack-effect-unless-paid",
            targets=[{"kind": "stack_effect", "actionId": support["id"]}],
        )
        self.assertIsNone(error)
        session.resolve_rules_top_action()
        choice = session.rules_engine["pendingChoice"]
        self.assertEqual(choice["kind"], "stack_counter_payment")
        self.assertIsNone(
            session.resolve_rules_choice(
                "p1", choice["id"], option="decline"
            )[0]
        )
        self.assertEqual(session.rules_engine["actionStack"], [])
        self.assertNotIn("pendingSupportActionId", token)
        self.assertEqual(session.rules_field_zone(token), "interzone")
        self.assertFalse(token["isSupport"])
        self.assertTrue(session.rules_card_can_enter_support(token))
        self.assert_unique_physical_cards(session)

        session.rules_engine["priorityPlayerId"] = "p1"
        error, _support = session.declare_rules_action(
            "p1", "Stampeding Brood Token",
            kind="play_card", as_support=True,
            source={
                "cardId": None, "zone": "battlefield",
                "itemId": token["id"],
            },
        )
        self.assertIsNone(error)
        session.resolve_rules_top_action()
        self.assertEqual(session.rules_field_zone(token), "confrontation")
        self.assertTrue(token["isSupport"])
        self.assertEqual(
            session.rules_manifestation_characteristics(token)["power"], 2
        )

        enemy = self.field(session, "m2", "enemy", owner="p2")
        session.rules_engine["confrontationResult"] = {
            "turn": session.phase_tracker["turn"],
            "status": "effects",
            "winnerId": "p1",
            "loserId": "p2",
            "stalemate": False,
            "participantItemIds": [token["id"], enemy["id"]],
            "winnerItemIds": [token["id"]],
            "loserItemIds": [enemy["id"]],
        }
        session.begin_rules_confrontation_cleanup()
        choice = session.rules_engine["pendingChoice"]
        self.assertEqual(choice["itemId"], token["id"])
        self.assertIsNone(
            session.resolve_rules_choice(
                "p1", choice["id"], option="interzone"
            )[0]
        )
        session.phase_tracker["turn"] += 1
        self.assertEqual(session.rules_field_zone(token), "interzone")
        self.assertFalse(token["isSupport"])
        self.assertTrue(token["hasSupport"])
        self.assertTrue(session.rules_card_can_enter_support(token))
        self.assertEqual(
            session.rules_manifestation_characteristics(token)["power"], 1
        )
        self.assert_unique_physical_cards(session)

    def test_receptacle_activation_availability_declaration_and_resolution_agree(self):
        session = self.world()
        gnarlipuff = self.cid("Gnarlipuff, the Slimy")
        session.put_zone_card("p2", "receptacle", gnarlipuff, "p1")
        target = self.field(
            session, "m2", "target", owner="p2", zone="interzone"
        )
        self.put(session, "p1", "hand", ["m3"])
        session.phase_tracker["index"] = semantic_fixtures.ADVANCED_PHASES.index(
            "end_actions"
        )
        session.rules_engine["priorityPlayerId"] = "p1"

        sources = list(session.rules_receptacle_activated_sources("p1"))
        self.assertEqual(
            [
                (container_id, card_id, ability["id"])
                for container_id, card_id, ability in sources
            ],
            [(
                "p2", gnarlipuff,
                "gnarlipuff-return-interzone-manifestation",
            )],
        )
        self.assertTrue(session.rules_player_can_act("p1"))
        self.assertIsNone(session.rules_auto_pass_player())
        error, action = session.declare_rules_action(
            "p1", "Gnarlipuff", kind="activated_effect",
            source={
                "cardId": gnarlipuff,
                "zone": "receptacle",
                "containerId": "p2",
            },
            ability_id="gnarlipuff-return-interzone-manifestation",
            payment_card_ids=["m3"],
            targets=[{"kind": "card", "itemId": target["id"]}],
        )
        self.assertIsNone(error)
        self.assertIsNotNone(action)
        session.resolve_rules_top_action()
        self.assertIsNone(session.find_battlefield_item(target["id"]))
        self.assertEqual(session.players["p2"]["zones"]["deck"], ["m2"])
        self.assert_unique_physical_cards(session)

    def test_rematch_preserves_loss_for_recall_then_reset_clears_it(self):
        session = self.world()
        first = self.field(session, "m2", "first-p1")
        opposing = self.field(
            session, "m3", "first-p2", owner="p2"
        )
        session.rules_engine["firstManifestationItemIds"] = {
            "p1": first["id"], "p2": opposing["id"],
        }
        session.phase_tracker["index"] = semantic_fixtures.ADVANCED_PHASES.index(
            "resolution_compare"
        )
        result = session.prepare_rules_confrontation_result()
        self.assertEqual(result["loserId"], "p1")

        session.phase_tracker["index"] = semantic_fixtures.ADVANCED_PHASES.index(
            "resolution_effects"
        )
        session.rules_engine["priorityPlayerId"] = "p1"
        rematch = self.cid("Rematch!")
        self.put(session, "p1", "hand", [rematch])
        session.add_rules_excess_essence(
            "p1", [{"temperament": "choleric", "amount": 2}]
        )
        error, _action = session.declare_rules_action(
            "p1", "Rematch!", kind="play_card",
            source={"cardId": rematch, "zone": "hand"},
            ability_id="schedule-rematch-after-resolution",
        )
        self.assertIsNone(error)
        session.resolve_rules_top_action()
        session.begin_rules_confrontation_cleanup()
        session.phase_tracker["index"] = semantic_fixtures.ADVANCED_PHASES.index(
            "resolution_move"
        )
        session.rules_engine["priorityPlayerId"] = "p1"
        self.assertIsNone(session.pass_rules_priority("p1")[0])
        error, transition = session.pass_rules_priority("p2")
        self.assertIsNone(error)
        self.assertTrue(transition["rematchStarted"])
        self.assertTrue(session.rules_player_lost_confrontation_this_turn("p1"))
        self.assertTrue(
            session.serialize_for("p1", "player")["rulesEngine"][
                "lostConfrontationThisTurn"
            ]
        )

        recall = self.cid("Recall")
        self.put(session, "p1", "hand", [recall])
        self.put(session, "p1", "deck", ["m4"])
        session.rules_engine["priorityPlayerId"] = "p1"
        error, recall_action = session.declare_rules_action(
            "p1", "Recall", kind="play_card",
            source={"cardId": recall, "zone": "hand"},
            ability_id="recall-searches-after-loss",
        )
        self.assertIsNone(error)
        self.assertIsNotNone(recall_action)

        session.reset_phase_tracker()
        self.assertFalse(
            session.rules_player_lost_confrontation_this_turn("p1")
        )
        self.assertFalse(
            session.serialize_for("p1", "player")["rulesEngine"][
                "lostConfrontationThisTurn"
            ]
        )
        self.assert_unique_physical_cards(session)


if __name__ == "__main__":
    unittest.main()
