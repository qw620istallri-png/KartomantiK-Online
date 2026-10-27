# Réduction du trafic WebSocket

Les diffusions précédentes envoyaient un état complet, filtré selon les droits
du destinataire, à chaque connexion. Celui-ci comprend notamment les zones,
définitions de Deck, pile, effets et les trente dernières entrées du journal.
La compression `deflate` était déjà active. Cette modification conserve les
règles et la présentation de chaque résolution ; elle change le transport.

## Mesure initiale

Une partie synthétique locale à deux sièges, avec 101 diffusions, produit
202 messages et environ 2,84 Mo de JSON. Le relevé effectué avant modification
est conservé dans `reports/network-usage/before.json`, avec l'empreinte du
serveur d'origine. Il ne s'agit pas du trafic capturé sur Render.

## Protocole et compatibilité

Le client demande `stateDeltaVersion: 1` dans son message `join`. Un serveur
compatible confirme cette version. La première synchronisation reste un état
complet, avec `stateRevision`. Les suivantes peuvent être des `state_patch`
contenant la révision de départ, la suivante et des opérations :

- `set` remplace une valeur ou un tableau ; les objets sont comparés par champ.
- `delete` retire une propriété devenue absente.
- `log_tail` retire le début périmé du journal visible et ajoute seulement les
  nouvelles entrées, dans leur ordre d'origine.

Un patch plus volumineux que l'état complet est remplacé par un état complet.
Une diffusion dont l'état visible est inchangé est omise. Chaque changement de
pile, résultat ou journal reste livré séparément ; aucun délai de résolution
n'est retiré et aucun regroupement de plusieurs résolutions n'est ajouté.

Le client reconstruit d'abord l'état entier, puis utilise le même rendu qu'avant.
Sa référence réseau est distincte de l'objet modifiable par l'interface. Une
révision manquante ou un patch invalide suspend l'application des patches et
demande un seul `request_state` jusqu'à réception d'un nouvel état complet.
Le patch est atomique : une opération invalide ne laisse pas de modification
partielle dans l'interface.

Un ancien client conserve les états complets habituels. Un nouveau client
fonctionne également avec un ancien serveur. `KKO_STATE_DELTAS=0` désactive la
négociation côté serveur, pour revenir aux états complets lors des nouvelles
connexions. Un redéploiement ferme les sockets existantes et fait renégocier
les clients à leur reconnexion.

## Droits, concurrence et reconnexion

La comparaison est calculée **après** `serialize_for`, indépendamment pour
chaque socket. Aucun historique privé n'est partagé entre connexions. Les
droits existants restent inchangés : l'adversaire et le spectateur de tournoi
n'obtiennent pas les choix privés ; l'observateur amical demeure un lecteur
privilégié selon les règles déjà en place.

Un verrou par socket ordonne les envois concurrents. La référence et la
révision n'avancent qu'après un envoi réussi. Les vues en attente provenant
d'une ancienne session ou d'un ancien rôle ne sont pas envoyées après un
nouveau `joined`. Chaque reconnexion ou changement de siège repart avec une
référence neuve et un état complet. Les listes du moteur sont figées sous leur
forme JSON avant le premier `await`.

## Lecture des compteurs dans Render

Les logs serveur contiennent des lignes `ws_traffic`. Elles sont agrégées au
plus une fois par minute, lors du prochain message après cet intervalle :

- `measurement: utf8_json_before_compression` : unité de mesure explicite.
- `totals.jsonBytes` : octets JSON effectivement transmis par l'application,
  avant compression ; les autres réponses WebSocket sont incluses.
- `totals.fullStateJsonBytes` : volume théorique des diffusions d'état si elles
  étaient toutes restées complètes. Les autres types de messages n'y sont pas
  inclus.
- `full`, `patch`, `unchanged`, `otherMessage` : nombres d'états complets,
  patches, diffusions inchangées omises et autres réponses.
- `byAction` : répartition selon la commande entrante, par exemple
  `set_activity`, `pass_priority` ou `resolve_rules_choice`. Les tâches sans
  commande associée sont regroupées sous `background`.

Ces logs ne contiennent ni contenu des cartes, ni noms de joueurs, ni codes de
partie. Le nombre de catégories est borné. **Leurs octets JSON ne sont pas les
octets facturés par Render** : compression, trames, keepalives et couches réseau
doivent être distingués. Le compteur Render reste la référence de facturation.
Les derniers messages d'une période inactive ne sont agrégés qu'à la reprise
du trafic ; il ne s'agit pas d'un export comptable complet.

## Vérification reproductible

`python tools/network_usage_audit.py` exécute six fixtures : actions mixtes,
mode manuel, journal, ordre du Deck, diffusions inchangées et 33 résolutions de
pile. Le véritable diffuseur produit les messages complets et incrémentaux.
Le vrai décodeur JavaScript reconstruit les 1 078 états attendus.

Le benchmark mesure aussi l'encodage local des trames avec la bibliothèque
WebSocket installée : `deflate`, fenêtres de 12 bits, conservation du contexte
et `memLevel: 5`. Les en-têtes WebSocket sont inclus, les couches TCP/TLS et
keepalives sont exclus. La négociation réelle et les parties réelles peuvent
produire d'autres ratios. Aucun gain mensuel précis n'est garanti.

Les tests dédiés couvrent les anciennes et nouvelles versions, les droits,
reconnexions, demandes de resynchronisation, envois concurrents, échecs d'envoi,
journal tronqué et changements de type JSON. Deux clients réseau en versions
différentes observent chacune des 33 résolutions. Les tests navigateur vérifient
la réception normale, la détection d'un trou de révision et la reprise.

Les résultats et empreintes sont conservés dans `reports/network-usage/`.
Version inchangée ; cette modification reste locale jusqu'à une demande de push.

Cette étape de développement est ensuite intégrée à la
[publication 140.3](RELEASE_140_3.md). Les preuves ci-dessus conservent leur
empreinte antérieure à la mise à jour des versions de ressources.

Validation finale : **1 409 tests Python réussis**, aucun échec ni test ignoré,
ainsi que 14 suites navigateur et une suite JavaScript du transport. Le parcours
à deux vrais navigateurs réussit deux actions et deux choix privés avec
reconnexion. Les preuves portent la même empreinte des sources dans
[le registre d'exécution](../reports/network-usage/EXECUTIONS.md).
