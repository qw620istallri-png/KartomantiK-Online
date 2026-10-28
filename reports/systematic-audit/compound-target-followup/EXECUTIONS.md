# Exécutions — effets composés et cibles invalidées

Empreinte finale commune : `184f4a3a5f5b7cab86d7d00b447e552c1a5b037f48bbdb99aef4eb0bb9976ad1`. Lot local après 141, non publié.

- Treize clauses sélectionnées avec attentes par carte indépendantes du moteur.
- 112 scénarios de famille et quatorze parcours WebSocket : 126 méthodes réussies.
- Avant correction du moteur : 108 réussites et quatre échecs reproduisant
  Paciphint. Les quatre mêmes identifiants passent après correction.
- Suite complète finale : 2 437 méthodes Python réussies, toutes distinctes,
  aucun échec ni test ignoré.
- Trois suites client réussies : parité des règles (608 scénarios), régressions
  frontend et transport incrémental. Aucun nouveau parcours UI propre à ces cartes.
- Registre strict : 100 → 109 cartes sur 450 (24,2 %), soit neuf nouvelles.
  Au moins une clause sélectionnée est vérifiée par carte, sans certification
  de toutes leurs capacités ou branches.

## Correction et reproduction

Paciphint conserve les emplacements de ses groupes. Si sa deuxième cible est
invalide, le déplacement encore légal du premier allié sous son Deck s'exécute.
Si l'allié est invalide, l'instruction conditionnelle d'ignorer une puissance ne
s'applique pas. Les transferts de marqueurs et échanges de contrôle exigent
encore leurs deux cibles. Toutes les cibles choisies invalidées font toujours
échouer l'effet entier, y compris la branche de points de Linoleus.

`python tools/card_compound_target_audit.py` exécute les contrats de
`audit/compound-targets.json`. Les résultats attendus sont explicitement écrits
par carte dans `tests/test_compound_targets.py`, pas déduits des valeurs de
résultat des capacités. Les déclarations volontaires et coûts sont réels ; les
événements déclenchés sont des stimuli explicites envoyés à la file de production.

Les parcours réseau invalident une cible dans une préparation contrôlée, puis
passent réellement les priorités. Un client incrémental et un client ancien
attendent le journal de résolution de l'action précise. Le pilote automatique
des phases est isolé. Les Bro emploient un dé fixé à 1.

La suite complète est `run_card_audit.units()` avec `audit.OUT` pointant vers
ce dossier. Les suites client figurent dans `ui-tests.json`. Les tests réseau et
Chrome utilisent ici une exécution hors sandbox Windows.

`tools/card_coverage_status.py --units reports/systematic-audit/compound-target-followup/unit-tests.json --write`
refuse une preuve périmée ou échouée. `coverage-before.json` conserve exactement
les octets du précédent compteur global. `evidence.json` relie les empreintes
actuelles des sources, contrats, résultats, journaux et registre. Les campagnes
précédentes conservent leurs empreintes historiques.

La preuve avant correction a été recueillie après correction des attentes de
couleur et de la portée de Psychowall dans le banc. Une référence d'action copiée
dans le pilote réseau a ensuite été corrigée ; les sources finales ont été figées
et toutes les campagnes relancées. Ces ajustements ne sont pas comptés comme des
bugs supplémentaires du jeu.

Les remplacements du déplacement de Paciphint, son choix initial d'allié,
les jetons donneurs, cartes attachées, autres jets et autres capacités restent
hors de ce lot. Aucun changement VFX, client, version, commit ou push.
