# Couverture par familles — pioches et défausses fixes

Ce lot vérifie **15 clauses de 13 cartes**, avec des quantités écrites depuis
les textes imprimés et figées dans `audit/draw-discard-family.json`. Les capacités
livrées exécutent les effets ; leurs valeurs ne fournissent pas les attentes.
Le banc distingue pioche, défausse de la Main et défausse du dessus du Deck.

## Défaut commun reproduit

Le sélecteur générique `discard_from_hand` déplaçait les cartes choisies avec
`move_zone_card`, sans passer par le traitement complet des mouvements d'effet.
Les entrées au Limbo ainsi produites contournaient la suspension de BOB. Lorsque
BOB et la mémoire de Quasimillenary pouvaient remplacer le même déplacement,
le choix d'ordre du joueur concerné n'apparaissait pas non plus.

La [preuve avant correction](../reports/systematic-audit/draw-family-followup/before.json)
conserve **162 méthodes : 152 réussites et dix échecs**. Les cinq effets de Main
(Dark Apparition, Filth-eater, Wheel, Makaboon et la branche mélancolique de Pidue)
échouaient chacun sur la suspension seule et sur le conflit suspension/exil.

Le correctif est limité au déplacement d'une carte défaussée par le sélecteur
commun : il utilise `move_zone_card_by_effect` pour l'entrée au Limbo. Le chemin
d'exil explicite est conservé. Les remplacements se décident avant l'extraction,
avec la même protection transactionnelle que les autres mouvements d'effet.

Les deux choix BOB/exil sont vérifiés : la carte reste en Main pendant le choix
d'ordre, puis rejoint exactement la Suspension ou l'Exil choisi. Elle n'est pas
ajoutée au Limbo dans ces cas. Les tests voisins des défausses suivies de pioche,
de Kanon et d'ordre des remplacements ont été rejoués.

## Clauses et branches sélectionnées

| Groupe | Clauses |
|---|---|
| Pioche fixe | Mazzolong, Keen-eyed Seeker, Reliable Ammonite, Callus, Ponder, Hermetic Threshold, Zum bleu et Pidue bleu |
| Défausse de la Main | Dark Apparition, Filth-eater, Wheel of Retribution, Makaboon et Pidue mélancolique |
| Défausse du dessus du Deck | Pluff et Zum mélancolique |

Les **162 scénarios de famille** vérifient les quantités exactes, l'ordre des
cartes piochées ou défaussées du Deck, les Decks/Mains vides ou limités à une carte,
les doublons, le destinataire, le contrôle adverse de la source et le ciblage de
son propre joueur lorsque le texte le permet. Les autres Mains et Decks restent
inchangés. Le déplacement ne se produit pas avant la résolution de l'effet ou
la validation du choix de défausse.

Les cas applicables couvrent aussi :

- blocage de pioche arrivé après la déclaration ;
- remplacement de la pioche par Kanon, avec le nombre exact de cartes examinées,
  défaussées et conservées ;
- suspension des sorties de Deck par BOB, et des entrées au Limbo depuis la Main ;
- immunité globale des Mains à 8 de puissance de BOB, sans ouvrir de choix impossible ;
- refus des choix mal formés, d'un mauvais joueur ou d'une réponse rejouée,
  sans mutation de l'état ;
- source partie après la mise sur la pile, et déclenchements refusés pour source
  couverte, désactivée ou en Impasse, mauvais événement/joueur/zone ;
- Mazzolong : Support joué, et non simplement mis en jeu ;
- Hermetic Threshold : première Volonté, avec exclusion du stimulus « pas la première » ;
- Pidue : uniquement les branches vitreuses et mélancoliques sélectionnées,
  avec couleur, adversaire, origine Main et phase appropriés.

Cinq scénarios supplémentaires de producteur sont inclus dans les 162 : entrées
réelles en Support pour Mazzolong/Wheel, défausse effective du Deck pour Makaboon,
et déclaration payée de Ponder avec le gestionnaire d'événement pour Callus et
Threshold. Les autres déclenchements emploient des stimuli explicites envoyés à
la file de production. Ponder et les deux activations de Zum utilisent leur
déclaration, leur paiement exact et la résolution réels.

**Seize parcours WebSocket** couvrent chaque clause et les deux ordres de Wheel
face à BOB/Quasimillenary. Les activations volontaires passent par les messages
réels ; les effets déclenchés et états de remplacement sont préparés explicitement.
Les joueurs passent leur priorité et répondent aux choix. Un client incrémental
et un client ancien doivent recevoir les bons résultats, avec le format de Main
correspondant à leur visibilité. Le pilote automatique des phases est isolé.
Le lot comporte donc **178 méthodes** au total.

## Preuves et compteur

Les [preuves par clause](../reports/systematic-audit/draw-family-followup/clauses.json)
et le [registre d'exécution](../reports/systematic-audit/draw-family-followup/EXECUTIONS.md)
conservent les identifiants réellement exécutés et les empreintes des sources.

```powershell
python tools/card_draw_family_audit.py
python -c "from pathlib import Path; import run_card_audit as r; r.audit.OUT=Path('reports/systematic-audit/draw-family-followup'); raise SystemExit(r.units())"
python tools/card_coverage_status.py --units reports/systematic-audit/draw-family-followup/unit-tests.json --write
```

Neuf cartes s'ajoutent : Keen-eyed Seeker, Reliable Ammonite, Callus, Ponder,
Hermetic Threshold, Dark Apparition, Filth-eater, Wheel of Retribution et Pluff.
Mazzolong, Makaboon, Zum et Pidue figuraient déjà dans le registre. Le
[compteur strict](../reports/systematic-audit/coverage-status.json) atteint
**118/450, soit 26,2 %**, avec au moins une clause vérifiée par carte.

## Limites

Les autres capacités des cartes, les cinq activations de Zum réunies, les autres
couleurs de Pidue, les mélanges de Main (Deny Fate/Pontificate), les effets composés
conditionnels et les parties complètes ne sont pas certifiés par ce lot. Les
déclarations produisant les tributs d'Ammonite et Filth-eater restent un parcours
distinct des stimuli de tribut utilisés ici.

Les tests de Kanon défaussent des Manifestations ; sa distribution de malus après
défausse d'une Volonté reste dans les audits précédents. Les nouvelles preuves
BOB/exil concernent les défausses simples d'une carte. Le sens des suites
conditionnelles « si vous le faites » quand leur défausse est remplacée n'est pas
départagé par ces tests. Les conflits entre davantage de remplacements restent
des scénarios distincts.

Les premières corrections de préparation (propriété de Ponder joué par le second
joueur, destination normale de la Volonté jouée, visibilité des Mains et état
réseau final déjà reçu) ne sont pas présentées comme des défauts du jeu. La
reproduction conservée utilise les préparations corrigées avant le correctif moteur.

Aucun changement VFX, fichier client, version, commit ou push. Les corrections
locales antérieures sont conservées. Aucun nouveau parcours UI de carte, Safari,
appareil physique ou illustration distante n'est certifié par ce lot.
