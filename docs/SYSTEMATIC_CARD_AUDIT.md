# Vérification systématique des cartes et de l'interface

Cette campagne complète les audits ciblés. Elle conserve les preuves par couche
et rend les lacunes visibles. « 450 cartes chargées » ne signifie jamais
« 450 textes intégralement certifiés ».

## Passe sémantique des résultats chiffrés

`python tools/card_numeric_audit.py` exécute le lot des puissances, points,
décomptes et portées. Les attentes sont écrites dans
`tests/test_quantitative_card_audit.py` à partir du texte imprimé et des décisions
du créateur, indépendamment des valeurs encodées des capacités.
`reports/systematic-audit/NUMERIC.md` et `numeric.json` conservent le texte de
chaque carte concernée, son empreinte et les identifiants des tests exécutés.

Ce lot porte sur certaines clauses de 24 cartes, avec Mimer et Entrust comme
interactions supplémentaires. Il ne certifie pas toutes leurs branches ni les
moments de déclenchement des effets isolés. La campagne générale antérieure
reste historique après une modification des sources ; le lot ciblé ne rafraîchit
pas ses preuves de navigateurs, matrice et séquences.

## Passe des départs de source, des cibles et des mémoires

`python tools/card_departure_audit.py` exécute les régressions de départ et trois
parcours WebSocket avec reconnexion. Les résultats et limites figurent dans
`reports/systematic-audit/DEPARTURES.md` et `departure.json`.

Les deux arbitrages du créateur sont appliqués et conservés dans
`audit/rule-decisions.json` : une source absente utilise ses valeurs imprimées,
et une carte revenue au Limbo est une nouvelle entrée qui invalide son ancien
ciblage. Le lot est clos pour les cas décrits dans son rapport ; cela ne certifie
pas toutes les interactions du catalogue. `departure-observations.json` conserve
les observations historiques antérieures aux réponses et aux correctifs.

## Références courantes et totaux d'Impasse

`python tools/card_first_reference_audit.py` vérifie le remplacement d'une
Première Manifestation partie par la suivante dans l'ordre d'entrée en CZ.
L'absence de toute Manifestation adverse vaut zéro pour les calculs de
Lombriculpop et Armored Pachywyrm, selon l'arbitrage du créateur. Le lot rejoue
aussi les régressions des départs et quatre contrôles navigateur ciblés.
Les résultats et limites sont dans `reports/systematic-audit/FIRST_REFERENCES.md`
et `first-reference.json` ; la suite Python complète conserve sa preuve séparée
dans `unit-tests.json`. Les totaux d'Impasse sont vérifiés par propriétaire,
depuis les deux sièges et comme observateur, sur PC et mobile paysage.

## Commande complète

```powershell
python tools/run_card_audit.py
```

Prérequis : les dépendances Python des tests, Playwright et Chrome, ainsi que les
fixtures de la sandbox locale déjà utilisées par `card_scenario_batches.py`.
La sandbox reste exclue de la publication. Le banc n'ajoute aucune commande de
test au serveur de production et n'active aucun contournement dans le client.

Le lancement ne change ni Git, ni la version du jeu. Il écrit ses preuves dans
`reports/systematic-audit/` et quitte avec un code non nul en cas d'échec.

## Sources et fiches

- Texte anglais du catalogue, conservé intégralement et avec son empreinte pour
  chaque carte ; les arbitrages et errata priment en cas de différence.
- `audit/rule-decisions.json` : arbitrages explicites du créateur, séparés des
  capacités encodées. Les références de tests sont validées.
- Métadonnées compilées : implementation examinée, jamais oracle de son propre
  comportement.
- `reports/systematic-audit/cards/` : une fiche par carte avec clauses, capacités,
  mécaniques, matrice et limites. `matrix.json` contient les données détaillées.

Les trois revues dans `audit/semantic-reviews/` couvrent les textes des 450
cartes et leurs 760 paragraphes imprimés, avec attentes, branches et exemples
indépendants des capacités encodées. `tools/card_semantic_audit.py` vérifie les
identifiants, positions, textes, empreintes et paragraphes de ces fiches.
Cette validation documentaire ne certifie pas l'exécution de chaque clause.
Les statuts historiques et les mentions de cartes dans les tests sont conservés
séparément des résultats effectifs. Les compléments et leurs limites figurent
dans `reports/systematic-audit/SEMANTIC_REVIEW.md` et `SEMANTIC_FIXES.md`.

## Couches exécutées

1. **Matrice des capacités** : chemin normal et refus atomiques pour priorité,
   fin de partie, choix/Immédiat en cours, source absente, cible manquante ou
   protégée, mauvaise phase et ressources indisponibles. Les chemins spéciaux,
   capacités déclenchées et effets permanents restent identifiés séparément.
2. **Mécaniques partagées** : suite Python complète, avec identifiant et résultat
   de chaque test. Le rapport relie les familles et arbitrages aux modules
   effectivement exécutés. Un module réussi ne certifie pas toutes les cartes
   qui le citent.
3. **Deux joueurs réels** : deux contextes Chrome indépendants, pages et sockets
   du jeu. Les 450 cartes sont rendues, les 182 actions volontaires empruntent les
   commandes et gestionnaires du client, puis les choix/Pile sont poursuivis.
   Aucun remplacement de `send` ni injection de `latestState`. Les caractères
   synthétiques des cibles de fixture sont seuls ajoutés au catalogue du client.
4. **Interaction réelle** : pointeur pour les distributions de deck, choix privé
   de Suspend après reconnexion, réponse répétée et confidentialité, sur PC et
   mobile paysage. Les événements DOM et appels de gestionnaires utilisés pour
   la couverture large sont distingués des gestes physiques.
5. **Séquences reproductibles** : graines fixes, transferts/suspensions pour les
   450 cartes, puis séquences de Pile/coût/Weaken/Oppress/Cleanse/expiration avec
   oracle chiffré issu des textes. Conservation des cartes et propriétaires,
   essences non négatives, refus atomiques et confidentialité sont vérifiés à
   chaque étape. Le préfixe jusqu'au premier échec est conservé.
6. **Régressions UI** : parité client/serveur, paiements blancs, gestes, connexion,
   choix, espace de la main, Ponderer, rareté et VFX, rendu général.

Les fixtures du serveur de test sont pilotées uniquement par l'entrée standard
de son processus parent. Le port du jeu est local et temporaire. Les connexions
des joueurs conservent le protocole et les contrôles d'autorisation normaux.

Les requêtes vers les illustrations distantes sont bloquées dans le banc de
jeu local. Un contrôle séparé, `node tools/card_art_audit.mjs`, charge réellement
les 450 URLs et vérifie HTTP, type de contenu, décodage, dimensions et empreintes
des images sans substitution. `remote-art.json` garde cette preuve et les
empreintes de ses entrées ; il ne certifie pas l'identité artistique par examen
visuel. Les gestes tactiles sont synthétisés dans Chrome. Les essais sur
téléphone physique seront réalisés par le créateur, selon son choix ; aucun
appareil physique ni Safari iOS n'est certifié ici.

## Rejouer une couche

```powershell
python tools/card_behavior_audit.py --execute --write
python tools/card_behavior_audit.py --check
python tools/card_audit_traces.py --seed 42
python tools/run_card_audit.py --units-only
node tools/card_audit_browser.mjs
python tools/run_card_audit.py --ui-only
node tools/card_art_audit.mjs
python tools/card_semantic_audit.py --write --unit-tests reports/systematic-audit/unit-tests.json --remote-art reports/systematic-audit/remote-art.json
python tools/run_card_audit.py --report-only
```

`--report-only` refuse une preuve absente, périmée ou un parcours navigateur
partiel. L'empreinte couvre moteur, client, styles, textes, arbitrages, fixtures
et tests : modifier un de ces éléments impose de relancer les couches.

Pour diagnostiquer : `node tools/card_audit_browser.mjs --focus=inner-deserts-127`.
Ce lancement écrit `browser-debug.json` et ne remplace jamais la preuve complète.

## Lire les résultats

Ouvrir `reports/systematic-audit/EXECUTIONS.md`, puis les fiches concernées.
Les statuts `carrier-only`, `dedicated-path`, `needs-family-scenario` et
`independent-scenario-review-required` désignent une limite, pas une réussite.
Les résultats chiffrés et conditions propres à chaque texte demandent des
scénarios indépendants : les parcours UI prouvent le transport, les choix et la
terminaison, sans prouver à eux seuls la conformité complète de chaque effet.

Après chaque bug confirmé : reproduire avec une graine/scénario, écrire l'attente
depuis le texte ou l'arbitrage, corriger la couche responsable, puis rejouer la
famille et cette campagne. Ajouter progressivement les branches alternatives
et interactions au lieu de masquer les cases non couvertes.

## Suite publiée en version 140.1

Le [suivi Grimoire et pile](AUDIT_GRIMOIRE_STACK_AFTER_140.md) décrit les nouvelles
branches vérifiées, les corrections d'interface et le signalement Sermon/Tong
qui reste à reproduire. Les [notes de version](RELEASE_140_1.md) résument les
corrections publiées. Les résultats complets de
matrice, traces et parcours des 450 cartes de la version 140 restent historiques ;
les nouvelles preuves Python et UI portent leur propre empreinte de source.

## Suite locale sur la latence et les reconnexions

L'[audit des séquences réseau](AUDIT_LATENCY_AFTER_140_1.md) ajoute dix scénarios
à deux connexions et corrige les commandes périmées ainsi que l'avance
automatique consécutive à un simple refus. Les preuves locales sont séparées
dans `reports/systematic-audit/latency-followup/` ; la publication 140.1 n'est
pas modifiée par ces nouveaux résultats.

## Suite locale des clauses de Soutien

L'[audit des clauses et interactions de Soutien](AUDIT_SUPPORT_CLAUSES_AFTER_140_1.md)
ajoute 26 méthodes avec des attentes explicites pour 15 paragraphes de 12 cartes.
Il corrige les déclenchements omis après certaines mises en Soutien, la pioche de
Mazzolong après le jeu spécial de Chabak et le contournement de Pin Down par cinq
mises en jeu déjà en attente. Les associations de clauses et leurs résultats
sont conservés dans `reports/systematic-audit/support-followup/clauses.json`.
Les branches absentes de ce registre ne sont pas déclarées couvertes.

La campagne générale a été rejouée sur ces sources : 1 270 tests Python, 13 suites
UI, 450 rendus et 182 actions navigateur, 40 traces / 12 175 étapes, ainsi que la
matrice complète et les 450 illustrations distantes, sans échec. Le
[rapport courant et ses limites](../reports/systematic-audit/support-followup/EXECUTIONS.md)
conserve cette preuve séparément des campagnes historiques. La couverture
sémantique de chaque clause et de toutes ses branches reste incomplète.

## Suite locale des enchaînements et de leurs conséquences

L'[audit des conséquences d'Enchaînement](AUDIT_CHAIN_OUTCOMES_AFTER_140_1.md)
ajoute 31 tests, dont deux scénarios réseau, pour 15 paragraphes sélectionnés de
huit cartes. Il corrige les destinations et mémoires d'Urocione, le mélange de
Lady of the Humps quand Chain n'aboutit pas, les interdictions de Chain et la
mémoire du Vaisseau d'origine de Dol. Les preuves explicites sont dans
`reports/systematic-audit/chain-outcomes-followup/clauses.json`.
Les preuves générales de la passe Soutien précédente restent historiques ; les
branches non associées à des assertions ne deviennent pas couvertes par ce lot.

La preuve finale de cette passe comprend 1 301 tests Python sans échec ni test
ignoré et quatre suites UI ciblées réussies. Le
[rapport des enchaînements](../reports/systematic-audit/chain-outcomes-followup/EXECUTIONS.md)
distingue ces exécutions actuelles des campagnes générales précédentes.

## Suite locale WebKit, distribution et jetons

L'[audit de pile WebKit et de clauses chiffrées](AUDIT_STACK_WEBKIT_AND_DISTRIBUTION_AFTER_140_1.md)
ajoute 24 scénarios de pile dans Chrome/WebKit et 19 tests de branches pour
Echo of the Wilds et Stampeding Brood. Le défaut signalé dans la pile sur Safari
Mac reste non reproduit : WebKit Windows ne certifie pas ce navigateur réel.
Les preuves nouvelles sont séparées dans `safari-stack-followup/` et
`distribution-token-followup/`. Aucun correctif spéculatif ni publication.

## Suite locale des recherches et déclarations de noms

L'[audit des recherches de Deck](AUDIT_DECK_SEARCH_AFTER_140_1.md) ajoute 25 tests
de clauses pour Hermeto, Recall, Mejik et Poopom, dont deux scénarios réseau.
Il corrige la révélation omise après recherche et le nom de Mejik choisi trop
tard. Six configurations navigateur couvrent les choix et journaux dans trois
langues sur PC et mobile paysage. Les preuves, les échecs avant correction et
les limites sont conservés dans `reports/systematic-audit/deck-search-followup/`.

## Suite locale du passage automatique et des phases

L'[audit de l'auto-skip et des phases](AUDIT_AUTO_PHASES_AFTER_140_1.md) ajoute
19 tests et rejoue 59 scénarios ciblés. Il corrige l'arrêt des longues piles à
la limite de 60 opérations ainsi que la reprise des phases vides lorsque la
dernière carte tombe exactement sur cette limite. Il ajoute un garde-fou pour
les états manuels/inactifs et vérifie les choix, les réponses, les quinze étapes
et la publication de chaque résolution. Les preuves avant/après sont dans
`reports/systematic-audit/auto-phase-followup/`.

## Suite locale des retours en main et interdictions de rejouer

L'[audit des retours et du rejeu](AUDIT_BOUNCE_REPLAY_AFTER_140_1.md) ajoute
24 méthodes pour six paragraphes sélectionnés de Pigon, Chiff and Chaff,
Atavic Introspection et Abandon. Il ferme le contournement du verrou par
déclaration sur la pile, aligne la disponibilité pour le passage automatique
et limite le déclenchement de Chiff à sa propre entrée en Soutien. Deux
scénarios réseau vérifient la reconnexion et les copies identiques.
Les preuves avant/après et leurs limites sont séparées dans
`reports/systematic-audit/bounce-replay-followup/`.

## Publication 140.2

Les suites locales depuis 140.1 sont intégrées à la
[version 140.2](RELEASE_140_2.md). La validation de publication rejoue
1 388 tests Python et 14 suites UI, tous réussis, avec les versions du client
et du service worker synchronisées. Les preuves de publication sont séparées
dans `reports/systematic-audit/release-140-2/` ; les empreintes des campagnes
précédentes restent historiques et ne certifient pas toutes les branches.

## Publication 140.3 et suite locale des Atavic

La [version 140.3](RELEASE_140_3.md) publie le réglage visible de création et le
transport incrémental. Les preuves de publication sont séparées dans
`reports/systematic-audit/release-140-3/` ; les comparaisons de trafic restent
des fixtures locales, sans prévision de facture Render.

La [passe Atavic suivante](AUDIT_ATAVIC_END_AFTER_140_3.md) ajoute 22 méthodes
pour cinq paragraphes sélectionnés de deux cartes, dont deux parcours réseau.
Elle corrige la pioche trop précoce d'Atavic Oppression et le choix de Kanon
écrasé. Les branches de marqueurs, refus, seuils et choix de fin de tour sont
documentées dans `reports/systematic-audit/atavic-end-followup/`.

L'[arbitrage de ciblage d'Introspection](AUDIT_ATAVIC_LIMBO_AFTER_140_3.md)
autorise deux cartes dans un seul des deux Limbos et confirme le Deck du
propriétaire comme destination. Neuf nouvelles méthodes et six configurations
navigateur complètent cette branche. Les preuves sont séparées dans
`reports/systematic-audit/atavic-limbo-followup/` ; les autres branches non
exécutées ne sont pas déclarées couvertes.

## Publication 140.31 et suite locale des défausses/pioches

La [version 140.31](RELEASE_140_31.md) publie ces corrections Atavic. La
[passe suivante](AUDIT_DISCARD_DRAW_AFTER_140_31.md) ajoute 24 méthodes pour
trois paragraphes sélectionnés de Pray the Ether, Alchemical Press et
Martyrize. Elle corrige les pioches qui contournaient les restrictions ou
Kanon, ainsi que les offres impossibles de Press sous immunité de Main.
Deux parcours réseau vérifient les choix après reconnexion et les quantités
exactes. Les preuves avant/après sont séparées dans
`reports/systematic-audit/discard-draw-followup/`. Cette suite reste locale,
sans nouvelle publication et sans modification des VFX.

L'[audit des événements de Kanon](AUDIT_KANON_EVENTS_AFTER_140_31.md) ajoute
25 méthodes pour neuf paragraphes sélectionnés de huit cartes. Il corrige
les événements de pioche/défausse omis, les remplacements contournés, l'ordre
défausse puis pioche et la sélection d'exemplaires identiques. Deux parcours
réseau et six configurations du sélecteur navigateur complètent les preuves
dans `reports/systematic-audit/kanon-events-followup/`. Les événements multiples
ou retardés de Gorlok restent une branche distincte à auditer.

La [passe Gorlok](AUDIT_GORLOK_DRAW_AFTER_140_31.md) étend ensuite ce même
paragraphe avec 26 méthodes, dont trois parcours réseau. Elle sépare les groupes
de pioche retardés, suit les exemplaires en Main, conserve l'effet après le
départ de la source et corrige le libellé d'exil. Six configurations navigateur
vérifient le choix. Les preuves sont dans
`reports/systematic-audit/gorlok-draw-followup/` ; ce paragraphe déjà sélectionné
dans le lot Kanon n'est pas compté une seconde fois comme une nouvelle clause.

La [passe Traumatize/Womb](AUDIT_PRIVATE_HAND_AFTER_140_31.md) ajoute 23 méthodes,
dont trois parcours réseau, pour leurs deux paragraphes imprimés. Elle corrige
les remplacements et immunités contournés, les exemplaires sélectionnés, le
déclenchement de Womb en Réaction et la confidentialité des choix/journaux.
Six configurations navigateur vérifient douze scénarios de sélection. Ces quatre
lots locaux sont intégrés à la [publication 140.32](RELEASE_140_32.md), avec une
validation séparée dans `reports/systematic-audit/release-140-32/`. Les autres
sélecteurs et les combinaisons non exécutées restent à couvrir.

## Suite locale après 141 : Vaisseau et Interzone

La [passe des choix du Vaisseau](AUDIT_VESSEL_CHOICES_AFTER_141.md) ajoute
28 méthodes, dont trois parcours WebSocket, pour trois paragraphes sélectionnés
de Gummo, Wish Upon the Stars et Pescojolero. Elle distingue les exemplaires,
refuse les anciennes entrées et les réponses invalides, conserve les remplacements
des retours de Wish et rétablit les effets d'entrée des cartes amenées en
Interzone. Six configurations Chrome vérifient 18 scénarios de sélecteur.
Les preuves sont séparées dans `reports/systematic-audit/vessel-choice-followup/`.
Ce lot reste local, sans publication ni modification des VFX. Ses limites et les
corrections de préparation des premiers tests sont explicites dans le rapport.

La [passe Bloatuba/Ponderer](AUDIT_DECK_SEQUENCES_AFTER_141.md) ajoute ensuite
26 méthodes, dont trois parcours réseau, pour leurs deux paragraphes sélectionnés.
Elle corrige les doublons des répartitions, les positions retirées par Bloatuba,
les choix périmés, la suspension de ses sorties du Deck et les métadonnées
effacées par un simple changement d'ordre. Dissect sert d'interaction au
répartiteur commun, sans certification supplémentaire de toute sa carte.
Six configurations Chrome rejouent 18 scénarios. Les preuves sont séparées dans
`reports/systematic-audit/deck-sequence-followup/`. La limite du suivi par
identifiant/version du Deck est documentée ; le lot reste local, sans push.

## Couverture par familles d'effets

Le [premier banc par familles](AUDIT_EFFECT_FAMILIES_AFTER_141.md) vérifie en lot
23 clauses de puissance de 21 cartes, avec des attentes manuelles indépendantes
des capacités du moteur. Il exécute 291 scénarios de famille, onze parcours
WebSocket et cinq contrôles du banc. Les contrats et les résultats sont reliés
par effet ; une capacité candidate sans contrat n'est pas déclarée couverte.
Les preuves sont dans `reports/systematic-audit/power-family-followup/`.

Le [compteur strict](../reports/systematic-audit/coverage-status.json) déduplique
les cartes des lots numériques et des lots à clauses explicites, en exigeant
que tous leurs tests liés aient réussi dans la suite complète courante. La
commande `tools/card_coverage_status.py --units <preuve complète> --write`
refuse une preuve périmée ou échouée. Ce compteur ne transforme pas la couverture
de clauses sélectionnées en certification exhaustive de cartes.

Le [deuxième lot, consacré aux points](AUDIT_POINT_FAMILY_AFTER_141.md), vérifie
23 effets fixes de 19 cartes : destinataire exact, scores négatifs, blocages,
conditions de déclenchement et redirections de Balance. Ses 292 méthodes
comprennent 285 scénarios de famille, six parcours WebSocket et un contrôle
des attentes. Seize scénarios emploient des producteurs réels d'événements ;
Cannon et Zam-za ajoutent deux scénarios avec paiement et choix d'ordre sur
la pile. Les parties non liées aux points des effets composés restent
explicitement hors de ces preuves lorsqu'elles ne sont pas testées.
Treize cartes s'ajoutent au registre, qui atteint 100/450 (22,2 %) avec au
moins une clause sélectionnée vérifiée. Les preuves sont séparées dans
`reports/systematic-audit/score-family-followup/`. Aucun push ni changement VFX.

Le [troisième lot, consacré aux points proportionnels](AUDIT_SCALED_POINTS_AFTER_141.md),
renforce ensuite six clauses déjà comptées : Floating Dancer, Plea, Agrupol,
Donmo, Lombriculpop et Armored Pachywyrm. Il ajoute 113 scénarios de famille,
six parcours WebSocket et un contrôle des coefficients attendus. Les changements
du décompte avant résolution, jetons/copies, propriétaire/contrôleur, orientations
d'épuisement et remplacements de Première Manifestation ont leurs cas propres.
Le compteur reste à 100/450 : cette passe ajoute des branches vérifiées,
sans compter deux fois les mêmes cartes. Les preuves sont séparées dans
`reports/systematic-audit/scaled-score-followup/`. Aucun push ni changement VFX.

Le [lot des effets composés et cibles invalidées](AUDIT_COMPOUND_TARGETS_AFTER_141.md)
ajoute 112 scénarios et 14 parcours WebSocket pour 13 clauses sélectionnées.
Il corrige Paciphint : perdre sa deuxième cible ne doit pas supprimer le
déplacement encore légal de l'allié sous son Deck. Les échanges et transferts
qui exigent deux cibles restent complets ou sans effet ; toutes les cibles
choisies invalidées continuent de faire échouer l'effet entier. La reproduction
conserve quatre échecs avant correction. Neuf cartes s'ajoutent au registre
strict, qui atteint 109/450 (24,2 %), avec au moins une clause vérifiée par carte.
Les preuves sont dans `reports/systematic-audit/compound-target-followup/`.
Aucun push ni changement VFX.

Le [lot des pioches et défausses fixes](AUDIT_DRAW_DISCARD_FAMILY_AFTER_141.md)
vérifie ensuite 15 clauses de 13 cartes, avec 162 scénarios et 16 parcours
WebSocket. Il corrige les défausses choisies de Main qui contournaient la
suspension de BOB et le choix d'ordre BOB/exil. La reproduction conserve dix
échecs avant correction. Les quantités, doublons, ressources limitées,
blocages, immunités, acteurs de choix et remplacements sont vérifiés selon
leur applicabilité. Neuf cartes s'ajoutent au registre strict : 118/450
(26,2 %), avec au moins une clause sélectionnée vérifiée par carte. Les preuves
sont dans `reports/systematic-audit/draw-family-followup/`. Aucun push ni VFX modifié.

Le [lot des mélanges de Main suivis de pioche](AUDIT_SHUFFLE_DRAW_AFTER_141.md)
vérifie Deny Fate et Pontificate Heresy : 37 scénarios et cinq parcours WebSocket,
avec reconnexion et contrôles de confidentialité. Il corrige les contournements
de Kanon, des blocages de pioche et de Purifying Ritual, l'ordre mélange/pioche
des deux joueurs, les événements de pioche groupés et le résultat privé de
Deny Fate. Dix échecs sont conservés avant correction. Les choix consécutifs de
Kanon doivent être terminés avant la pioche restante. Les preuves sont dans
`reports/systematic-audit/shuffle-draw-followup/`. Les suites conditionnelles
« si vous le faites » restent distinctes et attendent une précision de règle.
Aucun push ni changement VFX.

La [passe des défausses remplacées suivies de pioche](AUDIT_CONDITIONAL_DISCARD_AFTER_141.md)
ferme ensuite ces précisions : Suspension ou Exil ne suppriment pas la condition
de défausse accomplie ; l'errata Bêta de Press impose défausse puis pioche.
Les règles sont enregistrées dans `audit/rule-decisions.json`. Le comportement
actuel respecte déjà ces branches. Les 70 scénarios et six parcours WebSocket
renforcent deux cartes déjà comptées, sans nouvelle correction du moteur ni
incrément artificiel du nombre de cartes. Les preuves sont séparées dans
`reports/systematic-audit/conditional-discard-followup/`. Aucun push ni VFX modifié.

La [passe des observateurs de défausse](AUDIT_DISCARD_OBSERVERS_AFTER_141.md)
vérifie huit clauses avec 168 scénarios et dix parcours WebSocket. L'arbitrage
du créateur maintient les événements de défausse depuis Main/Deck après un
remplacement par Suspension ou Exil. Le suivi commun est corrigé, ainsi que
le comptage des Volontés défaussées par Kanon. Otranth reste lié aux seules
arrivées réelles au Limbo. La reproduction conserve 50 échecs avant correction.
Les preuves sont séparées dans `reports/systematic-audit/discard-observer-followup/`.
Les déclenchements propres aux cartes défaussées et les instructions multiples
avant une même collecte restent distincts. Aucun push ni changement VFX.

La [passe des effets propres après défausse](AUDIT_SELF_DISCARD_141_1.md)
vérifie ensuite Tombloom et Nghoul-ong : 33 scénarios et quatre parcours réseau.
L'effet retrouve sa propre occurrence en Suspension et peut l'exiler. Les
départs/réentrées et autres copies ne sont pas confondus. La permission gratuite
exige un exil réellement accompli. La reproduction conserve 15 échecs sur
28 tests avant correction. Les preuves sont dans
`reports/systematic-audit/self-discard-followup/`. Les validations de la version
141.1 et du bouton d'installation mobile sont consignées séparément.

La [validation finale de 141.1](RELEASE_141_1.md) réexécute 2 948 tests Python
distincts et quatre suites client, toutes réussies. Le registre strict atteint
122/450 (27,1 %), avec au moins une clause sélectionnée vérifiée par carte,
sans certification exhaustive. Le bouton d'installation Android et son guide
sont vérifiés sur 14 contrôles, avec rendu mobile émulé dans Chrome ; aucun
téléphone physique ni Safari réel n'est certifié.
