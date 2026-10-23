"""Opening hands, mulligans, First Manifestation, Recovery draw and final scores."""

import random

from .common import ADVANCED_PHASES, NUM_SEATS, new_id, validate_tournament_deck


class PregameMixin:
    # -- first assisted-rules slice ------------------------------------
    def _draw_player_to_limit(self, player_id, hand_limit=7):
        player = self.players[player_id]
        needed = max(0, hand_limit - len(player["zones"]["hand"]))
        drawn = []
        for _ in range(min(needed, len(player["zones"]["deck"]))):
            card_id = player["zones"]["deck"][0]
            error, _ = self.move_zone_card(player_id, "deck", player_id, "hand", card_id, "bottom")
            if error:
                return error, drawn
            drawn.append(card_id)
        return None, drawn

    def rules_opening_hand_limit(self, player_id, default_limit=7, timing="before_draw"):
        """Return the hand size used by the opening sequence.

        The timing argument is deliberately explicit: encoded effects that alter
        the opening hand can later be applied before or after the first draw
        without duplicating the sequence.  No currently encoded card changes the
        limit, so the rulebook default remains authoritative today.
        """
        _ = player_id, timing
        return max(0, int(default_limit))

    def rules_card_can_be_first_manifestation(self, card_id, player_id=None):
        metadata = self.card_rules.get(card_id, {})
        if player_id is not None and self.rules_confrontation_entry_blocked(player_id, metadata):
            return False
        is_manifestation = card_id in self.manifestation_ids or metadata.get("type") == "manifestation"
        # Inner Deserts art is already playable, but its machine-readable card
        # types are still placeholders. Assisted rules must not turn missing
        # metadata into a false mandatory Mulligan. Such a card is accepted as
        # a manually verified first Manifestation until the catalog is typed.
        manually_verified_placeholder = bool(metadata.get("placeholder"))
        return bool(
            (is_manifestation or manually_verified_placeholder)
            and metadata.get("canBeFirstManifestation", True)
        )

    def rules_opening_hand_is_playable(self, player_id):
        player = self.players.get(player_id)
        return bool(player and any(
            self.rules_card_can_be_first_manifestation(card_id)
            for card_id in player["zones"]["hand"]
        ))

    def _draw_rules_opening_hand(self, player_id, default_limit=7):
        before_limit = self.rules_opening_hand_limit(player_id, default_limit, "before_draw")
        error, drawn = self._draw_player_to_limit(player_id, before_limit)
        if error:
            return error, None
        after_limit = self.rules_opening_hand_limit(player_id, before_limit, "after_draw")
        if after_limit != before_limit:
            error, adjusted = self._draw_player_to_limit(player_id, after_limit)
            if error:
                return error, None
            drawn.extend(adjusted)
        return None, {"count": len(drawn), "handLimit": after_limit}

    def rules_recovery_hand_limit(self, player_id, default_limit=7, timing="before_draw"):
        """Return the hand size used by a normal-turn Recovery draw.

        Keeping the before/after timing explicit lets encoded effects alter the
        limit later without making the clients responsible for draw order.
        """
        limit = self.rules_hand_limit(player_id, default_limit)
        if timing == "before_draw":
            extra = 0
            for source in self.rules_active_passive_sources(
                "extra_recovery_draw_per_empty_interzone"
            ):
                if (
                    self.rules_item_controller_id(source) == player_id
                    and self.rules_field_zone(source) == "interzone"
                ):
                    occupied = self.rules_interzone_slot_count(player_id)
                    extra += max(0, 3 - occupied)
            limit += extra
        return max(0, limit)

    def rules_quasimillenary_active(self, player_id):
        return player_id in (self.rules_engine.get("limboRecoveryPlayerIds") or []) and any(
            self.rules_item_controller_id(source) == player_id
            and self.rules_field_zone(source) == "interzone"
            for source in self.rules_active_passive_sources("recovery_draw_from_limbo")
        )

    def toggle_rules_limbo_recovery(self, player_id):
        if not any(
            self.rules_item_controller_id(source) == player_id
            and self.rules_field_zone(source) == "interzone"
            for source in self.rules_active_passive_sources("recovery_draw_from_limbo")
        ):
            return "Quasimillenary is not in your Interzone.", None
        enabled = self.rules_engine.setdefault("limboRecoveryPlayerIds", [])
        if player_id in enabled:
            enabled.remove(player_id)
        else:
            enabled.append(player_id)
        return None, {"enabled": player_id in enabled}

    def _draw_rules_recovery_hand(self, player_id, default_limit=7):
        before_limit = self.rules_recovery_hand_limit(player_id, default_limit, "before_draw")
        if self.rules_quasimillenary_active(player_id) and self.players[player_id]["zones"]["graveyard"]:
            player = self.players[player_id]
            random.shuffle(player["zones"]["graveyard"])
            needed = max(0, before_limit - len(player["zones"]["hand"]))
            drawn = []
            marked = self.rules_engine.setdefault("limboDrawn", {}).setdefault(player_id, [])
            for _ in range(min(needed, len(player["zones"]["graveyard"]))):
                card_id = player["zones"]["graveyard"][0]
                move_error, _owner = self.move_zone_card(player_id, "graveyard", player_id, "hand", card_id, "bottom")
                if move_error:
                    return move_error, None
                marked.append(card_id)
                drawn.append(card_id)
            # Not enough cards in Limbo: the rest comes from the deck as usual.
            error, from_deck = self._draw_player_to_limit(player_id, before_limit)
            if error:
                return error, None
            return None, {
                "count": len(drawn) + len(from_deck), "handLimit": before_limit,
                "fromLimbo": drawn,
            }
        error, drawn = self._draw_player_to_limit(player_id, before_limit)
        if error:
            return error, None
        return None, {"count": len(drawn), "handLimit": before_limit}

    def _start_rules_match_after_opening(self):
        self.phase_tracker["index"] = ADVANCED_PHASES.index("recovery_end")
        self.phase_passes.clear()
        self.rules_engine["priorityPasses"] = []
        first_player = self.player_for_seat(0) or next(iter(self.players.values()), None)
        self.rules_engine["priorityPlayerId"] = first_player.get("id") if first_player else None

    def prepare_rules_opening_hands(self, hand_limit=7):
        """Draw and validate both opening hands as one server-owned sequence."""
        if not self.rules_pregame_active():
            return "The opening-hand setup is no longer active.", None
        player_ids = list(self.players)
        confirmed_ids = self.rules_engine["deckConfirmedPlayerIds"]
        if len(player_ids) < NUM_SEATS or not all(pid in confirmed_ids for pid in player_ids):
            return None, {"prepared": False, "draws": {}, "started": False}
        if self.mode == "tournament" and self.status != "active":
            # tournament: the opening hands wait for the organizer to start the match
            return None, {"prepared": False, "draws": {}, "started": False, "waitingForStart": True}

        draws = {}
        required = self.rules_engine["openingMulliganRequiredPlayerIds"]
        ready = self.rules_engine["readyPlayerIds"]
        for player_id in player_ids:
            if player_id not in self.rules_engine["openingHandPlayerIds"]:
                error, result = self._draw_rules_opening_hand(player_id, hand_limit)
                if error:
                    return error, None
                self.rules_engine["openingHandPlayerIds"].append(player_id)
                draws[player_id] = result["count"]
            if self.rules_opening_hand_is_playable(player_id):
                if player_id in required:
                    required.remove(player_id)
            elif player_id not in required and player_id not in self.rules_engine["mulliganPlayerIds"]:
                required.append(player_id)

        started = not required and all(player_id in ready for player_id in player_ids)
        if started:
            self._start_rules_match_after_opening()
        return None, {
            "prepared": True,
            "draws": draws,
            "mulliganRequiredPlayerIds": list(required),
            "started": started,
        }

    def start_tournament_match(self, hand_limit=7):
        """Organizer start: the game begins for both players at the same moment.

        With assisted rules the opening sequence runs (opening hands, then keep or
        Mulligan). A manual table gets shuffled decks and seven cards per player.
        """
        self.status = "active"
        if self.rules_engine["enabled"]:
            return self.prepare_rules_opening_hands(hand_limit)
        draws = {}
        for player_id, player in self.players.items():
            if player["zones"]["hand"]:
                continue
            random.shuffle(player["zones"]["deck"])
            count = 0
            for _index in range(min(hand_limit, len(player["zones"]["deck"]))):
                card_id = player["zones"]["deck"][0]
                error, _owner = self.move_zone_card(player_id, "deck", player_id, "hand", card_id, "bottom")
                if error:
                    return error, None
                count += 1
            draws[player_id] = count
        return None, {"prepared": True, "draws": draws, "started": True, "manual": True}

    def draw_opening_hand(self, player_id, hand_limit=7):
        """Draw one player's initial hand without invoking Recovery or game end."""
        if not self.rules_engine["enabled"]:
            return "Assisted rules are not active.", None
        if self.ended:
            return "The game has already ended.", None
        if player_id not in self.players:
            return "Unknown player.", None
        if self.phase_tracker["turn"] != 1 or self.current_phase_id() != "recovery_start":
            return "Opening hands can only be drawn during the first Recovery start step.", None
        player_ids = list(self.players)
        confirmed_ids = self.rules_engine["deckConfirmedPlayerIds"]
        if len(player_ids) < NUM_SEATS or not all(pid in confirmed_ids for pid in player_ids):
            return "Both players must validate their decks before drawing opening hands.", None
        if player_id in self.rules_engine["openingHandPlayerIds"]:
            return "You have already drawn your opening hand.", None

        error, result = self._draw_rules_opening_hand(player_id, hand_limit)
        if error:
            return error, None
        self.rules_engine["openingHandPlayerIds"].append(player_id)
        return None, result

    def rules_pregame_active(self):
        return bool(
            self.rules_engine["enabled"]
            and not self.ended
            and self.phase_tracker["turn"] == 1
            and self.current_phase_id() == "recovery_start"
        )

    def casual_deck_setup_active(self):
        return bool(
            self.mode == "casual"
            and not self.rules_engine["enabled"]
            and not self.ended
            and self.phase_tracker["turn"] == 1
            and self.current_phase_group() == "recovery"
            and not self.rules_engine["openingHandPlayerIds"]
        )

    def reset_rules_pregame_player(self, player_id):
        """Invalidate only this player's setup choices after a deck replacement."""
        if not (self.rules_pregame_active() or self.casual_deck_setup_active()):
            return
        for key in (
            "deckConfirmedPlayerIds", "openingHandPlayerIds", "mulliganPlayerIds",
            "openingMulliganRequiredPlayerIds", "openingMulliganFailedPlayerIds", "readyPlayerIds",
        ):
            self.rules_engine[key] = [pid for pid in self.rules_engine[key] if pid != player_id]

    def confirm_casual_deck(self, player_id, hand_limit=7):
        """Validate a normal-game deck and draw both opening hands once ready."""
        if not self.casual_deck_setup_active():
            return "Deck selection is locked after the opening hands are drawn.", None
        if player_id not in self.players:
            return "Unknown player.", None
        error = self.deck_validation_error(player_id)
        if error:
            return error, None
        confirmed_ids = self.rules_engine["deckConfirmedPlayerIds"]
        if player_id not in confirmed_ids:
            confirmed_ids.append(player_id)
        player_ids = list(self.players)
        if len(player_ids) < NUM_SEATS or not all(pid in confirmed_ids for pid in player_ids):
            return None, {"confirmed": True, "draws": {}, "started": False}

        draws = {}
        for opening_player_id in player_ids:
            error, drawn = self._draw_player_to_limit(opening_player_id, hand_limit)
            if error:
                return error, None
            draws[opening_player_id] = len(drawn)
            self.rules_engine["openingHandPlayerIds"].append(opening_player_id)
        return None, {"confirmed": True, "draws": draws, "started": True}

    def deck_validation_error(self, player_id):
        player = self.players.get(player_id)
        definition = player.get("deckDefinition") if player else None
        if not isinstance(definition, dict):
            return "Import a deck before validating it."
        main_cards = []
        sideboard_cards = []
        for group in definition.get("groups") or []:
            kind = str(group.get("kind") or "").lower()
            if kind == "maybeboard":
                continue
            (sideboard_cards if kind == "sideboard" else main_cards).extend(group.get("cardIds") or [])
        policy = self.tournament_policy if self.ban_list_enabled else None
        return validate_tournament_deck(
            main_cards, sideboard_cards, self.card_points or {}, policy, self.card_labels,
            limit_bonus=self.rules_deck_limit_bonus(main_cards),
        )

    def rules_deck_limit_bonus(self, card_ids):
        return sum(
            int(self.card_rules.get(card_id, {}).get("constructionLimitBonus") or 0)
            for card_id in card_ids
        )

    def set_rules_deck_confirmed(self, player_id, confirmed=True):
        if not self.rules_pregame_active():
            return "Deck selection is locked after the match begins.", None
        if player_id not in self.players:
            return "Unknown player.", None
        confirmed_ids = self.rules_engine["deckConfirmedPlayerIds"]
        if not confirmed:
            player_ids = list(self.players)
            if len(player_ids) >= NUM_SEATS and all(pid in confirmed_ids for pid in player_ids):
                return "Decks are locked after both players validate.", None
            self.rules_engine["deckConfirmedPlayerIds"] = [pid for pid in confirmed_ids if pid != player_id]
            return None, {"confirmed": False}
        error = self.deck_validation_error(player_id)
        if error:
            return error, None
        if player_id in confirmed_ids:
            return None, {"confirmed": True, "opening": None, "alreadyConfirmed": True}
        if player_id not in confirmed_ids:
            confirmed_ids.append(player_id)
        error, opening = self.prepare_rules_opening_hands()
        if error:
            return error, None
        return None, {"confirmed": True, "opening": opening}

    def rules_first_manifestation_active(self):
        return bool(
            self.rules_engine["enabled"]
            and not self.ended
            and self.current_phase_id() == "confrontation_choose"
            and not self.rules_engine["firstManifestationComplete"]
        )

    def rules_existing_first_manifestation(self, player_id):
        return next((
            item for item in sorted(self.battlefield, key=lambda entry: int(entry.get("confrontationOrder") or 0))
            if self.rules_item_controller_id(item) == player_id
            and self.rules_field_zone(item) == "confrontation"
            and (item.get("isTokenCard") or self.rules_item_card_rules(item).get("type") == "manifestation")
        ), None)

    def rules_first_manifestation_slot_taken(self, player_id):
        return bool(
            self.rules_engine.get("firstManifestationComplete")
            or player_id in self.rules_engine["firstManifestationItemIds"]
            or self.rules_existing_first_manifestation(player_id)
        )

    def register_rules_existing_first_manifestations(self):
        """Cards already in the CZ before selection occupy their controller's PM slot."""
        selected = self.rules_engine["firstManifestationItemIds"]
        validated = self.rules_engine["firstManifestationValidatedPlayerIds"]
        for player_id in self.players:
            if player_id in selected:
                continue
            item = self.rules_existing_first_manifestation(player_id)
            if item is not None:
                item["isSupport"] = False
                selected[player_id] = item["id"]
                if player_id not in validated:
                    validated.append(player_id)
        if len(self.players) >= NUM_SEATS and all(pid in selected and pid in validated for pid in self.players):
            self.rules_engine["firstManifestationComplete"] = False
            self.validate_first_manifestation(next(iter(self.players)))

    def _rules_wants_first_manifestation_after(self, player_id):
        if player_id in (self.rules_engine.get("trapPlayerIds") or []):
            return True
        sources = self.rules_active_passive_sources("play_first_manifestation_after_opponents")
        mine = any(self.rules_item_controller_id(source) == player_id for source in sources)
        theirs = any(self.rules_item_controller_id(source) != player_id for source in sources)
        return mine and not theirs

    def rules_plays_first_manifestation_after(self, player_id):
        """Hermetic Hourglass or Trap: this player plays the First Manifestation after the opponent.

        When every player wants to play last (Trap against Hourglass, two Traps),
        the demands cancel out instead of leaving both players waiting.
        """
        if not self._rules_wants_first_manifestation_after(player_id):
            return False
        return not all(self._rules_wants_first_manifestation_after(pid) for pid in self.players)

    def rules_first_manifestation_order_error(self, player_id):
        if not self.rules_plays_first_manifestation_after(player_id):
            return None
        validated = self.rules_engine["firstManifestationValidatedPlayerIds"]
        if any(pid != player_id and pid in validated for pid in self.players):
            return None
        if player_id in (self.rules_engine.get("trapPlayerIds") or []):
            return "Your Trap makes you play your First Manifestation after the opponent: wait for their validated First Manifestation."
        return "Your Hermetic Hourglass makes you play after the opponent: wait for their validated First Manifestation."

    def rules_is_trap_card(self, card_id):
        return any(
            (ability.get("result") or {}).get("kind") == "first_manifestation_trap"
            for ability in self.card_rules.get(card_id, {}).get("playedAbilities") or []
        )

    def play_first_manifestation_trap(self, player_id, card_id):
        """Trap: played at Revelation in place of the First Manifestation, which is then played after the opponent's."""
        if not self.rules_first_manifestation_active():
            return "A Trap can only be played in place of the First Manifestation.", None
        player = self.players.get(player_id)
        if player is None or card_id not in player["zones"]["hand"] or not self.rules_is_trap_card(card_id):
            return "Choose a Trap from your Hand.", None
        if (
            self.rules_first_manifestation_slot_taken(player_id)
            or player_id in self.rules_engine["firstManifestationValidatedPlayerIds"]
            or player_id in self.rules_engine["trapPlayerIds"]
        ):
            return "You have already chosen your First Manifestation.", None
        # The Trap waits face down in the Confrontation Zone, like a First
        # Manifestation: it is turned over (and the 5 points lost) when the
        # opponent's First Manifestation is revealed.
        self.take_zone_card(player_id, "hand", card_id)
        self.rules_engine.setdefault("trapCards", {})[player_id] = {"cardId": card_id, "revealed": False}
        self.rules_engine["trapPlayerIds"].append(player_id)
        return None, {"playerId": player_id, "delta": 0}

    def reveal_rules_traps(self, player_ids):
        """Turn the waiting Traps over: each goes to its owner's Limbo and costs 5 points."""
        revealed = []
        for pid in player_ids:
            trap = (self.rules_engine.get("trapCards") or {}).get(pid)
            if not trap or trap.get("revealed") or pid not in self.players:
                continue
            card_id = trap["cardId"]
            trap["revealed"] = True
            self.put_zone_card(pid, "hand", card_id, pid, "bottom")
            self.move_zone_card(pid, "hand", pid, "graveyard", card_id, "top")
            delta = self.adjust_rules_score(pid, -5)
            revealed.append({"playerId": pid, "cardId": card_id, "delta": delta})
        return revealed

    def flush_rules_traps(self):
        """A Trap still face down when the step ends is turned over anyway."""
        revealed = self.reveal_rules_traps(list((self.rules_engine.get("trapCards") or {}).keys()))
        self.rules_engine["trapCards"] = {}
        return revealed

    def register_first_manifestation(self, player_id, item):
        if not self.rules_first_manifestation_active():
            return None
        order_error = self.rules_first_manifestation_order_error(player_id)
        if order_error and not item.get("persistedFirst"):
            return order_error
        if item.get("ownerId") != player_id or not self.rules_card_can_be_first_manifestation(item.get("cardId"), player_id):
            return "Your first play must be one of your Manifestations."
        selected = self.rules_engine["firstManifestationItemIds"]
        existing = self.rules_existing_first_manifestation(player_id)
        if player_id in selected or (existing is not None and existing.get("id") != item.get("id")):
            return "You have already chosen your first Manifestation."
        # Playing after the opponent (Trap, Hermetic Hourglass): their First
        # Manifestation is already revealed and this one arrives face up.
        item["faceUp"] = bool(
            self.rules_plays_first_manifestation_after(player_id)
            and not item.get("persistedFirst")
        )
        self.mark_rules_confrontation_entry(item)
        selected[player_id] = item["id"]
        return None

    def set_rules_field_zone(self, player_id, item_id, field_zone):
        if not self.rules_engine["enabled"]:
            return "Assisted rules are not active.", None
        if field_zone != "confrontation" or self.current_phase_id() != "confrontation_reaction":
            return "A Manifestation can enter Support only during Reaction.", None
        item = self.find_battlefield_item(item_id)
        if item is None or self.rules_item_controller_id(item) != player_id:
            return "This Manifestation is not under your control.", None
        if self.rules_item_card_rules(item).get("type") != "manifestation":
            return "Only a Manifestation can enter the confrontation.", None
        if self.rules_support_entry_locked(player_id):
            return "Manifestations cannot be put in Support until the end of the turn.", None
        if self.rules_item_zone_locked(item):
            return "This Manifestation cannot change zone until the end of the turn.", None
        source_field_zone = self.rules_field_zone(item)
        if source_field_zone not in {"interzone", "stalemate"}:
            return "This Manifestation is not in a zone from which it can enter Support.", None
        if self.rules_engine.get("priorityPlayerId") != player_id:
            return "You do not have priority.", None
        if not self.rules_card_can_enter_support(item, source_field_zone):
            return "This Manifestation does not currently have Support.", None
        self.mark_rules_support_entry(item)
        return None, {
            "itemId": item_id, "cardId": item.get("cardId"),
            "fieldZone": "confrontation", "asSupport": True,
        }

    def validate_first_manifestation(self, player_id, validated=True):
        if not self.rules_first_manifestation_active():
            return "The simultaneous first Manifestation step is not active.", None
        confirmed_players = self.rules_engine["firstManifestationValidatedPlayerIds"]
        if not validated:
            return "Your first Manifestation is final and locked in: it cannot be changed once placed.", None
        item_id = self.rules_engine["firstManifestationItemIds"].get(player_id)
        if not item_id or not self.find_battlefield_item(item_id):
            return "Play a Manifestation face down before validating.", None
        order_error = self.rules_first_manifestation_order_error(player_id)
        if order_error:
            return order_error, None
        if player_id not in confirmed_players:
            confirmed_players.append(player_id)
        after_ids = [pid for pid in self.players if self.rules_plays_first_manifestation_after(pid)]
        first_ids = [pid for pid in self.players if pid not in after_ids]
        traps_revealed = []
        if after_ids and all(pid in confirmed_players for pid in first_ids):
            for pid in first_ids:
                revealed_item = self.find_battlefield_item(
                    self.rules_engine["firstManifestationItemIds"].get(pid)
                )
                if revealed_item:
                    revealed_item["faceUp"] = True
            traps_revealed = self.reveal_rules_traps(after_ids)
        player_ids = list(self.players)
        revealed = len(player_ids) >= NUM_SEATS and all(pid in confirmed_players for pid in player_ids)
        if revealed:
            traps_revealed += self.flush_rules_traps()
            self.rules_engine["firstManifestationComplete"] = True
            self.phase_tracker["index"] = ADVANCED_PHASES.index("confrontation_before_revelation")
            self.rules_engine["priorityPasses"] = []
            first_player = self.player_for_seat(0) or next(iter(self.players.values()), None)
            last_winner = self.rules_engine.get("lastConfrontationWinnerId")
            self.rules_engine["priorityPlayerId"] = (
                last_winner if last_winner in self.players
                else (first_player.get("id") if first_player else None)
            )
        return None, {
            "validated": True, "selectionComplete": revealed, "revealed": False,
            "trapsRevealed": traps_revealed,
        }

    def mulligan_opening_hand(self, player_id, hand_limit=7):
        if not self.rules_pregame_active():
            return "Mulligans are only available before both players are ready.", None
        if player_id not in self.players:
            return "Unknown player.", None
        if player_id not in self.rules_engine["openingHandPlayerIds"]:
            return "Draw your opening hand before taking a mulligan.", None
        if player_id in self.rules_engine["mulliganPlayerIds"]:
            return "You have already taken your opening mulligan.", None
        if player_id in self.rules_engine["readyPlayerIds"]:
            return "Your opening hand is already confirmed.", None

        player = self.players[player_id]
        mulligan_required = player_id in self.rules_engine["openingMulliganRequiredPlayerIds"]
        while player["zones"]["hand"]:
            card_id = player["zones"]["hand"][0]
            error, _owner_id = self.move_zone_card(
                player_id, "hand", player_id, "deck", card_id, "bottom"
            )
            if error:
                return error, None
        random.shuffle(player["zones"]["deck"])
        error, draw_result = self._draw_rules_opening_hand(player_id, hand_limit)
        if error:
            return error, None
        player["score"] = int(player.get("score") or 0) - 10
        self.rules_engine["mulliganPlayerIds"].append(player_id)
        if mulligan_required:
            self.rules_engine["openingMulliganRequiredPlayerIds"].remove(player_id)
        playable = self.rules_opening_hand_is_playable(player_id)
        if not playable and player_id not in self.rules_engine["openingMulliganFailedPlayerIds"]:
            self.rules_engine["openingMulliganFailedPlayerIds"].append(player_id)

        remaining = self.rules_engine["openingMulliganRequiredPlayerIds"]
        failed = self.rules_engine["openingMulliganFailedPlayerIds"]
        started = False
        outcome = None
        if not remaining:
            if failed:
                winner_ids = [pid for pid in self.players if pid not in failed]
                outcome = {
                    "reason": "invalid_opening_hand_after_mulligan",
                    "loserIds": list(failed),
                    "winnerIds": winner_ids,
                    "draw": len(winner_ids) != 1,
                }
                self.finish_rules_game(outcome)
            elif all(
                candidate_id in self.rules_engine["readyPlayerIds"]
                for candidate_id in self.players
            ):
                started = True
                self._start_rules_match_after_opening()
        return None, {
            "count": draw_result["count"],
            "handLimit": draw_result["handLimit"],
            "scoreCost": 10,
            "score": player["score"],
            "required": mulligan_required,
            "playable": playable,
            "started": started,
            "remainingMulliganPlayerIds": list(remaining),
            "outcome": outcome,
        }

    def set_rules_ready(self, player_id):
        if not self.rules_pregame_active():
            return "Opening hands can only be confirmed before the match begins.", None
        if player_id not in self.players:
            return "Unknown player.", None
        if player_id not in self.rules_engine["openingHandPlayerIds"]:
            return "Draw your opening hand before confirming it.", None
        if player_id in self.rules_engine["openingMulliganRequiredPlayerIds"]:
            return "Complete the required opening Mulligan before confirming your hand.", None
        if player_id in self.rules_engine["openingMulliganFailedPlayerIds"]:
            return "This opening hand cannot be confirmed.", None
        if not self.rules_opening_hand_is_playable(player_id):
            return "Your opening hand needs a playable Manifestation.", None
        ready = self.rules_engine["readyPlayerIds"]
        if player_id not in ready:
            ready.append(player_id)
        player_ids = list(self.players)
        started = (
            len(player_ids) >= NUM_SEATS
            and not self.rules_engine["openingMulliganRequiredPlayerIds"]
            and all(pid in ready for pid in player_ids)
        )
        if started:
            self._start_rules_match_after_opening()
        return None, {"ready": True, "started": started}

    def rules_end_game_points(self, player_id):
        """Points from cards that score "at the end of the game"."""
        def end_game_results(card_id):
            for ability in self.card_rules.get(card_id, {}).get("triggeredAbilities") or []:
                if (ability.get("trigger") or {}).get("event") == "end_of_game":
                    yield ability.get("result") or {}

        total = 0
        player = self.players[player_id]
        for card_id in player["zones"]["deck"]:
            for result in end_game_results(card_id):
                if result.get("kind") == "final_deck_points":
                    total += int(result.get("value") or 0)
        for container in self.players.values():
            owners = container["zoneOwners"].get("receptacle", {})
            for card_id in container["zones"]["receptacle"]:
                if container["id"] != player_id:
                    continue
                if owners.get(card_id, container["id"]) == player_id:
                    continue
                for result in end_game_results(card_id):
                    if result.get("kind") != "final_vessel_penalty":
                        continue
                    limit = int(result.get("maxBasePower") or 0)
                    count = sum(
                        1 for other_id in container["zones"]["receptacle"]
                        if self.card_rules.get(other_id, {}).get("type") == "manifestation"
                        and int(self.card_rules.get(other_id, {}).get("power") or 0) <= limit
                    )
                    total -= int(result.get("value") or 0) * count
        for item in self.battlefield:
            if (
                self.rules_item_controller_id(item) == player_id
                and self.rules_field_zone(item) == "interzone"
                and self.rules_item_effects_active(item)
            ):
                total += sum(
                    int(passive.get("value") or 0)
                    for passive in self.rules_item_card_rules(item).get(
                        "passiveEffects"
                    ) or []
                    if passive.get("kind") == "final_interzone_points"
                )
        return total

    def calculate_final_scores(self):
        scores = {}
        for player_id, player in self.players.items():
            vessel_cards = player["zones"]["receptacle"]
            card_points = self.card_points or {}
            vessel_points = sum(card_points.get(card_id, 0) for card_id in vessel_cards)
            remaining_manifestations = sum(
                1 for card_id in player["zones"]["deck"] if card_id in self.manifestation_ids
            )
            effect_points = int(player.get("score") or 0)
            deck_bonus = remaining_manifestations * 5
            end_game_points = self.rules_end_game_points(player_id)
            scores[player_id] = {
                "vesselPoints": vessel_points,
                "effectPoints": effect_points,
                "remainingManifestations": remaining_manifestations,
                "deckBonus": deck_bonus,
                "endGamePoints": end_game_points,
                "total": vessel_points + effect_points + deck_bonus + end_game_points,
            }
        alternate_players = {
            player_id for player_id, player in self.players.items()
            if any(
                passive.get("kind") == "negative_score_victory"
                for card_id in player["zones"]["graveyard"]
                for passive in self.card_rules.get(
                    card_id, {}
                ).get("passiveEffects") or []
            )
        }
        alternate_winners = [
            player_id for player_id in alternate_players
            if scores[player_id]["total"] <= -130
        ]
        if alternate_winners:
            winner_ids = alternate_winners
        else:
            eligible = {
                player_id: score for player_id, score in scores.items()
                if player_id not in alternate_players
            }
            best = max(
                (score["total"] for score in eligible.values()),
                default=0,
            )
            winner_ids = [
                player_id for player_id, score in eligible.items()
                if score["total"] == best
            ]
        return {
            "reason": "incomplete_recovery_hand",
            "scores": scores,
            "winnerIds": winner_ids,
            "draw": len(winner_ids) != 1,
            "alternateVictoryPlayerIds": alternate_winners,
            "normalVictoryExcludedPlayerIds": list(alternate_players),
        }

    def rules_recovery_mulligan_active(self):
        return bool(
            self.rules_engine["enabled"]
            and not self.ended
            and self.current_phase_id() == "recovery_draw"
            and self.rules_engine["recoveryMulliganTurn"] == self.phase_tracker["turn"]
            and self.rules_engine["recoveryMulliganRequiredPlayerIds"]
        )

    def _advance_rules_after_recovery(self):
        self.phase_tracker["index"] = ADVANCED_PHASES.index("recovery_end")
        self.phase_passes.clear()
        self.rules_engine["priorityPasses"] = []
        first_player = self.player_for_seat(0) or next(iter(self.players.values()), None)
        last_winner = self.rules_engine.get("lastConfrontationWinnerId")
        self.rules_engine["priorityPlayerId"] = (
            last_winner if last_winner in self.players
            else (first_player.get("id") if first_player else None)
        )

    def mulligan_recovery_hand(self, player_id, hand_limit=7):
        """Resolve the cost-free mandatory Mulligan used from turn two onward."""
        if not self.rules_recovery_mulligan_active():
            return "No Recovery Mulligan is currently required.", None
        if player_id not in self.players:
            return "Unknown player.", None
        required = self.rules_engine["recoveryMulliganRequiredPlayerIds"]
        if player_id not in required:
            return "Your Recovery hand already contains a playable Manifestation.", None

        player = self.players[player_id]
        while player["zones"]["hand"]:
            card_id = player["zones"]["hand"][0]
            error, _owner_id = self.move_zone_card(
                player_id, "hand", player_id, "deck", card_id, "bottom"
            )
            if error:
                return error, None
        random.shuffle(player["zones"]["deck"])
        error, draw_result = self._draw_rules_recovery_hand(player_id, hand_limit)
        if error:
            return error, None

        required.remove(player_id)
        attempted = self.rules_engine["recoveryMulliganPlayerIds"]
        if player_id not in attempted:
            attempted.append(player_id)
        playable = self.rules_opening_hand_is_playable(player_id)
        failed = self.rules_engine["recoveryMulliganFailedPlayerIds"]
        if not playable and player_id not in failed:
            failed.append(player_id)

        resumed = False
        outcome = None
        if not required:
            if failed:
                winner_ids = [pid for pid in self.players if pid not in failed]
                outcome = {
                    "reason": "invalid_recovery_hand_after_mulligan",
                    "loserIds": list(failed),
                    "winnerIds": winner_ids,
                    "draw": len(winner_ids) != 1,
                    "turn": self.phase_tracker["turn"],
                }
                self.finish_rules_game(outcome)
            else:
                resumed = True
                self._advance_rules_after_recovery()
        return None, {
            "count": draw_result["count"],
            "handLimit": draw_result["handLimit"],
            "scoreCost": 0,
            "score": player["score"],
            "playable": playable,
            "resumed": resumed,
            "remainingMulliganPlayerIds": list(required),
            "outcome": outcome,
        }

    def resolve_recovery_draw(self, hand_limit=7):
        """Refill both hands as one Recovery action, then evaluate game end.

        The draw is deliberately simultaneous from the rules engine's point of
        view: even if the first player's deck runs short, the opponent still
        consumes every card needed to reach seven before scores are counted.
        """
        if not self.rules_engine["enabled"]:
            return "Assisted rules are not active.", None
        if self.ended:
            return "The game has already ended.", None
        if self.current_phase_id() != "recovery_draw":
            return "Recovery hands can only be refilled during the Recovery draw step.", None
        turn = self.phase_tracker["turn"]
        if self.rules_engine["recoveryDrawTurn"] == turn:
            return "Recovery hands have already been refilled this turn.", None
        if len(self.players) != NUM_SEATS:
            return "Both players must be seated before resolving the Recovery draw.", None

        # Quasimillenary: its controller chooses where this Recovery draw comes from.
        decided = self.rules_engine.setdefault("limboRecoveryDecided", {})
        for pid in sorted(self.players, key=lambda current: self.players[current].get("seat", 0)):
            if decided.get(pid) == turn or not self.players[pid]["zones"]["graveyard"]:
                continue
            if not any(
                self.rules_item_controller_id(source) == pid
                and self.rules_field_zone(source) == "interzone"
                for source in self.rules_active_passive_sources("recovery_draw_from_limbo")
            ):
                continue
            choice_id = new_id()
            self.rules_engine["pendingChoice"] = {
                "id": choice_id, "kind": "binary_choice", "purpose": "quasimillenary",
                "playerId": pid, "options": ["yes", "no"],
                "headingKey": "rulesQuasiHeading", "textKey": "rulesQuasiText",
                "yesKey": "rulesQuasiYes", "noKey": "rulesQuasiNo",
                "sourceCardId": next((
                    src.get("cardId") for src in self.rules_active_passive_sources("recovery_draw_from_limbo")
                    if self.rules_item_controller_id(src) == pid
                ), None),
                "controllerId": pid, "handLimit": hand_limit,
            }
            return None, {
                "awaitingChoice": True, "choiceId": choice_id, "draws": {},
                "handLimits": {}, "mulliganRequiredPlayerIds": [], "outcome": None,
                "phaseId": self.current_phase_id(), "advanced": False,
                "incompletePlayerIds": [],
            }
        draws = {}
        hand_limits = {}
        for player in sorted(self.players.values(), key=lambda current: current.get("seat", 0)):
            player_id = player["id"]
            error, draw_result = self._draw_rules_recovery_hand(player_id, hand_limit)
            if error:
                return error, None
            draws[player_id] = draw_result["count"]
            hand_limits[player_id] = draw_result["handLimit"]
        self.rules_engine["limboRecoveryPlayerIds"] = []

        self.rules_engine["recoveryDrawTurn"] = turn
        self.rules_engine["recoveryMulliganTurn"] = turn
        self.rules_engine["recoveryMulliganPlayerIds"] = []
        self.rules_engine["recoveryMulliganRequiredPlayerIds"] = []
        self.rules_engine["recoveryMulliganFailedPlayerIds"] = []
        incomplete_player_ids = [
            player_id for player_id, player in self.players.items()
            if len(player["zones"]["hand"]) < hand_limits[player_id]
        ]
        if incomplete_player_ids:
            outcome = self.calculate_final_scores()
            outcome["incompletePlayerIds"] = incomplete_player_ids
            self.finish_rules_game(outcome)
        else:
            required = [
                player_id for player_id in self.players
                if not self.rules_opening_hand_is_playable(player_id)
            ]
            self.rules_engine["recoveryMulliganRequiredPlayerIds"] = required
            if required:
                self.rules_engine["priorityPlayerId"] = None
            else:
                self._advance_rules_after_recovery()
        return None, {
            "draws": draws,
            "handLimits": hand_limits,
            "incompletePlayerIds": incomplete_player_ids,
            "mulliganRequiredPlayerIds": list(self.rules_engine["recoveryMulliganRequiredPlayerIds"]),
            "advanced": not self.ended and self.current_phase_id() == "recovery_end",
            "phaseId": self.current_phase_id(),
            "outcome": self.rules_engine["outcome"],
        }
