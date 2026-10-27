# Atavic Introspection : un seul Limbo, Deck du propriétaire

Les deux arbitrages du créateur sont conservés dans
`audit/rule-decisions.json`, sous `atavic-introspection-single-limbo` :

- Les deux cartes peuvent provenir du propre Limbo ou du Limbo adverse, mais
  doivent être choisies dans un seul et même Limbo.
- Elles rejoignent le Deck de leur propriétaire d'origine. Le contrôleur
  d'Introspection choisit leur ordre, même lorsqu'il ne possède pas ces cartes.
  Le raccourci imprimé « your deck » ne déroge pas à la propriété des zones.

## Correction

La définition limitait les cibles au propre Limbo par `container: self`.
Cette restriction est remplacée par `sameContainer: true`, déjà pris en charge
par le serveur et le client pour Caress the Spirit. Le contrôle des cibles et
celui de disponibilité d'un déclenchement imposent une paire légale dans un
unique Limbo ; une carte disponible de chaque côté ne suffit pas.

Le mécanisme de placement au-dessus/au-dessous du Deck était déjà associé au
propriétaire du Limbo sélectionné. Il est conservé, ainsi que les protections
de propriété des zones ; aucune exception autorisant les cartes adverses dans
le Deck du contrôleur n'est introduite.

L'écran de répartition depuis le Limbo montre maintenant explicitement
« Limbo de [joueur] → son Deck », y compris dans la nouvelle interface où le
titre générique du choix n'est pas toujours affiché. Les instructions sont
disponibles en français, anglais et italien. La traduction française de la
carte disait à tort « vos Limbes » ; elle indique désormais « un même Limbo ».
Le texte anglais imprimé reste inchangé, avec l'arbitrage de propriété prioritaire.

## Preuves

La reproduction initiale porte sur six méthodes, dont trois en échec : l'offre
et le ciblage refusaient le Limbo adverse. `before.json` conserve cette empreinte
historique. Trois méthodes supplémentaires complètent ensuite la vérification
des destinations, du changement de contrôleur et du protocole réseau.

Les neuf méthodes ciblées vérifient : disponibilité dans chaque Limbo,
interdiction des sélections mélangées, absence de choix impossible à une carte
de chaque côté, ordre dessus/dessous dans les deux sens, Deck du propriétaire
et conservation des cartes des autres zones.

Le scénario réseau utilise deux vrais sockets, un client incrémental et un
ancien client. Le contrôleur choisit dans le Limbo adverse ; une tentative de
mélange est refusée sans mutation. La sélection reste en place avant résolution,
le choix d'ordre survit à la reconnexion, le propriétaire des cartes ne peut
pas répondre à la place du contrôleur, et une réponse répétée ne déplace rien.
Le Deck adverse reste privé dans les états envoyés au contrôleur.

Six configurations Chrome croisent trois langues avec PC et mobile paysage.
Chaque configuration contrôle les cas des deux propriétaires, soit douze
confirmations réelles du bouton, son verrouillage et le destinataire envoyé.
Ces essais utilisent des fixtures d'interface explicites et des illustrations
locales ; ils sont distincts du scénario réseau.

Les associations au paragraphe imprimé et à l'arbitrage sont dans
`reports/systematic-audit/atavic-limbo-followup/ruling.json`. Commande ciblée :
`python tools/card_atavic_limbo_audit.py` ; interface :
`node tests/test_atavic_limbo_ui.cjs`.

## Limites

Les essais réseau préparent explicitement l'événement de fin de tour et isolent
le passage automatique. La sélection de copies identiques et le placement après
invalidation partielle ne sont pas certifiés par ce lot. Aucune nouvelle campagne
générale des 450 cartes, contrôle d'illustrations distantes ou certification de
Safari Mac/appareil physique n'est revendiquée.

Les preuves de la première passe Atavic restent historiques. Les corrections de
cette passe et celles d'Oppression restent locales après la publication 140.3,
sans commit ni push supplémentaire.

Validation finale : **1 440 tests Python réussis**, aucun échec ni test ignoré,
ainsi que six suites navigateur et une suite JavaScript du transport. Les
empreintes, résultats et limites sont conservés dans
[le registre d'exécution](../reports/systematic-audit/atavic-limbo-followup/EXECUTIONS.md).
