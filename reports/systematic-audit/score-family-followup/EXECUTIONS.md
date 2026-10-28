# Exécutions — famille des points fixes

Empreinte finale commune : `bc8e55305a69c25aec9b9b112473dc8a9ef65a664420648b45f3e1bfa8f952da`. Lot local après 141, non publié.

- 19 cartes et 23 effets avec attentes indépendantes du code des capacités.
- 285 scénarios de famille, six parcours WebSocket et un contrôle du banc :
  292 méthodes réussies, aucun échec ni test ignoré.
- Suite complète : 2 191 méthodes Python réussies, toutes distinctes,
  aucun échec ni test ignoré.
- Trois suites client réussies : parité des règles (608 scénarios),
  régressions frontend et transport incrémental. Aucun nouveau parcours UI
  propre aux 19 cartes n'est certifié par ces trois suites.
- Registre strict : 87 → 100 cartes sur 450 (22,2 %), soit 13 nouvelles.
  Ce sont des cartes ayant au moins une clause vérifiée, sans certification
  de toutes leurs branches.

## Reproduction et provenance

`python tools/card_score_family_audit.py` exécute les contrats de
`audit/score-family.json`. Chaque scénario possède un identifiant réel de test.
La matrice générale fournit des stimuli explicites à la file des déclenchements.
Seize cas emploient un producteur d'événement du moteur, en isolant l'effet
sélectionné. Deux autres cas paient réellement Strengthen : Cannon et Zam-za,
avec le gestionnaire de déclaration et chacun des deux ordres possibles.
Six parcours réseau passent les priorités et vérifient les scores des deux
clients en attendant la résolution de l'identifiant précis de l'action.

La suite complète est `run_card_audit.units()` avec `audit.OUT` pointant vers
ce dossier. Les trois suites client figurent dans `ui-tests.json`. Les tests
WebSocket et Chrome emploient ici une exécution hors sandbox Windows.

`tools/card_coverage_status.py --units reports/systematic-audit/score-family-followup/unit-tests.json --write`
refuse les sources périmées ou une suite échouée. Les preuves par clause sont
liées à des tests qui ont tous réussi dans la suite complète courante.
`coverage-before.json` conserve exactement les octets du précédent compteur,
qui reste une référence historique. `evidence.json` relie les empreintes des
contrats, résultats, journaux et du registre global actualisé.

Les six effets proportionnels restent sans nouveau contrat dans ce groupe.
Les clauses composées ne sont vérifiées qu'à hauteur des assertions explicites.
Leur déplacement ou leur autre effet ne devient pas certifié par le seul test
du montant de points. Les premières corrections de préparation des tests
(événements propres à la source et placement d'une méthode du banc) ne sont
pas présentées comme des bugs du jeu.

Aucun nouveau correctif moteur nécessaire pour ce lot, aucun changement VFX,
client, version, commit ou push. Les preuves historiques sont conservées.
