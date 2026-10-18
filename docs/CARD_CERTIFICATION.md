# Certification automatique des cartes

La commande suivante contrôle les 450 cartes, exécute tous les scripts de la
sandbox et régénère le rapport détaillé :

```powershell
py tools\card_certification.py --write
```

Elle produit :

- `reports/card-certification.json`, destiné aux outils et à la CI ;
- `reports/card-certification.md`, destiné à la lecture humaine.

Pour vérifier que les rapports versionnés sont à jour sans les modifier :

```powershell
py tools\card_certification.py --check
```

`--strict-scenarios` renvoie un échec tant qu'une carte annoncée comme
automatisée ne possède qu'une preuve structurelle. Ce mode mesure la dette de
scénarios ; il est volontairement plus exigeant que la suite normale.

## Niveaux de preuve

- **Scénario comportemental** : un scénario écrit utilise le vrai gestionnaire
  de messages, paie les coûts, résout la Pile et vérifie les résultats.
- **Règles génériques exécutées** : la totalité du texte de la carte se limite à
  des mots-clés génériques contrôlés et joués automatiquement.
- **Capacités exécutées isolément** : chaque résultat, effet continu, passif ou
  permission de jeu de la carte est exécuté avec sa vraie définition dans un
  état riche et isolé. Cela couvre aussi les voies spécialisées comme Trap et
  les effets de fin de partie.
- **Règles statiques exécutées** : la carte n'a pas de capacité déclarative ;
  ses états sandbox, ses calculs de caractéristiques et ses règles compilées
  sont exercés par le moteur.
- **Preuve structurelle** : catalogue, compilation, contrats de cible, phases,
  références de tests et états sandbox sont cohérents. Un scénario dédié reste
  nécessaire pour certifier le comportement complet du texte.
- **Partielle / manuelle** : une limite connue est documentée dans le registre
  de couverture.

La suite `tests/test_card_certification.py` régénère le rapport en mémoire,
exerce chaque carte et vérifie que les deux artefacts versionnés correspondent
exactement au résultat courant.
