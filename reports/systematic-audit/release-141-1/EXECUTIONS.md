# Validation de la version 141.1

Empreinte : `1b7a65e57a730228e696e59680e49225e0ea8656afc2d900c5ff9a5bb3e7227e`.

- 2 948 tests Python distincts réussis, aucun échec ni test ignoré.
- Quatre suites client : parité (608 scénarios), frontend, transport,
  installation PWA (14 contrôles).
- Nouveau lot propre à Tombloom/Nghoul-ong : 37 méthodes réussies.
- Compteur strict : 122/450 (27,1 %), avec au moins une clause sélectionnée
  par carte. Toutes les branches du catalogue ne sont pas certifiées.
- Source client, index et service worker synchronisés en 141.1.
- Captures PC et mobiles vérifiées. Les événements natifs sont simulés,
  aucun téléphone physique ni Safari réel n'est certifié.

Les sources étaient figées pendant cette validation. `unit-tests.json`,
`ui-tests.json`, leurs journaux et `evidence.json` conservent les exécutions,
empreintes et liens vers les preuves détaillées. La publication a été autorisée
par l'utilisateur et intervient après cette validation.
