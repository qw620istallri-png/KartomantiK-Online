# Interactions des cartes en main — bêta 139.17

Un clic ou un tap sur une carte de la main ouvre son inspection. Il ne joue,
ne défausse et ne sélectionne plus une carte comme paiement. Cette règle vaut
aussi pour les cartes proposées depuis le Limbo, le Grimoire ou la suspension.

| Intention | Geste principal |
|---|---|
| Inspecter une carte | Clic / tap ; Entrée ou Espace au clavier |
| Réordonner sa main | Glisser dans la main ; les commandes de tri restent disponibles |
| Jouer une carte | Glisser de la main vers le plateau |
| Utiliser une capacité depuis la main lorsque la carte ne peut pas être jouée | Glisser vers le plateau pour ouvrir son coût |
| Payer un Tribut, y compris une demande conditionnelle | Glisser les cartes sur la carte qui demande le paiement |
| Révéler, exiler ou défausser une carte comme coût supplémentaire | Glisser la carte sur la carte qui demande le coût |
| Ajouter des cartes au paiement optionnel | Glisser sur la carte demandant le paiement ; un second dépôt retire la sélection |
| Choisir des cartes de sa main pour un effet, dont le Grimoire | Glisser dans le panneau de l'effet ; confirmer les sélections multiples |
| Défausser manuellement | Glisser vers le Limbo |

Les boutons explicites de confirmation, refus, quantité et les menus d'actions
restent disponibles. Le ciblage de cartes sur le plateau garde son fonctionnement
existant. Les sélecteurs de cartes hors de la main ne sont pas modifiés.

Un dépôt hors de la destination demandée ne paie et ne choisit rien. Une
annulation tactile, la perte de focus ou un mouvement trop faible ne valide
aucune action. Le clic généré après un glisser est absorbé.

Le fond du choix du Grimoire couvre désormais toute la fenêtre. Dans la nouvelle
interface, la main est placée au-dessus de ce fond, hors du contexte d'empilement
du plateau. Les coûts utilisent les vraies cartes surlignées de la main, sans
dupliquer celle-ci dans un sélecteur cliquable.

## Vérification

`node tests/test_hand_interactions.cjs` couvre le clic et le glisser souris
(1440 × 1000) et le tap et le glisser tactiles synthétisés via Chrome/CDP
(844 × 390) : Grimoire, choix simples et multiples, quatre demandes de paiement,
coûts supplémentaires, cartes du Limbo/Grimoire/suspendues, jeu normal, dépôts
invalides et gestes annulés. Il vérifie aussi la hauteur du fond et l'accès à la
main. Ces gestes ne constituent pas une validation sur un téléphone physique.

Les tests généraux sont `tests/test_frontend.cjs` et
`tests/test_hand_space_shortcut.cjs`.
