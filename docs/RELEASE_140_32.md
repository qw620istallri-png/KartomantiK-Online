# Bêta 140.32 — Pioches et choix de cartes en Main

- Pray the Ether, Alchemical Press et Martyrize respectent les blocages de
  pioche et le remplacement de Kanon. Press ne propose plus de défausse
  impossible avec une Main immunisée.
- Kanon traite correctement les exemplaires identiques, défausse les cartes
  choisies avant de piocher les restantes, et conserve les événements et
  remplacements nécessaires à Denblew, Makaboon, Tombloom, Tenebro et BOB.
- Gorlok conserve un groupe distinct pour chaque pioche, suit les exemplaires
  encore en Main et continue son effet après le départ de sa source. Le choix
  annonce clairement l'exil, dans les trois langues.
- Traumatize respecte l'immunité de Main, les remplacements de défausse et
  l'exemplaire sélectionné, sans nouvelle perte de points après confirmation.
- Extortionist Womb se déclenche en Réaction, après la Révélation, sur la pile.
  Son choix montre toute la Main révélée et désactive les cartes qui ne peuvent
  pas être enchaînées. Le refus ou l'impossibilité d'enchaîner donnent le résultat
  avec deux jetons de puissance deux {H}, dans la mesure permise par le champ.
- Les choix de Main privés et la preuve de Womb dans les journaux sont filtrés
  pour les spectateurs. La Main révélée reste consultable dans le sélecteur
  après reconnexion ; une Main sans carte enchaînable est montrée aux seuls
  destinataires autorisés dans la fenêtre de révélation.

Les preuves et limites sont détaillées dans les audits
[défausse/pioche](AUDIT_DISCARD_DRAW_AFTER_140_31.md),
[Kanon](AUDIT_KANON_EVENTS_AFTER_140_31.md),
[Gorlok](AUDIT_GORLOK_DRAW_AFTER_140_31.md) et
[Traumatize/Womb](AUDIT_PRIVATE_HAND_AFTER_140_31.md).
Ces lots vérifient des branches sélectionnées ; ils ne certifient pas toutes
les clauses ou interactions du catalogue, Safari Mac ou les appareils physiques.

Le travail VFX distinct n'est pas inclus. Version des ressources :
`20261027-rules-beta-140-32`, affichée `beta 140.32`.
Les preuves historiques restent inchangées. La validation de publication est
séparée dans `reports/systematic-audit/release-140-32/`.

Validation finale : **1 538 tests Python réussis**, aucun échec ni test ignoré,
huit suites navigateur et une suite JavaScript du transport réussies. Les quatre
lots ajoutent 98 méthodes, dont dix parcours réseau. Les preuves partagent la
même empreinte dans [le registre de publication](../reports/systematic-audit/release-140-32/EXECUTIONS.md).
