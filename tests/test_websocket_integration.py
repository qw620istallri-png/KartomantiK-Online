import asyncio
import json
import os
import sys
import unittest

from websockets.asyncio.client import connect
from websockets.asyncio.server import serve


SERVER_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "server"))
if SERVER_DIR not in sys.path:
    sys.path.insert(0, SERVER_DIR)

import main as server_main
from session import ADVANCED_PHASES


class WebSocketRulesIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        server_main.sessions.clear()
        server_main.connections.clear()
        self.server = await serve(
            server_main.handler,
            "127.0.0.1",
            0,
            process_request=server_main.process_request,
            compression=None,
        )
        port = self.server.sockets[0].getsockname()[1]
        self.uri = f"ws://127.0.0.1:{port}/ws"
        self.clients = []
        self.ws1, joined = await self.join(
            {
                "type": "join",
                "createNew": True,
                "rulesBeta": True,
                "name": "P1",
                "clientId": "p1",
            }
        )
        self.code = joined["codePlayer"]
        self.ws2, _joined = await self.join(
            {
                "type": "join",
                "code": self.code,
                "name": "P2",
                "clientId": "p2",
            }
        )
        self.session = server_main.sessions[self.code]
        await self.receive_until(self.ws1, lambda message: message.get("type") == "state")
        await self.receive_until(self.ws2, lambda message: message.get("type") == "state")

    async def asyncTearDown(self):
        for websocket in self.clients:
            await websocket.close()
        await asyncio.sleep(0)
        self.server.close()
        await self.server.wait_closed()
        server_main.sessions.clear()
        server_main.connections.clear()

    async def join(self, payload):
        websocket = await connect(self.uri)
        self.clients.append(websocket)
        await websocket.send(json.dumps(payload))
        joined = await self.receive_until(
            websocket, lambda message: message.get("type") == "joined"
        )
        return websocket, joined

    async def receive_until(self, websocket, predicate, limit=40):
        for _index in range(limit):
            message = json.loads(await asyncio.wait_for(websocket.recv(), timeout=2))
            if predicate(message):
                return message
        self.fail("Expected WebSocket message was not received.")

    async def send(self, websocket, payload):
        await websocket.send(json.dumps(payload))

    def prepare_active_rules(self, phase_id, priority="p1"):
        rules = self.session.rules_engine
        rules["deckConfirmedPlayerIds"] = ["p1", "p2"]
        rules["readyPlayerIds"] = ["p1", "p2"]
        rules["priorityPlayerId"] = priority
        rules["priorityPasses"] = []
        rules["pendingChoice"] = None
        rules["autoSkipPhases"] = False
        self.session.phase_tracker["index"] = ADVANCED_PHASES.index(phase_id)

    async def test_splendor_gem_is_optional_and_broadcasts_without_passing_priority(self):
        self.prepare_active_rules("confrontation_reaction")
        self.session.rules_engine["firstManifestationComplete"] = True
        self.session.battlefield = [{
            "id": "splendor", "cardId": "inner-deserts-143", "ownerId": "p1",
            "faceUp": True, "fieldZone": "field", "chosenTemperament": "choleric",
            "counters": {"Gem": 2}, "x": 0, "y": 0, "rotation": 0,
        }]
        await self.send(self.ws1, {
            "type": "spend_counter_essence", "itemId": "splendor",
            "abilityId": "splendor-spends-a-gem-as-excess-essence",
        })
        state = await self.receive_until(self.ws1, lambda message: message.get("type") == "state" and any(
            entry.get("details", {}).get("kind") == "counter_essence"
            for entry in message.get("recentLog", [])
        ))
        self.assertEqual(state["battlefield"][0]["counters"]["Gem"], 1)
        self.assertEqual(state["tokens"][0]["counters"]["essence"], 1)
        self.assertEqual(state["rulesEngine"]["priorityPlayerId"], "p1")
        self.assertFalse(state["rulesEngine"]["actionStack"])
        peer = await self.receive_until(self.ws2, lambda message: message.get("type") == "state" and any(
            entry.get("details", {}).get("kind") == "counter_essence"
            for entry in message.get("recentLog", [])
        ))
        self.assertEqual(peer["tokens"][0]["counters"]["essence"], 1)

        # A requested payment may belong to the non-priority player. Converting
        # their Gem must pass the socket guard without completing that choice.
        self.session.status = "active"
        self.session.rules_engine.update(priorityPlayerId="p2", pendingChoice={
            "id": "requested-payment", "kind": "effect_payment", "playerId": "p1",
            "payment": "{R}{R}", "sourceCardId": "inner-deserts-143",
        })
        await self.send(self.ws1, {"type": "spend_counter_essence", "itemId": "splendor", "abilityId": "splendor-spends-a-gem-as-excess-essence"})
        paid = await self.receive_until(self.ws1, lambda message: message.get("type") == "state" and sum(
            token.get("counters", {}).get("essence", 0) for token in message.get("tokens", [])
        ) == 2)
        self.assertEqual(paid["rulesEngine"]["pendingChoice"]["id"], "requested-payment")
        self.assertEqual(paid["rulesEngine"]["priorityPlayerId"], "p2")

    async def test_multicolour_will_uses_the_requested_white_essence_allocation(self):
        self.prepare_active_rules("end_actions")
        self.session.rules_engine["firstManifestationComplete"] = True
        self.session.card_rules.update({
            "white-choice-will": {"type": "persistent_will", "powerCost": "{R}{G}", "cost": 2, "temperaments": ["choleric", "phlegmatic"]},
            "white-choice-red": {"type": "manifestation", "power": 1, "temperaments": ["choleric"]},
            "white-choice-green": {"type": "manifestation", "power": 1, "temperaments": ["phlegmatic"]},
        })
        player = self.session.players["p1"]
        player["zones"]["hand"] = ["white-choice-will", "white-choice-red", "white-choice-green"]
        player["zoneOwners"]["hand"] = {card_id: "p1" for card_id in player["zones"]["hand"]}
        self.session.add_rules_excess_essence("p1", [{"temperament": "transcendent", "amount": 1}])
        await self.send(self.ws1, {
            "type": "declare_rules_action", "label": "Chosen white payment", "kind": "play_card",
            "source": {"cardId": "white-choice-will", "zone": "hand"},
            "paymentCardIds": ["white-choice-red"], "transcendentPayment": {"phlegmatic": 1},
        })
        state = await self.receive_until(self.ws1, lambda message: message.get("type") == "state" and any(
            entry.get("type") == "rules_action_declared" and entry.get("details", {}).get("label") == "Chosen white payment"
            for entry in message.get("recentLog", [])
        ))
        declared = next(entry for entry in state["recentLog"] if entry["type"] == "rules_action_declared" and entry["details"].get("label") == "Chosen white payment")
        self.assertEqual(declared["details"]["cost"]["essenceSpent"][0]["pays"], "phlegmatic")
        self.assertEqual(player["zones"]["hand"], ["white-choice-green"])
        self.assertIn("white-choice-red", player["zones"]["graveyard"])

    async def test_invalid_numeric_payload_returns_error_and_keeps_connection_open(self):
        await self.ws1.send('{"type":"add_token","x":NaN,"y":0}')
        error = await self.receive_until(
            self.ws1, lambda message: message.get("type") == "error"
        )
        self.assertEqual(error["message"], "Invalid numeric value.")

        await self.send(self.ws1, {"type": "chat_message", "text": "still connected"})
        chat = await self.receive_until(
            self.ws1,
            lambda message: message.get("type") == "chat_message"
            and message.get("text") == "still connected",
        )
        self.assertEqual(chat["byId"], "p1")

    async def test_non_object_json_returns_error_and_keeps_connection_open(self):
        await self.ws1.send("[]")
        error = await self.receive_until(
            self.ws1, lambda message: message.get("type") == "error"
        )
        self.assertEqual(error["message"], "Invalid message.")

        await self.send(self.ws1, {"type": "set_activity", "activity": "ready"})
        state = await self.receive_until(
            self.ws1,
            lambda message: message.get("type") == "state"
            and message["players"]["p1"].get("activity") == "ready",
        )
        self.assertEqual(state["players"]["p1"]["activity"], "ready")

    async def test_passing_with_nothing_to_play_skips_the_empty_phases(self):
        self.prepare_active_rules("end_actions")
        self.session.rules_engine["autoSkipPhases"] = True
        self.session.rules_engine["firstManifestationComplete"] = True
        for player_id in ("p1", "p2"):
            self.session.players[player_id]["zones"]["hand"] = []
        turn = self.session.phase_tracker["turn"]
        await self.send(self.ws1, {"type": "pass_priority", "passed": True})
        state = await self.receive_until(
            self.ws1,
            lambda message: message.get("type") == "state"
            and message["phaseTracker"]["turn"] == turn + 1,
        )
        self.assertNotEqual(
            state["phaseTracker"]["index"], ADVANCED_PHASES.index("end_actions")
        )

    async def test_first_manifestations_stay_hidden_through_before_revelation(self):
        self.prepare_active_rules("confrontation_choose")
        first_p1 = server_main.CARD_ID_BY_NUMBER[2]
        first_p2 = server_main.CARD_ID_BY_NUMBER[190]
        for player_id, card_id in (("p1", first_p1), ("p2", first_p2)):
            player = self.session.players[player_id]
            player["zones"]["hand"] = [card_id]
            player["zoneOwners"]["hand"] = {card_id: player_id}

        await self.send(self.ws1, {
            "type": "place_card",
            "ownerId": "p1",
            "fromZone": "hand",
            "cardId": first_p1,
            "x": 500,
            "y": 700,
        })
        await self.receive_until(
            self.ws1,
            lambda message: message.get("type") == "state"
            and "p1" in message["rulesEngine"]["firstManifestationItemIds"],
        )
        await self.send(self.ws2, {
            "type": "place_card",
            "ownerId": "p2",
            "fromZone": "hand",
            "cardId": first_p2,
            "x": 900,
            "y": 500,
        })
        # Dropping the First Manifestation validates it: no separate click, so
        # the second drop already moves the game to Before Revelation.
        before = await self.receive_until(
            self.ws2,
            lambda message: message.get("type") == "state"
            and message["phaseTracker"]["index"]
            == ADVANCED_PHASES.index("confrontation_before_revelation"),
        )
        self.assertEqual(
            sorted(before["rulesEngine"]["firstManifestationValidatedPlayerIds"]),
            ["p1", "p2"],
        )
        self.assertTrue(all(
            not item["faceUp"] for item in before["battlefield"]
            if item.get("id") in before["rulesEngine"]["firstManifestationItemIds"].values()
        ))

        await self.send(self.ws1, {"type": "pass_priority", "passed": True})
        await self.receive_until(
            self.ws1,
            lambda message: message.get("type") == "state"
            and message["rulesEngine"]["priorityPasses"] == ["p1"],
        )
        await self.send(self.ws2, {"type": "pass_priority", "passed": True})
        revealed = await self.receive_until(
            self.ws2,
            lambda message: message.get("type") == "state"
            and message["phaseTracker"]["index"]
            == ADVANCED_PHASES.index("confrontation_reveal"),
        )
        self.assertTrue(all(
            item["faceUp"] for item in revealed["battlefield"]
            if item.get("id") in revealed["rulesEngine"]["firstManifestationItemIds"].values()
        ))

    async def test_declared_will_resolves_through_real_priority_messages(self):
        self.prepare_active_rules("confrontation_reaction")
        self.session.rules_engine["firstManifestationComplete"] = True
        strengthen = server_main.CARD_ID_BY_NUMBER[266]
        tribute = server_main.CARD_ID_BY_NUMBER[190]
        target_card = server_main.CARD_ID_BY_NUMBER[2]
        player = self.session.players["p1"]
        player["zones"]["hand"] = [strengthen, tribute]
        player["zoneOwners"]["hand"] = {
            strengthen: "p1",
            tribute: "p1",
        }
        target = {
            "id": "target",
            "ownerId": "p1",
            "cardId": target_card,
            "x": 700,
            "y": 700,
            "faceUp": True,
            "rotation": 0,
            "counters": {},
            "fieldZone": "confrontation",
        }
        self.session.battlefield = [target]
        ability_id = server_main.CARD_ABILITIES[strengthen][0]["id"]

        await self.send(self.ws1, {
            "type": "declare_rules_action",
            "label": "Strengthen",
            "kind": "play_card",
            "source": {"cardId": strengthen, "zone": "hand"},
            "targets": [{
                "kind": "card",
                "itemId": "target",
                "cardId": target_card,
            }],
            "paymentCardIds": [tribute],
            "abilityId": ability_id,
        })
        stacked = await self.receive_until(
            self.ws1,
            lambda message: message.get("type") == "state"
            and len(message["rulesEngine"]["actionStack"]) == 1,
        )
        self.assertEqual(
            stacked["rulesEngine"]["actionStack"][0]["source"]["cardId"],
            strengthen,
        )

        await self.send(self.ws2, {"type": "pass_priority", "passed": True})
        await self.receive_until(
            self.ws2,
            lambda message: message.get("type") == "state"
            and message["rulesEngine"]["priorityPasses"] == ["p2"],
        )
        await self.send(self.ws1, {"type": "pass_priority", "passed": True})
        resolved = await self.receive_until(
            self.ws1,
            lambda message: message.get("type") == "state"
            and not message["rulesEngine"]["actionStack"]
            and len(message["rulesEngine"]["ongoingEffects"]) == 1,
        )
        self.assertEqual(
            resolved["rulesEngine"]["ongoingEffects"][0]["target"]["itemId"],
            "target",
        )
        self.assertEqual(
            self.session.rules_manifestation_characteristics(target)["power"],
            5,
        )

    async def test_immediate_will_resolves_in_declaration_message(self):
        self.prepare_active_rules("confrontation_reaction")
        self.session.rules_engine["firstManifestationComplete"] = True
        pontificate = server_main.CARD_ID_BY_NUMBER[394]
        tribute = server_main.CARD_ID_BY_NUMBER[151]
        p1_extra = server_main.CARD_ID_BY_NUMBER[2]
        p2_extra = server_main.CARD_ID_BY_NUMBER[190]
        p1 = self.session.players["p1"]
        p2 = self.session.players["p2"]
        p1["zones"]["hand"] = [pontificate, tribute, p1_extra]
        p1["zoneOwners"]["hand"] = {
            card_id: "p1" for card_id in p1["zones"]["hand"]
        }
        p2["zones"]["hand"] = [p2_extra]
        p2["zoneOwners"]["hand"] = {p2_extra: "p2"}
        p1_deck = [server_main.CARD_ID_BY_NUMBER[number] for number in (3, 4, 5, 6)]
        p2_deck = [server_main.CARD_ID_BY_NUMBER[number] for number in (191, 192, 193, 194)]
        p1["zones"]["deck"] = p1_deck
        p1["zoneOwners"]["deck"] = {card_id: "p1" for card_id in p1_deck}
        p2["zones"]["deck"] = p2_deck
        p2["zoneOwners"]["deck"] = {card_id: "p2" for card_id in p2_deck}
        ability_id = server_main.CARD_ABILITIES[pontificate][0]["id"]

        await self.send(self.ws1, {
            "type": "declare_rules_action",
            "label": "Pontificate Heresy",
            "kind": "play_card",
            "source": {"cardId": pontificate, "zone": "hand"},
            "targets": [],
            "paymentCardIds": [tribute],
            "abilityId": ability_id,
        })
        state = await self.receive_until(
            self.ws1,
            lambda message: message.get("type") == "state"
            and message["phaseTracker"]["index"]
            == ADVANCED_PHASES.index("confrontation_reaction"),
        )
        self.assertEqual(state["rulesEngine"]["actionStack"], [])
        self.assertEqual(
            len(state["players"]["p1"]["zones"]["hand"]["cards"]), 4
        )
        self.assertEqual(state["players"]["p2"]["zones"]["hand"]["count"], 4)
        self.assertEqual(state["rulesEngine"]["priorityPasses"], [])
        self.assertIn(pontificate, p1["zones"]["graveyard"])
        resolved_logs = [
            entry for entry in self.session.log
            if entry["type"] == "rules_action_resolved"
        ]
        self.assertTrue(resolved_logs[-1]["details"]["immediate"])

    async def test_suspension_choice_keeps_hand_private_and_resolves_over_websocket(self):
        self.prepare_active_rules("confrontation_before_revelation")
        gobres = server_main.CARD_ID_BY_NUMBER[388]
        target_will = server_main.CARD_ID_BY_NUMBER[267]
        source = {
            "id": "gobres", "ownerId": "p1", "cardId": gobres,
            "x": 600, "y": 700, "faceUp": True, "rotation": 0,
            "counters": {}, "fieldZone": "interzone",
        }
        self.session.battlefield = [source]
        p2 = self.session.players["p2"]
        p2["zones"]["hand"] = [target_will]
        p2["zoneOwners"]["hand"] = {target_will: "p2"}
        required = self.session.apply_rules_action_result({
            "controllerId": "p1",
            "source": {"cardId": gobres, "itemId": "gobres"},
            "targets": [{"kind": "player", "playerId": "p2"}],
            "ability": {"result": {
                "kind": "suspend_opponent_hand_will"
            }},
        })
        self.assertEqual(required["choiceKind"], "suspend_hand_will")
        await server_main.broadcast_state(self.session)
        owner_state = await self.receive_until(
            self.ws2,
            lambda message: message.get("type") == "state"
            and message["rulesEngine"]["pendingChoice"] is not None,
        )
        opponent_state = await self.receive_until(
            self.ws1,
            lambda message: message.get("type") == "state"
            and message["rulesEngine"]["pendingChoice"] is not None,
        )
        self.assertEqual(
            owner_state["rulesEngine"]["pendingChoice"]["cardIds"],
            [target_will],
        )
        self.assertNotIn(
            "cardIds", opponent_state["rulesEngine"]["pendingChoice"]
        )

        await self.send(self.ws2, {
            "type": "resolve_rules_choice",
            "choiceId": owner_state["rulesEngine"]["pendingChoice"]["id"],
            "cardIds": [target_will],
        })
        resolved = await self.receive_until(
            self.ws2,
            lambda message: message.get("type") == "state"
            and message["rulesEngine"]["pendingChoice"] is None
            and len(message["rulesEngine"]["suspendedCards"]) == 1,
        )
        self.assertEqual(
            resolved["rulesEngine"]["suspendedCards"][0]["cardId"],
            target_will,
        )
        self.assertEqual(p2["zones"]["hand"], [])

    async def test_hidden_chain_choice_is_filtered_private_and_selectable(self):
        self.prepare_active_rules("confrontation_reaction")
        manifestation = server_main.CARD_ID_BY_NUMBER[1]
        second_manifestation = server_main.CARD_ID_BY_NUMBER[2]
        will = server_main.CARD_ID_BY_NUMBER[267]
        p1 = self.session.players["p1"]
        p1["zones"]["deck"] = [
            manifestation, will, second_manifestation,
        ]
        p1["zoneOwners"]["deck"] = {
            manifestation: "p1",
            will: "p1",
            second_manifestation: "p1",
        }
        required = self.session.apply_rules_action_result({
            "controllerId": "p1",
            "source": {"cardId": "lady"},
            "ability": {"result": {
                "kind": "chain_from_zone",
                "zone": "deck",
                "optional": False,
                "shuffleAfter": True,
            }},
        })
        self.assertEqual(required["choiceKind"], "chain_manifestation")
        await server_main.broadcast_state(self.session)
        owner_state = await self.receive_until(
            self.ws1,
            lambda message: message.get("type") == "state"
            and message["rulesEngine"]["pendingChoice"] is not None,
        )
        opponent_state = await self.receive_until(
            self.ws2,
            lambda message: message.get("type") == "state"
            and message["rulesEngine"]["pendingChoice"] is not None,
        )
        choice = owner_state["rulesEngine"]["pendingChoice"]
        self.assertEqual(
            choice["cardIds"], [manifestation, second_manifestation]
        )
        self.assertNotIn(
            "cardIds", opponent_state["rulesEngine"]["pendingChoice"]
        )

        await self.send(self.ws1, {
            "type": "resolve_rules_choice",
            "choiceId": choice["id"],
            "cardIds": [second_manifestation],
            "placement": {"x": 400, "y": 500},
        })
        resolved = await self.receive_until(
            self.ws1,
            lambda message: message.get("type") == "state"
            and message["rulesEngine"]["pendingChoice"] is None
            and any(
                item.get("cardId") == second_manifestation
                and item.get("isChained")
                for item in message["battlefield"]
            ),
        )
        chained = next(
            item for item in resolved["battlefield"]
            if item.get("cardId") == second_manifestation
        )
        # chained cards are laid out on the first free slot of their controller's Confrontation row
        self.assertEqual((chained["x"], chained["y"]), (445.0, 800.0))

    async def test_opponent_chain_choice_is_owned_by_the_chaining_player(self):
        self.prepare_active_rules("confrontation_reaction")
        manifestation = server_main.CARD_ID_BY_NUMBER[1]
        p2 = self.session.players["p2"]
        p2["zones"]["hand"] = [manifestation]
        p2["zoneOwners"]["hand"] = {manifestation: "p2"}
        required = self.session.apply_rules_action_result({
            "controllerId": "p1",
            "source": {"cardId": "lady"},
            "ability": {"result": {
                "kind": "chain_from_zone", "zone": "hand", "optional": False,
                "players": "each_opponent",
            }},
        })
        self.assertEqual(required["playerId"], "p2")
        await server_main.broadcast_state(self.session)
        opponent_state = await self.receive_until(
            self.ws2,
            lambda message: message.get("type") == "state"
            and message["rulesEngine"]["pendingChoice"] is not None,
        )
        choice = opponent_state["rulesEngine"]["pendingChoice"]
        self.assertEqual(choice["playerId"], "p2")
        self.assertFalse(choice["optional"])
        await self.send(self.ws2, {
            "type": "resolve_rules_choice",
            "choiceId": choice["id"],
            "cardIds": [manifestation],
            "placement": {"x": 300, "y": 300},
        })
        resolved = await self.receive_until(
            self.ws2,
            lambda message: message.get("type") == "state"
            and message["rulesEngine"]["pendingChoice"] is None
            and any(
                item.get("cardId") == manifestation and item.get("isChained")
                for item in message["battlefield"]
            ),
        )
        chained = next(
            item for item in resolved["battlefield"]
            if item.get("cardId") == manifestation
        )
        self.assertEqual(chained.get("ownerId"), "p2")

    async def test_reset_board_bypasses_pending_choice_and_ended_state(self):
        self.prepare_active_rules("confrontation_reaction")
        self.session.rules_engine["pendingChoice"] = {
            "id": "blocking-choice",
            "kind": "chain_manifestation",
            "playerId": "p1",
            "fromZone": "deck",
            "cardIds": [],
            "_cardIds": [],
        }
        self.session.ended = True

        await self.send(self.ws1, {"type": "reset_board"})
        state = await self.receive_until(
            self.ws1,
            lambda message: message.get("type") == "state"
            and message["rulesEngine"]["pendingChoice"] is None
            and not message["ended"]
            and any(
                entry.get("type") == "reset_board"
                for entry in message.get("recentLog") or []
            ),
        )

        self.assertFalse(state["ended"])
        self.assertIsNone(self.session.rules_engine["pendingChoice"])
        self.assertEqual(self.session.rules_engine["actionStack"], [])

    async def test_manual_card_play_bypasses_assisted_timing_and_stack(self):
        self.prepare_active_rules("recovery_draw")
        manual_card = server_main.CARD_ID_BY_NUMBER[2]
        p1 = self.session.players["p1"]
        p1["zones"]["hand"] = [manual_card]
        p1["zoneOwners"]["hand"] = {manual_card: "p1"}

        await self.send(self.ws1, {
            "type": "place_card",
            "fromZone": "hand",
            "cardId": manual_card,
            "faceUp": True,
            "manualBypass": True,
            "x": 400,
            "y": 500,
        })
        state = await self.receive_until(
            self.ws1,
            lambda message: message.get("type") == "state"
            and any(
                item.get("cardId") == manual_card
                for item in message["battlefield"]
            ),
        )
        placed = next(
            item for item in state["battlefield"]
            if item.get("cardId") == manual_card
        )
        self.assertEqual(placed["fieldZone"], "interzone")
        self.assertEqual(self.session.rules_engine["actionStack"], [])
        self.assertNotIn(manual_card, p1["zones"]["hand"])

    async def test_flem_is_played_into_the_interzone_only_during_end_actions(self):
        flem = next(
            card["id"] for card in server_main.CARD_DATA if card["name"] == "Flem"
        )
        p1 = self.session.players["p1"]
        p1["zones"]["hand"] = [flem]
        p1["zoneOwners"]["hand"] = {flem: "p1"}
        place = {
            "type": "place_card", "fromZone": "hand", "cardId": flem,
            "faceUp": True, "x": 400, "y": 500,
        }

        self.prepare_active_rules("resolution_effects")
        await self.send(self.ws1, place)
        error = await self.receive_until(
            self.ws1, lambda message: message.get("type") == "error"
        )
        self.assertIn("End Phase", error["message"])
        self.assertEqual(p1["zones"]["hand"], [flem])

        self.prepare_active_rules("end_actions")
        await self.send(self.ws1, place)
        state = await self.receive_until(
            self.ws1,
            lambda message: message.get("type") == "state"
            and any(item.get("cardId") == flem for item in message["battlefield"]),
        )
        placed = next(item for item in state["battlefield"] if item.get("cardId") == flem)
        self.assertEqual(placed["fieldZone"], "interzone")
        self.assertFalse(placed.get("isSupport"))
        self.assertEqual(self.session.rules_engine["actionStack"], [])
        self.assertEqual(p1["zones"]["hand"], [])

    async def test_peropero_exposes_the_deck_top_and_lets_its_manifestation_be_played(self):
        peropero = "k6l96o0xphpycpm_en"
        flem = next(card["id"] for card in server_main.CARD_DATA if card["name"] == "Flem")
        p1 = self.session.players["p1"]
        p1["zones"]["deck"] = [flem] + p1["zones"]["deck"][:3]
        p1["zoneOwners"]["deck"][flem] = "p1"
        self.prepare_active_rules("end_actions")
        place = {
            "type": "place_card", "fromZone": "deck", "cardId": flem,
            "faceUp": True, "x": 400, "y": 500,
        }
        self.session.battlefield.append({
            "id": "pero", "ownerId": "p1", "controllerId": "p1", "cardId": peropero,
            "x": 0, "y": 0, "faceUp": True, "rotation": 0, "counters": {},
            "stackedOn": None, "fieldZone": "field",
        })
        self.assertEqual(self.session.serialize_for("p2", "player")["rulesEngine"]["uncoveredTops"], {"p1": flem})
        await self.send(self.ws1, place)
        state = await self.receive_until(
            self.ws1,
            lambda message: message.get("type") == "state"
            and any(item.get("cardId") == flem for item in message["battlefield"]),
        )
        placed = next(item for item in state["battlefield"] if item.get("cardId") == flem)
        self.assertEqual(placed["fieldZone"], "interzone")
        self.assertNotIn(flem, p1["zones"]["deck"])

    async def test_atavic_persistent_will_is_playable_before_the_revelation(self):
        fury = "m2l3v60n0iakrm2_en"
        p1 = self.session.players["p1"]
        p1["zones"]["hand"] = [fury]
        p1["zoneOwners"]["hand"] = {fury: "p1"}
        self.session.rules_engine["firstManifestationComplete"] = True
        declare = {
            "type": "declare_rules_action", "label": "Atavic Fury",
            "kind": "play_card", "source": {"cardId": fury, "zone": "hand"},
            "targets": [], "paymentCardIds": [],
            "placement": {"x": 400, "y": 500},
        }

        self.prepare_active_rules("confrontation_reaction")
        await self.send(self.ws1, declare)
        error = await self.receive_until(
            self.ws1, lambda message: message.get("type") == "error"
        )
        self.assertIn("End actions", error["message"])

        self.prepare_active_rules("confrontation_before_revelation")
        await self.send(self.ws1, declare)
        state = await self.receive_until(
            self.ws1,
            lambda message: message.get("type") == "state"
            and len(message["rulesEngine"]["actionStack"]) == 1,
        )
        self.assertEqual(
            state["rulesEngine"]["actionStack"][0]["source"]["cardId"], fury
        )

    async def test_kiss_decline_requests_and_applies_the_loser_target_over_websocket(self):
        self.prepare_active_rules("confrontation_reaction")
        self.session.rules_engine["firstManifestationComplete"] = True
        kiss = server_main.CARD_ID_BY_NUMBER[416]
        tribute = server_main.CARD_ID_BY_NUMBER[151]
        p1_card = server_main.CARD_ID_BY_NUMBER[1]
        p2_card = server_main.CARD_ID_BY_NUMBER[2]
        self.session.card_rules[tribute].update({
            "power": 2,
            "temperaments": ["choleric"],
            "tributeTemperaments": ["choleric"],
        })
        self.session.card_rules[p1_card]["power"] = 1
        self.session.card_rules[p2_card]["power"] = 3
        self.session.battlefield = [
            {
                "id": "p1-first", "ownerId": "p1", "cardId": p1_card,
                "x": 500, "y": 700, "faceUp": True, "rotation": 0,
                "fieldZone": "confrontation", "confrontationOrder": 1,
                "counters": {},
            },
            {
                "id": "p2-first", "ownerId": "p2", "cardId": p2_card,
                "x": 900, "y": 500, "faceUp": True, "rotation": 0,
                "fieldZone": "confrontation", "confrontationOrder": 2,
                "counters": {},
            },
        ]
        p1 = self.session.players["p1"]
        p1["zones"]["hand"] = [kiss, tribute]
        p1["zoneOwners"]["hand"] = {kiss: "p1", tribute: "p1"}

        await self.send(self.ws1, {
            "type": "declare_rules_action",
            "label": "Kiss of the Myrmillo!",
            "kind": "play_card",
            "source": {"cardId": kiss, "zone": "hand"},
            "targets": [],
            "paymentCardIds": [tribute],
            "abilityId": server_main.CARD_ABILITIES[kiss][0]["id"],
        })
        payment_state = await self.receive_until(
            self.ws2,
            lambda message: message.get("type") == "state"
            and message["rulesEngine"]["pendingChoice"] is not None
            and message["rulesEngine"]["pendingChoice"]["kind"]
            == "immediate_effect_payment",
        )
        await self.send(self.ws2, {
            "type": "resolve_rules_choice",
            "choiceId": payment_state["rulesEngine"]["pendingChoice"]["id"],
            "option": "decline",
        })
        target_state = await self.receive_until(
            self.ws1,
            lambda message: message.get("type") == "state"
            and message["rulesEngine"]["pendingChoice"] is not None
            and message["rulesEngine"]["pendingChoice"]["kind"]
            == "trigger_targets",
        )
        self.assertEqual(
            target_state["rulesEngine"]["pendingChoice"]["playerId"], "p1"
        )

        await self.send(self.ws1, {
            "type": "resolve_rules_choice",
            "choiceId": target_state["rulesEngine"]["pendingChoice"]["id"],
            "targets": [{
                "kind": "card",
                "itemId": "p2-first",
                "cardId": p2_card,
            }],
        })
        resolved = await self.receive_until(
            self.ws1,
            lambda message: message.get("type") == "state"
            and message["rulesEngine"]["pendingChoice"] is None
            and next(
                item for item in message["battlefield"]
                if item["id"] == "p2-first"
            ).get("effectivePower") == 2,
        )
        self.assertEqual(
            next(
                item for item in resolved["battlefield"]
                if item["id"] == "p2-first"
            )["counters"]["power"],
            -1,
        )
        self.assertIn(kiss, p1["zones"]["exile"])


    async def test_essence_pool_create_decrement_and_remove_round_trip(self):
        self.prepare_active_rules("end_actions")
        await self.send(self.ws1, {
            "type": "create_essence_token",
            "temperament": "choleric",
            "neutral": False,
            "label": "",
            "color": "#d3654a",
            "count": 2,
            "x": 640,
            "y": 720,
        })
        created = await self.receive_until(
            self.ws1,
            lambda message: message.get("type") == "state"
            and any(
                token.get("ownerId") == "p1"
                and token.get("temperament") == "choleric"
                and token.get("counters", {}).get("essence") == 2
                for token in message.get("tokens", [])
            ),
        )
        token = next(
            token for token in created["tokens"]
            if token.get("ownerId") == "p1" and token.get("temperament") == "choleric"
        )

        await self.send(self.ws1, {
            "type": "add_counter",
            "tokenId": token["id"],
            "counterKey": "essence",
            "delta": -1,
        })
        decremented = await self.receive_until(
            self.ws1,
            lambda message: message.get("type") == "state"
            and any(
                entry.get("id") == token["id"]
                and entry.get("counters", {}).get("essence") == 1
                for entry in message.get("tokens", [])
            ),
        )
        self.assertEqual(
            next(entry for entry in decremented["tokens"] if entry["id"] == token["id"])["counters"]["essence"],
            1,
        )

        await self.send(self.ws1, {"type": "remove_token", "tokenId": token["id"]})
        removed = await self.receive_until(
            self.ws1,
            lambda message: message.get("type") == "state"
            and not any(entry.get("id") == token["id"] for entry in message.get("tokens", [])),
        )
        self.assertFalse(any(entry.get("id") == token["id"] for entry in removed["tokens"]))


if __name__ == "__main__":
    unittest.main()


class TournamentStartTests(unittest.IsolatedAsyncioTestCase):
    """The organizer's start deals the opening hands; the lobby never does."""

    DECKS = json.loads(open(os.path.join(SERVER_DIR, "..", "public", "starter-decks.json"), encoding="utf-8").read())

    async def asyncSetUp(self):
        server_main.sessions.clear()
        server_main.connections.clear()
        self.server = await serve(
            server_main.handler, "127.0.0.1", 0,
            process_request=server_main.process_request, compression=None,
        )
        self.uri = f"ws://127.0.0.1:{self.server.sockets[0].getsockname()[1]}/ws"
        self.clients = []

    async def asyncTearDown(self):
        for websocket in self.clients:
            await websocket.close()
        self.server.close()
        await self.server.wait_closed()
        server_main.sessions.clear()
        server_main.connections.clear()

    async def connect_join(self, payload):
        websocket = await connect(self.uri)
        self.clients.append(websocket)
        await websocket.send(json.dumps(payload))
        for _index in range(40):
            message = json.loads(await asyncio.wait_for(websocket.recv(), timeout=2))
            if message.get("type") == "joined":
                return websocket
        self.fail("join failed")

    async def settle(self):
        await asyncio.sleep(0.3)

    async def run_tournament(self, rules):
        organizer = await self.connect_join({
            "type": "join", "createTournament": True, "rulesBeta": rules, "name": "Org", "clientId": "org",
        })
        session = next(iter(server_main.sessions.values()))
        codes = session.tournament_codes()
        players = []
        for index, key in enumerate(("player1", "player2")):
            players.append(await self.connect_join({
                "type": "join", "code": codes[key], "name": f"P{index + 1}", "clientId": f"p{index + 1}",
            }))
        for websocket, temperament in zip(players, ("phlegmatic", "choleric")):
            deck = next(entry for entry in self.DECKS if temperament in entry["id"])
            await websocket.send(json.dumps({"type": "import_deck", "deck": deck, "name": deck["name"], "confirmDeck": True}))
        await self.settle()
        hands = lambda: [len(session.players[pid]["zones"]["hand"]) for pid in ("p1", "p2")]
        self.assertEqual(hands(), [0, 0])  # nothing is dealt before the start
        await organizer.send(json.dumps({"type": "start_tournament"}))
        await self.settle()
        self.assertEqual(session.status, "active")
        self.assertEqual(hands(), [7, 7])
        return session, players

    async def test_assisted_tournament_deals_opening_hands_at_start(self):
        session, players = await self.run_tournament(True)
        for websocket in players:
            await websocket.send(json.dumps({"type": "set_rules_ready"}))
        await self.settle()
        self.assertEqual(session.current_phase_id(), "confrontation_choose")

    async def test_manual_tournament_deals_seven_cards_at_start(self):
        await self.run_tournament(False)
