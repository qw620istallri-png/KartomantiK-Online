# Version 141.2

Le gestionnaire d'installation n'annule plus la promotion native du navigateur.
Le bouton « Installer l'app » conserve l'événement et ouvre le dialogue natif au
clic, sur Chrome et sur les navigateurs qui exposent cette API, dont Samsung
Internet. Si l'événement arrive pendant que le guide est ouvert, un bouton
d'installation apparaît directement dans ce guide.

Le recours manuel Samsung Internet reste dans ce navigateur : icône près de la
barre d'adresse ou menu. Les textes sont traduits en français, anglais et italien.
Un événement consommé par l'interface native est effacé ; une installation ferme
le guide et masque l'entrée. Les événements antérieurs à l'initialisation restent
pris en charge.

Validation : **25 contrôles d'installation réussis** et suite de régression
frontend réussie. Les versions du client, de l'index et du service worker sont
alignées sur `20261028-rules-beta-141-2`.

Preuves : `reports/systematic-audit/mobile-native-install-followup/`.
La reproduction initiale conserve 9 échecs sur 20 contrôles ; la preuve finale
comprend un cas supplémentaire avant initialisation et quatre rendus navigateur.

Les événements d'installation sont simulés. Les captures sont produites par
Chrome avec des agents utilisateur Android, Samsung et iOS ; elles ne certifient
pas Samsung Internet réel, Safari ou un appareil physique. La proposition
automatique reste soumise aux critères et au choix du navigateur. Le site ne
peut pas installer silencieusement l'application.

Sources primaires : [installation PWA](https://web.dev/learn/pwa/installation-prompt)
et [guide Samsung Internet / Chrome](https://developer.samsung.com/automation/v2-pwa-guide.html).
Les règles des cartes et leur compteur de couverture ne changent pas dans cette
version ; les 2 948 tests Python de 141.1 ne sont pas présentés comme réexécutés.
