# P1/E1 human evidence campaign — preparation only

Status: **PREPARATION ONLY / NOT EXECUTED / NOT PASS**

This runbook prepares the final-candidate human campaign shared by #32 and #94. It does not replace human observation, assistive-technology use, untrained participants, or release-candidate evidence.

## Candidate binding

Before any session, record and freeze:

- source commit SHA;
- Windows installer filename and SHA-256;
- release/tag or candidate identifier;
- Procurement v1 / P1 / E1 identifiers;
- observation date, Windows version and relevant assistive technology/version;
- observer identity or pseudonymous reviewer ID.

Evidence from `v3.4.0-alpha.7-rc.1` is historical and MUST NOT be relabelled as evidence for a later Qualified candidate.

## Campaign separation and reuse

A single observed session may contribute to both issues only when the observation itself applies to both acceptance criteria. Every observation MUST carry one or both mappings:

- `ISSUE32_ONBOARDING_COMPREHENSION` — first successful experience, correct explanation of the product and reaching the first evidence-backed item in **Da controllare** without blocking assistance;
- `ISSUE94_HANDS_ON_OPERABILITY` — broader end-to-end use, evidence inspection, judgment recording, accessibility and operational friction.

Shared recruitment is allowed. Shared conclusions without explicit mapping are not.

## Required human tracks

### A. Keyboard-only

A person operates the applicable final candidate without a pointing device. Observe at minimum authentication/onboarding where applicable, primary navigation, document/evidence inspection, focus visibility/order, dialogs, and judgment recording. Record blockers, focus traps, unreachable controls and unexpected keyboard requirements.

### B. Assistive technology

A person using a screen reader or other applicable assistive technology performs a spot check on the final candidate. Record technology/version, accessible names, reading order, status/error announcements, evidence context and whether the user can distinguish source evidence, finding and human judgment.

### C. Untrained onboarding/comprehension

Run 5–10 sessions without teaching participants the product workflow in advance. Use the same neutral task prompt for all participants. Do not expose expected answers or ThisTinti findings before the participant has formed the requested understanding.

For #32, retain the existing acceptance target: at least 8 of 10 testers must explain the product correctly and reach the first evidence-backed item in **Da controllare** without blocking assistance. If fewer than 10 participants are used during preparation, do not reinterpret the 8/10 target as a percentage or declare #32 passed; resolve the issue acceptance criterion explicitly before qualification.

### D. Broader hands-on path

For #94, observe the applicable final workflow beyond onboarding, including evidence inspection and judgment entry. Keep #94's own acceptance criteria distinct; do not infer its result from #32 success.

## Neutral session protocol

1. Confirm consent/authorisation for observation and any recording.
2. Assign a pseudonymous session ID; avoid unnecessary personal data.
3. Record the exact candidate binding before starting.
4. Give only the predefined task prompt. Assistance that changes the outcome must be logged.
5. Capture timestamps and factual observations before interpretation.
6. Ask comprehension questions before revealing expected answers or system findings.
7. Map each observation to #32, #94, or both.
8. Classify findings only after the session; preserve raw notes.
9. If a blocking/serious defect is fixed, bind retest evidence to the corrected candidate. Never carry the prior PASS forward automatically.

## Session record schema

Each session record must contain:

```yaml
schema: thistinti-human-session.v0.1
status: OBSERVED # never pre-populate this in a blank template
session_id: H-###
candidate:
  source_sha: <40-hex>
  installer: <filename>
  installer_sha256: <64-hex>
  candidate_id: <tag-or-id>
environment:
  windows_version: <value>
  assistive_technology: <name/version-or-NONE>
track: [KEYBOARD_ONLY|ASSISTIVE_TECH|UNTRAINED_ONBOARDING|HANDS_ON]
issue_mapping: [ISSUE32_ONBOARDING_COMPREHENSION|ISSUE94_HANDS_ON_OPERABILITY]
consent_record: <reference>
started_at_utc: <timestamp>
ended_at_utc: <timestamp>
blocking_assistance: true|false
observations:
  - id: O-001
    timestamp: <timestamp>
    fact: <what was observed>
    mapping: [<issue mapping>]
findings:
  - id: HUF-001
    severity: BLOCKER|SERIOUS|MODERATE|MINOR
    description: <description>
    reproduction: <steps>
    evidence_refs: [<ref>]
comprehension:
  explanation_correct: true|false|NOT_APPLICABLE
  reached_first_evidence_backed_item: true|false|NOT_APPLICABLE
observer_attestation: <reference>
```

Blank templates MUST use placeholders and `PREPARATION_ONLY`; they must not contain fabricated `OBSERVED`, PASS, participant identities or attestations.

## Finding and remediation rules

- `BLOCKER`: prevents completion or reliable evidence/judgment inspection; release-blocking.
- `SERIOUS`: materially risks misunderstanding, inaccessible operation or incorrect judgment; resolve before qualification unless the governing issue explicitly documents otherwise.
- `MODERATE` / `MINOR`: document disposition and residual risk.
- Any UX/accessibility failure that prevents a reviewer from correctly inspecting evidence or recording judgment is release-blocking under #136.
- A remediation record must name the finding, corrective commit/build and retest session. A code change alone is not human retest evidence.

## Campaign summary

The final summary must report separately:

- candidate binding and participant/session count;
- #32 observations and its exact acceptance result;
- #94 observations and its exact acceptance result;
- keyboard-only result;
- assistive-technology result;
- blocking/serious findings and remediation/retest status;
- excluded/invalid sessions with reasons;
- residual limitations.

Do not collapse these into a single `PASS` field. Do not claim WCAG conformance from this campaign alone. Do not treat automated accessibility checks, screenshots, historical RC evidence or internal agent review as substitutes for the required human evidence.

## Exit / handoff

This preparation is ready for human execution only when the applicable final candidate is named. #32 and #94 remain open until the required real observations exist and their distinct acceptance criteria are satisfied. Any material candidate change after observation requires an applicability decision and, where the affected path changed, fresh human retest.