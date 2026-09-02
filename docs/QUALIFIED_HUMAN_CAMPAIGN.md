# ThisTinti 1.0 Qualified — final human evidence campaign

Status: **PREPARATION ONLY / NOT EXECUTED / NOT A PASS**.

This campaign coordinates the final-candidate human evidence required by #32 and #94 without collapsing their acceptance criteria. It does not simulate participants, observers, assistive-technology users, screenshots, defects, approvals, or accessibility results.

Target release claim: `ThisTinti 1.0 Qualified — Procurement v1 — profile P1 — protocol E1`.

## Candidate identity

Every executed session must bind to the same applicable candidate identity:

- full 40-hex source SHA;
- release/artifact identifier;
- artifact SHA-256;
- Windows/build/display environment;
- installed-build identity where applicable;
- campaign protocol version/hash;
- assistive technology and version when used.

Historical RC1/RC13 observations and automated browser/accessibility checks remain regression context only. They cannot satisfy final human gates for another candidate.

## Participant boundary

For #32, use ten genuinely untrained participants (`prior_this_tinti_experience = NONE`) so the existing `8/10` acceptance target can be evaluated directly. Record assistance exactly; blocking assistance means that session does not satisfy the #32 success criterion.

A participant may also contribute #94 observations when the same session actually exercises the corresponding path. Do not infer #94 PASS merely because the participant completed onboarding.

Observers must record what happened, not coach a desired result. Participant and observer identifiers may be pseudonymous, but the campaign custodian must retain the real consent/authorisation record outside public evidence where required.

## #32 success record

A session satisfies #32 only when all of the following are observed on the bound candidate:

1. the participant explains the product purpose correctly without coaching;
2. the participant reaches the first evidence-backed item in `Da controllare`;
3. the participant does so within the protocol target;
4. no blocking assistance is provided;
5. no serious terminology/navigation failure changes the participant's interpretation of the result.

Final structural acceptance requires ten untrained sessions and at least eight session-level successes. Structural validation is not independent human evidence and cannot itself close #32.

## #94 observed path

The coordinated campaign records the applicable final-candidate observations separately for:

- installation and first run;
- workspace creation/access and primary navigation;
- demo/job-worker path;
- finding → evidence → extracted row → original-document trace;
- supervised correction and reanalysis;
- activity/retry/restart/persistence;
- diagnostics and JSON report;
- project/product claims as observed in the installed product;
- update/backup/restore/uninstall where applicable;
- zoom 125%, 150% and 200%;
- full keyboard-only path by a person;
- assistive-technology spot check by a person, preferably NVDA;
- serious-defect reproduction evidence.

`NOT_APPLICABLE` is allowed only with a recorded rationale. A missing observation is `NOT_RUN`, not PASS.

## Accessibility evidence discipline

Keyboard and assistive-technology observations must have `observation_mode = HUMAN`. Automated axe/Chromium/unit-test results may be linked as supplemental technical evidence but cannot occupy the human evidence field.

For the assistive-technology spot check record tool/version, task path, announcements/focus behaviour relevant to the task, any blocker, and the observer's evidence references. Do not claim WCAG conformance from this spot check; professional accessibility review remains a separate claim if one is made.

## Findings and stop rules

Use the Stream C severity/remediation scheme. Stop or mark the campaign blocked when a defect:

- prevents a reviewer from reaching the source evidence needed to understand a finding;
- prevents recording or understanding the human judgment;
- makes keyboard-only or assistive-technology completion impossible for the required task;
- materially misrepresents local-first/no-SaaS or other release claims;
- causes data loss, unsafe recovery behaviour, or a serious installed-product failure during the observed path.

Material fixes must be tied to a new candidate identity and retested as required by #136 change control. Do not silently carry observations across materially changed builds.

## Evidence manifest

Use `docs/qualification/human-campaign.template.json` as the machine-readable record. `scripts/validate_human_campaign.py` checks fail-closed structural invariants only.

Preparation validation:

```bash
python scripts/validate_human_campaign.py docs/qualification/human-campaign.template.json
```

Final structural validation after real execution:

```bash
python scripts/validate_human_campaign.py path/to/executed-human-campaign.json --final
```

`--final` requires exact candidate/artifact identity, ten untrained #32 sessions, >=8 #32 successes, human keyboard evidence, human assistive-technology evidence, complete #94 criterion mapping or justified `NOT_APPLICABLE`, and no open release-blocking human findings. Passing this validator means only that the evidence package is structurally complete; it does not prove the observations are truthful, independent, or sufficient for an external accessibility claim.

## Shared-observation mapping

Each raw observation may map independently to #32 and #94. Store separate issue/criterion/result fields. A shared observation is reusable only when candidate, artifact, environment, participant/session and raw evidence reference are the same and the observation genuinely addresses both criteria.

No BLIND/HOLDOUT case contents are required for this campaign. Demo/synthetic or otherwise authorised non-blind material is sufficient for human workflow/accessibility observation unless a later approved protocol explicitly requires something else.
