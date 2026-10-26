# Pile WebKit et clauses de distribution — suite locale

Le signalement concerne les illustrations **dans le panneau de pile sur Safari
Mac**, et non leur animation de déplacement. Cette passe ne reproduit pas encore
ce défaut : elle ne le déclare donc ni corrigé ni certifié sur macOS.

## Pile : comparaison réelle entre moteurs

`tests/test_stack_browser_compat.cjs` ouvre l'application dans Chrome installé
et Playwright WebKit sur Windows, à 1 440 × 1 000 et 1 280 × 720. Il teste la
pile assistée classique, la pile assistée bêta et la pile manuelle bêta.

Chaque configuration utilise quatre cartes et deux profils : images locales,
puis quatre illustrations réelles du catalogue chargées à distance après un
retard imposé de 350 ms. Le second profil réaffiche l'état pendant ce chargement
et agrandit la pile bêta par son vrai bouton.

Les 24 cas vérifient le décodage, les styles de visibilité, le ratio et les
dimensions des images, ainsi que leur placement dans la vignette et sa ligne.
Les exceptions JavaScript font échouer le cas. Des captures sont conservées.
Le rapport horodaté contient les versions des moteurs, les URLs des quatre
illustrations distantes et les empreintes des fichiers client sélectionnés.

Preuves : [résultats navigateur](../reports/systematic-audit/safari-stack-followup/browser.json),
[première passe locale](../reports/systematic-audit/safari-stack-followup/initial-local.json).

**Limite :** WebKit 27.2 sur Windows n'est pas Safari Mac, ni une ancienne version
de Safari. Les dimensions et styles calculés ne prouvent pas à eux seuls tous
les détails de peinture. Le signalement reste ouvert pour une reproduction sur
le Mac concerné. Aucun correctif de production spéculatif n'est ajouté.

## Clauses : attentes chiffrées indépendantes

19 nouvelles méthodes testent deux paragraphes sélectionnés, avec les vraies
définitions de cartes et les chemins de choix/pile du moteur.

| Carte | Branches vérifiées |
| --- | --- |
| Echo of the Wilds | Défaite d'un participant uniquement ; choix avant mise sur la pile ; aucune modification avant résolution ; +3 sur une cible, +2/+1 choisis sur deux, +1 sur trois ; contraintes de zone/contrôleur ; absence de cible ; cible disparue ; refus sans mutation ; persistance après changement de tour ou départ de la source ; retrait par Cleanse ou sortie du champ |
| Stampeding Brood | Entrée au Vaisseau adverse uniquement ; choix du propriétaire immuable ; 0/1/2 jetons selon places disponibles ; caractéristiques exactes : puissance 1, vert, Soutien, Interzone ; refus et rejeu sans mutation ; aucun débordement en CZ malgré une interdiction de Soutien ; conservation à la Résolution et au tour suivant dans l'Interzone |

Les associations explicites entre texte imprimé, attentes et méthodes exécutées
sont conservées dans
[clauses.json](../reports/systematic-audit/distribution-token-followup/clauses.json).
Commande : `python tools/card_distribution_token_audit.py`.
Ces nouveaux cas ne révèlent pas de défaut de production.

La suite Python complète passe également : **1 320 tests réussis**, aucun échec
ni test ignoré. Les 19 nouveaux tests y sont inclus. Le
[registre d'exécution](../reports/systematic-audit/distribution-token-followup/EXECUTIONS.md)
et ses preuves agrégées portent l'empreinte des sources de cette passe.

Certaines résolutions sont isolées de leur déclaration/paiement et certains
résultats de confrontation sont préparés explicitement. La conservation des
jetons de Brood est prouvée dans l'Interzone ; leurs interactions ultérieures
avec une défaite ou une égalité en CZ restent hors de cette passe.

Cette passe ne certifie pas l'ensemble des clauses des 450 cartes. Les anciennes
campagnes complètes de navigateur, de matrice et d'illustrations restent
historiques ; les preuves nouvelles sont séparées. Aucun appareil physique
n'est certifié. Version 140.1 conservée, aucun commit ni push.
