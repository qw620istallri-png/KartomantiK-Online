# Corrections de l'audit des paiements combinés — après 139.2.1

Les trois problèmes de paiement reproduits lors de l'audit précédent sont corrigés localement. Version inchangée, aucun push.

- **Martyrize et Censor** : le serveur retire des cartes disponibles pour le coût supplémentaire les cartes déjà réservées au tribut principal ou optionnel. L'interface exclut les exemplaires choisis de ses candidats. Deux exemplaires distincts peuvent toujours payer deux coûts distincts. Une combinaison invalide est refusée avant toute consommation de ressources.
- **Rally** : son supplément peut utiliser les Essences déjà disponibles et l'excédent du tribut principal dans un même paiement. La part utilisée est déduite de l'excédent créé, sans double dépense. Le joueur peut payer zéro, une partie ou la totalité de cet excédent et ajouter un tribut distinct. L'interface calcule le maximum après sélection du tribut.
- **Compensate et Drildrill** : le remboursement suit la répartition du coût imprimé. Hermetic Hourglass rend deux Essences bleues et deux jaunes. Compensate rembourse le propriétaire ; Drildrill rembourse le contrôleur. Les modificateurs du coût payé ne changent pas le remboursement imprimé.

Validation : **732 tests Python réussis**, dont six nouveaux tests de régression avec sous-cas ; contrôles navigateur PC/mobile réussis (1440 × 1000 et 844 × 390). Les contrôles couvrent notamment le refus sans mutation d'un paiement invalide, les exemplaires distincts, le supplément partiel de Rally, son paiement mixte et l'annulation du parcours client avant validation.

Régressions moteur : tests/test_combined_payment_audit.py. Régressions client ajoutées à tests/test_release_139_2.cjs.

L'audit suivant examine les transferts entre zones, les cibles qui ont quitté leur zone à la résolution, la suspension de BOB et les déclenchements d'entrée après réanimation. Ses nouvelles observations ne sont pas incluses dans ces corrections.
