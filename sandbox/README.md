# Bac à sable des cartes (local)

Un état de jeu préparé par carte, pour tester chaque carte à la main sur la
nouvelle table, ou la faire jouer par un script, puis noter si elle est validée.
Rien de ceci n'est actif sur le serveur en ligne : tout dépend de `KKO_SANDBOX=1`.

## Lancer

- Windows : double-clic sur `sandbox/start-sandbox.cmd` (port 8788, ouvre le navigateur).
- Ailleurs : `KKO_SANDBOX=1 PORT=8788 python server/main.py`, puis `http://localhost:8788/?sandbox`.
- `?sandbox=<id de carte>` ou `?sandbox=<id de scénario>` ouvre directement une carte.

Le panneau (onglet « Bac à sable » à gauche) permet de :
- chercher une carte (nom, numéro) et filtrer (à tester, en bug, validées, avec scénario écrit) ;
- recharger l'état de départ, jouer le siège adverse, laisser l'adversaire passer tout seul ;
- rejouer le script automatique pas à pas (les étapes s'animent sur la table) ;
- valider la carte ou signaler un bug avec une note : c'est écrit dans `sandbox/validation.json`.

## États génériques

Toute carte a des états de départ construits d'après son type et ses capacités,
proposés dans la liste « Scénario » :
- Manifestation : en Confrontation ; en Première Manifestation encore en main (l'adversaire
  a déjà posé la sienne face cachée : révélation et effets d'entrée) ; en main à la
  Réaction (Support depuis la main, capacité depuis la main, effet d'entrée en Support) ;
  dans ton Interzone (Support depuis l'Interzone, capacité ou bonus d'Interzone).
- Volonté : en main avec une Manifestation de tribut assez forte, à une étape où elle se
  joue ; une Volonté persistante aussi déjà résolue sur le terrain.

Les cartes de remplissage sont d'abord les 16 Manifestations sans texte, puis les
cartes à mots-clés seuls, puis les textes les plus courts (surtout dans les decks).

## Cartes simples validées automatiquement

`python tools/sandbox_validate_simple.py` valide les cartes sans capacité propre dont
chaque ligne est un mot-clé géré partout pareil (`SIMPLE_LINES` dans `server/sandbox.py`) :
pas de texte, Support / Support depuis la main / Float, pas en Première Manifestation,
pas de tribut, tribut depuis l'Interzone, jouable en Interzone en Fin de tour,
tribut d'un autre tempérament, valeur de tribut fixe (Faroc-Ko : 2, de n'importe quelle zone),
tribut sous le deck ou en Impasse. Pour chacune : les
règles compilées doivent correspondre au texte et tous ses scripts génériques doivent
passer (révélation en Première Manifestation, Support joué et résolu, puissance).
Le verdict est écrit avec `"auto": true` ; un verdict posé à la main n'est jamais écrasé.
`--check` vérifie sans rien écrire.

## Scénarios écrits (`sandbox/scenarios.json`)

Un scénario écrit fixe tout :

| Champ | Sens |
| --- | --- |
| `cardId` | la carte testée, notée `$card` partout ailleurs |
| `phase`, `turn`, `priority` | étape avancée (`confrontation_reaction`, `end_actions`…), tour, `me` ou `opp` |
| `players.me` / `players.opp` | zones `hand`, `deck`, `graveyard` (Limbes), `receptacle`, `exile`, `score` : un nombre = autant de cartes neutres, ou une liste de cartes |
| `battlefield` | `{id, owner, card, zone, first}` ; `zone` = `confrontation`, `interzone`, `stalemate`, `field` ; `first` = Première Manifestation |
| `checks` | ce que le testeur doit vérifier à la main (UI/UX) |
| `script` | étapes automatiques, voir plus bas |

Une carte s'écrit `"$card"`, un id réel, ou `"vanilla[:tempérament[:puissance]]"`
(Manifestation sans texte, choisie sans doublon). `{"card": …, "as": "nom"}` donne
un alias `%nom` réutilisable dans le script ; un objet du terrain se nomme `@id`,
les joueurs `&me` / `&opp`.

Étapes de script :
- `{"send": {…message client…}, "as": "me"}` : le même message que le navigateur envoie
  (`declare_rules_action`, `resolve_rules_choice`, `pass_priority`…) ;
  `"expectError": true` quand le serveur doit refuser ;
- `{"resolve": true}` : les deux joueurs passent jusqu'à résolution du haut de la Pile ;
- `{"passUntil": {"choice": "trigger_targets"}}` ou `{"passUntil": {"phase": "…"}}`
  (`"orChoice": true` : s'arrêter aussi au premier choix demandé) ;
- `{"choose": {"targets": […]}}` / `{"choose": {"option": "accept"}}` : répond au choix en attente ;
- `{"expect": …}` : `{"zone": "opp.graveyard", "contains"|"excludes": …, "count": n}`,
  `{"onField": "@id", "is": false}`, `{"power": "@id", "eq": n}`, `{"score": "me", "eq": n}`,
  `{"stack": n}`, `{"phase": "…"}`, `{"choice": "kind"}`,
  `{"cardOnField": "$card", "zone": "confrontation", "support": true, "faceUp": true}`,
  `{"cardPower": "$card", "eq": n}`, `{"confrontationResolved": true}`.

`tests/test_sandbox_scenarios.py` charge chaque scénario et chaque état générique,
joue tous les scripts par le vrai gestionnaire de messages, et vérifie les cartes simples.
