# Audit des résultats chiffrés et des portées

Exécuté : 2026-10-24T09:06:47.736137+00:00
Empreinte : `a6714c2394854b0f2e6fefe816244e76065e27564a45cd084a4364a83d5f93dd`

```json
{
  "executed": 23,
  "passed": 23,
  "failed": 0,
  "skipped": 0,
  "cardsWithSelectedClauseProof": 24,
  "fullCatalogSemanticCertification": false
}
```

## Corrections reproduites

- Induce Desertion utilise la puissance de base actuelle (copie, doublement et jeton), sans additionner les bonus.
- Le gain de Mukkabell utilise aussi cette puissance de base après un doublement.
- Les jetons génériques sont reconnus comme Manifestations pour le ciblage et les effets de groupe. Le sélecteur affiche leur symbole et puissance.
- Les décomptes de l’Interzone incluent ces jetons (Floating Dancer, Pinpia Psychobulb et Reap What You’ve Sown).
- Les effets visant les cartes actuellement sur le champ ne touchent pas Stalemate (Pimbo, Starkaz, Sever the Ascent et Protect).

## Clauses disposant d’assertions indépendantes

| Carte | Tests liés |
|---|---|
| Induce Desertion | test_induce_uses_doubled_base_and_excludes_additive_bonus, test_induce_uses_mimers_snapshot_base_and_not_its_bonus, test_induce_counts_generic_token_base |
| Mukkabell | test_mukkabell_win_uses_chained_modified_base_not_print_or_bonus |
| Floating Dancer | test_dancer_counts_tokens_under_current_control |
| Pinpia Psychobulb | test_pinpia_creates_one_retained_essence_per_actual_interzone_manifestation |
| Plea for Generosity | test_plea_excludes_tokens_and_copies_but_counts_animated_will |
| Agrupol, Ponderer of Fields | test_agrupol_counts_ownership_across_both_vessels |
| Donmo, the Truth-Bender | test_donmo_counts_exhaustion_and_control_not_ownership_or_type |
| Humiliate | test_humiliate_penalizes_current_controller_and_persists |
| Pass Judgment | test_judgment_snapshots_hand_on_resolution_excluding_played_will |
| Strengthen | test_printed_fixed_modifiers_have_exact_amount_and_expiry |
| Accentuate | test_printed_fixed_modifiers_have_exact_amount_and_expiry |
| Weaken | test_printed_fixed_modifiers_have_exact_amount_and_expiry |
| Oppress | test_printed_fixed_modifiers_have_exact_amount_and_expiry, test_generic_token_targeting_keeps_type_visibility_and_protection_checks |
| Corrode | test_corrode_affects_both_sides_and_tokens_but_only_existing_cz |
| Pimbo | test_pimbo_includes_generic_tokens_and_animated_wills_on_field, test_pimbo_does_not_reach_stalemate_which_is_outside_the_field |
| Friendly Presence | test_friendly_presence_targets_current_opponent_cz_only |
| Venerable Viper | test_viper_locks_existing_opponent_interzone_including_tokens |
| Lombriculpop | test_excess_power_points_use_current_first_power_and_floor_at_zero |
| Armored Pachywyrm | test_excess_power_points_use_current_first_power_and_floor_at_zero |
| Graceful Petal | test_graceful_petal_rewards_immutable_owner_after_vessel_entry |
| Reap What You’ve Sown | test_reap_counts_tokens_for_score_and_draws_only_for_free_spaces |
| Protect | test_protect_covers_current_controlled_field_cards_but_not_stalemate |
| Starkaz, the Brilliant | test_starkaz_and_sever_share_field_scope_without_reaching_stalemate |
| Sever the Ascent | test_starkaz_and_sever_share_field_scope_without_reaching_stalemate |

Les nombres attendus sont écrits dans les tests à partir du texte imprimé et des décisions de règles du créateur. Les valeurs encodées des capacités servent à exécuter l’effet, pas à produire son résultat attendu.

Les Volontés jouées passent par la déclaration, le paiement et la Pile. Les capacités déclenchées sont principalement isolées à la résolution ; leur moment de déclenchement n’est pas certifié par ce lot. Mukkabell couvre également le vrai choix d’Enchaînement et son déclenchement de victoire. Graceful Petal couvre le déplacement puis l’appel explicite du déclenchement d’entrée au Vaisseau.

## Limites et suite

- Autres cartes et clauses non couvertes par les assertions de ce lot.
- Déclenchement, timing et branches alternatives des effets isolés.
- Valeurs à conserver lorsque la source ou une cible quitte une zone avant la résolution.
- Combinaisons supplémentaires, navigateurs et appareils réels.

Ce lot ne certifie pas toutes les clauses des 24 cartes. La campagne générale précédente est historique : son empreinte ne correspond plus aux sources après ces corrections. Elle n’est pas revalidée par les seuls tests de ce lot.

[Assertions exécutables](../../tests/test_quantitative_card_audit.py) · [preuves de ce lot](numeric.json) · [première reproduction avant correctifs](numeric-before.json)
