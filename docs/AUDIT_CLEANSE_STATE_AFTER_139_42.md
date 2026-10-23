# Audit Cleanse et durée des états après 139.42

Passe du 23 octobre 2026. Corrections intégrées à la version 139.43 à la demande du joueur.

## Défauts reproduits et corrigés

- Les bonus/malus des emplacements internes `counters.power` et `counters.tempCounter` survivaient à Cleanse. Ce sont des modifications de statistiques, distinctes des ressources nommées. Cleanse les retire maintenant, en gardant Gem, Quiet, Shackle, Atavic et les autres compteurs de ressources. L'ancien test qui conservait artificiellement +2 a été corrigé ; Humiliate retrouve bien sa puissance et son tempérament d'origine.
- La copie de base et de capacités de Gummo restait après Cleanse. `gummoCopy` est maintenant retiré avant de recalculer les caractéristiques imprimées ; une propriété héritée de la copie n'est pas rétablie par ce recalcul.
- Les bornes de puissance stockées directement sur une carte n'étaient pas nettoyées. Elles sont désormais retirées comme les modificateurs équivalents de la liste d'effets.
- Une Volonté animée par Rinq/Ju Lien restait une Manifestation jusqu'à la Résolution. Cleanse annule désormais cette transformation immédiatement : retour comme Volonté sur le champ, sortie de la Zone de Confrontation, ressources conservées, capacités d'origine actives, sans nouvelle entrée sur le champ.
- Quand Cleanse supprimait le lien de Jaw/Nectar, ou quand l'ancienne cible quittait le champ, le reciblage ne trouvait plus d'effet à déplacer. Il recrée maintenant le modificateur depuis la capacité initiale de la source. Les quatre Volontés concernées (Jaw, Nectar, Armored Husk, Altruistic Inflorescence) passent les tests de déclaration, paiement, Épuisement et résolution.
- Nectar pouvait recibler pendant une Réaction malgré son texte qui exige la Phase Finale. Son activation est maintenant limitée à `end_actions` ; une tentative hors fenêtre ne dépense aucune ressource et n'épuise pas la carte.

## Règles confirmées par le joueur

- Un modificateur de Jaw/Nectar retiré par Cleanse ne revient pas tout seul. Une nouvelle activation de ciblage est requise.
- Un passif imprimé continu, par exemple une suppression globale d'effets, continue en revanche à s'appliquer tant que sa condition reste vraie.
- Une mémoire, comme l'exil après victoire, reste distincte des modificateurs. Cleanse la conserve ; elle disparaît au Deck ou à l'Exil. Le test de victoire vérifie qu'elle exile toujours la carte après nettoyage de ses bonus.
- Cleanse annule immédiatement l'animation d'une Volonté, sans envoyer cette carte aux Limbes ou dans une autre pile.

## Cas conservés

- Les sorties vers la main, les Limbes, le Deck et la suspension suivie d'un retour créent une nouvelle instance sans les anciens compteurs, copies ou bonus. Le passage de l'Interzone en Soutien conserve l'instance et ses ressources.
- Nettoyer une source réactive ses effets imprimés, mais ne répète pas son effet d'entrée. Temperamental Splendor garde ses Gem et son tempérament choisi, sans nouvelle demande de choix.
- Un effet déjà sur la Pile et un modificateur résolu indépendant de sa source restent valides. Cleanse ne les annule pas en nettoyant seulement leur source.
- La perte du dernier bonus pouvant maintenir une carte au-dessus de zéro déclenche bien les actions d'état lors de la résolution de Cleanse.

## Vérification

- `tests/test_cleanse_state_audit.py` : 20 tests, dont plusieurs permutations de cartes ou de zones.
- `tests/test_cleanse_state_integration.py` : nettoyage via les vrais messages joueur, état reçu sans le pseudo-compteur de puissance, ressources conservées, reconnexion puis reciblage de Nectar payé et résolu sur sa nouvelle cible.
- Suite Python complète : **895 tests réussis**, incluant les 21 régressions de cette passe et les contrôles de catalogue/scénarios.
- Régressions générales de l'interface dans Chrome : **réussies**. Registre d'automatisation régénéré et validé par la suite complète.

Cette passe vérifie ces familles d'états et les cas reproduits ; elle ne prouve pas toutes les combinaisons possibles du catalogue.
