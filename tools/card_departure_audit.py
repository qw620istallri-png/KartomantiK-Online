"""Run the bounded source/target departure audit and retain actual evidence.

python tools/card_departure_audit.py
Exit 0 certifies the bounded cases below, not the entire card catalog.
"""
import hashlib
import json
import sys
import unittest
from datetime import datetime, timezone

from run_card_audit import ROOT, EvidenceResult
import card_behavior_audit as audit


def main():
    start_digest = audit.digest()
    sys.path.insert(0, str(ROOT / "tests"))
    patterns = ("test_departure_resolution_audit.py", "test_departure_resolution_integration.py", "test_departure_rulings.py")
    for pattern in patterns:
        if not (ROOT / "tests" / pattern).is_file():
            raise RuntimeError("Missing departure proof: " + pattern)
    suite = unittest.TestSuite(unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern=pattern) for pattern in patterns)
    result = unittest.TextTestRunner(verbosity=1, resultclass=EvidenceResult).run(suite)
    cards = []
    for cid in ("inner-deserts-012", "inner-deserts-036", "pgvrly9397pua77_en", "pwsjhnw4vpvqgkv_en", "inner-deserts-145", "1q6crbc7nwugrgs_en",
                "inner-deserts-038", "inner-deserts-014", "9ypw4x4igfon1qi_en", "0coh7nrbvcvan1i_en", "z2fen73ktw8pbqz_en", "inner-deserts-019", "ud9clfoj2c6x96o_en"):
        card = audit.batches.CATALOG.cards[cid]
        text = card.get("effect") or ""
        cards.append({"cardId": cid, "name": card["name"], "printedText": text,
                      "printedTextSha256": hashlib.sha256(text.encode("utf8")).hexdigest(),
                      "allClausesAndBranchesCertified": False})
    required_rulings = {"source-power-after-departure", "limbo-target-roundtrip"}
    decisions = json.loads(audit.DECISIONS.read_text(encoding="utf8"))["decisions"]
    resolved_rulings = [r for r in decisions if r["id"] in required_rulings]
    if {r["id"] for r in resolved_rulings} != required_rulings:
        raise RuntimeError("Departure rulings have not been recorded")
    proof = {"schemaVersion": 1, "sourceDigest": start_digest,
             "finishedAt": datetime.now(timezone.utc).isoformat(),
             "summary": {"executed": result.testsRun,
                         "passed": sum(t["status"] == "pass" for t in result.executions),
                         "failed": len(result.failures) + len(result.errors) + len(result.unexpectedSuccesses),
                         "skipped": len(result.skipped), "pendingRulings": 0,
                         "departureAuditComplete": result.wasSuccessful(), "fullCatalogSemanticCertification": False},
             "cards": cards, "tests": result.executions, "resolvedRulings": resolved_rulings,
             "coverage": ["Déclaration réelle de Bolbakazim et résolution après disparition de sa source.",
                          "Réponse Exile réelle puis reconnexion et deux passes de priorité via WebSocket.",
                          "Identité des objets du champ : une nouvelle instance n'hérite pas des cibles ni des modifications visant l'ancienne.",
                          "Mémoire des règles accordées par Mukkabell/Looj : main, Limbo, Deck, Exil, Cleanse et contrôleurs distincts.",
                          "Trois reconnexions réseau : activation après Exile, mémoire de contrôle et invalidation automatique de Recover. Les mutations de fixture sont distinguées des messages réels.",
                          "Puissances imprimées après départ : Mukkabell, Referen-Doom, Lombriculpop et Armored Pachywyrm.",
                          "Anciennes entrées du Limbo/Vaisseau invalidées, repositions préservées, cibles indépendantes restantes résolues, copies héritées invalidées et nouvelles sélections acceptées."],
             "limitations": ["Deux exemplaires physiques en zones privées ne disposent pas d'identifiants individuels ; le format tournoi impose des cartes uniques par deck.",
                             "Les comparaisons lorsque les deux Manifestations de référence sont absentes ne sont pas couvertes par ce lot.",
                             "Les autres mémoires et toutes les combinaisons de cartes ne sont pas certifiées par ce lot."]}
    if audit.digest() != start_digest:
        raise RuntimeError("Source changed during departure audit")
    audit.OUT.mkdir(parents=True, exist_ok=True)
    (audit.OUT / "departure.json").write_text(json.dumps(proof, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    lines = ["# Audit des départs de source, des cibles et des mémoires", "",
             f"Exécuté : {proof['finishedAt']}", f"Empreinte : `{start_digest}`", "",
             "**Lot terminé pour les cas décrits ci-dessous ; les deux arbitrages du créateur sont appliqués.**", "",
             "```json", json.dumps(proof["summary"], indent=2), "```", "",
             "## Corrections reproduites", "",
             "- Mukkabell et Looj conservaient leurs règles accordées seulement dans l'objet du champ. Elles sont désormais enregistrées comme mémoires et restaurées après la main ou le Limbo.",
             "- Chaque règle conserve le contrôleur de l'effet qui l'a accordée. Des Enchaînements successifs conservent chaque règle une seule fois, avec son propre contrôleur.",
             "- L'exil ou la mise au Deck d'un autre exemplaire physique n'efface plus une mémoire attachée à une carte encore sur le champ ou en Stalemate.",
             "- Looj attribue les points au véritable gagnant de la Confrontation, même après un changement de contrôleur de la Manifestation enchaînée. Le contrôleur de l'effet reste inchangé sur la Pile.",
             "- Les copies n'héritent pas de ces mémoires ; Cleanse les préserve ; Deck et Exil les effacent lorsque la carte concernée y entre.", "",
             "- Recover et Reforging Fate ne peuvent plus viser une nouvelle entrée de la même carte au Limbo. Le suivi s'applique aussi aux cibles du Vaisseau et de la main, sans invalider un simple changement d'ordre dans la même zone.",
             "- Une source partie du champ utilise sa puissance imprimée. Lombriculpop et Armored Pachywyrm conservent ainsi leur calcul au lieu de produire zéro. Mukkabell et Referen-Doom avaient déjà ce repli ; les tests le garantissent.", "",
             "## Preuves exécutées", "", *["- " + item for item in proof["coverage"]], "",
             "## Arbitrages confirmés du créateur", "", *["- " + item["rule"] for item in resolved_rulings], "",
             "Les réponses du créateur sont conservées dans audit/rule-decisions.json et priment sur les interprétations antérieures. Le livret local, section 3.2 (pages imprimées 19–20), reste la référence pour l'indépendance des effets, le ciblage et les mémoires.", "",
             "## Limites", "", *["- " + item for item in proof["limitations"]], "",
             "Les campagnes générales et les preuves du lot numérique précédent sont historiques après ces modifications. Les tests actuels ne restampillent pas des parcours navigateur ou des séquences non relancés.", "",
             "[Résultats détaillés](departure.json) · [Première reproduction](departure-before.json) · [Reproduction des décisions avant correctif](departure-rulings-before.json) · [Assertions des décisions](../../tests/test_departure_rulings.py) · [Parcours réseau](../../tests/test_departure_resolution_integration.py)", ""]
    (audit.OUT / "DEPARTURES.md").write_text("\n".join(lines), encoding="utf8")
    print(json.dumps(proof["summary"]))
    return int(not result.wasSuccessful())


if __name__ == "__main__":
    raise SystemExit(main())
