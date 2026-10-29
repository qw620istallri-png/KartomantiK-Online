# Déplacements et Scry manuels après la 141.3

Les corrections sont locales. La base publiée reste la 141.3 (`2f08549`).

## Déplacements

Les départs manuels du plateau étaient déduits de la présence de la carte dans les piles suivantes. Une autre copie déjà au Limbo pouvait donc faire voler une carte vers cette pile alors que le serveur l'avait envoyée à l'Exil ou à la main. Les transferts entre piles et la pioche manuelle n'avaient pas leur propre vol. Enfin, les icônes compactes des piles adverses repliées ne permettaient pas le dépôt et les effets pouvaient viser un élément masqué.

Les journaux `move_card` et `remove_battlefield_item` alimentent maintenant le pipeline VFX existant. Origine capturée avant rendu, destination serveur explicite, un seul vol par action et aucune rediffusion du passé à la reconnexion. Les messages privés produisent un dos. Les pioches `draw` et `draw_to_limit` ont le même retour, avec au plus cinq cartes animées pour les gros tirages. Les icônes compactes portent leurs destinations ; les effets les visent lorsqu'une pile adverse est repliée. Le mouvement réduit conserve une impulsion sur la destination.

Le banc réel à deux navigateurs couvre PC/PC, tactile/tactile et PC/petit tactile, dans les deux sens. Il vérifie Deck, Limbo, Exil, main et Vaisseau, transferts entre piles, Interzone/Volontés, confidentialité, pioche, arrivée depuis la main et nettoyage. Les zones finales sont vérifiées dans les états reçus par les deux joueurs.

## Scry

Le popup commun Scry/Révélation utilise désormais la disposition demandée pour Search : commandes à gauche et grille de cartes défilable à droite. Fermer reste visible, la taille se règle par un curseur natif, le toucher inspecte et l'appui long ouvre les options. La molette utilise le défilement vertical natif. Les menus restent bornés au viewport et l'inspection passe au-dessus du popup. Les déplacements gardent le fonctionnement existant avec carte grisée et annulation.

Le résultat Scry demeure envoyé uniquement au demandeur. Les tests réseau vérifient les dix premières cartes sans réordonner le Deck, un déplacement au bas du Deck sans fuite d'identité au pair, et le refus d'un observateur.

## Preuves et limites

Les JSON, scripts et empreintes sont dans `reports/systematic-audit/manual-motion-followup/` et `manual-scry-followup/`. Les erreurs initiales du banc sont distinguées des défauts reproduits dans leurs README. Les captures et journaux restent locaux selon `.gitignore`.

Les essais tactiles utilisent Chrome émulé ; aucun téléphone, Safari réel ou Samsung Internet réel n'est certifié. Les illustrations sont locales. Il ne s'agit pas d'une preuve exhaustive des déplacements simultanés ni des occurrences identiques de Scry.

Validation ciblée finale : **78/78 contrôles de déplacement**, **54/54 contrôles Scry**
et **3/3 parcours réseau Scry** passent. Les quatre suites voisines passent
(frontend, nettoyage du glissement, rareté/effets immédiats, parité) ; la parité
a aussi été relancée après Defer : **608 scénarios passent**.

Validation générale finale : **3242/3242 tests Python passent**, aucun échec ni
test ignoré. Registre strict actualisé à **142/450 cartes (31,6 %)**, soit six
nouvelles cartes avec clauses prouvées et 308 hors registre. Les preuves du lot,
de la suite générale et du registre utilisent le même digest courant. Aucun push.
