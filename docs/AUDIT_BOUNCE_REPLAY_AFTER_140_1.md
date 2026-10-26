# Retours en main et interdictions de rejouer — suite locale

Cette passe ajoute 24 méthodes, dont deux scénarios réseau à deux sièges,
pour six paragraphes sélectionnés de Pigon, Chiff and Chaff, Atavic
Introspection et Abandon. Les attentes sont écrites à partir du texte imprimé ;
les actions utilisent les définitions livrées. Le lien explicite entre chaque
paragraphe et ses assertions est dans
[clauses.json](../reports/systematic-audit/bounce-replay-followup/clauses.json).

## Écarts reproduits et corrigés

| Chemin | Avant | Après |
| --- | --- | --- |
| Déclaration de jeu depuis la main | Le déplacement manuel et Chain respectaient l'interdiction, mais la déclaration directe sur la pile la contournait | La validation de source refuse aussi cette déclaration avant tout paiement ou déplacement |
| Disponibilité d'un Soutien en main | Une carte interdite pouvait compter comme action disponible pour le passage automatique | Le calcul de disponibilité respecte le même verrou ; une autre copie libre reste jouable |
| Chiff and Chaff | Son retour en main pouvait se déclencher à l'entrée en Soutien d'une autre carte | Le déclenchement est limité à sa propre entrée en Soutien |

La reproduction avant correction est conservée dans `before.json` : 22 méthodes,
17 réussies et cinq en échec, avec 12 échecs de sous-cas. Cette preuve garde son
empreinte historique. Les deux méthodes réseau ont été ajoutées ensuite.

## Branches vérifiées

- Pigon : paiement de deux essences et épuisement avant réponse, cible en
  Soutien, refus d'une source épuisée, absence de remboursement si la cible
  disparaît, poursuite de la résolution après départ de la source.
- Chiff : condition préparée avec une entrée adverse depuis l'Interzone ;
  entrée propre mettant le retour sur la pile sans déplacer la cible avant
  résolution ; absence de déclenchement lorsqu'une autre carte entre.
- Atavic : paiement d'exactement cinq marqueurs Contrôle avant réponse,
  refus atomique à quatre, conservation du sixième marqueur et retour d'une
  Manifestation en Interzone.
- Retours ciblés : destination du propriétaire même sous contrôle adverse,
  verrou créé seulement après déplacement effectif, cible disparue ou Protégée,
  copies libres et interdites, interdiction de Chain depuis la main, expiration
  au tour suivant et perte du bonus de terrain après retour. Cleanse sur la
  source et son départ ne retirent pas l'interdiction de rejouer. Une activation
  de défausse depuis la main reste possible : elle ne joue pas la carte.
- Abandon : seuls les Soutiens du joueur ciblé reviennent, chacun à son
  propriétaire ; Adamant adverse empêche le retour mais Adamant propre ne
  l'empêche pas ; deux copies retournées restent interdites après le jeu d'une
  troisième copie libre ; aucun faux retour ou verrou pour les jetons et aucune
  demande vide lorsque le joueur n'a pas de Soutien.

## Protocole réseau

Le premier scénario active réellement Pigon, vérifie la présence de la cible
avant les passes, résout le retour, reconnecte le propriétaire et refuse le
rejeu sans mutation. Une avance de tour explicite de fixture permet ensuite
le jeu et vérifie la puissance imprimée, sans l'ancien bonus.

Le second prépare l'entrée réelle de Chiff et son déclenchement, résout le
retour, joue une autre copie identique par le protocole puis refuse la copie
interdite. Il vérifie l'absence de nouvelle pile ou de choix intempestif de
Chiff. Les passes réseau attendent leur accusé avant d'envoyer la suivante.
Le pilote automatique est désactivé dans ces deux scénarios pour isoler le
protocole ; ce ne sont pas de nouvelles preuves de cadence des résolutions.

## Limites

Certaines résolutions sont isolées de leur déclaration et de leur coût. Les
Manifestations synthétiques servent de cibles, sans remplacer les capacités
réelles des cartes auditées. L'identité des copies après des déplacements entre
zones cachées, la remise à zéro des mémoires au Deck/Exil et les sources de Chain
autres que la main restent hors de ce lot.

La condition de Chiff est vérifiée avec les entrées enregistrées au tour
courant ; sa portée entre plusieurs tours n'est pas certifiée. Les neuf
définitions `enters_support` ont été inspectées, mais seules les branches
sélectionnées de Chiff ont de nouvelles assertions indépendantes ici. Les autres
paragraphes d'Atavic ne sont pas certifiés par analogie.

Les anciennes campagnes de rendu des 450 cartes, les illustrations distantes,
les appareils physiques et Safari Mac réel ne sont pas rejoués par cette passe.
Les registres des campagnes précédentes restent historiques. La version 140.1
est conservée ; aucun commit ni push.

Commande ciblée : `python tools/card_bounce_replay_audit.py`.
Les résultats de régression et leurs empreintes sont conservés séparément dans
[le registre d'exécution](../reports/systematic-audit/bounce-replay-followup/EXECUTIONS.md).

## Validation finale

Les 24 tests ciblés et les 1 388 tests de la suite Python complète réussissent,
sans échec ni test ignoré. Les quatre suites UI réussissent : parité des règles,
continuité des choix, frontend et interface sémantique. Ces preuves portent la
même empreinte des sources. Le contrôle `git diff --check` ne relève pas
d'erreur ; Git annonce seulement les conversions LF/CRLF habituelles.
