# Corrections de l'audit pile et priorité — après 139.2.1

Les quatre problèmes reproduits dans l'audit du 22 octobre 2026 sont corrigés localement, sans changement de version ni push.

- **Fenêtres spéciales et auto-pass** : Juggernut et Gummo restent activables en fin de Recovery ; Wretched Arena reste activable avant Révélation. La détection des actions disponibles tient compte des fenêtres explicites des capacités de champ, de leur paiement et de l'état de la source.
- **Volontés Persistantes** : la pile doit être vide pour les jouer, y compris en phase finale, avant Révélation pour les Atavic, et pour Juggernut joué comme une Persistante. Le serveur, l'auto-pass et les indications de la main appliquent la même restriction.
- **Soup** : son autorisation permet les réponses avec des Persistantes aux timings des Éphémères, y compris sur une pile occupée.
- **Effets simultanés optionnels** : la priorité de départ du lot est conservée pendant les confirmations et les sélections de cibles. L'ordre des Obelisks reste stable quel que soit leur ordre dans le tableau du plateau ; le cadeau est toujours choisi à la résolution.

Le test historique autorisant une Atavic à répondre à une autre Atavic avant Révélation a été remplacé par le contrôle de pile vide prévu au livret actuel, page 14. L'autorisation de jouer avant Révélation reste vérifiée sur pile vide.

Validation : **726 tests Python réussis** ; régressions navigateur PC/mobile réussies, avec une matrice dédiée aux timings des Persistantes et à Soup. Les nouveaux cas moteur sont dans `tests/test_stack_priority_audit.py`.
