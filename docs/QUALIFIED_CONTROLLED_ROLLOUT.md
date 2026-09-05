# Qualified controlled rollout handoff

Status: **PREPARATION ONLY — NOT EXECUTED — NOT PASS**

This runbook prepares the small controlled rollout/acceptance step required by #136 for the bounded release claim:

`ThisTinti 1.0 Qualified — Procurement v1 — profile P1 — protocol E1`

It does not create user evidence, customer acceptance, security evidence, legal approval, signing evidence, recovery evidence, BLIND/HOLDOUT evidence, or a Qualified result. Those gates remain independent.

## 1. Purpose

The controlled rollout is the final limited operational exercise after the applicable candidate has been frozen and the release package is ready for real use. Its purpose is to discover release-blocking operational defects in the intended use path before broader distribution.

The rollout must answer a narrow question:

> Can the exact candidate and official artifacts be used in the intended bounded Procurement P1 workflow, by authorised people in an approved environment, without an unresolved release blocker?

It must not be used to manufacture product-market-fit evidence, replace #19, reclassify public/synthetic cases as BLIND/HOLDOUT, or turn internal preparation into external validation.

## 2. Preconditions

Do not start the rollout until the rollout owner records which of the following are complete, not applicable, or still blocking:

- exact source SHA and release artifact identities are frozen;
- P1 scope and exclusions are frozen;
- E1 manifest and candidate identity are frozen;
- applicable same-SHA technical gates are green;
- #19 blind evidence exists and any required post-correction holdout has been completed;
- #134 independent security assessment and required retests are complete;
- #135 independent privacy/legal/trademark/claims review is complete for the applicable wording;
- #20 official Windows signing is verified on the official artifacts;
- #32/#94 applicable human evidence is complete on the final candidate;
- backup/recovery has been exercised on the intended release environment;
- release-blocking defects from the above tracks are closed or explicitly rejected with a documented decision compatible with #136.

A missing prerequisite is not converted into a PASS by a successful rollout observation.

## 3. Segregation and data boundary

The rollout must not expose E1 BLIND/HOLDOUT contents to development personnel outside the access rules established by #132/#19.

Allowed rollout inputs are limited to material whose use is separately authorised for this operational exercise. Public or synthetic material already inspected by development agents remains `NOT_BLIND` and may be used only for rehearsal or operational smoke coverage, never as a substitute for the E1 blind result.

Record only the minimum repository-facing metadata needed to prove what was exercised. Do not commit protected customer documents, credentials, personal data, reviewer notes, or secrets.

## 4. Candidate identity lock

Before the first session, record in the evidence manifest:

- source SHA;
- release/version identifier;
- installer/application artifact names and SHA-256 values;
- signature/publisher verification reference where applicable;
- Rule Pack, Practice Model and Company Profile identities/hashes;
- parser/engine versions;
- P1/E1 scope/manifest identity;
- intended environment identifier and relevant configuration reference;
- rollout plan version.

If any material candidate identity changes during the rollout, stop and classify the impact under #136 change control. Do not silently combine observations from different candidates.

## 5. Authorised rollout plan

Before execution, the rollout owner records:

- approving person/role reference;
- participating organisation/environment reference where applicable;
- authorised participant roles;
- approved input-data class and handling rules;
- session window;
- support/escalation contact;
- rollback owner and rollback method;
- explicitly excluded operations;
- acceptance decision authority.

Participant count and operational duration are not invented by this repository. They must be set by the real rollout plan and justified as sufficiently small/controlled for the intended environment.

## 6. Required operational path

Exercise only applicable, supported P1 operations. At minimum the observed path should cover, where applicable:

1. install/update and start the exact official artifact;
2. enter or access the intended local/workspace environment;
3. ingest an authorised Procurement practice through an allowed acquisition/parser path;
4. observe degraded/unsupported acquisition behaviour when naturally applicable or through separately authorised rehearsal material;
5. run analysis and reach an evidence-backed item requiring human review;
6. inspect finding -> fact/evidence -> source document linkage;
7. record a supervised human judgment without treating the machine output as an autonomous decision;
8. exercise a correction/reanalysis path where applicable;
9. restart and verify persistence/state continuity;
10. inspect diagnostics/audit information needed for support;
11. exercise the approved backup/recovery interaction or reference the separately executed recovery evidence without claiming that a reference is a fresh restore test;
12. verify rollback/uninstall/update behaviour required by the rollout plan.

The rollout is not a licence to introduce new features or bypass unsupported paths to make the demonstration look complete.

## 7. Observation record

For each session record an opaque session ID and:

- exact candidate/artifact identity;
- date/time and environment reference;
- observer and participant-role references;
- authorised input class/reference;
- planned steps attempted;
- steps completed without blocking assistance;
- defects/findings with reproduction references;
- severity/materiality;
- whether the finding affects evidence correctness, confidentiality, integrity, availability, reviewer comprehension, recovery, or release claims;
- remediation owner/status;
- retest reference where applicable;
- participant/observer acceptance statement reference, if one is genuinely provided.

Do not fabricate signatures, participant statements, customer approval, timestamps, organisation names, or defect outcomes in the repository template.

## 8. Severity and stop rules

Stop the rollout and mark the release decision `BLOCKED` if a reproducible condition can:

- corrupt, substitute, stale, or falsely validate DOCUMENT -> FACT -> FINDING -> GIUDIZIO evidence;
- expose protected company data or credentials beyond the approved boundary;
- bypass the intended human-review model;
- make the official artifact unverifiable or materially different from the frozen candidate;
- prevent required reviewer evidence inspection or judgment recording;
- make the intended recovery/rollback path unusable;
- invalidate an approved security/privacy/legal/release claim;
- otherwise meet the Critical/High or qualification-critical policy in #136.

Serious UX/accessibility defects that prevent correct evidence inspection or judgment are release blockers even when CI remains green.

A blocker must be remediated, gain regression coverage where technically appropriate, and be retested on the corrected candidate. Material corrections trigger the change-control consequences defined by #136, including fresh holdout evidence where required.

## 9. Acceptance decision

The final rollout record may use only:

- `NOT_EXECUTED` — no real rollout occurred;
- `BLOCKED` — one or more unresolved release blockers remain;
- `CONDITIONAL` — execution occurred but explicitly listed non-blocking residual items or prerequisite decisions remain; this is **not** a Qualified PASS;
- `ACCEPTED` — the authorised decision authority accepted the exact exercised candidate for the bounded rollout scope and no unresolved release blocker remains.

`ACCEPTED` is one input to #136. It does not by itself mean `ThisTinti 1.0 Qualified`.

## 10. Cross-gate mapping

Evidence may be referenced across gates only when the observation genuinely satisfies each gate's own acceptance criterion:

- #32: onboarding/comprehension criteria remain distinct;
- #94: broader hands-on/accessibility/operability criteria remain distinct;
- #134: independent security testing cannot be self-certified by rollout participants;
- #135: legal/privacy/trademark/claims approval cannot be inferred from operational success;
- #20: Authenticode/signature verification is an independent artifact property;
- #19/#132: blind/holdout and reviewer protocol remain independent scientific evidence;
- backup/recovery: a separately exercised restore remains separately evidenced.

Do not collapse these into a single `rollout_pass=true` flag.

## 11. Evidence package for #136

The handoff back to the qualification supervisor should contain only reviewable references and non-sensitive evidence:

- completed controlled-rollout evidence manifest;
- exact candidate/artifact hashes;
- rollout approval/authorisation reference;
- session ledger with opaque IDs;
- defect/remediation/retest ledger;
- residual-risk decisions;
- rollback/recovery references;
- final acceptance decision reference;
- explicit statement of limitations and anything not exercised.

Protected source documents and confidential customer material stay in the approved evidence store, not in Git.

## 12. Rehearsal

This runbook and its manifest template may be rehearsed internally before the final candidate exists. Rehearsal must be labelled `REHEARSAL / NOT_BLIND / NOT QUALIFICATION EVIDENCE` and may use synthetic or public material already exposed to development.

A rehearsal PASS proves only that the handoff mechanics are usable. It cannot satisfy the real controlled-rollout gate.
