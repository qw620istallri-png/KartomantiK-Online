# Audit des clauses d'exil après la 141.3

La 141.3 a été poussée sur `main` au commit `2f08549`. Ce lot suivant reste local.

## Périmètre sélectionné

| Carte | Clauses vérifiées |
| --- | --- |
| Exile | Manifestation sur le champ ou dans l'un des Limbos ; coût de quatre essences ; cible devenue protégée/invalide. |
| Carcass Devourer | ETB facultatif, zéro à deux cibles de son Limbo choisies avant la pile ; somme des puissances de base effectivement exilées. |
| Referen-Doom | ETB facultatif, n'importe quel nombre de Volontés de son Limbo ; +1 par exil effectif jusqu'à la fin du tour, y compris 21 cibles distinctes. |
| Horned Augustus | Confrontation, épuisement payé à l'activation ; zéro à trois cartes de son Limbo ; un Support jeton de puissance 1 colérique par exil effectif. |
| Everspring | Paiement de trois Larmes ; zéro à trois Manifestations au Vaisseau adverse, total maximal de 60 points ; retour en Exil chez le propriétaire. |
| Shattered Memory | Épuisement pour une carte de n'importe quel type dans l'un des Limbos ; exil de la source comme coût, puis exactement une essence transcendante à la résolution. |
| Subjugate | Coût minimal d'une essence puis jusqu'à quatre supplémentaires, seuils de dix points ; surplus d'un tribut utilisable pour le supplément, reste flottant conservé. |

Les autres paragraphes de Carcass, Referen-Doom et Everspring ne sont pas ajoutés à la certification de ce lot. Les cartes d'interaction ne sont pas comptées comme cartes couvertes.

## Corrections

1. Carcass et Referen-Doom ne comptent plus une suspension par BOB comme un exil réussi : aucun bonus de puissance n'est accordé pour la carte suspendue.
2. Carcass demande ses cibles après acceptation de l'ETB, avant sa mise sur la pile. L'adversaire voit donc les cibles déclarées avant de répondre.
3. Choisir zéro cible pour Carcass termine normalement l'effet ; aucun second sélecteur de Limbo ne s'ouvre à la résolution. Le chemin de compatibilité pour une action brute sans contrat de cibles reste conservé.

Les mouvements et l'attribution des bonus restent gérés dans leurs couches existantes : `effects/power.py` et `triggers.py`. Aucun changement de catalogue ni de protocole réseau.

## Preuves

- 91 cas sélectionnés passent : 82 méthodes unitaires et neuf parcours réseau à deux connexions.
- Les tests contrôlent les valeurs exactes, l'absence d'effet avant résolution, les paiements à la déclaration et les cibles devenues absentes, les cibles restantes d'un effet multiple et la nouvelle instance après sortie/retour au Limbo ou au Vaisseau.
- Les bonus temporaires expirent à la rotation de tour, ceux de Carcass persistent sur le champ et disparaissent lors d'une nouvelle entrée. Les effets encore sur la pile poursuivent l'exil après départ de leur source.
- Les paiements invalides, limites de nombre et de points, faux propriétaire fourni par le client et cibles de mauvais type/zone sont refusés dans les branches décrites.
- Les 52 contrôles voisins passent. Deux tests historiques ont été adaptés à la séquence correcte de Carcass au lieu d'attendre un choix tardif.
- Les preuves de régression complète et le compteur courant sont dans `reports/systematic-audit/exile-family-followup/` et `coverage-status.json`.

## Limites

Ce sont des clauses et branches nommées, pas toutes les interactions des sept cartes. Les événements ETB et les zones initiales sont des fixtures contrôlées ; les parcours réseau désactivent l'avance automatique des phases. Aucun nouveau contrôle d'illustration distante, de téléphone, de Safari réel ou de partie complète n'est revendiqué. Les doublons physiques d'une même référence dans une zone ne sont pas certifiés par ce lot.

Validation finale : **3174/3174 tests Python passent**, zéro échec et zéro test
ignoré ; les deux suites client concernées passent. Registre strict actualisé à
**136/450 cartes (30,2 %)**, soit sept nouvelles et 314 hors registre.
Le digest des preuves du lot, de la régression complète et du registre est identique.
