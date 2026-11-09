# Passe Inflate the Ego / Puissance fixée et plafonnée

- **4 525/4 525 tests Python** réussis en 707,825 secondes.
- Zéro échec, test ignoré, identifiant dupliqué ou preuve exclue.
- **8/8 contrats ciblés** réussis pour les deux paragraphes d'Inflate the Ego.
- Son coût de cinq Tributs cholériques est réduit de la moitié, arrondie à
  l'inférieur, de la puissance de base modifiée de la Première Manifestation
  de son contrôleur. Le coût final ne descend jamais sous zéro et le coût
  imprimé reste inchangé.
- Sans Première Manifestation valide de son contrôleur, la déclaration est
  refusée atomiquement. Si la cible n'est plus sa Première Manifestation à la
  résolution, le coût reste payé et la Volonté rejoint le Limbo, mais aucun
  modificateur n'est créé.
- Une résolution valide fixe immédiatement la puissance courante à 10 et la
  plafonne à 10 jusqu'à la fin du tour. Un malus ultérieur peut la ramener à
  8, tandis qu'un bonus ultérieur ne peut pas dépasser 10.
- L'expiration normale retire seulement ce modificateur temporaire. La
  Dissipation retire aussi les autres changements de puissance qu'elle doit
  nettoyer, conformément à son contrat indépendant.
- Les 15 tests adjacents d'ordre des modificateurs et les deux régressions
  historiques ciblées réussissent également.
- Aucun défaut moteur n'a été découvert dans ce lot.
- Registre strict : **412/450 cartes (91,6 %)**.
- Lacunes restantes : **38 cartes, 53 paragraphes et 167 oracles**.

La suite complète est enregistrée dans `unit-tests.json` et la preuve des
deux paragraphes dans `clauses.json`.
