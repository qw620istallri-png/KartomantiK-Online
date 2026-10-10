import ast
import json
import os
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def load_server_catalog():
    source = (ROOT / "server" / "main.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    function = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "load_card_data"
    )
    namespace = {
        "json": json,
        "os": os,
        "PUBLIC_DIR": os.fspath(ROOT / "public"),
    }
    exec(compile(ast.Module(body=[function], type_ignores=[]), "server/main.py", "exec"), namespace)
    return namespace["load_card_data"]()


def build_server_rules(cards, abilities):
    source = (ROOT / "server" / "main.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    functions = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name in {
            "continuous_power_rules_for_card",
            "interzone_tribute_power_for_card",
            "play_phases_for_card",
            "build_card_rules",
        }
    ]
    namespace = {
        "re": re,
        "TRIBUTE_SYMBOL_TEMPERAMENT": {
            "G": "phlegmatic", "B": "vitreous", "P": "melancholic",
            "Y": "capricious", "R": "choleric", "H": "hollow",
            "T": "transcendent",
        },
    }
    exec(compile(ast.Module(body=functions, type_ignores=[]), "server/main.py", "exec"), namespace)
    return namespace["build_card_rules"](cards, abilities)


class CardCatalogTests(unittest.TestCase):
    def test_inner_deserts_is_active_in_the_browser_and_server_catalogs(self):
        beta = json.loads((ROOT / "public" / "cards-data.json").read_text(encoding="utf-8"))
        desert = json.loads((ROOT / "public" / "extensions" / "inner-desert" / "cards.json").read_text(encoding="utf-8"))
        manifest = json.loads((ROOT / "public" / "extensions" / "inner-desert" / "manifest.json").read_text(encoding="utf-8"))

        self.assertEqual(len(beta), 300)
        self.assertEqual(len(desert), 150)
        server_catalog = load_server_catalog()
        self.assertEqual(len(server_catalog), 450)
        self.assertEqual(len({card["id"] for card in server_catalog}), 450)
        self.assertEqual(manifest["status"], "active")
        self.assertTrue(all(
            card["image"].startswith("https://api.kartomantik.com/api/files/")
            and card["image"].endswith(".webp")
            for card in desert
        ))

    def test_inner_deserts_has_complete_deck_metadata_and_server_points(self):
        desert = json.loads((ROOT / "public" / "extensions" / "inner-desert" / "cards.json").read_text(encoding="utf-8"))
        server_catalog = load_server_catalog()
        server_by_id = {card["id"]: card for card in server_catalog}

        self.assertEqual(
            [card["id"] for card in desert],
            [f"inner-deserts-{number:03d}" for number in range(1, 151)],
        )
        self.assertEqual(
            [card["collectionNumber"] for card in desert],
            list(range(301, 451)),
        )
        self.assertTrue(all(card["type"] in {"manifestation", "persistent_will", "ephemeral_will"} for card in desert))
        self.assertTrue(all(isinstance(card["points"], int) for card in desert))
        self.assertTrue(all("placeholder" not in card for card in desert))
        self.assertTrue(all(card.get("name") and card.get("effect") and card.get("translations", {}).get("fr") for card in desert))

        samples = {
            "inner-deserts-001": ("Flem", 5),
            "inner-deserts-002": ("Buuz, the Helicoidal", 10),
            "inner-deserts-134": ("BOB", 50),
            "inner-deserts-150": ("Sever the Ascent", 0),
        }
        desert_by_id = {card["id"]: card for card in desert}
        for card_id, (name, points) in samples.items():
            self.assertEqual(desert_by_id[card_id]["name"], name)
            self.assertEqual(desert_by_id[card_id]["points"], points)
            self.assertEqual(server_by_id[card_id]["points"], points)

        self.assertEqual(
            {card["id"]: card["points"] for card in desert},
            {card["id"]: server_by_id[card["id"]]["points"] for card in desert},
        )

    def test_beginning_turn_cards_use_distinct_trigger_and_permission_models(self):
        abilities = json.loads((ROOT / "public" / "card-abilities.json").read_text(encoding="utf-8"))

        incubator = abilities["skh6d780jne193w_en"][0]
        dunes = abilities["dc44xrlrhikfvlr_en"][0]
        veteran = abilities["iwpmdq754ew0mw7_en"][0]

        self.assertEqual(incubator["trigger"], {"event": "beginning_of_turn", "zone": "interzone"})
        self.assertEqual(dunes["result"]["kind"], "each_player_recovery_choice")
        self.assertNotIn("trigger", veteran)
        self.assertEqual(veteran["playPermission"]["requiredZone"], "graveyard")
        self.assertEqual(veteran["playPermission"]["phaseIds"], ["confrontation_reaction"])
        self.assertTrue(veteran["playPermission"]["asSupport"])
        self.assertEqual(veteran["playPermission"]["temperamentOverride"], "hollow")
        self.assertEqual(veteran["playPermission"]["winAsSupportDestination"], "exile")

    def test_support_entry_watchers_share_the_trigger_catalog(self):
        abilities = json.loads((ROOT / "public" / "card-abilities.json").read_text(encoding="utf-8"))

        mazzolong = abilities["h8xzt2gkg2ax241_en"][0]
        wheel = abilities["cny6n2v2tap5jnm_en"][0]

        self.assertEqual(mazzolong["trigger"], {
            "event": "enters_support", "sourceZone": "interzone", "played": True,
            "eventController": "owner",
        })
        self.assertEqual(mazzolong["result"], {"kind": "draw_owner", "value": 1})
        self.assertEqual(wheel["trigger"], {
            "event": "enters_support", "target": "event_controller",
        })
        self.assertEqual(wheel["targets"], {"kind": "player", "min": 1, "max": 1})
        self.assertEqual(wheel["result"], {"kind": "discard_hand_target", "value": 1})

    def test_targeted_entry_effects_are_encoded_for_direct_board_selection(self):
        abilities = json.loads((ROOT / "public" / "card-abilities.json").read_text(encoding="utf-8"))

        flower = abilities["6xfwhr4h38wvm4u_en"][0]
        repeller = abilities["dxl82w4oxzcg1eg_en"][0]
        chiff = abilities["m3it0ajngl4nlo3_en"][0]

        self.assertEqual(flower["trigger"], {
            "event": "enters_field_zone",
            "zone": "confrontation",
        })
        self.assertEqual(flower["targets"]["maxPower"], 2)
        self.assertTrue(flower["targets"]["excludeEventSource"])
        self.assertEqual(flower["ongoingEffect"], {
            "kind": "power_modifier", "value": 2, "duration": "until_end_of_turn",
        })
        self.assertEqual(repeller["targets"]["controller"], "self")
        self.assertEqual(repeller["result"]["zone"], "hand")
        self.assertTrue(repeller["result"]["restrictPlayUntilEndOfTurn"])
        self.assertTrue(chiff["targets"]["supportOnly"])
        self.assertEqual(chiff["targets"]["controller"], "opponent")

    def test_urocione_encodes_the_reusable_chain_result(self):
        abilities = json.loads((ROOT / "public" / "card-abilities.json").read_text(encoding="utf-8"))
        urocione = abilities["xf03zroy4tigefr_en"][0]

        self.assertEqual(urocione["trigger"], {
            "event": "enters_field", "visibility": "face_up",
        })
        self.assertEqual(urocione["result"], {
            "kind": "chain_from_zone", "zone": "hand", "optional": True,
            "winDestination": "opponent_receptacle",
        })

    def test_chain_cards_survive_result_cleaning(self):
        from server.session import Session
        abilities = json.loads((ROOT / "public" / "card-abilities.json").read_text(encoding="utf-8"))
        looj = Session.clean_rules_trigger_result(abilities["inner-deserts-036"][0]["result"])
        self.assertEqual(
            [entry["result"]["kind"] for entry in looj["chainAbilities"]],
            ["move_source_to_owner_hand", "score_each_opponent"],
        )
        self.assertEqual(
            Session.clean_rules_trigger_result(abilities["mv2vad6gwrfbi1l_en"][0]["result"])["scoreCost"],
            -10,
        )
        self.assertEqual(
            Session.clean_rules_trigger_result(abilities["4rnpxnnceu8x9o9_en"][0]["result"])["players"],
            "each_opponent",
        )
        self.assertEqual(
            Session.clean_rules_trigger_result(abilities["inner-deserts-081"][0]["result"])["preMove"],
            "first_manifestation_to_deck_bottom",
        )
        self.assertEqual(
            Session.clean_rules_trigger_result(abilities["k4m0j5h0l3f61hs_en"][0]["result"])["afterChain"],
            {"kind": "discard_deck_per_base_power"},
        )

    def test_manual_batch_cards_compile_with_timing_and_result_cleaning(self):
        from server.session import Session
        abilities = json.loads((ROOT / "public" / "card-abilities.json").read_text(encoding="utf-8"))
        for card_id in (
            "5xurdeiiyq7kgir_en", "rl4ppd0wsyov7lw_en", "ud9clfoj2c6x96o_en",
            "9yylrq6xancbn0m_en", "i7h2c7ku2gt1yvg_en", "unk0z0mamdx1el5_en",
            "k7dq8ye448xwj54_en", "ynp0apjx1risrpt_en", "yk0ic6ev7465bxo_en",
            "bc3esblt60j7at5_en", "zh4rjhzon9qes6m_en", "f18fccv1k2co206_en",
            "pekwxpsy3c0ro3l_en",
        ):
            result = abilities[card_id][0]["result"]
            cleaned = Session.clean_rules_trigger_result(result)
            if cleaned is None:
                cleaned = Session.clean_rules_action_result(result)
            self.assertIsNotNone(cleaned, card_id)
            self.assertEqual(cleaned["kind"], result["kind"], card_id)
        self.assertEqual(
            Session.clean_rules_action_result(abilities["9yylrq6xancbn0m_en"][0]["result"])["afterDraw"], 1
        )
        self.assertTrue(Session.clean_rules_action_result(abilities["rl4ppd0wsyov7lw_en"][0]["result"])["retained"])
        self.assertTrue(Session.clean_rules_action_result(abilities["pekwxpsy3c0ro3l_en"][0]["result"])["losesEffects"])

    def test_neutralize_encodes_a_stack_card_target(self):
        abilities = json.loads((ROOT / "public" / "card-abilities.json").read_text(encoding="utf-8"))
        neutralize = abilities["2y961kgs0crdict_en"][0]

        self.assertEqual(neutralize["id"], "neutralize-stack-card")
        self.assertEqual(neutralize["action"], "play_card")
        self.assertEqual(neutralize["targets"], {
            "kind": "stack_action", "min": 1, "max": 1,
        })
        self.assertEqual(neutralize["result"], {"kind": "neutralize_stack_action"})

    def test_deny_and_ignore_share_conditional_stack_payment(self):
        abilities = json.loads((ROOT / "public" / "card-abilities.json").read_text(encoding="utf-8"))
        deny = abilities["g0mtnp4zbhwj7cb_en"][0]
        ignore = abilities["ey6fuk5gguasrb0_en"][0]

        self.assertEqual(deny["targets"], {"kind": "stack_action", "min": 1, "max": 1})
        self.assertEqual(deny["result"], {
            "kind": "counter_stack_action_unless_payment",
            "payment": "{H}{H}", "payer": "owner", "mode": "neutralize",
        })
        self.assertEqual(ignore["targets"], {"kind": "stack_effect", "min": 1, "max": 1})
        self.assertEqual(ignore["result"], {
            "kind": "counter_stack_action_unless_payment",
            "payment": "{H}{H}", "payer": "controller", "mode": "cancel",
        })

    def test_imitate_encodes_a_will_only_stack_copy(self):
        abilities = json.loads((ROOT / "public" / "card-abilities.json").read_text(encoding="utf-8"))
        imitate = abilities["q6rha5kz42bkxle_en"][0]

        self.assertEqual(imitate["id"], "copy-target-will-on-stack")
        self.assertEqual(imitate["action"], "play_card")
        self.assertEqual(imitate["targets"], {
            "kind": "stack_action", "min": 1, "max": 1,
            "cardTypes": ["ephemeral_will", "persistent_will"],
        })
        self.assertEqual(imitate["result"], {"kind": "copy_stack_action"})

    def test_server_catalog_derives_static_support_rules_from_card_text(self):
        cards = load_server_catalog()
        abilities = json.loads((ROOT / "public" / "card-abilities.json").read_text(encoding="utf-8"))
        rules = build_server_rules(cards, abilities)
        by_number = {int(card["collectionNumber"]): card["id"] for card in cards}

        wind_sprout = rules[by_number[1]]
        merciful_pago = rules[by_number[3]]
        world_spore = rules[by_number[7]]
        jondo = rules[by_number[19]]
        chiff = rules[by_number[58]]

        self.assertTrue(wind_sprout["supportFromHand"])
        self.assertFalse(wind_sprout["supportFromInterzone"])
        self.assertFalse(wind_sprout["canBeFirstManifestation"])
        self.assertTrue(merciful_pago["supportFromInterzone"])
        self.assertTrue(merciful_pago["supportFromHand"])
        self.assertEqual(merciful_pago["supportWinEffect"], {
            "kind": "opponent_vessel_score", "value": 10,
        })
        self.assertTrue(world_spore["canBeFirstManifestation"])
        self.assertEqual(jondo["supportWinDestination"], "exile")
        self.assertEqual(chiff["supportFromHandCondition"], {
            "kind": "opponent_support_from_interzone_this_turn",
        })
        support_keyword_cards = [
            card for card in cards
            if (card.get("effect") or "").startswith("Support.")
        ]
        self.assertTrue(support_keyword_cards)
        self.assertTrue(all(rules[card["id"]]["supportFromHand"] for card in support_keyword_cards))
        self.assertTrue(all(rules[card["id"]]["supportFromInterzone"] for card in support_keyword_cards))

        self.assertEqual(rules[by_number[12]]["continuousPowerRules"], [
            {"kind": "self_min_confrontation_count", "minimum": 4, "value": 1},
        ])
        self.assertEqual(rules[by_number[29]]["continuousPowerRules"], [
            {"kind": "friendly_support_flat", "value": 1},
        ])
        self.assertEqual(rules[by_number[35]]["continuousPowerRules"], [
            {"kind": "friendly_support_per_other_non_token_confrontation", "value": 1},
        ])
        self.assertEqual(rules[by_number[153]]["continuousPowerRules"], [
            {"kind": "self_any_stalemate", "value": 1},
        ])
        self.assertEqual(rules[by_number[198]]["continuousPowerRules"], [
            {"kind": "self_only_friendly_support", "value": 2},
        ])

    def test_confrontation_outcome_pilots_point_at_the_right_cards_and_abilities(self):
        cards = load_server_catalog()
        abilities = json.loads((ROOT / "public" / "card-abilities.json").read_text(encoding="utf-8"))
        rules = build_server_rules(cards, abilities)
        by_name = {card["name"]: card["id"] for card in cards}
        expected = {
            "Solenero, the Contrite": ("triggeredAbilities", "return-limbo-card-on-loss", "loses_confrontation"),
            "Sallow Thief": ("triggeredAbilities", "retrieve-owned-card-from-opponent-vessel", "wins_confrontation"),
            "Knobbly Colossus": ("triggeredAbilities", "destroy-opponent-will-or-manifestation-on-win", "wins_confrontation"),
            "Borombo, the Mad": ("triggeredAbilities", "destroy-opposing-confrontation-manifestation-on-loss", "loses_confrontation"),
            "Tardigramo": ("triggeredAbilities", "exile-random-vessel-manifestation-on-win", "wins_confrontation"),
            "Floating Dancer": ("triggeredAbilities", "score-per-interzone-manifestation-on-win", "wins_confrontation"),
            "Mind Parasite": ("triggeredAbilities", "chain-from-limbo-with-win-exile", "enters_field_zone"),
        }
        for name, (group, ability_id, event) in expected.items():
            with self.subTest(card=name):
                entry = next(a for a in rules[by_name[name]][group] if a["id"] == ability_id)
                self.assertEqual(entry["trigger"]["event"], event)
        dancer = rules[by_name["Floating Dancer"]]["triggeredAbilities"][0]
        self.assertEqual(dancer["result"], {
            "kind": "score_owner", "value": 5, "perCount": "own_interzone_manifestations",
        })
        thief = rules[by_name["Sallow Thief"]]["triggeredAbilities"][0]
        self.assertEqual(thief["targets"]["container"], "opponent")
        self.assertTrue(thief["optional"])
        mind_parasite = rules[by_name["Mind Parasite"]]["triggeredAbilities"][0]
        self.assertEqual(mind_parasite["result"]["winDestination"], "exile")
        self.assertEqual(mind_parasite["trigger"]["zone"], "confrontation")
        fate = rules[by_name["Reforging Fate"]]["playedAbilities"][0]
        self.assertEqual(fate["targets"]["zones"], ["graveyard"])
        self.assertNotIn("owner", fate["targets"])
        self.assertEqual(fate["result"], {
            "kind": "play_limbo_target_as_support", "winDestination": "exile",
        })

    def test_flem_family_compiles_end_phase_interzone_play_and_interzone_tribute(self):
        cards = load_server_catalog()
        abilities = json.loads((ROOT / "public" / "card-abilities.json").read_text(encoding="utf-8"))
        rules = build_server_rules(cards, abilities)
        flem_family = ("Flem", "Viter", "Mal", "Capry", "Chol")
        by_name = {card["name"]: card for card in cards}
        for name in flem_family:
            with self.subTest(card=name):
                metadata = rules[by_name[name]["id"]]
                self.assertTrue(metadata["endPhaseInterzonePlay"])
                self.assertTrue(metadata["canPayTributeFromInterzone"])
                self.assertEqual(metadata["power"], 1)
        flagged = {
            card["name"] for card in cards if rules[card["id"]]["endPhaseInterzonePlay"]
        }
        self.assertEqual(flagged, set(flem_family))

    def test_power_static_pilots_compile_their_rules_and_tribute_restriction(self):
        cards = load_server_catalog()
        abilities = json.loads((ROOT / "public" / "card-abilities.json").read_text(encoding="utf-8"))
        rules = build_server_rules(cards, abilities)
        by_name = {card["name"]: card["id"] for card in cards}
        expected = {
            "Kelona, the Anchorite": {"kind": "self_per_controller_limbo_card", "value": -1, "floor": -6},
            "Lucerco the Reckless": {"kind": "self_per_opponent_confrontation_manifestation", "value": 1},
            "Vengeful Vilupera": {"kind": "self_per_owned_vessel_manifestation", "value": 1},
            "Prospero of the Bushes": {"kind": "first_manifestation_per_interzone_manifestation", "value": 1},
            "Bell, Ardent Fanatic": {"kind": "only_friendly_confrontation_manifestation", "value": 2},
        }
        for name, rule in expected.items():
            with self.subTest(card=name):
                self.assertEqual(rules[by_name[name]]["continuousPowerRules"], [rule])
        for name in ("Kelona, the Anchorite", "Gigabonblade", "Donmo, the Truth-Bender", "The Slumberer"):
            with self.subTest(card=name):
                self.assertFalse(rules[by_name[name]]["canPayTribute"])
        self.assertTrue(rules[by_name["Wind Sprout"]]["canPayTribute"])

    def test_vanilla_manifestations_have_no_printed_effect_to_automate(self):
        cards = load_server_catalog()
        abilities = json.loads((ROOT / "public" / "card-abilities.json").read_text(encoding="utf-8"))
        rules = build_server_rules(cards, abilities)
        vanilla = [card for card in cards if not (card.get("effect") or "").strip()]
        self.assertEqual(len(vanilla), 16)
        for card in vanilla:
            with self.subTest(card=card["name"]):
                metadata = rules[card["id"]]
                self.assertEqual(card["type"], "manifestation")
                self.assertNotIn(card["id"], abilities)
                self.assertGreaterEqual(metadata["power"], 2)
                self.assertTrue(metadata["canPayTribute"])
                self.assertTrue(metadata["canBeFirstManifestation"])
                self.assertEqual(metadata["continuousPowerRules"], [])
                self.assertEqual(metadata["triggeredAbilities"], [])
                self.assertEqual(metadata["activatedAbilities"], [])

    def test_plea_for_generosity_scores_from_the_targeted_player_board(self):
        cards = load_server_catalog()
        abilities = json.loads((ROOT / "public" / "card-abilities.json").read_text(encoding="utf-8"))
        rules = build_server_rules(cards, abilities)
        plea = next(card for card in cards if card["name"] == "Plea for Generosity")
        played = rules[plea["id"]]["playedAbilities"][0]
        self.assertEqual(played["targets"], {"kind": "player", "min": 1, "max": 1})
        self.assertEqual(played["result"], {
            "kind": "score_owner", "value": 5,
            "perCount": "target_player_confrontation_non_token_manifestations",
        })

    def test_errata_keywords_and_gummo_timing_are_in_the_catalog(self):
        cards = load_server_catalog()
        abilities = json.loads((ROOT / "public" / "card-abilities.json").read_text(encoding="utf-8"))
        rules = build_server_rules(cards, abilities)
        by_number = {int(card["collectionNumber"]): card for card in cards}

        self.assertIn("Upon the End of Recovery", by_number[264]["effect"])
        self.assertNotIn("Before the Revelation", by_number[264]["effect"])
        self.assertTrue(rules[by_number[309]["id"]]["adamant"])
        self.assertTrue(rules[by_number[310]["id"]]["float"])
        self.assertFalse(rules[by_number[301]["id"]]["adamant"])
        self.assertFalse(rules[by_number[301]["id"]]["float"])
        self.assertTrue(rules[by_number[434]["id"]]["persist"])

    def test_persist_pilots_use_the_shared_ongoing_effect(self):
        cards = load_server_catalog()
        abilities = json.loads((ROOT / "public" / "card-abilities.json").read_text(encoding="utf-8"))
        by_number = {int(card["collectionNumber"]): card for card in cards}

        persist = abilities[by_number[89]["id"]][0]
        gornagor = abilities[by_number[220]["id"]][0]

        self.assertEqual(persist["action"], "play_card")
        self.assertEqual(persist["targets"]["fieldZone"], "confrontation")
        self.assertEqual(persist["ongoingEffect"], {
            "kind": "grant_persist", "duration": "until_end_of_turn",
        })
        self.assertEqual(gornagor["tribute"], "{H}{H}{H}")
        self.assertEqual(gornagor["sourceFieldZone"], "confrontation")
        self.assertTrue(gornagor["targets"]["sourceOnly"])
        self.assertEqual(gornagor["ongoingEffect"], persist["ongoingEffect"])

    def test_memory_pilots_use_chain_and_delayed_memory_results(self):
        cards = load_server_catalog()
        abilities = json.loads((ROOT / "public" / "card-abilities.json").read_text(encoding="utf-8"))
        by_number = {int(card["collectionNumber"]): card for card in cards}

        lady = abilities[by_number[23]["id"]][0]
        refrain = abilities[by_number[56]["id"]][0]
        coral = abilities[by_number[65]["id"]][0]

        self.assertEqual(lady["result"], {
            "kind": "chain_from_zone",
            "zone": "deck",
            "optional": False,
            "winDestination": "exile",
            "shuffleAfter": True,
        })
        self.assertEqual(refrain["trigger"], {"event": "used_as_tribute"})
        self.assertEqual(refrain["result"], {
            "kind": "create_effect_memory",
            "memoryKind": "return_from_limbo_end_turn",
            "attachTo": "event_card",
            "opponentPayment": "{H}",
        })
        self.assertEqual(coral["result"], {
            "kind": "create_effect_memory",
            "memoryKind": "return_from_limbo_end_turn",
            "attachTo": "paid_action_source",
            "optional": True,
        })

    def test_deck_batch_uses_shared_reveal_reorder_and_guess_primitives(self):
        cards = load_server_catalog()
        abilities = json.loads((ROOT / "public" / "card-abilities.json").read_text(encoding="utf-8"))
        by_number = {int(card["collectionNumber"]): card for card in cards}

        triad = abilities[by_number[66]["id"]][0]
        dissect = abilities[by_number[347]["id"]][0]
        caress = abilities[by_number[324]["id"]][0]
        jodorosk = abilities[by_number[426]["id"]][0]

        self.assertEqual(triad["result"], {
            "kind": "resolve_top_deck_by_type",
            "manifestation": "chain",
            "will": "draw",
        })
        self.assertEqual(dissect["result"], {
            "kind": "reorder_top_decks",
            "count": 3,
            "eachPlayer": True,
        })
        self.assertTrue(caress["targets"]["enteredThisTurn"])
        self.assertEqual(
            caress["result"]["kind"], "split_targeted_limbo_cards"
        )
        self.assertEqual(jodorosk["trigger"], {
            "event": "enters_field_zone",
            "zone": "confrontation",
        })
        self.assertEqual(jodorosk["targets"]["controller"], "opponent")
        self.assertEqual(jodorosk["result"], {"kind": "guess_top_card"})

    def test_token_batch_uses_shared_creation_copy_and_capture_primitives(self):
        cards = load_server_catalog()
        abilities = json.loads((ROOT / "public" / "card-abilities.json").read_text(encoding="utf-8"))
        by_number = {int(card["collectionNumber"]): card for card in cards}

        jija = abilities[by_number[222]["id"]]
        bratto = abilities[by_number[176]["id"]][0]
        mirror = abilities[by_number[242]["id"]][0]
        recall = abilities[by_number[372]["id"]][0]
        tuxnu = abilities[by_number[424]["id"]][0]

        self.assertEqual(
            jija[0]["result"]["kind"],
            "create_tokens_for_target_interzone_count",
        )
        self.assertTrue(jija[1]["sacrificeTokenCreatedBySource"])
        self.assertEqual(jija[1]["loseScore"], 5)
        self.assertEqual(
            bratto["result"]["kind"], "capture_stalemate_and_copy"
        )
        self.assertEqual(bratto["targets"]["owner"], "opponent")
        self.assertEqual(
            mirror["trigger"]["event"], "manifestation_used_as_tribute"
        )
        self.assertEqual(
            recall["result"]["kind"], "exile_limbos_create_token_copies"
        )
        self.assertEqual(
            tuxnu["trigger"]["event"], "persistent_will_enters_field"
        )

    def test_hand_recovery_batch_uses_shared_limits_and_draw_replacement(self):
        cards = load_server_catalog()
        abilities = json.loads((ROOT / "public" / "card-abilities.json").read_text(encoding="utf-8"))
        rules = build_server_rules(cards, abilities)
        by_number = {int(card["collectionNumber"]): card for card in cards}

        pyramid = abilities[by_number[109]["id"]][0]
        plague = abilities[by_number[123]["id"]][0]
        palm = rules[by_number[444]["id"]]["passiveEffects"][0]
        combhand = rules[by_number[410]["id"]]["passiveEffects"][0]
        kanon = rules[by_number[364]["id"]]["passiveEffects"][0]

        self.assertEqual(
            pyramid["result"]["kind"], "schedule_next_turn_hand_limit"
        )
        self.assertEqual(pyramid["result"]["delta"], -1)
        self.assertEqual(
            plague["result"]["kind"], "choose_points_or_hand_limit"
        )
        self.assertEqual(palm, {
            "kind": "hand_limit_all",
            "value": 6,
            "overflowDestination": "deck_bottom",
        })
        self.assertEqual(
            combhand["kind"], "extra_recovery_draw_per_empty_interzone"
        )
        self.assertEqual(
            kanon["kind"], "replace_opponent_nonrecovery_draw"
        )

    def test_cost_resource_batch_uses_shared_discount_extra_and_retention_rules(self):
        cards = load_server_catalog()
        abilities = json.loads((ROOT / "public" / "card-abilities.json").read_text(encoding="utf-8"))
        rules = build_server_rules(cards, abilities)
        by_number = {int(card["collectionNumber"]): card for card in cards}

        teapot = rules[by_number[62]["id"]]["passiveEffects"][0]
        press = abilities[by_number[241]["id"]]
        inflate = abilities[by_number[418]["id"]][0]
        multicastigate = abilities[by_number[438]["id"]][0]
        subjugate = abilities[by_number[440]["id"]][0]
        cauldron = rules[by_number[294]["id"]]["passiveEffects"][0]

        self.assertEqual(teapot, {
            "kind": "reduce_will_tribute", "value": 1,
        })
        self.assertEqual(press[0]["result"], {
            "kind": "add_counter_source",
            "counter": "Formula", "value": 5,
        })
        self.assertEqual(
            press[1]["passiveEffect"]["kind"],
            "allow_limbo_tribute_with_counter",
        )
        self.assertEqual(
            press[2]["result"]["kind"], "optional_discard_then_draw"
        )
        self.assertEqual(
            inflate["costReduction"]["kind"], "half_first_base_power"
        )
        self.assertEqual(
            inflate["ongoingEffect"]["kind"], "power_set_maximum"
        )
        self.assertEqual(
            multicastigate["extraEssenceByTargetCount"],
            {"targetCount": 2, "amount": 3},
        )
        self.assertEqual(
            subjugate["extraEssenceForTargetPoints"]["maxExtra"], 4
        )
        self.assertEqual(cauldron["kind"], "retain_excess_essence")

    def test_random_batch_uses_server_owned_roll_results(self):
        cards = load_server_catalog()
        abilities = json.loads((ROOT / "public" / "card-abilities.json").read_text(encoding="utf-8"))
        by_number = {int(card["collectionNumber"]): card for card in cards}

        greed = abilities[by_number[243]["id"]]
        plinius = abilities[by_number[260]["id"]][0]
        mutate = abilities[by_number[274]["id"]][0]
        bibi = abilities[by_number[427]["id"]]
        pillarpede = abilities[by_number[428]["id"]][0]

        self.assertEqual(greed[1]["trigger"], {
            "event": "will_played", "eventController": "opponent",
        })
        self.assertEqual(greed[1]["result"]["table"], "greed")
        self.assertEqual(plinius["result"], {
            "kind": "roll_d6_power_by_parity", "even": 4, "odd": -4,
        })
        self.assertEqual(mutate["result"]["table"], "mutation")
        self.assertEqual(bibi[1]["result"]["kind"], "roll_d6_conditional_source")
        self.assertEqual(
            bibi[2]["trigger"]["event"], "wins_confrontation"
        )
        self.assertEqual(
            pillarpede["result"],
            {"kind": "roll_multiple_even_power_odd_discard", "rolls": 5},
        )

    def test_phase_victory_batch_compiles_outcome_and_timing_primitives(self):
        cards = load_server_catalog()
        abilities = json.loads((ROOT / "public" / "card-abilities.json").read_text(encoding="utf-8"))
        rules = build_server_rules(cards, abilities)
        by_number = {int(card["collectionNumber"]): card for card in cards}

        stomper = abilities[by_number[167]["id"]][0]
        sermon = abilities[by_number[223]["id"]][0]
        loudmouth = rules[by_number[150]["id"]]["passiveEffects"][0]
        half_han = rules[by_number[129]["id"]]
        jeovak = abilities[by_number[422]["id"]][0]

        self.assertTrue(stomper["immediate"])
        self.assertEqual(stomper["trigger"]["event"], "revelation")
        self.assertTrue(rules[by_number[167]["id"]]["shuffleWhenPutDeckBottom"])
        self.assertTrue(rules[by_number[25]["id"]]["shuffleWhenPutDeckBottom"])
        self.assertEqual(
            sermon["result"]["kind"], "skip_confrontation_unless_points"
        )
        self.assertEqual(
            loudmouth["kind"], "stalemate_if_last_confrontation_entry"
        )
        self.assertFalse(half_han["canPayTribute"])
        self.assertEqual(
            half_han["passiveEffects"], [{"kind": "negative_score_victory"}]
        )
        self.assertTrue(rules[by_number[422]["id"]]["playOnlyEmptyStack"])
        self.assertEqual(
            jeovak["result"]["kind"], "end_confrontation_relocate_all"
        )

    def test_inner_desert_keywords_are_generalized_beyond_pilots(self):
        cards = load_server_catalog()
        abilities = json.loads((ROOT / "public" / "card-abilities.json").read_text(encoding="utf-8"))
        rules = build_server_rules(cards, abilities)
        by_number = {int(card["collectionNumber"]): card for card in cards}

        adamant_cards = [
            card for card in cards
            if (card.get("effect") or "").startswith("Adamant.")
        ]
        self.assertGreaterEqual(len(adamant_cards), 8)
        self.assertTrue(all(rules[card["id"]]["adamant"] for card in adamant_cards))
        self.assertEqual(
            abilities[by_number[447]["id"]][0]["ongoingEffect"]["kind"],
            "grant_float",
        )
        self.assertEqual(
            abilities[by_number[333]["id"]][0]["ongoingEffect"]["scope"],
            "friendly_manifestations_in_interzone",
        )
        tower = abilities[by_number[345]["id"]]
        tower_by_id = {ability["id"]: ability for ability in tower}
        self.assertEqual(
            tower_by_id["float-with-abstraction-counter"]["passiveEffect"]["kind"],
            "float_with_counter",
        )
        self.assertEqual(
            tower_by_id["friendly-float-power-bonus"]["passiveEffect"]["kind"],
            "friendly_float_power_bonus",
        )
        self.assertEqual(
            abilities[by_number[450]["id"]][0]["ongoingEffect"]["kind"],
            "remove_float",
        )
        gobres = abilities[by_number[388]["id"]][0]
        self.assertEqual(gobres["trigger"]["event"], "before_revelation")
        self.assertEqual(
            gobres["result"]["kind"], "suspend_opponent_hand_will"
        )

    def test_replacement_and_counter_cost_pilots_share_generic_metadata(self):
        cards = load_server_catalog()
        abilities = json.loads((ROOT / "public" / "card-abilities.json").read_text(encoding="utf-8"))
        rules = build_server_rules(cards, abilities)
        by_number = {int(card["collectionNumber"]): card for card in cards}

        self.assertEqual(
            rules[by_number[327]["id"]]["tributeDestination"], "deck_bottom"
        )
        self.assertEqual(
            rules[by_number[374]["id"]]["tributeDestination"], "stalemate"
        )
        blossom = abilities[by_number[39]["id"]]
        self.assertEqual(blossom[0]["result"], {
            "kind": "add_counter_source", "counter": "Petal", "value": 1,
        })
        self.assertEqual(blossom[1]["removeAllCountersFromSource"], "Petal")
        self.assertEqual(
            blossom[1]["ongoingEffect"]["valuePerRemovedCounter"], 1
        )

    def test_eight_family_pilots_compile_shared_rules(self):
        cards = load_server_catalog()
        abilities = json.loads((ROOT / "public" / "card-abilities.json").read_text(encoding="utf-8"))
        rules = build_server_rules(cards, abilities)
        by_number = {int(card["collectionNumber"]): card for card in cards}

        self.assertEqual(
            abilities[by_number[226]["id"]][0]["ongoingEffect"]["scope"],
            "all_manifestations_in_confrontation",
        )
        self.assertCountEqual(
            rules[by_number[192]["id"]]["tributeTemperaments"],
            ["choleric", "vitreous"],
        )
        self.assertCountEqual(
            rules[by_number[194]["id"]]["tributeTemperaments"],
            ["choleric", "phlegmatic"],
        )
        self.assertIn(
            "transcendent",
            rules[by_number[257]["id"]]["tributeTemperaments"],
        )
        self.assertEqual(
            abilities[by_number[232]["id"]][0]["condition"],
            "controller_lost_confrontation",
        )
        self.assertEqual(
            rules[by_number[434]["id"]]["suspensionThresholds"],
            {"deck": 2, "graveyard": 5, "handImmunity": 8, "exile": 11},
        )
        self.assertEqual(
            abilities[by_number[434]["id"]][0]["result"],
            {"kind": "add_counter_source", "counter": "power", "value": 3},
        )

    def test_zero_power_replacement_pilots_compile_as_passives(self):
        cards = load_server_catalog()
        abilities = json.loads((ROOT / "public" / "card-abilities.json").read_text(encoding="utf-8"))
        rules = build_server_rules(cards, abilities)
        by_number = {int(card["collectionNumber"]): card for card in cards}

        self.assertEqual(
            rules[by_number[233]["id"]]["passiveEffects"],
            [{"kind": "sustain_exact_zero"}],
        )
        self.assertEqual(
            rules[by_number[243]["id"]]["passiveEffects"],
            [{"kind": "capture_opponent_exact_zero"}],
        )
        self.assertTrue(rules[by_number[309]["id"]]["adamant"])
        self.assertEqual(
            rules[by_number[309]["id"]]["passiveEffects"],
            [{"kind": "other_power_minimum_base"}],
        )

    def test_hot_potato_uses_generic_source_control_change(self):
        cards = load_server_catalog()
        abilities = json.loads((ROOT / "public" / "card-abilities.json").read_text(encoding="utf-8"))
        by_number = {int(card["collectionNumber"]): card for card in cards}

        hot_potato = abilities[by_number[186]["id"]][0]
        self.assertEqual(hot_potato["targets"], {
            "kind": "player", "min": 1, "max": 1,
            "controller": "opponent",
        })
        self.assertEqual(hot_potato["result"], {
            "kind": "change_source_control",
            "counter": "Burn",
            "counterValue": 1,
        })

    def test_immediate_effect_pilots_use_shared_resolution_flag(self):
        cards = load_server_catalog()
        abilities = json.loads((ROOT / "public" / "card-abilities.json").read_text(encoding="utf-8"))
        by_number = {int(card["collectionNumber"]): card for card in cards}

        pontificate = abilities[by_number[394]["id"]][0]
        extinguish = abilities[by_number[415]["id"]][0]
        kiss = abilities[by_number[416]["id"]][0]

        self.assertTrue(pontificate["immediate"])
        self.assertEqual(pontificate["result"], {
            "kind": "shuffle_hands_then_draw", "value": 4,
        })
        self.assertTrue(extinguish["immediate"])
        self.assertEqual(extinguish["result"], {
            "kind": "exile_all_limbos",
        })
        self.assertTrue(kiss["immediate"])
        self.assertEqual(kiss["result"], {
            "kind": "end_confrontation_unless_payment",
            "payment": "{H}{H}{H}",
            "exileOnDecline": True,
            "reduceWinnerManifestationOnControllerDefeat": True,
        })

    def test_control_family_uses_link_exchange_and_dynamic_burn_costs(self):
        cards = load_server_catalog()
        abilities = json.loads((ROOT / "public" / "card-abilities.json").read_text(encoding="utf-8"))
        by_number = {int(card["collectionNumber"]): card for card in cards}

        thought = abilities[by_number[168]["id"]][0]
        invert = abilities[by_number[185]["id"]][0]
        hot = abilities[by_number[186]["id"]]
        dominate = abilities[by_number[92]["id"]][0]

        self.assertEqual(
            thought["ongoingEffect"]["kind"], "control_link"
        )
        self.assertEqual(
            thought["targets"]["fieldZonesByType"]["persistent_will"],
            ["field"],
        )
        self.assertEqual(len(invert["targetGroups"]), 2)
        self.assertEqual(
            invert["result"], {"kind": "exchange_control_targets"}
        )
        self.assertEqual(
            hot[1]["tributeFromSourceCounter"], "Burn"
        )
        self.assertTrue(hot[1]["result"]["incrementCounter"])
        self.assertEqual(
            hot[2]["result"]["kind"],
            "score_controller_then_destroy_source",
        )
        self.assertTrue(dominate["result"]["rememberAtResolution"])

    def test_characteristic_effect_family_uses_shared_ongoing_kinds(self):
        cards = load_server_catalog()
        abilities = json.loads((ROOT / "public" / "card-abilities.json").read_text(encoding="utf-8"))
        by_number = {int(card["collectionNumber"]): card for card in cards}

        nectar = abilities[by_number[180]["id"]]
        embottle = abilities[by_number[391]["id"]][0]
        obscure = abilities[by_number[343]["id"]][0]
        starkaz = abilities[by_number[169]["id"]][0]
        thorn = abilities[by_number[172]["id"]][0]
        mirror = abilities[by_number[261]["id"]][0]

        self.assertEqual(nectar[0]["ongoingEffect"]["kind"], "lose_effects")
        self.assertEqual(
            nectar[1]["result"]["kind"], "retarget_source_effect"
        )
        self.assertEqual(
            embottle["ongoingEffect"]["duration"], "while_target_on_field"
        )
        self.assertEqual(obscure["resolveSourceTo"], "exile")
        self.assertEqual(obscure["ongoingEffect"]["kind"], "obscure_lock")
        self.assertTrue(starkaz["ongoingEffect"]["excludeSource"])
        self.assertEqual(thorn["reduceSourcePower"], 2)
        self.assertEqual(
            mirror["ongoingEffect"]["kind"], "copy_power_effects"
        )

    def test_protection_family_uses_passive_and_ongoing_protection(self):
        cards = load_server_catalog()
        abilities = json.loads((ROOT / "public" / "card-abilities.json").read_text(encoding="utf-8"))
        by_number = {int(card["collectionNumber"]): card for card in cards}

        self.assertEqual(
            abilities[by_number[28]["id"]][0]["passiveEffect"]["kind"],
            "protect_other_friendly_confrontation",
        )
        self.assertEqual(
            abilities[by_number[79]["id"]][0]["passiveEffect"]["kind"],
            "protect_friendly_interzone_and_wills",
        )
        self.assertEqual(
            abilities[by_number[287]["id"]][0]["passiveEffect"]["kind"],
            "protect_controller_hand",
        )
        self.assertEqual(
            abilities[by_number[322]["id"]][0]["passiveEffect"]["kind"],
            "mutual_opponent_immunity",
        )
        self.assertEqual(
            abilities[by_number[299]["id"]][0]["ongoingEffect"]["kind"],
            "protection",
        )

    def test_previous_partial_cards_have_complete_declarative_catalog_entries(self):
        abilities = json.loads(
            (ROOT / "public" / "card-abilities.json").read_text(
                encoding="utf-8"
            )
        )
        card_ids = {
            "aumzs91roqg77y1_en", "6xfwhr4h38wvm4u_en",
            "skh6d780jne193w_en", "xf03zroy4tigefr_en",
            "h8xzt2gkg2ax241_en", "5liq0tcj7m9ebqr_en",
            "fvk7w9y8xidbuwa_en", "dxl82w4oxzcg1eg_en",
            "24pwcptuijem6tw_en", "yy29lowj25q1z5y_en",
            "m3it0ajngl4nlo3_en", "qn8r98kyqqma972_en",
            "ek1bng9r7vhriwt_en", "q6rha5kz42bkxle_en",
            "ufujqhwlpmaw12y_en", "xav48hincrnl32d_en",
            "7e2ppf4rfgkdfms_en", "jy05w4j8zcuvezq_en",
            "y6g3tex9ypttk8u_en", "pwsjhnw4vpvqgkv_en",
            "cny6n2v2tap5jnm_en", "iwpmdq754ew0mw7_en",
            "ng6w09m6mrjq3xc_en", "pgvrly9397pua77_en",
            "az5wblp5x1div9e_en", "obn1uv72ewxv3y5_en",
            "dc44xrlrhikfvlr_en", "ghb6i1uoiqq12o2_en",
            "0e7afy7zmyhbfal_en", "ryg8e3lgopl6z52_en",
            "zni76s4aabicqag_en", "1q6crbc7nwugrgs_en",
            "dey791sghwx2ee3_en", "5x4aca4v6w9ma1f_en",
            "inner-deserts-022", "inner-deserts-045",
            "inner-deserts-116", "inner-deserts-134",
            "inner-deserts-146",
        }
        self.assertEqual(len(card_ids), 39)
        self.assertTrue(all(abilities.get(card_id) for card_id in card_ids))

        psychowall = {
            ability["id"]: ability
            for ability in abilities["inner-deserts-022"]
        }
        self.assertTrue(
            psychowall["any-player-destroy-psychowall"]["anyPlayer"]
        )
        self.assertEqual(
            psychowall["any-player-destroy-psychowall"]["result"],
            {"kind": "destroy_source"},
        )

        tower = {
            ability["id"]: ability
            for ability in abilities["inner-deserts-045"]
        }
        self.assertEqual(
            tower["enter-with-abstraction-counters"]["result"]["value"], 3
        )
        self.assertEqual(
            tower["move-abstraction-counter"]["result"]["kind"],
            "move_counter",
        )
        self.assertEqual(
            tower["move-abstraction-counter"]["targetGroups"][0][
                "minCounters"
            ],
            1,
        )

        flaying = {
            ability["id"]: ability
            for ability in abilities["y6g3tex9ypttk8u_en"]
        }
        self.assertEqual(
            flaying["flaying-jaw-retarget"]["result"]["effectKind"],
            "power_modifier",
        )
        self.assertTrue(flaying["flaying-jaw-retarget"]["exhaustSource"])
        self.assertEqual(
            flaying["flaying-jaw-retarget"]["phaseIds"], ["end_actions"]
        )

        mimer = abilities["pwsjhnw4vpvqgkv_en"][0]
        self.assertEqual(mimer["targets"]["controller"], "opponent")
        self.assertTrue(mimer["targets"]["firstManifestationOnly"])
        self.assertTrue(
            abilities["ufujqhwlpmaw12y_en"][0]["targets"]["supportOnly"]
        )
        self.assertEqual(
            abilities["inner-deserts-146"][0]["targets"]["kind"],
            "card_or_stack_action",
        )

    def test_interzone_support_batch_has_compiled_rules_and_abilities(self):
        cards = load_server_catalog()
        abilities = json.loads(
            (ROOT / "public" / "card-abilities.json").read_text(
                encoding="utf-8"
            )
        )
        rules = build_server_rules(cards, abilities)

        self.assertTrue(rules["inner-deserts-031"]["supportFromHand"])
        self.assertTrue(rules["inner-deserts-031"]["supportFromInterzone"])
        self.assertTrue(
            rules["jh2nsqxr9x2ii1l_en"]["canPayTributeFromInterzone"]
        )
        self.assertEqual(
            rules["jh2nsqxr9x2ii1l_en"]["interzoneTributePower"], 2
        )
        self.assertEqual(
            rules["inner-deserts-051"]["supportWinDestination"], "exile"
        )
        self.assertEqual(
            rules["xw1fbhs6hwz6thc_en"]["lossDestination"], "winner_interzone"
        )
        self.assertEqual(rules["inner-deserts-132"]["lossDestination"], "own_interzone")
        self.assertTrue(rules["93gvk0hy12hylm6_en"]["vesselEntryRoll"])
        self.assertEqual(rules["3oiehnpbub1byg6_en"]["supportWhenNoCounter"], "Block")
        expected = {
            "0kcy08a6jd7ez7k_en",
            "inner-deserts-010",
            "inner-deserts-011",
            "inner-deserts-051",
            "inner-deserts-058",
            "inner-deserts-080",
            "inner-deserts-105",
            "inner-deserts-107",
            "inner-deserts-125",
        }
        self.assertTrue(all(abilities.get(card_id) for card_id in expected))
        haltan = {
            ability["id"]: ability
            for ability in abilities["inner-deserts-125"]
        }
        self.assertTrue(
            haltan[
                "exhaust-sacrifice-to-prevent-point-changes"
            ]["immediate"]
        )
        self.assertEqual(
            abilities["inner-deserts-080"][0]["targets"]["kind"],
            "stack_item",
        )

    def test_destroy_uses_field_zone_specific_targeting(self):
        abilities = json.loads(
            (ROOT / "public" / "card-abilities.json").read_text(
                encoding="utf-8"
            )
        )
        destroy = abilities["f2cj2wys3jhbzci_en"][0]

        self.assertEqual(
            destroy["result"],
            {
                "kind": "move_target",
                "zone": "graveyard",
                "position": "top",
                "reason": "destroy",
            },
        )
        self.assertEqual(
            destroy["targets"]["fieldZonesByType"]["manifestation"],
            ["interzone"],
        )
        self.assertEqual(
            destroy["targets"]["fieldZonesByType"]["persistent_will"],
            ["field"],
        )

    def test_easy_manual_batches_compile_to_existing_rule_families(self):
        cards = load_server_catalog()
        abilities = json.loads(
            (ROOT / "public" / "card-abilities.json").read_text(
                encoding="utf-8"
            )
        )
        rules = build_server_rules(cards, abilities)

        for card_id in {
            "inner-deserts-102", "inner-deserts-006",
            "inner-deserts-030", "inner-deserts-054",
            "inner-deserts-078",
        }:
            self.assertTrue(rules[card_id]["canPayTributeFromInterzone"])
            self.assertEqual(rules[card_id]["interzoneTributePower"], 2)

        expected_abilities = {
            "tzizek39tj8rqq5_en",
            "5hpmlq50blbf3y6_en",
            "inner-deserts-098",
            "ivx8jr1o6utm32a_en",
            "0coh7nrbvcvan1i_en",
            "uin3dxt3bc50z6q_en",
            "u9blfiufeef8djr_en",
            "72zvsiuky5ytolh_en",
            "nzyipkk7u6vrd4a_en",
            "inner-deserts-145",
            "inner-deserts-139",
            "nbms08jb9t9eqbh_en",
            "874751ghrblya5j_en",
            "mwby5hp16qdnjpj_en",
            "i6oj7gtnkfd1jja_en",
            "nupb1i59d98g3md_en",
            "4naoqbqz6ebozj5_en",
            "erkwir53va9m8gm_en",
            "265f4wdooq43pjn_en",
            "a058t24med4h5nx_en",
            "rqvzo3iji2a1l65_en",
            "m2l3v60n0iakrm2_en",
            "d6jip43i66i34xk_en",
            "fknxa83uens94ju_en",
            "16hmmz3fw32r27q_en",
            "8xi4zh0ekdl42me_en",
            "inner-deserts-014",
            "9ypw4x4igfon1qi_en",
            "y4muuingw5y9l7z_en",
            "wfxxi0znaojxiti_en",
            "5enwyodanyu1it8_en",
            "gybb0ktsth7clz5_en",
            "j2a7x783j5ql0ab_en",
        }
        self.assertTrue(
            all(abilities.get(card_id) for card_id in expected_abilities)
        )

        for card_id in (
            "erkwir53va9m8gm_en", "265f4wdooq43pjn_en", "a058t24med4h5nx_en",
            "rqvzo3iji2a1l65_en", "m2l3v60n0iakrm2_en",
        ):
            self.assertTrue(rules[card_id]["playBeforeRevelation"], card_id)
            self.assertTrue(rules[card_id]["activatedAbilities"] or card_id == "rqvzo3iji2a1l65_en")
        self.assertFalse(rules["inner-deserts-139"].get("playBeforeRevelation"))
        self.assertTrue(rules["inner-deserts-095"]["reactionEmptyStackOnly"])
        self.assertEqual(
            rules["inner-deserts-112"]["continuousPowerRules"][0],
            {"kind": "self_per_opponent_confrontation_total", "value": 1, "cap": 3},
        )
        self.assertEqual(
            rules["n9olbthp7vtmypo_en"]["continuousPowerRules"][0]["kind"],
            "friendly_confrontation_flat",
        )
        self.assertEqual(
            rules["twn0cer0tjbw09n_en"]["continuousPowerRules"][0]["kind"],
            "self_per_controller_hand_card",
        )
        self.assertEqual(
            rules["kaw822pzpzd2l9k_en"]["continuousPowerRules"][0]["kind"],
            "self_per_stalemate_manifestation",
        )
        self.assertEqual(
            rules["86nfr2vhox3l6y2_en"]["continuousPowerRules"][0]["kind"],
            "self_per_controller_limbo_manifestation",
        )

        rally = abilities["5q6t7i5pzctbi8s_en"][0]
        self.assertEqual(
            rally["optionalExtraEssence"],
            {"temperament": "hollow", "max": 20},
        )
        self.assertEqual(
            rally["result"]["kind"],
            "create_support_tokens_from_optional_extra_essence",
        )


if __name__ == "__main__":
    unittest.main()
