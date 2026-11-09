# Passe Obscure / Verrou temporaire

- **4 517/4 517 tests Python** réussis en 705,600 secondes.
- Zéro échec, test ignoré, identifiant dupliqué ou preuve exclue.
- **9/9 contrats ciblés** réussis pour les trois paragraphes d'Obscure.
- La cible doit être une Manifestation ou une Volonté Persistante sur le
  champ ; les cartes éphémères, la Zone d'Ex æquo, les cibles absentes et les
  cibles déjà Immunisées sont refusées atomiquement.
- Une cible valide perd ses effets et devient Immunisée aux cartes et effets
  jusqu'à la fin du tour. Si c'est une Manifestation, sa puissance compte
  comme zéro pour la confrontation pendant la même durée.
- Obscure est exilée à sa résolution, même si sa cible devient ensuite
  invalide. Si Obscure a perdu ses propres effets avant de se résoudre, elle
  rejoint au contraire le Limbo et ne crée aucun verrou.
- La Dissipation retire directement le modificateur continu sans annuler
  l'exil déjà effectué ; l'expiration de fin de tour restaure effets,
  vulnérabilité et contribution à la confrontation.
- Aucun défaut moteur n'a été découvert dans ce lot.
- Registre strict : **411/450 cartes (91,3 %)**.
- Lacunes restantes : **39 cartes, 55 paragraphes et 177 oracles**.

La suite complète est enregistrée dans `unit-tests.json` et la preuve des
trois paragraphes dans `clauses.json`.
