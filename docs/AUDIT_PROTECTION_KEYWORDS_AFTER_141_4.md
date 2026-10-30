# Audit Protection, perte d’effets et capacités accordées après 141.4

Lot local sans commit, push ni changement de version. Il conserve les corrections précédentes des puissances continues et des interactions de Pile.

## Contrat sélectionné

Le fichier `audit/protection-keywords.json` contient treize cartes et dix-neuf clauses sélectionnées. Les attentes de destinataire, paiement, effets et durée sont écrites depuis les textes imprimés, indépendamment des métadonnées exécutées. Le texte complet de chaque carte est épinglé par SHA-256.

| Carte | Clauses et branches sélectionnées |
|---|---|
| Armored Husk | Protection de la cible à l’entrée ; épuisement et paiement d’une essence phlegmatique pour changer de cible en Phase Finale. |
| Altruistic Inflorescence | Support accordé à l’entrée ; changement de cible contre épuisement et trois essences phlegmatiques en Phase Finale. |
| Flaying Jaw | Malus de −2 à l’entrée ; changement de cible contre épuisement et une essence mélancolique en Phase Finale. |
| Annihilating Nectar | Perte d’effets à l’entrée ; changement de cible contre épuisement et une essence capricieuse en Phase Finale. |
| Nullify | Manifestation ou Volonté Persistante privée de ses effets, sauf paiement de deux essences creuses par son propriétaire. |
| Float | Float accordé à une Manifestation ciblée, conservé après la fin du tour et retiré par Cleanse. |
| Bivalv, the Circumspect | Défausse depuis la Main comme coût ; Protection de sa carte ciblée contre les adversaires jusqu’à la fin du tour. |
| Gladionimbus | Sacrifice depuis l’Interzone ; Float accordé aux Manifestations qui s’y trouvent sous son contrôle à la résolution. Le paragraphe Support/Float imprimé de Gladionimbus n’est pas sélectionné par ce lot. |
| Mobile Sanctuary | Protection continue des autres Manifestations de sa Confrontation, selon le contrôle actuel et l’état de sa source. |
| Rajas, Great Aegis | Source en Interzone ; Protection continue des Persistantes amies et des autres Manifestations de son Interzone. |
| Unreachable Pillar | Protection du Vaisseau contre l’adversaire et suppression des capacités de ses Manifestations. |
| Protect | Protection des Manifestations et Volontés contrôlées actuellement sur le champ, jusqu’à la fin du tour ; les arrivées ultérieures ne sont pas incluses. |
| Hot Potato | Premier paragraphe uniquement : transfert à l’adversaire avec un marqueur Burn à la résolution de son effet d’entrée. Les transferts répétés et sa pénalité finale ne sont pas sélectionnés par cette preuve. |

Onze cartes étaient hors du registre strict. Flaying Jaw et Protect avaient déjà une preuve pour certaines clauses : leurs branches supplémentaires ne sont pas recomptées comme de nouvelles cartes. Graceful Petal sert uniquement de porteur d’un véritable déclenchement de Vaisseau pour le test de Pillar ; il n’est pas ajouté au registre par cette interaction.

## Défauts corrigés

**Annihilating Nectar avait une capacité de lancement au lieu d’une capacité d’entrée.** Le producteur réel d’entrée ne trouvait aucun déclenchement, notamment pour une copie jeton. La capacité `nectar-disable-target` est désormais un déclenchement d’entrée face visible, comme son texte le demande. Une Persistante payée rejoint d’abord le champ ; le choix de cible de son effet d’entrée est ensuite demandé et l’effet attend sa résolution. Une seule application est créée.

**Hot Potato présentait le même défaut d’entrée.** La recherche dans les autres Persistantes a révélé que son premier paragraphe était aussi encodé au lancement. Son transfert initial passe maintenant par un déclenchement d’entrée face visible, y compris pour un jeton copie. La carte est encore contrôlée par son créateur avant la résolution de ce déclenchement ; elle passe ensuite à l’adversaire avec un marqueur Burn, sans changer de propriétaire. Le cas est ajouté avec sept méthodes unitaires et un parcours à deux clients. Les autres capacités de Hot Potato ne sont pas modifiées.

La recherche des textes de Persistantes contenant « When … enters the field » ne trouve plus de capacité de lancement sur ces cartes après correction. Ce contrôle structurel ne certifie pas leurs autres paragraphes. Bibi, seule Manifestation apparaissant dans la recherche élargie, possède déjà un déclenchement d’entrée séparé de son choix de contrôle au lancement.

**Les liens nécessitant source et cible sur le champ persistaient lorsque la cible rejoignait l’Impasse.** Husk, Inflorescence et Jaw reproduisaient déjà ce défaut ; Nectar utilise le même mécanisme après sa correction d’entrée. Le nettoyage retire maintenant ces liens lorsque la cible se trouve en Impasse. Il ne s’agit pas d’un effacement général des modificateurs : les copies de statistiques déjà résolues de Mimer restent exemptées, et les autres durées conservent leur comportement.

Le premier correctif avait également retiré les modifications de durée `while_target_on_field`, ce qui cassait un scénario existant de Mimer combiné à Entrust. Le contrôle voisin a détecté cette régression immédiatement. Le correctif final est limité à `while_source_and_target_on_field`, hors effets de copie ; les scénarios voisins passent de nouveau. Cet essai n’est pas présenté comme un défaut supplémentaire du jeu.

**Rajas protégeait encore une Volonté Persistante située en Impasse.** Sa branche pour les Persistantes ne vérifiait pas cette frontière du champ. Une carte qui s’y trouve ne reçoit plus cette Protection continue. Les destinataires d’Interzone et les Persistantes sur le champ restent protégés contre les adversaires.

## Vérifications exécutées

- **122 méthodes de famille** : entrée via le producteur réel, copie jeton, Persistante véritablement payée, valeurs de puissance exactes, coûts et épuisement du changement de cible, mauvaise phase, paiement absent, cible partie/protégée pendant la réponse, source partie/masquée/privée d’effets, Cleanse sur source ou cible, absence de réapplication spontanée, nouvelle entrée distincte, contrôle et propriété.
- Les modificateurs d’entrée nettoyés par Cleanse restent retirés jusqu’à une nouvelle activation. Les effets continus de Sanctuary et Rajas restent actifs après Cleanse de leur destinataire, sans objet ajouté à la Pile.
- Les effets collectifs incluent les destinataires présents lors de leur résolution, y compris ceux arrivés pendant une réponse. Ils n’incluent pas les arrivées ultérieures. Gladionimbus ne donne Float ni aux adversaires, ni aux Persistantes, ni aux cartes d’Impasse.
- **13 parcours à deux connexions WebSocket** utilisent les déclarations, paiements, choix et passes réels. Cinq paient et résolvent la Persistante, puis choisissent sa cible et résolvent son effet d’entrée. Cinq exécutent les Volontés/activations ponctuelles. Trois jouent réellement Defer pour retirer une source continue. Les états des deux clients sont vérifiés, avec un client à états différentiels et un client ancien.
- **Deux tests de sensibilité** injectent un malus de Jaw incorrect et une durée valide mais trop longue de Protect. Une vérification existante de Nectar est actualisée et réutilisée pour son entrée payée sans cible et l’absence de choix vide : **138 cas liés au lot** au total (122 nouveaux scénarios de famille, treize parcours réseau, deux tests de sensibilité et ce contrôle actualisé).
- **144 contrôles Chrome** : les douze cartes du lot initial, source active/Cleanse du destinataire/source privée d’effets, les deux points de vue et deux formats (PC et mobile paysage tactile). Ils vérifient les filtres réels de cibles, les états de capacités disponibles, les marqueurs de modificateur et le −2 affiché de Jaw. Leurs titres sont présents et aucune erreur de script n’est admise. Hot Potato possède des preuves unitaires et réseau ; elle n’est pas ajoutée artificiellement à ce décompte d’interface.
- La parité interface/serveur passe sur **609 scénarios**. Le générateur adapte ses cas à la forme des capacités ; ce compteur n’est pas un nombre de cartes et peut varier quand une capacité de lancement devient un déclenchement.

## Limites et erreurs de banc

Les états initiaux de plateau, les cibles synthétiques de puissances 3 et 4, ainsi que certains changements de contrôle/visibilité sont contrôlés. Les actions payées, producteurs de déclenchement, choix, calculs, nettoyages, sérialisation et échanges réseau utilisent le code de production. Les contrôles navigateur appellent le constructeur réel de sélection et rendent réellement le plateau ; ils ne jouent pas douze parties complètes.

Les premiers essais d’interface comparaient `itemId` alors que les candidats de champ utilisent `id`, puis attendaient encore une icône de modificateur dormant alors que l’interface masque déjà ces icônes. Ces erreurs du banc sont conservées séparément dans `browser-fixture-initial.json` et `browser-fixture-dormant.json`. Le premier test de sensibilité utilisait une durée non reconnue, supprimée par la validation ; il utilise maintenant une autre durée reconnue et vérifie la prolongation indue. Aucun de ces essais n’est compté comme défaut supplémentaire du jeu.

L’avance automatique des phases est désactivée dans les treize parcours réseau pour isoler les effets. Les illustrations sont locales ; Safari, les appareils physiques et les illustrations distantes ne sont pas certifiés par ce lot. Les preuves antérieures sont conservées avec leurs empreintes historiques ; la suite générale courante revalide leurs identifiants Python sans transformer leurs anciens contrôles visuels en nouvelles exécutions.

Une première régression générale a été interrompue pour ajouter le défaut voisin de Hot Potato découvert pendant le contrôle structurel. Son journal incomplet est conservé dans `full-aborted-for-hot-potato.log` ; il ne constitue pas une preuve de réussite. La régression finale est relancée une fois les sources complètes figées.

La régression complète suivante a exécuté 4326 tests et trouvé quatre attentes historiques à actualiser : le compteur des actions volontaires, le registre structurel généré d’automatisation, les rapports génériques des lots et une ancienne attente interdisant le lancement de Nectar sans Manifestation à cibler. Ce dernier contrôle vérifie désormais une entrée réellement payée, qui réussit sans déclenchement ciblé ni choix vide lorsqu’aucune cible n’est disponible. Les deux capacités déplacées étant désormais des déclenchements, le nombre d’actions volontaires passe de 182 à 180 ; la tolérance historique de deux déclarations non acceptées dans le banc différentiel est conservée. Les rapports générés gardent 450 cartes, 496 capacités et 500 porteurs : ce sont des contrôles génériques, pas une certification des textes complets.

Les deux contrôles ciblés et les dix contrôles des fichiers générés passent après actualisation. `unit-tests-before-refresh.json` et `full-before-refresh.log` conservent les quatre échecs historiques ; la dernière régression générale utilise les nouvelles sources et rapports. Aucun changement supplémentaire du moteur n’a été nécessaire pour ces quatre attentes.

## Bilan final

La dernière suite générale passe : **4326/4326 tests Python réussis**, aucun échec ni test ignoré, en **739,336 secondes**. Les **138 cas liés au lot** et les preuves des dix-neuf clauses sont collectés depuis cette exécution, sans réexécuter les parcours pour assembler le rapport. Les 144 contrôles Chrome et les 609 scénarios de parité restent rattachés à leurs sources vérifiées.

Le registre strict atteint **227/450 cartes (50,4 %)** avec au moins une clause explicitement reliée à des tests réussis, soit **onze nouvelles cartes** et **223 hors registre**. Aucun lien n’est exclu de cette collecte. Il ne s’agit pas d’une certification de tous les paragraphes ou de toutes les interactions de ces 227 cartes.

Suite générale, précontrôle, collecte des clauses, contrôle structurel d’entrée et registre courant partagent l’empreinte `937dee457aced052ffde2d17c763e7aada2144987705d623b07e1e8fa57e33ba`. Les essais interrompu et antérieur à l’actualisation des contrôles sont conservés comme historiques ; seule la dernière suite complète est annoncée comme réussite finale.

Tous les changements restent locaux au-dessus de 141.4, commit `ebeb398fc3cd4b3a54142074104f92e309e552c9`. **Aucun commit ni push.**
