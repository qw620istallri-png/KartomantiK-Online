# Couverture par familles — points proportionnels

Ce troisième lot renforce six clauses déjà présentes dans le registre strict.
Il conserve une attente indépendante pour le coefficient signé, le destinataire,
la population à compter et le coût de Plea. Les textes et leurs empreintes sont
figés dans `audit/scaled-score-family.json` ; les résultats attendus ne sont pas
produits par le compteur du moteur.

| Carte | Calcul vérifié | Scénarios, réseau inclus |
|---|---|---:|
| Floating Dancer | +5 par Manifestation sous son contrôle en Interzone | 20 |
| Plea for Generosity | +5 par Manifestation non-jeton du joueur ciblé en CZ | 18 |
| Agrupol | +5 par Manifestation dont on est propriétaire dans les Vaisseaux | 18 |
| Donmo | Chaque adversaire gagne 5 par carte épuisée sous son contrôle | 21 |
| Lombriculpop | +5 par point d'écart positif avec la Première Manifestation adverse | 21 |
| Armored Pachywyrm | L'adversaire ciblé perd 5 par point de cet écart positif | 21 |

Le lot exécute **120 méthodes** : 113 scénarios de famille, six parcours WebSocket
et un contrôle du banc. Ce dernier modifie volontairement chaque coefficient
attendu et exige que son scénario échoue ; il ne compte pour aucune carte.

## Branches et interactions sélectionnées

Les six effets sont testés avec zéro, une, deux et trois unités de calcul,
des scores négatifs, une prévention des points arrivée après leur déclaration,
Balance à égalité ou en redirection, ainsi qu'un autre contrôleur. Le score ne
doit changer qu'à la résolution. Une unité ajoutée ou retirée pendant l'attente
doit modifier le résultat ; le calcul ne conserve pas le nombre de la déclaration.

Pour les capacités déclenchées, la file de production reçoit un événement
explicite. Des cas distincts passent par les vrais constructeurs de déclenchements
de résultat de confrontation ou de phase finale. Les sources couvertes,
désactivées ou en Impasse, et les mauvais événements, ne créent pas l'effet.
Le départ de la source ou son changement de contrôleur après sa mise sur la pile
n'attribuent pas l'effet en attente à un nouveau contrôleur.

Les cas dédiés vérifient notamment :

- Floating Dancer inclut jetons, copies et Volontés animées, exclut les autres
  zones, les cartes couvertes et les Volontés ordinaires ; si Dancer arrive en
  Interzone avant le calcul, il se compte lui-même.
- Plea peut cibler son propre joueur ou l'adversaire. Les jetons et copies sont
  exclus, une Volonté réellement animée est incluse. Déclaration, deux essences
  vertes, refus sans ressources, mauvaise priorité, joueur absent et choix en
  attente passent par les fonctions réelles. Le score revient au lanceur.
- Agrupol distingue le propriétaire du détenteur du Vaisseau et du contrôleur
  de la source. Les préparations respectent l'interdiction de placer une carte
  dans le Vaisseau de son propriétaire. Les doublons comptent séparément. Une
  Volonté animée redevenue Volonté en quittant le terrain ne compte pas comme
  Manifestation au Vaisseau. Agrupol qui rejoint le Vaisseau avant résolution
  s'ajoute au décompte de son propriétaire.
- Donmo compte aussi les Volontés, jetons et copies épuisés. Les orientations
  0°/180°/360° sont restaurées, 90°/270° sont épuisées. Donmo épuisé se compte
  lui-même ; le contrôle courant prime sur la propriété. Sauter la phase finale
  du contrôleur empêche son déclenchement.
- Lombriculpop et Pachywyrm lisent les puissances courantes, avec doublement de
  base et bonus, mais ne somment pas les Supports. L'écart est borné à zéro.
  Après le départ de la Première Manifestation adverse, ils utilisent le Support
  promu ; sans Manifestation adverse, la référence vaut zéro. Une source partie
  utilise sa puissance imprimée. Une nouvelle instance revenue avec un bonus
  ne remplace pas la source de l'ancien effet.
- Les cartes simplement comptées continuent de compter si elles reçoivent
  Protection : elles ne sont pas les cibles de ces capacités.

Six parcours WebSocket, un par carte, vérifient les scores reçus par un client
incrémental et un client ancien après les vraies passes de priorité. Le décompte
change pendant que l'action attend. Plea utilise une déclaration réseau payée ;
les cinq déclenchements sont préparés par un stimulus explicite. L'attente se
termine sur le journal de résolution de l'identifiant précis de l'action.

## Preuves et compteur

Les [preuves par clause](../reports/systematic-audit/scaled-score-followup/clauses.json),
les [exécutions](../reports/systematic-audit/scaled-score-followup/EXECUTIONS.md)
et leurs empreintes restent séparées des campagnes précédentes.

```powershell
python tools/card_scaled_score_audit.py
python -c "from pathlib import Path; import run_card_audit as r; r.audit.OUT=Path('reports/systematic-audit/scaled-score-followup'); raise SystemExit(r.units())"
python tools/card_coverage_status.py --units reports/systematic-audit/scaled-score-followup/unit-tests.json --write
```

Le [registre strict](../reports/systematic-audit/coverage-status.json) reste à
**100 cartes sur 450, soit 22,2 %**, avec au moins une clause vérifiée par carte.
Ces six cartes étaient déjà comptées ; leurs nouvelles branches renforcent les
preuves sans ajouter six cartes fictives. Cela ne certifie pas toutes les
capacités ni toutes les interactions de ces cartes.

## Limites

Les populations ajoutées, restaurées, transférées ou retirées sont des préparations
contrôlées ; ces tests ne certifient pas chaque carte susceptible de produire
ces changements. Les résultats de confrontation sont préparés pour auditer
les déclenchements, sans simuler un combat complet à chaque fois. Le pilote
automatique des phases est isolé dans les parcours réseau.

L'épuisement de cartes couvertes, attachées ou en Impasse dans le décompte de
Donmo reste hors de ce lot. Son activation de restauration et son interdiction
de tribut ne deviennent pas certifiées par le test de ses points. Le mélange
du Deck par Agrupol n'est pas vérifié ici. Les interactions avec plusieurs
sources de redirection et les parties complètes restent des cas distincts.

Aucun correctif de production n'a été nécessaire sur les branches vérifiées.
Les corrections locales Vaisseau/Deck antérieures sont conservées. Aucun
changement VFX, client, version, commit ou push. Aucune nouvelle certification
de parcours UI des cartes, Safari Mac, appareil physique ou illustration distante.
