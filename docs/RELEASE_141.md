# Bêta 141 — Effets d'éléments sur les cartes

- Chaque carte face visible joue un court effet de son élément, choisi par son
  Tempérament : Colérique feu, Flegmatique plante, Vitreux glace, Mélancolique
  ombre, Capricieux foudre, Creux cendre, Transcendant lumière.
- L'effet se joue à la révélation, à l'arrivée face visible, au déplacement sur
  le plateau et quand la carte déclenche ou résout son effet depuis le terrain.
- L'intensité suit la puissance (40 % à 0, 100 % à 6 et plus) ; une Volonté
  utilise son coût de Tribut. Aucun effet ne reste affiché, et rien ne se joue
  avec « réduire les animations ».
- Moteur : `public/js/vfx-elements.js` (un canvas éphémère partagé, bords
  fondus). Les scènes de cartes existantes de `vfx.js` sont inchangées.

Base : bêta 140.32. Version des ressources : `20261027-rules-beta-141`,
affichée `beta 141.0`.
