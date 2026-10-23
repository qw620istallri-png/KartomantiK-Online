# Audit des signalements Mimer, Empathic Mask et Trap

Passe du 23 octobre 2026, après la version 139.4. Corrections intégrées à la version 139.41 à la demande du joueur.

## Copies figées à la résolution

Le catalogue utilise deux mécanismes de copie de caractéristiques : Mimer (`copy_power_temperament`) et Mirrorbeast (`copy_power_effects`). Les deux relisaient leur cible lors des calculs ; les valeurs pouvaient aussi être réécrites au départ de la cible. Mirrorbeast perdait ses capacités copiées quand cette cible quittait le champ.

Les caractéristiques sont désormais mémorisées lors de la résolution, avec les règles copiées pour Mirrorbeast. La lecture de l'état, les changements de la cible, son nettoyage, sa sortie vers les Limbes ou sa suspension ne réécrivent pas la copie. Une nouvelle activation de Mimer prend de nouvelles valeurs. Ses propres modificateurs continuent de s'appliquer. Mirrorbeast conserve sa copie jusqu'à son échéance ; le client utilise également les capacités mémorisées. Nettoyer le copieur retire bien sa copie.

L'ancien test qui mémorisait les valeurs au départ de la cible a été corrigé pour refléter la précision du joueur : la référence est la résolution. Les autres copies de cartes et de Volontés n'utilisent pas ce lien dynamique de caractéristiques.

## Choix d'activation et couleurs

Les sept cartes possédant plusieurs activations ont été examinées : Malaleuco, Zum, Empathic Mask, Bizarre Mechanism, Sandokaron, Haltan et Shattered Memory.

- Les actions encore identifiées par un numéro reçoivent un nom explicite en anglais, français et italien. Les actions de Malaleuco étant disponibles dans des zones différentes, elles ne forment pas un choix simultané ; leurs noms sont néanmoins explicites.
- Sandokaron conserve ses deux choix de Bannières. Empathic Mask conserve les noms et symboles des cinq tempéraments.
- Bizarre Mechanism proposait les trois effets même lorsque le nombre de compteurs Enigma ne les autorisait pas. Les boutons et le contrôle d'auto-passe respectent maintenant `requireSourceCounter`. La troisième activation exige aussi une carte en main avant d'être proposée.
- Le marqueur de tempérament déjà ajouté utilise les caractéristiques effectives du serveur, reste absent sur les cartes face cachée et disparaît quand le changement expire. Il couvre aussi les copies de tempérament de Mimer.

## Inspection

Le défaut de Trap venait de sa représentation séparée, sous la couche d'interaction du plateau. Les clics et menus sont routés par cette couche. Les tests PC/mobile couvrent les Traps révélés des deux joueurs, le Trap couvert de son propriétaire et la confidentialité du Trap adverse.

Les autres surfaces examinées disposent de chemins distincts : cartes ordinaires du champ, cartes suspendues, sources de Stack, références du journal et sources de choix avec aperçu. Aucun autre blocage similaire n'a été reproduit sur ces chemins. Les tests existants de suspension couvrent aussi les entrées privées désactivées.

## Chain et mises en jeu directes

Slumberer et Juggernut portent tous deux `playAsPersistentWill`, mais le contrôle de Chain ne vérifiait que leur type Manifestation. Ils sont désormais exclus des candidats de Chain depuis la main, le Deck, les Limbes et le Réceptacle ; une requête directe est également refusée sans déplacer de carte. Une sélection refusée conserve son choix en cours.

Le repli de Womb s'applique quand la main ne contient que ces cartes et ne permet donc aucun Chain. Les mises en jeu directes restent indépendantes : les tests jouent l'activation réelle d'Urolong et vérifient qu'elle peut toujours mettre ces deux cartes en Soutien, privées d'effets comme son texte l'exige.

## Vérifications

- Suite Python complète : **829 tests réussis**.
- Régressions dédiées : `test_mimer_snapshot.py` et `test_copy_chain_followup_audit.py`.
- Parcours navigateur PC/mobile : libellés dans les trois langues, conditions de compteurs, capacités copiées, symboles de tempérament et inspection des Traps.
- Régressions générales de l'interface, catalogue de 496 capacités / 500 variantes / 379 cartes et contrôle du registre d'automatisation.

Ces contrôles couvrent les familles signalées et les cas voisins identifiés ; ils ne constituent pas une preuve exhaustive de toutes les interactions possibles du jeu.
