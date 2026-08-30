# ThisTinti 1.0 Qualified — Stream C handoff package

Status: **PREPARATION ONLY**. This document does not assert that any external review, human campaign, signature, recovery exercise, approval, authorisation or qualification gate has passed.

Target claim: `ThisTinti 1.0 Qualified — Procurement v1 — profile P1 — protocol E1`.

This runbook prepares the independent and human-evidence work that can proceed without inspecting BLIND/HOLDOUT contents and without modifying the active Procurement provenance slice. Final evidence must always identify the exact candidate SHA/build/environment actually assessed.

## 1. Evidence identity contract

Every Stream C evidence record must include:

- `evidence_id` — stable identifier;
- `track` — `SECURITY`, `LEGAL_PRIVACY_CLAIMS`, `SIGNING`, `HUMAN`, `RECOVERY`, or `ROLLOUT`;
- `candidate_source_sha`;
- `release_version` and artifact identifier(s);
- artifact SHA-256 where applicable;
- environment/OS/deployment topology;
- protocol or checklist version/hash;
- assessor/observer identity or pseudonymous ID and independence/role declaration where required;
- start/end date;
- result state: `NOT_RUN`, `IN_PROGRESS`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`;
- source evidence references;
- findings/remediation references;
- residual-risk decision where applicable.

No historical evidence may be relabelled as final-candidate evidence solely because the workflow is unchanged.

## 2. Severity and remediation record

Use one record per finding:

```yaml
finding_id: C-TRACK-0001
track: SECURITY | LEGAL_PRIVACY_CLAIMS | HUMAN | RECOVERY | SIGNING | ROLLOUT
candidate_source_sha: <exact sha>
artifact_ids: []
environment: <exact environment>
title: <short title>
severity: CRITICAL | HIGH | MEDIUM | LOW | OBSERVATION
qualification_impact: BLOCKER | CONDITIONAL | NON_BLOCKING
category: <security/privacy/legal/claims/accessibility/operability/recovery/signing/etc>
reproduction_or_basis: <steps or review basis>
evidence_refs: []
first_observed_at: <timestamp>
status: OPEN | FIXED_PENDING_RETEST | RETESTED_PASS | ACCEPTED_RESIDUAL | REJECTED_NOT_APPLICABLE
remediation_commit_or_change: <sha/ref or null>
retest_evidence_refs: []
residual_risk_owner: <real approver or null>
residual_risk_rationale: <text or null>
```

Release-blocking rules:

1. Critical/high security conditions incompatible with controlled release block qualification.
2. Any defect capable of corrupting, substituting or falsely validating DOCUMENTO → FACT → FINDING → GIUDIZIO evidence is a blocker regardless of rarity.
3. A privacy/legal/claim issue that makes the bounded Qualified statement materially misleading blocks release.
4. A UX/accessibility defect that prevents a reviewer from correctly reaching evidence or recording judgment blocks release.
5. Fixes that materially affect parser/rule/provenance interpretation must not inherit previous blind evidence automatically; follow #136 change control and fresh holdout requirements.

## 3. Independent security / pentest handoff (#134)

### Package supplied to assessor

Supply only material authorised for the security assessment; do not provide BLIND/HOLDOUT case contents.

- exact candidate source SHA and artifact hashes;
- intended deployment topology and trust boundaries;
- authentication/session model and reverse-proxy assumptions;
- PostgreSQL role/RLS/migration model where applicable;
- document ingestion/parser/OCR/archive size and failure-mode description;
- release pipeline and dependency inventory sufficient for supply-chain review;
- backup/restore architecture;
- incident/vulnerability reporting route;
- explicit test-account/data handling instructions;
- this severity/remediation template.

### Minimum assessor coverage

- authenticated and unauthenticated attack surface;
- session/authentication, CSRF, CSP/CORS and proxy/header assumptions;
- workspace/tenant isolation and database privilege boundaries;
- malicious documents, malformed PDFs/images, OCR/parser boundaries, archive/size limits and denial-of-service paths;
- secrets exposure, CI/release permissions and dependency/supply-chain path;
- evidence integrity: attempts to substitute or stale DOCUMENT/FACT/FINDING/judgment support;
- backup/restore security properties;
- vulnerability disclosure and incident path.

### Required deliverables

- dated report naming exact candidate/artifacts/environment;
- complete finding register using equivalent severity/reproducibility detail;
- remediation decisions;
- retest evidence for blocking findings;
- explicit residual-risk record.

Internal automation or repository tests are preparation only and cannot mark #134 PASS.

## 4. Independent privacy/legal/trademark/claims handoff (#135)

### Review packet

Provide the reviewer with versioned copies/references of:

- P1/E1 bounded claim and exclusions;
- intended deployment/local-first statements;
- authorisation/anonymisation procedure for CALIBRATION/BLIND/HOLDOUT without exposing sequestered content;
- retention/deletion/export/backup operating assumptions;
- controller/processor/subprocessor assumptions and draft DPA position where applicable;
- incident/breach handling statements;
- Apache-2.0 notices and third-party attribution inventory;
- public site, release notes, pilot material, terms/disclaimer/support/warranty wording intended for 1.0;
- name/trademark usage and intended territories/classes for professional clearance;
- economic-value language.

### Claims guardrail

Public/commercial wording must preserve these distinctions:

1. `potential exposure signalled by ThisTinti`;
2. `anomaly confirmed by a reviewer`;
3. `recoverable or avoided value validated by the company`.

Do not convert one level into another by implication. Do not claim universal accuracy, legal compliance, autonomous accounting/payment decisions or guaranteed recovery.

### Review output schema

```yaml
review_item_id: L-0001
area: PRIVACY | DATA_GOVERNANCE | LICENSING | TRADEMARK | TERMS | CLAIMS
materiality: BLOCKER | MATERIAL | MINOR | OBSERVATION
source_document_and_version: <ref>
issue: <description>
required_change: <description or null>
status: OPEN | REMEDIATED_PENDING_REVIEW | APPROVED | ACCEPTED_RESIDUAL | NOT_APPLICABLE
reviewer_basis: <rationale>
approved_wording: <text/ref or null>
```

No internal review may be labelled independent evidence for #135.

## 5. Human evidence campaign mapping (#32 + #94)

Use one coordinated final-candidate campaign where observations genuinely apply to both issues, but record applicability separately.

### Participant/session record

```yaml
session_id: H-0001
candidate_source_sha: <exact sha>
artifact_sha256: <hash>
environment: <Windows/build/display/assistive tech>
participant_id: <pseudonymous id>
prior_this_tinti_experience: NONE | LIMITED | EXPERIENCED
assistance_given: <none or exact description>
observer_id: <real observer>
started_at: <timestamp>
ended_at: <timestamp>
evidence_refs: []
```

### #32 onboarding/comprehension criteria

Record separately whether the participant:

- correctly explains the product's purpose without being coached;
- reaches the first evidence-backed item in `Da controllare`;
- does so within the protocol target and without blocking assistance;
- encounters terminology or navigation confusion that changes interpretation.

The target remains at least 8/10 untrained testers meeting the #32 acceptance criterion; do not infer this from smaller or differently instructed samples.

### #94 broader hands-on criteria

For the applicable final candidate record observed completion/failure of:

- installation and first run;
- local workspace creation/access and primary navigation;
- real demo/job-worker path;
- finding → evidence → extracted row → original document trace;
- supervised correction and reanalysis;
- activity/retry/restart/persistence;
- diagnostics and JSON report;
- product/project claims consistent with actual local-first/no-SaaS behaviour;
- update/backup/restore/uninstall where applicable;
- zoom 125/150/200%;
- full keyboard path;
- assistive-technology spot check, preferably NVDA;
- serious-defect reproduction evidence.

### Shared-observation rule

A single observation may be referenced by both #32 and #94 only when candidate/build/environment match and the raw observation really satisfies the distinct criterion in each issue. Keep separate mapping rows:

```yaml
observation_id: OBS-0001
session_id: H-0001
issue_32_criterion: <criterion or null>
issue_32_result: PASS | FAIL | NOT_APPLICABLE
issue_94_criterion: <criterion or null>
issue_94_result: PASS | FAIL | NOT_APPLICABLE
evidence_refs: []
```

Human observation cannot be replaced by automated accessibility tests.

## 6. Windows signing preparation (#20)

Preparation checklist before final freeze:

- select certificate type/provider and legal ownership identity;
- document private-key custody model; keys must remain outside repository and logs;
- choose timestamp authority and verification command/process;
- design signing order for application executable, installer and uninstaller where supported;
- ensure release workflow signs only trusted release contexts, never untrusted fork PRs;
- preserve SHA-256 checksum generation independently of signature;
- define certificate renewal, revocation and emergency rotation procedure;
- define negative publication rule: unsigned or invalidly signed artifacts cannot become official Qualified release assets.

Final evidence must be collected on the frozen Qualified artifacts and include publisher identity display, cryptographic verification, timestamp verification and checksums. Preparation is not PASS.

## 7. Backup/recovery exercise

### Preconditions

- use intended release deployment/storage model;
- identify exact candidate SHA and schema/database version;
- define recovery point objective used by the exercise, without presenting it as a contractual SLA unless formally approved;
- create a manifest of data expected before backup and after restore.

### Exercise procedure

1. Create representative authorised/non-sensitive operational state or approved synthetic state.
2. Record pre-backup manifest and hashes/counts for key entities.
3. Perform documented backup using the intended operator path.
4. Simulate loss/corruption only in an isolated test environment.
5. Restore using the documented recovery path.
6. Verify application startup, migration/schema compatibility and persistence.
7. Verify evidence-chain objects remain internally consistent; do not merely check that files exist.
8. Record elapsed operator steps, errors, manual interventions and logs.
9. Open findings for any missing, stale, duplicated or silently changed evidence.

### Recovery evidence record

```yaml
recovery_run_id: R-0001
candidate_source_sha: <sha>
environment: <exact environment>
backup_artifact_ref: <ref>
backup_hash: <hash>
pre_manifest_ref: <ref>
post_restore_manifest_ref: <ref>
result: PASS | FAIL
operator_id: <real operator>
evidence_refs: []
findings: []
```

A real release-environment exercise remains required before Stream C exit.

## 8. Final Stream C evidence index

Before #136 can close, assemble a versioned evidence index with one row per required track:

| Track | Required issue/gate | Candidate SHA | Evidence ref | Status | Blocking findings | Retest/final verification |
|---|---|---|---|---|---|---|
| Security | #134 | | | NOT_RUN | | |
| Privacy/legal/trademark/claims | #135 | | | NOT_RUN | | |
| Windows signing | #20 | | | NOT_RUN | | |
| Onboarding/comprehension | #32 | | | NOT_RUN | | |
| Hands-on/accessibility/operability | #94 | | | NOT_RUN | | |
| Backup/recovery | #136 | | | NOT_RUN | | |
| Controlled rollout/acceptance | #136 | | | NOT_RUN | | |

`NOT_RUN` is the correct state until real evidence exists.

## 9. External handoff readiness checklist

A track is ready to hand to an external/person-dependent actor when:

- scope and acceptance criteria are frozen enough for that actor's task;
- exact candidate dependency is labelled as either `PRE-FREEZE PREPARATION` or `FINAL-CANDIDATE REQUIRED`;
- no BLIND/HOLDOUT contents are disclosed outside protocol;
- evidence templates and severity/remediation workflow are supplied;
- responsibility for retest/review is explicit;
- there is no wording that could be mistaken for PASS before execution.

Current safe use of this document is preparation and handoff only.
