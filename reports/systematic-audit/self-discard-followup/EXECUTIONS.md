# Exécutions — effets propres après défausse

Empreinte finale de 141.1 : `1b7a65e57a730228e696e59680e49225e0ea8656afc2d900c5ff9a5bb3e7227e`.

- 33 scénarios unitaires et quatre parcours WebSocket : 37 méthodes réussies.
- Reproduction initiale : 13 réussites, 15 échecs, sur 28 méthodes.
  Les 15 identifiants échoués sont retrouvés et réussis dans la suite finale.
- Deux cas JSON et trois bornes de coût complètent les cas initiaux.
- Suite finale de version : 2 948 méthodes Python distinctes réussies,
  sans échec ni test ignoré ; quatre suites client réussies.
- Registre strict : 121 → 122/450 (27,1 %). Nghoul-ong s'ajoute ; Tombloom
  était déjà comptée. Au moins une clause sélectionnée par carte, pas toutes
  les branches des 450 cartes.

`python tools/card_self_discard_audit.py` exécute les contrats manuels de
`audit/self-discard.json`. L'arbitrage autorise leur propre effet à exiler
l'occurrence déposée en Suspension. Les sources sorties/réentrées et les autres
copies restent distinctes ; un réordonnancement ne crée pas une nouvelle carte.
Le statut de Tombloom décrit la destination réelle. Nghoul-ong exige son exil
effectif et refuse les cibles trop coûteuses ou qui ne sont pas Éphémères.

Les quatre parcours commencent par Pray joué réellement, son choix de défausse
et les mouvements remplacés par BOB. Une reconnexion conserve le choix propre
de la carte. Le parcours Nghoul-ong réussi joue Ponder sans tribut par le
protocole, puis l'exile en sortie de Pile. Les interventions retirant la source
et les états de remplacement restent des préparations contrôlées.

`coverage-before.json` conserve les octets du registre précédent, avec l'empreinte
consignée par discard-observer-followup. Le hash du fichier zones avant correction
correspond à la production validée par ce lot précédent. `evidence.json` relie
ces preuves historiques à la suite finale de version et aux sources actuelles.

Les actions anciennes sans snapshot conservent leur repli historique au Limbo.
Les doublons des cibles en général, le redémarrage du processus, toutes les autres
combinaisons, les appareils physiques et Safari réel ne sont pas certifiés.
