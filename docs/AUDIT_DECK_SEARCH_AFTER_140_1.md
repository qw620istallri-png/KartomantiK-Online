# Recherches dans le Deck et déclarations de noms — suite locale

Cette passe ajoute 25 méthodes pour quatre paragraphes sélectionnés : Hermeto,
Recall, Mejik et Poopom. Les attentes chiffrées et les branches sont écrites à
partir du texte anglais imprimé ; les actions utilisent les définitions réelles.
Les associations explicites sont dans
[clauses.json](../reports/systematic-audit/deck-search-followup/clauses.json).

## Écarts reproduits et corrigés

| Chemin | Avant | Après |
| --- | --- | --- |
| Hermeto et Recall : révélation | Les cartes cherchées arrivaient en main cachées ; leurs identifiants étaient retirés du résultat envoyé à l'adversaire | Seules les cartes sélectionnées sont révélées, visibles en main et nommées avec des références consultables dans le journal ; le reste du Deck demeure privé |
| Mejik : coût de déclaration | La source était épuisée et l'adversaire recevait la priorité avant que le nom soit choisi ; le nom était demandé à la résolution | Le joueur confirme le nom avant la mise sur la pile. Le nom et l'épuisement sont engagés ensemble, puis l'adversaire peut répondre. La résolution utilise ce nom sans second choix, même si Mejik a quitté le champ |
| Recherche sur Deck vide | Le retour anticipé omettait l'instruction finale de mélange | L'instruction est exécutée sans demander un choix vide |

Le formulaire distingue le choix du nom comme coût d'activation du choix de
Poopom pendant son effet. Les détails de la pile affichent le nom déclaré. Le
journal distingue la déclaration de Mejik du résultat de sa recherche.
Hermeto indique explicitement « jusqu'à deux », la révélation et la possibilité
de confirmer sans sélectionner de carte. Les trois langues sont renseignées.

La reproduction initiale est conservée dans
[before.json](../reports/systematic-audit/deck-search-followup/before.json) :
20 méthodes exécutées, six méthodes en échec, avec neuf échecs/sous-cas détaillés.
Cette preuve porte son empreinte historique. Les cinq méthodes supplémentaires
complètent ensuite le parcours réel de Recall, les refus/rejeux de Mejik,
la confidentialité des résultats dissimulés et les deux scénarios réseau.

## Branches vérifiées

- Hermeto : entrée au Vaisseau adverse uniquement, propriétaire immuable,
  sélection de zéro/une/deux cartes, Deck vide ou d'une carte, refus atomiques,
  confidentialité des candidats, révélation des seules cartes choisies,
  mélange exactement une fois et refus des sélections dupliquées/surnuméraires.
- Recall : perte de confrontation du tour courant requise pour déclarer,
  recherche d'exactement une carte disponible, parcours réel de déclaration et
  pile, Volonté au Limbo une seule fois, résultat public, refus et rejeu.
- Mejik : source en Interzone et non épuisée, nom engagé avant réponse,
  refus des noms invalides/de l'autre joueur, choix préalable bloquant les
  réponses, refus du rejeu, cible soi-même ou adversaire, recherche sans résultat,
  mélange du seul Deck concerné et résolution après départ de la source.
- Poopom : déclenchement réel d'entrée, comparaison par nom plutôt que par
  identifiant de catalogue, +4 exact jusqu'à la fin du tour, carte correspondante
  conservée au-dessus, mauvais nom défaussant une seule carte sans piocher,
  poursuite de la révélation/défausse après départ de la source, refus atomique.

## Réseau et interface

Deux scénarios utilisent le protocole réel à deux sièges : reconnexion conservant
le choix privé d'Hermeto puis révélation au second joueur ; activation de Mejik,
nom et épuisement avant priorité adverse, journal de déclaration unique, puis
résolution par les deux passes de priorité sans nouveau choix. Le pilote de
passage automatique est tenu à l'arrêt pour isoler ce transport ; ses preuves
de latence restent distinctes.

Six configurations Chrome combinent PC 1 440 × 1 000 et mobile paysage
844 × 390 avec français, anglais et italien. Elles utilisent les vrais clics
et champs pour les choix zéro/une/deux cartes et le nom déclaré, vérifient le
bouton de confirmation visible, le verrouillage après réponse, les références
de cartes du journal et les détails de pile. Les captures sont conservées dans
`reports/systematic-audit/deck-search-followup/` ; les images locales isolent
le comportement UI.

## Limites

La première suite complète relève uniquement un rapport généré périmé : le
parcours de Mejik attendait l'ancien nombre de messages. Sa preuve est conservée
dans `regression-before.json`. La régénération ajuste ce nombre de 530 à 528
dans la synthèse et de trois à un pour Mejik. Le test de cohérence est
rejoué. Cette régénération serveur ne constitue pas une nouvelle campagne
navigateur des 450 cartes ; cette couche du rapport reste historique.

Certaines résolutions sont isolées de leur déclaration/paiement et les résultats
de confrontation utilisés pour Recall sont préparés explicitement. Les autres
clauses, interactions et recherches du catalogue ne sont pas certifiées par
analogie. Les anciennes campagnes générales des 450 cartes restent historiques.
Cette passe ne teste ni appareil physique ni Safari Mac réel ; son signalement
reste ouvert. Aucun ajout de commande de test au serveur de production.

Commandes ciblées : `python tools/card_deck_search_audit.py` et
`node tests/test_deck_search_ui.cjs`. Le registre final conserve les preuves
de régression séparément. Version 140.1 conservée ; aucun commit ni push.

## Validation finale

La suite complète finale passe : **1 345 tests Python réussis**, aucun échec ni
test ignoré. Les cinq suites UI réussissent également : nouveau parcours,
interface sémantique, frontend, continuité des choix et parité client-serveur.
Le [registre d'exécution](../reports/systematic-audit/deck-search-followup/EXECUTIONS.md)
et les preuves agrégées portent la même empreinte que les sources exécutées.
