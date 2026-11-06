# Lacunes de couverture sémantique stricte

Empreinte source : `43786db67a4d392fbbd8acf150989f179143f37efef3ef7feef7acb342b37f28`

- Cartes couvertes : **395/450**
- Cartes hors registre : **55**
- Paragraphes imprimés restant à relier : **78**
- Oracles de branches déjà décrits mais non reliés : **239**

## Lots mécaniques recommandés

| # | Mécanique | Cartes nouvelles | Exemples |
|---:|---|---:|---|
| 1 | `result:move_target` | 2 | Destroy, Eliminate the Profane |
| 2 | `result:set_field_power` | 2 | Trim the Excess, Equalize |
| 3 | `trigger:end_of_game` | 2 | Piercing Lover, Phimosino |
| 4 | `trigger:enters_support` | 2 | Gomeran, Echo Mistress, Unruly Flail |
| 5 | `trigger:enters_zone` | 2 | Inspired Nimbus, Worm Bomb |
| 6 | `trigger:manifestation_used_as_tribute` | 2 | Melancholic Mirror, Sacred Mountain |
| 7 | `trigger:player_loses_confrontation` | 2 | Grudge Weaver, Zborh, the Eternal |
| 8 | `ongoing:grant_persist` | 1 | Gigabonblade |
| 9 | `ongoing:obscure_lock` | 1 | Obscure |
| 10 | `ongoing:power_set_maximum` | 1 | Inflate the Ego |
| 11 | `passive:balance_points` | 1 | Balance of the Spirit |
| 12 | `passive:disable_other_effects` | 1 | Discombobulator |
| 13 | `passive:entering_manifestation_becomes_hollow` | 1 | Asciugoth, the Absorbent |
| 14 | `passive:excess_essence_as_hollow` | 1 | Tricephalous Oil-Dog |
| 15 | `passive:extra_recovery_draw_per_empty_interzone` | 1 | Solitary Combhand |
| 16 | `passive:field_manifestations_as_tribute` | 1 | Orator of the Absurd |
| 17 | `passive:hand_limit_all` | 1 | Palm Coercer |
| 18 | `passive:increase_will_tribute` | 1 | Cognitive Fog |
| 19 | `passive:interzone_entry_penalty` | 1 | Spiked Pit |
| 20 | `passive:persistent_wills_as_ephemeral` | 1 | Soup, the Graceful |
| 21 | `passive:protect_controller_hand` | 1 | Purifying Ritual |
| 22 | `passive:recovery_draw_from_limbo` | 1 | Quasimillenary |
| 23 | `passive:redirect_opponent_targeting_to_source` | 1 | Obtrusive Mass |
| 24 | `passive:reduce_will_tribute` | 1 | Arcane Teapot |
| 25 | `passive:retain_excess_essence` | 1 | Essence Cauldron |
| 26 | `passive:sacrifice_at_power` | 1 | Quper, the Bestower |
| 27 | `passive:solo_confrontation_win_points` | 1 | Honor and Respect |
| 28 | `passive:sustain_exact_zero` | 1 | Life Sustainer |
| 29 | `passive:swap_with_targeted_confrontation_manifestation` | 1 | Wandering Outcast |
| 30 | `passive:vessel_manifestations_as_tribute` | 1 | Brabataba, the Unambitious |
| 31 | `passive:vessel_reveals_owner_hand` | 1 | Bonzai, the Unexpected |
| 32 | `play-permission` | 1 | Wandering Veteran |
| 33 | `result:choose_points_or_weaken_first` | 1 | Dulfer, the Touchy |
| 34 | `result:copy_entering_persistent_will_for_others` | 1 | Tuxnu, the Transparent |
| 35 | `result:destroy_matching_on_field` | 1 | Punish the Winners |
| 36 | `result:distribute_power` | 1 | Damage |
| 37 | `result:double_target_base_power` | 1 | Entrust |
| 38 | `result:end_confrontation_unless_payment` | 1 | Kiss of the Myrmillo! |
| 39 | `result:exile_all_limbos` | 1 | Extinguish Nostalgia |
| 40 | `result:exile_limbos_create_token_copies` | 1 | Recall the Consumed |
| 41 | `result:first_manifestation_trap` | 1 | Trap |
| 42 | `result:grant_limbo_will_play` | 1 | Freenya, Heartless Songstress |
| 43 | `result:obelisk_gift` | 1 | Obelisk of Friendship |
| 44 | `result:roll_d6_target_table` | 1 | Mutate Uncontrollably |
| 45 | `result:split_targeted_limbo_cards` | 1 | Caress the Dawn |
| 46 | `result:stalemate_confrontation` | 1 | Static Scuttler |
| 47 | `tribute-destination:deck_bottom` | 1 | Glob-glob |
| 48 | `tribute-destination:stalemate` | 1 | Sly Frog |

## Cartes hors registre

| # | Carte | Type | Clauses | Branches décrites | Mécaniques |
|---:|---|---|---:|---:|---|
| 40 | Entrust | ephemeral_will | 1 | 4 | `result:double_target_base_power` |
| 62 | Arcane Teapot | manifestation | 1 | 5 | `passive:reduce_will_tribute` |
| 63 | Inspired Nimbus | manifestation | 1 | 5 | `result:grant_free_will_play`, `trigger:enters_zone` |
| 75 | Gomeran, Echo Mistress | manifestation | 2 | 8 | `result:create_event_token_copy_in_support`, `trigger:enters_support` |
| 82 | Freenya, Heartless Songstress | manifestation | 2 | 10 | `result:grant_limbo_will_play`, `trigger:card_played` |
| 127 | Quasimillenary | manifestation | 1 | 6 | `passive:recovery_draw_from_limbo` |
| 133 | Cognitive Fog | persistent_will | 1 | 5 | `passive:increase_will_tribute` |
| 134 | Punish the Winners | ephemeral_will | 1 | 5 | `result:destroy_matching_on_field` |
| 151 | Static Scuttler | manifestation | 1 | 1 | `result:stalemate_confrontation`, `trigger:loses_confrontation` |
| 158 | Wandering Outcast | manifestation | 1 | 1 | `passive:swap_with_targeted_confrontation_manifestation` |
| 160 | Soup, the Graceful | manifestation | 1 | 1 | `passive:persistent_wills_as_ephemeral` |
| 163 | Unruly Flail | manifestation | 1 | 1 | `conditional-support`, `result:neutralize_stack_action`, `target:stack_action`, `trigger:enters_support` |
| 166 | Obtrusive Mass | manifestation | 1 | 1 | `passive:redirect_opponent_targeting_to_source` |
| 174 | Worm Bomb | manifestation | 1 | 1 | `result:destroy_random_vessel_manifestations`, `trigger:enters_zone` |
| 177 | Trim the Excess | ephemeral_will | 1 | 1 | `result:set_field_power` |
| 178 | Equalize | ephemeral_will | 1 | 1 | `result:set_field_power` |
| 197 | Wandering Veteran | manifestation | 2 | 2 | `play-permission`, `support-win:exile` |
| 205 | Piercing Lover | manifestation | 1 | 1 | `result:final_vessel_penalty`, `trigger:end_of_game` |
| 215 | Grudge Weaver | manifestation | 2 | 2 | `result:add_counter_source`, `result:grant_source_support_until_end_turn`, `trigger:player_loses_confrontation` |
| 227 | Damage | ephemeral_will | 1 | 1 | `result:distribute_power` |
| 231 | Honor and Respect | persistent_will | 1 | 1 | `passive:solo_confrontation_win_points` |
| 233 | Life Sustainer | persistent_will | 1 | 1 | `passive:sustain_exact_zero` |
| 239 | Obelisk of Friendship | persistent_will | 2 | 2 | `result:obelisk_gift`, `trigger:reaction` |
| 242 | Melancholic Mirror | persistent_will | 1 | 1 | `result:copy_related_tribute_if_exhaust`, `trigger:manifestation_used_as_tribute` |
| 246 | Brabataba, the Unambitious | manifestation | 1 | 1 | `passive:vessel_manifestations_as_tribute` |
| 255 | Orator of the Absurd | manifestation | 1 | 1 | `passive:field_manifestations_as_tribute` |
| 274 | Mutate Uncontrollably | ephemeral_will | 5 | 5 | `result:roll_d6_target_table` |
| 283 | Destroy | ephemeral_will | 1 | 1 | `result:move_target` |
| 287 | Purifying Ritual | persistent_will | 2 | 2 | `passive:protect_controller_hand` |
| 291 | Trap | ephemeral_will | 2 | 2 | `result:first_manifestation_trap` |
| 294 | Essence Cauldron | persistent_will | 1 | 1 | `passive:retain_excess_essence` |
| 295 | Eliminate the Profane | ephemeral_will | 1 | 1 | `result:move_target` |
| 304 | Quper, the Bestower | manifestation | 1 | 4 | `passive:sacrifice_at_power` |
| 315 | Zborh, the Eternal | manifestation | 2 | 6 | `adamant`, `result:move_source_to_owner_hand`, `trigger:player_loses_confrontation` |
| 324 | Caress the Dawn | ephemeral_will | 2 | 10 | `result:split_targeted_limbo_cards` |
| 327 | Glob-glob | manifestation | 1 | 3 | `tribute-destination:deck_bottom` |
| 334 | Bonzai, the Unexpected | manifestation | 1 | 4 | `passive:vessel_reveals_owner_hand` |
| 335 | Phimosino | manifestation | 1 | 4 | `result:final_deck_points`, `trigger:end_of_game` |
| 343 | Obscure | ephemeral_will | 3 | 12 | `ongoing:obscure_lock` |
| 362 | Gigabonblade | manifestation | 3 | 12 | `ongoing:grant_persist` |
| 372 | Recall the Consumed | ephemeral_will | 1 | 4 | `result:exile_limbos_create_token_copies` |
| 374 | Sly Frog | manifestation | 1 | 4 | `tribute-destination:stalemate` |
| 392 | Discombobulator | persistent_will | 2 | 8 | `passive:disable_other_effects`, `result:unless_payment_exile_source`, `trigger:before_revelation` |
| 404 | Dulfer, the Touchy | manifestation | 1 | 4 | `result:choose_points_or_weaken_first`, `trigger:vessel_revelation` |
| 410 | Solitary Combhand | manifestation | 1 | 5 | `passive:extra_recovery_draw_per_empty_interzone` |
| 415 | Extinguish Nostalgia | ephemeral_will | 1 | 5 | `result:exile_all_limbos` |
| 416 | Kiss of the Myrmillo! | ephemeral_will | 3 | 15 | `result:end_confrontation_unless_payment` |
| 417 | Spiked Pit | persistent_will | 1 | 6 | `passive:interzone_entry_penalty` |
| 418 | Inflate the Ego | ephemeral_will | 2 | 10 | `ongoing:power_set_maximum` |
| 423 | Sacred Mountain | manifestation | 1 | 5 | `result:exile_tribute_manifestation_score_others`, `trigger:manifestation_used_as_tribute` |
| 424 | Tuxnu, the Transparent | manifestation | 1 | 5 | `result:copy_entering_persistent_will_for_others`, `trigger:persistent_will_enters_field` |
| 433 | Tricephalous Oil-Dog | manifestation | 1 | 5 | `passive:excess_essence_as_hollow` |
| 435 | Asciugoth, the Absorbent | manifestation | 1 | 5 | `passive:entering_manifestation_becomes_hollow` |
| 437 | Balance of the Spirit | persistent_will | 2 | 10 | `passive:balance_points` |
| 444 | Palm Coercer | persistent_will | 2 | 12 | `passive:hand_limit_all` |
