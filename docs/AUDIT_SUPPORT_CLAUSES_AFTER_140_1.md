# Clauses de Soutien et interactions après 140.1

Travail local, sans changement de version ni publication. Cette passe complète
l'audit réseau et ajoute des preuves de résultats propres aux textes des cartes.

## Défauts reproduits

1. Pan Zuto déplaçait une carte de l'Interzone au Soutien sans ses déclenchements
   d'entrée dans la CZ. First Stone n'imposait donc pas son Enchaînement.
2. Consult omettait également les déclenchements d'entrée dans la CZ.
3. Twist the Soul omettait les déclenchements d'entrée sur le champ et dans la
   CZ : Keen-eyed Seeker ne faisait pas piocher, First Stone ne réagissait pas.
4. Le jeu spécial de Chabak n'annonçait pas l'événement de jeu en Soutien à
   Mazzolong : sa pioche n'était pas déclenchée.
5. Des mises en jeu déjà en attente contournaient l'interdiction de Pin Down :
   Pan Zuto, Consult, Twist the Soul, Silem et Regurgitating Catacomb.

Les premières reproductions sont conservées dans
`reports/systematic-audit/support-followup/before.json`, `expanded-before.json`
et `locks-before.json`, avec les résultats des méthodes et leurs empreintes
sources. Le collecteur conserve le dernier diagnostic lorsqu'une méthode a
plusieurs sous-cas en échec ; il ne fournit pas un décompte exhaustif de ceux-ci.

## Corrections et contrôles négatifs

Le chemin partagé distingue maintenant une nouvelle entrée sur le champ d'un
déplacement interne depuis l'Interzone. Tous deux provoquent l'entrée dans la CZ,
mais seul le premier provoque les effets d'entrée sur le champ. Une mise en jeu
par effet ne devient pas pour autant un jeu de carte.

Les tests vérifient notamment :

- Pan Zuto vers First Stone enchaîne exactement une fois ; vers Keen-eyed Seeker,
  il ne fait pas repiocher puisque la carte était déjà sur le champ.
- Consult et Twist provoquent les effets d'entrée applicables et les compteurs
  d'Intoxicating Blossom, sans déclencher la pioche de Mazzolong.
- Le véritable Enchaînement et le jeu spécial de Chabak déclenchent cette pioche,
  au bénéfice du contrôleur courant de Mazzolong.
- Pin Down empêche les cinq mises en jeu testées, sans extraire la carte de sa
  zone ; Wretched Arena les autorise puisqu'elles ne jouent pas les cartes.
  Consult défausse néanmoins les Volontés précédentes, puis laisse la
  Manifestation trouvée sur le Deck si elle ne peut entrer.
- Stoic Snoozer exige la défaite du tour précédent ; son +1 ne bénéficie qu'aux
  futurs Soutiens du bon joueur et expire au tour suivant.
- Jondo compare strictement les puissances de base, ignore les bonus additifs,
  et son exil de destination concerne le Soutien gagnant.
- Peropero expose le sommet du Deck de son contrôleur courant aux deux joueurs.
  Une carte couverte ou une Volonté est refusée sans mutation ; une Manifestation
  légalement jouée continue à se résoudre après son départ.
- Twist renvoie la carte gagnante au Vaisseau du contrôleur de l'effet, et la
  perdante ou ex aequo à la main de son propriétaire immuable.
- Silem supprime les effets des cartes amenées depuis l'Impasse ; leur expiration
  restaure les effets sans rejouer un déclenchement d'entrée.

## Preuve par clause

`python tools/card_support_audit.py` exécute les 26 méthodes du lot puis produit
`reports/systematic-audit/support-followup/clauses.json` : 15 paragraphes
sélectionnés de 12 cartes, avec texte anglais, empreinte, attente manuscrite et
identifiants exacts des tests. Les associations sont explicites ; elles ne
proviennent pas d'une recherche de noms de cartes dans le code.

Certaines actions sont isolées à leur résolution, sans refaire leur paiement ou
leur interface. Les tests d'événements injectent explicitement les événements
de production : ils ne prouvent pas tous les chemins qui peuvent les générer.
Les branches non listées et les autres interactions restent hors de ce lot.
Aucun pourcentage de certification globale n'en est déduit.

## Campagne générale

Les réexécutions de matrice, séquences, tests Python, parcours navigateur et UI
sont enregistrées dans le même dossier de suivi. Les rapports historiques de
publication et de l'audit réseau précédent restent inchangés. L'agrégat de cette
passe exige que toutes ses preuves portent l'empreinte des sources courantes.

Ces contrôles généraux ne remplacent pas les oracles manquants des autres
clauses. L'identité artistique des images, les téléphones physiques et Safari
iOS ne sont pas certifiés par cette passe.

## Résultats terminés

Toutes les couches ont terminé sans échec :

| Couche | Exécution |
| --- | --- |
| Clauses sélectionnées | 26 tests, 15 paragraphes, 12 cartes |
| Python complet | 1 270 tests réussis, aucun ignoré |
| UI | 13 suites réussies |
| Matrice | 450 cartes, 496 capacités, 119 contrôles de formulations imprimées |
| Navigateurs | 450 rendus, 182 actions, 2 parcours, aucun choix bloqué |
| Séquences | 40 traces, 12 175 étapes |
| Illustrations distantes | 450 chargements et décodages, aucun doublon binaire |

Les six preuves de sources (clauses, Python, UI, matrice, navigateurs et traces)
portent toutes l'empreinte
`1f52e2db65981db08ee88559df11725c7fcee78151f2d38ad2e66e09eaa40ba9`.
Les illustrations ont été chargées à nouveau ; les empreintes de leurs entrées
ont été validées. Les 450 fiches et 760 paragraphes restent structurellement
valides, sans que cette validation documentaire certifie leur exécution entière.

Le [rapport courant](../reports/systematic-audit/support-followup/EXECUTIONS.md)
résume les couches et les limites. `evidence.json` conserve les empreintes de
fichier et les résumés. La matrice garde notamment ses 2 826 cases
`needs-family-scenario` : ce sont des limites de couverture, pas des tests
nouvellement réussis ni un nombre de cartes restantes.
