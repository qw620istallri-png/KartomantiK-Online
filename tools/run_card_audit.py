"""Run the reproducible card/UI audit and retain actual execution evidence.

python tools/run_card_audit.py                  # all layers, local Chrome
python tools/run_card_audit.py --units-only     # real unittest IDs/outcomes
python tools/run_card_audit.py --report-only    # merge current evidence only

Requires the existing local sandbox fixtures, Python test dependencies and
Playwright/Chrome. No network publishing, game version change or Git mutation.
"""
import argparse
import json
import subprocess
import sys
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "tools")]
import card_behavior_audit as audit

FAMILIES = {
    "payment": ["test_special_payments", "test_combined_payment_audit", "test_payment_interruption_audit", "test_rules_availability"],
    "stack-target-priority": ["test_stack_target_audit", "test_stack_target_integration", "test_stack_priority_audit", "test_grouped_target_audit"],
    "copy-control": ["test_copy_chain_followup_audit", "test_modifier_order_audit", "test_control_cleanup_audit", "test_chosen_entry_control"],
    "chain": ["test_copy_chain_followup_audit", "test_choice_liveness_audit"],
    "departure-memory": ["test_departure_resolution_audit", "test_departure_resolution_integration", "test_departure_rulings"],
    "first-reference": ["test_first_reference_audit", "test_first_reference_integration"],
    "suspend-immediate": ["test_suspend_immediate_audit", "test_sync_suspend_integration"],
    "replacement-events": ["test_replacement_order_audit", "test_observed_events_audit", "test_zone_transition_audit"],
    "cleanse-duration": ["test_cleanse_state_audit", "test_choice_modifier_lifetime", "test_modifier_order_audit"],
    "choices-reconnect": ["test_choice_atomicity", "test_choice_reconnect", "test_choice_liveness_integration"],
    "endgame": ["test_terminal_state_audit"],
}
UI_GATES = ["test_rules_parity.cjs", "test_choice_continuity.cjs", "test_white_essence_payment.cjs",
            "test_drag_cleanup.cjs", "test_connection_lifecycle.cjs", "test_ponderer_drag.cjs",
            "test_rarity_immediate_vfx.cjs", "test_hand_interactions.cjs", "test_hand_space_shortcut.cjs",
            "test_frontend.cjs", "test_release_139_2.cjs", "test_stalemate_totals.cjs", "test_semantic_ui.cjs"]


class EvidenceResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.executions = []
        self.current = None

    def startTest(self, test):
        super().startTest(test)
        self.current = {"testId": test.id(), "status": "running", "started": time.monotonic()}

    def addSuccess(self, test):
        super().addSuccess(test)
        self.current["status"] = "pass"

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.current.update(status="fail", detail=self._exc_info_to_string(err, test))

    def addError(self, test, err):
        super().addError(test, err)
        if self.current:
            self.current.update(status="error", detail=self._exc_info_to_string(err, test))
        else:
            self.executions.append({"testId": test.id(), "status": "error", "detail": self._exc_info_to_string(err, test)})

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        if self.current:
            self.current.update(status="skip", reason=reason)
        else:
            self.executions.append({"testId": test.id(), "status": "skip", "reason": reason})

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        if err is not None:
            self.current.update(status="fail", detail=self._exc_info_to_string(err, test))

    def addExpectedFailure(self, test, err):
        super().addExpectedFailure(test, err)
        self.current["status"] = "expected-failure"

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        self.current["status"] = "unexpected-success"

    def stopTest(self, test):
        if self.current:
            self.current["durationSeconds"] = round(time.monotonic() - self.current.pop("started"), 4)
            self.executions.append(self.current)
            self.current = None
        super().stopTest(test)


def units():
    start_digest = audit.digest()
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
    result = unittest.TextTestRunner(verbosity=1, resultclass=EvidenceResult).run(suite)
    proof = {"schemaVersion": 1, "sourceDigest": start_digest, "finishedAt": datetime.now(timezone.utc).isoformat(),
             "summary": {"executed": result.testsRun, "passed": sum(t["status"] == "pass" for t in result.executions),
                         "failed": len(result.failures) + len(result.errors) + len(result.unexpectedSuccesses), "skipped": len(result.skipped)},
             "tests": result.executions}
    audit.OUT.mkdir(parents=True, exist_ok=True)
    (audit.OUT / "unit-tests.json").write_text(json.dumps(proof, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return int(not result.wasSuccessful() or audit.digest() != start_digest)


def read_evidence(name):
    path = audit.OUT / name
    if not path.is_file():
        raise ValueError(f"Missing execution evidence: {name}")
    report = json.loads(path.read_text(encoding="utf-8"))
    if report["sourceDigest"] != audit.digest():
        raise ValueError(f"Stale execution evidence: {name}; rerun its command")
    return report


def report():
    matrix, browser, traces, unit, ui = [read_evidence(name) for name in
        ("matrix.json", "browser.json", "traces.json", "unit-tests.json", "ui-tests.json")]
    semantic_command = [sys.executable, "tools/card_semantic_audit.py", "--write",
                        "--unit-tests", "reports/systematic-audit/unit-tests.json",
                        "--remote-art", "reports/systematic-audit/remote-art.json"]
    if execute(semantic_command, "semantic-review")["status"] != "pass":
        raise ValueError("Independent review registry validation failed")
    semantic = json.loads((audit.OUT / "semantic-review.json").read_text(encoding="utf-8"))
    if not matrix.get("executed") or browser.get("scope") != "full-catalog":
        raise ValueError("A non-executed matrix or focused browser run cannot certify the catalog")
    expected = set(audit.batches.CATALOG.order)
    if (len(matrix["cards"]) != len(expected) or len(browser["rendering"]) != len(expected)
            or {entry["cardId"] for entry in matrix["cards"]} != expected or {entry["cardId"] for entry in browser["rendering"]} != expected):
        raise ValueError("Card roster missing, duplicated or changed")
    expected_actions = {(cid, ability["id"]) for cid in expected for ability in audit.batches.main.CARD_ABILITIES.get(cid, [])
                        if not any(ability.get(k) for k in ("trigger", "passiveEffect", "playPermission"))}
    actual_actions = {(a["cardId"], a["abilityId"]) for a in browser["actions"]}
    if expected_actions != actual_actions or len(browser["actions"]) != len(expected_actions):
        raise ValueError("Browser voluntary action roster is incomplete")
    if len(browser["journeys"]) != 2 or {Path(g["command"][-1]).name for g in ui["gates"]} != set(UI_GATES):
        raise ValueError("Missing browser journey or UI regression gate")
    family_proof = {}
    for family, modules in FAMILIES.items():
        tests = [t for t in unit["tests"] if t["testId"].split(".")[0] in modules]
        missing = [module for module in modules if not any(t["testId"].startswith(module + ".") for t in tests)]
        family_proof[family] = {"executed": len(tests), "passed": sum(t["status"] == "pass" for t in tests),
                                "missingModules": missing, "testIds": [t["testId"] for t in tests]}
    ruling_proof = {}
    for ruling in matrix["rulings"]:
        modules = ruling.get("tests", [])
        missing = [module for module in modules if not (ROOT / "tests" / (module + ".py")).is_file()]
        tests = [t for t in unit["tests"] if t["testId"].split(".")[0] in modules]
        ruling_proof[ruling["id"]] = {"missingReferences": missing, "executedTestsInReferencedModules": len(tests),
                                     "note": "Module execution is not proof that every assertion of this ruling is covered."}
    failures = sum(r["summary"].get("failed", r["summary"].get("failures", 0)) for r in (matrix, browser, traces, unit, ui))
    failures += matrix["summary"]["printedFailures"]
    failures += sum(bool(f["missingModules"]) for f in family_proof.values()) + sum(bool(r["missingReferences"]) for r in ruling_proof.values())
    # Card-specific evidence stays linked rather than converting broad test
    # references or smoke carriers to a full-text semantic PASS.
    for card in matrix["cards"]:
        card["browserExecution"] = [a for a in browser["actions"] if a["cardId"] == card["cardId"]]
        modules = {Path(ref).stem for ref in card["testReferences"] if ref.endswith(".py")}
        card["referenceExecution"] = {module: sum(t["testId"].startswith(module + ".") and t["status"] == "pass" for t in unit["tests"]) for module in sorted(modules)}
    audit.write(matrix)
    merged = {"schemaVersion": 1, "sourceDigest": audit.digest(), "finishedAt": datetime.now(timezone.utc).isoformat(),
              "summary": {"cards": len(expected), "voluntaryUiActions": len(expected_actions), "unit": unit["summary"],
                          "matrix": matrix["summary"], "browser": browser["summary"], "traces": traces["summary"], "ui": ui["summary"],
                          "independentReview": semantic["summary"],
                          "remoteArt": semantic.get("remoteArt", {}).get("summaryAsRecorded"),
                          "failed": failures, "fullTextSemanticCertification": False},
              "families": family_proof, "rulings": ruling_proof,
              "remaining": ["Relier chaque clause revue à un oracle exécutable ; les mentions AST ne certifient pas les clauses.",
                            "Compléter les branches alternatives et interactions pertinentes qui ne sont pas encore exécutées.",
                            "Les porteurs déclenchés/passifs isolés ne prouvent pas toutes les séquences de partie.",
                            "Les parcours navigateur vérifient la fin du choix/Pile ; leurs résultats chiffrés demandent un oracle dédié."]}
    (audit.OUT / "evidence.json").write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# Rapport des exécutions", "", f"Empreinte : `{merged['sourceDigest']}`", "",
             "```json", json.dumps(merged["summary"], ensure_ascii=False, indent=2), "```", "",
             "## Mécaniques : tests effectivement exécutés", "", "| Famille | Exécutés | Réussis | Modules absents |", "|---|---:|---:|---|",
             *[f"| {name} | {p['executed']} | {p['passed']} | {', '.join(p['missingModules']) or 'aucun'} |" for name, p in family_proof.items()],
             "", "## Couverture restante", "", *[f"- {item}" for item in merged["remaining"]], "",
             "[450 fiches et matrice](README.md) · [revue indépendante](SEMANTIC_REVIEW.md) · [preuves détaillées](evidence.json) · [navigateurs](browser.json) · [séquences](traces.json)", ""]
    (audit.OUT / "EXECUTIONS.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(merged["summary"], ensure_ascii=True))
    return int(bool(failures))


def execute(command, name):
    started = time.monotonic()
    log = audit.OUT / (name + ".log")
    with log.open("w", encoding="utf-8") as stream:
        completed = subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, timeout=900,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    print(f"{name}: {'PASS' if completed.returncode == 0 else 'FAIL'} ({time.monotonic()-started:.1f}s)", flush=True)
    return {"command": command, "status": "pass" if completed.returncode == 0 else "fail", "exitCode": completed.returncode,
            "log": log.name, "durationSeconds": round(time.monotonic() - started, 3)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--units-only", action="store_true")
    parser.add_argument("--ui-only", action="store_true")
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args()
    audit.OUT.mkdir(parents=True, exist_ok=True)
    if args.units_only:
        return units()
    if args.report_only:
        return report()
    if not args.ui_only:
        for command, name in [([sys.executable, "tools/card_behavior_audit.py", "--execute", "--write"], "matrix"),
                              ([sys.executable, "tools/card_audit_traces.py"], "traces"),
                              ([sys.executable, __file__, "--units-only"], "units"),
                              (["node", "tools/card_audit_browser.mjs"], "browser")]:
            if execute(command, name)["status"] == "fail":
                return 1
    start_digest = audit.digest()
    gates = [execute(["node", "tests/" + gate], Path(gate).stem) for gate in UI_GATES]
    ui = {"schemaVersion": 1, "sourceDigest": start_digest, "gates": gates,
          "summary": {"executed": len(gates), "failed": sum(g["status"] == "fail" for g in gates)}}
    (audit.OUT / "ui-tests.json").write_text(json.dumps(ui, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.ui_only:
        return int(bool(ui["summary"]["failed"]) or start_digest != audit.digest())
    return report()


if __name__ == "__main__":
    raise SystemExit(main())
