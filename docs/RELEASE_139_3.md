# Bêta 139.3 — fin des audits complémentaires

Cette version termine les passes annoncées sur les choix refusés et repris, les déplacements ordonnés, les copies et effets temporaires, et la confidentialité des données réseau. Les corrections locales de l’audit d’atomicité sont incluses.

## Corrections

- **Choix atomiques** : un second groupe invalide ne modifie plus le premier deck ou la première relocalisation. Les transferts et les cibles de répartition de perte de puissance sont validés avant toute mutation.
- **Reprise des choix** : les boutons se réactivent après un refus serveur. Les placements de deck et de relocalisation restent utilisables ; l’annulation d’un choix périmé est diffusée aux deux joueurs. Une ancienne réponse, un mauvais joueur ou un double envoi ne rejouent pas le choix.
- **Timidette** : son contrôleur choisit l’ordre des Supports sous chaque deck concerné. Le sélecteur existant sert pour le dessus et le dessous, avec les textes anglais/français/italien adaptés. Les groupes où aucun deck ne reçoit deux cartes réelles se résolvent sans confirmation inutile.
- **Retours ordonnés** : Timidette et Gusted Nebula utilisent les remplacements de mouvement, notamment la suspension de BOB. Timidette ne produit pas le bonus de Gusted Nebula.
- **Mimer** : les dernières puissance, puissance de base et couleur sont mémorisées au départ de la cible. Le résultat ne dépend plus d’un rafraîchissement d’affichage préalable.
- **Copies** : une copie qui disparaît libère les cartes qu’elle suspendait et retire ses propres mémoires attachées. Elle ne reçoit pas les mémoires de la carte réelle.
- **Mémoires différées** : le retour d’une carte réelle depuis les Limbes ou la main rétablit le lien avec son nouvel objet sur le champ. L’entrée dans le deck ou l’exil continue d’effacer sa mémoire.
- **Confidentialité** : les inspections, ordres de deck, recherches privées, Volontés couvertes, nouvelles cartes piochées et retours privés de suspension sont filtrés dans les données de résolution et les journaux. Le filtrage couvre l’état courant, le flux récent, le journal complet et la reconnexion. Les révélations et les recherches vers l’Interzone restent publiques ; les accès privilégiés existants sont conservés.

## Vérification

- **777 tests Python réussis** sur la version finale.
- 27 régressions dédiées dans `test_choice_atomicity.py`, `test_choice_reconnect.py` et `test_remaining_rules_audit.py`, dont cinq tests par WebSocket réel.
- Tests navigateur généraux, parcours de version sur PC/mobile et glisser-déposer d’Expansive Ponderer : réussis.
- Catalogue : 496 capacités, 500 variantes d’état, 379 cartes, aucune carte en échec. Registre d’automatisation à jour.
- Ressources HTML, application, service worker et README synchronisés en `20261022-rules-beta-139-3`.

Les audits et leurs cas de contrôle sont détaillés dans `AUDIT_CHOICE_ATOMICITY_AFTER_139_2_2.md` et `AUDIT_REMAINING_139_3.md`. Ils couvrent les parcours définis et les défauts reproduits ; les tests du catalogue ne prouvent pas toutes les combinaisons possibles du jeu.
