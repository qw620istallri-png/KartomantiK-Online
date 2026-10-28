"""Resolving a pending choice: dispatch on `choice['kind']` to one handler per choice family.

A handler returns `(error, result)`; it returns None only when none of its
purpose-specific branches applied, in which case the generic discard path runs.
"""


from ..replacements import replacement_checkpoint

RULES_CHOICE_HANDLERS = {
    "optional_stack_action": "_rules_choice_optional_stack_action",
    "support_return_order": "_rules_choice_support_return_order",
    "score_delta_choice": "_rules_choice_score_delta_choice",
    "simultaneous_stack_order": "_rules_choice_simultaneous_stack_order",
    "persist_first_manifestation": "_rules_choice_persist_first_manifestation",
    "token_count": "_rules_choice_token_count",
    "pick_distribution_extra": "_rules_choice_pick_distribution_extra",
    "reveal_hand_discard": "_rules_choice_reveal_hand_discard",
    "pick_own_item": "_rules_choice_pick_own_item",
    "effect_memory_return": "_rules_choice_effect_memory_return",
    "deck_reorder": "_rules_choice_deck_reorder",
    "peek_top_card": "_rules_choice_peek_top_card",
    "guess_top_card": "_rules_choice_guess_top_card",
    "optional_trigger": "_rules_choice_optional_trigger",
    "optional_discard_draw": "_rules_choice_optional_discard_draw",
    "points_or_weaken_first": "_rules_choice_points_or_weaken_first",
    "declare_card_name": "_rules_choice_declare_card_name",
    "temperament_choice": "_rules_choice_temperament_choice",
    "binary_choice": "_rules_choice_binary_choice",
    "clemency_choice": "_rules_choice_clemency_choice",
    "points_or_hand_limit": "_rules_choice_points_or_hand_limit",
    "hand_overflow": "_rules_choice_hand_overflow",
    "draw_replacement": "_rules_choice_draw_replacement",
    "power_loss_distribution": "_rules_choice_power_loss_distribution",
    "random_target_effect": "_rules_choice_random_target_effect",
    "skip_confrontation_payment": "_rules_choice_skip_confrontation_payment",
    "confrontation_relocation": "_rules_choice_confrontation_relocation",
    "suspend_hand_will": "_rules_choice_suspend_hand_will",
    "effect_memory_payment": "_rules_choice_effect_memory_payment",
    "immediate_effect_payment": "_rules_choice_immediate_effect_payment",
    "trigger_targets": "_rules_choice_trigger_targets",
    "stack_copy_targets": "_rules_choice_stack_copy_targets",
    "effect_payment": "_rules_choice_effect_payment",
    "stack_counter_payment": "_rules_choice_stack_counter_payment",
    "recovery_shared_choice": "_rules_choice_recovery_shared_choice",
    "confrontation_destination": "_rules_choice_confrontation_destination",
    "confrontation_replace_interzone": "_rules_choice_confrontation_replace_interzone",
    "chain_manifestation": "_rules_choice_chain_manifestation",
}


class ChoicesMixin:
    def _rules_continue_draws_after_choice(self, choice, response):
        if response[0] is None and choice.get("_drawRequestsAfterChoice"):
            remaining = choice["_drawRequestsAfterChoice"]
            next_choice = self.rules_engine.get("pendingChoice")
            if next_choice is not None:
                next_choice["_drawRequestsAfterChoice"] = remaining
            else:
                self.continue_rules_draw_requests(remaining)
        return response

    @replacement_checkpoint("choice")
    def resolve_rules_choice(self, player_id, choice_id, card_ids=None, option=None, item_id=None,
                             placement=None, targets=None, transcendent_payment=None):
        if self.ended:
            return "The game has already ended.", None
        choice = self.rules_engine.get("pendingChoice")
        if not choice or choice.get("id") != choice_id or choice.get("playerId") != player_id:
            return "This card choice is no longer available.", None
        if choice.get("kind") == "replacement_order":
            return self.resolve_rules_replacement_order(player_id, choice, card_ids)
        if choice.get("_optionalReplacement"):
            if option not in {"yes", "no"}:
                return "Choose whether to apply the replacement.", None
            return self.resolve_rules_replacement_order(player_id, choice, [option])
        handler = RULES_CHOICE_HANDLERS.get(choice.get("kind"))
        if handler is not None:
            payment_options = {"transcendent_payment": transcendent_payment} if choice.get("kind") in {
                "stack_counter_payment", "effect_memory_payment", "immediate_effect_payment", "effect_payment",
            } else {}
            response = getattr(self, handler)(player_id, choice_id, choice, card_ids, option, item_id, placement, targets, **payment_options)
            if response is not None:
                return self._rules_continue_draws_after_choice(choice, response)
        response = self._resolve_rules_discard_choice(player_id, choice_id, choice, card_ids)
        return self._rules_continue_draws_after_choice(choice, response)
