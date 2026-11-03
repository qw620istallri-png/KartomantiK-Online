"""Shared trigger invariants for uncovered enters-field cards."""
import copy
import unittest

import card_ability_smoke as smoke
import main


FIELD_ENTRY_NAMES = (
    "The Slumberer",
    "Skysailing Triad",
    "Inert Anchorstone",
    "Zrutrug, the Indebted",
    "Parasitic Drill",
    "Gorb, the Musclebound",
    "Quorum, the Untouchable",
    "Larman Doz, the Upright",
    "Moaning Consul",
    "Bizarre Mechanism",
    "Pillarpede",
    "Flower of Evil",
    "Temperamental Splendor",
)


class FieldEntryFamilyClauses(unittest.TestCase):
    @staticmethod
    def card(name):
        return next(card for card in main.CARD_DATA if card["name"] == name)

    def ability(self, name):
        card = self.card(name)
        abilities = [
            ability for ability in main.CARD_ABILITIES[card["id"]]
            if (ability.get("trigger") or {}).get("event")
            == "enters_field"
        ]
        self.assertEqual(len(abilities), 1, name)
        return card, abilities[0]

    def fixture(self, name):
        card, ability = self.ability(name)
        session, source, stack_action = smoke.make_session(
            card["id"], ability
        )
        source["faceUp"] = True
        session.rules_engine["pendingChoice"] = None
        session.rules_engine["actionStack"] = []
        return card, ability, session, source, stack_action

    def test_all_thirteen_compile_one_exact_field_entry_trigger(self):
        self.assertEqual(len(FIELD_ENTRY_NAMES), 13)
        for name in FIELD_ENTRY_NAMES:
            with self.subTest(card=name):
                card, ability = self.ability(name)
                self.assertIn("enters the field", card["effect"].lower())
                self.assertEqual(
                    ability["trigger"]["event"], "enters_field"
                )
                self.assertIn(
                    ability["trigger"].get("visibility", "face_up"),
                    {"face_up", "any"},
                )
                self.assertTrue(
                    ability.get("result")
                    or ability.get("ongoingEffect")
                    or ability.get("ongoingEffects")
                )

    def test_field_entry_requires_the_source_to_enter_face_up(self):
        for name in FIELD_ENTRY_NAMES:
            with self.subTest(card=name):
                card, _ability, session, source, _stack = (
                    self.fixture(name)
                )
                actions = session.queue_rules_battlefield_entry_triggers(
                    card["id"], "p1", source["id"], True, defer=True
                )
                self.assertEqual(len(actions), 1)
                self.assertEqual(
                    session.queue_rules_battlefield_entry_triggers(
                        card["id"], "p1", source["id"], False, defer=True
                    ),
                    [],
                )

    def test_each_field_entry_effect_begins_real_resolution(self):
        for name in FIELD_ENTRY_NAMES:
            with self.subTest(card=name):
                card, ability, session, source, stack_action = (
                    self.fixture(name)
                )
                before = copy.deepcopy((
                    session.players,
                    session.battlefield,
                    session.rules_engine["ongoingEffects"],
                ))
                action = session.queue_rules_battlefield_entry_triggers(
                    card["id"], "p1", source["id"], True, defer=True
                )[0]
                action["targets"] = smoke.targets_for(
                    ability, stack_action
                )
                session.rules_engine["actionStack"] = [action]
                resolved = session.resolve_rules_top_action()
                effect = resolved["action"].get("effectResult") or {}
                self.assertEqual(resolved["status"], "resolved")
                self.assertNotEqual(effect.get("kind"), "invalid_targets")
                self.assertTrue(
                    effect
                    or session.rules_engine.get("pendingChoice")
                    or (
                        session.players,
                        session.battlefield,
                        session.rules_engine["ongoingEffects"],
                    ) != before
                )


if __name__ == "__main__":
    unittest.main()
