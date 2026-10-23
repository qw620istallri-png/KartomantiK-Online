# Audit des fantômes de glisser-déposer après 139.44

## Signalement et reproduction

En mode manuel, une carte déplacée du plateau vers le Réceptacle adverse peut
laisser une copie translucide sans interaction possible dans la colonne adverse.

La copie de déplacement (`.drag-ghost`) correspond à ces caractéristiques :
opacité 0,65 et `pointer-events: none`. Le test Chrome reproduit sa persistance
en interrompant le flux avant `pointerup`, puis en envoyant un mouvement de
souris avec le bouton déjà relâché. Avant correction, la copie reste présente.
Le relâchement normal suivi d'un changement d'état ne laisse pas de copie.
L'événement précis qui fait perdre le relâchement dans la partie signalée
n'a pas été observé directement ; les interruptions et reconstructions du
plateau sont couvertes explicitement.

## Corrections

- Un seul geste de carte actif à la fois, suivi par son identifiant de pointeur.
- Nettoyage sur relâchement, annulation, perte de capture, perte de focus,
  masquage de l'onglet, départ de page, disparition de la source ou nouveau geste.
- Un mouvement souris/stylet sans bouton enfoncé annule un geste dont le
  relâchement a été perdu. Les événements d'un autre pointeur sont ignorés.
- Les événements de fin sont suivis en capture, avant les gestionnaires locaux
  pouvant arrêter leur propagation. Les cartes fixes capturent le pointeur.
- Les rangées réordonnées suivent le même nettoyage, sans capture sur la carte :
  leur déplacement entre parents libère la capture du navigateur et ne doit pas
  interrompre le réordonnancement.
- Le déplacement ordinaire, les choix de destination sur le plateau, l'entrée
  en Support, les choix par emplacements, le réordonnancement, la répartition
  et les remplacements utilisent cette gestion commune. Une annulation nettoie
  les visuels sans envoyer une sélection ou un déplacement au serveur.
- Les jetons retrouvent leur position initiale si le geste est annulé.
- Un second défaut confirmé concernait les aperçus agrandis : retirer leur
  fenêtre parente entière ne déclenchait pas l'observateur du parent immédiat.
  Leur nettoyage surveille maintenant aussi la disparition d'un ancêtre et
  la perte de focus.

## Validation

- `node tests/test_drag_cleanup.cjs` : dépôt réel au Réceptacle adverse,
  carte visible dans la pile après mise à jour, relâchement perdu,
  annulations, reconstruction du plateau, événements tardifs, pointeurs
  concurrents, propagation arrêtée, tactile Chrome réel avec et sans
  reconstruction, disparition d'une fenêtre d'aperçu, choix par emplacement,
  jetons, copie de choix sur le plateau et déplacement en Support.
- `node tests/test_ponderer_drag.cjs` : répartition complète sur 1440 × 1000,
  1280 × 720 et 844 × 390, sans débordement ni erreur JavaScript.
- `node tests/test_frontend.cjs` : régressions générales de l'interface.
- `git diff --check` : sans erreur.

Corrections intégrées à la version 139.45.
