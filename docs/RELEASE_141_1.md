# Version 141.1

La version regroupe les corrections et les audits locaux poursuivis après 141 :
identité des choix du Vaisseau et des séquences de Deck, quantités et conditions
des familles de puissance/points/pioche/défausse, résolution partielle de
Paciphint, remplacements des défausses et séquences de Kanon, puis effets propres
de Tombloom et Nghoul-ong. Les contrats et rapports distinguent les clauses
sélectionnées, les interactions exécutées et la certification exhaustive.

Le bouton d'installation Android reste accessible lorsque l'invite native manque,
avec un guide traduit. Les événements d'installation précoces sont conservés et
les modes déjà installés masquent le bouton. Les fichiers de version du client,
de l'index et du service worker portent tous `20261028-rules-beta-141-1`.

Les [observateurs de défausse](AUDIT_DISCARD_OBSERVERS_AFTER_141.md),
[effets propres après défausse](AUDIT_SELF_DISCARD_141_1.md) et
[installation mobile](AUDIT_MOBILE_INSTALL_141_1.md) ont leurs preuves séparées.
Les rapports précédents conservent leur empreinte historique ; la suite globale
de cette version réexécute les tests actuels et alimente le compteur strict.

Validation de la version : `reports/systematic-audit/release-141-1/`.
Les **2 948 tests Python distincts** et les **quatre suites client** réussissent,
dont 608 scénarios de parité et 14 contrôles d'installation. Aucun échec ni test
ignoré. Le compteur strict atteint **122/450 (27,1 %)** avec au moins une clause
sélectionnée vérifiée par carte. Nghoul-ong rejoint le registre ; Tombloom y
figurait déjà.

Les appareils physiques restent à vérifier manuellement. Aucune nouvelle
certification de Safari réel ou de toutes les branches des 450 cartes.
