# Ajouter l'automatisation d'une carte

Ce guide décrit le chemin normal pour ajouter une carte au mode assistance.
Lire d'abord `docs/ASSISTED_RULES_ENGINE.md`.

## 1. Lire la carte et identifier les mécaniques

Avant de modifier le code, noter :

- type de carte ;
- fenêtres légales ;
- coûts imprimés et supplémentaires ;
- source et zones autorisées ;
- cibles et restrictions ;
- événement déclencheur ;
- résultat immédiat ;
- durée ;
- éventuelle mémoire ;
- effets de remplacement ;
- choix obligatoires ou optionnels ;
- informations privées concernées.

Vérifier le livret et l'errata. Ne pas importer les conventions d'un autre jeu.

## 2. Chercher une primitive existante

Commencer dans :

- `public/card-abilities.json` ;
- `clean_rules_action_result` ;
- `clean_rules_trigger_result` ;
- `apply_rules_action_result` ;
- `create_rules_ongoing_effects` ;
- `resolve_rules_choice`.

Si la mécanique existe, la carte ne doit normalement nécessiter qu'une entrée
JSON et des tests.

## 3. Choisir la forme de capacité

### Volonté jouée

```json
{
  "id": "grant-persist-until-end-of-turn",
  "action": "play_card",
  "targets": {
    "min": 1,
    "max": 1,
    "cardType": "manifestation",
    "zones": ["battlefield"],
    "fieldZone": "confrontation"
  },
  "ongoingEffect": {
    "kind": "grant_persist",
    "duration": "until_end_of_turn"
  }
}
```

Ajouter `"immediate": true` lorsque le texte indique explicitement
`Immediate Effect`. Le moteur impose alors la position supérieure dans un lot
simultané et résout l'action sans passes de priorité.

### Capacité activée

```json
{
  "id": "gain-persist-until-end-of-turn",
  "tribute": "{H}{H}{H}",
  "sourceFieldZone": "confrontation",
  "targets": {
    "min": 1,
    "max": 1,
    "cardType": "manifestation",
    "fieldZone": "confrontation",
    "controller": "self",
    "sourceOnly": true
  },
  "ongoingEffect": {
    "kind": "grant_persist",
    "duration": "until_end_of_turn"
  }
}
```

Champs de coûts activés disponibles :

```text
tribute
essenceCost
exhaustSource
sacrificeSource
removeAllCountersFromSource
```

`sourceZones` autorise une capacité activée depuis `hand` ou `battlefield`.
`sourceFieldZone` continue de préciser `interzone`, `confrontation` ou une
autre zone du champ lorsque la source est déjà posée. Utiliser
`ongoingEffects` lorsqu'une même résolution crée plusieurs effets continus.

`optionalExtraEssence` décrit un surpaiement volontaire exclusivement en
Essences. Le nombre choisi par le client est revalidé et prélevé par le serveur
avant d'être disponible dans `action.cost.optionalExtraEssenceSpent`.

### Cibles asymétriques

Utiliser `targetGroups` lorsque chaque cible possède un contrat différent :

```json
{
  "targetGroups": [
    {
      "min": 1,
      "max": 1,
      "cardType": "manifestation",
      "fieldZone": "interzone",
      "controller": "opponent"
    },
    {
      "min": 1,
      "max": 1,
      "cardType": "manifestation",
      "fieldZone": "interzone",
      "controller": "self"
    }
  ]
}
```

Le client demande les groupes dans l'ordre et le serveur revalide chaque cible
avec son propre contrat.

### Capacité déclenchée

```json
{
  "id": "draw-when-used-as-tribute",
  "trigger": {"event": "used_as_tribute"},
  "result": {"kind": "draw_owner", "value": 1}
}
```

### Effet passif

```json
{
  "id": "sustain-manifestations-at-exact-zero",
  "passiveEffect": {
    "kind": "sustain_exact_zero"
  }
}
```

Un `passiveEffect` n'apparaît jamais parmi les actions activables du client.
Il est consulté par le moteur lorsqu'un événement concerné est sur le point de
se produire.

Événements déjà utilisés :

```text
beginning_of_turn
end_of_turn
enters_field
manifestation_enters_field
enters_support
enters_zone
used_as_tribute
```

Un effet déclenché formulé avec `may` ou `can` doit déclarer
`"optional": true` au niveau de la capacité. Le moteur demande alors au
contrôleur s'il souhaite utiliser l'effet avant de demander ses cibles et
avant de l'ajouter à la Pile.

`cleanse_target` retire uniquement les modifications ajoutées à la carte :
effets continus qui la modifient, caractéristiques copiées, perte d'effets,
Tempérament ou Support temporaire et contrôle ajouté. Ne jamais supprimer ses
compteurs, sa zone, son orientation ni ses caractéristiques imprimées.

### Permission de jeu

Utiliser `playPermission` lorsqu'une carte obtient temporairement le droit
d'être jouée depuis une zone inhabituelle. Ne pas transformer une permission en
déclenchement.

## 4. Résultats disponibles

Principaux résultats :

```text
score_owner
draw_owner
discard_hand_target
discard_deck_owner
discard_hand_owner_then_draw
move_target
move_random_zone_card
neutralize_stack_action
counter_stack_action_unless_payment
copy_stack_action
chain_from_zone
add_counter_source
create_effect_memory
each_player_recovery_choice
change_source_control
resolve_top_deck_by_type
reorder_top_decks
split_targeted_limbo_cards
guess_top_card
create_tokens_for_target_interzone_count
capture_stalemate_and_copy
copy_related_tribute_if_exhaust
exile_limbos_create_token_copies
copy_entering_persistent_will_for_others
schedule_next_turn_hand_limit
choose_points_or_hand_limit
move_targets
move_counter
destroy_source
adjust_target_power
optional_discard_then_draw
roll_d6_power_by_parity
roll_d6_target_table
roll_d6_conditional_source
roll_multiple_even_power_odd_discard
score_controller_by_source_roll_then_exile
force_win_if_highest_base_first
skip_confrontation_unless_points
end_confrontation_relocate_all
suspend_opponent_hand_will
```

Une capacité activée peut limiter sa fenêtre avec :

```json
{"phaseIds": ["end_actions"]}
```

Utiliser `"anyPlayer": true` uniquement lorsqu'un texte permet explicitement
à chaque joueur d'activer la capacité d'une source qu'il ne contrôle pas. Le
serveur continue de vérifier la capacité par son identifiant et attribue
l'action au joueur qui paie le coût.

Pour déplacer un marqueur, utiliser deux `targetGroups`. Le premier peut
imposer `"counter": "Abstraction"` et `"minCounters": 1`; le résultat
`move_counter` revalide les deux cartes et le nombre de marqueurs à la
résolution.

La cible `"kind": "card_or_stack_action"` est réservée aux effets imprimés qui
peuvent viser indifféremment une carte sur le champ ou une carte jouée sur la
Pile. Une protection créée sur la Pile suit le permanent s'il entre ensuite
sur le champ.

Si un nouveau résultat est nécessaire :

1. le nettoyer et le borner dans `clean_rules_action_result` ou
   `clean_rules_trigger_result` ;
2. l'appliquer dans `apply_rules_action_result` ;
3. retourner un résultat structuré pour le journal ;
4. ajouter ses traductions ;
5. écrire ses tests.

Ne jamais utiliser un résultat générique silencieux qui ressemble à un succès
lorsque la cible ou le coût est invalide.

## 5. Effets continus

Structure :

```json
{
  "kind": "power_modifier",
  "value": 3,
  "duration": "until_end_of_turn"
}
```

Valeur dérivée d'un coût en marqueurs :

```json
{
  "kind": "power_modifier",
  "valuePerRemovedCounter": 1,
  "duration": "until_end_of_turn"
}
```

Kinds actuellement reconnus par le calcul des caractéristiques :

```text
power_modifier
power_ignored
copy_power_temperament
power_minimum
power_maximum
grant_persist
grant_float
remove_float
```

Un nouveau kind doit être appliqué dans le calcul pertinent, pas uniquement
stocké dans `ongoingEffects`.

## 6. Mémoire

Exemple Coral Skull :

```json
{
  "kind": "create_effect_memory",
  "memoryKind": "return_from_limbo_end_turn",
  "attachTo": "paid_action_source",
  "optional": true
}
```

Exemple Refrain Repeater :

```json
{
  "kind": "create_effect_memory",
  "memoryKind": "return_from_limbo_end_turn",
  "attachTo": "event_card",
  "opponentPayment": "{H}"
}
```

N'utiliser une mémoire que si la règle doit survivre au départ de sa source.
Un effet seulement lié à la présence de la source doit rester un effet continu.

## 7. Remplacements de Tribut

Les remplacements simples sont compilés dans `build_card_rules` :

```text
tributeDestination = graveyard
tributeDestination = deck_bottom
tributeDestination = stalemate
```

Pour une nouvelle destination, étendre `pay_rules_tribute` et conserver un
enregistrement dans `action.cost.tributeMovements`.

## 8. Interface

Aucune modification d'interface n'est nécessaire si la capacité utilise :

- le sélecteur de cible existant ;
- le paiement de Tribut existant ;
- un résultat automatique existant.

Une interface est nécessaire pour un nouveau `pendingChoice`.

Dans ce cas :

1. sérialiser uniquement les données publiques ;
2. ajouter un rendu dans `renderRulesChoice` ou dans le flux de plateau ;
3. bloquer la fermeture si le choix est obligatoire ;
4. ajouter les traductions anglaise, française et italienne ;
5. journaliser la décision.

## 9. Tests obligatoires

### Catalogue

Dans `tests/test_card_catalog.py`, vérifier que l'identifiant de carte pointe
vers la bonne capacité et que les champs importants sont exacts.

### Moteur

Dans `tests/test_game_state.py`, couvrir :

- déclaration légale ;
- coût payé immédiatement ;
- cible devenue invalide ;
- résolution ;
- changement de zone ;
- expiration ;
- choix refusé ou impossible ;
- interaction avec priorité et Pile.

### WebSocket

Ajouter un scénario dans `tests/test_websocket_integration.py` si la capacité
introduit :

- un nouveau message ;
- un nouveau choix ;
- une transition de phase ;
- une information privée ;
- une synchronisation visible par les deux joueurs.

## 10. Checklist

- [ ] texte vérifié dans le livret, l'errata et la carte ;
- [ ] primitive existante recherchée ;
- [ ] capacité déclarée dans `card-abilities.json` ;
- [ ] cible revalidée à la résolution ;
- [ ] coût payé à la déclaration ;
- [ ] déclenchements simultanés regroupés ;
- [ ] informations privées non divulguées ;
- [ ] résultat structuré et journalisé ;
- [ ] traductions ajoutées si nouveau choix ;
- [ ] test catalogue ;
- [ ] test moteur ;
- [ ] test WebSocket si nécessaire ;
- [ ] syntaxe JavaScript vérifiée ;
- [ ] version des assets augmentée si le client a changé.

## 11. Mettre à jour le registre de couverture

Après les tests :

1. ajouter ou modifier l'entrée de la carte dans
   `public/automation-coverage-overrides.json` uniquement si son statut ou ses
   références de tests doivent être confirmés manuellement ;
2. utiliser `automated` seulement lorsque chaque capacité imprimée est couverte ;
3. régénérer le registre :

```powershell
py tools\automation_coverage.py --write
py tools\automation_coverage.py --check
```

Le client charge `automation-coverage.json`. Le badge est visible en mode
assistance et l'inspecteur affiche toujours le statut détaillé.

## 12. Exemple de stratégie pour une carte complexe

Ne pas commencer par la carte complète.

Pour une carte qui :

- change de contrôle ;
- crée un déclenchement différé ;
- remplace sa destination ;
- modifie une limite de Main ;

procéder dans cet ordre :

1. ajouter un pilote simple du changement de contrôle ;
2. ajouter un pilote simple du déclenchement différé ;
3. ajouter un pilote simple du remplacement ;
4. tester les interactions ;
5. encoder enfin la carte complexe en combinant les primitives.

Une carte est considérée couverte capacité par capacité. Elle ne doit pas être
présentée comme « entièrement automatisée » tant que chaque paragraphe de son
texte n'est pas encodé et testé.
