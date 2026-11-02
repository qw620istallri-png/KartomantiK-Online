"""Shared trigger invariants for uncovered enters-field-zone cards."""
import copy
import unittest

import card_ability_smoke as smoke
import main


ZONE_ENTRY_NAMES = (
    "Advocate of Catharsis",
    "Ju Lien, the Provocateur",
    "Juggling Amphora",
    "Thought Saboteur",
    "Perfidious Baranchio",
    "Fintus, the Spectacular",
    "Jija, Matron Bomb",
    "Plinius, Risk-taker",
    "Mirrorbeast",
    "Buddhan the Dark",
    "Tebebe, Taken by the Dunes",
    "Mollino, the Repeller",
    "Auction Profiteer",
    "Thoughtcutter",
    "Punitive Tripod",
    "Jodorosk, the Psychomage",
)


class ZoneEntryFamilyClauses(unittest.TestCase):
    @staticmethod
    def card(name):
        return next(card for card in main.CARD_DATA if card["name"] == name)

    def ability(self, name):
        card = self.card(name)
        abilities = [
            ability for ability in main.CARD_ABILITIES[card["id"]]
            if (ability.get("trigger") or {}).get("event")
            == "enters_field_zone"
        ]
        self.assertEqual(len(abilities), 1, name)
        return card, abilities[0]

    @staticmethod
    def target_override(name, session):
        if name == "Thought Saboteur":
            item = session.find_battlefield_item("opp-will-field")
        elif name == "Mirrorbeast":
            item = session.find_battlefield_item("opp-con")
        else:
            return None
        return [{
            "kind": "card",
            "itemId": item["id"],
            "cardId": item["cardId"],
            "ownerId": item["ownerId"],
            "controllerId": item.get("controllerId") or item["ownerId"],
        }]

    def fixture(self, name):
        card, ability = self.ability(name)
        session, source, stack_action = smoke.make_session(
            card["id"], ability
        )
        zone = ability["trigger"]["zone"]
        source["fieldZone"] = zone
        source["faceUp"] = True
        session.rules_engine["pendingChoice"] = None
        return card, ability, session, source, stack_action, zone

    def test_all_sixteen_compile_one_exact_zone_entry_trigger(self):
        self.assertEqual(len(ZONE_ENTRY_NAMES), 16)
        for name in ZONE_ENTRY_NAMES:
            with self.subTest(card=name):
                card, ability = self.ability(name)
                zone = ability["trigger"]["zone"]
                self.assertIn(zone, {"confrontation", "interzone"})
                self.assertIn(
                    "Confrontation Zone"
                    if zone == "confrontation" else "Interzone",
                    card["effect"],
                )
                self.assertTrue(
                    ability.get("result")
                    or ability.get("ongoingEffect")
                    or ability.get("ongoingEffects")
                )

    def test_trigger_requires_the_exact_zone_and_a_live_face_up_source(self):
        for name in ZONE_ENTRY_NAMES:
            with self.subTest(card=name):
                _card, _ability, session, source, _stack, zone = (
                    self.fixture(name)
                )
                session.rules_engine["actionStack"] = []
                actions = session.queue_rules_field_zone_entry_triggers(
                    source, zone, defer=True
                )
                self.assertEqual(len(actions), 1)

                wrong_zone = (
                    "interzone"
                    if zone == "confrontation"
                    else "confrontation"
                )
                self.assertEqual(
                    session.queue_rules_field_zone_entry_triggers(
                        source, wrong_zone, defer=True
                    ),
                    [],
                )
                source["faceUp"] = False
                self.assertEqual(
                    session.queue_rules_field_zone_entry_triggers(
                        source, zone, defer=True
                    ),
                    [],
                )
                source["faceUp"] = True
                source["effectsDisabled"] = True
                self.assertEqual(
                    session.queue_rules_field_zone_entry_triggers(
                        source, zone, defer=True
                    ),
                    [],
                )

    def test_each_zone_entry_effect_begins_real_resolution(self):
        for name in ZONE_ENTRY_NAMES:
            with self.subTest(card=name):
                _card, ability, session, source, stack_action, zone = (
                    self.fixture(name)
                )
                existing_stack = (
                    [stack_action] if name == "Thoughtcutter" else []
                )
                session.rules_engine["actionStack"] = existing_stack
                before = copy.deepcopy((
                    session.players,
                    session.battlefield,
                    session.rules_engine["ongoingEffects"],
                ))
                actions = session.queue_rules_field_zone_entry_triggers(
                    source, zone, defer=True
                )
                action = actions[0]
                action["targets"] = (
                    self.target_override(name, session)
                    or smoke.targets_for(ability, stack_action)
                )
                session.rules_engine["actionStack"].append(action)
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
