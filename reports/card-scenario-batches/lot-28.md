# Lot 28 — cartes 271 à 280

Verdict : **PASS** · 0 contrôle(s) manuel(s) conservé(s).

| # | Carte | Serveur | Joueurs | Client | Statut |
|---:|---|---|---|---|---|
| 271 | Nullify | ✓ (1 cap.) | ✓ (1 actions) | ✓ | PASS |
| 272 | Weaken | ✓ (1 cap.) | ✓ (1 actions) | ✓ | PASS |
| 273 | Deny Fate | ✓ (1 cap.) | ✓ (1 actions) | ✓ | PASS |
| 274 | Mutate Uncontrollably | ✓ (1 cap.) | ✓ (1 actions) | ✓ | PASS |
| 275 | Accentuate | ✓ (1 cap.) | ✓ (1 actions) | ✓ | PASS |
| 276 | Deny | ✓ (1 cap.) | ✓ (1 actions) | ✓ | PASS |
| 277 | Recall | ✓ (1 cap.) | ✓ (1 actions) | ✓ | PASS |
| 278 | Help! | ✓ (1 cap.) | ✓ (1 actions) | ✓ | PASS |
| 279 | Duel Honorably | ✓ (1 cap.) | ✓ (1 actions) | ✓ | PASS |
| 280 | Censor | ✓ (1 cap.) | ✓ (1 actions) | ✓ | PASS |

## Parcours vérifié

1. Préparer deux joueurs, la phase, les zones, la Pile, les cibles et les coûts.
2. Déclarer chaque action volontaire par le gestionnaire de messages du serveur.
3. Résoudre la Pile ou exposer le choix obligatoire au joueur concerné.
4. Sérialiser l’état pour les deux sièges et contrôler la confidentialité des mains.
5. Charger la carte dans le vrai bac à sable Chromium et vérifier son rendu.
