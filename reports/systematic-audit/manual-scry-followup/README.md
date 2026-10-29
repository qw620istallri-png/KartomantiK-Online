# Scry manuel : fenêtre mobile et confidentialité

- `before.json` : 36 cas, 18 passent et 18 échouent. Commandes hors écran et absence du défilement vertical demandé sur les petits formats.
- `browser.json` : contrôle final sur 1440×1000, 844×390 et 640×288, FR/EN/IT, avec gestes tactiles émulés pour les petits formats.
- Sont contrôlés : commandes à gauche, Fermer visible, défilement des cartes, maintien pour les options et accès au bas du Deck, envoi et annulation de l'action, réouverture, inspection au-dessus du popup et réglage de taille.
- Trois tests Python à sockets réelles contrôlent Scry privé, déplacement au bas du Deck et refus d'un observateur. Le premier test de confidentialité attendait à tort une diffusion d'état spontanée ; Scry ne diffuse volontairement rien. Le banc demande maintenant un resync du pair pour vérifier aussi l'absence de fuite dans le journal public.
- Le popup garde la sémantique existante : action envoyée immédiatement, carte grisée et annulation quand elle est disponible. Fermer ne sert pas de nouvelle validation du jeu.

Le banc UI passe par le gestionnaire `scry_result` avec un état contrôlé et des illustrations locales. Les sockets constituent une couche de preuve séparée. Chrome tactile émulé ne certifie pas un téléphone physique. L'identité de deux occurrences de la même référence dans un Scry n'est pas certifiée ici.

## Reproduction

Depuis la racine du dépôt, avec les dépendances Python serveur/test et Playwright/Chrome installés :

```powershell
$env:PYTHONPATH='server;tests;tools'
$env:PYTHONIOENCODING='utf-8'
node tests/test_scry_mobile.cjs
```

Ce poste utilise aussi le répertoire existant `C:/Users/istal/Documents/tmp/kko-test-deps` dans PYTHONPATH pour ses dépendances Python locales.
