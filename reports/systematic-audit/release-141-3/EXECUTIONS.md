# Validation de la 141.3

- Python : **3083/3083**, aucun échec ni test ignoré.
- Six suites client passent : mobile manuel (168), débordement mobile (96), frontend, nettoyage du glissement, installation PWA (25), parité client/serveur (608 scénarios).
- Registre strict : **129/450 cartes (28,7 %)** avec preuve de clauses sélectionnées, 321 hors de ce registre. Ce compteur ne certifie pas toutes les branches des 129 cartes.
- `unit-tests.json` correspond au digest courant avant publication ; `evidence.json` conserve les empreintes des artefacts.
- La première invocation de parité ne trouvait pas les dépendances Python locales. Son échec de préparation est conservé, puis la seule suite concernée a été relancée avec PYTHONPATH corrigé.
- Captures et journaux locaux non versionnés selon `.gitignore`. Scripts et JSON permettent de reproduire les contrôles.
- Aucun téléphone physique, Safari ou Samsung Internet réel testé.
