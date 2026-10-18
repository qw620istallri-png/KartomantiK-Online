# Audit KKO — cartes, serveur et nouvelle UI bêta

Date : 18 octobre 2026

## Verdict après correctifs

Les défauts serveur et bureau confirmés par cet audit sont corrigés. La fuite d'informations privées est fermée pour `zoneEntryTurns`, `conditionalSupportHandCardIds` et le canal additionnel `playPermissions`; les entrées numériques invalides ne coupent plus la connexion et ne peuvent plus injecter `NaN`; les sessions inactives sont nettoyées; les cartes de main et le bouton de repli du chat sont utilisables par les technologies d'assistance.

- **P0 ouvert : 0** — 1 corrigé.
- **P1 ouvert : 0** — 4 corrigés.
- **P2 fonctionnel bureau ouvert : 0** — libellé du chat corrigé.
- **P2 mobile/tactile reporté : 2** — cibles tactiles et écran portrait, conformément à la priorité actuelle.
- **Dette structurelle : 1** — découpage des grands fichiers à planifier séparément; aucune réécriture risquée n'a été mêlée aux correctifs.

## Correctifs appliqués le 18 octobre 2026

- Sérialisation filtrée par lecteur pour les marqueurs de zones privées, les cartes conditionnelles en main et les permissions de jeu liées à la main.
- Test sentinelle récursif vérifiant qu'aucun identifiant privé de main, deck, exil, rareté, sideboard ou définition de deck n'apparaît dans la vue adverse.
- Validation centralisée des nombres réseau, refus des valeurs non finies, rejet des messages JSON non objets et encodage JSON avec `allow_nan=False`.
- Réponse d'erreur contrôlée après charge invalide; la même connexion WebSocket reste utilisable.
- Nettoyage périodique des sessions expirées toutes les 60 secondes, sans supprimer une session encore connectée.
- Cartes normales, suspendues et fantômes accessibles au clavier avec nom, focus, Entrée/Espace et menu via Maj+F10.
- Nom accessible du bouton de repli du chat présent dès sa création et remis à jour lors d'un changement de langue.

### Validation finale

- **594 tests Python : OK** en 74,15 s.
- **Régression frontend complète : OK**.
- **Régression clavier + UI bêta : OK**.
- **450/450 cartes certifiées**, 493 capacités et 497 chemins; scénarios par lots de 10 toujours verts.
- Détecteur Impeccable relancé après modification. Ses alertes restantes concernent l'esthétique existante, les cibles tactiles reportées et les mêmes faux positifs d'images dynamiques; aucun nouveau défaut issu de ces correctifs.

## Preuves exécutées

- 594 tests Python : **OK** en 74,15 s.
- Régression frontend : **OK**.
- Raccourci clavier de la main : **OK**.
- Certification cartes existante : **450/450**, 493 capacités et 497 chemins.
- Chrome via Playwright : bureau 1440×1000, tablette tactile 1024×768, téléphone paysage 844×390 et téléphone portrait 390×844.
- Aucun débordement horizontal, aucune image réellement cassée et aucune erreur JavaScript dans les quatre profils.
- Appui long tactile synthétisé sur une carte : menu « Inspecter » ouvert correctement.
- Analyseur Impeccable exécuté sur `public/index.html`; les alertes d'images sans `src` et de conteneur rogné sont des faux positifs après vérification dans Chrome.

## Défauts confirmés

### [P0 — CORRIGÉ] Des identités de cartes privées sont envoyées à l'adversaire

**Emplacements :** `server/session.py:18367`, `server/session.py:18383`, producteurs aux lignes 468 et 5033.

La zone `hand` est correctement réduite à `{ "count": 1 }` dans la vue adverse, mais `rulesEngine.zoneEntryTurns` contient une clé telle que `p1:hand:secret-card`. Un second canal, `conditionalSupportHandCardIds`, expose aussi les identifiants exacts des cartes conditionnelles présentes en main.

**Preuve minimale obtenue :**

```json
{
  "opponentHandView": { "count": 2 },
  "zoneEntryTurns": { "p1:hand:secret-card": 1 },
  "conditionalSupportHandCardIds": { "p1": ["conditional-secret"], "p2": [] }
}
```

**Impact :** un client adverse modifié, les DevTools ou un proxy WebSocket permettent de connaître certaines cartes secrètes. La confidentialité serveur promise par le produit est rompue.

**Correction recommandée :** conserver `zoneEntryTurns` côté serveur et ne sérialiser que les entrées publiques ou appartenant au lecteur. Ne transmettre à chaque joueur que sa propre liste `conditionalSupportHandCardIds`. Ajouter un test récursif avec identifiants sentinelles pour la main, le deck, l'exil et les choix privés.

### [P1 — CORRIGÉ] Les nombres invalides peuvent couper la connexion

**Emplacements :** `server/main.py:1112`, `server/main.py:1322`, `server/main.py:1572`, `server/main.py:1665`, `server/main.py:1837`, `server/main.py:1976`, `server/main.py:2027`, `server/main.py:2185`; appel non protégé à `handle_message` ligne 2586.

Plusieurs conversions `int(...)` et `float(...)` ne capturent pas `TypeError`/`ValueError`. Le message `{ "type": "draw", "count": "abc" }` laisse échapper `ValueError: invalid literal for int()` hors du gestionnaire de message.

**Impact :** un client altéré ou une donnée corrompue interrompt son gestionnaire WebSocket et produit une déconnexion au lieu d'une erreur contrôlée.

**Correction recommandée :** centraliser `finite_int` et `finite_float`, borner les valeurs, puis répondre avec `send_error` sans quitter la boucle de connexion.

### [P1 — CORRIGÉ] `NaN` peut corrompre l'état diffusé

**Emplacements :** mêmes conversions `float(...)`, particulièrement `server/main.py:1572` et `server/main.py:1665`.

Une coordonnée chaîne `"NaN"` devient un flottant non fini, reste dans le plateau et est encodée par Python sous la forme non standard `NaN`. `JSON.parse` côté navigateur refuse ce paquet.

**Impact :** un joueur peut rendre les mises à jour d'état illisibles pour les clients connectés et polluer durablement la session.

**Correction recommandée :** refuser toute valeur pour laquelle `math.isfinite(value)` est faux et encoder avec `json.dumps(..., allow_nan=False)` comme dernier garde-fou.

### [P1 — CORRIGÉ] Les sessions expirées ne sont jamais supprimées

**Emplacements :** `server/session.py:42`, `server/session.py:268`, registre global `server/main.py:586`.

`Session.is_expired()` existe, mais aucun appel de production ne l'utilise et aucun `sessions.pop(...)` ou nettoyage périodique n'est présent.

**Impact :** chaque création de partie reste en mémoire jusqu'au redémarrage du processus. Un serveur public longuement actif grossira sans limite et peut être épuisé par de nombreuses créations de sessions.

**Correction recommandée :** lancer une coroutine de nettoyage périodique, préserver les sessions ayant des connexions actives et tester l'expiration avec une horloge contrôlée.

### [P1 — CORRIGÉ] Les cartes de la main ne sont pas utilisables au clavier

**Emplacement :** `public/app.js:7979`.

Une carte de la main est rendue comme un `<div>` avec clic, menu contextuel et glisser-déposer, sans `tabindex`, rôle interactif ni commande clavier équivalente. Le raccourci Espace ouvre la main, mais ne permet pas de sélectionner et jouer une carte donnée.

**Impact :** le flux principal est inaccessible aux utilisateurs clavier ou à mobilité réduite. Cela enfreint l'objectif WCAG 2.1.1 Keyboard.

**Correction recommandée :** utiliser un élément `button` ou `role="button" tabindex="0"`, exposer le nom de la carte et déclencher le menu d'actions avec Entrée/Espace. Chaque geste de glisser doit avoir une alternative par commandes.

### [P2 — REPORTÉ MOBILE/TACTILE] Les cibles tactiles sont trop petites

**Emplacements :** `public/ui-beta.css:268`, `public/ui-beta.css:531`, `public/ui-beta.css:691-718`.

Dans le scénario inspecté, 32 contrôles visibles sur 36 ou 37 font moins de 44 px sur au moins un axe. Sur téléphone paysage, plusieurs commandes tombent à 24×24 px et le bouton de priorité à 108×27 px.

**Impact :** erreurs de frappe et difficulté d'utilisation à une main, surtout en pleine partie.

**Correction recommandée :** conserver la densité visuelle mais porter les zones tactiles à 44×44 px avec padding, pseudo-éléments ou espacement invisible.

### [P2 — CORRIGÉ] Le bouton de repli du chat n'a pas de nom accessible initial

**Emplacements :** `public/ui-beta.js:807`, nom appliqué seulement dans `setChatFolded` aux lignes 1008-1011.

L'arbre d'accessibilité Chrome contient un bouton sans nom. `aria-label` n'est ajouté qu'après un changement de l'état replié.

**Impact :** un lecteur d'écran annonce un bouton sans fonction identifiable.

**Correction recommandée :** appeler `setChatFolded(local.chatFolded)` à l'initialisation ou fournir directement `aria-label` et `title` dans le balisage créé.

### [P2 — REPORTÉ MOBILE/TACTILE] L'écran portrait ne masque pas sémantiquement le jeu situé derrière

**Emplacement :** `public/ui-beta.css:675-682`.

L'écran « Tournez votre appareil » recouvre visuellement le jeu, mais le plateau et ses contrôles restent dans l'arbre d'accessibilité et dans l'ordre de tabulation.

**Impact :** un utilisateur de lecteur d'écran ou clavier peut atteindre des commandes invisibles sous l'instruction de rotation.

**Correction recommandée :** rendre le contenu du jeu `inert` et `aria-hidden` pendant l'affichage de l'écran portrait, puis restaurer ces états en paysage.

### [P2 — DETTE PLANIFIÉE] Les fichiers centraux sont devenus très difficiles à isoler

- `server/session.py` : 19 306 lignes, 954 Ko.
- `public/app.js` : 13 071 lignes, 638 Ko.
- `server/main.py` : 2 620 lignes, 125 Ko.

**Impact :** une règle de carte peut affecter une autre mécanique, la sérialisation ou l'interface sans frontière claire. La fuite privée illustre ce risque : les zones sont filtrées, mais les champs dérivés ajoutés plus tard ne le sont pas.

**Correction recommandée :** extraire d'abord la sérialisation privée et les validateurs d'entrée, car ce sont des frontières de sécurité testables. Éviter une réécriture globale.

## Cartes : ce que le vert signifie réellement

Les 450 cartes passent les scénarios actuels : 4 scénarios dédiés, 47 validations simples, 373 validations de capacités et 24 validations statiques. Les 493 capacités déclarées ont un chemin de smoke test. Cela prouve l'absence d'erreur structurelle connue et l'exécution des mécanismes encodés.

Cela ne constitue pas encore une preuve exhaustive de toutes les interactions combinatoires entre deux cartes, les interruptions réseau, les doubles déclenchements simultanés et les interprétations du texte imprimé. Karma Bro et Kaos Bro gardent aussi leur geste physique en contrôle manuel.

## Points positifs

- Les 606 tests passent après les corrections serveur, règles et interface.
- Les 450 cartes se rendent sans erreur JavaScript.
- Les vues principales ne débordent pas aux quatre formats testés.
- Le plateau paysage reste lisible à 844×390.
- L'appui long tactile fonctionne.
- Le bandeau rétracté se redéploie correctement lors du focus clavier après sa transition.
- Les images sans `src` signalées statiquement sont remplies avant affichage : aucune image visible cassée n'a été observée.
- Le cache long des ressources versionnées est correctement configuré.
- Les textes de chat passent par `esc(...)` avant insertion HTML.

## Santé UI technique

| Dimension | Score | Observation |
|---|---:|---|
| Accessibilité | 3/4 | Cartes et chat accessibles au clavier; dette tactile/portrait reportée |
| Performance | 3/4 | Aucun défaut visible; client brut volumineux mais ressources cachées |
| Responsive | 3/4 | Bureau, tablette et paysage stables; portrait volontairement bloqué |
| Thème | 3/4 | Système cohérent sombre/or/crème, quelques valeurs directes |
| Intégrité d'implémentation | 3/4 | Entrées et données privées durcies; fichiers centraux encore monolithiques |
| **Total** | **15/20** | **Solide sur bureau; dette mobile et structurelle identifiée** |

## État après corrections

1. Les champs dérivés privés sont filtrés et couverts par des tests sentinelles.
2. Les nombres réseau non finis et les charges JSON invalides sont refusés; l'encodage JSON est strict.
3. Le nettoyage périodique des sessions est actif.
4. Les cartes disposent d'une interaction clavier et le bouton de chat a un nom accessible dès l'initialisation.
5. Les cibles tactiles et l'isolation sémantique du mode portrait restent reportées, conformément à la priorité bureau actuelle.

## Captures et données

- `reports/ui-beta-audit.json`
- `reports/ui-beta-desktop.png`
- `reports/ui-beta-tablet-touch.png`
- `reports/ui-beta-phone-landscape.png`
- `reports/ui-beta-phone-portrait.png`
