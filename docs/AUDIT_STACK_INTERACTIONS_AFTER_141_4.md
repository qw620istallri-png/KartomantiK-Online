# Audit des interactions avec la Pile après 141.4

Lot local, sans changement de version et sans push. Il complète le lot des puissances continues conservé dans ce même checkout. Le contrat indépendant est `audit/stack-interactions.json` ; les preuves sont dans `reports/systematic-audit/stack-interactions-followup/`.

## Périmètre sélectionné

Treize cartes, dix-huit clauses imprimées sélectionnées : Neutralize, Deny, Ignore, Veer the Will, Compensate, Imitate, Malaleuco, Scrambling Beacon, Nullifying Radiance, Wall off, Eorthoda, Simulacrum of Clemency et Duel Honorably.

Pour Malaleuco, seule la copie activée depuis l’Interzone est sélectionnée. Pour Beacon et Radiance, le lot porte sur leur activation de réponse ; les marqueurs et la couleur initiale sont des états contrôlés. Les autres paragraphes de ces cartes ne sont pas certifiés par cette sélection. Les quatorze scénarios existants de paiement de Duel sont réutilisés explicitement, sans les présenter comme de nouveaux tests.

Les coûts, catégories de cibles, bénéficiaires et destinations attendus sont écrits dans le contrat indépendamment des métadonnées du moteur. Le texte du catalogue est épinglé par empreinte SHA-256. Deux tests de sensibilité injectent un coût et une destination erronés pour vérifier que les oracles les détectent.

## Corrections

- **Nullifying Radiance** : la couleur choisie était perdue si sa source quittait le champ avant la résolution. L’activation conserve la couleur comme référence de secours ; si la source est toujours présente, la validation continue à lire son choix actuel. Un parcours joue réellement Defer en réponse pour enlever Radiance avant sa résolution.
- **Simulacrum of Clemency** : lorsque la Volonté liée avait disparu ou était devenue non neutralisable, le jeu proposait encore un choix dont les deux branches donnaient cinq points. Le gain se fait maintenant sans cette confirmation inutile et sans épuiser Clemency.
- **Catégorie des copies** : les copies de Volontés étaient exclues des cibles « carte sur la Pile ». Le serveur et l’interface les reconnaissent désormais comme cartes/Volontés ; Ignore ne les traite pas comme des effets détachés. Une autre copie peut les cibler et Thoughtcutter les compte.
- **Propriété des copies** : la copie héritait du propriétaire de l’original. Elle appartient désormais à son créateur : il paie Deny et reçoit le remboursement de Compensate, calculé sur le tribut imprimé, malgré le coût de copie nul. L’original conserve son propriétaire.
- **Résolution des copies Persistantes** : elles disparaissaient sans rejoindre le champ. Elles entrent maintenant comme jetons de Volonté Persistante et utilisent le circuit normal d’entrée, y compris les déclenchements et le transfert de Protection. Leur neutralisation/disparition ne crée aucune carte réelle au Limbo, en Main ou en Exil.
- **Réservation de Main** : une copie pouvait réserver à tort une vraie carte homonyme dans la Main de son contrôleur. Les copies sont exclues de cette réservation de source physique.
- **Eorthoda** : sa protection de tribut était un effet séparé, donc trop tardive. Le producteur de l’événement de tribut l’applique désormais dans la déclaration publique atomique, avant toute réponse, sans ajouter d’objet à la Pile ni de choix d’ordre. La Protection de la Persistante est transférée au champ jusqu’à la fin du tour et peut être retirée par Cleanse.

Les trois derniers arbitrages du créateur sur la propriété, la catégorie des copies et le timing d’Eorthoda sont enregistrés dans `audit/rule-decisions.json`. Les textes de Faroc-Ko et Philfer ont aussi été examinés : leurs valeurs de tribut sont déjà statiques, sans capacité déclenchée encodée. Cela ne constitue pas une nouvelle certification de ces deux cartes.

## Vérifications ciblées

- **129 méthodes de famille** : coûts exacts, refus atomiques, catégories, priorité, source absente/cachée/privée d’effets/épuisée, cibles disparues ou protégées, payeur, remboursement, copie de copie, effets appliqués aux bonnes cibles et nettoyage des zones.
- **12 scénarios de déclenchement** : véritables déclarations payées et producteur public de tribut/Volonté jouée, timing d’Eorthoda, transfert/expiration/Cleanse, choix de Clemency, épuisement, contrôle, réponses invalides et doubles réponses, timing de Duel.
- **17 parcours à deux connexions WebSocket**, avec un client à états différentiels et un client ancien : déclarations payées, réponses, choix, passes de priorité, valeurs finales et états reçus des deux côtés. Deux parcours créent réellement une copie par Imitate, puis la ciblent avec Neutralize ou Compensate.
- **Deux tests de sensibilité** et **14 scénarios existants de Duel** : soit **174 cas liés au lot**.
- **100 contrôles Chrome** : dix cartes de réponse, cinq états de cible dont une copie, aux formats PC et mobile paysage. Ils vérifient les candidats réels de l’interface à partir de la sérialisation publique.
- **608 scénarios de parité interface/serveur** passent. Le contrôle de continuité des choix passe également. Un ensemble voisin de 139 tests Python passait avant les dernières précisions sur les copies ; la suite générale ci-dessous revalide ensuite ces sources finales.

## Limites des preuves

Les actions originales en attente sont des états contrôlés ; les réponses utilisent les déclarations, coûts et résolutions de production. Les déclenchements passent par le producteur public, car une déclaration Session isolée ne produit pas elle-même les événements normalement ajoutés par le serveur. La protection intrinsèque d’Eorthoda est appliquée dans cette même opération publique, avant diffusion ou réponse adverse.

L’avance automatique des phases est désactivée dans les dix-sept parcours réseau pour isoler la Pile. Ces parcours ne certifient pas une partie complète. Les contrôles Chrome portent sur les filtres de cibles, avec illustrations locales ; ils ne certifient ni Safari réel, ni les illustrations distantes, ni un appareil physique. Les copies Persistantes sont vérifiées avec Hermetic Hourglass et avec l’entrée à trois marqueurs de Scrambling Beacon, pas avec toutes les Persistantes du catalogue.

Les journaux avant correction conservent les régressions Radiance, Clemency, propriété/timing et copie Persistante. Certains premiers essais avaient aussi des erreurs de banc (producteur public omis, alias manquant, mauvais nom de RPC, filtre UI oubliant `stack_item`) ; elles sont distinguées des corrections du jeu et ne constituent pas des défauts supplémentaires.

## Bilan final

**4189/4189 tests Python passent**, aucun échec ni test ignoré, en **665,682 secondes**. Les **174 cas du lot** et les liens des dix-huit clauses sont assemblés depuis cette exécution générale, sans relancer les parcours pour produire le rapport. Les 100 contrôles Chrome restent liés aux empreintes actuelles de leur périmètre ; les empreintes du lot visuel précédent des puissances continues restent également inchangées.

Le registre strict atteint **216/450 cartes (48 %)** avec au moins une clause explicitement reliée à des tests réussis, soit **treize nouvelles cartes** et **234 hors registre**. Ce décompte ne certifie pas tous les effets de ces 216 cartes. Aucun lien de preuve n’est exclu de cette collecte. Suite générale, clauses du lot, précontrôle et registre partagent l’empreinte `6bf2cb5c72398414778b75017fc86e4bdf5a523b682a0d9e525339df52dc7741`.

Les corrections du présent lot et celles des puissances continues restent locales, au-dessus du commit publié `ebeb398fc3cd4b3a54142074104f92e309e552c9` (141.4). **Aucun commit ni push.**
