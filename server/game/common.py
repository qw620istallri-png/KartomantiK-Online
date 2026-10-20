"""Constants and helpers shared by the session model and its mixins."""
import random
import uuid

PRIVATE_ZONES = {"deck", "hand", "exile"}
SHARED_ZONES = {"graveyard", "receptacle"}
RULES_SCORE_COUNTS = {
    "own_interzone_manifestations",
    "target_player_confrontation_non_token_manifestations",
    "own_manifestations_in_vessels",
    "excess_power_over_target_first_manifestation",
    "source_base_power",
    "source_current_power",
    "source_card_points",
    "own_exhausted_cards",
}
RULES_AFTER_CHAIN = {
    "discard_deck_per_base_power", "power_counter_target_per_base_power",
    "look_top_pick_hand", "boost_controller_first", "reveal_top_opponent_suspend",
}
ALL_ZONES = PRIVATE_ZONES | SHARED_ZONES

NORMAL_PHASES = ("recovery", "confrontation", "resolution", "end")
ADVANCED_PHASES = (
    "recovery_start", "recovery_draw", "recovery_end",
    "confrontation_choose", "confrontation_before_revelation", "confrontation_reveal",
    "confrontation_immediate", "confrontation_entry", "confrontation_reaction",
    "resolution_compare", "resolution_effects", "resolution_move",
    "end_actions", "end_triggers", "end_expire",
)
PHASE_GROUP = {phase_id: phase_id.split("_", 1)[0] for phase_id in ADVANCED_PHASES}

SESSION_TTL_SECONDS = 6 * 60 * 60  # expire an inactive session after 6h

# On-field pile SCREEN positions are no longer server state at all — they're
# a pure function of (viewer's seat, pile owner's seat, zone), with no runtime
# transform/mirroring involved, so they live entirely client-side now (see
# PILE_SCREEN_POS in app.js). That replaced an earlier attempt at deriving a
# single mirrored pair of clusters from one axis: dragging a pile while
# actually viewing it directly, vs. viewing that same pile from the OTHER
# seat (mirrored), gave measurably different "looks right" coordinates — i.e.
# no single per-owner position can look correct from both viewpoints at once.
# The only fix is a value per (viewer, owner, zone) triple, which needs no
# server involvement since it depends on nothing session-specific.
NUM_SEATS = 2
READ_ONLY_ROLES = {"observer", "spectator", "judge", "organizer"}
PRIVILEGED_VIEW_ROLES = {"observer", "judge"}
RULES_ACTION_KINDS = {
    "manual", "play_card", "activated_effect", "triggered_effect",
}
TRIBUTE_SYMBOL_TEMPERAMENT = {
    "G": "phlegmatic",
    "B": "vitreous",
    "P": "melancholic",
    "Y": "capricious",
    "R": "choleric",
    "H": "hollow",
    "T": "transcendent",
}
RULES_WILL_TYPES = {"ephemeral_will", "persistent_will"}
# passives that only work from the Stalemate Zone (Fee-fee)
RULES_STALEMATE_PASSIVE_KINDS = {"stalemate_win_blocked", "stalemate_ignores_low_power"}
# activated results whose purpose is to put a Manifestation into Support
RULES_SUPPORT_ENTRY_RESULTS = {
    "grant_source_support_until_end_turn", "stalemate_target_grant_source_support",
    "play_limbo_target_as_support", "play_vessel_target_as_support", "chabak_support",
    "will_becomes_support_manifestation", "grant_friendly_interzone_support_until_end_turn",
}
# Entering a zone with a required target and nothing to target: the card still enters.
RULES_ENTRY_EVENTS = {"enters_field", "enters_support", "enters_field_zone"}
RULES_DESTROY_MATCHES = {
    "entered_support_this_turn", "won_confrontation_this_turn",
}
RULES_EFFECT_DURATIONS = {
    "until_end_of_turn",
    "until_end_of_next_turn",
    "while_source_and_target_on_field",
    "while_target_on_field",
    "while_source_on_field",
    "until_resolution",
}
RULES_TEMPERAMENTS = {
    "capricious", "choleric", "hollow", "melancholic", "phlegmatic",
    "transcendent", "vitreous",
}
RULES_COPIED_EFFECT_KEYS = {
    "adamant", "float", "persist", "canPayTribute", "suspensionThresholds",
    "canPayTributeFromInterzone", "interzoneTributePower",
    "supportFromHand", "supportFromHandCondition", "supportFromInterzone",
    "supportFromStalemate",
    "lossDestination", "supportWhenNoCounter", "supportCondition",
    "playOnlyEmptyStack", "supportWinDestination", "supportWinEffect",
    "continuousPowerRules", "activatedAbilities", "triggeredAbilities",
    "playPermissions", "passiveEffects",
}
TEMPERAMENT_DOMINANCE = {
    "phlegmatic": {"vitreous", "capricious"},
    "vitreous": {"melancholic", "choleric"},
    "melancholic": {"capricious", "phlegmatic"},
    "capricious": {"choleric", "vitreous"},
    "choleric": {"phlegmatic", "melancholic"},
    "transcendent": {"phlegmatic", "vitreous", "melancholic", "capricious", "choleric", "hollow"},
    "hollow": set(),
}


def gen_code(length=6):
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I ambiguity
    return "".join(random.choices(alphabet, k=length))


def new_id():
    return uuid.uuid4().hex[:12]


def validate_tournament_deck(card_ids, sideboard_ids, card_points, policy=None, card_labels=None, limit_bonus=0):
    policy = policy or {}
    card_labels = card_labels or {}
    label = lambda card_id: card_labels.get(card_id, card_id)
    if len(card_ids) != 30 or len(set(card_ids)) != 30:
        return "A tournament deck must contain exactly 30 unique cards."
    if len(sideboard_ids) > 6 or len(set(sideboard_ids)) != len(sideboard_ids):
        return "A tournament sideboard may contain at most 6 unique cards."
    if set(card_ids) & set(sideboard_ids):
        return "A card cannot be in both the tournament deck and sideboard."
    if any(card_id not in card_points for card_id in card_ids + sideboard_ids):
        return "The tournament deck contains an unknown card."
    point_limit = 500 + max(0, int(limit_bonus or 0))
    if sum(card_points[card_id] for card_id in card_ids) > point_limit:
        return f"A tournament deck cannot exceed {point_limit} points."
    combined = set(card_ids + sideboard_ids)
    banned = [card_id for card_id in policy.get("bannedCardIds", []) if card_id in combined]
    if banned:
        return "Banned card(s): " + ", ".join(label(card_id) for card_id in banned) + "."
    for group in policy.get("restrictedGroups", []):
        present = [card_id for card_id in group.get("cardIds", []) if card_id in combined]
        if len(present) > 1:
            group_name = group.get("name") or "Restricted group"
            return f'{group_name}: only one of these cards is allowed across deck and sideboard ({", ".join(label(card_id) for card_id in present)}).'
    return None


def normalize_role(role):
    """Accept the old observer boolean while newer callers use named roles."""
    if isinstance(role, bool):
        return "observer" if role else "player"
    return role or "player"


def make_player(player_id, name, cluster_index=0, seat=None):
    seat = cluster_index % NUM_SEATS if seat is None else int(seat)
    return {
        "id": player_id,
        "name": name,
        "connected": False,
        "score": 0,
        "seat": seat,
        "zones": {zone: [] for zone in ALL_ZONES},
        # Cards remain owned by the player who imported them even while they
        # sit in an opponent's Empathic Vessel. Values are keyed by card id;
        # Kartomantik decks contain unique cards, so this stays unambiguous.
        "zoneOwners": {zone: {} for zone in ALL_ZONES},
        "cardRarities": {},
        "deckDefinition": None,
        # The sideboard is deliberately not a game zone: it stays private,
        # does not count as the Deck, and cards can only enter play after a
        # fresh validated deck import.
        "sideboard": [],
        "activity": None,  # transient "what menu are they in" hint, never private
    }
