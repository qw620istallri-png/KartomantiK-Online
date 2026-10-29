# Recherche du Deck et menus sur petit écran

Le premier signalement ne disposait ni de capture ni de modèle de téléphone.
La capture ensuite fournie (1280 × 576, italien) confirme le menu du mode manuel
coupé après les entrées Limbo/Exil. Le blocage est reproduit sur les dimensions
paysage 844 × 390 : avec 40 cartes, le bouton
de validation du navigateur de pile descend sous l'écran. Le menu complet d'une
Manifestation dépasse également la hauteur disponible, sans pouvoir défiler.

Le navigateur de pile additionnait une liste de 74 vh à un en-tête et un pied
de fenêtre. La boîte, limitée à 88 vh, autorisait ensuite son contenu à déborder.
Elle est maintenant une colonne de hauteur bornée avec commandes réservées ;
seule la liste de cartes occupe et fait défiler l'espace restant. La hauteur
utilise le viewport dynamique. Une barre de défilement discrète indique la liste.

Tous les menus contextuels partagent une limite de hauteur, le défilement vertical
tactile et une limite de largeur. Leur position est recalculée à l'ouverture et
lors des changements du viewport visuel ou de la fenêtre : un menu ouvert reste
accessible après redimensionnement. Les boutons principaux de ces deux surfaces
mesurent au moins 44 pixels sur un écran tactile.

## Vérification

`node tests/test_mobile_overflow.cjs` exécute **96 contrôles** sur huit formats,
en français, anglais et italien : 1440 × 1000 et 844 × 390 avec souris ;
320 × 568, 390 × 844, 568 × 320, 844 × 390, 1280 × 576 et 640 × 288
(ce dernier à DPR 2) avec tactile émulé.

Les contrôles utilisent 40 cartes, une sélection préparée par la fonction de
production du navigateur de pile et le vrai menu d'une Manifestation. Des gestes natifs envoyés à Chrome
vérifient le défilement, puis un appui sur les boutons vérifie les messages
`move_card` et `remove_battlefield_item`, notamment `position: bottom`. Les
positions des commandes sont vérifiées avant l'appui, sans se reposer sur le
défilement automatique de Playwright. Un redimensionnement vérifie aussi le
repositionnement d'un menu déjà ouvert.

Les préparations utilisent explicitement `rulesEngine.enabled = false`, donc
le mode manuel et son menu complet. La capture fournie ne permet pas d'identifier
le viewport CSS ou la densité de pixels du téléphone. Le suivi ajoute les deux
hypothèses de mise en page 1280 × 576 à DPR 1 et 640 × 288 à DPR 2, en trois
langues, avec des captures italiennes du menu après défilement jusqu'au bouton
de retour sous le Deck. Aucune identification de modèle n'est déduite de l'image.

La reproduction conservée contient 42 échecs sur les 72 contrôles initiaux.
Après correction, ces 72 contrôles réussissent. Le suivi avec la capture fournie
porte le banc à **96 contrôles réussis**. La suite `node tests/test_frontend.cjs`
réussit également sur le correctif ; le suivi ajoute des tests sans modifier
à nouveau les fichiers de production.
Les captures, résultats et empreintes sont dans
`reports/systematic-audit/mobile-overflow-followup/`.

Un premier essai a été arrêté car l'écran de rotation masquait les contrôles en
portrait. Le banc masque explicitement cet écran pour les tests de géométrie en
portrait ; en production, le jeu continue de demander le mode paysage. Ces
tests ne prétendent pas rendre le jeu jouable en portrait.

La vérification complémentaire démarre directement dans la langue testée et
attend l'initialisation des libellés du navigateur de pile. Une première passe
changeait la langue uniquement après le démarrage et conservait ses libellés
fixes en français : ce défaut de préparation du banc est corrigé pour les
captures finales et une assertion contrôle le libellé de confirmation.
La passe intermédiaire `language-setup.json` conserve la mauvaise clé de
préférence du banc, ainsi qu'une mesure effectuée avant le traitement de
l'événement de redimensionnement. La clé réelle est `ko_language` ; le test
attend maintenant ce traitement avant de contrôler les limites du menu.
Ces ajustements ne nécessitent aucun nouveau correctif de production.

Il s'agit de Chrome avec tactile émulé, pas de Safari, Samsung Internet ou d'un
téléphone physique. Le geste ouvrant le menu est une ouverture contrôlée par
événement contextuel ; son défilement et le choix final utilisent des gestes
réels du navigateur. Les images sont locales pour isoler la mise en page.

Les règles serveur et leur registre de couverture restent ceux du lot précédent.
Les 3 083 tests Python antérieurs ne sont pas présentés comme réexécutés sur
cette modification d'interface. Aucun changement de version, commit ou push.
