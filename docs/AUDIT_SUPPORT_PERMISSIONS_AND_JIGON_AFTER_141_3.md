# Lot élargi : permissions Support et Jigon

Tout reste local après la version publiée 141.3, sans push ni changement de version.

## Jigon : défaut reproduit et correction

Une Volonté Éphémère cachée par Jigon, dotée d'une capacité jouée encodée, était refusée par `rules_action_ability` avec « This source Manifestation has lost its effects ». La vérification exigeait que les effets de son objet de terrain soient actifs. Or une carte face cachée n'a pas d'effets actifs sur le terrain : jouer la Volonté et activer une capacité du terrain sont deux opérations distinctes.

Le contrôle accepte maintenant le jeu d'une source autorisée `concealedWill`, comme il acceptait déjà `revealedFreeWill`. Il continue à refuser l'activation d'une Manifestation privée de ses effets. Les validations de provenance, contrôle, timing, cible et paiement restent exécutées.

L'ancien test de Jigon utilisait Hermetic Hourglass. Cette Volonté Persistante ne possède pas de capacité jouée encodée et évitait le contrôle fautif. Les nouveaux cas emploient Renforcer / Strengthen : coût imprimé {H}, puissance d'une cible de 1 à 4 seulement à la résolution, puis Volonté au Limbo.

Les tests exercent la recherche depuis le Deck, le mélange, la création réelle de la Volonté cachée, le déclenchement de défaite de Jigon et le jeu gratuit qui en résulte. Une victoire ne débloque pas la gratuité ; une autre Volonté liée à un autre Jigon n'est pas libérée. Le coût normal reste exigé avant la défaite. L'interaction Tebebe conserve son coût de trois essences {H}.

## Couverture regroupée : 39 cartes Support

Les oracles sont relus depuis le texte imprimé et épinglés dans `audit/support-permissions.json`, indépendamment des flags du moteur. Le même banc exécute pour chaque carte : jeu depuis la main, entrée depuis l'Interzone, permission depuis l'Impasse, mauvaise phase, absence de priorité, contrôle adverse, perte d'effets, verrouillage des Supports, seconde déclaration depuis la main et restriction de Première Manifestation. Le contrôle d'une carte possédée par l'adversaire est distinct de sa propriété. Les cartes autorisées depuis l'Interzone vérifient aussi le refus d'une seconde déclaration pendant leur déplacement.

Le jeu depuis la main passe par la pile, ne crée rien sur le terrain avant la résolution et ne demande aucun tribut. Une carte venant de l'Interzone reste visible à sa position d'origine jusqu'à la résolution, puis son entrée en Support est enregistrée une seule fois. Les refus vérifient que l'état n'a pas changé. Nubilung possède une permission supplémentaire depuis l'Impasse, prise en compte dans sa fixture.

Les cibles d'entrée requises et les capacités permettant de choisir un contrôleur sont fournies par les fixtures. Les effets particuliers des cartes restent sur la pile après leur entrée et ne sont pas certifiés par les assertions Support. Le texte complet de chaque carte est épinglé, mais seules les clauses « Support », « Support from hand » et, lorsqu'elle existe, « Cannot be played as First Manifestation » sont ajoutées au registre pour ces 39 cartes.

| Carte | Clause Support | Depuis l'Interzone | Première Manifestation autorisée |
| --- | --- | --- | --- |
| Wind Sprout | Support from hand. | Non | Non |
| World Spore | Support from hand. | Non | Oui |
| First Stone | Support from hand. | Non | Non |
| Concealed Manta | Support from hand. | Non | Non |
| Chitinous Repeller | Support from hand. | Non | Non |
| Little Abhorrence | Support from hand. | Non | Non |
| Possessed Pyramid | Support from hand. | Non | Oui |
| Lament, Thought-nullifier | Support from hand. | Non | Non |
| Auriwings | Support from hand. | Non | Non |
| Yzzit, the Gambler | Support from hand. | Non | Non |
| Unpredictable Loudmouth | Support from hand. | Non | Oui |
| Candle Serpent | Support from hand. | Non | Non |
| Ononok, Chaotic Scatterer | Support from hand. | Non | Oui |
| Chobariki, of the Shiny Muscles | Support from hand. | Non | Non |
| Mamelath, the Polymancer | Support from hand. | Non | Non |
| Timidette, the Elusive | Support from hand. | Non | Non |
| Bakato, the Obsessive | Support from hand. | Non | Non |
| Manymaws | Support from hand. | Non | Non |
| Jesterina, the Decadent | Support from hand. | Non | Non |
| Ozzit, the Unwary | Support from hand. | Non | Non |
| Nubilung, the Elder | Support from hand. | Non | Non |
| Pegasso | Support from hand. | Non | Non |
| Phalanx Tower | Support from hand. | Non | Non |
| Bibi, the Confused | Support from hand. | Non | Non |
| Drildrill | Support from hand. | Non | Oui |
| Merciful Pago | Support. | Oui | Oui |
| Sprawling Tentacle | Support. | Oui | Non |
| Forest Guide | Support. | Oui | Oui |
| Absent Trinket | Support. | Oui | Oui |
| Cimba, the Boisterous | Support. | Oui | Non |
| Tigrolione | Support. | Oui | Oui |
| Skapus, the Vile | Support. | Oui | Non |
| Granite Mass | Support. | Oui | Non |
| Worn Old Shape | Support. | Oui | Non |
| Hogma, the Petty | Support. | Oui | Oui |
| Buuz, the Helicoidal | Support. | Oui | Non |
| Manibirbo | Support. | Oui | Non |
| Nameless Arcane | Support. | Oui | Oui |
| Jeovak, the Illusory | Support. | Oui | Non |

## Validation et méthode

- **463 cas ciblés passent** : 443 tests Support, dix tests Jigon et frontières de permission, deux tests de sensibilité des oracles et huit parcours à deux connexions WebSocket.
- **69 clauses sélectionnées pour 40 cartes** : 39 cartes Support et Jigon. Ce sont 40 cartes supplémentaires au registre après la régression complète passante.
- Les six parcours réseau Support représentent main simple, Interzone, choix de contrôleur, cible d'entrée, génération ultérieure de jetons et exception depuis l'Impasse. Les deux autres vérifient Jigon payant et gratuit. Les deux clients utilisent des formats de synchronisation différents.
- **91 tests voisins passent**, notamment Loop/Jigon, choix, copies, paiements, Support et Tebebe.
- **608 scénarios de parité client/serveur passent**.
- Les tests de sensibilité modifient volontairement les permissions encodées de Wind Sprout et Forest Guide, et vérifient que les attentes indépendantes détectent ces défauts.

Le lanceur `tools/card_support_permissions_audit.py --units <preuve complète courante>` peut assembler les clauses à partir des identifiants et résultats déjà exécutés dans la suite générale. Il vérifie le digest et la liste attendue des tests, sans relancer les mêmes parcours seulement pour produire le rapport. Le mode sans argument exécute toujours le lot ciblé pendant les corrections. Une seule régression générale est lancée après stabilisation de ce lot de 40 cartes.

Les premières erreurs du banc sont conservées et distinguées des défauts : 14 refus de déclaration dus aux cibles ou capacités de contrôleur omises pour sept cartes Support ; mauvais coût attendu pour Strengthen avant lecture de son coût imprimé {H} ; deux erreurs réseau dues aux coordonnées/rotation absentes des fixtures unitaires. Ces cas ne sont pas des défauts supplémentaires du moteur. `jigon-before.json` conserve la reproduction du vrai refus « lost its effects » dans trois des six premiers tests.

## Limites

Les autres paragraphes des cartes Support et toutes leurs interactions ne sont pas certifiés. Les états initiaux, les adversaires et les résultats de confrontation servant au déclenchement sont contrôlés. L'avance automatique des phases est désactivée dans les huit parcours réseau pour isoler permissions et pile. Ce lot n'ajoute aucune certification de rendu navigateur, d'illustration distante, de téléphone ou de Safari réel.

Validation finale : **3788/3788 tests Python passent**, aucun échec ni test ignoré, en 636,285 secondes. Une seule suite générale a été exécutée pour ce lot. Le mode `--units` du lanceur a ensuite assemblé les preuves à partir de cette exécution, sans relancer les tests. Les 463 cas ciblés, les résultats généraux et le registre partagent le même digest courant.

Le registre strict atteint **188/450 cartes (41,8 %)**, soit 40 nouvelles cartes avec clauses sélectionnées prouvées et 262 hors registre. Cela ne certifie pas tous les paragraphes ou toutes les interactions des 188 cartes. **Aucun push.**
