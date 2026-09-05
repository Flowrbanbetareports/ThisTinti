# ThisTinti 1.0 Qualified — final human evidence campaign

Status: **PREPARATION ONLY / NOT A PASS**.

This contract operationalises the shared final-candidate human campaign for #32 and #94. It does not create participants, observers, accessibility evidence, comprehension evidence, approval, or qualification evidence. It must not use BLIND/HOLDOUT contents.

## Candidate identity

Every counted session must bind to the same final candidate:

- `release_version = 1.0.0`;
- `release_tag = v1.0.0`;
- one full 40-hex source SHA;
- one exact artifact identifier and SHA-256;
- the actual environment used by the participant.

Historical `v3.4.0-alpha.*` / RC sessions remain development evidence and cannot be promoted into final Qualified evidence.

## Session eligibility

A counted session must be genuinely performed and observed by a person. Automated browser runs, scripted accessibility checks, synthetic event playback, contributor self-review, fabricated sessions, or inferred results are not human evidence.

The session record must state participant ID, observer ID, prior ThisTinti experience, assistance given, candidate/artifact identity, environment, start/end time and evidence references. No BLIND/HOLDOUT content may be used in this campaign.

## #32 onboarding/comprehension

The existing acceptance target remains unchanged: at least 8 successful participants out of 10 untrained participants.

A participant counts as untrained only when `prior_this_tinti_experience = NONE`. A success requires all of:

1. the participant explains the product purpose correctly without coaching;
2. reaches the first evidence-backed item in `Da controllare`;
3. does so inside the protocol target;
4. receives no blocking assistance.

Limited/experienced contributors may generate useful #94 observations but cannot be counted toward #32's 8/10 target.

## #94 hands-on/accessibility

The final campaign must preserve distinct human evidence for:

- keyboard-only navigation;
- assistive-technology use, naming the actual technology used;
- the broader hands-on product path.

Automated Chromium/accessibility tests remain regressions only. A PASS row for keyboard or assistive technology must point to at least one supporting human-observed session on the exact candidate.

## Shared observation rule

A session may support both issues only when the raw observation is genuinely applicable to both. The #32 and #94 mappings remain separate; one issue's PASS cannot be copied into the other.

## Findings and remediation

Record serious human/accessibility findings individually. `CRITICAL`, `HIGH` or `SERIOUS` findings must be remediated and retested before a structurally complete final campaign record is accepted by the validator. A fix that materially changes parser/rule/provenance interpretation returns to #136 change control rather than being silently accepted here.

## Validator semantics

Run:

```text
python scripts/validate_human_campaign.py <manifest>
python scripts/validate_human_campaign.py <manifest> --final
```

Preparation mode accepts placeholders and requires `status = PREPARATION_ONLY`. Final structural mode requires actual hashes, `status = FINAL_EVIDENCE_RECORDED`, exact candidate consistency, human-only session types, #32 sample arithmetic and supporting #94 sessions.

Even in final structural mode the only successful output is:

`VALID_STRUCTURE_NOT_QUALIFICATION_PASS`

The validator cannot authenticate who participated, whether the observer was independent, whether a screen reader was really used, whether comprehension was genuine, or whether evidence references are truthful. Those remain human/external facts. `qualification_decision` must therefore remain `NOT_A_PASS`.
