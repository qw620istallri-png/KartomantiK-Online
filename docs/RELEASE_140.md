# Bêta 140 — règles des cartes et cohérence de l’interface

Cette version regroupe les corrections des audits réalisés après 139.45.

- Les cibles conservent leur identité de zone ; une carte partie puis revenue au
  Limbo ne reste pas une ancienne cible. Les effets utilisent la Première
  Manifestation courante et les valeurs imprimées des sources ayant quitté le champ.
- Les modificateurs, copies, changements de tempérament et nettoyages respectent
  leur ordre de résolution, leur durée et les restrictions de modification.
- Les paiements spéciaux, excédents de tribut, choix multiples et permissions de
  jeu sont cohérents entre serveur et interface. Rally accepte plus de 20 essences.
- Pago et Flaying Jaw utilisent les déclenchements normaux sur la Pile.
  Timid Brain lance effectivement son jeu en Soutien. Tenebro propose son
  remplacement avant toute entrée au Limbo. Wandering Outcast laisse son
  contrôleur accepter ou refuser l’échange après connaissance de la cible.
- Duel Honorably peut être neutralisé par le paiement de l’un ou l’autre joueur
  pendant sa présence sur la Pile. Lunar Liturgy fait sauter la Phase Finale
  uniquement au joueur concerné.
- Les jetons respectent les interdictions de mise en jeu ; les remplacements
  par suspension ou exil ne produisent pas d’événements ou de ressources indus.
- L’Impasse affiche les points de chaque joueur et les choix, surbrillances et
  permissions de l’interface restent synchronisés lors des changements d’état.

Les textes des 450 cartes ont une revue indépendante enregistrée dans
`audit/semantic-reviews/`. Cette revue ne certifie pas l’exécution de toutes les
branches et interactions : les preuves et leurs limites restent séparées dans
`reports/systematic-audit/`. La campagne finale et la consolidation des preuves
ont été exécutées après cette publication. Les essais sur téléphone physique seront réalisés
par le créateur, conformément à son choix.

Les versions du client, des URLs de ressources et du service worker sont
synchronisées en `20261025-rules-beta-140`.

Validation avant publication : 1 205 tests Python réussis et les 13 suites
Chrome de régression réussies. La suite UI générale a été rejouée après
adaptation de ses assertions à l’effet d’entrée séparé de Flaying Jaw.

Campagne finale : 1 206 tests Python, 13 suites UI, 182 parcours d'action et
deux parcours navigateur de reconnexion, 40 séquences comprenant 12 175 étapes,
ainsi que les 450 illustrations distantes passent sans échec. La revue
indépendante conserve les 450 textes et leurs 760 paragraphes ; les limites de
certification par clause restent explicites dans le rapport des exécutions.
