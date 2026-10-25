# Audit des départs de source, des cibles et des mémoires

Exécuté : 2026-10-24T10:52:25.765044+00:00
Empreinte : `6c2f35c141e38df5929a6186dede0d8bbe2cbed938e3ab93a693e1fe465ca0f1`

**Lot terminé pour les cas décrits ci-dessous ; les deux arbitrages du créateur sont appliqués.**

```json
{
  "executed": 27,
  "passed": 27,
  "failed": 0,
  "skipped": 0,
  "pendingRulings": 0,
  "departureAuditComplete": true,
  "fullCatalogSemanticCertification": false
}
```

## Corrections reproduites

- Mukkabell et Looj conservaient leurs règles accordées seulement dans l'objet du champ. Elles sont désormais enregistrées comme mémoires et restaurées après la main ou le Limbo.
- Chaque règle conserve le contrôleur de l'effet qui l'a accordée. Des Enchaînements successifs conservent chaque règle une seule fois, avec son propre contrôleur.
- L'exil ou la mise au Deck d'un autre exemplaire physique n'efface plus une mémoire attachée à une carte encore sur le champ ou en Stalemate.
- Looj attribue les points au véritable gagnant de la Confrontation, même après un changement de contrôleur de la Manifestation enchaînée. Le contrôleur de l'effet reste inchangé sur la Pile.
- Les copies n'héritent pas de ces mémoires ; Cleanse les préserve ; Deck et Exil les effacent lorsque la carte concernée y entre.

- Recover et Reforging Fate ne peuvent plus viser une nouvelle entrée de la même carte au Limbo. Le suivi s'applique aussi aux cibles du Vaisseau et de la main, sans invalider un simple changement d'ordre dans la même zone.
- Une source partie du champ utilise sa puissance imprimée. Lombriculpop et Armored Pachywyrm conservent ainsi leur calcul au lieu de produire zéro. Mukkabell et Referen-Doom avaient déjà ce repli ; les tests le garantissent.

## Preuves exécutées

- Déclaration réelle de Bolbakazim et résolution après disparition de sa source.
- Réponse Exile réelle puis reconnexion et deux passes de priorité via WebSocket.
- Identité des objets du champ : une nouvelle instance n'hérite pas des cibles ni des modifications visant l'ancienne.
- Mémoire des règles accordées par Mukkabell/Looj : main, Limbo, Deck, Exil, Cleanse et contrôleurs distincts.
- Trois reconnexions réseau : activation après Exile, mémoire de contrôle et invalidation automatique de Recover. Les mutations de fixture sont distinguées des messages réels.
- Puissances imprimées après départ : Mukkabell, Referen-Doom, Lombriculpop et Armored Pachywyrm.
- Anciennes entrées du Limbo/Vaisseau invalidées, repositions préservées, cibles indépendantes restantes résolues, copies héritées invalidées et nouvelles sélections acceptées.

## Arbitrages confirmés du créateur

- Au calcul, une source encore sur le champ utilise ses caractéristiques modifiées actives. Si elle a quitté le champ pour le Limbo, le Vaisseau, la main, le Deck ou l'Exil, ses modificateurs sont perdus et l'effet utilise ses valeurs imprimées. Mukkabell : base 4 doublée à 8, puis départ avant résolution = 20 points ; sans départ = 40 points.
- Une carte ciblée qui quitte puis regagne le Limbo est une nouvelle entrée. Elle n'est plus la cible initiale : l'effet échoue pour cette cible ; les autres cibles indépendantes encore valides se résolvent normalement.

Les réponses du créateur sont conservées dans audit/rule-decisions.json et priment sur les interprétations antérieures. Le livret local, section 3.2 (pages imprimées 19–20), reste la référence pour l'indépendance des effets, le ciblage et les mémoires.

## Limites

- Deux exemplaires physiques en zones privées ne disposent pas d'identifiants individuels ; le format tournoi impose des cartes uniques par deck.
- Les comparaisons lorsque les deux Manifestations de référence sont absentes ne sont pas couvertes par ce lot.
- Les autres mémoires et toutes les combinaisons de cartes ne sont pas certifiées par ce lot.

Les campagnes générales et les preuves du lot numérique précédent sont historiques après ces modifications. Les tests actuels ne restampillent pas des parcours navigateur ou des séquences non relancés.

[Résultats détaillés](departure.json) · [Première reproduction](departure-before.json) · [Reproduction des décisions avant correctif](departure-rulings-before.json) · [Assertions des décisions](../../tests/test_departure_rulings.py) · [Parcours réseau](../../tests/test_departure_resolution_integration.py)
