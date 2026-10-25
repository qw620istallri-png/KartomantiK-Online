"""Bounded First Manifestation and Stalemate UI proof, without publishing."""
import json
import subprocess
import sys
import time
import unittest
from datetime import datetime, timezone

from run_card_audit import ROOT, EvidenceResult
import card_behavior_audit as audit


def main():
    digest = audit.digest()
    sys.path.insert(0, str(ROOT / "tests"))
    patterns = ("test_first_reference_audit.py", "test_first_reference_integration.py",
                "test_departure_resolution_audit.py", "test_departure_resolution_integration.py", "test_departure_rulings.py")
    suite = unittest.TestSuite(unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern=pattern) for pattern in patterns)
    result = unittest.TextTestRunner(verbosity=1, resultclass=EvidenceResult).run(suite)
    gates = []
    for script in ("test_stalemate_totals.cjs", "test_rules_parity.cjs", "test_choice_continuity.cjs", "test_frontend.cjs"):
        start = time.monotonic()
        execution = subprocess.run(["node", str(ROOT / "tests" / script)], cwd=ROOT, capture_output=True, text=True, encoding="utf8", errors="replace", timeout=180)
        gates.append({"script": script, "exitCode": execution.returncode, "seconds": round(time.monotonic() - start, 3),
                      "stdout": execution.stdout, "stderr": execution.stderr})
    decisions = json.loads(audit.DECISIONS.read_text(encoding="utf8"))["decisions"]
    ruling = next(entry for entry in decisions if entry["id"] == "current-first-reference")
    historical = audit.OUT / "first-reference-before.json"
    success = result.wasSuccessful() and all(gate["exitCode"] == 0 for gate in gates)
    proof = {"schemaVersion": 1, "sourceDigest": digest, "finishedAt": datetime.now(timezone.utc).isoformat(),
             "summary": {"executed": result.testsRun, "passed": sum(t["status"] == "pass" for t in result.executions),
                         "failed": len(result.failures) + len(result.errors), "skipped": len(result.skipped),
                         "browserGates": len(gates), "browserPassed": sum(g["exitCode"] == 0 for g in gates),
                         "boundedAuditComplete": success, "fullCatalogSemanticCertification": False},
             "ruling": ruling, "tests": result.executions, "browser": gates,
             "beforeFix": json.loads(historical.read_text(encoding="utf8")) if historical.is_file() else {"evidenceUnavailable": True},
             "baseReadersBeforeFix": json.loads((audit.OUT / "first-reference-bases-before.json").read_text(encoding="utf8")) if (audit.OUT / "first-reference-bases-before.json").is_file() else {"evidenceUnavailable": True},
             "coverage": [
                 "Lombriculpop et Armored Pachywyrm : absence adverse = puissance zéro, y compris après le départ des deux cartes initiales.",
                 "Promotion selon l'ordre d'entrée en CZ ; puissance courante de la nouvelle Première Manifestation, sans rejouer ses effets d'entrée ni modifier ses propriétés de Support.",
                 "Retrait, destruction à zéro, cartes hors CZ ou couvertes exclues ; sélection initiale couverte préservée.",
                 "Mimer : l'ancienne cible partie reste invalide ; une nouvelle activation peut viser la Première Manifestation promue. Comparaison stricte des bases et énumération sans mutation.",
                 "Mamelath crée ses jetons depuis les bases modifiées des Premières Manifestations déplacées ; Hermetic Hourglass compare aussi les bases modifiées. Les bonus additifs ne sont pas comptés comme puissance de base.",
                 "Exile déclaré réellement, quatre passes via WebSocket, reconnexion adverse et résultat de points vérifié des deux côtés. Seul l'état initial après victoire est une fixture.",
                 "Impasse : deux totaux par propriétaire, copies et jetons à zéro, noms longs, changement de siège, observateur, rafraîchissement et zone vide sur PC/mobile paysage.",
                 "Clic réel sur la bande, espace réservé aux miniatures, cartes sous les totaux et panneau dégagé des compteurs de confrontation."
             ],
             "limitations": ["Les totaux d'Impasse affichent les valeurs imprimées par propriétaire ; ce ne sont pas des prédictions de tous les effets futurs ou des cartes temporairement verrouillées.",
                             "Les illustrations distantes sont remplacées par le dos local dans les fixtures navigateur.",
                             "Cette passe ne certifie pas toutes les clauses des 450 cartes ni toutes leurs interactions. Les campagnes générales non relancées restent historiques."]}
    if audit.digest() != digest:
        raise RuntimeError("Source changed during reference audit")
    audit.OUT.mkdir(parents=True, exist_ok=True)
    (audit.OUT / "first-reference.json").write_text(json.dumps(proof, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    lines = ["# Références aux Premières Manifestations et totaux d'Impasse", "", f"Exécuté : {proof['finishedAt']}",
             f"Empreinte : `{digest}`", "", "## Résultat", "", "```json", json.dumps(proof["summary"], indent=2), "```", "",
             "Deux bugs moteur reproduits avant correctif : référence adverse absente donnant toujours zéro point, et référence conservant l'identifiant de la Première Manifestation partie.",
             "La promotion est synchronisée lors des sorties du champ et du nettoyage des états. Tous les lecteurs existants, la sélection de cibles et les deux clients reçoivent ainsi le même identifiant courant.", "",
             "Deux autres régressions ont été reproduites : Mamelath et Hermetic Hourglass lisaient la puissance imprimée au lieu de la base modifiée. Ils passent maintenant par le calcul de base commun, qui exclut les bonus additifs.", "",
             "La bande d'Impasse et son panneau donnent maintenant les points de chaque propriétaire avec son nom et sa couleur. Le total commun est supprimé, les copies/jetons ne rapportant pas de points sont exclus. Les miniatures et les titres ne se recouvrent pas.", "",
             "## Arbitrage du créateur", "", ruling["rule"], "", "## Preuves exécutées", "", *["- " + item for item in proof["coverage"]], "",
             "## Limites", "", *["- " + item for item in proof["limitations"]], "",
             "La reproduction antérieure contient 21 assertions en échec sur six méthodes, sans erreur de fixture ; son empreinte source n'avait pas été enregistrée. Le fichier JSON conserve son hash et son caractère historique.", "",
             "Une seconde reproduction (first-reference-bases-before.json) contient les deux échecs de lecture des bases, sur dix méthodes exécutées. Ses résultats sont historiques et ne sont pas réattribués à la version corrigée.", "",
             "[Résultats et sorties réelles](first-reference.json) · [Régression moteur](../../tests/test_first_reference_audit.py) · [Parcours réseau](../../tests/test_first_reference_integration.py) · [UI PC/mobile](../../tests/test_stalemate_totals.cjs)", ""]
    (audit.OUT / "FIRST_REFERENCES.md").write_text("\n".join(lines), encoding="utf8")
    print(json.dumps(proof["summary"]))
    return int(not success)


if __name__ == "__main__":
    raise SystemExit(main())
