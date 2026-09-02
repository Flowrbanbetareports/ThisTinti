# ThisTinti 1.0 Qualified — controlled rollout acceptance

Status: **PREPARATION ONLY / NOT EXECUTED / NOT A QUALIFICATION PASS**

This runbook prepares the small controlled rollout/acceptance gate required by #136 for the bounded claim:

`ThisTinti 1.0 Qualified — Procurement v1 — profile P1 — protocol E1`

It does not recruit a company, create authorisation, simulate an operator, inspect BLIND/HOLDOUT material, or turn internal testing into customer acceptance.

## Purpose

The rollout is a final operational check on the exact release candidate after the applicable qualification evidence is complete. It is intentionally small and controlled. Its purpose is to discover release-blocking operational defects in realistic authorised use, not to create marketing evidence or broaden the Qualified scope.

## Entry conditions

Do not start the controlled rollout until all of the following are recorded:

- exact full 40-hex source SHA and official candidate identity `1.0.0` / `v1.0.0`;
- exact release artifact SHA-256 values used by the operator;
- P1 scope and exclusions supplied to the participant/operator;
- explicit authorisation for the data and environment used in the rollout;
- confirmation that no E1 BLIND/HOLDOUT case content is exposed to development staff through this campaign;
- security/privacy/legal constraints applicable to the deployment are available;
- backup/recovery and operator escalation material are available;
- a named stop condition and rollback/recovery path exist before first use.

A rollout against a legacy `v3.4.0-alpha.*`/RC build is historical evidence only and cannot satisfy this gate.

## Minimum observed campaign

For each authorised rollout session record, at minimum:

- participant/operator identifier or pseudonymous stable ID;
- organisation/environment identifier where disclosure is permitted;
- UTC start/end timestamps;
- candidate source SHA and artifact hash actually used;
- deployment mode and relevant environment assumptions;
- authorised workload/data class, without copying confidential document content into the qualification manifest;
- P1 tasks attempted and whether they completed without blocking assistance;
- whether evidence could be inspected and a human judgment recorded correctly;
- restart/persistence behaviour if exercised;
- backup/recovery or rollback action if triggered;
- every observed defect with severity, reproduction reference and disposition;
- explicit operator/observer attestation that the record reflects observed behaviour rather than a synthetic test.

The campaign may reuse evidence from #32/#94 only where the observation is genuinely applicable and explicitly cross-referenced. It may not inherit a PASS merely because the human campaign was green on another SHA.

## Severity and stop rules

The rollout must stop or remain non-complete when any unresolved condition can invalidate the bounded release claim, including:

- critical/high security or operational defect;
- epistemic/provenance integrity defect;
- false-green behaviour or evidence-binding failure;
- inability of a reviewer to inspect evidence or record judgment correctly;
- material data-protection, recovery, portability or resource/capacity failure;
- any defect classified as a release blocker under #136.

A stopped campaign is evidence of a blocker, not a failed administrative exercise. Correct the defect in the owning lane, add regression coverage where applicable, determine change-control consequences, and rerun the evidence required by #136 on the corrected candidate.

## Acceptance discipline

The controlled rollout may be structurally marked complete only when:

1. every session is tied to the exact final candidate SHA/artifacts;
2. authorisation is recorded for each session/workload;
3. at least one real authorised operator/session was observed;
4. no unresolved release blocker remains;
5. every serious finding has a disposition and required retest evidence;
6. scope/limitations observed in the rollout are carried into the final dossier;
7. no BLIND/HOLDOUT contents were used as rollout material or exposed through the campaign;
8. the final record is referenced from the `controlled_rollout` track of the #136 final evidence dossier.

This preparation intentionally sets no commercial KPI, conversion target, ROI threshold or sales-success criterion. Those would be productisation/commercialisation concerns, not evidence that the bounded Qualified release is safe and operable.

## Structural validation

Use the committed template only as a skeleton:

```bash
python scripts/validate_controlled_rollout.py qualification/controlled_rollout.template.json
```

After a real authorised campaign, copy the template outside the repository fixture, fill it with evidence references and run:

```bash
python scripts/validate_controlled_rollout.py path/to/controlled_rollout.json --final
```

`--final` validates structure and fail-closed conditions only. It cannot authenticate a company, participant, authorisation, observer, defect disposition or acceptance decision.