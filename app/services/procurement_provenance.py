from __future__ import annotations

from collections import Counter
from typing import Any

from ..version import RELEASE_VERSION

MATRIX_SCHEMA = "thistinti.procurement-provenance-matrix.v1"
MATRIX_VERSION = "0.1"
RULE_PACK_ID = "procurement-baseline-v0.1"
RULE_PACK_VERSION = "0.1"

# `complete` means the finding has the qualified DOCUMENTO -> FACT -> FINDING ->
# GIUDIZIO chain and a human judgment can bind only to the exact current finding
# version. `incomplete` means the engine emits the finding and EvidenceLink rows,
# but the qualified FACT/FINDING/JUDGMENT provenance path is not implemented yet.
_RULES: tuple[dict[str, Any], ...] = (
    {
        "family": "identity-linkage",
        "case_type": "duplicate_document_number",
        "provenance_status": "complete",
        "blind_eligible": True,
        "evidence": "Qualified property/state-machine vertical slice with immutable finding versions and exact judgment binding.",
    },
    {
        "family": "identity-linkage",
        "case_type": "duplicate_payment",
        "provenance_status": "incomplete",
        "blind_eligible": False,
        "evidence": "Engine finding and EvidenceLink exist; no qualified ProvenanceFinding/ProvenanceJudgment vertical slice.",
    },
    {
        "family": "quantity-consistency",
        "case_type": "unit_mismatch",
        "provenance_status": "incomplete",
        "blind_eligible": False,
        "evidence": "Engine finding and EvidenceLink exist; provenance does not yet bind normalized quantity facts to a versioned finding.",
    },
    {
        "family": "quantity-consistency",
        "case_type": "delivered_over_order",
        "provenance_status": "incomplete",
        "blind_eligible": False,
        "evidence": "Engine finding and EvidenceLink exist; no qualified FACT-to-FINDING lineage for the compared quantities.",
    },
    {
        "family": "quantity-consistency",
        "case_type": "invoiced_over_received",
        "provenance_status": "incomplete",
        "blind_eligible": False,
        "evidence": "Engine finding and EvidenceLink exist; no qualified FACT-to-FINDING lineage for the compared quantities.",
    },
    {
        "family": "quantity-consistency",
        "case_type": "credit_below_return",
        "provenance_status": "incomplete",
        "blind_eligible": False,
        "evidence": "Engine finding and EvidenceLink exist; no qualified FACT-to-FINDING lineage for return and credit quantities.",
    },
    {
        "family": "amount-consistency",
        "case_type": "currency_mismatch",
        "provenance_status": "incomplete",
        "blind_eligible": False,
        "evidence": "Engine finding and EvidenceLink exist; currency facts are not yet linked through the qualified provenance chain.",
    },
    {
        "family": "amount-consistency",
        "case_type": "line_total_mismatch",
        "provenance_status": "incomplete",
        "blind_eligible": False,
        "evidence": "Engine finding and EvidenceLink exist; calculated and observed monetary facts are not yet version-bound provenance inputs.",
    },
    {
        "family": "amount-consistency",
        "case_type": "price_over_order",
        "provenance_status": "incomplete",
        "blind_eligible": False,
        "evidence": "Engine finding and EvidenceLink exist; compared price facts are not yet linked to a versioned ProvenanceFinding.",
    },
    {
        "family": "amount-consistency",
        "case_type": "discount_missing",
        "provenance_status": "incomplete",
        "blind_eligible": False,
        "evidence": "Engine finding and EvidenceLink exist; discount facts are not yet linked to a versioned ProvenanceFinding.",
    },
    {
        "family": "amount-consistency",
        "case_type": "tax_rate_mismatch",
        "provenance_status": "incomplete",
        "blind_eligible": False,
        "evidence": "Engine finding and EvidenceLink exist; tax-rate facts are not yet linked to a versioned ProvenanceFinding.",
    },
    {
        "family": "amount-consistency",
        "case_type": "duplicate_invoice_line",
        "provenance_status": "incomplete",
        "blind_eligible": False,
        "evidence": "Engine finding and EvidenceLink exist; duplicate-line signature inputs are not yet qualified provenance facts.",
    },
    {
        "family": "amount-consistency",
        "case_type": "payment_over_invoice",
        "provenance_status": "incomplete",
        "blind_eligible": False,
        "evidence": "Engine finding and EvidenceLink exist; invoice/payment total facts are not yet linked to a versioned ProvenanceFinding.",
    },
    {
        "family": "expected-evidence-completeness",
        "case_type": "unmatched_invoice_line",
        "provenance_status": "incomplete",
        "blind_eligible": False,
        "evidence": "Engine finding and EvidenceLink exist; the absence/matching interpretation is not represented as qualified provenance.",
    },
    {
        "family": "expected-evidence-completeness",
        "case_type": "payment_without_invoice",
        "provenance_status": "incomplete",
        "blind_eligible": False,
        "evidence": "Engine finding and EvidenceLink exist; expected-evidence absence is not yet represented through FACT/FINDING provenance.",
    },
    {
        "family": "expected-evidence-completeness",
        "case_type": "return_without_credit",
        "provenance_status": "incomplete",
        "blind_eligible": False,
        "evidence": "Engine finding and EvidenceLink exist; expected credit evidence is not yet represented through FACT/FINDING provenance.",
    },
)

_FAMILIES = (
    "identity-linkage",
    "quantity-consistency",
    "amount-consistency",
    "temporal-consistency",
    "expected-evidence-completeness",
)


def procurement_provenance_matrix() -> dict[str, Any]:
    rules = [dict(item) for item in _RULES]
    family_payload: list[dict[str, Any]] = []
    for family in _FAMILIES:
        family_rules = [item for item in rules if item["family"] == family]
        counts = Counter(item["provenance_status"] for item in family_rules)
        if not family_rules:
            status = "unsupported"
        elif counts["complete"] == len(family_rules):
            status = "complete"
        else:
            status = "incomplete"
        family_payload.append(
            {
                "id": family,
                "provenance_status": status,
                "rule_count": len(family_rules),
                "complete_rule_count": counts["complete"],
                "incomplete_rule_count": counts["incomplete"],
                "case_types": [item["case_type"] for item in family_rules],
            }
        )

    blockers = sorted(item["case_type"] for item in rules if not item["blind_eligible"])
    return {
        "schema": MATRIX_SCHEMA,
        "version": MATRIX_VERSION,
        "product_version": RELEASE_VERSION,
        "rule_pack_id": RULE_PACK_ID,
        "rule_pack_version": RULE_PACK_VERSION,
        "scope": "Procurement pilot rule-pack provenance qualification only.",
        "status_definitions": {
            "complete": "Qualified DOCUMENTO -> FACT -> FINDING -> GIUDIZIO lineage exists for this rule.",
            "incomplete": "The engine rule exists, but its qualified provenance lineage is not complete.",
            "unsupported": "The declared rule family has no engine rule in the current pilot baseline.",
        },
        "families": family_payload,
        "rules": rules,
        "excluded_runtime_rules": [
            {
                "case_type": "field_consistency",
                "reason": "Dynamic RuleProposal findings are not part of the fixed Procurement v0.1 blind Rule Pack.",
            }
        ],
        "blind_readiness": {
            "ready": not blockers and all(item["provenance_status"] != "unsupported" for item in family_payload),
            "policy": "Every pilot Rule Pack rule and declared family must have complete provenance before blind evaluation freeze.",
            "blocking_case_types": blockers,
            "unsupported_families": sorted(
                item["id"] for item in family_payload if item["provenance_status"] == "unsupported"
            ),
        },
        "claim_boundary": {
            "engine_finding_equals_provenance_qualified_finding": False,
            "incomplete_rules_may_support_blind_accuracy_claims": False,
            "matrix_change_requires_new_pilot_manifest": True,
        },
    }
