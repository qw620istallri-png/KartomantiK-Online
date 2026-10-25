# Corrections issues de la revue indépendante

Les trois revues initiales ont enregistré 51 signalements et trois questions de
règles historiques. Une relecture des corrections et de leurs régressions n'a
confirmé aucun de ces défauts comme encore ouvert. Les fiches initiales gardent
leur statut historique : le tableau ci-dessous décrit le suivi, sans convertir
une revue statique en certification de toutes les branches d'une carte.

Les résultats exécutés et leur empreinte sont conservés dans
[unit-tests.json](unit-tests.json). Les modules ci-dessous contiennent des
attentes manuscrites à partir du texte imprimé et des arbitrages ; leurs
références servent à retrouver les scénarios, pas à certifier toute la carte.

| Cartes / problème | Correction vérifiée | Régressions |
|---|---|---|
| Merciful Pago, Flaying Jaw | Déclenchements normaux sur la Pile ; cibles et effet à la résolution | semantic_batch_001_150, semantic_batch_151_300 |
| Advocate of Catharsis | Engagements privés avant toute entrée simultanée | semantic_batch_001_150 |
| Intoxicating Blossom, Suspend Judgment | Contrôleur courant plutôt que propriétaire | semantic_batch_001_150 |
| Jurat | Tous les tributs du tour, y compris après son effet ; registres purgés au redémarrage | semantic_batch_001_150, semantic_integration_followup |
| Gomeran, Carcass Devourer, Jija | Mélange après placement sous le Deck, avec les deux formulations imprimées | semantic_batch_001_150, semantic_batch_151_300 |
| Revive | Effets d'entrée et observateurs après mise en jeu directe | semantic_batch_001_150 |
| Wandering Outcast | Soutiens admissibles ; décision après connaissance du ciblage et avant mutation | semantic_integration_followup |
| Colossus, Nullify, Wall off | Types de Volontés admissibles corrigés | semantic_batch_151_300, semantic_batch_301_450 |
| Trim, Equalize | Puissance fixée et refus des autres modificateurs, y compris tempérament et capacités | semantic_batch_151_300, semantic_integration_followup |
| Pin Down, Wretched Arena | Interdiction de mettre en jeu distincte de l'interdiction de jouer ; jetons inclus | semantic_batch_151_300, tenebro_replacement_audit |
| Hot Potato, Buddhan the Dark | Contrôleur et décompte conservés après départ de la source | semantic_batch_151_300 |
| Glabron, Grudge, Everspring, Hogma | Exclusions et restrictions non imprimées retirées | semantic_batch_151_300 |
| Unreachable Pillar, Piercing Lover | Effets du Vaisseau neutralisés aussi au calcul final | semantic_batch_151_300 |
| Zum | Modificateur sans expiration inventée | semantic_batch_151_300 |
| Duel Honorably | Paiement pendant la présence sur la Pile ; payeurs conformes à l'arbitrage ; choix de tribut subséquents conservés | stack_intrinsic_payment |
| Nullifying Radiance | Effet d'entrée unique : compteurs et choix de couleur | semantic_batch_151_300 |
| Karmapult | Sacrifice payé comme coût et mémorisé pour la résolution | semantic_batch_151_300 |
| Quper, Nameless Arcane | Remplacements respectés ; pas de bonus ou d'essence sans l'événement requis | semantic_batch_301_450 |
| Linoleus, Manymaws, Lilitha, Donmo | Sources, exclusions, tempéraments et cibles multiples | semantic_batch_301_450 |
| Caress, Induce Desertion | Contraintes de conteneur et cibles distinctes | semantic_batch_301_450, semantic_ui |
| Denblew | Un bonus par action distincte de pioche hors Récupération | semantic_batch_301_450, semantic_integration_followup |
| Referren-Doom, Pescojolero, Rally | Plafonds arbitraires retirés ; ressources et nombre de cibles réels | semantic_batch_301_450, semantic_integration_followup, semantic_ui |
| Timidette | Choix obligatoire d'au moins une cible admissible | semantic_batch_301_450 |
| Nghoul-ong | Permission liée à la Volonté éphémère choisie et à son instance au Limbo | semantic_batch_301_450, semantic_ui |
| Chabak | Choix d'ordre sous le Deck conservé pour chaque propriétaire | semantic_batch_001_150, semantic_batch_301_450 |
| Thoughtcutter, Gobres | Cartes réellement jouées et zone de déclenchement correcte | semantic_batch_301_450 |
| Punitive Tripod | Puissance fixée sans plafond non imprimé | semantic_batch_301_450 |
| Rah-kio | Jetons de l'Impasse exclus de la destruction du champ | semantic_batch_301_450 |
| Jodorosk | Volonté visible, gratuite, durable et correctement affichée | semantic_batch_301_450, semantic_ui |
| Temperamental Splendor | Exil sans Gem détecté hors activation ; initialisation d'entrée préservée | semantic_batch_301_450, semantic_integration_followup |
| Float / Sever | Ordre de résolution des modifications conservé | semantic_batch_301_450 |
| Timid Brain | Effet immédiat lançant le jeu réel en Soutien, sans permission différée | semantic_batch_001_150 |
| Tenebro | Remplacement avant Limbo, choix multiples atomiques, ordre avec BOB et confidentialité | tenebro_replacement_audit |

Les noms de modules correspondent aux fichiers `tests/test_<nom>.py` ou `.cjs`.

Les trois anciennes questions de règle ont un suivi distinct : Parasitic Drill
peut se lier à elle-même selon son texte ; Lunar Liturgy utilise l'arbitrage
individuel conservé dans `audit/rule-decisions.json`. Pour Drildrill, le
remboursement après une destruction remplacée est une interprétation des deux
instructions imprimées indépendantes, et non un nouvel arbitrage du créateur.
La régression BOB vérifie une suspension sans entrée au Limbo et exactement deux
essences vitreuses et deux capricieuses pour le contrôleur de la Volonté ciblée.

La revue documentée couvre 450 textes ; les oracles exécutés restent un ensemble
de scénarios ciblés. Les branches non exécutées, les interactions non couvertes,
l'identité visuelle des illustrations et les appareils physiques ne sont pas
certifiés par ce tableau.
