# Bêta 139.45 — choix, paiements, synchronisation et effets immédiats

Cette version regroupe les corrections des audits réalisés après 139.44.

## Corrections

- **Choix et cibles** : conservation des groupes de cibles, validation des rôles
  et exclusions, suppression des choix devenus impossibles et reprise des
  déclenchements différés. Une copie de Stack conserve ses cibles héritées et
  applique les règles normales de résolution partielle.
- **Paiements** : sélection explicite des Essences blanches pour les paiements
  demandés par des effets, conversions de compteurs et recherche d'un paiement
  légal tenant compte des sources et coûts spéciaux.
- **Fin de partie** : arrêt des choix, continuations et résolutions après la fin,
  avec conservation du plateau et de la Stack pour consultation.
- **Déplacements** : nettoyage des fantômes translucides, surbrillances et
  aperçus après interruption ou reconstruction du plateau. Les gestes de choix,
  d'entrée en Support, de réordonnancement et de jetons sont également couverts.
- **Reconnexion** : les anciens sockets ne remplacent plus l'état récent et ne
  relancent plus une reconnexion. Les validations différées sont annulées au
  départ ou à la déconnexion ; elles ne partent plus vers une autre partie.
  Fermer une ancienne connexion ne marque plus déconnecté un siège encore actif.
- **Suspend** : les Volontés de Gobres retiennent la priorité lorsqu'elles sont
  jouables. Leur identifiant de suspension est transmis et validé ; leur source
  devient publique après leur jeu sur la Stack. L'aura de jouabilité respecte
  leurs conditions. BOB exige ses effets actifs pour appliquer son seuil d'exil.
- **Effets immédiats** : résolution avant la recherche de réponses ordinaires,
  refus des déclarations et passes pendant leur résolution, interface adaptée
  et maintien des choix de paiement internes après reconnexion.
- **Animations** : nettoyage des cartes retenues, créations visuelles différées,
  aperçus et verrous de Main à la déconnexion ou au changement de partie.

## Validation

- **965 tests Python réussis**, moteur et parcours WebSocket réels.
- Régressions Chrome générales et ciblées : reconnexion, Suspend, effets
  immédiats, déplacements et paiements d'Essence blanche ; parcours PC/mobile.
- Répartition Ponderer vérifiée sur trois formats d'écran.
- Ressources HTML, application, service worker et README synchronisés en
  `20261023-rules-beta-139-45`.

Les détails et limites de chaque passe figurent dans les quatre rapports
`AUDIT_*_AFTER_139_44.md` livrés avec cette version.
