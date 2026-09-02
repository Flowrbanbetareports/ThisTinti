# ThisTinti 1.0 Qualified — final evidence dossier

Status: **PREPARATION ONLY / NOT A QUALIFICATION PASS**

This runbook prepares the final evidence binder for the bounded claim:

`ThisTinti 1.0 Qualified — Procurement v1 — profile P1 — protocol E1`

It does not create evidence, authenticate an external assessor, inspect BLIND/HOLDOUT cases, or replace any gate in #136. Its purpose is narrower: prevent the final release package from accidentally combining build-dependent evidence from different candidate SHAs or treating internal preparation as completion.

## Release identity

The first official Qualified release is exactly `1.0.0` / `v1.0.0`. Historical `v3.4.0-alpha.*` and RC tags are development prereleases and are not accepted as release identity for this dossier.

Before finalisation, record one full 40-hex `source_sha`. Every build-dependent evidence record in the dossier must bind to that same SHA. A later material change creates a new candidate and requires the evidence required by #136 change control to be rerun rather than inherited silently.

The dossier is deliberately distinct from repository merge enforcement in #133. #133 controls whether a PR may merge. This dossier records the evidence set used for the final bounded release claim after the relevant work has actually been performed.

## Evidence tracks

The template keeps the following tracks explicit and separate:

- Stream A technical candidate / same-SHA qualification sweep;
- Stream B P1/E1 freeze, blind evaluation and any required post-correction holdout;
- independent security assessment / retest (#134);
- independent privacy, legal, trademark and claims review (#135);
- official Windows signing and clean-system verification (#20);
- human onboarding/comprehension and broader hands-on/accessibility evidence (#32/#94);
- measured performance/capacity envelope (#166);
- Local/Self-Hosted data-protection posture (#167);
- backup/recovery, clean reconstruction and exit portability (#168);
- residual-risk reconciliation under #21;
- small controlled rollout/acceptance required by #136.

A track may be `WAITING_FINAL_SHA`, `WAITING_EXTERNAL`, `BLOCKED`, or `COMPLETE`. Only `COMPLETE` is accepted by `--final`, and it must carry at least one evidence reference. The validator checks structure and SHA binding only; it cannot prove that an external report, human observation, company authorisation or review is genuine.

## Build-dependent evidence

For every build-dependent record, capture:

- exact `source_sha`;
- evidence or workflow identifier;
- immutable URL or repository reference where possible;
- result/conclusion;
- date/time where relevant;
- artifact SHA-256 where the evidence concerns a release artifact.

Required workflow checks are recorded as an exact-head snapshot. In final mode every listed check must be `success` and bind to `source_sha`. The list itself must be accompanied by a policy/ruleset reference so this dossier does not invent a weaker substitute for #133.

## External and human evidence

Do not put confidential case contents into this dossier. Store references to the authorised evidence package, report, sealed reviewer records, or redacted deliverable. BLIND/HOLDOUT case content remains segregated under #132/#19.

Internal validators never convert `WAITING_EXTERNAL` into `COMPLETE`. Security, legal/privacy, human, company-validation and reviewer evidence remain external/human facts that must be obtained by the responsible subject.

## Change control

Immediately before finalisation:

1. compare the candidate SHA with every build-dependent record;
2. confirm whether any material parser, rule, provenance, storage, recovery, portability, deployment or evidence-interpretation change occurred after a completed campaign;
3. if yes, mark the affected track non-complete and rerun the evidence required by #136;
4. record whether a fresh holdout is required and, if required, its completed evidence reference;
5. run the structural validator with `--final` only after all real evidence is present.

A structurally valid final dossier is still not self-certifying. Final qualification remains the decision governed by #136 and the underlying independent/human evidence.

## Command

Preparation template check:

```bash
python scripts/validate_qualified_release_dossier.py qualification/final_evidence_dossier.template.json
```

Final structural check after copying and filling the template with real evidence:

```bash
python scripts/validate_qualified_release_dossier.py path/to/final_dossier.json --final
```

The committed template must remain preparation-only. Never fill it with invented evidence merely to make `--final` pass.
