"""Local card sandbox: one prepared game state per card, to test it by hand or by script.

Only active when the server runs with KKO_SANDBOX=1. A scenario (sandbox/scenarios.json)
describes the two players' zones, the field, the step and who has priority; cards
without a written scenario get a generic one built from their type. A scenario can
also carry a `script`: real client messages (same path as the browser) followed by
`expect` checks, run by tests/test_sandbox_scenarios.py and by the sandbox panel.
"""
import copy
import json
import os
import re
import time

from session import ADVANCED_PHASES, new_id

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
SANDBOX_DIR = os.path.join(ROOT, "sandbox")
SCENARIOS_PATH = os.path.join(SANDBOX_DIR, "scenarios.json")
VALIDATION_PATH = os.path.join(SANDBOX_DIR, "validation.json")
OPPONENT_ID = "sandbox-opponent"
VALIDATION_STATUSES = {"ok", "bug", "todo"}


def enabled():
    return os.environ.get("KKO_SANDBOX") == "1"


def load_scenarios():
    try:
        with open(SCENARIOS_PATH, "r", encoding="utf-8") as scenario_file:
            return json.load(scenario_file).get("scenarios") or []
    except FileNotFoundError:
        return []


def load_validation():
    try:
        with open(VALIDATION_PATH, "r", encoding="utf-8") as validation_file:
            return json.load(validation_file)
    except (FileNotFoundError, ValueError):
        return {}


def write_validation(data):
    os.makedirs(SANDBOX_DIR, exist_ok=True)
    with open(VALIDATION_PATH, "w", encoding="utf-8") as validation_file:
        json.dump(data, validation_file, ensure_ascii=False, indent=2, sort_keys=True)
        validation_file.write("\n")


def validation_entry(status, note, scenario_id=None, auto=False):
    entry = {
        "status": status,
        "note": " ".join(str(note or "").split())[:500],
        "scenarioId": scenario_id,
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    if auto:
        entry["auto"] = True
    return entry


def save_validation(card_id, status, note, scenario_id=None):
    if status not in VALIDATION_STATUSES:
        raise ValueError("Unknown validation status.")
    data = load_validation()
    if status == "todo":
        data.pop(card_id, None)
    else:
        data[card_id] = validation_entry(status, note, scenario_id)
    write_validation(data)
    return data


# Printed lines whose whole meaning is a rules flag the engine already handles
# generically: a card made only of these (or of no text at all) can be validated
# by checking its compiled flags plus one scripted play, without a human look.
SIMPLE_LINES = {
    "support.": ("supportFromHand", "supportFromInterzone"),
    "support from hand.": ("supportFromHand",),
    "support from hand; float.": ("supportFromHand", "float"),
    "support; float.": ("supportFromHand", "supportFromInterzone", "float"),
    "float.": ("float",),
    "adamant.": ("adamant",),
    "cannot be played as first manifestation.": ("notFirst",),
    "cannot be used as tribute.": ("noTribute",),
    "can be used as tribute from the interzone.": ("canPayTributeFromInterzone",),
    "~ can be used as tribute from the interzone.": ("canPayTributeFromInterzone",),
    "in the end phase, ~ can be played into the interzone.": ("endPhaseInterzonePlay",),
    "if ~ is used as tribute, it is put on the bottom of its owner's deck instead of entering the limbo.":
        ("tributeDestination:deck_bottom",),
    "if ~ is used as tribute, it is put into the stalemate zone instead of entering the limbo.":
        ("tributeDestination:stalemate",),
}
# "When X is used as tribute, it can also be considered of {B} temperament."
ALT_TRIBUTE_LINE = re.compile(r"^when ~ is used as tribute, it can also be considered of \{([gbpyr])\} temperament\.$")
# "If X is used as tribute, it is considered to have a base power of 🌿🌿." (from any zone)
TRIBUTE_POWER_LINE = re.compile(r"^if ~ is used as tribute, it is considered (?:to have a base power of|of base power) (.+)\.$")
SYMBOL_TEMPERAMENT = {"g": "phlegmatic", "b": "vitreous", "p": "melancholic", "y": "capricious", "r": "choleric"}
TEMPERAMENT_LABELS = {
    "phlegmatic": "Flegmatique", "vitreous": "Vitreux", "melancholic": "Mélancolique",
    "capricious": "Capricieux", "choleric": "Colérique",
}
SIMPLE_KEYWORD_LABELS = {
    "supportFromHand": "Support depuis la main", "supportFromInterzone": "Support depuis l'Interzone",
    "float": "Float", "adamant": "Adamant", "notFirst": "pas en Première Manifestation",
    "noTribute": "pas de tribut", "canPayTributeFromInterzone": "tribut depuis l'Interzone",
    "endPhaseInterzonePlay": "jouable en Interzone en Fin de tour",
    "tributeDestination:deck_bottom": "tribut sous le deck", "tributeDestination:stalemate": "tribut en Impasse",
}


def effect_lines(card):
    return [line.strip() for line in str(card.get("effect") or "").replace("\r", "").split("\n") if line.strip()]


def card_line_key(card, line):
    """The line in lower case with the card's own name replaced by ~."""
    key = " ".join(line.lower().split())
    name = str(card.get("name") or "").lower()
    for variant in (f"the {name}", name, f"the {name.split(',')[0]}", name.split(",")[0]):
        if variant:
            key = key.replace(variant, "~")
    return key


def simple_keywords(card, abilities):
    """The keyword flags of a card made only of simple lines; None for any other card."""
    if card.get("type") != "manifestation" or abilities.get(card["id"]):
        return None
    keywords = []
    for line in effect_lines(card):
        key = card_line_key(card, line)
        flags = SIMPLE_LINES.get(key)
        alternate = ALT_TRIBUTE_LINE.match(key)
        if alternate:
            flags = (f"tributeTemperament:{SYMBOL_TEMPERAMENT[alternate.group(1)]}",)
        tribute_power = TRIBUTE_POWER_LINE.match(key)
        if tribute_power:
            symbols = re.findall(r"\{[a-z]\}|[🔥🌿💧🔮⚡🌈]", tribute_power.group(1))
            flags = (f"tributePower:{len(symbols)}",) if symbols else None
        if flags is None:
            return None
        keywords.extend(flag for flag in flags if flag not in keywords)
    return keywords


def simple_label(keywords):
    labels = []
    for keyword in keywords:
        if keyword.startswith("tributePower:"):
            labels.append(f"vaut {keyword.split(':')[1]} en tribut")
        elif keyword.startswith("tributeTemperament:"):
            labels.append(f"tribut aussi {TEMPERAMENT_LABELS[keyword.split(':')[1]]}")
        else:
            labels.append(SIMPLE_KEYWORD_LABELS.get(keyword, keyword))
    return ", ".join(labels) or "sans texte"


class Catalog:
    """Card data, compiled rules and the filler Manifestations used to set a table."""

    def __init__(self, cards, abilities, card_rules=None):
        self.cards = {card["id"]: card for card in cards}
        self.order = [card["id"] for card in cards]
        self.abilities = abilities
        self.rules = card_rules or {}
        self.simple = {
            card["id"]: keywords for card in cards
            if (keywords := simple_keywords(card, abilities)) is not None
        }
        # fillers, best first: no text at all, then keyword-only cards, then the shortest texts
        manifestations = [card["id"] for card in cards if card.get("type") == "manifestation"]
        vanilla = [card_id for card_id in manifestations if self.simple.get(card_id) == []]
        keyword_only = [card_id for card_id in manifestations if self.simple.get(card_id)]
        rest = sorted(
            (card_id for card_id in manifestations if card_id not in self.simple),
            key=lambda card_id: len(str(self.cards[card_id].get("effect") or "")),
        )
        self.vanilla = vanilla
        self.fillers = vanilla + keyword_only + rest

    def index(self, coverage=None, validation=None):
        """Lightweight card list for the sandbox picker."""
        scenarios = load_scenarios()
        by_card = {}
        for scenario in scenarios:
            by_card.setdefault(scenario["cardId"], []).append(
                {"id": scenario["id"], "title": scenario.get("title") or scenario["id"],
                 "scripted": bool(scenario.get("script"))}
            )
        rows = []
        for card_id in self.order:
            card = self.cards[card_id]
            rows.append({
                "id": card_id,
                "name": card.get("name"),
                "number": card.get("collectionNumber"),
                "set": card.get("setName"),
                "type": card.get("type"),
                "temperaments": card.get("temperaments") or [],
                "coverage": ((coverage or {}).get(card_id) or {}).get("status"),
                "scenarios": by_card.get(card_id, []),
                "variants": [
                    {"id": scenario["id"], "title": scenario["title"], "scripted": bool(scenario.get("script"))}
                    for scenario in generic_scenarios(self, card_id)
                ],
                "simple": card_id in self.simple,
                "validation": (validation or {}).get(card_id),
            })
        return rows


class Allocator:
    """Hands out unique card ids: a Kartomantik deck never holds two copies of a card."""

    def __init__(self, catalog, reserved=()):
        self.catalog = catalog
        self.used = set(reserved)

    def take(self, spec):
        spec = str(spec)
        if not spec.startswith("vanilla"):
            if spec not in self.catalog.cards:
                raise ValueError(f"Unknown card id in scenario: {spec}")
            self.used.add(spec)
            return spec
        _, _, rest = spec.partition(":")
        temperament, _, power = rest.partition(":")
        free = [card_id for card_id in self.catalog.fillers if card_id not in self.used]
        tier = [card_id for card_id in free if card_id in self.catalog.vanilla] or free
        candidates = tier
        if temperament:
            candidates = [
                card_id for card_id in tier
                if temperament in (self.catalog.cards[card_id].get("temperaments") or [])
            ] or [
                card_id for card_id in free
                if temperament in (self.catalog.cards[card_id].get("temperaments") or [])
            ] or tier
        if power:
            # "4" = closest to 4, "4+" = at least 4 (a tribute that pays a cost of 4)
            at_least = power.endswith("+")
            target = int(power.rstrip("+"))
            power_of = lambda card_id: int(self.catalog.cards[card_id].get("power") or 0)
            # stable sort: among equally close powers the better filler tier stays first
            candidates = sorted(candidates, key=lambda card_id: (
                at_least and power_of(card_id) < target, abs(power_of(card_id) - target),
            ))
        card_id = candidates[0]
        self.used.add(card_id)
        return card_id


def payment_temperament(card):
    temperaments = [temp for temp in (card.get("temperaments") or []) if temp not in {"hollow", "transcendent"}]
    return temperaments[0] if temperaments else ""


def _ability_zones(catalog, card_id):
    """Where the card's abilities can be used from: 'hand', 'interzone', 'field'."""
    zones = set()
    for ability in catalog.abilities.get(card_id) or []:
        source_zones = ability.get("sourceZones") or []
        if "hand" in source_zones:
            zones.add("hand")
        if ability.get("sourceFieldZone") == "interzone":
            zones.add("interzone")
    return zones


def _has_trigger(catalog, card_id, *events):
    return any(
        (ability.get("trigger") or {}).get("event") in events
        for ability in catalog.abilities.get(card_id) or []
    )


def generic_scenarios(catalog, card_id):
    """Starting states built from the card's type and abilities, most useful first.

    Manifestations: in Confrontation (default), as First Manifestation still in hand
    (reveal and enter-the-field triggers), in hand at Reaction (Support from hand,
    abilities from the hand) and in the Interzone (Support from the Interzone,
    Interzone abilities and bonuses). Wills: in hand with their payment at a step
    where they can be played; a Persistent Will also already resolved on the field.
    """
    card = catalog.cards[card_id]
    rules = catalog.rules.get(card_id) or {}
    card_type = card.get("type")
    text = str(card.get("effect") or "").lower()
    name = card.get("name")
    variants = []

    def scenario(variant, title, phase, hand, battlefield, checks, **extra):
        variants.append({
            "id": f"generic:{variant}:{card_id}", "cardId": card_id, "generic": True,
            "title": title, "phase": phase, "turn": 2, "priority": "me",
            "players": {
                "me": {"hand": hand, "deck": 6, "graveyard": 1},
                "opp": {"hand": 2, "deck": 6, "graveyard": 1},
            },
            "battlefield": battlefield, "checks": checks, **extra,
        })

    opp_side = [
        {"id": "opp-fighter", "owner": "opp", "card": "vanilla::3", "zone": "confrontation", "first": True},
        {"id": "opp-interzone", "owner": "opp", "card": "vanilla::2", "zone": "interzone"},
    ]
    my_fighter = {"id": "my-fighter", "owner": "me", "card": "vanilla::3", "zone": "confrontation", "first": True}
    if card_type == "manifestation":
        zones = _ability_zones(catalog, card_id)
        entry_first = _has_trigger(catalog, card_id, "enters_field", "enters_field_zone", "revelation", "before_revelation")
        confrontation = lambda: scenario(
            "confrontation", f"{name} en Confrontation", "confrontation_reaction",
            ["vanilla", "vanilla", "vanilla"],
            [{"id": "tested", "owner": "me", "card": "$card", "zone": "confrontation", "first": True},
             {"id": "my-interzone", "owner": "me", "card": "vanilla::2", "zone": "interzone"}] + opp_side,
            ["La carte est révélée sur ta Zone de Confrontation, contre une Manifestation adverse.",
             "Vérifie sa puissance affichée, ses capacités sur le terrain, puis passe pour voir la Résolution."],
        )
        first = lambda: scenario(
            "first", f"{name} en Première Manifestation", "confrontation_choose",
            ["$card", "vanilla", "vanilla"],
            [{"id": "opp-fighter", "owner": "opp", "card": "vanilla::3", "zone": "confrontation",
              "first": True, "faceUp": False, "validated": True},
             {"id": "my-interzone", "owner": "me", "card": "vanilla::2", "zone": "interzone"},
             {"id": "opp-interzone", "owner": "opp", "card": "vanilla::2", "zone": "interzone"}],
            ["L'adversaire a déjà posé et validé sa Première Manifestation, face cachée.",
             "Pose la carte face cachée sur ta Zone de Confrontation et valide : révélation, puis ses effets d'entrée."],
            firstManifestation=True,
            script=[
                {"label": "Poser la carte face cachée en Confrontation", "send": {
                    "type": "place_card", "fromZone": "hand", "cardId": "$card", "x": 0, "y": 0, "faceUp": False,
                }},
                {"label": "Les deux Premières Manifestations sont choisies", "expect": {"phase": "confrontation_before_revelation"}},
                {"label": "Passer jusqu'à la Réaction (ou au premier choix demandé)",
                 "passUntil": {"phase": "confrontation_reaction", "orChoice": True}},
                {"label": "La carte est révélée en Confrontation", "expect": {"cardOnField": "$card", "zone": "confrontation", "faceUp": True}},
            ],
        )
        if (not rules.get("canBeFirstManifestation", True) or rules.get("cannotEnterConfrontation")
                or rules.get("confrontationEntryLimboWills")):
            confrontation()
        elif entry_first:
            first()
            confrontation()
        else:
            confrontation()
            first()
        if (rules.get("supportFromHand") or rules.get("supportFromHandCondition") or "hand" in zones
                or _has_trigger(catalog, card_id, "enters_support")):
            scenario(
                "hand", f"{name} en main, à la Réaction", "confrontation_reaction",
                ["$card", "vanilla", "vanilla"],
                [my_fighter, {"id": "my-interzone", "owner": "me", "card": "vanilla::2", "zone": "interzone"}] + opp_side,
                ["La carte est en main pendant la Réaction, avec la priorité.",
                 "Joue-la en Support depuis la main, ou utilise sa capacité depuis la main."],
            )
        if (rules.get("supportFromInterzone") or "interzone" in zones or "interzone" in text
                or rules.get("canPayTributeFromInterzone")):
            scenario(
                "interzone", f"{name} dans ton Interzone", "confrontation_reaction",
                ["vanilla", "vanilla", "vanilla"],
                [my_fighter, {"id": "tested", "owner": "me", "card": "$card", "zone": "interzone"}] + opp_side,
                ["La carte attend dans ton Interzone pendant la Réaction, avec la priorité.",
                 "Teste son entrée en Support, sa capacité ou son bonus depuis l'Interzone."],
            )
    else:
        payment = [f"vanilla:{payment_temperament(card)}:{max(int(card.get('cost') or 0), 1)}+", "vanilla", "vanilla"]
        phase = "end_actions" if card_type == "persistent_will" else "confrontation_reaction"
        play_phases = rules.get("playPhases") or []
        if play_phases and phase not in play_phases:
            phase = play_phases[0]
        if rules.get("playBeforeRevelation"):
            phase = "confrontation_before_revelation"
        scenario(
            "hand", f"{name} en main", phase, ["$card"] + payment,
            [my_fighter, {"id": "my-interzone", "owner": "me", "card": "vanilla::2", "zone": "interzone"}] + opp_side,
            ["La carte doit briller comme jouable dans ta main.",
             "Joue-la : coût (une Manifestation de ta main en tribut), cibles, Pile, résolution et animation."],
        )
        if card_type == "persistent_will":
            scenario(
                "field", f"{name} déjà résolue sur le terrain", "confrontation_reaction",
                ["vanilla", "vanilla", "vanilla"],
                [my_fighter, {"id": "tested", "owner": "me", "card": "$card", "zone": "field"},
                 {"id": "my-interzone", "owner": "me", "card": "vanilla::2", "zone": "interzone"}] + opp_side,
                ["La Volonté est déjà sur le terrain, côté Volontés.",
                 "Teste ses effets continus et ses capacités activées."],
            )
    if card_id in catalog.simple:
        attach_simple_script(catalog, card_id, variants)
    return variants


def generic_scenario(catalog, card_id):
    return generic_scenarios(catalog, card_id)[0]


def attach_simple_script(catalog, card_id, variants):
    """A keyword-only card gets a script on the variant that shows its keyword."""
    keywords = catalog.simple[card_id]
    power = catalog.cards[card_id].get("power")
    by_variant = {scenario["id"].split(":")[1]: scenario for scenario in variants}
    if "supportFromHand" in keywords and "hand" in by_variant:
        by_variant["hand"]["script"] = [
            {"label": "Jouer la carte en Support depuis la main", "send": {
                "type": "declare_rules_action", "label": "Support", "kind": "play_card", "asSupport": True,
                "source": {"cardId": "$card", "zone": "hand", "containerId": "&me"}, "placement": {"x": 0, "y": 0},
            }},
            {"label": "Les deux joueurs passent", "resolve": True},
            {"label": "Elle est en Support dans ta Confrontation", "expect": {"cardOnField": "$card", "zone": "confrontation", "support": True}},
            {"label": f"Sa puissance est {power}", "expect": {"cardPower": "$card", "eq": power}},
        ]
    if "supportFromInterzone" in keywords and "interzone" in by_variant:
        by_variant["interzone"]["script"] = [
            {"label": "Entrer en Support depuis l'Interzone", "send": {
                "type": "declare_rules_action", "label": "Support", "kind": "play_card", "asSupport": True,
                "source": {"cardId": "$card", "zone": "battlefield", "itemId": "@tested"}, "placement": {"x": 0, "y": 0},
            }},
            {"label": "Les deux joueurs passent", "resolve": True},
            {"label": "Elle est en Support dans ta Confrontation", "expect": {"cardOnField": "$card", "zone": "confrontation", "support": True}},
        ]
    if "confrontation" in by_variant and not by_variant["confrontation"].get("script"):
        by_variant["confrontation"]["script"] = [
            {"label": "La carte est révélée en Confrontation", "expect": {"cardOnField": "$card", "zone": "confrontation"}},
            {"label": f"Sa puissance est {power}", "expect": {"cardPower": "$card", "eq": power}},
            {"label": "Passer jusqu'à la comparaison", "passUntil": {"phase": "resolution_compare"}},
            {"label": "La Confrontation a un résultat", "expect": {"confrontationResolved": True}},
        ]


def check_simple_card(catalog, card_id):
    """Compiled flags of a keyword-only card against its printed lines. Returns the failures."""
    keywords = set(catalog.simple[card_id])
    card = catalog.cards[card_id]
    rules = catalog.rules.get(card_id) or {}
    tribute_power = next(
        (int(keyword.split(":")[1]) for keyword in keywords if keyword.startswith("tributePower:")), None,
    )
    expected = {
        "supportFromHand": "supportFromHand" in keywords,
        "supportFromInterzone": "supportFromInterzone" in keywords,
        "float": "float" in keywords,
        "adamant": "adamant" in keywords,
        "canBeFirstManifestation": "notFirst" not in keywords,
        "canPayTribute": "noTribute" not in keywords,
        "canPayTributeFromInterzone": "canPayTributeFromInterzone" in keywords,
        "endPhaseInterzonePlay": "endPhaseInterzonePlay" in keywords,
        "tributeDestination": next(
            (keyword.split(":")[1] for keyword in keywords if keyword.startswith("tributeDestination:")), "graveyard",
        ),
        "tributeTemperaments": sorted(set(card.get("temperaments") or []) | {
            keyword.split(":")[1] for keyword in keywords if keyword.startswith("tributeTemperament:")
        }),
        "tributePowerOverride": (
            {"power": tribute_power, "condition": None} if tribute_power is not None else None
        ),
        "interzoneTributePower": tribute_power,
        "type": "manifestation",
        "power": card.get("power"),
    }
    rules = dict(rules, tributeTemperaments=sorted(rules.get("tributeTemperaments") or []))
    failures = [
        f"{key} = {rules.get(key)!r}, attendu {value!r}"
        for key, value in expected.items() if rules.get(key) != value
    ]
    for key in ("continuousPowerRules", "activatedAbilities", "playedAbilities", "triggeredAbilities",
                "playPermissions", "passiveEffects"):
        if rules.get(key):
            failures.append(f"{key} devrait être vide")
    return failures


def find_scenario(catalog, scenario_id=None, card_id=None):
    for scenario in load_scenarios():
        if scenario_id and scenario["id"] == scenario_id:
            return copy.deepcopy(scenario)
        if not scenario_id and card_id and scenario["cardId"] == card_id:
            return copy.deepcopy(scenario)
    if scenario_id and scenario_id.startswith("generic:"):
        card_id = scenario_id.rsplit(":", 1)[1]
    elif scenario_id and scenario_id.startswith("generic-"):
        card_id = scenario_id.removeprefix("generic-")
    if card_id not in catalog.cards:
        return None
    variants = generic_scenarios(catalog, card_id)
    return next((scenario for scenario in variants if scenario["id"] == scenario_id), variants[0])


def apply_scenario(session, catalog, scenario, me_id, opp_id=OPPONENT_ID, opp_name="Adversaire"):
    """Put the session in the scenario's state. Returns the alias map used by scripts."""
    seats = {"me": me_id, "opp": opp_id}
    for side, player_id in seats.items():
        if player_id not in session.players:
            session.get_or_create_player(player_id, opp_name if side == "opp" else "Testeur", seat=0 if side == "me" else 1)
    tested = scenario["cardId"]
    allocator = Allocator(catalog, reserved=[tested])
    aliases = {"$card": tested, "&me": me_id, "&opp": opp_id}

    def resolve(entry):
        spec, alias = (entry.get("card"), entry.get("as")) if isinstance(entry, dict) else (entry, None)
        if isinstance(spec, dict):
            card_id = resolve(spec)
        else:
            card_id = tested if spec == "$card" else allocator.take(spec)
        if alias:
            aliases[f"%{alias}"] = card_id
        return card_id

    def fill(zones):
        for zone in zones:
            for side, player_id in seats.items():
                player = session.players[player_id]
                raw = ((scenario.get("players") or {}).get(side) or {}).get(zone, 0)
                entries = ["vanilla"] * raw if isinstance(raw, int) else list(raw)
                cards = [resolve(entry) for entry in entries]
                player["zones"][zone] = cards
                player["zoneOwners"][zone] = {card_id: player_id for card_id in cards}

    # hands first (Will payments need fillers of one temperament), then the field,
    # then the other visible zones; hidden decks take whatever is left
    fill(("hand",))
    session.battlefield = []
    first_items = {}
    validated = []
    for index, entry in enumerate(scenario.get("battlefield") or []):
        owner_id = seats[entry.get("owner", "me")]
        item_id = entry.get("id") or new_id()
        card_id = resolve(entry)
        item = {
            "id": item_id, "ownerId": owner_id, "cardId": card_id,
            "faceUp": entry.get("faceUp", True), "fieldZone": entry.get("zone", "confrontation"),
            "counters": dict(entry.get("counters") or {}), "x": 0, "y": 0, "rotation": 0,
        }
        if item["fieldZone"] == "field":
            item.pop("fieldZone")  # resolved Wills leave their zone implicit, like the engine
        for key in ("isSupport", "exhausted"):
            if key in entry:
                item[key] = entry[key]
        session.battlefield.append(item)
        aliases[f"@{item_id}"] = item_id
        if entry.get("first"):
            first_items[owner_id] = item_id
        if entry.get("validated"):
            validated.append(owner_id)

    for side, player_id in seats.items():
        player = session.players[player_id]
        spec = (scenario.get("players") or {}).get(side) or {}
        player["score"] = int(spec.get("score") or 0)
    fill(("graveyard", "receptacle", "exile", "deck"))

    engine = session.rules_engine
    engine["deckConfirmedPlayerIds"] = [me_id, opp_id]
    engine["openingHandPlayerIds"] = [me_id, opp_id]
    engine["readyPlayerIds"] = [me_id, opp_id]
    # firstManifestation: the step where both players still choose their First
    # Manifestation (a pre-placed card marked `validated` is already locked in)
    choosing = bool(scenario.get("firstManifestation"))
    engine["firstManifestationComplete"] = not choosing
    engine["firstManifestationTriggersQueued"] = not choosing
    engine["firstManifestationItemIds"] = first_items
    engine["firstManifestationValidatedPlayerIds"] = validated
    engine["actionStack"] = []
    engine["priorityPasses"] = []
    engine["pendingChoice"] = None
    engine["outcome"] = None
    engine["confrontationResult"] = None
    engine["passAllPlayerIds"] = [opp_id] if scenario.get("opponentPasses", True) else []
    session.phase_tracker["enabled"] = True
    session.phase_tracker["advanced"] = True
    session.phase_tracker["turn"] = int(scenario.get("turn") or 2)
    session.phase_tracker["index"] = ADVANCED_PHASES.index(scenario.get("phase") or "confrontation_reaction")
    session.phase_passes = set()
    engine["priorityPlayerId"] = seats[scenario.get("priority") or "me"]
    session.ended = False
    session.sandbox = {"scenario": scenario, "aliases": aliases, "seats": seats}
    session.add_log(me_id, "sandbox_loaded", {"scenarioId": scenario["id"], "cardId": tested})
    return aliases


# ---------------------------------------------------------------- scripts

def substitute(value, aliases):
    if isinstance(value, str):
        return aliases.get(value, value)
    if isinstance(value, list):
        return [substitute(entry, aliases) for entry in value]
    if isinstance(value, dict):
        return {key: substitute(entry, aliases) for key, entry in value.items()}
    return value


def zone_cards(session, seats, path):
    side, _, zone = path.partition(".")
    return session.players[seats[side]]["zones"][zone]


def check_expectation(session, expect, aliases, seats):
    """None when the expectation holds, else a readable failure."""
    expect = substitute(expect, aliases)
    if "cardOnField" in expect:
        item = next((entry for entry in session.battlefield if entry["cardId"] == expect["cardOnField"]), None)
        if item is None:
            return f"{expect['cardOnField']} n'est pas sur le terrain"
        if "zone" in expect and session.rules_field_zone(item) != expect["zone"]:
            return f"{expect['cardOnField']} est en {session.rules_field_zone(item)}, attendu {expect['zone']}"
        if "faceUp" in expect and bool(item.get("faceUp")) != expect["faceUp"]:
            return f"{expect['cardOnField']} est {'face cachée' if expect['faceUp'] else 'face visible'}"
        if "support" in expect and bool(item.get("isSupport")) != expect["support"]:
            return f"{expect['cardOnField']} {'n’est pas' if expect['support'] else 'est'} en Support"
        return None
    if "cardPower" in expect:
        item = next((entry for entry in session.battlefield if entry["cardId"] == expect["cardPower"]), None)
        power = session.rules_manifestation_characteristics(item)["power"] if item else None
        if power != expect["eq"]:
            return f"puissance de {expect['cardPower']} = {power}, attendu {expect['eq']}"
        return None
    if "confrontationResolved" in expect:
        if not session.rules_engine.get("confrontationResult"):
            return "aucun résultat de Confrontation"
        return None
    if "zone" in expect:
        cards = zone_cards(session, seats, expect["zone"])
        if "contains" in expect and expect["contains"] not in cards:
            return f"{expect['zone']} ne contient pas {expect['contains']} ({cards})"
        if "excludes" in expect and expect["excludes"] in cards:
            return f"{expect['zone']} contient encore {expect['excludes']}"
        if "count" in expect and len(cards) != expect["count"]:
            return f"{expect['zone']} : {len(cards)} cartes au lieu de {expect['count']}"
        return None
    if "onField" in expect:
        present = session.find_battlefield_item(expect["onField"]) is not None
        if present != bool(expect.get("is", True)):
            return f"{expect['onField']} {'absent du' if expect.get('is', True) else 'toujours sur le'} terrain"
        return None
    if "power" in expect:
        item = session.find_battlefield_item(expect["power"])
        power = session.rules_manifestation_characteristics(item)["power"] if item else None
        if power != expect["eq"]:
            return f"puissance de {expect['power']} = {power}, attendu {expect['eq']}"
        return None
    if "score" in expect:
        score = session.players[seats[expect["score"]]]["score"]
        if score != expect["eq"]:
            return f"score {expect['score']} = {score}, attendu {expect['eq']}"
        return None
    if "stack" in expect:
        size = len(session.rules_engine["actionStack"])
        if size != expect["stack"]:
            return f"Pile : {size} action(s), attendu {expect['stack']}"
        return None
    if "phase" in expect:
        phase = session.current_phase_id()
        if phase != expect["phase"]:
            return f"étape {phase}, attendu {expect['phase']}"
        return None
    if "choice" in expect:
        choice = session.rules_engine.get("pendingChoice")
        kind = choice.get("kind") if choice else None
        if kind != expect["choice"]:
            return f"choix en attente {kind}, attendu {expect['choice']}"
        return None
    return f"vérification inconnue : {expect}"


class ScriptSocket:
    """Stands in for a browser socket: collects the errors the server sends back."""

    def __init__(self):
        self.errors = []

    async def send(self, raw):
        payload = json.loads(raw)
        if payload.get("type") == "error":
            self.errors.append(payload.get("message"))


async def run_script(session, handle_message, auto_advance, auto_pass_types, on_step=None):
    """Play the scenario's script through the real message handler. Returns step reports."""
    state = session.sandbox
    aliases, seats = state["aliases"], state["seats"]
    reports = []
    # scripts pass explicitly: no engine auto-pass may move the game past a check
    session.rules_engine["autoSkipPhases"] = False
    session.rules_engine["passAllPlayerIds"] = []
    for index, step in enumerate(state["scenario"].get("script") or []):
        if "resolve" in step:
            reports.append(await _resolve_top(session, index, handle_message, auto_advance, auto_pass_types))
        elif "passUntil" in step:
            reports.append(await _pass_until(session, step["passUntil"], index, handle_message, auto_advance, auto_pass_types))
        elif "expect" in step:
            failure = check_expectation(session, step["expect"], aliases, seats)
            reports.append({"step": index, "kind": "expect", "label": step.get("label"), "ok": failure is None, "error": failure})
        elif "choose" in step:
            choice = session.rules_engine.get("pendingChoice")
            if not choice:
                reports.append({"step": index, "kind": "choose", "ok": False, "error": "aucun choix en attente"})
            else:
                message = {"type": "resolve_rules_choice", "choiceId": choice["id"], **substitute(step["choose"], aliases)}
                reports.append(await _send(session, choice["playerId"], message, index, handle_message, auto_advance, auto_pass_types))
        else:
            actor = seats[step.get("as", "me")]
            message = substitute(step["send"], aliases)
            if message.get("type") == "pass_priority" and step.get("as") is None:
                actor = session.rules_engine["priorityPlayerId"]
            reports.append(await _send(session, actor, message, index, handle_message, auto_advance, auto_pass_types))
        report = reports[-1]
        report["label"] = step.get("label")
        if step.get("expectError"):
            # a refusal is the expected outcome: success means the server said no
            refused = report["error"]
            report["ok"] = bool(refused)
            report["error"] = None if refused else "l'action aurait dû être refusée"
            report["refusal"] = refused
        if on_step:
            await on_step(report)
        if not report["ok"]:
            break
    return reports


async def _resolve_top(session, index, handle_message, auto_advance, auto_pass_types):
    """Both players pass until the top Stack action has resolved."""
    depth = len(session.rules_engine["actionStack"])
    if not depth:
        return {"step": index, "kind": "resolve", "ok": False, "error": "la Pile est vide"}
    for _ in range(4):
        actor = session.rules_engine["priorityPlayerId"]
        report = await _send(session, actor, {"type": "pass_priority"}, index, handle_message, auto_advance, auto_pass_types)
        if not report["ok"]:
            return report
        if len(session.rules_engine["actionStack"]) < depth or session.rules_engine.get("pendingChoice"):
            return {"step": index, "kind": "resolve", "ok": True, "error": None}
    return {"step": index, "kind": "resolve", "ok": False, "error": "l'action du dessus ne s'est pas résolue"}


async def _pass_until(session, goal, index, handle_message, auto_advance, auto_pass_types):
    """The priority holder passes until a choice is asked or a step is reached."""
    for _ in range(20):
        choice = session.rules_engine.get("pendingChoice")
        if ("choice" in goal and choice and choice.get("kind") == goal["choice"]) or (
            "phase" in goal and session.current_phase_id() == goal["phase"]
        ):
            return {"step": index, "kind": "passUntil", "ok": True, "error": None}
        if choice and goal.get("orChoice"):
            return {"step": index, "kind": "passUntil", "ok": True, "error": None}
        if choice:
            return {"step": index, "kind": "passUntil", "ok": False, "error": f"choix inattendu : {choice.get('kind')}"}
        actor = session.rules_engine["priorityPlayerId"]
        report = await _send(session, actor, {"type": "pass_priority"}, index, handle_message, auto_advance, auto_pass_types)
        if not report["ok"]:
            return report
    return {"step": index, "kind": "passUntil", "ok": False, "error": f"jamais atteint : {goal}"}


async def _send(session, actor_id, message, index, handle_message, auto_advance, auto_pass_types):
    socket = ScriptSocket()
    info = {"session": session, "playerId": actor_id, "role": "player", "isObserver": False}
    await handle_message(socket, info, message)
    if message.get("type") in auto_pass_types and session.rules_engine.get("enabled"):
        await auto_advance(session, actor_id)
    return {
        "step": index, "kind": message.get("type"), "ok": not socket.errors,
        "error": "; ".join(socket.errors) or None,
    }
