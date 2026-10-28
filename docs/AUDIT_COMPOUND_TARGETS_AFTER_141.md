# Résolution des effets composés et cibles invalidées

Ce lot vérifie 13 clauses sélectionnées, avec **112 scénarios de famille et
14 parcours WebSocket**. Les textes sont figés avec leur empreinte dans
`audit/compound-targets.json`. Les résultats attendus sont écrits par carte dans
`tests/test_compound_targets.py`, indépendamment des valeurs des capacités.

## Défaut reproduit et correction

Paciphint met d'abord une Manifestation alliée sous le Deck de son propriétaire.
Si ce déplacement réussit, il ignore ensuite la puissance de l'autre cible en CZ.
La deuxième instruction dépend de la première ; la première ne dépend pas de
la présence de la deuxième cible au moment de la résolution.

La revalidation conserve les positions des groupes et remplace une cible
invalide par un emplacement sans cible. Le gestionnaire de Paciphint filtrait
ensuite ces emplacements, ne trouvait plus deux cartes et abandonnait l'ensemble.
L'allié restait donc sur le terrain alors que son déplacement était encore légal.

La [reproduction avant correction](../reports/systematic-audit/compound-target-followup/before.json)
conserve 112 exécutions : **108 réussites et quatre échecs**, tous lorsque la
deuxième cible de Paciphint avait quitté le terrain, reçu Protection, rejoint
l'Impasse ou quitté puis regagné le terrain comme nouvelle instance.

Le correctif se limite au gestionnaire de Paciphint : il conserve les deux rôles,
exécute le déplacement de l'allié encore valide et applique l'ignorance de puissance
seulement si la deuxième cible est encore valide. Si l'allié est devenu invalide,
aucun déplacement ne réussit et aucune puissance n'est ignorée. Le marqueur Flower
payé à la déclaration reste consommé.

## Règles conservées et contrôles voisins

La règle déjà confirmée reste inchangée : si toutes les cibles choisies deviennent
invalides, l'effet entier échoue. Le retrait automatique d'une telle entrée de
pile utilise toujours le pipeline normal. Les cas sans cible ne sont pas assimilés
à une déclaration dont la cible a disparu.

| Carte | Résultat vérifié |
|---|---|
| Linoleus | Sans cible choisie : +5 points. Avec cible valide : +5 et +1 puissance. Cible choisie puis invalidée : l'effet entier échoue. |
| Tombloom | Cible valide : exil de Tombloom et −2 jusqu'à la fin du tour. Cible devenue invalide : aucune de ces instructions. |
| Incite to Sacrifice | +6 et mémoire d'exil à la victoire sur la cible valide ; aucun des deux si elle devient invalide. |
| Stormmace | +2 et Protection sur la Première Manifestation valide ; le sacrifice payé n'est pas remboursé si la cible devient invalide. |
| Kaos Bro | Un dé par cible restante valide ; sur un résultat de 1, destruction de cette seule carte. |
| Karma Bro | Un dé par cible restante valide ; sur un résultat de 1, +10 points par réussite. |
| Shattering the Self | Le joueur encore ciblable défausse trois cartes même si la Manifestation est devenue invalide ; le malus n'atteint aucune cible illégale. |
| Paciphint | Le déplacement de l'allié valide reste exécuté si seule la deuxième cible devient invalide. L'étape suivante exige le déplacement réussi et sa propre cible valide. |
| Hyperuranic Tower | Le transfert d'un marqueur Abstraction exige ses deux cibles ; aucun demi-transfert. |
| Dominate the Aspects | Échange complet et deux mémoires seulement avec deux cibles valides ; aucun demi-échange. |
| Invert Emotions | Deux Manifestations d'Interzone valides requises pour échanger leurs contrôleurs. |
| Induce Desertion | Les deux cibles et leur relation restent requises pour calculer le malus ; aucun calcul à partir d'une cible invalidée. |
| Multicastigate | Chaque Support encore valide est détruit ; une cible perdue ne sauve pas l'autre et ne rembourse pas le coût supplémentaire. |

Les scénarios couvrent la résolution normale, toutes les cibles devenues invalides,
et chaque position de carte invalidée séparément par départ, Protection, Impasse
ou sortie/rentrée. La déclaration et les coûts consignés ne sont pas réécrits.
Les modificateurs ne sont pas attachés aux anciennes cibles invalides. Les effets
volontaires passent par la déclaration et les paiements réels ; les déclenchements
emploient la file de production avec des événements explicitement préparés.

Psychowall rend à la fois l'adversaire et ses cartes Immunes : ce cas fait échouer
les deux cibles de Shattering. Le banc n'invente pas un joueur adverse Immunisé
dont la Manifestation resterait légale sous cette même aura.

Quatorze parcours réseau couvrent une cible invalidée par carte, et les deux
positions de Paciphint. Les effets joués ou activés utilisent une déclaration
WebSocket réelle ; les déclenchements sont préparés explicitement. Après les
passes de priorité, un client incrémental et un client ancien doivent recevoir
la résolution de l'identifiant précis de l'action et les bons scores. Le résultat
du moteur est ensuite contrôlé avec les mêmes attentes indépendantes.

## Preuves, compteur et limites

Les [preuves par clause](../reports/systematic-audit/compound-target-followup/clauses.json)
et le [registre d'exécution](../reports/systematic-audit/compound-target-followup/EXECUTIONS.md)
conservent les identifiants des tests et les empreintes des sources.

Neuf cartes s'ajoutent au registre strict : Stormmace, Kaos Bro, Karma Bro,
Shattering the Self, Paciphint, Hyperuranic Tower, Dominate the Aspects,
Invert Emotions et Multicastigate. Linoleus, Tombloom, Incite et Induce y figuraient
déjà. Le [compteur](../reports/systematic-audit/coverage-status.json) atteint donc
**109/450, soit 24,2 %**, avec au moins une clause vérifiée par carte. Il ne
certifie pas toutes leurs capacités ou interactions.

Les premiers ajustements des attentes de couleur, de la préparation Psychowall
et d'une référence d'action copiée dans le banc réseau ne sont pas présentés
comme des défauts du jeu. La reproduction conservée précède le correctif moteur
et emploie les préparations corrigées. Une première campagne devenue périmée
après l'ajustement du banc réseau a été arrêtée, puis la validation relancée.

Ce lot ne certifie pas le moment du choix de l'allié de Paciphint, les remplacements
de son déplacement, les jetons comme donneurs ou les cartes attachées. Les dés des
Bro sont fixés à 1 ; les autres résultats restent des cas distincts. Scrambling
Beacon et les autres gestionnaires composés ne sont pas certifiés par analogie.
Le pilote automatique des phases est isolé dans ces parcours réseau ; ses contrôles
existants restent dans la suite complète. Aucun nouveau parcours UI de carte,
Safari, appareil physique ou illustration distante n'est certifié ici.

Les corrections locales antérieures sont conservées. Aucun changement de VFX,
fichier client, version, commit ou push.
