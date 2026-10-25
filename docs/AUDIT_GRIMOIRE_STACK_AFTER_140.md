# Grimoire et séquences de pile après la version 140

Travail du 25 octobre 2026, intégré à la version 140.1 à la demande du créateur.

Le choix des Volontés du Grimoire affiche désormais les cartes sélectionnées,
permet de les retirer en cliquant leur aperçu, grise leurs exemplaires dans
la main et propose « Confirmer la pose (N) » ou « Ne rien poser ».
La sélection fait partie de la clé de rendu. L'instruction de glisser une carte
est réutilisée plutôt qu'ajoutée à chaque rafraîchissement. Ces deux corrections
s'appliquent aux autres choix de plusieurs cartes depuis la main.

## Clauses et branches ajoutées à la couverture

`tests/test_semantic_grimoire_sequences.py` contient huit méthodes manuscrites :

| Cas | Résultat vérifié |
| --- | --- |
| Grimoire : zéro, une ou deux copies identiques | Nombre exact dans la main, sur le Grimoire et sur son compteur ; aucun envoi aux Limbes |
| Type interdit ou troisième copie inexistante | Refus sans mutation ni perte du choix |
| Volonté appartenant à l'autre joueur | Identité et propriétaire visibles dans les deux vues |
| Grimoire absent au moment de confirmer | Main conservée |
| Grimoire quitte le champ | Chaque Volonté est exilée chez son propriétaire |
| Jouer une Volonté d'un autre propriétaire | Coût normal, cible normale, +3 effectif, retour aux Limbes du propriétaire |
| Renforcer résolu pendant la Réaction | Aucune comparaison tant que Renforcer est sur la pile ; Sermon gagne ensuite 8–6 contre Tong |
| Renforcer résolu après la comparaison | Sermon passe bien à 8 ; le résultat déjà fixé à 5–6 ne change pas |

Le sixième cas reproduisait un défaut : le serveur exigeait que les Volontés
sur le Grimoire appartiennent à son contrôleur, alors que son texte les rend
jouables comme depuis sa main. Cette restriction est retirée ; la source jouée
conserve le véritable propriétaire et le passage automatique reconnaît cette
possibilité de jeu.

`tests/test_stack_pacing.py` ajoute six méthodes traversant le moteur et la
diffusion des états serveur :

- pile ordinaire : états successifs de profondeur 2, 1, 0 et scores 3, 5, 6 ;
- effets immédiats : résolution et diffusion individuelles avant l'effet normal ;
- réponse devenue possible pendant la pause : arrêt du vidage automatique ;
- interruption du pilote : libération de sa garde de réentrance ;
- Renforcer/Sermon/Tong avec passages automatiques réels : pile vidée pendant
  la Réaction, confirmation de fin de Réaction, puis comparaison à 8–6 ;
- choix d'un effet immédiat terminé : libération des effets normaux différés.

Le serveur diffuse chaque résolution avant la suivante et ménage 1,7 seconde
pour les tables connectées. Les simulations hors connexion restent sans délai.
Un seul pilote de passage automatique peut être actif par session. Chaque
reprise réévalue les possibilités de réponse et les choix requis.

## Interface

`tests/test_choice_continuity.cjs` ajoute neuf assertions par format d'écran,
en français : libellés explicites, aperçu de copies distinctes, instruction
unique après plusieurs états reçus, images grisées, retrait d'une sélection,
compte du bouton, charge utile exacte, verrouillage du double envoi et choix
vide explicite. Les vérifications existantes couvrent aussi le changement de
main, la reconnexion et les réponses périmées.

Les deux formats Chrome contrôlés sont 1440 × 1000 et 844 × 390. Les captures
du banc de test utilisent des dos de cartes locaux ; elles prouvent la mise en
page et les états, pas les illustrations distantes ni un appareil physique.

## Signalement Sermon et Tong

Dans le journal fourni, la comparaison est enregistrée à 18:05:35 avec une pile
vide lors des passes précédentes. Renforcer est déclaré à 18:06:25, dans
`resolution_effects`, et son +3 est appliqué à 18:08:47. Le livret français,
section « Phase de Résolution », précise que les effets de cette fenêtre
n'altèrent pas le résultat de la confrontation.

Le joueur indique toutefois avoir joué pendant la bonne phase et soupçonne un
passage automatique avec une pile non vide. Ce scénario ne se reproduit pas
dans les tests ajoutés. Le journal établit l'ordre enregistré par le serveur,
sans établir à lui seul ce qui était affiché au moment de la manipulation.
Ce signalement reste à reproduire ; il n'est pas déclaré corrigé par la seule
amélioration de la cadence et de la diffusion des états intermédiaires.

La vérification du client a identifié un défaut d'affichage distinct : les
annonces de phase attendent dans la file d'animations et pouvaient annoncer
« Confrontation » alors que l'état courant était déjà en Résolution. Les
annonces d'une autre phase ou d'un ancien tour sont désormais ignorées ; une
annonce visible est retirée quand elle ne correspond plus à la phase courante.
Quatre assertions par format dans `test_rarity_immediate_vfx.cjs` vérifient les
annonces périmées, l'annonce courante et le retrait lors d'un changement d'état.
Le lien causal avec la partie signalée n'est pas établi.

## Portée de la preuve

Première validation avant le changement de numéro de version : 1 220 tests
Python réussis, aucun échec ni test ignoré ; 13 suites UI réussies. La passe
suivante sur les [effets différés au tribut](AUDIT_DELAYED_TRIBUTE_140_1.md)
complète cette couverture. Les rapports d'exécution sont actualisés après
cette seconde passe et conservent leur empreinte de source.
Le registre indépendant reste structurellement valide : 450 cartes et
760 paragraphes. Ses liens AST indexent désormais aussi ces nouvelles familles
de scénarios et le suivi d'intégration. Ils restent des liens de navigation ;
les contrats sont détaillés ici et les exécutions figurent dans le rapport Python.

Les nouveaux tests complètent la couverture des branches ; ils ne certifient
pas l'ensemble des interactions des 450 cartes. Les campagnes complètes de
matrice, traces et parcours des 450 cartes publiées avec la version 140 restent
historiques après ces modifications. Leurs empreintes ne sont pas réécrites.
Les nouvelles exécutions Python et UI sont consignées séparément dans
`reports/systematic-audit/unit-tests.json` et `ui-tests.json`.
