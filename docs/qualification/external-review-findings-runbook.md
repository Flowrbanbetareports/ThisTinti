# External review findings and residual-risk runbook

Status: **PREPARATION ONLY — NOT AN INDEPENDENT REVIEW — NOT A PASS**

This runbook supports issue #21 and the independent tracks #134 (security/pentest) and #135 (privacy/legal/trademark/claims) for the bounded release claim `ThisTinti 1.0 Qualified — Procurement v1 — profile P1 — protocol E1`.

It does not create external evidence. Internal contributors may prepare the structure and populate logistics, but only a genuinely independent assessor/reviewer may supply findings or conclusions attributable to that review. An internal test, CI result, automated scanner, AI-generated opinion, or repository maintainer statement must not be represented as independent evidence.

## Exact-candidate binding

Final review evidence must identify the exact source SHA, environment/deployment profile, report date, assessor organisation/person and review track. For the official Qualified release line, the final register is valid only for `release_version=1.0.0` and `release_tag=v1.0.0`; historical `v3.4.0-alpha.*` prereleases remain legacy development artifacts and cannot satisfy this gate.

A review performed against an earlier candidate may remain useful evidence, but it is stale for release qualification when a later material change affects the reviewed surface. The register must record whether a finding requires retest and which exact SHA/environment the retest covered.

## Required separation

Keep at least these tracks distinct:

- `SECURITY`: independent security assessment / penetration test (#134).
- `PRIVACY_LEGAL`: independent privacy, legal, trademark and public-claims review (#135).

Passing one track cannot close the other. Findings can cross-reference one another, but each has its own reviewer, scope and disposition.

## Finding record

Every finding needs a stable ID and must state:

- track and reviewed surface;
- exact candidate SHA and environment;
- title and concise description;
- severity (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, `INFO`) for technical/security impact where applicable;
- materiality (`MATERIAL`, `NON_MATERIAL`, `UNKNOWN`) for legal/privacy/claims impact where applicable;
- reproducibility or evidence reference when relevant;
- remediation status (`OPEN`, `IN_PROGRESS`, `REMEDIATED`, `NOT_APPLICABLE`, `RISK_ACCEPTED`);
- remediation commit/SHA or documented non-code action when remediated;
- whether retest is required and, when required, its status (`NOT_RUN`, `PASS`, `FAIL`);
- residual-risk decision, rationale and accountable approver when risk is accepted.

Do not downgrade a finding merely to make the gate pass. Severity/materiality assigned by the independent reviewer remains authoritative unless the reviewer explicitly revises it.

## Release-blocking policy

The final register must fail closed when any of these conditions exists:

1. a `CRITICAL` or `HIGH` security finding remains `OPEN`/`IN_PROGRESS`, or required retest is `NOT_RUN`/`FAIL`;
2. a privacy/legal/trademark/claims finding marked `MATERIAL` remains unresolved without an explicit, accountable residual-risk decision compatible with #136;
3. a finding affecting provenance/evidence integrity, protected company data, reviewer correctness, release claims or intended operating safety is unresolved even if CI is green;
4. a remediation changed the reviewed surface but no required retest is tied to the corrected exact SHA/environment;
5. the assessor identity, report date, scope or exact candidate binding is missing;
6. the two independent tracks are collapsed into one unscoped informal conclusion.

`RISK_ACCEPTED` is not an automatic escape hatch. It requires a written rationale and named accountable approver; it cannot override the mandatory-fix policy in #136.

## Post-#171 surfaces that must not disappear from scope

The independent handoffs must explicitly consider the canonical `document_evidence_snapshots` introduced by #171. Depending on track, this includes tenant/RLS access, full-byte evidence persistence, disclosure through reviewer/export paths, replacement/TOCTOU resistance, retention/deletion/legal-hold behaviour, backup/restore reappearance, at-rest protection boundary, incident handling and migration/backfill semantics.

## Final handoff procedure

1. Freeze the candidate identity and intended environment supplied to each external subject.
2. Give the assessor only the relevant prepared packet; do not pre-fill findings or conclusions on their behalf.
3. Record the received report metadata and findings verbatim enough to preserve severity/materiality and disposition without reproducing confidential report content unnecessarily.
4. Link remediation to exact commits/non-code actions.
5. Obtain required retest from the independent assessor on the corrected candidate.
6. Run `python scripts/validate_external_review_findings.py <register.json> --final`.
7. Attach/link the resulting register from #134/#135 and finally #21. A validator PASS means only that the evidence register is structurally complete and contains no declared unresolved blocker; it does **not** prove that the external evidence is authentic or sufficient by itself.

## Residual-risk acceptance

Residual risk must remain explicit. Record the risk statement, why remediation is not being performed before 1.0, compensating controls, expiry/review trigger, approver and date. Any change that materially alters the accepted risk requires renewed review rather than silent inheritance.
