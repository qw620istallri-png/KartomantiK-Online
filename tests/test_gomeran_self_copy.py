"""Reported 13/11: Help! played in the Resolution chained Gomeran, which copied itself.

Help! and Reforging Fate are now Reaction-only, and Gomeran never copies its own entry.
"""

from session import ADVANCED_PHASES
from test_game_state import RealCardRulesCase


GOMERAN = "xfgbjv2gjb09fj9_en"
HELP = "mv2vad6gwrfbi1l_en"
REFORGING_FATE = "z2fen73ktw8pbqz_en"
SUPPORT_WILLS = (
    HELP, REFORGING_FATE, "gu9rppos4r9ucsr_en", "9c7s9dn3sa5dcko_en",
    "72zvsiuky5ytolh_en", "5q6t7i5pzctbi8s_en", "inner-deserts-072",
)


class GomeranSelfCopyTests(RealCardRulesCase):
    ALL = (GOMERAN,) + SUPPORT_WILLS

    def started(self, phase="resolution_effects"):
        session, p1, p2 = self.make_session()
        session.phase_tracker.update(index=ADVANCED_PHASES.index(phase), turn=3)
        session.rules_engine.update(
            readyPlayerIds=["p1", "p2"],
            firstManifestationComplete=True,
            firstManifestationTriggersQueued=True,
            priorityPlayerId="p1",
            priorityPasses=[],
            actionStack=[],
            pendingChoice=None,
        )
        session.battlefield = [self.field_item("first", "p1", "m-1")]
        return session, p1, p2

    def chain_gomeran_with_help(self, session, p1):
        self.put(p1, "hand", [GOMERAN])
        session.apply_rules_action_result({
            "id": "help", "controllerId": "p1",
            "source": {"cardId": HELP, "zone": "hand", "ownerId": "p1"},
            "ability": {"result": self.ABILITIES[HELP][0]["result"]},
        })
        choice = session.rules_engine["pendingChoice"]
        error, chained = session.resolve_rules_choice(
            "p1", choice["id"], [GOMERAN], placement={"x": 10, "y": 10},
        )
        self.assertIsNone(error, error)
        self.assertEqual(chained["status"], "chained")
        return chained

    def drain_stack(self, session):
        for _ in range(20):
            if session.rules_engine.get("pendingChoice"):
                choice = session.rules_engine["pendingChoice"]
                if choice.get("kind") == "optional_stack_action":
                    session.resolve_rules_choice(choice["playerId"], choice["id"], option="accept")
                    continue
                break
            if not session.rules_engine.get("actionStack"):
                break
            session.resolve_rules_top_action()

    def gomerans(self, session):
        return [item for item in session.battlefield if item.get("cardId") == GOMERAN]

    def test_chained_gomeran_does_not_copy_itself(self):
        for phase in ("resolution_effects", "confrontation_reaction"):
            with self.subTest(phase=phase):
                session, p1, _p2 = self.started(phase)
                chained = self.chain_gomeran_with_help(session, p1)
                self.assertNotIn(
                    "gomeran-copies-support-entry",
                    [entry["ability"]["id"] for entry in chained["triggeredActions"]],
                )
                self.drain_stack(session)
                self.assertEqual(len(self.gomerans(session)), 1)
                self.assertFalse(any(
                    item.get("isTokenCopy") for item in session.battlefield
                ))

    def test_chained_gomeran_still_copies_the_next_allied_support(self):
        session, p1, _p2 = self.started("confrontation_reaction")
        self.chain_gomeran_with_help(session, p1)
        self.drain_stack(session)
        entering = self.field_item("ally", "p1", "m-2", isSupport=True)
        session.battlefield.append(entering)
        queued = session.queue_rules_support_entry_triggers(entering, played=True, defer=True)
        self.assertEqual(
            [entry["ability"]["id"] for entry in queued],
            ["gomeran-copies-support-entry"],
        )


    def test_wills_that_put_into_support_are_reaction_only(self):
        rules = self.real_rules()
        for card_id in SUPPORT_WILLS:
            self.assertEqual(rules[card_id]["playPhases"], ["confrontation_reaction"])
        for phase, allowed in (
            ("confrontation_reaction", True),
            ("resolution_effects", False),
            ("end_actions", False),
        ):
            session, _p1, _p2 = self.started(phase)
            for card_id in SUPPORT_WILLS:
                with self.subTest(phase=phase, card=card_id):
                    error = session.rules_action_timing_error(
                        "play_card",
                        {"cardId": card_id, "zone": "hand", "cardType": "ephemeral_will"},
                        player_id="p1",
                    )
                    self.assertEqual(error is None, allowed, error)
