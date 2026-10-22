# Corrections de l'audit des confirmations — après 139.2.1

L'audit effectué sur `1ed73bc` a été corrigé localement. Cette modification ne change pas le numéro de version et n'a pas été poussée.

## Choix bloquants

- **Atavic Introspection** : ne propose plus la récupération de deux cartes si les Limbes n'en contiennent pas deux éligibles. Le filtre des cibles couvre les cartes hors terrain, y compris les anciens contrats sans `kind` explicite.
- **Tut, Rhythmic Whirlwind** : avec deux cartes dans le deck, demande une carte dessus et une dessous. Avec une seule carte, celle-ci reste dans le deck sans confirmation inutile. Le paiement d'activation reste requis. Avec trois cartes, la répartition habituelle deux dessus / une dessous est conservée.

## Cibles et retours différés

- **Memento, the Fallen** et **Referen-Doom, the Dreamer** : après acceptation, ouvrent le sélecteur des Limbes avant de rejoindre la pile. Le joueur peut confirmer zéro, une ou plusieurs cibles autorisées. Le client transmet désormais aussi une sélection vide lorsque le minimum vaut zéro. L'adversaire reçoit ensuite la priorité normalement.
- Memento exclut sa propre carte. Referen-Doom propose seulement les Volontés. Ces effets et Zombieswing se limitent aux cartes éligibles dans les Limbes du joueur.
- **Zombieswing** : le serveur exclut sa propre carte lors du calcul des cibles disponibles et de leur validation. Sans autre Manifestation éligible, aucune proposition. Le client excluait déjà la source dans son sélecteur ; le défaut venait du serveur.
- **Coral Skull** et **Loop, the Insistent** : ne proposent plus un retour différé si la Volonté a déjà quitté les Limbes ; la mémoire devenue inutile est supprimée. Loop conserve sa condition de défaite.

## Propositions sans ressource utilisable

Le moteur contrôle les prérequis connus avant de demander l'activation d'un effet optionnel. Les résolveurs continuent à les vérifier à la résolution si la situation change entre-temps.

| Cartes | Condition nécessaire pour proposer l'effet |
|---|---|
| Alchemical Press, Atavic Oppression | Au moins une carte en main |
| Quorum, Ju Lien, Bullyboo | Au moins une Volonté en main |
| Phalanx Tower, Dew Invoker, Obelisk of Friendship, Auction Profiteer | Au moins une Manifestation en main |
| Juggling Amphora | Au moins deux Manifestations en main |
| Mind Parasite | Une Manifestation pouvant faire Chain depuis les Limbes |
| Dol | Une Manifestation du joueur pouvant faire Chain depuis un Réceptacle, y compris celui de l'adversaire |
| Gummo | Une Manifestation dans son Réceptacle et une source encore présente |
| Melancholic Mirror | Une source encore prête à être épuisée et une Manifestation liée à copier |
| Carcass Devourer | Une Manifestation dans les Limbes à exiler |

**Obelisk** garde sa séquence : proposition en Réaction, effet dans la pile, cadeau choisi à la résolution. **Freenya** conserve sa proposition même avec des Limbes vides, puisqu'elle accorde une permission utilisable plus tard. **Numbi** conserve son effet sur l'adversaire même avec une main vide chez son contrôleur : Chain si possible, preuve de la main sinon. Si la main adverse est entièrement vide, aucune proposition inutile.

## Ordre sans conséquence

**Shababba, Divining Cube** : un deck contenant une seule carte ne demande plus de choisir dessus/dessous, puisque les deux dispositions sont identiques. L'effet conserve la procédure normale de continuation. Avec deux cartes ou plus, le choix reste disponible.

## Validation

- **721 tests Python réussis**, contrôles frontend généraux réussis et régressions navigateur PC/mobile réussies.
- Régressions moteur dédiées dans `tests/test_confirmation_audit.py` : prérequis absents et présents, sélections légales et interdites, résolution effective, paiement de Tut avec des decks de 0 à 3 cartes, retours différés, Freenya et Numbi.
- Régressions navigateur dans `tests/test_release_139_2.cjs` : sélecteurs de Memento et Referen-Doom sur PC et téléphone, filtrage des cartes, confirmation de zéro ou d'une cible.
- Registre `public/automation-coverage.json` régénéré après la mise à jour des contrats de cibles.
