# Mélanges de Main suivis de pioche

Ce lot vérifie les clauses de **Deny Fate** (mélanger sa Main, puis piocher sept
cartes, seulement avant la Révélation) et **Pontificate Heresy** (effet immédiat :
tous mélangent leur Main, puis chacun pioche quatre cartes). Les textes et les
quantités attendues sont figés manuellement dans `audit/shuffle-draw.json`.

## Défauts reproduits et correction

La [reproduction initiale](../reports/systematic-audit/shuffle-draw-followup/before.json)
conserve 31 méthodes, dont **dix échecs** :

- Deny Fate contournait le remplacement de pioche de Kanon et transmettait les
  identifiants des cartes piochées à l'adversaire dans son résultat de résolution.
- Pontificate contournait Kanon et les blocages de pioche, ne regroupait pas les
  cartes piochées en un événement de pioche, et déplaçait les cartes d'une Main
  protégée par le Purifying Ritual adverse.
- Pontificate faisait mélanger puis piocher le premier joueur avant de mélanger
  la Main du second, au lieu de terminer les mélanges avant les pioches.

Les deux effets passent désormais par la demande commune de pioche. Pontificate
termine les mouvements de toutes les Mains avant les demandes de pioche. Une
Main immunisée conserve ses cartes ; la pioche depuis le Deck reste une
instruction indépendante et s'effectue si elle est autorisée.

Les demandes restantes sont conservées sur le choix en cours dans un champ
privé. Elles ne reprennent qu'après une réponse valide et la fin des choix
consécutifs de remplacement. Si Kanon fait défausser une Volonté, sa distribution
de malus doit donc être terminée avant la pioche du second joueur. Le champ est
transféré au choix suivant et reste présent dans l'état serveur après sérialisation.
Les refus et réponses rejouées ne reprennent pas la séquence.

Le résultat historique `draw` de Deny Fate est filtré pour les autres joueurs,
comme les autres listes privées de cartes piochées. Le propriétaire conserve ses
informations. Les rôles d'observation privilégiés gardent leur modèle existant.

## Scénarios exécutés

**37 méthodes de famille** vérifient les quantités exactes, conservation du
multiensemble de cartes, Mains et Decks vides ou courts, doublons, jeu par le
second joueur, paiement exact et destination normale de la Volonté jouée.

Les interactions sélectionnées couvrent les blocages de pioche de chaque joueur,
BOB (sorties de Deck et immunité de Main), Purifying Ritual allié et adverse,
Kanon seul ou chez les deux joueurs, sa distribution de malus après défausse de
Volontés, les événements de pioche groupés et l'ordre des étapes. Les conflits
BOB/exil sont résolus avant tout mouvement et reprennent la pioche restante une
seule fois. Les choix invalides, du mauvais joueur ou déjà consommés sont refusés
sans mutation ; le choix et sa continuation survivent à un aller-retour JSON.

**Cinq parcours WebSocket** utilisent de vraies déclarations, passages de priorité
pour Deny Fate et résolutions immédiates pour Pontificate. Un client incrémental
et un client ancien reçoivent les états attendus. Les parcours Kanon incluent
reconnexion, refus d'une sélection vide et d'une confirmation rejouée. La phase
reste stable pendant l'effet et les choix. Le pilote automatique des phases est
isolé : ces parcours ne constituent pas un nouvel audit de l'auto-skip.

Le lot totalise **42 méthodes**. Les deux premiers essais réseau normaux
attendaient à tort un nouvel état après avoir déjà consommé l'état final ; le
banc réutilise cet état. Cet ajustement n'est pas compté comme défaut du jeu.

## Preuves et limites

La commande `python tools/card_shuffle_draw_audit.py` produit les
[preuves par clause](../reports/systematic-audit/shuffle-draw-followup/clauses.json).
Le [registre d'exécution](../reports/systematic-audit/shuffle-draw-followup/EXECUTIONS.md)
relie reproduction, suite complète, suites client et empreintes des fichiers.

La validation finale réussit **2 657 méthodes Python distinctes** et trois suites
client, dont 608 scénarios de parité. Aucun échec ni test ignoré. Les deux cartes
s'ajoutent au [registre strict](../reports/systematic-audit/coverage-status.json),
qui passe de **118 à 120 sur 450 (26,7 %)**, avec au moins une clause sélectionnée
vérifiée par carte. Cela ne certifie pas toutes leurs branches.

Les mélanges sont rendus déterministes dans les scénarios pour vérifier
l'ordre et les quantités ; la qualité du hasard n'est pas auditée. Les
remplacements sont préparés explicitement. Toutes les interactions possibles,
parties complètes et autres clauses des cartes ne sont pas certifiées.

Les effets conditionnels « défaussez ; si vous le faites, piochez » restent dans
le lot suivant : leur traitement lorsque la défausse est suspendue ou exilée
attend une précision de règle. Aucun changement VFX, fichier client, version,
commit ou push. Aucun nouveau test Safari, appareil physique ou illustration.

Mise à jour : les précisions sur les suites conditionnelles ont été reçues et
vérifiées dans la [passe suivante](AUDIT_CONDITIONAL_DISCARD_AFTER_141.md).
La limite indiquée ci-dessus décrit le périmètre historique du lot de mélanges.
