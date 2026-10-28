# Défausse remplacée suivie de pioche

Les précisions du créateur du 28 octobre 2026 ferment les questions laissées
ouvertes par les lots précédents : une défausse de Main redirigée en Suspension
ou en Exil satisfait la condition permettant de piocher ; **l'errata Bêta prime
sur l'ancienne impression d'Alchemical Press**. Son ordre corrigé est bien
défausse, puis pioche, comme dans le catalogue actuel EN/FR/IT du dépôt.

Ces décisions sont conservées dans `audit/rule-decisions.json`. Les attentes
manuelles de `audit/conditional-discard-draw.json` demandent une carte défaussée,
puis deux cartes pour Pray the Ether et une pour Alchemical Press. Les capacités
du moteur ne fournissent pas ces quantités.

## Résultat et branches

Le chemin actuel respecte déjà ces décisions grâce au correctif précédent du
sélecteur commun. **Aucune nouvelle correction du moteur ni du catalogue n'est
nécessaire pour ces branches.** La condition porte sur l'action de défausse
effectuée, et non sur l'arrivée finale de la carte au Limbo.

La pioche suivante conserve ses contraintes : un blocage empêche les sorties du
Deck ; Kanon ouvre son choix ; BOB peut suspendre les cartes à piocher. Une Main
restant vide ne prouve donc pas que la pioche a été omise. Les tests vérifient
aussi le Deck et les cartes suspendues.

Les **70 scénarios de famille** croisent les deux cartes avec cinq destinations :
Limbo ordinaire, Exil seul, Suspension seule et chacun des deux résultats d'un
conflit BOB/exil. Chaque profil est vérifié avec Deck normal, limité à une carte
ou vide, deux copies identiques en Main, blocage de pioche et Kanon.

Les autres cas vérifient les refus atomiques de sélection invalide ou du mauvais
joueur, l'ordre incomplet des remplacements, les confirmations rejouées, le
choix ordinaire après aller-retour JSON et l'indépendance de la source partie.
Aucune pioche n'a lieu si la défausse est impossible (Main vide ou immunisée).
La Main adverse reste inchangée et ce déclenchement de Press ne dépense aucun
marqueur Formule.

Les **six parcours WebSocket** couvrent chaque carte face à l'Exil avec Kanon,
à BOB seul et au conflit BOB/exil. Pour Press, une vraie déclaration de Pray
déclenche l'offre optionnelle. Le joueur accepte, ordonne la Pile et résout
Press avant Pray. L'action Pray sous-jacente reste sur la Pile pour isoler et
vérifier le résultat de Press.

Les choix refusent une sélection vide et ne déplacent rien avant confirmation
de l'ordre des remplacements. Une reconnexion à cette étape conserve la
continuation. Les identifiants privés du Deck de Kanon ne sont transmis qu'au
joueur concerné. Une confirmation consommée ne redéfausse ni ne repioche. Les
deux clients, incrémental et ancien, reçoivent les états ; la phase reste stable
et son pilote automatique est isolé.

Les premiers essais réseau de Pray réutilisaient une déclaration de préparation
sans rétablir la priorité avant la déclaration réelle : le serveur la refusait
correctement. Le banc restaure désormais la priorité de départ. Cet ajustement
n'est pas présenté comme un défaut du jeu.

## Preuves et limites

`python tools/card_conditional_discard_audit.py` produit les
[76 exécutions par clause](../reports/systematic-audit/conditional-discard-followup/clauses.json).
Le [registre](../reports/systematic-audit/conditional-discard-followup/EXECUTIONS.md)
et `evidence.json` relient résultats, arbitrages, sources et compteur strict.
Ces deux cartes étaient déjà comptées : ce lot renforce leurs branches.

La suite complète finale réussit **2 733 méthodes Python distinctes**, sans
échec ni test ignoré. Les trois suites client passent aussi, dont 608 scénarios
de parité. Le registre strict reste à **120/450 (26,7 %)** avec au moins une
clause sélectionnée vérifiée par carte, sans certification exhaustive.

Les remplacements sont des états contrôlés. Les tests unitaires de Press isolent
son action ; les parcours réseau en vérifient le producteur réel. La reconnexion
ne certifie pas un redémarrage du serveur ni une restauration de sauvegarde.
Les autres capacités de Press, les réactions d'autres cartes à une défausse
remplacée et toutes les combinaisons possibles restent des contrôles distincts.
Aucun nouveau test UI de carte, Safari, appareil physique ou illustration.

Aucun changement VFX, client, version, commit ou push. Les corrections locales
des lots antérieurs sont conservées.
