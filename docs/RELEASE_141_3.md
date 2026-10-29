# Version 141.3

Le mode manuel mobile permet de déposer directement dans les zones réelles du
plateau. Un glissement rapide dans l'Interzone ou les Volontés place la carte
séparément ; un maintien bref sur une carte permet une superposition volontaire.
Le navigateur du Deck présente ses commandes à gauche et ses cartes défilables
à droite, avec filtre par nom, inspection par tap et options par appui long.
Les boutons de validation et les menus restent accessibles sur petit écran.

Le lot de cartes corrige Convert the Pain et Lilitha, dont les suites
conditionnelles exigeaient une destruction effective, ainsi que Repress the
Self, dont le gain indépendant est conservé après suspension ou exil selon
l'arbitrage du créateur. Huit cartes ont des preuves de clauses sélectionnées,
dont sept nouvelles dans le registre strict.

Les détails sont dans les rapports de
[destruction ciblée](AUDIT_TARGETED_DESTRUCTION_AFTER_141.md),
[débordement mobile](AUDIT_MOBILE_OVERFLOW_AFTER_141.md) et
[dépôt direct / Deck](AUDIT_MOBILE_DIRECT_UI_AFTER_141.md).
L'itération intermédiaire avec panneau de destinations est historique ; elle
est remplacée par le dépôt direct demandé.

La validation finale et ses empreintes sont conservées dans
`reports/systematic-audit/release-141-3/`. Les versions du client, des 24 URL
d'assets de l'index et du service worker sont alignées sur
`20261029-rules-beta-141-3`.

Les fichiers JSON et les rapports sont versionnés. Les PNG et journaux de test
restent locaux conformément au `.gitignore` et sont régénérables par les scripts.
Les tests mobiles utilisent Chrome avec gestes tactiles émulés ; aucun appareil
physique, clavier logiciel, Safari ou Samsung Internet réel n'est certifié.

Validation finale : **3083 tests Python passent**, ainsi que les six suites client,
dont 264 contrôles mobiles et 608 scénarios de parité. Le registre strict est à
**129/450 cartes (28,7 %)** pour des clauses sélectionnées.
