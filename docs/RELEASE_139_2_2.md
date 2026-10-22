# Beta 139.2.2 — clôture des audits du moteur

Cette version regroupe les corrections des audits de confirmations, pile et priorité, paiements combinés, transferts et destinations de confrontation. Tous les problèmes reproduits dans ces audits sont corrigés et couverts par les vérifications décrites ci-dessous.

## Dernières corrections

- Les destinations spéciales de victoire/défaite s'appliquent au résultat réel de la Manifestation avant les captures ordinaires. Reforging Fate exile un Support qui a gagné sous le contrôle du réanimateur, quel que soit son propriétaire. Il ne l'exile pas en cas de défaite.
- La comparaison mémorise les participants gagnants/perdants : les changements de contrôle ultérieurs ne changent pas leur résultat. Tigrolione et Losers' Chariot suivent aussi leur défaite réelle pour leurs destinations spéciales.
- BOB libère les cartes suspendues lorsqu'il quitte la CZ pour Stalemate ou l'Interzone, même s'il reste sur le champ. La baisse de puissance seule ne les libère pas. Le seuil 11 exile toujours BOB et ses cartes suspendues.
- Les placements ordinaires dans Stalemate et dans l'Interzone du propriétaire rétablissent le contrôle attendu. Le choix d'Interzone reste utilisable pour une carte dont le propriétaire et le contrôleur différaient pendant la confrontation.
- Les coûts supplémentaires d'exil/défausse ne sont plus silencieusement empêchés par l'immunité des mains de BOB : payer un coût utilise le chemin de paiement, distinct du déplacement provoqué par un effet.

## Rectification du dernier diagnostic

Le dernier rapport avait attribué trop largement le problème de Reforging Fate à la capture selon le propriétaire. Le livret courant, §4.2.3 page 25, prescrit explicitement cette règle pour les captures ordinaires. Elle est conservée. Le défaut concernait la priorité des destinations spéciales et leur condition de victoire, à distinguer des captures ordinaires. Les tests vérifient les deux comportements. Le §3.2 page 19 sert également de référence pour la propriété, le contrôle et les entrées en zones partagées.

## Corrections précédentes incluses

- Confirmations optionnelles seulement lorsqu'une ressource ou une cible utile existe ; sélecteurs de Limbes et choix de zéro cible fonctionnels.
- Fenêtres spéciales de Juggernut/Gummo/Wretched Arena, restriction de pile vide des Persistantes, exception de Soup et priorité conservée pendant les choix simultanés.
- Réservation des cartes pour éviter un double paiement, excédent utilisable avec Rally et remboursements multicolores corrects.
- Vérification de présence des cibles à la résolution, suspension appliquée aux transferts et choix différés, effets d'entrée des Manifestations réanimées mis en pile. Urolong conserve son exception de perte des effets.

## Validation

**750 tests Python réussis** ; régressions navigateur générales et PC/mobile réussies.

Les régressions dédiées sont dans `tests/test_confirmation_audit.py`, `tests/test_stack_priority_audit.py`, `tests/test_combined_payment_audit.py`, `tests/test_zone_transition_audit.py` et `tests/test_control_cleanup_audit.py`.

Le contrôle du catalogue exécute 496 capacités sur 500 variantes d'état pour 379 cartes encodées. Il complète les tests de règles et ne constitue pas une preuve exhaustive de toutes les combinaisons possibles du jeu. Le registre d'automatisation est vérifié à jour.

Les contrôles navigateur couvrent les parcours de paiement, les choix de cartes des Limbes, Grimoire, les confirmations, les timings et les interfaces PC/mobile. La version des ressources et du service worker est synchronisée en `20261022-rules-beta-139-2-2`.
