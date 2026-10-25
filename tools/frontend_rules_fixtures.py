"""Browser parity fixtures built with production rules and recipient serializers."""

import json

import card_scenario_batches as batches


def target_key(target):
    if target["kind"] == "card":
        return "card:" + str(target.get("itemId") or target.get("id"))
    if target["kind"] == "zone_card":
        return ":".join(str(target.get(key)) for key in ("kind", "containerId", "zone", "cardId"))
    if target["kind"] == "player":
        return "player:" + target["playerId"]
    return "stack:" + target["actionId"]


def fixture(card_id, ability, variant="ready"):
    session, actor, source, targets, _cost = batches.prepare_action(card_id, ability)
    item = session.find_battlefield_item(source.get("itemId"))
    if variant.startswith("play-window:"):
        session.phase_tracker["index"] = batches.ADVANCED_PHASES.index(variant.split(":", 1)[1])
    elif variant == "used-up":
        item["abilityUses"] = {ability["id"]: ability["useLimit"]}
    elif variant == "used-this-turn":
        item["abilityTurnUses"] = {ability["id"]: session.phase_tracker["turn"]}
    elif variant == "no-created-token":
        session.battlefield = [entry for entry in session.battlefield if not entry.get("isTokenCard")]
    elif variant == "empty-hand":
        session.players[actor]["zones"]["hand"] = [card_id] if source["zone"] == "hand" else []
    elif variant == "implicit-field-zone":
        item.pop("fieldZone", None)
    elif variant in {"protected-targets", "immune-targets"}:
        session.rules_engine["ongoingEffects"].extend({
            "kind": "protection" if variant == "protected-targets" else "immune",
            "duration": "end_of_turn", "fromOpponents": True,
            "target": {"itemId": entry["id"]},
        } for entry in session.battlefield)
    elif variant == "wrong-stack-target":
        for action in session.rules_engine["actionStack"]:
            action["targets"] = []
    elif variant == "wrong-effect-temperament":
        item["chosenTemperament"] = "hollow"
    elif variant == "generic-token-targets":
        for pid in session.players:
            for zone in ("confrontation", "interzone"):
                session.create_rules_token_copy(None, pid, generic_power=6,
                    generic_temperament="phlegmatic", field_zone=zone)
    contract = session.rules_action_target_rules({"ability": ability}) or {}
    groups = contract.get("groups")
    expected_targets = []
    for index, group in enumerate(groups if isinstance(groups, list) else [contract]):
        if not groups and int(group.get("max") or 0) == 0:
            continue
        legal = session.rules_legal_target_candidates(
            group, actor, source_item_id=source.get("itemId"), source_card_id=card_id,
        )
        expected_targets.extend(f"{index}:{target_key(target)}" for target in legal)
    error, _ability = session.rules_action_ability(
        actor, ability.get("action") or "activated_effect", source, ability["id"], targets,
    )
    used_ids = {entry.get("cardId") for entry in session.battlefield}
    used_ids.update((entry.get("source") or {}).get("cardId") for entry in session.rules_engine["actionStack"])
    for player in session.players.values():
        for cards in player["zones"].values():
            used_ids.update(cards)
    overrides = [{"id": cid, "name": cid, "effect": "", **session.card_rules[cid],
                  "points": session.card_points.get(cid)}
                 for cid in used_ids if cid and cid not in batches.main.CARD_RULES]
    result = {"label": f"{card_id}/{ability['id']}/{variant}", "ability": ability,
            "source": source, "actor": actor, "state": session.serialize_for(actor, "player"),
            "cards": overrides, "targets": sorted(set(expected_targets)),
            "sourceAllowed": None if variant in {"protected-targets", "immune-targets", "wrong-stack-target", "wrong-effect-temperament"} else error is None,
            "serverError": error}
    if variant.startswith("play-window:"):
        error, _action = session.declare_rules_action(
            actor, "Catalog play timing", kind="play_card", source=source,
            payment_card_ids=[], targets=[],
        )
        result["playable"] = error is None
        result["serverError"] = error
    return result


def build():
    fixtures = []
    for card_id, abilities in batches.main.CARD_ABILITIES.items():
        for ability in abilities:
            if ability.get("trigger") or ability.get("passiveEffect") or ability.get("playPermission"):
                continue
            if (ability.get("result") or {}).get("kind") in {"first_manifestation_trap", "create_essence"}:
                continue  # dedicated placement and permanent counter conversion UI
            fixtures.append(fixture(card_id, ability))
            variants = []
            if ability.get("useLimit"):
                variants.append("used-up")
            if ability.get("usePerTurn"):
                variants.append("used-this-turn")
            if ability.get("sacrificeTokenCreatedBySource"):
                variants.append("no-created-token")
            if ability.get("requireHandManifestations") or ability.get("requireHandCard"):
                variants.append("empty-hand")
            if ability.get("sourceFieldZone") == "field":
                variants.append("implicit-field-zone")
            contracts = ability.get("targetGroups") or (ability.get("targets") or {}).get("groups") or [ability.get("targets") or {}]
            if any((contract.get("kind") or "card") in {"card", "card_or_stack_action"} and int(contract.get("max") or 0) for contract in contracts):
                variants.extend(["protected-targets", "immune-targets", "generic-token-targets"])
            if any(contract.get("targetsFieldCard") or contract.get("targetsOwnFieldCard") or contract.get("targetsConfrontationManifestation") for contract in contracts):
                variants.append("wrong-stack-target")
            if any(contract.get("effectTemperamentChosenBySource") for contract in contracts):
                variants.append("wrong-effect-temperament")
            fixtures.extend(fixture(card_id, ability, variant) for variant in variants)
    for card_id, metadata in batches.main.CARD_RULES.items():
        if metadata.get("type") not in {"ephemeral_will", "persistent_will"} and not metadata.get("playAsPersistentWill"):
            continue
        if metadata.get("playedAbilities"):
            continue
        for phase in ("confrontation_reaction", "confrontation_before_revelation", "end_actions"):
            fixtures.append(fixture(card_id, {"id": "printed-play", "action": "play_card", "targets": {"min": 0, "max": 0}}, f"play-window:{phase}"))
    return fixtures


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=True))
