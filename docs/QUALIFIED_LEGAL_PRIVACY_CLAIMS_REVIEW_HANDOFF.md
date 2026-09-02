# Qualified P1/E1 — independent legal/privacy/trademark/claims review handoff

Status: **PREPARATION ONLY / NOT REVIEWED / NOT APPROVED**

This packet prepares the independent review required by #135 and #21 for the bounded claim `ThisTinti 1.0 Qualified — Procurement v1 — profile P1 — protocol E1`. It is not legal advice and must never be used as evidence that an independent review occurred.

## Reviewer independence and identity

The final evidence must identify the reviewer or reviewing organisation, competence/scope, date, conflicts or material relationships, documents/versions examined, candidate/release identity where applicable, and signed or otherwise attributable final disposition. Repository authors and automated agents may prepare this packet but cannot satisfy the independent-review requirement.

## Materials to provide

Provide the reviewer with immutable or versioned copies of: P1 scope/exclusions; E1 protocol and manifest; pilot authorisation/anonymisation procedure; intended deployment/local-first description; retention/deletion/export/backup documentation; incident/vulnerability path; Apache-2.0 and third-party notices; terms/disclaimer/support/warranty wording; design-partner/pilot contractual wording; public site, release notes, product UI claims and sales material; trademark/name usage and intended territories/classes; security/recovery handoff summaries relevant to data governance.

For every supplied item record a stable path/URL, version or source SHA, content hash where practical, and review date. A later material wording or operating-model change requires explicit delta review rather than silent inheritance.

### Material architecture delta: canonical evidence snapshots

The qualified candidate now persists canonical document evidence bytes in `document_evidence_snapshots` and serves qualified reviewer/export evidence from that canonical store. This is a material data-governance surface, not merely an integrity hash or transient parser cache. The independent review must therefore examine the actual persisted evidence bytes and their lifecycle, not infer privacy properties from source-document paths or hashes alone.

At minimum the reviewer packet must describe, for each intended Local and Self-Hosted deployment model where applicable:

- what document/evidence bytes are persisted, why they are required for the bounded P1/E1 workflow, and whether derived copies are created;
- tenant/workspace linkage and the intended access-control/RLS boundary around snapshot rows;
- whether operators, reviewers, exports, support personnel, database administrators or backup operators can access the bytes and under what authority;
- retention, deletion, legal-hold and data-subject/request implications for the snapshot rows themselves, including whether deletion of a source file leaves canonical bytes behind;
- backup/restore consequences, including how deleted or restricted snapshot bytes can reappear from backup media and what controls govern that path;
- encryption-at-rest responsibility and the boundary between application controls and host/database/storage controls; absence of an application-managed encryption feature must not be described as equivalent to encrypted storage;
- export/reviewer behavior, including whether canonical bytes can leave the primary database through generated evidence packages or reviewer downloads;
- incident-response implications for compromise, accidental disclosure, tenant-boundary failure or snapshot substitution;
- migration/upgrade behavior for existing documents that predate snapshot storage, including any backfill or fail-closed behavior relevant to privacy expectations.

The reviewer must record any assumption that depends on deployment configuration rather than product-enforced behavior. A green CI result or successful RLS test is technical evidence only and does not decide controller/processor roles, lawful basis, retention lawfulness, contractual duties or acceptable residual privacy risk.

## Review matrix

The independent reviewer should disposition every row as `APPROVED`, `APPROVED_WITH_LIMITATION`, `REMEDIATION_REQUIRED`, `OUT_OF_SCOPE_WITH_REASON`, or `NOT_REVIEWED`. Empty/unknown rows fail closed for final qualification.

| Area | Minimum questions | Required evidence/disposition |
| --- | --- | --- |
| Controller/processor roles | Who determines purpose/means? What changes by deployment/pilot arrangement? | Named role model, assumptions, unresolved role ambiguity |
| Lawful basis & purpose limitation | Is each intended processing purpose supported and bounded? | Purpose/basis mapping and prohibited secondary uses |
| Pilot authorisation | Is each real scenario explicitly authorised before use? | Authorisation requirements, responsible party, retention of proof |
| Anonymisation/pseudonymisation | What must be removed/transformed before ingestion and who verifies it? | Procedure, residual re-identification risk, exceptions |
| Canonical evidence snapshots | Are persisted full evidence bytes necessary, bounded, access-controlled and described accurately? | Data-category inventory, purpose, access roles, tenant/RLS assumptions and limitations |
| Snapshot retention/deletion | Can canonical bytes outlive the source document, request, pilot or intended retention window? | Snapshot-specific retention/deletion/legal-hold decision and operational limits |
| Snapshot backup/restore | Can deleted/restricted snapshot bytes reappear from backups or restored environments? | Restore implications, operator responsibilities and documented controls |
| Snapshot encryption/storage boundary | Which layer actually protects persisted bytes at rest and in backups? | Deployment-specific responsibility statement; no unsupported encryption claim |
| Reviewer/export disclosure | Can canonical evidence bytes leave the database through reviewer or export surfaces? | Approved purpose/access/disclosure constraints and handling requirements |
| CALIBRATION/BLIND/HOLDOUT governance | Are access, segregation and contamination rules compatible with privacy obligations? | Approved handling constraints; no inspection of case contents is required for this repository review |
| Retention/deletion/export | What data/artifacts/backups persist, for how long, and how are requests executed? | Retention schedule/decision, deletion/export limitations |
| Backup/recovery | Can deleted or restricted data reappear from backups? | Restore/deletion implications and documented controls |
| DPA/subprocessors | When are DPAs required and are processors/subprocessors actually used? | Applicable contract requirements and assumptions |
| Data-subject/incident handling | Which rights/incident duties apply to the intended model? | Responsibility/routing and material gaps |
| Local-first/deployment claims | Do claims match the actual intended architecture and data flows? | Approved bounded wording and exceptions |
| Licence/notices | Are Apache-2.0 and third-party obligations met? | Attribution/notices disposition and remediation list |
| Terms/disclaimer/support/warranty | Are limitations and responsibilities suitable for the bounded release? | Approved wording or tracked edits |
| Design-partner contracts | Do statements exceed evidence or conflict with E1 segregation? | Contractual issues/remediation |
| ThisTinti name/trademark | Is use cleared for intended territories/classes? | Search/opinion scope, conflicts, decision and limitations |
| Qualified claim | Does wording remain limited to Procurement v1 / P1 / E1? | Final approved statement and required limitations |
| Accuracy/compliance/autonomy claims | Are universal accuracy, compliance or autonomous-decision claims avoided unless separately evidenced? | Prohibited/approved wording |
| Economic claims | Are potential exposure, reviewer-confirmed anomaly and company-validated recoverable/avoided value kept distinct? | Approved terminology and examples/constraints |
| Public materials consistency | Do site, release notes, UI and sales copy agree with the reviewed claim? | Material inventory and delta/remediation list |

## Finding record

Every finding must have a stable ID, area, materiality (`BLOCKER`, `HIGH`, `MEDIUM`, `LOW`, `INFORMATIONAL` or reviewer-defined mapped equivalent), affected document/version, description/rationale, required remediation, owner, status, and reviewer retest/re-review disposition where applicable. Accepted residual risk must name the accepting accountable human and rationale; repository automation cannot accept legal/privacy risk.

Any unresolved condition that can expose protected company data, invalidate authorisation, materially misstate the Qualified claim, or make intended release wording legally incompatible is a release blocker under #21/#135 regardless of CI state.

## Claims guardrails for draft material

Until independent approval, public/commercial material must not imply that qualification is universal, that a finding is an autonomous decision, that ThisTinti establishes legal/accounting compliance, or that signalled value is automatically recovered. Economic reporting must preserve three separate levels: (1) potential exposure signalled by the system; (2) anomaly confirmed by a reviewer; (3) recoverable/avoided value validated by the company.

The target phrase itself remains a **future bounded release statement** until every #136 exit condition is satisfied. Presence of this document, a completed internal checklist, or a reviewer invitation is not approval.

## Final evidence index

The final independent package should include:

- reviewer identity/organisation, independence/conflict statement and date;
- exact review scope and material inventory with versions/hashes;
- completed review matrix, including the canonical-evidence snapshot rows where applicable;
- finding/remediation ledger and re-review evidence;
- residual-risk decisions by accountable humans;
- trademark/name clearance scope and limitations;
- final approved Qualified wording plus limitations/disclaimers;
- explicit statement of anything not reviewed;
- immutable report reference/hash where practical.

## Handoff readiness

This packet is ready to send to an independent reviewer once the actual material inventory is populated. Do not change `NOT REVIEWED` to a passing state internally. Final candidate-dependent wording, deployment assumptions and any materially changed public or data-flow material must be reviewed against the applicable release candidate before #135 can close.
