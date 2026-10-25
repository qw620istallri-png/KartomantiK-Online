"""Execute the bounded printed-text numeric audit; retain real test outcomes.

python tools/card_numeric_audit.py
The numbers asserted in tests/test_quantitative_card_audit.py are handwritten
from the printed text and creator rulings, never generated from ability values.
"""
import hashlib
import json
import sys
import unittest
from datetime import datetime, timezone

from run_card_audit import ROOT, EvidenceResult
import card_behavior_audit as audit

sys.path.insert(0, str(ROOT / "tests"))
from test_quantitative_card_audit import QuantitativeCardAuditTests as Cases

# Explicit links to independently asserted clauses. A link is not certification
# of all clauses/branches of this card. Mimer/Entrust are interaction fixtures.
CARD_CASES = {
    Cases.INDUCE: ["induce_uses_doubled_base_and_excludes_additive_bonus", "induce_uses_mimers_snapshot_base_and_not_its_bonus", "induce_counts_generic_token_base"],
    Cases.MUKKABELL: ["mukkabell_win_uses_chained_modified_base_not_print_or_bonus"],
    Cases.DANCER: ["dancer_counts_tokens_under_current_control"],
    Cases.PINPIA: ["pinpia_creates_one_retained_essence_per_actual_interzone_manifestation"],
    Cases.PLEA: ["plea_excludes_tokens_and_copies_but_counts_animated_will"],
    Cases.AGRUPOL: ["agrupol_counts_ownership_across_both_vessels"],
    Cases.DONMO: ["donmo_counts_exhaustion_and_control_not_ownership_or_type"],
    Cases.HUMILIATE: ["humiliate_penalizes_current_controller_and_persists"],
    Cases.JUDGMENT: ["judgment_snapshots_hand_on_resolution_excluding_played_will"],
    Cases.STRENGTHEN: ["printed_fixed_modifiers_have_exact_amount_and_expiry"],
    Cases.ACCENTUATE: ["printed_fixed_modifiers_have_exact_amount_and_expiry"],
    Cases.WEAKEN: ["printed_fixed_modifiers_have_exact_amount_and_expiry"],
    Cases.OPPRESS: ["printed_fixed_modifiers_have_exact_amount_and_expiry", "generic_token_targeting_keeps_type_visibility_and_protection_checks"],
    Cases.CORRODE: ["corrode_affects_both_sides_and_tokens_but_only_existing_cz"],
    Cases.PIMBO: ["pimbo_includes_generic_tokens_and_animated_wills_on_field", "pimbo_does_not_reach_stalemate_which_is_outside_the_field"],
    Cases.FRIENDLY: ["friendly_presence_targets_current_opponent_cz_only"],
    Cases.VIPER: ["viper_locks_existing_opponent_interzone_including_tokens"],
    Cases.LOMBRIC: ["excess_power_points_use_current_first_power_and_floor_at_zero"],
    Cases.PACHY: ["excess_power_points_use_current_first_power_and_floor_at_zero"],
    Cases.PETAL: ["graceful_petal_rewards_immutable_owner_after_vessel_entry"],
    Cases.REAP: ["reap_counts_tokens_for_score_and_draws_only_for_free_spaces"],
    Cases.PROTECT: ["protect_covers_current_controlled_field_cards_but_not_stalemate"],
    Cases.STARKAZ: ["starkaz_and_sever_share_field_scope_without_reaching_stalemate"],
    Cases.SEVER: ["starkaz_and_sever_share_field_scope_without_reaching_stalemate"],
}


def main():
    start_digest = audit.digest()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Cases)
    result = unittest.TextTestRunner(verbosity=1, resultclass=EvidenceResult).run(suite)
    execution = {test["testId"].rsplit(".", 1)[-1]: test for test in result.executions}
    cards = []
    for cid, cases in CARD_CASES.items():
        card = audit.batches.CATALOG.cards[cid]
        text = card.get("effect") or ""
        cards.append({"cardId": cid, "name": card["name"], "printedText": text,
                      "printedTextSha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                      "testIds": [execution["test_" + case]["testId"] for case in cases],
                      "allClausesAndBranchesCertified": False})
    proof = {"schemaVersion": 1, "sourceDigest": start_digest,
             "finishedAt": datetime.now(timezone.utc).isoformat(),
             "summary": {"executed": result.testsRun,
                         "passed": sum(t["status"] == "pass" for t in result.executions),
                         "failed": len(result.failures) + len(result.errors) + len(result.unexpectedSuccesses),
                         "skipped": len(result.skipped), "cardsWithSelectedClauseProof": len(cards),
                         "fullCatalogSemanticCertification": False},
             "coverage": {"voluntaryWills": "production declaration, payment and Stack resolution",
                          "triggeredEffects": "isolated at resolution; trigger timing/activation not certified",
                          "mukkabell": "actual Chain choice, granted win trigger, Stack resolution",
                          "gracefulPetal": "physical movement, explicit production zone-entry trigger, Stack resolution"},
             "cards": cards, "tests": result.executions,
             "remaining": ["Autres cartes et clauses non couvertes par les assertions de ce lot.",
                           "Déclenchement, timing et branches alternatives des effets isolés.",
                           "Valeurs à conserver lorsque la source ou une cible quitte une zone avant la résolution.",
                           "Combinaisons supplémentaires, navigateurs et appareils réels."]}
    if audit.digest() != start_digest:
        raise RuntimeError("Source changed during numeric audit")
    audit.OUT.mkdir(parents=True, exist_ok=True)
    (audit.OUT / "numeric.json").write_text(json.dumps(proof, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# Audit des résultats chiffrés et des portées", "", f"Exécuté : {proof['finishedAt']}",
             f"Empreinte : `{start_digest}`", "", "```json", json.dumps(proof["summary"], indent=2), "```", "",
             "## Corrections reproduites", "",
             "- Induce Desertion utilise la puissance de base actuelle (copie, doublement et jeton), sans additionner les bonus.",
             "- Le gain de Mukkabell utilise aussi cette puissance de base après un doublement.",
             "- Les jetons génériques sont reconnus comme Manifestations pour le ciblage et les effets de groupe. Le sélecteur affiche leur symbole et puissance.",
             "- Les décomptes de l’Interzone incluent ces jetons (Floating Dancer, Pinpia Psychobulb et Reap What You’ve Sown).",
             "- Les effets visant les cartes actuellement sur le champ ne touchent pas Stalemate (Pimbo, Starkaz, Sever the Ascent et Protect).", "",
             "## Clauses disposant d’assertions indépendantes", "", "| Carte | Tests liés |", "|---|---|",
             *[f"| {c['name']} | {', '.join(t.rsplit('.', 1)[-1] for t in c['testIds'])} |" for c in cards], "",
             "Les nombres attendus sont écrits dans les tests à partir du texte imprimé et des décisions de règles du créateur. Les valeurs encodées des capacités servent à exécuter l’effet, pas à produire son résultat attendu.", "",
             "Les Volontés jouées passent par la déclaration, le paiement et la Pile. Les capacités déclenchées sont principalement isolées à la résolution ; leur moment de déclenchement n’est pas certifié par ce lot. Mukkabell couvre également le vrai choix d’Enchaînement et son déclenchement de victoire. Graceful Petal couvre le déplacement puis l’appel explicite du déclenchement d’entrée au Vaisseau.", "",
             "## Limites et suite", "", *["- " + item for item in proof["remaining"]], "",
             "Ce lot ne certifie pas toutes les clauses des 24 cartes. La campagne générale précédente est historique : son empreinte ne correspond plus aux sources après ces corrections. Elle n’est pas revalidée par les seuls tests de ce lot.", "",
             "[Assertions exécutables](../../tests/test_quantitative_card_audit.py) · [preuves de ce lot](numeric.json) · [première reproduction avant correctifs](numeric-before.json)", ""]
    (audit.OUT / "NUMERIC.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(proof["summary"]))
    return int(not result.wasSuccessful())


if __name__ == "__main__":
    raise SystemExit(main())
