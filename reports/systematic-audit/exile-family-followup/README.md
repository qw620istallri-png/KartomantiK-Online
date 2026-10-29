# Exil : suite locale après la 141.3

La 141.3 publiée reste au commit `2f08549`. Les modifications de ce lot sont locales.

## Lecture des preuves

- `before.json` : 74 méthodes, 62 passent, 12 échouent. Onze échecs de Carcass exposent l'absence du choix des cibles avant la pile ; Referen-Doom reçoit à tort +1 sous BOB.
- `target-choice-fixed.json` : après rétablissement du choix avant la pile, la récompense indue de Carcass sous BOB et la relance du choix après zéro cible deviennent observables. Un des quatre échecs est une fixture de retour du Vaisseau envoyée vers une main de mauvais propriétaire ; la fixture est corrigée, sans changer le moteur.
- Les journaux initiaux, locaux, comprennent aussi des erreurs de préparation du banc : nom d'accesseur d'épuisement inexistant, propriété invalide d'une carte au Vaisseau, ordre d'Exil comparé inutilement, nom de champ du jeton d'essence. Ils ne sont pas revendiqués comme bugs du jeu.
- `clauses.json` : 91 cas passants, dont 82 méthodes unitaires et neuf parcours à deux sockets. Neuf paragraphes sélectionnés de sept cartes sont liés explicitement aux IDs de tests.
- `adjacent.log` : 52 contrôles voisins passent après mise à jour de deux anciennes attentes de Carcass.
- `unit-tests.json` et `evidence.json` : régression complète et empreintes finales, une fois terminées.

Les oracles de coûts, limites et récompenses sont écrits depuis les textes imprimés ; l'effet réel utilise les capacités livrées. Les cibles, l'entrée ETB et l'état de BOB sont des fixtures. Les neuf parcours réseau utilisent de vrais choix/déclarations/réponses ; l'avance automatique des phases est neutralisée pour isoler les effets. Aucun match complet ni appareil physique n'est certifié.

Les journaux sont locaux selon `.gitignore` ; JSON, scripts et rapport sont versionnables.
