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
