# Bêta 150.1.2 — Disposition Solo stabilisée

Version des ressources : `20261103-rules-beta-150-1-2`, affichée
`beta 150.1.2`.

## Zones et orientation

- La table Solo reste toujours orientée sur P1, même lorsqu'une action ou un
  import est effectué pour P2.
- Les identifiants de sièges Solo contenant `:` sont maintenant décodés depuis
  la droite pour les piles, cartes de zone, scores et destinations de
  glisser-déposer.
- Les quatre piles de P1 restent à gauche et les quatre piles de P2 à droite,
  sans duplication.

## Interface

- La Main P2 utilise exactement la même position et la même emprise que la Main
  adverse des autres modes ; elle ne descend plus sur la zone de jeu.
- Les totaux de Confrontation sont ancrés vers le bord extérieur gauche de la
  zone P1 et le bord extérieur droit de la zone P2.

## Validation ciblée

- Régressions Solo desktop/mobile, frontend général, interactions de Main et
  nettoyage du drag réussies.
- **78/78 gestes réels** réussis sur les configurations PC, mobile et mixtes.
- **4 363/4 363 tests Python** réussis, sans échec, test ignoré ou identifiant
  dupliqué.
- **609 scénarios** de parité client/serveur et 25 contrôles PWA réussis.
- Registre strict inchangé : **309/450 cartes (68,7 %)**, aucune preuve exclue.
