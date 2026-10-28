# Couverture par familles — gains et pertes de points

Ce deuxième lot étend le banc à **19 cartes et 23 effets de points fixes**.
Chaque attente est relue depuis le texte imprimé et conservée dans
`audit/score-family.json` : montant signé, destinataire, événement, zone et
relation entre joueurs. Le texte complet et son empreinte sont figés. Les
nombres attendus ne viennent pas des valeurs encodées dans les capacités.

## Scénarios exécutés

Le lot contient **292 méthodes de test** : 285 scénarios de famille, six parcours
WebSocket et un contrôle du banc. Le contrôle modifie volontairement chaque
montant attendu et exige que son scénario échoue ; il ne compte pour aucune carte.

Les scénarios applicables vérifient :

- le score exact des deux joueurs et l'attente sur la pile avant résolution ;
- les scores négatifs, deux déclenchements distincts résolus successivement et
  le blocage des changements de points, y compris posé après la mise sur la pile ;
- le propriétaire de Graceful Petal, le joueur de l'événement pour Cannon et
  Forfog, le détenteur du Vaisseau pour Soul-borer et les adversaires pour Kox ;
- les effets sous contrôle adverse, les sources couvertes ou désactivées,
  le départ de la source après la mise sur la pile et les événements incorrects ;
- l'Interzone, les seuils de 9/10/11 Union ou Violence et les deux mémoires de Katun ;
- Balance, avec égalité réelle des totaux de Vaisseau ou redirection vers l'autre
  joueur, pour chaque gain/perte du groupe ;
- Linoleus avec une autre Manifestation valide et sans cible, avec absence de
  nouvelle boucle de gain provoquée par son propre bonus.

Seize scénarios passent par des producteurs réels : préparation des événements
de début de tour ou de résultat de confrontation, variation de score, défausse,
entrée en Support, déplacement vers le Vaisseau, entrée au Limbo, départ du
terrain ou réduction de puissance. Ils isolent la capacité sélectionnée après
production de l'événement. L'ordre des déclenchements simultanés n'y est pas certifié.

Cannon et Zam-za ont en plus chacun un scénario de paiement réel de Strengthen,
avec le gestionnaire de déclaration du serveur, le choix d'ordre et la résolution
dans chacun des deux ordres légaux. Le test de Zam-za vérifie aussi les trois
essences vertes excédentaires après le paiement du coût générique d'une essence.

Six parcours WebSocket couvrent les routes Incubator, Petal, Cannon, Soul-borer,
Kox au Limbo et Linoleus. La file est préparée avec un stimulus explicite, puis les
joueurs passent réellement leur priorité. Un client incrémental et un client
ancien doivent recevoir les scores exacts après l'identifiant précis de
résolution. Le pilote automatique des phases est isolé dans ces parcours.

## Registre et preuves

Treize cartes s'ajoutent au registre strict précédent de 87 cartes. Graceful
Petal, Pale Entity, Conflux, Atavic Fury, Forfog et Linoleus y figuraient déjà.
Le nouveau total est **100 cartes sur 450, soit 22,2 %**, avec au moins une clause
sélectionnée vérifiée par carte. Ce compteur ne certifie pas toutes les branches
de ces 100 cartes.

Les [preuves par effet](../reports/systematic-audit/score-family-followup/clauses.json)
conservent les identifiants de chaque méthode et ses résultats. Le
[registre d'exécution](../reports/systematic-audit/score-family-followup/EXECUTIONS.md)
relie la suite complète, les trois suites client et l'empreinte des sources.
Le [compteur global](../reports/systematic-audit/coverage-status.json) déduplique
les cartes et refuse les références d'interaction sans preuve explicite.

```powershell
python tools/card_score_family_audit.py
python -c "from pathlib import Path; import run_card_audit as r; r.audit.OUT=Path('reports/systematic-audit/score-family-followup'); raise SystemExit(r.units())"
python tools/card_coverage_status.py --units reports/systematic-audit/score-family-followup/unit-tests.json --write
```

## Limites et suite

Les événements explicites du banc ne constituent pas des parties complètes.
Les parties non liées aux points d'un effet composé restent à vérifier lorsqu'elles
ne sont pas affirmées par ces tests : notamment la restauration des marqueurs
d'Otranth et le déplacement de Chariot. Le changement de propriétaire d'une carte
n'est pas simulé ; le propriétaire est immuable, tandis que son contrôleur peut changer.

Le cas de Linoleus dont la cible de puissance devient invalide après sa mise
sur la pile reste à auditer séparément. Les conflits entre plusieurs remplacements
et les interactions entre plusieurs sources de redirection ne sont pas certifiés
par les tests de Balance avec une seule source.

L'inventaire du mécanisme compte 29 capacités : les six effets proportionnels
(Floating Dancer, Plea, Agrupol, Lombriculpop, Armored Pachywyrm et Donmo) restent
hors des nouveaux contrats de ce lot. Leur présence dans l'inventaire ne leur
ajoute aucune preuve. Ils pourront former le groupe suivant avec leurs propres
attentes de comptage.

Aucun nouveau correctif de production n'a été nécessaire sur les branches de
points vérifiées. Les corrections locales Vaisseau/Deck antérieures sont conservées.
Les VFX et les fichiers client de la version 141 restent inchangés. Aucun commit,
push ou changement de version ; aucune nouvelle certification Safari, appareil
physique, illustration distante ou parcours UI des cartes n'est impliquée.
