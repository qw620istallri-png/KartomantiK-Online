# Références aux Premières Manifestations et totaux d'Impasse

Exécuté : 2026-10-24T11:06:22.437792+00:00
Empreinte : `12ccf1833e0d427482cfa08bdefa638d51d3b27e758b96e925b5153b1b76e369`

## Résultat

```json
{
  "executed": 38,
  "passed": 38,
  "failed": 0,
  "skipped": 0,
  "browserGates": 4,
  "browserPassed": 4,
  "boundedAuditComplete": true,
  "fullCatalogSemanticCertification": false
}
```

Deux bugs moteur reproduits avant correctif : référence adverse absente donnant toujours zéro point, et référence conservant l'identifiant de la Première Manifestation partie.
La promotion est synchronisée lors des sorties du champ et du nettoyage des états. Tous les lecteurs existants, la sélection de cibles et les deux clients reçoivent ainsi le même identifiant courant.

Deux autres régressions ont été reproduites : Mamelath et Hermetic Hourglass lisaient la puissance imprimée au lieu de la base modifiée. Ils passent maintenant par le calcul de base commun, qui exclut les bonus additifs.

La bande d'Impasse et son panneau donnent maintenant les points de chaque propriétaire avec son nom et sa couleur. Le total commun est supprimé, les copies/jetons ne rapportant pas de points sont exclus. Les miniatures et les titres ne se recouvrent pas.

## Arbitrage du créateur

Lorsqu'une Première Manifestation quitte la Zone de Confrontation, la Manifestation suivante selon l'ordre d'entrée sous le contrôle du même joueur devient immédiatement sa Première Manifestation. Lombriculpop et Armored Pachywyrm lisent la puissance courante de cette nouvelle Première Manifestation à la résolution ; si aucune Manifestation adverse ne reste en CZ, la référence vaut zéro, et non la puissance imprimée de la carte partie.

## Preuves exécutées

- Lombriculpop et Armored Pachywyrm : absence adverse = puissance zéro, y compris après le départ des deux cartes initiales.
- Promotion selon l'ordre d'entrée en CZ ; puissance courante de la nouvelle Première Manifestation, sans rejouer ses effets d'entrée ni modifier ses propriétés de Support.
- Retrait, destruction à zéro, cartes hors CZ ou couvertes exclues ; sélection initiale couverte préservée.
- Mimer : l'ancienne cible partie reste invalide ; une nouvelle activation peut viser la Première Manifestation promue. Comparaison stricte des bases et énumération sans mutation.
- Mamelath crée ses jetons depuis les bases modifiées des Premières Manifestations déplacées ; Hermetic Hourglass compare aussi les bases modifiées. Les bonus additifs ne sont pas comptés comme puissance de base.
- Exile déclaré réellement, quatre passes via WebSocket, reconnexion adverse et résultat de points vérifié des deux côtés. Seul l'état initial après victoire est une fixture.
- Impasse : deux totaux par propriétaire, copies et jetons à zéro, noms longs, changement de siège, observateur, rafraîchissement et zone vide sur PC/mobile paysage.
- Clic réel sur la bande, espace réservé aux miniatures, cartes sous les totaux et panneau dégagé des compteurs de confrontation.

## Limites

- Les totaux d'Impasse affichent les valeurs imprimées par propriétaire ; ce ne sont pas des prédictions de tous les effets futurs ou des cartes temporairement verrouillées.
- Les illustrations distantes sont remplacées par le dos local dans les fixtures navigateur.
- Cette passe ne certifie pas toutes les clauses des 450 cartes ni toutes leurs interactions. Les campagnes générales non relancées restent historiques.

La reproduction antérieure contient 21 assertions en échec sur six méthodes, sans erreur de fixture ; son empreinte source n'avait pas été enregistrée. Le fichier JSON conserve son hash et son caractère historique.

Une seconde reproduction (first-reference-bases-before.json) contient les deux échecs de lecture des bases, sur dix méthodes exécutées. Ses résultats sont historiques et ne sont pas réattribués à la version corrigée.

[Résultats et sorties réelles](first-reference.json) · [Régression moteur](../../tests/test_first_reference_audit.py) · [Parcours réseau](../../tests/test_first_reference_integration.py) · [UI PC/mobile](../../tests/test_stalemate_totals.cjs)

## Vérification finale sur la même empreinte

- [Suite Python complète](unit-tests.json) : 1 046 tests réussis  aucun échec ni test ignoré.
- 38 tests ciblés réussis, dont quatre parcours réseau avec reconnexion (trois repris du lot précédent, un nouveau).
- Quatre contrôles navigateur réussis : totaux d’Impasse, parité, continuité des choix et régression frontend. PC et mobile paysage, deux sièges et vue observateur pour les totaux.
- Captures PC/mobile inspectées : bande compacte et panneau ouvert, noms longs et absence de recouvrement des totaux. Les illustrations utilisent le dos local dans ces fixtures.
- git diff --check : aucun défaut de whitespace. Détecteur JS : zéro signalement ; les six signalements CSS sont antérieurs et hors des règles modifiées.

Les campagnes générales de matrice, séquences et couverture des 450 textes ne sont pas restampillées par ces preuves ciblées. Aucun push ni changement de version.
