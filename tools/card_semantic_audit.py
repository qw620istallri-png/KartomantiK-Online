"""Validate independent card reviews; keep static review and runtime proof separate.

Only original English catalog JSON is an expectation source here. Test mentions
are navigation aids, never evidence that a complete card clause was tested.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATHS = ("public/cards-data.json", "public/extensions/inner-desert/cards.json")
REVIEW_PATHS = tuple(f"audit/semantic-reviews/{name}.json" for name in ("001-150", "151-300", "301-450"))
TEST_PATTERNS = ("test_semantic_batch_*.py", "test_semantic_integration_followup.py",
                 "test_semantic_grimoire_sequences.py", "test_delayed_tribute_memory.py",
                 "test_tenebro_replacement_audit.py", "test_stack_intrinsic_payment.py")
STATUSES = {"reviewed-match", "reviewed-defect", "ruling-required"}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def paragraphs(text):
    return [part.strip() for part in re.split(r"[\r\n]+", text) if part.strip()]


def filled(value):
    if isinstance(value, str):
        return bool(value.strip())
    return isinstance(value, list) and bool(value) and all(filled(item) for item in value)


def normalize_record(record):
    """Adapt the three author formats without changing their recorded findings."""
    clauses = []
    for clause in record.get("clauses", record.get("clauseReview", [])):
        clauses.append({
            "text": str(clause.get("text", clause.get("originalText", ""))).strip(),
            "expectedBehavior": clause.get("expectedBehavior", clause.get("independentCardContract")),
            "branches": clause.get("branchesAndExactOracles", clause.get("negativeAlternativeAndNumericScenario")),
            "recordedStatus": clause.get("status"),
            "original": clause,
        })
    return {"cardId": record.get("cardId"), "catalogPosition": record.get("catalogPosition"),
            "name": record.get("name"), "recordedStatus": record.get("status"),
            "clauses": clauses, "original": record}


def validate_reviews(catalog, documents, expected_count=450):
    """Return actionable diagnostics rather than silently repairing review data."""
    diagnostics, records = [], []

    def issue(code, **details):
        diagnostics.append({"severity": "error", "code": code, **details})

    if len(catalog) != expected_count:
        issue("catalog-count", actual=len(catalog), expected=expected_count)
    catalog_ids = [card["id"] for card in catalog]
    for cid, count in Counter(catalog_ids).items():
        if count != 1:
            issue("duplicate-catalog-id", cardId=cid, count=count)
    for source, document in documents:
        source_records = document.get("records", document.get("cards"))
        if not isinstance(source_records, list):
            issue("missing-record-list", source=source)
            continue
        for raw in source_records:
            record = normalize_record(raw)
            record["reviewSource"] = source
            records.append(record)
    if len(records) != expected_count:
        issue("review-count", actual=len(records), expected=expected_count)
    for field in ("cardId", "catalogPosition"):
        for value, count in Counter(record[field] for record in records).items():
            if count != 1:
                issue(f"duplicate-{field}", value=value, count=count)
    by_id = {card["id"]: card for card in catalog}
    expected_positions = {cid: index for index, cid in enumerate(catalog_ids, 1)}
    reviewed_ids = {record["cardId"] for record in records}
    for cid in sorted(set(catalog_ids) - reviewed_ids):
        issue("missing-card", cardId=cid)
    covered_paragraphs = 0
    for record in records:
        cid, raw = record["cardId"], record["original"]
        context = {"cardId": cid, "source": record["reviewSource"]}
        if cid not in by_id:
            issue("unknown-card", **context)
            continue
        if record["catalogPosition"] != expected_positions[cid]:
            issue("catalog-position", expected=expected_positions[cid], actual=record["catalogPosition"], **context)
        text = str(by_id[cid].get("effect") or "")
        if raw.get("printedText") != text:
            issue("printed-text-mismatch", **context)
        if raw.get("printedTextSha256") != sha(text.encode("utf-8")):
            issue("printed-text-sha-mismatch", **context)
        expected, actual = Counter(paragraphs(text)), Counter(clause["text"] for clause in record["clauses"])
        missing, extra = expected - actual, actual - expected
        if missing or extra:
            issue("paragraph-coverage", missing=list(missing.elements()), extra=list(extra.elements()), **context)
        covered_paragraphs += sum((expected & actual).values())
        for index, clause in enumerate(record["clauses"], 1):
            if not filled(clause["expectedBehavior"]):
                issue("missing-expectation", clause=index, **context)
            if not filled(clause["branches"]):
                issue("missing-branches", clause=index, **context)
            if clause["recordedStatus"] not in STATUSES:
                issue("invalid-clause-status", clause=index, actual=clause["recordedStatus"], **context)
        if not expected and not filled((raw.get("noEffectTextReview") or {}).get("expectedBehavior", raw.get("independentExpectedBehavior"))):
            issue("missing-no-effect-expectation", **context)
        if record["recordedStatus"] not in STATUSES:
            issue("invalid-card-status", actual=record["recordedStatus"], **context)
    return {"valid": not diagnostics, "diagnostics": diagnostics,
            "summary": {"catalogCards": len(catalog), "reviewRecords": len(records),
                        "uniqueReviewedCards": len(reviewed_ids),
                        "catalogParagraphs": sum(len(paragraphs(str(card.get("effect") or ""))) for card in catalog),
                        "matchedParagraphEntries": covered_paragraphs,
                        "recordedCardStatuses": dict(sorted(Counter(record["recordedStatus"] for record in records).items()))},
            "cards": records}


def source_digest(root):
    """Same ordered source scope as card_behavior_audit.digest, without engine imports."""
    paths = [*sorted((root / "server").rglob("*.py")), *sorted((root / "public").rglob("*.js")),
             *sorted((root / "public").rglob("*.css")), root / "public/index.html",
             *(root / path for path in CATALOG_PATHS), root / "public/card-abilities.json",
             root / "public/automation-coverage-overrides.json", *sorted((root / "audit").glob("*.json")),
             *sorted((root / "tools").glob("*.py")), *sorted((root / "tools").glob("*.mjs")),
             *sorted((root / "tests").glob("test_*.*"))]
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def test_mentions(catalog, paths):
    """Only exact string literals: no method-name guessing or full-clause claims."""
    values = {}
    for card in catalog:
        for value in (card["id"], card.get("name")):
            if value:
                values.setdefault(value.casefold(), set()).add(card["id"])
    result = []
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        for cls in (node for node in tree.body if isinstance(node, ast.ClassDef)):
            constants = [node for node in cls.body if isinstance(node, (ast.Assign, ast.AnnAssign))]
            class_values = {node.value for assignment in constants for node in ast.walk(assignment)
                            if isinstance(node, ast.Constant) and isinstance(node.value, str)}
            for method in (node for node in cls.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_")):
                method_values = {node.value for node in ast.walk(method) if isinstance(node, ast.Constant) and isinstance(node.value, str)}
                matches = []
                for scope, literals in (("method-string-literal", method_values), ("class-constant-string-literal", class_values)):
                    for literal in sorted(literals):
                        for cid in sorted(values.get(literal.casefold(), ())):
                            matches.append({"cardId": cid, "matchedLiteral": literal, "scope": scope})
                result.append({"testId": f"{path.stem}.{cls.name}.{method.name}", "file": path.name,
                               "line": method.lineno, "cardMentions": matches,
                               "evidenceKind": "test-mentions-only", "provesWholeClause": False})
    return result


def attach_runtime(mentions, report, current_digest):
    fresh = report.get("sourceDigest") == current_digest if report else False
    executions = {test["testId"]: test for test in report.get("tests", [])} if report else {}
    for mention in mentions:
        execution = executions.get(mention["testId"])
        mention["execution"] = {"recordedStatus": execution.get("status") if execution else "not-in-supplied-report",
                                "reportFresh": fresh,
                                "currentExecutionCertified": bool(execution and fresh),
                                "durationSeconds": execution.get("durationSeconds") if execution else None}
    return {"supplied": report is not None, "sourceDigest": report.get("sourceDigest") if report else None,
            "currentSourceDigest": current_digest, "fresh": fresh,
            "finishedAt": report.get("finishedAt") if report else None,
            "summaryAsRecorded": report.get("summary") if report else None,
            "warning": "Test/card mentions do not map or certify exact clauses. Historical findings remain historical."}


def validate_art_inputs(root, report):
    diagnostics = []
    hashes = report.get("inputHashes") or {}
    if not hashes:
        diagnostics.append({"code": "missing-input-hashes"})
    for relative, expected in hashes.items():
        path = (root / relative).resolve()
        if not path.is_relative_to(root.resolve()):
            diagnostics.append({"code": "input-outside-workspace", "path": relative})
        elif not path.is_file() or sha(path.read_bytes()) != expected:
            diagnostics.append({"code": "input-hash-mismatch", "path": relative})
    return {"inputHashesValid": not diagnostics, "diagnostics": diagnostics,
            "inputHashes": hashes, "summaryAsRecorded": report.get("summary"),
            "finishedAt": report.get("finishedAt"), "physicalDevice": report.get("physicalDevice"),
            "limitationsAsRecorded": report.get("limitations", []),
            "scope": "Saved remote-art report input hashes only; no new network or visual validation."}


def markdown(report):
    summary = report["summary"]
    lines = ["# Revue sémantique des cartes", "",
             f"Catalogue : {summary['catalogCards']} cartes ; {summary['catalogParagraphs']} paragraphes imprimés.",
             f"Registre : {summary['reviewRecords']} fiches ; {summary['matchedParagraphEntries']} correspondances de paragraphes.",
             f"Validation structurelle : {'valide' if report['valid'] else 'INCOMPLÈTE / INVALIDE'}.", "",
             "## Revue indépendante documentée", "",
             "Les attentes et branches proviennent des revues manuelles des agents. Ce contrôle compare leur texte et leur SHA au catalogue anglais ; il ne refait pas une revue humaine du créateur et ne prouve pas leur justesse sémantique.",
             "Les statuts et défauts d'origine sont conservés comme historiques. Aucun défaut n'est déclaré clos par une simple mention de carte dans un test.", "",
             "| Statut historique | Cartes |", "| --- | ---: |"]
    lines += [f"| {status} | {count} |" for status, count in summary["recordedCardStatuses"].items()]
    runtime = report["runtimeEvidence"]
    lines += ["", "## Tests runtime manuscrits", "",
              f"Méthodes indexées : {len(report['testMentions'])}. Rapport d'exécution fourni : {runtime['supplied']}. Empreinte source actuelle : {runtime['fresh']}.",
              "Les liens AST signalent uniquement une chaîne littérale contenant un nom ou identifiant exact de carte, dans la méthode ou une constante de classe. Ils ne prouvent aucune clause complète, ni les assertions exactes. Un statut d'exécution périmé reste historique.", "",
              "## Limites", "", "La couverture complète des clauses, des branches et des interactions n'est PAS certifiée. Les appareils physiques sont exclus à la demande de l'utilisateur ; il les vérifiera lui-même."]
    if report.get("remoteArt"):
        lines += ["", f"Illustrations distantes : empreintes des entrées du rapport valides = {report['remoteArt']['inputHashesValid']}. Aucun téléchargement ni contrôle visuel supplémentaire ici."]
    lines += ["", "## Diagnostics", ""]
    lines += [f"- `{item['code']}` : {json.dumps(item, ensure_ascii=False)}" for item in report["diagnostics"]] or ["Aucun diagnostic structurel."]
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--unit-tests", type=Path, help="Optional saved unit-tests.json; freshness is checked.")
    parser.add_argument("--remote-art", type=Path, help="Optional saved remote-art.json; input hashes are checked.")
    parser.add_argument("--out", type=Path, default=ROOT / "reports/systematic-audit")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true", help="Write JSON and Markdown reports (default).")
    mode.add_argument("--check", action="store_true", help="Validate and print diagnostics without writing reports.")
    args = parser.parse_args(argv)
    catalog = [card for relative in CATALOG_PATHS for card in read_json(ROOT / relative)]
    documents = [(relative, read_json(ROOT / relative)) for relative in REVIEW_PATHS]
    report = validate_reviews(catalog, documents)
    report.update(schemaVersion=1, generatedAt=datetime.now(timezone.utc).isoformat(),
                  evidenceKind="independent-static-review-registry", fullSemanticCoverageCertified=False,
                  paragraphComparison="Split CR/LF and trim paragraph-edge whitespace; entire printedText and SHA remain byte-exact UTF-8 checks.",
                  physicalDevices={"included": False, "reason": "User will verify physical devices manually."},
                  inputHashes={relative: sha((ROOT / relative).read_bytes()) for relative in (*CATALOG_PATHS, *REVIEW_PATHS)})
    paths = sorted({path for pattern in TEST_PATTERNS for path in (ROOT / "tests").glob(pattern)})
    mentions = test_mentions(catalog, paths)
    unit = read_json(args.unit_tests) if args.unit_tests else None
    report["runtimeEvidence"] = attach_runtime(mentions, unit, source_digest(ROOT))
    if args.unit_tests:
        report["runtimeEvidence"].update(path=str(args.unit_tests), sha256=sha(args.unit_tests.read_bytes()))
    report["testMentions"] = mentions
    report["summary"].update(indexedTestMethods=len(mentions),
                            cardsMentionedByTests=len({match["cardId"] for test in mentions for match in test["cardMentions"]}),
                            indexedMethodsWithCurrentExecution=sum(test["execution"]["currentExecutionCertified"] for test in mentions))
    for card in report["cards"]:
        card["testMentionIds"] = [test["testId"] for test in mentions if any(match["cardId"] == card["cardId"] for match in test["cardMentions"])]
        card["fullClauseExecutionCertified"] = False
    if args.remote_art:
        report["remoteArt"] = validate_art_inputs(ROOT, read_json(args.remote_art))
        report["remoteArt"].update(path=str(args.remote_art), sha256=sha(args.remote_art.read_bytes()))
    if not args.check:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "semantic-review.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (args.out / "SEMANTIC_REVIEW.md").write_text(markdown(report), encoding="utf-8")
    print(json.dumps({**report["summary"], "valid": report["valid"], "diagnostics": len(report["diagnostics"]),
                      "runtimeReportFresh": report["runtimeEvidence"]["fresh"]}, ensure_ascii=False))
    for diagnostic in report["diagnostics"]:
        print(json.dumps(diagnostic, ensure_ascii=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
