# Mode manuel par côté et entrées sur le champ

## Correction du mode manuel

Dans le mode manuel, le total de puissance ne consulte plus le propriétaire ou
le contrôleur de la carte. Une Manifestation face visible est comptée pour le
joueur correspondant au côté physique de la zone de Confrontation où son centre
est placé. Déplacer une carte sur le côté adverse transfère donc immédiatement
sa puissance au total adverse, ce qui permet de gérer manuellement les
changements de contrôle.

Le mode assisté reste autoritaire et continue d'utiliser `controllerId`.

## Couverture ajoutée

- 13 cartes avec une clause imprimée « enters the field ».
- Événement compilé exact, entrée face visible obligatoire et début du chemin
  de résolution réel sans cible invalide.
- Les branches complètes des effets restent couvertes par les scénarios
  spécifiques des cartes et ne sont pas déclarées certifiées par ce lot.

## Validation

- Suite complète : **4 353/4 353 tests Python uniques réussis**.
- Zéro échec, test ignoré ou identifiant dupliqué.
- Registre strict : **298/450 cartes (66,2 %)**.
- Inventaire restant : **152 cartes**.
- Régression navigateur du mode manuel, frontend général, continuité des choix
  desktop/mobile et parité client/serveur exécutées séparément.

La preuve complète consolidée la plus récente est conservée dans
`../solo-mode-followup/unit-tests.json`.
