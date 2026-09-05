# E1 pool segregation runbook — P1 / Procurement v1

Status: **PREPARATION ONLY — NOT BLIND EVIDENCE — NOT QUALIFICATION**

This runbook prepares the boundary between internal qualification tooling and the external people who will hold authorised cases and independent ground truth. It does not authorise data, create reviewers, prove independence, or inspect BLIND/HOLDOUT contents.

## Purpose

Before any calibration starts, E1 requires three already-assigned pools:

- `CALIBRATION`: 5–10 authorised cases that may be released for calibration;
- `BLIND`: 20–25 authorised cases hidden from developers until the frozen candidate and independent ground truth are ready;
- `HOLDOUT`: a non-empty independent pool reserved for the post-BLIND remediation candidate.

Public/synthetic material, including Evidence Factory material from #140, is `NOT_BLIND`. It may exercise tooling or pre-calibration stress paths but must never be substituted into BLIND/HOLDOUT qualification evidence.

## Roles and information boundary

**Authorised custodian** owns case authorisation, anonymisation/disposition, pool assignment, opaque pool manifests, access control and the cross-pool similarity/overlap check. Qualification C receives only references, counts, hashes, timestamps and status declarations needed by the E1 manifest; it does not receive BLIND/HOLDOUT case contents.

**Reviewer 1 and Reviewer 2** work independently. Their identities may be represented by opaque references in the repository-facing manifest, but the real independence evidence must exist outside the self-declared manifest. Neither reviewer may see ThisTinti output for a case before submitting their own assessment.

**Adjudicator** resolves reviewer disagreement only after both independent submissions are frozen. Adjudication is a separate step, not a way to create the two initial reviews.

**Qualification C** maintains the schema/validator and verifies structural consistency only. A validator `PASS` cannot turn a missing authorisation, reviewer, access control or real case set into evidence.

## Pre-calibration handoff

1. The custodian confirms the approved P1 scope reference and prepares authorised case sources under the applicable privacy/data handling procedure.
2. Before calibration, the custodian assigns every intended qualification case exactly once to `CALIBRATION`, `BLIND` or `HOLDOUT`.
3. The custodian produces one opaque manifest per pool and records a distinct SHA-256 for each. The repository-facing E1 manifest contains hashes and references, not case contents.
4. The custodian performs the cross-pool overlap/similarity check. Its evidence reference is recorded as `segregation.cross_pool_similarity_check.evidence_ref`. The internal validator does not independently prove that result.
5. BLIND and HOLDOUT access controls are applied before calibration. `developer_access_before_release` must remain `false` for both pools.
6. The three pool assignments are sealed. `pools_sealed_at` must not precede any individual pool seal timestamp.
7. Two independent reviewers and the adjudication procedure are secured before calibration. Record only appropriate opaque references; do not place unnecessary personal data in the repository.
8. Set the E1 manifest declarations from their real supporting records, then run:

   `python scripts/validate_e1_manifest.py <manifest.json> --pre-calibration`

9. A structural `PASS` means only that the declared prerequisite record is internally coherent. It is **not** evidence that the external records are genuine and it is **not** an E1 PASS.
10. Start calibration only after the pre-calibration structural gate is green and the responsible human has independently confirmed the referenced external evidence.

## Contamination controls

- Qualification C and developers must not open or inspect BLIND/HOLDOUT case contents while preparing this gate.
- BLIND/HOLDOUT `opened_at` remains `null` at the pre-calibration gate.
- If a BLIND/HOLDOUT case is exposed early, do not relabel the exposure away. Quarantine it and replace/reassign through the custodian process before proceeding.
- Material used for demos, stress tests, public-source research or pre-calibration debugging remains `NOT_BLIND` even if it resembles a future company case.
- Pool hashes/IDs must be distinct. Reusing the same manifest/hash across pools is rejected structurally.
- The cross-pool similarity result must be backed by an external evidence record; setting `PASSED` in JSON alone proves nothing.

## Sequence after the gate

1. Release only CALIBRATION cases according to the authorised procedure.
2. Freeze the candidate/configuration required by E1 before BLIND execution.
3. Independently freeze reviewer ground truth before comparing it with ThisTinti output.
4. Execute BLIND once under the protocol; record any remediation without rewriting the original result.
5. If remediation is needed, build the post-remediation candidate and then open the reserved HOLDOUT under its release condition.
6. The final E1 manifest may record actual pool-open timestamps. Final validation re-checks the declared segregation evidence without requiring those timestamps to remain null.

## Failure / stop conditions

Stop before calibration if any of the following is true:

- P1 is not approved and hash-bound;
- any pool is missing, empty, unsealed or lacks its opaque manifest/hash;
- CALIBRATION is outside 5–10 cases or BLIND outside 20–25;
- pool hashes or manifest IDs collide;
- BLIND/HOLDOUT access has already been opened to developers;
- authorisation/anonymisation-disposition/custodian references are absent;
- the cross-pool similarity/overlap check has not been completed;
- assignment/access-control evidence is absent;
- two independent reviewers or the adjudication protocol are not secured;
- calibration has already begun before the pre-calibration record was sealed.

Do not fix a stop condition by changing the manifest alone. Fix the real external prerequisite, record its evidence reference, then rerun the structural validator.
