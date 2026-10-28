# Exécutions — pioches et défausses fixes

Empreinte finale commune : `c2978a4e88d131ef5810ef85c7de68ce7556ec2ca3069a4bfcdee71ad2ce2b61`. Lot local après 141, non publié.

- Quinze clauses sélectionnées sur treize cartes avec attentes indépendantes.
- 162 scénarios de famille et seize parcours WebSocket : 178 méthodes réussies.
- Avant correction : 152 réussites et dix échecs sur BOB seul ou en conflit avec
  un exil, pour les cinq défausses simples de la Main. Les mêmes tests passent après.
- Suite complète finale : 2 615 méthodes Python réussies, toutes distinctes,
  aucun échec ni test ignoré.
- Trois suites client réussies : parité des règles (608 scénarios), régressions
  frontend et transport incrémental. Aucun nouveau parcours UI propre à ces cartes.
- Registre strict : 109 → 118 cartes sur 450 (26,2 %), soit neuf nouvelles.
  Au moins une clause vérifiée par carte, sans certification exhaustive.

## Correction et reproduction

Le sélecteur commun applique les remplacements avant l'entrée au Limbo d'une
carte défaussée de Main. BOB suspend cette carte, et le joueur concerné choisit
l'ordre si son exil Quasimillenary est également applicable. Le chemin d'exil
explicite du sélecteur n'est pas modifié. Les deux destinations de remplacement
sont testées, avec conservation de la carte en Main avant confirmation de l'ordre.

`python tools/card_draw_family_audit.py` exécute les contrats manuels de
`audit/draw-discard-family.json`. Les capacités livrées exécutent les effets,
les textes imprimés fournissent les quantités attendues. Les événements sont
préparés explicitement, sauf cinq cas supplémentaires employant de vrais chemins
Support, déclaration payée de Volonté et défausse de Deck. Les tributs complets
et les parties entières ne sont pas certifiés par ces stimuli.

Ponder et les activations de Zum utilisent des déclarations et paiements réels.
Les seize parcours réseau passent la priorité puis répondent aux choix Kanon,
de défausse et d'ordre des remplacements. Un client incrémental et un client
ancien doivent recevoir les bons états ; le pilote automatique des phases est isolé.

La suite complète est `run_card_audit.units()` avec `audit.OUT` pointant vers
ce dossier. Les suites client figurent dans `ui-tests.json`. Les tests réseau et
Chrome utilisent ici une exécution hors sandbox Windows.

`tools/card_coverage_status.py --units reports/systematic-audit/draw-family-followup/unit-tests.json --write`
refuse une preuve périmée ou échouée. `coverage-before.json` conserve exactement
les octets du précédent compteur global. `evidence.json` relie les empreintes
actuelles des sources, contrats, résultats, journaux et registre. Les campagnes
précédentes gardent leurs empreintes historiques.

La preuve avant correction emploie des propriétaires de cartes légaux et tient
compte de la destination normale de la Volonté jouée. Les premiers ajustements
correspondants du banc, ainsi que sa lecture des Mains selon la visibilité et
la réutilisation d'un état réseau final déjà reçu, ne sont pas présentés comme
des bugs supplémentaires du jeu.

Les mélanges, suites conditionnelles de défausse suivie de pioche, autres branches
de Pidue/Zum, jets et interactions non exécutées restent hors de ce lot. Aucun
changement VFX, client, version, commit ou push ; corrections antérieures conservées.
