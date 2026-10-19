"""Regression tests for card bugs reported from play testing.

Wandering Veteran, Shattering the Self, Censor, Destroy, Borombo and Glabron.
Engine tests use the shipped card-abilities.json compiled by the real server
builder; client tests evaluate the relevant app.js functions with Node.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
SERVER_DIR = os.path.abspath(os.path.join(TESTS_DIR, "..", "server"))
for path in (SERVER_DIR, TESTS_DIR):
    if path not in sys.path:
        sys.path.insert(0, path)

import test_game_state as game_state_tests  # noqa: E402  (module import: its cases are not collected twice)
from session import ADVANCED_PHASES  # noqa: E402
from test_card_catalog import build_server_rules  # noqa: E402

ROOT = Path(TESTS_DIR).parent
APP_JS = (ROOT / "public" / "app.js").read_text(encoding="utf-8")
ABILITIES = json.loads((ROOT / "public" / "card-abilities.json").read_text(encoding="utf-8"))

WANDERING_VETERAN = "iwpmdq754ew0mw7_en"
SHATTERING_THE_SELF = "k7dq8ye448xwj54_en"
CENSOR = "op83bq67vaf368q_en"
DESTROY = "f2cj2wys3jhbzci_en"
BOROMBO = "70wsdfb29mmcsqf_en"
GLABRON = "x15xumjqqhrnrds_en"
KNOBBLY_COLOSSUS = "o1b1hf2xpmkt8j2_en"
STICKY_FASCES_FLY = "inner-deserts-101"
TIMID_BRAIN = "5zgq2zcogt4g4d0_en"
FAROC_KO = "inner-deserts-006"


def app_function(name):
    """Source of a top-level `function name(...) { ... }` of app.js."""
    start = APP_JS.index(f"\nfunction {name}(") + 1
    return APP_JS[start:APP_JS.index("\n}\n", start) + 2]


def run_node(script):
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("Node.js is not installed")
    completed = subprocess.run(
        [node, "-e", script], capture_output=True, text=True, timeout=60, check=False,
    )
    if completed.returncode != 0:
        raise AssertionError(completed.stderr)
    return json.loads(completed.stdout)


class ReportedCardRulesCase(game_state_tests.RealCardRulesCase):
    ALL = (
        WANDERING_VETERAN, SHATTERING_THE_SELF, CENSOR, DESTROY, BOROMBO, GLABRON,
        KNOBBLY_COLOSSUS, STICKY_FASCES_FLY, TIMID_BRAIN, FAROC_KO,
    )

    def started_session(self, phase_id="confrontation_reaction", priority="p1"):
        session, p1, p2 = self.make_session()
        session.rules_engine["readyPlayerIds"] = ["p1", "p2"]
        session.rules_engine["firstManifestationComplete"] = True
        for player in (p1, p2):
            self.put(player, "deck", [f"deck-{player['id']}-{index}" for index in range(10)])
        session.phase_tracker["index"] = ADVANCED_PHASES.index(phase_id)
        session.rules_engine["priorityPlayerId"] = priority
        return session, p1, p2

    @staticmethod
    def resolve_top(session, first_passer="p2"):
        second = "p1" if first_passer == "p2" else "p2"
        session.rules_engine["priorityPlayerId"] = first_passer
        error, _ = session.pass_rules_priority(first_passer)
        if error:
            raise AssertionError(error)
        error, resolution = session.pass_rules_priority(second)
        if error:
            raise AssertionError(error)
        return resolution


class WanderingVeteranTests(ReportedCardRulesCase):
    def test_play_permission_is_not_an_activated_ability_on_the_field(self):
        rules = self.real_rules()[WANDERING_VETERAN]
        self.assertEqual(rules["activatedAbilities"], [])
        self.assertEqual(
            [entry["id"] for entry in rules["playPermissions"]], ["support-from-limbo-this-turn"],
        )
        session, p1, _p2 = self.started_session()
        session.battlefield = [self.field_item("vet", "p1", WANDERING_VETERAN, field_zone="interzone")]
        error, _ = session.declare_rules_action(
            "p1", "Veteran", kind="activated_effect",
            source={"cardId": WANDERING_VETERAN, "zone": "battlefield", "itemId": "vet"},
            ability_id="support-from-limbo-this-turn",
        )
        self.assertIsNotNone(error)

    def test_client_activated_ability_filter_matches_the_server(self):
        """The field action button comes from app.js' activatedAbilitiesByCard."""
        start = APP_JS.index("activatedAbilitiesByCard = new Map(\n")
        predicate = re.compile(r"\.filter\((\(ability\) => [^\n]*?)\),\n").search(APP_JS, start).group(1)
        abilities_path = json.dumps(str(ROOT / "public" / "card-abilities.json"))
        client = run_node(f"""
            const data = JSON.parse(require("fs").readFileSync({abilities_path}, "utf8"));
            const keep = {predicate};
            const out = {{}};
            for (const [cardId, abilities] of Object.entries(data)) out[cardId] = abilities.filter(keep).map((a) => a.id);
            process.stdout.write(JSON.stringify(out));
        """)
        self.assertEqual(client[WANDERING_VETERAN], [])
        cards = json.loads((ROOT / "public" / "cards-data.json").read_text(encoding="utf-8"))
        cards += json.loads(
            (ROOT / "public" / "extensions" / "inner-desert" / "cards.json").read_text(encoding="utf-8")
        )
        server = build_server_rules(cards, ABILITIES)
        for card_id in ABILITIES:
            with self.subTest(card_id=card_id):
                self.assertEqual(
                    client[card_id],
                    [entry["id"] for entry in server[card_id]["activatedAbilities"]],
                )


class ShatteringTheSelfTests(ReportedCardRulesCase):
    def play_shatter(self, target_player_id):
        session, p1, p2 = self.started_session()
        for card_id in ("m-10", "m-11"):
            session.card_rules[card_id]["temperaments"] = ["melancholic"]
        self.put(p1, "deck", ["m-0", "m-1", "will-x", "m-2"])
        self.put(p2, "deck", ["m-5", "m-6", "m-7", "m-8"])
        self.put(p1, "hand", [SHATTERING_THE_SELF, "m-10", "m-11"])
        session.card_rules["m-12"]["power"] = 5
        session.battlefield = [self.field_item("theirs", "p2", "m-12")]
        error, _ = session.declare_rules_action(
            "p1", "Shattering the Self", kind="play_card",
            source={"cardId": SHATTERING_THE_SELF, "zone": "hand"},
            targets=[
                {"kind": "player", "playerId": target_player_id},
                {"kind": "card", "itemId": "theirs", "cardId": "m-12"},
            ],
            payment_card_ids=["m-10", "m-11"], ability_id="shattering-the-self",
        )
        self.assertIsNone(error)
        resolution = self.resolve_top(session)
        return session, p1, p2, resolution["action"]["effectResult"]

    def test_the_selected_opponent_discards_from_their_own_deck(self):
        session, p1, p2, result = self.play_shatter("p2")
        self.assertEqual(p2["zones"]["deck"], ["m-8"])
        self.assertEqual(p2["zones"]["graveyard"][-3:], ["m-7", "m-6", "m-5"])
        self.assertEqual(p1["zones"]["deck"], ["m-0", "m-1", "will-x", "m-2"])
        self.assertEqual((result["playerId"], result["count"], result["manifestations"]), ("p2", 3, 3))
        self.assertEqual(self.power_of(session, "theirs"), 2)

    def test_the_selected_caster_discards_from_their_own_deck(self):
        session, p1, p2, result = self.play_shatter("p1")
        self.assertEqual(p1["zones"]["deck"], ["m-2"])
        self.assertEqual(p2["zones"]["deck"], ["m-5", "m-6", "m-7", "m-8"])
        self.assertEqual((result["playerId"], result["count"], result["manifestations"]), ("p1", 3, 2))
        self.assertEqual(result["cardIds"], ["m-0", "m-1", "will-x"])
        self.assertEqual(self.power_of(session, "theirs"), 3)


class CensorTests(ReportedCardRulesCase):
    def test_censor_without_a_hand_manifestation_is_not_playable(self):
        session, p1, _p2 = self.started_session()
        session.battlefield = [self.field_item("victim", "p2", "m-1")]
        self.put(p1, "hand", [CENSOR, "will-x"])
        session.card_rules["will-x"]["cost"] = 9  # unaffordable: only Censor could be played
        self.assertFalse(session.rules_player_can_act("p1"))
        error, _ = session.declare_rules_action(
            "p1", "Censor", kind="play_card", source={"cardId": CENSOR, "zone": "hand"},
            ability_id="censor-exiles-hand-manifestation-to-destroy",
            targets=[{"kind": "card", "itemId": "victim", "cardId": "m-1"}],
        )
        self.assertIn("need a Manifestation in hand", error)
        self.assertEqual(p1["zones"]["hand"], [CENSOR, "will-x"])
        self.assertEqual(session.rules_engine["actionStack"], [])

        self.put(p1, "hand", [CENSOR, "will-x", "m-2"])
        self.assertTrue(session.rules_player_can_act("p1"))
        error, _ = session.declare_rules_action(
            "p1", "Censor", kind="play_card", source={"cardId": CENSOR, "zone": "hand"},
            ability_id="censor-exiles-hand-manifestation-to-destroy", cost_card_id="m-2",
            targets=[{"kind": "card", "itemId": "victim", "cardId": "m-1"}],
        )
        self.assertIsNone(error)
        self.assertIn("m-2", p1["zones"]["exile"])

    def test_client_marks_additional_cost_cards_unplayable_without_the_cost_card(self):
        helper = app_function("rulesAdditionalCostAvailableClient")
        censor = json.dumps(ABILITIES[CENSOR][0])
        brain = json.dumps(ABILITIES[TIMID_BRAIN][0])
        result = run_node(f"""
            let latestState = null;
            const myPlayerId = "p1";
            const cardsById = new Map([
              ["censor", {{ type: "ephemeral_will" }}], ["brain", {{ type: "manifestation" }}],
              ["m", {{ type: "manifestation" }}], ["w", {{ type: "persistent_will" }}],
            ]);
            {helper}
            const check = (hand, ability, source) => {{
              latestState = {{ players: {{ p1: {{ zones: {{ hand: {{ cards: hand }} }} }} }} }};
              return rulesAdditionalCostAvailableClient({{ encodedAbility: ability, card: {{ id: source }} }});
            }};
            process.stdout.write(JSON.stringify([
              check(["censor", "w"], {censor}, "censor"),
              check(["censor", "w", "m"], {censor}, "censor"),
              check(["brain", "m"], {brain}, "brain"),
              check(["brain", "brain"], {brain}, "brain"),
              check(["brain", "w"], {brain}, "brain"),
              check([], {{ id: "plain" }}, "x"),
            ]));
        """)
        self.assertEqual(result, [False, True, False, False, True, True])
        for function in ("handCardIsPlayable", "handCardHasHandAction", "rulesDraftCanBePaid"):
            with self.subTest(function=function):
                self.assertIn("rulesAdditionalCostAvailableClient(draft)", app_function(function))


class DestroyTests(ReportedCardRulesCase):
    def test_destroy_targets_and_destroys_a_resolved_persistent_will(self):
        session, p1, p2 = self.started_session(phase_id="end_actions", priority="p2")
        session.card_rules["pw"] = {
            "type": "persistent_will", "cost": 1, "powerCost": "{G}", "temperaments": ["phlegmatic"],
        }
        self.put(p2, "hand", ["pw", "m-3"])
        error, _ = session.declare_rules_action(
            "p2", "Persistent Will", kind="play_card", source={"cardId": "pw", "zone": "hand"},
            payment_card_ids=["m-3"],
        )
        self.assertIsNone(error)
        self.resolve_top(session, first_passer="p1")
        will = next(item for item in session.battlefield if item["cardId"] == "pw")
        # the engine leaves the Will's field zone implicit: the client must read it as "field"
        self.assertNotIn(will.get("fieldZone"), {"confrontation", "interzone", "stalemate"})
        self.assertEqual(session.rules_field_zone(will), "field")

        for card_id in ("m-10", "m-11", "m-12"):
            session.card_rules[card_id]["temperaments"] = ["hollow"]
        session.battlefield.append(self.field_item("fighter", "p2", "m-4"))
        self.put(p1, "hand", [DESTROY, "m-10", "m-11", "m-12"])
        session.rules_engine["priorityPlayerId"] = "p1"
        error, _ = session.declare_rules_action(
            "p1", "Destroy", kind="play_card", source={"cardId": DESTROY, "zone": "hand"},
            targets=[{"kind": "card", "itemId": "fighter", "cardId": "m-4"}],
            payment_card_ids=["m-10", "m-11", "m-12"],
            ability_id="destroy-field-will-or-interzone-manifestation",
        )
        self.assertIn("different field zone", error)
        error, _ = session.declare_rules_action(
            "p1", "Destroy", kind="play_card", source={"cardId": DESTROY, "zone": "hand"},
            targets=[{"kind": "card", "itemId": will["id"], "cardId": "pw"}],
            payment_card_ids=["m-10", "m-11", "m-12"],
            ability_id="destroy-field-will-or-interzone-manifestation",
        )
        self.assertIsNone(error)
        self.resolve_top(session)
        self.assertIsNone(session.find_battlefield_item(will["id"]))
        self.assertEqual(p2["zones"]["graveyard"][0], "pw")

    def client_targets(self, ability, battlefield, first_ids):
        helper = app_function("rulesStructuredActionTargets")
        return run_node(f"""
            const myPlayerId = "p1";
            const cardsById = new Map([
              ["pw", {{ type: "persistent_will" }}], ["ew", {{ type: "ephemeral_will" }}],
              ["m", {{ type: "manifestation", power: 2 }}],
            ]);
            const latestState = {{
              battlefield: {json.dumps(battlefield)},
              players: {{ p1: {{ zones: {{}} }}, p2: {{ zones: {{}} }} }},
              rulesEngine: {{ firstManifestationItemIds: {json.dumps(first_ids)}, actionStack: [] }},
              phaseTracker: {{ turn: 1 }},
            }};
            {helper}
            const draft = rulesStructuredActionTargets({json.dumps(ability)});
            process.stdout.write(JSON.stringify(draft.structuredTargets.map((target) => target.key)));
        """)

    def test_client_offers_field_wills_to_destroy(self):
        battlefield = [
            {"id": "will", "ownerId": "p2", "cardId": "pw", "faceUp": True},
            {"id": "own-will", "ownerId": "p1", "cardId": "pw", "faceUp": True, "fieldZone": "field"},
            {"id": "iz", "ownerId": "p2", "cardId": "m", "faceUp": True, "fieldZone": "interzone"},
            {"id": "fight", "ownerId": "p2", "cardId": "m", "faceUp": True, "fieldZone": "confrontation"},
            {"id": "first", "ownerId": "p2", "cardId": "m", "faceUp": True},
        ]
        keys = self.client_targets(ABILITIES[DESTROY][0], battlefield, {"p2": "first"})
        self.assertEqual(sorted(keys), ["iz", "own-will", "will"])


class BoromboTests(ReportedCardRulesCase):
    def lose_with_borombo(self, winner_card_id, winner_power):
        session, p1, p2 = self.started_session()
        session.card_rules[winner_card_id]["power"] = winner_power
        session.battlefield = [
            self.field_item("borombo", "p1", BOROMBO),
            self.field_item("winner", "p2", winner_card_id),
            self.field_item("support", "p2", "m-2", isSupport=True),
            self.field_item("their-iz", "p2", "m-3", field_zone="interzone"),
            self.field_item("my-iz", "p1", "m-4", field_zone="interzone"),
        ]
        session.rules_engine["firstManifestationItemIds"] = {"p1": "borombo", "p2": "winner"}
        for _ in range(8):
            if session.current_phase_id() == "resolution_effects":
                break
            session.pass_rules_priority(session.rules_engine["priorityPlayerId"])
        self.assertEqual(session.current_phase_id(), "resolution_effects")
        self.assertEqual(session.rules_engine["confrontationResult"]["loserId"], "p1")
        return session, p1, p2

    def choose(self, session, player_id, kind, **kwargs):
        choice = session.rules_engine["pendingChoice"]
        self.assertIsNotNone(choice)
        self.assertEqual((choice["kind"], choice["playerId"]), (kind, player_id))
        error, _ = session.resolve_rules_choice(player_id, choice["id"], **kwargs)
        self.assertIsNone(error)
        return choice

    def resolve_stack(self, session):
        while session.rules_engine["actionStack"]:
            session.pass_rules_priority(session.rules_engine["priorityPlayerId"])

    def test_borombo_chooses_its_target_alongside_an_optional_winner_trigger(self):
        session, p1, p2 = self.lose_with_borombo(KNOBBLY_COLOSSUS, 6)
        choice = self.choose(session, "p1", "trigger_targets", targets=[
            {"kind": "card", "itemId": "support", "cardId": "m-2"},
        ])
        self.assertEqual(choice["sourceCardId"], BOROMBO)
        # Knobbly Colossus is still asked afterwards
        self.choose(session, "p2", "optional_stack_action", option="accept")
        self.choose(session, "p2", "trigger_targets", targets=[
            {"kind": "card", "itemId": "my-iz", "cardId": "m-4"},
        ])
        self.assertCountEqual(
            [action["ability"]["id"] for action in session.rules_engine["actionStack"]],
            ["destroy-opposing-confrontation-manifestation-on-loss", "destroy-opponent-will-or-manifestation-on-win"],
        )
        self.resolve_stack(session)
        self.assertIsNone(session.find_battlefield_item("support"))
        self.assertIsNotNone(session.find_battlefield_item("winner"))
        self.assertIn("m-2", p2["zones"]["graveyard"])
        self.assertIn("m-4", p1["zones"]["graveyard"])

    def test_borombo_target_choice_waits_for_a_mandatory_winner_target_choice(self):
        session, p1, p2 = self.lose_with_borombo(STICKY_FASCES_FLY, 6)
        self.choose(session, "p2", "trigger_targets", targets=[
            {"kind": "card", "itemId": "their-iz", "cardId": "m-3"},
        ])
        choice = self.choose(session, "p1", "trigger_targets", targets=[
            {"kind": "card", "itemId": "winner", "cardId": STICKY_FASCES_FLY},
        ])
        self.assertEqual(choice["sourceCardId"], BOROMBO)
        self.assertCountEqual(
            [action["ability"]["id"] for action in session.rules_engine["actionStack"]],
            ["destroy-opposing-confrontation-manifestation-on-loss", "fasces-fly-wins-weaken-interzone"],
        )
        self.resolve_stack(session)
        self.assertIsNone(session.find_battlefield_item("winner"))
        self.assertIn(STICKY_FASCES_FLY, p2["zones"]["graveyard"])

    def test_client_offers_opposing_confrontation_targets_to_borombo(self):
        battlefield = [
            {"id": "first", "ownerId": "p2", "cardId": "m", "faceUp": True},
            {"id": "sup", "ownerId": "p2", "cardId": "m", "faceUp": True, "fieldZone": "confrontation", "isSupport": True},
            {"id": "iz", "ownerId": "p2", "cardId": "m", "faceUp": True, "fieldZone": "interzone"},
            {"id": "mine", "ownerId": "p1", "cardId": "m", "faceUp": True, "fieldZone": "confrontation"},
        ]
        keys = DestroyTests.client_targets(self, ABILITIES[BOROMBO][0], battlefield, {"p2": "first"})
        self.assertEqual(sorted(keys), ["first", "sup"])


class GlabronTests(ReportedCardRulesCase):
    def test_glabron_from_hand_stalemates_then_is_played_in_support(self):
        session, p1, _p2 = self.started_session()
        session.battlefield = [
            self.field_item("mine", "p1", "m-1"), self.field_item("theirs", "p2", "m-2"),
            self.field_item("fodder", "p1", "m-3", field_zone="interzone"),
        ]
        session.rules_engine["firstManifestationItemIds"] = {"p1": "mine", "p2": "theirs"}
        self.put(p1, "hand", [GLABRON])
        self.assertTrue(session.rules_player_can_act("p1"))
        error, _ = session.declare_rules_action(
            "p1", "Glabron", kind="play_card", source={"cardId": GLABRON, "zone": "hand"},
            as_support=True,
        )
        self.assertIsNotNone(error)  # no Support yet
        error, _ = session.declare_rules_action(
            "p1", "Glabron", kind="activated_effect", source={"cardId": GLABRON, "zone": "hand"},
            targets=[{"kind": "card", "itemId": "fodder", "cardId": "m-3"}],
            ability_id="glabron-stalemates-own-interzone-card-for-support",
        )
        self.assertIsNone(error)
        self.resolve_top(session)
        self.assertEqual(session.find_battlefield_item("fodder")["fieldZone"], "stalemate")
        session.rules_engine["priorityPlayerId"] = "p1"
        error, _ = session.declare_rules_action(
            "p1", "Glabron", kind="play_card", source={"cardId": GLABRON, "zone": "hand"},
            as_support=True,
        )
        self.assertIsNone(error)
        self.resolve_top(session)
        glabron = next(item for item in session.battlefield if item["cardId"] == GLABRON)
        self.assertEqual((glabron["fieldZone"], glabron.get("isSupport")), ("confrontation", True))

    def test_client_drag_and_drop_recognises_glabrons_support_ability(self):
        """Dropping Glabron (hand or Interzone) must start its ability, not refuse the card."""
        drop = app_function("resolveDrop")
        predicates = re.findall(r'String\(ability\.result\?\.kind \|\| ""\)\.\w+\("grant_source_support"\)', drop)
        self.assertEqual(len(predicates), 2)
        glabron = json.dumps(ABILITIES[GLABRON][0])
        timid = json.dumps(ABILITIES[TIMID_BRAIN][0])
        result = run_node(
            "const out = [];"
            + "".join(
                f"out.push(((ability) => {predicate})({card}));"
                for predicate in predicates for card in (glabron, timid)
            )
            + "process.stdout.write(JSON.stringify(out));"
        )
        self.assertEqual(result, [True, True, True, True])


if __name__ == "__main__":
    unittest.main()


class FarocKoTributeTests(ReportedCardRulesCase):
    """Faroc-Ko has 5 power, but used as tribute it is worth 2 from any zone."""

    def play_will(self, session, cost, payment):
        session.card_rules["will-x"].update({"cost": cost, "powerCost": "{G}" * cost})
        return session.declare_rules_action(
            "p1", "Will", kind="play_card", source={"cardId": "will-x", "zone": "hand"},
            payment_card_ids=payment,
        )

    def test_from_hand_it_pays_two_not_five(self):
        self.assertEqual(self.real_rules()[FAROC_KO]["power"], 5)
        session, p1, _p2 = self.started_session()
        self.put(p1, "hand", ["will-x", FAROC_KO])
        error, _ = self.play_will(session, 3, [FAROC_KO])
        self.assertIsNotNone(error)
        error, action = self.play_will(session, 2, [FAROC_KO])
        self.assertIsNone(error)
        self.assertEqual(action["cost"]["tributeCardIds"], [FAROC_KO])

    def test_from_the_interzone_it_also_pays_two(self):
        session, p1, _p2 = self.started_session()
        self.put(p1, "hand", ["will-x"])
        session.battlefield = [self.field_item("faroc", "p1", FAROC_KO, field_zone="interzone")]
        error, _ = self.play_will(session, 3, ["battlefield|faroc"])
        self.assertIsNotNone(error)
        error, _ = self.play_will(session, 2, ["battlefield|faroc"])
        self.assertIsNone(error)
        self.assertIsNone(session.find_battlefield_item("faroc"))

    def test_the_client_hand_shows_the_tribute_value(self):
        session, p1, _p2 = self.started_session()
        self.put(p1, "hand", [FAROC_KO])
        self.assertEqual(session.rules_tribute_power_overrides_snapshot(), {"p1": {FAROC_KO: 2}})


LOOP_THE_INSISTENT = "1a8wzhi7xhbcenj_en"


class LoopTheInsistentTests(ReportedCardRulesCase):
    ALL = ReportedCardRulesCase.ALL + (LOOP_THE_INSISTENT,)

    def play_will_tributing_loop(self, clear_result_at_end=False):
        session, p1, _p2 = self.started_session()
        session.card_rules["w"] = {
            "type": "ephemeral_will", "cost": 3, "powerCost": "{Y}{Y}{Y}", "temperaments": ["capricious"],
        }
        session.card_rules["m-9"]["power"] = 9
        session.battlefield = [self.field_item("mine", "p1", "m-1"), self.field_item("theirs", "p2", "m-9")]
        session.rules_engine["firstManifestationItemIds"] = {"p1": "mine", "p2": "theirs"}
        self.put(p1, "hand", ["w", LOOP_THE_INSISTENT])
        error, _ = session.declare_rules_action(
            "p1", "w", kind="play_card", source={"cardId": "w", "zone": "hand"},
            payment_card_ids=[LOOP_THE_INSISTENT],
        )
        self.assertIsNone(error)
        action = session.rules_engine["actionStack"][-1]
        session.queue_rules_tribute_triggers(
            action["cost"].get("tributeCardIds") or [], "p1", simultaneous_action_id=action["id"],
            tribute_movements=action["cost"].get("tributeMovements") or [],
        )
        for _ in range(120):
            if clear_result_at_end and session.current_phase_id().startswith("end_"):
                # a rematch or The Stomper clears the result; the loss of this turn still counts
                session.rules_engine["confrontationResult"] = None
            choice = session.rules_engine.get("pendingChoice")
            if choice:
                if choice["kind"] == "confrontation_destination":
                    error, _ = session.resolve_rules_choice(choice["playerId"], choice["id"], option=choice["options"][0])
                elif choice["kind"] == "simultaneous_stack_order":
                    error, _ = session.resolve_rules_choice(
                        choice["playerId"], choice["id"], card_ids=[entry["id"] for entry in choice["_group"]],
                    )
                else:
                    error, _ = session.resolve_rules_choice(choice["playerId"], choice["id"], option="accept")
                self.assertIsNone(error)
                continue
            if session.phase_tracker["turn"] > 1:
                break
            error, _ = session.pass_rules_priority(session.rules_engine["priorityPlayerId"])
            self.assertIsNone(error)
        return p1

    def test_loop_returns_the_tributed_will_to_hand(self):
        p1 = self.play_will_tributing_loop()
        self.assertIn("w", p1["zones"]["hand"])

    def test_loop_returns_the_will_even_once_the_result_is_cleared(self):
        p1 = self.play_will_tributing_loop(clear_result_at_end=True)
        self.assertIn("w", p1["zones"]["hand"])


class SupportEntryLockTests(ReportedCardRulesCase):
    """Pin Down: once resolved, no Manifestation may enter the Confrontation Zone this turn."""

    def veteran_permission_session(self):
        session, p1, _p2 = self.started_session()
        self.put(p1, "graveyard", [WANDERING_VETERAN])
        entry = {
            "id": "perm", "playerId": "p1", "cardId": WANDERING_VETERAN, "fromZone": "graveyard",
            "phaseIds": ["confrontation_reaction"], "asSupport": True, "turn": session.phase_tracker["turn"],
        }
        session.rules_engine["playPermissions"] = [entry]
        return session, entry

    def test_support_permission_is_not_an_action_once_locked(self):
        session, entry = self.veteran_permission_session()
        self.assertTrue(session.rules_play_permission_usable("p1", entry, "confrontation_reaction"))
        session.rules_engine["supportLocks"] = [{"turn": session.phase_tracker["turn"], "playerId": None}]
        self.assertFalse(session.rules_play_permission_usable("p1", entry, "confrontation_reaction"))
        self.assertTrue(session.serialize_for("p1", "player")["rulesEngine"]["supportEntryLocked"])

    def test_permission_outside_its_phase_is_not_an_action(self):
        session, entry = self.veteran_permission_session()
        self.assertFalse(session.rules_play_permission_usable("p1", entry, "end_actions"))


class StalemateEffectsTests(ReportedCardRulesCase):
    """Cards lose their effects in the Stalemate Zone unless their text works from there."""

    def test_stalemate_cards_have_no_effects(self):
        session, _p1, _p2 = self.started_session()
        session.card_rules["fx"] = {"type": "manifestation", "power": 2, "temperaments": ["hollow"]}
        session.card_rules["nubi"] = {
            "type": "manifestation", "power": 2, "temperaments": ["hollow"], "supportFromStalemate": True,
        }
        stalemate = self.field_item("s", "p1", "fx", field_zone="stalemate", x=0, y=0, rotation=0)
        nubilung = self.field_item("n", "p1", "nubi", field_zone="stalemate", x=0, y=0, rotation=0)
        field = self.field_item("f", "p1", "fx", field_zone="interzone", x=0, y=0, rotation=0)
        session.battlefield = [stalemate, nubilung, field]
        self.assertFalse(session.rules_item_effects_active(stalemate))
        self.assertTrue(session.rules_item_effects_active(nubilung))
        self.assertTrue(session.rules_item_effects_active(field))
        items = {entry["id"]: entry for entry in session.serialize_for("p1", "player")["battlefield"]}
        self.assertTrue(items["s"].get("effectsInactive"))
        self.assertFalse(items["n"].get("effectsInactive", False))
        self.assertFalse(items["f"].get("effectsInactive", False))


KAOS_BRO = "b0amfkmb3xewx7x_en"
KARMA_BRO = "9d2y8uy9ut7omyo_en"


class BroErrataTests(ReportedCardRulesCase):
    """Errata: the Bros choose a card on the field controlled by each player and roll a D6 for each."""

    ALL = ReportedCardRulesCase.ALL + (KAOS_BRO, KARMA_BRO)

    def play_bro(self, card_id, rolls):
        session, p1, p2 = self.started_session()
        session.battlefield = [
            self.field_item("mine", "p1", "m-1"), self.field_item("theirs", "p2", "m-2"),
            self.field_item("their-iz", "p2", "m-3", field_zone="interzone"),
        ]
        session.rules_engine["firstManifestationItemIds"] = {"p1": "mine", "p2": "theirs"}
        self.put(p1, "hand", [card_id])
        def play(targets):
            return session.declare_rules_action(
                "p1", "Bro", kind="play_card", source={"cardId": card_id, "zone": "hand"}, as_support=True,
                targets=targets,
            )[0]
        # the cards are chosen as the Bro is about to enter: one controlled by each player
        self.assertIsNotNone(play([
            {"kind": "card", "itemId": "theirs", "cardId": "m-2"},
            {"kind": "card", "itemId": "their-iz", "cardId": "m-3"},
        ]))
        self.assertIsNone(play([
            {"kind": "card", "itemId": "mine", "cardId": "m-1"},
            {"kind": "card", "itemId": "their-iz", "cardId": "m-3"},
        ]))
        self.resolve_top(session)
        trigger = session.rules_engine["actionStack"][-1]
        self.assertEqual(trigger["source"]["cardId"], card_id)
        from unittest import mock
        with mock.patch("session.random.randint", side_effect=list(rolls)):
            resolution = self.resolve_top(session)
        return session, p1, p2, resolution

    def test_kaos_bro_destroys_the_cards_rolling_one_or_six(self):
        session, _p1, p2, _ = self.play_bro(KAOS_BRO, [3, 6])
        self.assertIsNotNone(session.find_battlefield_item("mine"))
        self.assertIsNone(session.find_battlefield_item("their-iz"))
        self.assertIn("m-3", p2["zones"]["graveyard"])

    def test_karma_bro_scores_ten_per_one_or_six(self):
        session, p1, _p2, _ = self.play_bro(KARMA_BRO, [1, 6])
        self.assertEqual(p1["score"], 20)
        self.assertIsNotNone(session.find_battlefield_item("their-iz"))

    def test_the_bros_are_support_only_and_not_first_manifestations(self):
        rules = self.real_rules()
        for card_id in (KAOS_BRO, KARMA_BRO):
            self.assertTrue(rules[card_id].get("supportFromHand"))


class JuLienDisplayTests(ReportedCardRulesCase):
    def test_a_will_turned_manifestation_is_sent_with_its_power(self):
        session, _p1, _p2 = self.started_session()
        session.card_rules["w"] = {"type": "ephemeral_will", "cost": 3, "powerCost": "{G}{G}{G}", "temperaments": ["phlegmatic"]}
        will = self.field_item("w", "p1", "w", isSupport=True, effectsDisabled=True, x=0, y=0, rotation=0,
                               willManifestation={"power": 3, "turn": 1, "onWin": "free_play"})
        session.battlefield = [will]
        entry = session.serialize_for("p1", "player")["battlefield"][0]
        # the client counts it in the Confrontation total like a Manifestation (confrontationPowerOf)
        self.assertTrue(entry["willManifestation"])
        self.assertEqual((entry["effectivePower"], entry["confrontationPower"]), (3, 3))


class MelancholicMirrorTests(ReportedCardRulesCase):
    """Melancholic Mirror offers its exhaust when its controller pays a Tribute through an effect payment."""

    MIRROR = "wx7y64eaa0wlvuk_en"
    ALL = ReportedCardRulesCase.ALL + (MIRROR,)

    def mirror_session(self):
        session, p1, p2 = self.started_session()
        session.battlefield = [
            self.field_item("mir", "p2", self.MIRROR, field_zone="interzone"),
            self.field_item("a", "p1", "m-1"), self.field_item("b", "p2", "m-2"),
        ]
        return session, p1, p2

    def test_effect_payment_tribute_offers_the_mirror(self):
        session, _p1, p2 = self.mirror_session()
        self.put(p2, "hand", ["m-3"])
        session.rules_engine["pendingChoice"] = {
            "id": "pay", "kind": "immediate_effect_payment", "playerId": "p2",
            "payment": "{H}", "controllerId": "p1", "sourceCardId": "m-1",
        }
        error, result = session.resolve_rules_choice("p2", "pay", option="pay", card_ids=["m-3"])
        self.assertIsNone(error)
        self.assertEqual([action["source"]["cardId"] for action in result["triggeredActions"]], [self.MIRROR])
        choice = session.rules_engine["pendingChoice"]
        self.assertEqual((choice["kind"], choice["playerId"]), ("optional_stack_action", "p2"))

    def test_opponent_tribute_does_not_trigger_the_mirror(self):
        session, p1, _p2 = self.mirror_session()
        self.put(p1, "hand", ["m-3"])
        queued = session.queue_rules_tribute_triggers(["m-3"], "p1")
        self.assertNotIn(self.MIRROR, [action["source"]["cardId"] for action in queued])


class MalaleucoFromHandTests(ReportedCardRulesCase):
    """Malaleuco: "pay {B}{B}{B}" from the Hand is a Tribute (Manifestations or Essences), not Essences only."""

    MALALEUCO = "7yu566ip7zuqdoc_en"
    ALL = ReportedCardRulesCase.ALL + (MALALEUCO,)

    def test_tribute_from_hand_puts_it_in_the_interzone(self):
        session, p1, _p2 = self.started_session()
        session.battlefield = [
            self.field_item("a", "p1", "m-1", field_zone="confrontation"),
            self.field_item("b", "p2", "m-2", field_zone="confrontation"),
        ]
        for card_id in ("m-3", "m-4", "m-5"):
            session.card_rules[card_id].update({"temperaments": ["vitreous"], "power": 1})
        self.put(p1, "hand", [self.MALALEUCO, "m-3", "m-4", "m-5"])
        self.assertTrue(session.rules_player_can_act("p1"))
        error, _action = session.declare_rules_action(
            "p1", "Malaleuco", kind="activated_effect",
            source={"cardId": self.MALALEUCO, "zone": "hand"}, ability_id="malaleuco-to-interzone",
            payment_card_ids=["m-3", "m-4", "m-5"],
        )
        self.assertIsNone(error)
        self.resolve_top(session)
        self.assertIn(
            (self.MALALEUCO, "interzone"),
            [(item["cardId"], item.get("fieldZone")) for item in session.battlefield],
        )


class GrimoireWillTests(ReportedCardRulesCase):
    """A Will placed on the Grimoire is playable as if in the hand, so it keeps the player in the step."""

    GRIMOIRE = "omhqwnu5tvwlzzg_en"
    HUSK = "8g5pn3mukkuniog_en"
    TRIBUTE = "gbvulprmpw89ohr_en"
    ALL = ReportedCardRulesCase.ALL + (GRIMOIRE, HUSK, TRIBUTE)

    def test_a_placed_will_counts_as_an_action_and_can_be_played(self):
        session, p1, _p2 = self.started_session(phase_id="end_actions")
        grimoire = self.field_item("g", "p1", self.GRIMOIRE, field_zone="field")
        grimoire["attachedCards"] = [{"cardId": self.HUSK, "ownerId": "p1"}]
        session.battlefield = [
            self.field_item("a", "p1", "m-1", field_zone="confrontation"),
            self.field_item("b", "p2", "m-2", field_zone="confrontation"), grimoire,
        ]
        self.put(p1, "hand", [self.TRIBUTE])
        self.assertTrue(session.rules_player_can_act("p1"))
        error, _action = session.declare_rules_action(
            "p1", "Husk", kind="play_card", source={"cardId": self.HUSK, "zone": "attached", "itemId": "g"},
            payment_card_ids=[self.TRIBUTE],
        )
        self.assertIsNone(error)
