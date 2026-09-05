# #135 independent review completeness gate

Status: **PREPARATION ONLY — NOT LEGAL ADVICE — NOT REVIEWED — NOT A PASS**

This runbook complements `docs/QUALIFIED_LEGAL_PRIVACY_CLAIMS_REVIEW_HANDOFF.md` for the independent privacy/legal/trademark/claims review required by #135/#21/#136.

It has one narrow purpose: make it difficult to close #135 with an attractive report reference while silently leaving a required review area, reviewed material, architecture delta, limitation or approved-claims decision unaccounted for.

## Separation from the findings ledger

This is **not** a second findings/remediation ledger. Findings, materiality, remediation, retest and residual-risk handling remain in the external-review register prepared for #21/#134/#135 by `docs/qualification/external-review-findings-runbook.md` and `scripts/validate_external_review_findings.py`.

The #135-specific package instead records:

- who performed the independent review and the asserted independence/competence scope;
- the exact `1.0.0` / `v1.0.0` candidate SHA reviewed;
- a versioned or hash-accounted inventory of the material actually examined;
- one explicit disposition for every area in the #135 handoff matrix, including the post-#171 canonical evidence snapshot surfaces;
- evidence references and limitations/reasons supporting each disposition;
- the external findings-register reference rather than duplicating its findings;
- reviewer-approved bounded Qualified wording and required limitations.

## Preparation check

The committed template deliberately remains empty and `NOT_REVIEWED`:

```bash
python scripts/validate_legal_privacy_claims_review.py qualification/legal_privacy_claims_review.template.json
```

Passing this command means only that the skeleton schema is coherent.

## Final structural check

After a genuinely independent reviewer has completed the work, create the evidence package outside the repository fixture, preserve the report/material references, and run:

```bash
python scripts/validate_legal_privacy_claims_review.py path/to/legal_privacy_claims_review.json --final
```

Final mode fails closed unless:

- release identity is exactly `1.0.0` / `v1.0.0` and the candidate uses a full 40-hex SHA;
- reviewer identity/organisation, independence statement, competence scope, date and report reference are present;
- the material inventory is non-empty and each item has a content SHA-256 or an explicit reason why a digest is unavailable;
- the review matrix contains exactly the required #135 areas;
- no area remains `NOT_REVIEWED` or `REMEDIATION_REQUIRED`;
- `APPROVED_WITH_LIMITATION` and `OUT_OF_SCOPE_WITH_REASON` carry an explicit limitation/reason;
- every final matrix disposition has supporting evidence references;
- the package cross-references the separate findings/remediation register;
- reviewer-approved wording preserves the bounded `ThisTinti 1.0 Qualified — Procurement v1 — profile P1 — protocol E1` claim;
- no explicit `not_reviewed` item remains.

The package must always keep `qualification_decision` equal to `NOT_A_PASS`. A successful structural validation emits `VALID_STRUCTURE_NOT_QUALIFICATION_PASS`; it cannot authenticate the reviewer, decide lawful basis, clear a trademark, accept legal/privacy risk or qualify the release.

## Change control

A material change after review to public wording, data flows, canonical evidence storage, retention/deletion, backup/restore, export/reviewer disclosure, deployment assumptions, licence/notice inventory or intended territories/classes makes the affected review evidence stale until the independent reviewer performs the appropriate delta review. Do not inherit an earlier approval merely because the source code change appears small or CI remains green.
