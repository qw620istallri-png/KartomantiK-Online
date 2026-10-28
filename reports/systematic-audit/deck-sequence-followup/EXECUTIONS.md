# Exécutions — Bloatuba / Expansive Ponderer après 141

Lot local, non publié. Base publiée : `355efdd` (141), avec le lot Vaisseau
local précédent conservé. Empreinte finale commune : `e8d915a698f9537f4e892470262e6350dedcc9816810741ff5909d427a52a370`.

- 26 méthodes ciblées réussies : 23 clauses/interactions et trois parcours réseau.
- 1 592 tests Python réussis, aucun échec ni test ignoré.
- Sept suites client réussies : séquences de Deck, glissements de Ponderer,
  continuité des choix, parité client/serveur (608 scénarios), régressions
  frontend, reconnexion et transport.
- Six configurations Chrome pour 18 scénarios du nouveau sélecteur ; français,
  anglais et italien, PC et paysage mobile simulé. Quatre captures françaises
  inspectées visuellement. Les illustrations sont locales et ne certifient
  pas les images distantes.

## Commandes et provenance

```powershell
python tools/card_deck_sequence_audit.py
node tests/test_deck_sequence_ui.cjs
```

La suite complète emploie `run_card_audit.units()` avec `audit.OUT` pointant sur
ce dossier. Les sept suites sont listées avec leurs commandes dans `ui-tests.json`.
Les WebSockets et Chrome utilisent ici l'exécution hors sandbox Windows.

`before.json` conserve 23 méthodes avant correction : dix réussissent et treize
échouent, avec dix-neuf échecs/sous-cas. Les corrections initiales de préparation
précèdent ce relevé. Les assertions de confidentialité sont ensuite renforcées
pour inclure aussi la vue du joueur qui choisit.

`clauses.json`, `unit-tests.json` et `ui-tests.json` portent la même empreinte
finale. `evidence.json` relie les empreintes des preuves, payloads, journaux et
captures. Les preuves antérieures gardent leurs empreintes historiques.

Les identités du Deck restent représentées par les identifiants/versions
existants : ce lot ne certifie pas une identité unique pour chaque exemplaire
dans toutes les opérations du moteur. Les autres continuations, interactions,
Safari Mac, appareils physiques et illustrations distantes restent à couvrir.
Ni les 450 cartes ni toutes les branches de ces deux cartes ne sont déclarées
certifiées. Aucun changement de version, de VFX, commit ou push.
