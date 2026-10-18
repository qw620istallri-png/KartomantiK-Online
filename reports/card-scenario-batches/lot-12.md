# Lot 12 — cartes 111 à 120

Verdict : **PASS** · 0 contrôle(s) manuel(s) conservé(s).

| # | Carte | Serveur | Joueurs | Client | Statut |
|---:|---|---|---|---|---|
| 111 | Diabolical Giant | ✓ (1 cap.) | ✓ (1 actions) | ✓ | PASS |
| 112 | Mind Parasite | ✓ (1 cap.) | ✓ (0 actions) | ✓ | PASS |
| 113 | Shuk, the Bile-filled | ✓ (1 cap.) | ✓ (0 actions) | ✓ | PASS |
| 114 | Lament, Thought-nullifier | ✓ (1 cap.) | ✓ (0 actions) | ✓ | PASS |
| 115 | Forfog, the Hanged | ✓ (1 cap.) | ✓ (0 actions) | ✓ | PASS |
| 116 | Lerxur, the Black Moon | ✓ (1 cap.) | ✓ (0 actions) | ✓ | PASS |
| 117 | Ehgog, the Livid | ✓ (1 cap.) | ✓ (0 actions) | ✓ | PASS |
| 118 | Zrutrug, the Indebted | ✓ (1 cap.) | ✓ (0 actions) | ✓ | PASS |
| 119 | Reviving Cage | ✓ (1 cap.) | ✓ (1 actions) | ✓ | PASS |
| 120 | Repelling Urn | ✓ (0 cap.) | ✓ (0 actions) | ✓ | PASS |

## Parcours vérifié

1. Préparer deux joueurs, la phase, les zones, la Pile, les cibles et les coûts.
2. Déclarer chaque action volontaire par le gestionnaire de messages du serveur.
3. Résoudre la Pile ou exposer le choix obligatoire au joueur concerné.
4. Sérialiser l’état pour les deux sièges et contrôler la confidentialité des mains.
5. Charger la carte dans le vrai bac à sable Chromium et vérifier son rendu.
