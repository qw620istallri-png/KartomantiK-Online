"""Visibility rules and per-viewer serialisation."""

from .common import (
    SHARED_ZONES, ALL_ZONES, READ_ONLY_ROLES, PRIVILEGED_VIEW_ROLES, RULES_TEMPERAMENTS, new_id,
    normalize_role
)


class ViewMixin:
    # -- zone permissioning --------------------------------------------
    def can_view_zone(self, viewer_id, role, owner_id, zone):
        role = normalize_role(role)
        if zone in SHARED_ZONES:
            return True
        # private zone: the owner, or a trusted read-only observer, but never another player
        if role in PRIVILEGED_VIEW_ROLES:
            return True
        if viewer_id == owner_id:
            return True
        return zone == "hand" and self.rules_hand_revealed_to(viewer_id, owner_id)

    def rules_hand_revealed_to(self, viewer_id, owner_id):
        """Gorte (always) and Bonzai (before the Revelation) reveal a Hand."""
        if not self.rules_engine.get("enabled") or viewer_id == owner_id:
            return False
        if any(
            self.rules_item_controller_id(source) != owner_id
            for source in self.rules_active_passive_sources("reveal_opponent_hands")
        ):
            return True
        if self.current_phase_id() not in {
            "confrontation_choose", "confrontation_before_revelation",
        }:
            return False
        container = self.players.get(owner_id)
        if container is None:
            return False
        return any(
            self.card_owner_in_zone(owner_id, "receptacle", card_id) == viewer_id
            and any(
                passive.get("kind") == "vessel_reveals_owner_hand"
                for passive in self.card_rules.get(card_id, {}).get(
                    "passiveEffects"
                ) or []
            )
            for card_id in container["zones"].get("receptacle", [])
        )

    def can_act_on_zone(self, actor_id, role, owner_id, zone):
        role = normalize_role(role)
        if role in READ_ONLY_ROLES:
            return False
        if zone in SHARED_ZONES:
            return True
        return actor_id == owner_id

    # -- battlefield helpers --------------------------------------------
    def find_battlefield_item(self, item_id):
        for item in self.battlefield:
            if item["id"] == item_id:
                return item
        return None

    def find_token(self, token_id):
        for token in self.tokens:
            if token["id"] == token_id:
                return token
        return None

    def copy_card(self, actor_id, is_observer, item_id=None, source_owner=None, source_zone=None,
                  card_id=None, x=None, y=None):
        if is_observer:
            return "Observers cannot act.", None
        source = self.find_battlefield_item(item_id)
        if source is not None:
            if source.get("isTokenCard") or source.get("isCopy"):
                return "Only a real card can be copied.", None
            if not source.get("faceUp") or not source.get("cardId"):
                return "A face-down card cannot be copied.", None
            card_id = source["cardId"]
            rarity = source.get("rarity")
            default_x, default_y = source["x"] + 24, source["y"] + 24
            rotation = float(source.get("rotation") or 0)
        else:
            source_owner = source_owner or actor_id
            if source_zone not in ALL_ZONES:
                return "Unknown source zone.", None
            if not self.can_act_on_zone(actor_id, is_observer, source_owner, source_zone):
                return "You cannot copy from that zone.", None
            source_player = self.players.get(source_owner)
            if source_player is None or card_id not in source_player["zones"][source_zone]:
                return "Card not found in that zone.", None
            card_owner = self.card_owner_in_zone(source_owner, source_zone, card_id)
            rarity = (self.players.get(card_owner) or {}).get("cardRarities", {}).get(card_id)
            default_x, default_y = 0, 0
            rotation = 0.0
        item = {
            "id": new_id(), "ownerId": actor_id, "cardId": card_id,
            "x": float(default_x if x is None else x),
            "y": float(default_y if y is None else y),
            "faceUp": True, "rotation": rotation, "counters": {},
            "rarity": rarity, "stackedOn": None, "isCopy": True,
        }
        if self.rules_engine["enabled"] and self.card_rules.get(card_id, {}).get("type") == "manifestation":
            if self.current_phase_group() == "confrontation":
                self.mark_rules_confrontation_entry(item)
            else:
                item["fieldZone"] = "interzone"
                self.mark_rules_interzone_entry(item)
        self.battlefield.append(item)
        return None, item

    # -- serialization (permission-filtered per viewer) ------------------
    def serialize_for(self, viewer_id, role):
        role = normalize_role(role)
        can_view_hidden = role in PRIVILEGED_VIEW_ROLES
        pending_choice = self.rules_engine.get("pendingChoice")
        pending_choice_view = (
            {
                key: value for key, value in pending_choice.items()
                if not key.startswith("_")
            }
            if pending_choice else None
        )
        if (
            pending_choice_view
            and pending_choice.get("kind") in {
                "deck_reorder", "peek_top_card", "guess_top_card",
                "draw_replacement",
                "suspend_hand_will", "chain_manifestation",
            }
            and viewer_id != pending_choice.get("playerId")
            and not can_view_hidden
        ):
            pending_choice_view.pop("cardId", None)
            pending_choice_view.pop("cardIds", None)
            if "groups" in pending_choice_view:
                pending_choice_view["groups"] = [{
                    key: value for key, value in group.items()
                    if key != "cardIds"
                } for group in pending_choice_view["groups"]]
        if (
            pending_choice_view
            and "candidateCardIds" in pending_choice_view
            and viewer_id != pending_choice.get("playerId")
            and not can_view_hidden
        ):
            pending_choice_view.pop("candidateCardIds", None)
        players_view = {}
        for pid, player in self.players.items():
            zones_view = {}
            for zone, cards in player["zones"].items():
                if self.can_view_zone(viewer_id, role, pid, zone):
                    zones_view[zone] = {
                        "cards": list(cards),
                        "owners": {card_id: self.card_owner_in_zone(pid, zone, card_id) for card_id in cards},
                    }
                else:
                    zones_view[zone] = {"count": len(cards)}
            players_view[pid] = {
                "id": pid,
                "name": player["name"],
                "connected": player["connected"],
                "score": player["score"],
                "seat": player["seat"],
                "zones": zones_view,
                "cardRarities": dict(player.get("cardRarities", {})) if can_view_hidden or pid == viewer_id else {},
                "deckDefinition": player.get("deckDefinition") if can_view_hidden or pid == viewer_id else None,
                "sideboard": list(player.get("sideboard", [])) if can_view_hidden or pid == viewer_id else {"count": len(player.get("sideboard", []))},
                "activity": player.get("activity"),
            }

        zone_entry_turns_view = {}
        for entry_key, entry_turn in self.rules_engine["zoneEntryTurns"].items():
            parts = entry_key.split(":", 2)
            if len(parts) != 3:
                if can_view_hidden:
                    zone_entry_turns_view[entry_key] = entry_turn
                continue
            owner_id, zone, _card_id = parts
            if self.can_view_zone(viewer_id, role, owner_id, zone):
                zone_entry_turns_view[entry_key] = entry_turn

        conditional_support_hand_card_ids = self.rules_conditional_support_hand_card_ids()
        if not can_view_hidden:
            conditional_support_hand_card_ids = (
                {viewer_id: conditional_support_hand_card_ids.get(viewer_id, [])}
                if viewer_id in self.players else {}
            )

        play_permissions_view = [
            dict(entry) for entry in self.rules_engine["playPermissions"]
            if can_view_hidden or entry.get("playerId") == viewer_id
        ]

        battlefield_view = []
        for item in self.battlefield:
            # the owner sees their own hidden cards; a trusted observer sees everything too
            can_peek = can_view_hidden or item["ownerId"] == viewer_id
            if (
                not can_peek and self.rules_engine["enabled"]
                and item["id"] in (self.rules_engine.get("firstManifestationItemIds") or {}).values()
                and item["ownerId"] in self.rules_engine["firstManifestationValidatedPlayerIds"]
                and viewer_id in self.players and viewer_id != item["ownerId"]
                and self.rules_plays_first_manifestation_after(viewer_id)
            ):
                can_peek = True  # Hermetic Hourglass: the opponent's First Manifestation is shown first
            if item["faceUp"] or can_peek:
                card_id = item["cardId"]
            else:
                card_id = None
            entry = {
                "id": item["id"],
                "ownerId": item["ownerId"],
                "cardId": card_id,
                "x": item["x"],
                "y": item["y"],
                "faceUp": item["faceUp"],
                "rotation": item["rotation"],
                "counters": item["counters"],
            }
            if item.get("fieldZone"):
                entry["fieldZone"] = item["fieldZone"]
            elif self.rules_engine.get("enabled") and self.rules_field_zone(item) == "confrontation":
                # a First Manifestation stands in the Confrontation (rules_field_zone):
                # say so, so every client check reads the same zone (Unruly Flail...)
                entry["fieldZone"] = "confrontation"
            if item.get("isSupport"):
                entry["isSupport"] = True
            if item.get("manualStack"):
                entry["manualStack"] = item["manualStack"]
            if item.get("chosenTemperament"):
                entry["chosenTemperament"] = item["chosenTemperament"]
            if item.get("supportUntilTurn"):
                entry["supportUntilTurn"] = item["supportUntilTurn"]
            if (
                self.rules_engine["enabled"] and item.get("faceUp")
                and item.get("fieldZone") == "interzone"
                and self.rules_item_card_rules(item).get("type") == "manifestation"
                and self.rules_card_can_enter_support(item)
            ):
                entry["canEnterSupport"] = True
            if item.get("isChained"):
                entry["isChained"] = True
            controller_id = self.rules_item_controller_id(item)
            if controller_id and controller_id != item.get("ownerId"):
                entry["controllerId"] = controller_id
            if item.get("temperamentOverride") in RULES_TEMPERAMENTS:
                entry["temperamentOverride"] = item["temperamentOverride"]
            if item.get("confrontationOrder"):
                entry["confrontationOrder"] = item["confrontationOrder"]
            if item.get("effectsDisabled"):
                entry["effectsDisabled"] = True
            elif (
                self.rules_engine["enabled"] and item.get("faceUp")
                and not self.rules_item_effects_active(item)
            ):
                # lost effects (Stalemate Zone, Discombobulator, lose_effects...): no action offered
                entry["effectsInactive"] = True
            if item.get("playableFree"):
                entry["playableFree"] = item["playableFree"]
            if item.get("willManifestation"):
                # Rinq / Ju Lien: a Will that counts as a Manifestation until the Resolution
                entry["willManifestation"] = True
            if item.get("attachedCards"):
                entry["attachedCards"] = [dict(card) for card in item["attachedCards"]]
            for option_key in ("outcastOff", "karmapultAuto", "gummoCopy", "persuaded"):
                if item.get(option_key):
                    entry[option_key] = item[option_key]
            if item.get("concealedWill") and can_peek:
                entry["concealedWill"] = True
                if item.get("concealedFree"):
                    entry["concealedFree"] = True
                if item.get("tebebeConcealed"):
                    entry["tebebeConcealed"] = True
            if item.get("isTokenCard"):
                entry["isTokenCard"] = True
                entry["temperament"] = item["temperament"]
                entry["power"] = item["power"]
            elif item.get("isCopy"):
                entry["isCopy"] = True
                if card_id is not None and item.get("rarity"):
                    entry["rarity"] = item["rarity"]
            elif card_id is not None and item.get("rarity"):
                entry["rarity"] = item["rarity"]
            if (
                self.rules_engine["enabled"] and item.get("faceUp")
                and (item.get("isTokenCard") or self.rules_item_card_rules(item).get("type") == "manifestation")
            ):
                characteristics = self.rules_manifestation_characteristics(item)
                entry["effectivePower"] = characteristics["power"]
                entry["effectiveTemperament"] = characteristics["temperament"]
                if self.rules_field_zone(item) == "confrontation":
                    # what this card really adds to the total compared at the Resolution
                    # (never below 0, ignored Power and Spite thresholds count as 0)
                    entry["confrontationPower"] = self.rules_confrontation_power(item)
            if item.get("stackedOn"):
                entry["stackedOn"] = item["stackedOn"]
                entry["stackOffsetX"] = item["stackOffsetX"]
                entry["stackOffsetY"] = item["stackOffsetY"]
            battlefield_view.append(entry)

        return {
            "type": "state",
            "players": players_view,
            "battlefield": battlefield_view,
            "tokens": list(self.tokens),
            "strokes": list(self.strokes),
            "ended": self.ended,
            "mode": self.mode,
            "tournament": self.tournament_summary(role) if self.mode == "tournament" else None,
            "deckPolicy": {
                "enabled": self.ban_list_enabled,
                "policy": self.tournament_policy if self.ban_list_enabled else {"bannedCardIds": [], "restrictedGroups": []},
            },
            "phaseTracker": self.serialize_phase_tracker(),
            "rulesEngine": {
                "enabled": self.rules_engine["enabled"],
                "autoSkipPhases": bool(self.rules_engine.get("autoSkipPhases", True)),
                "autoSkipOffPlayerIds": list(self.rules_engine.get("autoSkipOffPlayerIds") or []),
                "passAllPlayerIds": list(self.rules_engine.get("passAllPlayerIds") or []),
                "deckConfirmedPlayerIds": list(self.rules_engine["deckConfirmedPlayerIds"]),
                "openingHandPlayerIds": list(self.rules_engine["openingHandPlayerIds"]),
                "mulliganPlayerIds": list(self.rules_engine["mulliganPlayerIds"]),
                "openingMulliganRequiredPlayerIds": list(self.rules_engine["openingMulliganRequiredPlayerIds"]),
                "openingMulliganFailedPlayerIds": list(self.rules_engine["openingMulliganFailedPlayerIds"]),
                "readyPlayerIds": list(self.rules_engine["readyPlayerIds"]),
                "recoveryMulliganTurn": self.rules_engine["recoveryMulliganTurn"],
                "recoveryMulliganPlayerIds": list(self.rules_engine["recoveryMulliganPlayerIds"]),
                "recoveryMulliganRequiredPlayerIds": list(self.rules_engine["recoveryMulliganRequiredPlayerIds"]),
                "recoveryMulliganFailedPlayerIds": list(self.rules_engine["recoveryMulliganFailedPlayerIds"]),
                "beginningTriggersTurn": self.rules_engine["beginningTriggersTurn"],
                "beginningPermissionsTurn": self.rules_engine["beginningPermissionsTurn"],
                "playPermissions": play_permissions_view,
                "supportEntries": [dict(entry) for entry in self.rules_engine["supportEntries"]],
                "playRestrictions": [dict(entry) for entry in self.rules_engine["playRestrictions"]],
                "zoneEntryTurns": zone_entry_turns_view,
                "recentLimboEntries": [
                    dict(entry)
                    for entry in self.rules_engine.get(
                        "recentLimboEntries"
                    ) or []
                    if int(entry.get("turn") or 0)
                    == self.phase_tracker["turn"]
                ],
                "handLimitEffects": [
                    dict(entry) for entry in self.rules_engine["handLimitEffects"]
                ],
                "tributePowerOverrides": self.rules_tribute_power_overrides_snapshot(),
                "outcome": self.rules_engine["outcome"],
                "priorityPlayerId": self.rules_engine["priorityPlayerId"],
                "resolvePrompt": self.rules_confrontation_resolve_prompt(),
                # Pin Down and similar locks: no Manifestation may enter the Confrontation Zone
                "supportEntryLocked": bool(
                    viewer_id in self.players and self.rules_support_entry_locked(viewer_id)
                ),
                "conditionalSupportHandCardIds": conditional_support_hand_card_ids,
                "priorityPasses": list(self.rules_engine["priorityPasses"]),
                "actionStack": list(self.rules_engine["actionStack"]),
                "lastResolvedAction": self.rules_engine["lastResolvedAction"],
                "ongoingEffects": list(self.rules_engine["ongoingEffects"]),
                "effectMemories": [
                    {
                        "id": memory.get("id"),
                        "ownerId": memory.get("ownerId"),
                        "controllerId": memory.get("controllerId"),
                        "cardId": memory.get("cardId"),
                        "kind": memory.get("kind"),
                        "createdTurn": memory.get("createdTurn"),
                        "data": dict(memory.get("data") or {}),
                    }
                    for memory in self.rules_engine.get("effectMemories") or []
                ],
                "suspendedCards": [{
                    "id": entry.get("id"),
                    "ownerId": entry.get("ownerId"),
                    "cardId": (
                        entry.get("cardId")
                        if entry.get("fromZone") == "battlefield"
                        or viewer_id == entry.get("playableByPlayerId")
                        or self.can_view_zone(
                            viewer_id, role,
                            entry.get("fromContainerId") or entry.get("ownerId"),
                            entry.get("fromZone"),
                        )
                        else None
                    ),
                    "sourceEffectId": entry.get("sourceEffectId"),
                    "playableByPlayerId": entry.get("playableByPlayerId"),
                    "returnTurn": entry.get("returnTurn"),
                } for entry in self.rules_engine.get("suspendedCards") or []],
                "pendingChoice": pending_choice_view,
                "firstManifestationItemIds": dict(self.rules_engine["firstManifestationItemIds"]),
                "firstManifestationValidatedPlayerIds": list(self.rules_engine["firstManifestationValidatedPlayerIds"]),
                "trapPlayerIds": list(self.rules_engine.get("trapPlayerIds") or []),
                # hand cards whose hand effect the viewer could use now (Ranba's condition...)
                "usableHandAbilityCardIds": self.rules_usable_hand_ability_card_ids(viewer_id),
                # a Trap waiting in place of a First Manifestation: face down for the opponent
                "trapCards": {
                    pid: {
                        "cardId": trap["cardId"] if trap.get("revealed") or viewer_id == pid else None,
                        "revealed": bool(trap.get("revealed")),
                    }
                    for pid, trap in (self.rules_engine.get("trapCards") or {}).items()
                },
                "limboRecoveryPlayerIds": list(self.rules_engine.get("limboRecoveryPlayerIds") or []),
                "uncoveredHand": {
                    pid: [
                        c for c in dict.fromkeys(self.rules_engine.get("limboDrawn", {}).get(pid) or [])
                        if c in self.players[pid]["zones"]["hand"]
                    ]
                    for pid in self.players if self.rules_engine.get("limboDrawn", {}).get(pid)
                },
                "uncoveredTops": {
                    pid: self.players[pid]["zones"]["deck"][0]
                    for pid in self.players if self.rules_uncovered_deck_top(pid)
                },
                "firstManifestationComplete": self.rules_engine["firstManifestationComplete"],
                "confrontationResult": dict(self.rules_engine["confrontationResult"]) if self.rules_engine["confrontationResult"] else None,
                "lastConfrontationWinnerId": self.rules_engine["lastConfrontationWinnerId"],
            },
            # a small tail of the action log, piggybacked on every state sync so
            # the opponent-row mini activity feed updates live without a
            # separate poll — the full log (request_log) is still the
            # authoritative, complete history used for the debug/download panel
            "recentLog": [
                self.log_entry_for_role(entry, role) for entry in self.log[-30:]
                if self.log_entry_visible_to(entry, role)
            ],
        }

    @staticmethod
    def log_entry_visible_to(entry, role):
        """The observers' own chat stays out of what the players receive."""
        return not (
            normalize_role(role) == "player"
            and entry.get("type") == "chat_message"
            and (entry.get("details") or {}).get("channel") == "observers"
        )

    def log_entry_for_role(self, entry, role):
        if self.mode != "tournament" or normalize_role(role) not in {"player", "spectator"}:
            return entry
        redacted = dict(entry)
        details = dict(entry.get("details") or {})
        for key in ("cardId", "cardIds", "cards", "deck", "deckDefinition", "sideboard"):
            details.pop(key, None)
        redacted["details"] = details
        return redacted

    def serialize_log(self, role="observer"):
        return {"type": "log", "entries": [
            self.log_entry_for_role(entry, role) for entry in self.log
            if self.log_entry_visible_to(entry, role)
        ]}
