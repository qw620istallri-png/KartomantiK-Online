# Couverture par familles d'effets — premier lot

Le banc permet désormais de vérifier un groupe de cartes avec les mêmes
scénarios, tout en conservant une attente indépendante pour chaque effet réel.
Le premier lot porte sur **21 cartes et 23 clauses de puissance** : variations
fixes ciblées, et modification intrinsèque de Thornmaster avec ses cas applicables.

## Contrats indépendants et exécutions

`audit/power-family.json` contient les attentes relues depuis les textes imprimés :
valeur, durée, cible, zone, condition de déclenchement et coût. Les identifiants
et textes sont figés avec leur empreinte. Une modification du texte exige une
nouvelle revue ; les nombres attendus ne sont pas calculés depuis les capacités
du moteur. Les capacités réellement livrées servent à exécuter chaque scénario.

`tools/card_effect_families.py` vérifie ces contrats et fournit un inventaire des
capacités candidates. L'inventaire issu du code sert au regroupement, jamais à
déclarer une carte couverte. Dans ce premier regroupement, 24 capacités de 22
cartes sont candidates ; 23 capacités de 21 cartes possèdent un contrat.
Jija reste explicitement sans contrat : son paiement demande de sacrifier un
jeton créé par cette source et de perdre des points. Ce cas nécessite sa propre
préparation et n'est pas validé par les autres malus de puissance.

Le banc génère un identifiant unittest distinct pour chaque couple effet/scénario.
Les scénarios sont appliqués selon les règles de la carte : un effet intrinsèque
de source n'est pas soumis artificiellement aux tests de ciblage de jetons ou de
Protection destinés aux autres effets.

## Vérifications du lot

Les 291 scénarios de famille vérifient, selon leur applicabilité :

- la valeur exacte après résolution, l'addition à un bonus existant et l'absence
  de modification des autres Manifestations ;
- le coût engagé avant l'effet : essences, marqueurs, points et épuisement ;
- les durées jusqu'à la fin du tour ou tant que la carte reste sur le champ ;
- Cleanse joué réellement, sans réapplication automatique du modificateur ;
- la perte du modificateur lors d'une sortie puis d'une nouvelle entrée ;
- les jetons, les contrôleurs, les limites de puissance et les zones autorisées,
  avec exclusion de l'Impasse et des Volontés non animées ;
- les cibles parties, protégées, déplacées en Impasse ou devenues adverses à la
  relation requise avant la résolution ;
- le départ de la source avant la résolution, avec le cas lié de Flaying Jaw ;
- les activations refusées pour mauvaise priorité, ressources manquantes, limite
  d'utilisation atteinte, source couverte, désactivée, hors champ ou contrôlée
  par l'adversaire ;
- les conditions de file des déclenchements : source visible, zone, joueur de
  l'événement, tempérament et phase lorsque le texte les impose.

Les effets volontaires passent par la déclaration, le paiement et la pile.
Les déclenchements utilisent la véritable file avec des stimuli explicites.
Ces derniers ne constituent pas une partie complète produisant chaque événement.

Onze parcours WebSocket, un par effet volontaire du lot, passent par les messages
réels, les deux passes de priorité, puis attendent le journal de résolution de
l'action précise. Un client incrémental et un client ancien reçoivent les états.
Le pilote automatique des phases est isolé dans ces parcours.

Cinq tests du banc complètent les preuves : modifier volontairement le nombre
attendu doit faire échouer chaque effet ; le compteur doit dédupliquer les cartes
et refuser les références d'interaction seules, les tests absents/échoués, les
textes modifiés et les rapports contenant des échecs. Au total, le lot exécute
**307 méthodes**, dont 302 scénarios de cartes et cinq contrôles du banc.

## Compteur strict reproductible

`tools/card_coverage_status.py` rassemble les liens explicites clause → tests des
lots conservés, vérifie leurs résultats dans la suite complète choisie et
déduplique les identifiants de carte. Une carte citée seulement comme interaction
ne s'ajoute pas au compteur. Les textes doivent toujours correspondre au catalogue.
La publication du compteur exige une preuve complète réussie portant la même
empreinte que les sources courantes.

```powershell
python tools/card_power_family_audit.py
python -c "import sys; sys.path.insert(0,'tools'); from pathlib import Path; import run_card_audit as r; r.audit.OUT=Path('reports/systematic-audit/power-family-followup'); raise SystemExit(r.units())"
python tools/card_coverage_status.py --units reports/systematic-audit/power-family-followup/unit-tests.json --write
```

Le compteur précédent était de 71 cartes. Cinq cartes de ce groupe étaient déjà
dans ce registre : Oppress, Strengthen, Weaken, Accentuate et Tombloom. Les autres
ajoutent 16 cartes distinctes, sans double comptage. Le résultat vérifié est
conservé dans [coverage-status.json](../reports/systematic-audit/coverage-status.json).
Il mesure les cartes ayant au moins une clause vérifiée, pas des cartes dont
toutes les branches seraient certifiées.

## Étendre la couverture

Pour une nouvelle carte de cette famille, lire le texte puis ajouter le contrat
et ses coûts/conditions indépendants. Les scénarios applicables et leurs noms
de tests sont générés automatiquement. Si un paiement ou une séquence ne rentre
pas dans ces préparations, laisser la carte dans l'inventaire et ajouter un cas
spécifique avant de la compter. Les familles de déplacements, gains/pertes de
points, pioches/défausses et choix pourront avoir leurs propres préparations,
en réutilisant les preuves par carte et le même compteur.

## Validation et limites

Les [preuves par clause](../reports/systematic-audit/power-family-followup/clauses.json)
et le [registre final](../reports/systematic-audit/power-family-followup/EXECUTIONS.md)
conservent les exécutions réelles et leurs empreintes. Ce lot ne nécessite pas
de nouveau correctif moteur sur les branches vérifiées. Les corrections locales
Vaisseau/Deck précédentes restent présentes. Aucun changement des VFX, du client
ou de sa version, aucun commit ni push.

Les autres capacités des cartes, tous les producteurs d'événements en partie,
les parties indépendantes des effets composés lorsque la cible devient invalide,
les paiements alternatifs et les interactions non décrites restent à couvrir.
La phase finale réelle n'est pas exécutée pour le test de dissipation : il
isole le changement de tour et le nettoyage des effets. Les cas de sortie de
zone utilisent des déplacements explicitement préparés.
Ces preuves backend ne certifient pas de nouveaux parcours UI pour les 21 cartes,
Safari Mac, des appareils physiques ou des illustrations distantes.
