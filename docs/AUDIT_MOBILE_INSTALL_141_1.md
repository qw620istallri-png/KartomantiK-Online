# Installation mobile

Le bouton était caché sur Android lorsqu'aucun `beforeinstallprompt` n'était
reçu. Son écoute commençait aussi seulement à l'initialisation tardive de
l'interface. La reproduction conserve cinq échecs sur onze contrôles de cycle
de vie et les captures initiales de l'accueil Android, iPhone et PC.

L'événement est maintenant capturé dès le chargement du module, puis l'interface
est mise à jour à son initialisation. Sur Android, l'entrée reste accessible
sans invite native et ouvre un guide adapté au menu du navigateur, traduit en
anglais, français et italien. Si l'invite existe, elle est utilisée une fois ;
si elle échoue, le guide prend le relais. Le bouton disparaît après l'événement
d'installation et dans l'application déjà ouverte en mode autonome.

Le guide iPhone/iPad est conservé. Son message pour les autres navigateurs
propose Safari en recours sans prétendre qu'aucun autre navigateur ne peut
installer. Le guide reçoit le focus à l'ouverture et se ferme par son bouton,
son fond ou Échap, avec retour au bouton d'installation. Aucun VFX n'est modifié.

La documentation primaire décrit l'événement comme une invitation que le site
peut personnaliser et prévoit des instructions lorsque cet événement manque.
Chrome Android propose aussi l'installation depuis son menu :
[installation PWA](https://web.developers.google.cn/learn/pwa/installation-prompt?hl=en),
[aide Chrome Android](https://support.google.com/chrome/answer/9658361?co=GENIE.Platform%3DAndroid&hl=en).
Les instructions ne promettent pas de forcer une invite native indisponible.

`node tests/test_pwa_install.cjs` vérifie **14 scénarios** : langues, événement
précoce ou tardif, consommation unique, échec de l'invite, mode installé,
événement `appinstalled`, absence de faux bouton PC et rendu navigateur.
Les captures après correction montrent le guide Android, le guide iPhone et
l'accueil PC, avec contrôle de l'absence de débordement horizontal et fermeture.
Le premier banc de cycle de vie a été complété avec le stockage local requis
par i18n avant la reproduction conservée ; ses erreurs de préparation ne sont
pas présentées comme des défauts du produit.

Les événements natifs sont simulés. Le rendu utilise Chrome et des agents
utilisateur mobiles ; il ne s'agit pas de Safari réel ni d'un téléphone physique.
Les preuves et captures sont dans
`reports/systematic-audit/mobile-install-followup/`.
