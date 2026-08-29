from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from ..version import RELEASE_VERSION

MATRIX_SCHEMA = "thistinti.procurement-provenance-matrix.v2"
MATRIX_VERSION = "0.2"
RULE_PACK_SCHEMA = "thistinti.procurement-rule-pack.v2"
RULE_PACK_PATH = Path(__file__).resolve().parents[2] / "pilot" / "procurement" / "rule-pack.v0.2.json"

# `complete` means the finding has the qualified DOCUMENTO -> FACT -> FINDING ->
# GIUDIZIO chain and a human judgment can bind only to the exact current finding
# version. `incomplete` means the engine emits the finding and EvidenceLink rows,
# but the qualified FACT/FINDING/JUDGMENT provenance path is not implemented yet.
_RULES: tuple[dict[str, Any], ...] = (
    {
        "family": "identity-linkage",
        "case_type": "duplicate_document_number",
        "provenance_status": "complete",
        "evidence": "Qualified property/state-machine vertical slice with immutable finding versions and exact judgment binding.",
    },
    {
        "family": "identity-linkage",
        "case_type": "duplicate_payment",
        "provenance_status": "incomplete",
        "evidence": "Engine finding and EvidenceLink exist; no qualified ProvenanceFinding/ProvenanceJudgment vertical slice.",
    },
    {
        "family": "quantity-consistency",
        "case_type": "unit_mismatch",
        "provenance_status": "incomplete",
        "evidence": "Engine finding and EvidenceLink exist; provenance does not yet bind normalized quantity facts to a versioned finding.",
    },
    {
        "family": "quantity-consistency",
        "case_type": "delivered_over_order",
        "provenance_status": "complete",
        "evidence": "Qualified exact commercial quantity/UOM/price/base and delivery quantity/UOM FACT set -> immutable finding versions -> exact current judgment binding; property/stateful and Deep qualification passed on the merged slice.",
    },
    {
        "family": "quantity-consistency",
        "case_type": "invoiced_over_received",
        "provenance_status": "complete",
        "evidence": "Qualified exact reference quantity/UOM plus invoice quantity/UOM/price/base FACT set -> immutable finding versions -> exact current judgment binding; fail-closed, property/stateful and Deep qualification passed on the qualified slice.",
    },
    {
        "family": "quantity-consistency",
        "case_type": "credit_below_return",
        "provenance_status": "incomplete",
        "evidence": "Engine finding and EvidenceLink exist; no qualified FACT-to-FINDING lineage for return and credit quantities.",
    },
    {
        "family": "amount-consistency",
        "case_type": "currency_mismatch",
        "provenance_status": "complete",
        "evidence": "Qualified exact document.currency FACT set -> immutable finding versions -> exact current judgment binding; defaulted or incomplete currency inputs fail closed.",
    },
    {
        "family": "amount-consistency",
        "case_type": "line_total_mismatch",
        "provenance_status": "incomplete",
        "evidence": "Engine finding and EvidenceLink exist; calculated and observed monetary facts are not yet version-bound provenance inputs.",
    },
    {
        "family": "amount-consistency",
        "case_type": "price_over_order",
        "provenance_status": "incomplete",
        "evidence": "Engine finding and EvidenceLink exist; compared price facts are not yet linked to a versioned ProvenanceFinding.",
    },
    {
        "family": "amount-consistency",
        "case_type": "discount_missing",
        "provenance_status": "incomplete",
        "evidence": "Engine finding and EvidenceLink exist; discount facts are not yet linked to a versioned ProvenanceFinding.",
    },
    {
        "family": "amount-consistency",
        "case_type": "tax_rate_mismatch",
        "provenance_status": "incomplete",
        "evidence": "Engine finding and EvidenceLink exist; tax-rate facts are not yet linked to a versioned ProvenanceFinding.",
    },
    {
        "family": "amount-consistency",
        "case_type": "duplicate_invoice_line",
        "provenance_status": "incomplete",
        "evidence": "Engine finding and EvidenceLink exist; duplicate-line signature inputs are not yet qualified provenance facts.",
    },
    {
        "family": "amount-consistency",
        "case_type": "payment_over_invoice",
        "provenance_status": "complete",
        "evidence": "Qualified exact current invoice/payment line_total FACT sets -> immutable finding versions -> exact current judgment binding; engine-equivalent amount aggregation and 0.02 tolerance, fail-closed support, property/stateful and Deep qualification passed on the qualified slice.",
    },
    {
        "family": "expected-evidence-completeness",
        "case_type": "unmatched_invoice_line",
        "provenance_status": "incomplete",
        "evidence": "Engine finding and EvidenceLink exist; the absence/matching interpretation is not represented as qualified provenance.",
    },
    {
        "family": "expected-evidence-completeness",
        "case_type": "payment_without_invoice",
        "provenance_status": "incomplete",
        "evidence": "Engine finding and EvidenceLink exist; expected-evidence absence is not yet represented through FACT/FINDING provenance.",
    },
    {
        "family": "expected-evidence-completeness",
        "case_type": "return_without_credit",
        "provenance_status": "incomplete",
        "evidence": "Engine finding and EvidenceLink exist; expected credit evidence is not yet represented through FACT/FINDING provenance.",
    },
)


def _load_rule_pack() -> dict[str, Any]:
    rule_pack = json.loads(RULE_PACK_PATH.read_text(encoding="utf-8"))
    if rule_pack.get("schema") != RULE_PACK_SCHEMA:
        raise ValueError("Procurement Rule Pack v0.2: schema non valido")
    if str(rule_pack.get("version") or "") != MATRIX_VERSION:
        raise ValueError("Procurement Rule Pack v0.2: versione inattesa")
    return rule_pack


def procurement_provenance_matrix() -> dict[str, Any]:
    rule_pack = _load_rule_pack()
    declared_families = {
        str(family["id"]): list(family.get("engine_case_types") or [])
        for family in rule_pack.get("rule_families") or []
    }
    declared_pairs = {
        (family_id, case_type) for family_id, case_types in declared_families.items() for case_type in case_types
    }
    rule_pairs = {(item["family"], item["case_type"]) for item in _RULES}
    if declared_pairs != rule_pairs:
        raise ValueError("Procurement Rule Pack v0.2: engine baseline diversa dalla provenance implementation")

    target = rule_pack.get("blind_target") or {}
    included = set(target.get("included_case_types") or [])
    excluded_items = target.get("excluded_case_types") or []
    excluded = {str(item.get("case_type") or ""): str(item.get("exclusion_reason") or "") for item in excluded_items}
    excluded_families = {
        str(item.get("id") or ""): str(item.get("exclusion_reason") or "")
        for item in target.get("excluded_families") or []
    }

    rules: list[dict[str, Any]] = []
    for item in _RULES:
        rule = dict(item)
        case_type = rule["case_type"]
        blind_scope = "included" if case_type in included else "excluded"
        rule["blind_scope"] = blind_scope
        rule["blind_eligible"] = blind_scope == "included" and rule["provenance_status"] == "complete"
        if blind_scope == "excluded":
            rule["exclusion_reason"] = excluded.get(case_type, "")
        rules.append(rule)

    family_payload: list[dict[str, Any]] = []
    unsupported_included_families: list[str] = []
    for family_id, case_types in declared_families.items():
        family_rules = [item for item in rules if item["family"] == family_id]
        counts = Counter(item["provenance_status"] for item in family_rules)
        if not family_rules:
            status = "unsupported"
        elif counts["complete"] == len(family_rules):
            status = "complete"
        else:
            status = "incomplete"

        included_count = sum(item["blind_scope"] == "included" for item in family_rules)
        excluded_count = sum(item["blind_scope"] == "excluded" for item in family_rules)
        if included_count and excluded_count:
            blind_scope = "mixed"
        elif included_count:
            blind_scope = "included"
        else:
            blind_scope = "excluded"

        family = {
            "id": family_id,
            "provenance_status": status,
            "blind_scope": blind_scope,
            "rule_count": len(family_rules),
            "blind_included_rule_count": included_count,
            "complete_rule_count": counts["complete"],
            "incomplete_rule_count": counts["incomplete"],
            "case_types": case_types,
        }
        if family_id in excluded_families:
            family["exclusion_reason"] = excluded_families[family_id]
        if status == "unsupported" and family_id not in excluded_families:
            unsupported_included_families.append(family_id)
        family_payload.append(family)

    blockers = sorted(
        item["case_type"]
        for item in rules
        if item["blind_scope"] == "included" and item["provenance_status"] != "complete"
    )
    target_status = str(target.get("status") or "")
    target_approved = target_status == "approved-for-blind"
    target_nonempty = bool(included)
    ready = target_approved and target_nonempty and not blockers and not unsupported_included_families

    return {
        "schema": MATRIX_SCHEMA,
        "version": MATRIX_VERSION,
        "product_version": RELEASE_VERSION,
        "rule_pack_id": rule_pack["rule_pack_id"],
        "rule_pack_version": rule_pack["version"],
        "scope": "Procurement engine coverage, provenance qualification and blind target projection.",
        "status_definitions": {
            "complete": "Qualified DOCUMENTO -> FACT -> FINDING -> GIUDIZIO lineage exists for this rule.",
            "incomplete": "The engine rule exists, but its qualified provenance lineage is not complete.",
            "unsupported": "The declared rule family has no engine rule in the current baseline.",
        },
        "blind_target": target,
        "families": family_payload,
        "rules": rules,
        "excluded_runtime_rules": [
            {
                "case_type": "field_consistency",
                "reason": "Dynamic RuleProposal findings are not part of the fixed Procurement blind Rule Pack.",
            }
        ],
        "blind_readiness": {
            "ready": ready,
            "target_status": target_status,
            "target_approved": target_approved,
            "target_nonempty": target_nonempty,
            "policy": (
                "Blind freeze requires an approved-for-blind non-empty target, complete provenance for every included "
                "case type, and no unsupported family left inside the target."
            ),
            "blocking_case_types": blockers,
            "unsupported_included_families": sorted(unsupported_included_families),
        },
        "claim_boundary": {
            "engine_finding_equals_provenance_qualified_finding": False,
            "incomplete_rules_may_support_blind_accuracy_claims": False,
            "excluded_rules_may_support_blind_accuracy_claims": False,
            "matrix_change_requires_new_pilot_manifest": True,
        },
    }
