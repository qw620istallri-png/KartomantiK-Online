"""Strict global Manifestation-as-Tribute contracts for Mirror and Mountain."""

from session import ADVANCED_PHASES
from test_game_state import RealCardRulesCase


MANIFESTATION_USED_AS_TRIBUTE_NAMES = (
    "Melancholic Mirror",
    "Sacred Mountain",
)

MIRROR = "wx7y64eaa0wlvuk_en"
MOUNTAIN = "inner-deserts-123"

MIRROR_ABILITY = {
    "id": "exhaust-to-copy-tribute-manifestation",
    "optional": True,
    "trigger": {
        "event": "manifestation_used_as_tribute",
        "eventController": "owner",
    },
    "result": {"kind": "copy_related_tribute_if_exhaust"},
}

MOUNTAIN_ABILITY = {
    "id": "sacred-mountain-exiles-tribute",
    "trigger": {"event": "manifestation_used_as_tribute"},
    "result": {"kind": "exile_tribute_manifestation_score_others"},
}


class ManifestationUsedAsTributeFamily(RealCardRulesCase):
    ALL = (MIRROR, MOUNTAIN)

    def started(self):
        session, p1, p2 = self.make_session()
        session.phase_tracker.update(
            index=ADVANCED_PHASES.index("end_actions"), turn=3,
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

    def source(self, card_id, owner, item_id, **extra):
        return self.field_item(
            item_id, owner, card_id, field_zone="field", rotation=0.0,
            **extra,
        )

    def queue_tribute(
        self, session, card_id, payer, owner=None, destination="graveyard",
        simultaneous_action_id=None, defer_if_choice=False,
    ):
        owner = owner or payer
        return session.queue_rules_tribute_triggers(
            [card_id], payer,
            simultaneous_action_id=simultaneous_action_id,
            tribute_movements=[{
                "cardId": card_id,
                "ownerId": owner,
                "destination": destination,
            }],
            defer_if_choice=defer_if_choice,
        )

    def test_both_compile_the_exact_printed_contract(self):
        rules = self.real_rules()
        self.assertEqual(set(rules), set(self.ALL))
        self.assertEqual(self.ABILITIES[MIRROR], [MIRROR_ABILITY])
        self.assertEqual(self.ABILITIES[MOUNTAIN], [MOUNTAIN_ABILITY])
        self.assertEqual(
            rules[MIRROR]["triggeredAbilities"], [MIRROR_ABILITY],
        )
        self.assertEqual(
            rules[MOUNTAIN]["triggeredAbilities"], [MOUNTAIN_ABILITY],
        )

    def test_real_will_payment_queues_both_with_exact_tribute_metadata(self):
        session, p1, _p2 = self.started()
        session.battlefield = [
            self.source(MIRROR, "p1", "mirror"),
            self.source(MOUNTAIN, "p2", "mountain"),
        ]
        self.put(p1, "hand", ["will-x", "m-1"])
        error, paid_action = session.declare_rules_action(
            "p1", "Paid Will", kind="play_card",
            source={"cardId": "will-x", "zone": "hand"},
            payment_card_ids=["m-1"],
        )
        self.assertIsNone(error, error)
        actions = session.queue_rules_tribute_triggers(
            paid_action["cost"]["tributeCardIds"], "p1",
            simultaneous_action_id=paid_action["id"],
            tribute_movements=paid_action["cost"]["tributeMovements"],
        )
        self.assertEqual(
            [entry["ability"]["id"] for entry in actions],
            [MIRROR_ABILITY["id"], MOUNTAIN_ABILITY["id"]],
        )
        for entry in actions:
            trigger = entry["ability"]["trigger"]
            self.assertEqual(
                (
                    trigger["relatedActionId"], trigger["relatedCardId"],
                    trigger["relatedOwnerId"], trigger["eventControllerId"],
                ),
                (paid_action["id"], "m-1", "p1", "p1"),
            )
        self.assertEqual(p1["zones"]["graveyard"], ["m-1"])

    def test_mirror_only_follows_its_controller_and_only_while_ready(self):
        session, _p1, _p2 = self.started()
        mirror = self.source(MIRROR, "p1", "mirror")
        mountain = self.source(MOUNTAIN, "p2", "mountain")
        session.battlefield = [mirror, mountain]
        opponent = self.queue_tribute(session, "m-1", "p2")
        self.assertEqual(
            [entry["ability"]["id"] for entry in opponent],
            [MOUNTAIN_ABILITY["id"]],
        )
        mirror["rotation"] = 90.0
        own_while_exhausted = self.queue_tribute(session, "m-2", "p1")
        self.assertEqual(
            [entry["ability"]["id"] for entry in own_while_exhausted],
            [MOUNTAIN_ABILITY["id"]],
        )
        mirror["rotation"] = 0.0
        own_while_ready = self.queue_tribute(session, "m-3", "p1")
        self.assertEqual(
            [entry["ability"]["id"] for entry in own_while_ready],
            [MIRROR_ABILITY["id"], MOUNTAIN_ABILITY["id"]],
        )

    def test_inactive_sources_do_not_observe_tributes(self):
        session, _p1, _p2 = self.started()
        mirror = self.source(MIRROR, "p1", "mirror", effectsDisabled=True)
        mountain = self.source(MOUNTAIN, "p1", "mountain")
        mountain["fieldZone"] = "stalemate"
        session.battlefield = [mirror, mountain]
        self.assertEqual(self.queue_tribute(session, "m-1", "p1"), [])

    def test_mirror_decline_does_not_exhaust_or_create_a_copy(self):
        session, p1, _p2 = self.started()
        mirror = self.source(MIRROR, "p1", "mirror")
        session.battlefield = [mirror]
        self.put(p1, "graveyard", ["m-1"])
        actions = self.queue_tribute(
            session, "m-1", "p1", defer_if_choice=True,
        )
        self.assertEqual(len(actions), 1)
        choice = session.rules_engine["pendingChoice"]
        self.assertEqual(
            (choice["kind"], choice["playerId"], choice["sourceCardId"]),
            ("optional_stack_action", "p1", MIRROR),
        )
        error, result = session.resolve_rules_choice(
            "p1", choice["id"], option="decline",
        )
        self.assertIsNone(error, error)
        self.assertEqual(result["status"], "declined")
        self.assertEqual(mirror["rotation"], 0.0)
        self.assertEqual(session.rules_engine["actionStack"], [])
        self.assertEqual(len(session.battlefield), 1)

    def test_mirror_accept_exhausts_and_creates_one_support_token_copy(self):
        session, p1, _p2 = self.started()
        mirror = self.source(MIRROR, "p1", "mirror")
        session.battlefield = [mirror]
        self.put(p1, "graveyard", ["m-1"])
        self.queue_tribute(session, "m-1", "p1", defer_if_choice=True)
        choice = session.rules_engine["pendingChoice"]
        error, accepted = session.resolve_rules_choice(
            "p1", choice["id"], option="accept",
        )
        self.assertIsNone(error, error)
        self.assertEqual(accepted["status"], "accepted")
        action = session.rules_engine["actionStack"].pop()
        result = session.apply_rules_action_result(action)
        self.assertEqual(result["status"], "accepted")
        self.assertEqual(mirror["rotation"], 90.0)
        copy = session.find_battlefield_item(result["createdItemId"])
        self.assertEqual(
            (
                copy["cardId"], copy["ownerId"],
                session.rules_item_controller_id(copy), copy["fieldZone"],
            ),
            ("m-1", "p1", "p1", "confrontation"),
        )
        self.assertTrue(
            copy["isCopy"] and copy["isTokenCopy"] and copy["isSupport"],
        )
        self.assertEqual(p1["zones"]["graveyard"], ["m-1"])

    def test_mountain_exiles_the_immutable_owner_card_and_scores_other_players(self):
        for payer, owner, expected_scores in (
            ("p1", "p1", (0, 5)),
            ("p2", "p1", (5, 0)),
        ):
            with self.subTest(payer=payer, owner=owner):
                session, p1, p2 = self.started()
                session.battlefield = [
                    self.source(MOUNTAIN, "p1", "mountain"),
                ]
                self.put(p1, "graveyard", {"m-1": owner})
                actions = self.queue_tribute(
                    session, "m-1", payer, owner=owner,
                )
                self.assertEqual(len(actions), 1)
                trigger = actions[0]["ability"]["trigger"]
                self.assertEqual(
                    (trigger["relatedOwnerId"], trigger["eventControllerId"]),
                    (owner, payer),
                )
                result = session.apply_rules_action_result(actions[0])
                self.assertEqual(result["status"], "exiled")
                self.assertEqual(p1["zones"]["graveyard"], [])
                self.assertEqual(p1["zones"]["exile"], ["m-1"])
                self.assertEqual((p1["score"], p2["score"]), expected_scores)
