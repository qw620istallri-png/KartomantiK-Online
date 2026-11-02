"""Independent contracts for every Manifestation with no printed effect."""
import unittest

import main
from session import ADVANCED_PHASES, Session


VANILLA_NAMES = (
    "Sated Swineheart",
    "Tiptup, the Whistler",
    "Amiable Blockhead",
    "Isolated Wordsmith",
    "Hurlon, Thought-implanter",
    "Rigid Omen",
    "Repudiated Orphan",
    "Yurfuq, Sad Lily",
    "Underground Snail",
    "Roly-polymancer",
    "Pok, the Teaser",
    "Incoherent Pard",
    "Ancient Bicep",
    "Fiery Furybeast",
    "Titan of the Blazing Womb",
    "Migmomirf",
)


class VanillaCardClauses(unittest.TestCase):
    def session(self):
        session = Session(
            card_points=main.CARD_POINTS,
            card_labels=main.CARD_LABELS,
            manifestation_ids=main.CARD_MANIFESTATION_IDS,
            card_rules=main.CARD_RULES,
            rules_beta=True,
        )
        for seat, player_id in enumerate(("p1", "p2")):
            session.get_or_create_player(
                player_id, player_id.upper(), seat=seat
            )
        session.rules_engine["deckConfirmedPlayerIds"] = ["p1", "p2"]
        session.rules_engine["readyPlayerIds"] = ["p1", "p2"]
        return session

    def cards(self):
        by_name = {card["name"]: card for card in main.CARD_DATA}
        return [by_name[name] for name in VANILLA_NAMES]

    def test_catalog_contains_exact_sixteen_vanilla_manifestations(self):
        actual = {
            card["name"]
            for card in main.CARD_DATA
            if not str(card.get("effect") or "").strip()
        }
        self.assertEqual(actual, set(VANILLA_NAMES))
        for card in self.cards():
            with self.subTest(card=card["name"]):
                self.assertEqual(card["type"], "manifestation")
                self.assertEqual(card["effect"], "")
                self.assertNotIn(card["id"], main.CARD_ABILITIES)

    def test_vanilla_compilation_contains_only_base_characteristics(self):
        empty_buckets = (
            "continuousPowerRules",
            "activatedAbilities",
            "playedAbilities",
            "triggeredAbilities",
            "playPermissions",
            "passiveEffects",
        )
        false_flags = (
            "adamant",
            "float",
            "persist",
            "cannotEnterConfrontation",
            "retainsExcessEssence",
            "canPayTributeFromInterzone",
            "canPayTributeFromLimbo",
            "supportFromHand",
            "supportFromInterzone",
            "supportFromStalemate",
            "playOnlyEmptyStack",
        )
        for card in self.cards():
            with self.subTest(card=card["name"]):
                rules = main.CARD_RULES[card["id"]]
                self.assertEqual(rules["type"], card["type"])
                self.assertEqual(rules["power"], card["power"])
                self.assertEqual(rules["powerCost"], card["powerCost"])
                self.assertEqual(
                    rules["temperaments"], card["temperaments"]
                )
                self.assertTrue(rules["canPayTribute"])
                self.assertTrue(rules["canBeFirstManifestation"])
                for key in empty_buckets:
                    self.assertEqual(rules[key], [], key)
                for key in false_flags:
                    self.assertFalse(rules[key], key)

    def test_vanilla_runtime_uses_default_first_tribute_and_no_support_or_triggers(self):
        for card in self.cards():
            with self.subTest(card=card["name"]):
                session = self.session()
                player = session.players["p1"]
                will_id = "audit-vanilla-will"
                session.card_rules[will_id] = {
                    "type": "ephemeral_will",
                    "cost": card["power"],
                    "powerCost": card["powerCost"],
                    "temperaments": list(card["temperaments"]),
                }
                session.put_zone_card("p1", "hand", will_id, "p1")
                session.put_zone_card("p1", "hand", card["id"], "p1")
                error, payment = session.rules_action_payment(
                    "p1", "play_card",
                    {
                        "cardId": will_id,
                        "cardType": "ephemeral_will",
                        "ownerId": "p1",
                        "controllerId": "p1",
                    },
                    [card["id"]],
                )
                self.assertIsNone(error)
                self.assertEqual(payment["cardIds"], [card["id"]])

                session.phase_tracker["index"] = ADVANCED_PHASES.index(
                    "confrontation_choose"
                )
                session.rules_engine["firstManifestationComplete"] = False
                player["zones"]["hand"].remove(card["id"])
                player["zoneOwners"]["hand"].pop(card["id"], None)
                item = {
                    "id": "vanilla-first",
                    "cardId": card["id"],
                    "ownerId": "p1",
                    "controllerId": "p1",
                    "faceUp": True,
                    "fieldZone": "interzone",
                    "x": 0,
                    "y": 0,
                    "rotation": 0,
                    "counters": {},
                    "stackedOn": None,
                }
                session.battlefield.append(item)
                self.assertIsNone(
                    session.register_first_manifestation("p1", item)
                )
                self.assertEqual(
                    session.rules_field_zone(item), "confrontation"
                )

                waiting = {
                    **item,
                    "id": "vanilla-waiting",
                    "faceUp": True,
                    "fieldZone": "interzone",
                }
                session.battlefield = [waiting]
                self.assertFalse(
                    session.rules_card_can_enter_support(
                        waiting, "interzone"
                    )
                )
                self.assertEqual(
                    session.queue_rules_field_zone_entry_triggers(
                        waiting, "interzone", defer=True
                    ),
                    [],
                )


if __name__ == "__main__":
    unittest.main()
