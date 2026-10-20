"""In-memory session/game-state model for Kartomantik Online.

Sessions hold zones, the shared tabletop, visibility permissions and the
optional assisted-rules beta state.  Card effects remain player-led for now;
the beta only owns rules that can already be proven from shared state.
"""
import time

# Constants and helpers live in game.common; they are re-exported here for
# main.py, the tests and the tools (tests also patch session.random).
from game.common import *  # noqa: F401,F403
from game.zones import ZonesMixin
from game.phases import PhasesMixin
from game.actions import ActionsMixin
from game.payment import PaymentMixin
from game.stack import StackMixin
from game.board import BoardMixin
from game.power import PowerMixin
from game.confrontation import ConfrontationMixin
from game.priority import PriorityMixin
from game.triggers import TriggersMixin
from game.chain import ChainMixin
from game.resolution import ResolutionMixin
from game.view import ViewMixin
from game.pregame import PregameMixin
from game.effects import EffectsMixin
from game.effects.score import ScoreEffectsMixin
from game.effects.cards import CardsEffectsMixin
from game.effects.power import PowerEffectsMixin
from game.effects.removal import RemovalEffectsMixin
from game.effects.board import BoardEffectsMixin
from game.effects.stack import StackEffectsMixin
from game.effects.dice import DiceEffectsMixin
from game.effects.signature import SignatureEffectsMixin
from game.choices import ChoicesMixin
from game.choices.stack import StackChoicesMixin
from game.choices.payment import PaymentChoicesMixin
from game.choices.confrontation import ConfrontationChoicesMixin
from game.choices.cards import CardsChoicesMixin
from game.choices.decisions import DecisionsChoicesMixin
from game.summary import SummaryMixin


class Session(
    ZonesMixin,
    PhasesMixin,
    ActionsMixin,
    PaymentMixin,
    StackMixin,
    BoardMixin,
    PowerMixin,
    ConfrontationMixin,
    PriorityMixin,
    TriggersMixin,
    ChainMixin,
    ResolutionMixin,
    ViewMixin,
    PregameMixin,
    EffectsMixin,
    ScoreEffectsMixin,
    CardsEffectsMixin,
    PowerEffectsMixin,
    RemovalEffectsMixin,
    BoardEffectsMixin,
    StackEffectsMixin,
    DiceEffectsMixin,
    SignatureEffectsMixin,
    ChoicesMixin,
    StackChoicesMixin,
    PaymentChoicesMixin,
    ConfrontationChoicesMixin,
    CardsChoicesMixin,
    DecisionsChoicesMixin,
    SummaryMixin,
):
    def __init__(self, mode="casual", tournament_policy=None, card_points=None, card_labels=None,
                 manifestation_ids=None, card_rules=None, rules_beta=False, ban_list_enabled=False):
        self.mode = "tournament" if mode == "tournament" else "casual"
        self.status = "lobby" if self.mode == "tournament" else "active"
        self.code_player = gen_code() if self.mode == "casual" else None
        self.code_observer = gen_code() if self.mode == "casual" else None
        self.code_player1 = gen_code(8) if self.mode == "tournament" else None
        self.code_player2 = gen_code(8) if self.mode == "tournament" else None
        self.code_spectator = gen_code(8) if self.mode == "tournament" else None
        self.code_judge = gen_code(8) if self.mode == "tournament" else None
        self.code_organizer = gen_code(10) if self.mode == "tournament" else None
        self.seat_claims = {0: None, 1: None}
        self.tournament_policy = tournament_policy or {"bannedCardIds": [], "restrictedGroups": []}
        self.ban_list_enabled = self.mode == "tournament" or bool(ban_list_enabled)
        self.card_points = None if card_points is None else dict(card_points)
        self.card_labels = card_labels or {}
        self.manifestation_ids = set(manifestation_ids or ())
        self.card_rules = {card_id: dict(metadata) for card_id, metadata in (card_rules or {}).items()}
        self.players = {}  # player_id -> player dict, in join order
        self.battlefield = []  # list of dict: id, ownerId, cardId, x, y, faceUp, rotation, counters
        self.tokens = []  # list of dict: id, ownerId, x, y, label, color, counters
        self.strokes = []  # freehand annotation strokes: id, ownerId, color, points:[[x,y],...]
        self.log = []  # chronological, sequence-numbered audit trail
        self.log_sequence = 0
        self.pending_hand_requests = {}  # requestId -> {requesterId, targetId, index, action}
        self.rules_engine = {
            "enabled": bool(rules_beta),
            "autoSkipPhases": True,
            # players who turned off "skip phases without action" for themselves
            "autoSkipOffPlayerIds": [],
            # players who held Enter: the engine passes for them, even with
            # playable cards, until they press Enter again
            "passAllPlayerIds": [],
            "deckConfirmedPlayerIds": [],
            "openingHandPlayerIds": [],
            "mulliganPlayerIds": [],
            "openingMulliganRequiredPlayerIds": [],
            "openingMulliganFailedPlayerIds": [],
            "readyPlayerIds": [],
            "recoveryDrawTurn": None,
            "recoveryMulliganTurn": None,
            "recoveryMulliganPlayerIds": [],
            "recoveryMulliganRequiredPlayerIds": [],
            "recoveryMulliganFailedPlayerIds": [],
            "beginningTriggersTurn": None,
            "beginningPermissionsTurn": None,
            "playPermissions": [],
            "supportEntries": [],
            "playRestrictions": [],
            "zoneEntryTurns": {},
            "recentLimboEntries": [],
            "handLimitEffects": [],
            "outcome": None,
            "priorityPlayerId": None,
            "priorityPasses": [],
            "actionStack": [],
            "deferredSimultaneousActions": [],
            "suspendedCards": [],
            "lastResolvedAction": None,
            "ongoingEffects": [],
            "effectMemories": [],
            "pendingChoice": None,
            "firstManifestationItemIds": {},
            "firstManifestationValidatedPlayerIds": [],
            "trapPlayerIds": [],
            "trapCards": {},
            "limboRecoveryPlayerIds": [],
            "limboDrawn": {},
            "firstManifestationComplete": False,
            "firstManifestationTriggersQueued": False,
            "confrontationEntrySequence": 0,
            "confrontationResult": None,
            "lastConfrontationWinnerId": None,
            "rematchPending": None,
            "forcedConfrontationWinnerId": None,
            "forcedConfrontationStalemate": False,
        }
        self.phase_tracker = {
            "enabled": bool(rules_beta),
            "advanced": bool(rules_beta),
            "index": 0,
            "turn": 1,
        }
        self.phase_passes = set()
        self.pending_searches = {}
        self.audit_alerts = []
        self.created_at = time.time()
        self.last_activity = time.time()
        self.ended = False
        self.score_history = []  # points of each player at the end of every turn
        self.final_summary = None  # the end summary, frozen when a player leaves the ended game
        # hand cards shown to the other players: player id -> Counter(card id), and
        # the hand last seen, to forget a copy as soon as it leaves the hand
        self.revealed_hand = {}
        self.revealed_hand_seen = {}
