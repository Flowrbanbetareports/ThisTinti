# Pilot E1 blind execution handoff — preparation only

Status: `PREPARATION_ONLY_NOT_EXECUTED`

This document prepares issue #19 for an authorised blind run without opening, inspecting, copying, or classifying BLIND/HOLDOUT case contents. It is not a FREEZE, PASS, reviewer record, ground truth, company authorisation, or external evidence.

## Preconditions before any blind case is exposed to ThisTinti

1. P1/E1 scope and exclusions are approved and versioned.
2. Calibration is complete and the final candidate is frozen.
3. The exact source SHA, parser/acquisition versions, Procurement Rule Pack identity/hash, Practice Model, Company Profile, provenance configuration and qualification configuration are recorded.
4. The blind registry contains 20–25 immutable case IDs and content hashes only after authorisation/anonymisation controls have been completed by the authorised custodian.
5. BLIND and HOLDOUT remain segregated from development access. Any pre-freeze content access is contamination and must be recorded as protocol failure.
6. Two independent reviewers are assigned and produce their reference records before exposure to ThisTinti findings. Reviewer A and Reviewer B must be distinct people.
7. Adjudication is separate, dated and attributable. It must not overwrite either original reviewer record.
8. No tuning, parser/rule/provenance change, prompt adjustment, case reassignment or pool movement occurs during the blind run.

## Manifest boundary

The machine-readable manifest may contain metadata required to prove execution identity and protocol integrity, but this repository must not receive BLIND/HOLDOUT document bytes or human reference contents merely to validate structure.

Required metadata includes:

- official claim identity: `1.0.0` / `v1.0.0` only for final release evidence;
- exact 40-hex candidate SHA;
- immutable P1/E1 component identities/hashes;
- blind case count and per-case opaque ID/content hash;
- explicit authorisation/anonymisation status;
- reviewer A/B identifiers proving distinctness without storing sensitive reviewer material here;
- timestamps showing reviewer references were sealed before findings exposure;
- adjudication metadata kept separate;
- run start/end timestamps;
- protocol-contamination flag;
- material-change flag after freeze;
- outcome state.

## Fail-closed rules

Final structural validation must fail when any of the following is true:

- candidate SHA is missing, malformed, or does not match the frozen identity;
- release identity is replaced by a legacy `v3.4.0-alpha.*` prerelease;
- blind pool is outside 20–25 cases;
- duplicate case IDs or content hashes exist;
- authorisation or anonymisation is not positively verified;
- a BLIND case is marked as exposed before freeze;
- reviewers are missing or not distinct;
- either reviewer reference is not sealed before ThisTinti findings exposure;
- adjudication replaces an original reviewer record;
- protocol contamination is present;
- a material parser/rule/provenance/evidence-interpretation change occurred after freeze without a new candidate and fresh holdout path;
- the manifest attempts to claim company-validated recoverable value without a distinct company-validation record.

## Execution sequence

The authorised operator freezes the candidate, seals the manifest, verifies the segregated blind pool, confirms reviewer references are already sealed, executes the frozen candidate once against the blind pool, records outputs without tuning, then performs comparison/adjudication and metrics outside the development-access boundary. Any material defect fix creates a new candidate; the original blind result is retained as historical evidence and a fresh independent holdout is required before the Qualified release can inherit the corrected claim.

## Economic reporting separation

Always report separately:

1. `potential_exposure_signalled_by_system`;
2. `reviewer_confirmed_anomaly`;
3. `company_validated_recoverable_or_avoided_value`.

No conversion between these levels is automatic.

## Handoff

The validator and template in this branch only validate evidence structure. They do not authenticate reviewers, authorisations, companies, signatures, content hashes, or the factual correctness of any blind result. Human/external evidence remains mandatory where required by #19/#136.