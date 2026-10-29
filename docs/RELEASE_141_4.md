# Version 141.4

Jigon peut jouer sa Volonté cachée lorsqu'elle possède une capacité jouée encodée. Le contrôle ne la refuse plus comme une source du terrain privée de ses effets. Son tribut normal reste requis ; la défaite de Jigon débloque le jeu gratuit selon son texte.

Les lots de cartes corrigent les récompenses d'exil effectivement remplacé, la sélection de Carcass Devourer, les mouvements depuis le Limbo sous BOB et les remplacements concurrents vers l'Interzone. Defer accepte les Volontés Éphémères présentes sur le champ. Les créations de jetons déclenchent leurs observateurs d'entrée, Reforging Fate conserve sa mémoire d'exil et Incinerate respecte l'Immunité ainsi que l'exclusion de l'Impasse.

En mode manuel, les animations de déplacement utilisent la destination confirmée par le serveur, y compris du point de vue adverse et pour les piles repliées. Le navigateur Scry reprend l'organisation mobile du Deck : commandes à gauche, cartes défilables à droite, inspection tactile, options par appui long et commandes accessibles.

Les rapports détaillés sont conservés dans les audits après 141.3 :

- [Exil](AUDIT_EXILE_FAMILY_AFTER_141_3.md).
- [Déplacements et Scry](AUDIT_MANUAL_MOTION_AND_SCRY_AFTER_141_3.md).
- [Destinations de zone](AUDIT_ZONE_DESTINATIONS_AFTER_141_3.md).
- [Support et jetons](AUDIT_SUPPORT_FAMILY_AFTER_141_3.md).
- [Lot élargi Support et Jigon](AUDIT_SUPPORT_PERMISSIONS_AND_JIGON_AFTER_141_3.md).

Ces documents décrivent les validations locales avant publication. La présente version publie cet ensemble ; leurs mentions historiques « aucun push » décrivent le moment de leur exécution.

Le registre strict atteint **188/450 cartes (41,8 %)** avec au moins une clause sélectionnée prouvée. Les 39 dernières cartes Support sont vérifiées pour leurs permissions et restrictions d'entrée ; leurs autres paragraphes ne sont pas certifiés par ce lot. Les états initiaux et certains événements sont contrôlés par les fixtures.

Le client, les 24 URL d'assets de l'index et le service worker sont alignés sur `20261029-rules-beta-141-4` afin de renouveler le cache de l'application installée. Les contrôles d'installation utilisent Chrome et des agents utilisateurs simulés ; aucun nouvel appareil physique, Safari ou Samsung Internet réel n'est certifié.

Les preuves finales de publication sont conservées dans `reports/systematic-audit/release-141-4/`. Les captures et journaux restent locaux conformément au `.gitignore`.

Validation finale sur les sources 141.4 : **3788/3788 tests Python passent**, aucun échec ni test ignoré, en 617,985 secondes. Les 25 contrôles PWA et la régression fonctionnelle du frontend passent. Les preuves existantes de déplacements et de Scry correspondent aux mêmes fichiers, après normalisation du seul tag de version de l'index. Le registre strict est actualisé sur cette suite générale courante : **188/450 cartes (41,8 %)**.
