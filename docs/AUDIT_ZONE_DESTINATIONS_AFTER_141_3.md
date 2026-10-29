# Lot de six cartes : destinations et remplacements

Les corrections de ce lot restent locales, après la publication de la 141.3.

| Carte | Clause et résultat exact sélectionnés |
| --- | --- |
| Defer | Manifestation ou Volonté (Persistante ou Éphémère) du champ au-dessus du Deck de son propriétaire ; coût de deux essences vitreuses. |
| Banish | Manifestation du champ sous le Deck de son propriétaire ; coût de trois essences vitreuses. |
| Revive | Manifestation de son Limbo vers son Interzone ; coût de quatre essences mélancoliques ; capacité de l'Interzone. |
| Claim the Forsaken | Manifestation entrée ce tour au Limbo adverse vers son propre Vaisseau ; quatre essences mélancoliques. |
| Salvage the Fragments | Manifestation entrée ce tour au Vaisseau adverse vers l'Impasse ; deux essences capricieuses. |
| Manipulate Intellect | Manifestation non possédée, entrée ce tour dans l'Interzone adverse, vers son Vaisseau ; quatre essences capricieuses. |

Les oracles de coût et destination sont littéraux dans `audit/zone-destination-family.json` et les tests. Les capacités exécutées sont celles du catalogue, dont le texte est épinglé par empreinte.

## Défauts corrigés

Revive et Claim extrayaient directement leur cible du Limbo, en contournant le remplacement par BOB. Ils préparent maintenant les remplacements avant extraction. Le déplacement effectivement remplacé ne crée aucun objet sur le terrain ni carte au Vaisseau, et une sortie de zone causée par effet reste enregistrée une fois pour les observateurs comme Katun.

Le cas ajouté Revive + Nullify Reason exposait aussi l'absence de l'Interzone dans le sélecteur commun des remplacements de destination. Elle est désormais incluse, de sorte que les remplacements concurrents avec BOB passent par le choix d'ordre existant. Les marqueurs/bonus d'entrée ne sont pas appliqués avant la décision de remplacement.

Defer refusait également les Volontés Éphémères sur le champ malgré son texte générique « Will ». Le contrat de ciblage les accepte maintenant, avec une preuve utilisant Pray the Ether comme carte réelle.

## Validation

- 65 cas : 57 méthodes unitaires et huit parcours à deux sockets réelles.
- Coûts payés à la déclaration, mouvement à la résolution, dessus/dessous exact, propriété et contrôle, type de carte, entrées ce tour, protection en réponse, disparition puis retour de la cible, capacité d'Interzone, BOB, Nullify et leur concurrence.
- Le départ de zone n'est enregistré qu'une fois, avec ou sans suspension.
- Les tests de départ et destination utilisent des cibles synthétiques contrôlées. L'avance automatique des phases est désactivée dans ces huit parcours pour isoler la pile.
- `before.json` conserve 51 méthodes dont deux échecs sur BOB ; le cas ultérieur Nullify est décrit dans le rapport final. Les deux erreurs d'import du tout premier essai étaient dans le banc, pas dans le jeu.

Les six clauses constituent une couverture sélectionnée, pas toutes les interactions des six cartes. Aucun contrôle d'illustration ni d'appareil physique n'est ajouté par ce lot. Le registre strict sera actualisé seulement avec une régression complète courante et passante.

Validation générale finale : **3242/3242 tests Python passent**, aucun échec ni
test ignoré. Registre strict actualisé à **142/450 cartes (31,6 %)**, soit six
nouvelles cartes avec clauses prouvées et 308 hors registre. Les preuves du lot,
de la suite générale et du registre utilisent le même digest courant. Aucun push.
