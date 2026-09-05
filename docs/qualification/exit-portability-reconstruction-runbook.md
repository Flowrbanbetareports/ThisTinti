# P1/E1 exit portability + reconstruction evidence — preparation only

Status: **PREPARATION ONLY / NOT EXECUTED / NOT PASS**

Refs: #136, #168, #21. This runbook extends the existing recovery-evidence lane; it does not replace `docs/qualification/recovery-evidence-runbook.md` and does not create a second backup methodology.

## Purpose

Issue #168 has two separate questions that must not be collapsed:

1. **Disaster reconstruction:** can an exact candidate be reconstructed on a clean, isolated target from a versioned package while preserving the evidence chain?
2. **Exit portability:** can an authorised operator leave the product with a package whose structure, integrity metadata and useful contents remain meaningfully inspectable without a running ThisTinti service?

A successful backup/restore is not automatically a portability PASS. Conversely, an archive that can be opened is not proof of recoverability.

## Existing mechanism reused

The current backup tool emits `thistinti-backup-v1`: a ZIP with `manifest.json`, a consistent database snapshot and, by default, application storage. The manifest records release version, database engine, entries, sizes and SHA-256 values. SQLite uses a database snapshot; PostgreSQL uses `pg_dump --format=custom --no-owner --no-privileges`.

The existing recovery qualification already requires an isolated restore, full-storage inclusion, bundle identity, database/storage/evidence-chain verification, measured RPO/RTO and operator evidence. #168 must reuse those records rather than claim a second restore proof.

### Post-#171 canonical-evidence requirement

Current `main` stores immutable canonical document bytes in database-backed `document_evidence_snapshots` in addition to the historical storage surface. Therefore the RELEASE 1.0.0 reconstruction exercise must treat those rows as first-class evidence, not as an implementation detail hidden inside a generic database restore.

For an exact candidate containing canonical snapshots, capture before loss and verify after restore, at minimum:

- snapshot row presence/count for the exercised authorised dataset;
- tenant/workspace ownership and document linkage;
- canonical byte length and canonical SHA-256 identity for representative or complete scope as declared;
- equality between restored canonical bytes and the pre-loss canonical snapshot identity;
- reviewer/export evidence identity where the applicable qualification contract consumes canonical bytes;
- no fallback to mutable filesystem bytes being counted as proof that canonical evidence survived.

Because `thistinti-backup-v1` includes a consistent database snapshot, the snapshot rows should be transported by that database image. That is a mechanism observation, not a PASS: the clean-machine exercise must prove they restore correctly on the exact candidate/package.

## Conservative 1.0 portability contract

For RELEASE 1.0.0, do not claim vendor-neutral semantic export unless the exact candidate demonstrates it. The current backup format is a reconstruction package first.

The qualification exercise must classify each layer separately:

- `container`: ZIP can be opened with a standard offline archive tool and `manifest.json` is readable JSON;
- `source_documents`: stored source files included in the package can be enumerated and extracted offline when authorisation permits;
- `integrity_metadata`: entry paths, byte sizes and SHA-256 values can be inspected offline from `manifest.json`;
- `database_snapshot`: snapshot format and required third-party tooling are documented exactly;
- `canonical_evidence_snapshots`: database-backed immutable canonical evidence is preserved and can be correlated to documents after reconstruction; offline intelligibility must be demonstrated separately rather than inferred from row presence;
- `semantic_records`: DOCUMENT/FACT/FINDING/GIUDIZIO and provenance records are meaningfully inspectable outside a running ThisTinti service only if the exercise demonstrates a documented, reproducible offline method on the exact package.

For PostgreSQL custom dumps, `database_snapshot` must not be described as directly human-readable merely because it is portable as a file. If inspection requires PostgreSQL/`pg_restore`, record that dependency. If no supported offline semantic inspection method exists, `semantic_records` remains `GAP` and #168 cannot be closed as full exit portability.

For SQLite, direct database inspection may be technically possible with standard SQLite tooling, but qualification still requires a documented schema/relationship guide and a clean-machine exercise; availability of a `.sqlite` file alone is not sufficient.

## Package identity and candidate binding

Before execution, fill `exit-portability-reconstruction-evidence.template.json` with:

- exact 40-hex source SHA and candidate/release identity;
- exact backup/reconstruction package hash;
- database engine/version and storage model;
- release artifact references;
- clean-machine environment identity;
- operator identity/attestation reference;
- reference to the corresponding recovery-evidence record, if disaster reconstruction is being qualified in the same campaign;
- canonical-snapshot applicability and the pre-loss canonical evidence identity reference when the candidate contains `document_evidence_snapshots`.

The package consumed on the clean target must have the same SHA-256 as the captured source package. A materially changed candidate, schema, storage layout, canonical-evidence representation, backup format or restore path requires an applicability decision and fresh evidence where affected.

## Clean-machine reconstruction exercise

Use an isolated machine/VM/container that does not already contain the tested ThisTinti data. Record installed prerequisites rather than silently relying on them.

1. Verify package SHA-256 before extraction/restore.
2. Inspect `manifest.json` and verify each archive entry against its recorded size/hash.
3. Record database tooling and exact versions required for restore.
4. Execute the approved restore path from the existing recovery runbook; do not overwrite source/pilot data.
5. Verify database integrity, storage integrity, schema/migration state, tenant/workspace boundaries and representative DOCUMENT → FACT → FINDING → GIUDIZIO/provenance relationships using the existing recovery evidence checks.
6. If canonical evidence snapshots apply, compare restored snapshot row/document/tenant identities and canonical byte hashes against the pre-loss canonical evidence manifest. A filesystem source file being present is not a substitute for this check.
7. Start the exact candidate against the reconstructed state and perform the applicable read-only reviewer smoke path. Where qualified reviewer/export surfaces consume canonical bytes, verify their evidence hash matches the restored canonical snapshot identity.
8. Record every manual intervention, missing prerequisite, undocumented step, warning and failure.

The final reconstruction result may only be `PASS` when the linked recovery record is final/verified for this candidate/environment and the reconstruction-specific checks have evidence references.

## Offline exit inspection exercise

This is intentionally performed without a running ThisTinti service.

1. Copy only the exit package plus documented prerequisite tools to an isolated target.
2. Open the archive and inspect `manifest.json` offline.
3. Enumerate package entries and independently recalculate representative or complete hashes according to the declared test scope.
4. Extract authorised source-document samples and verify their identity against the manifest without starting ThisTinti.
5. Inspect the database snapshot using only the documented third-party/offline method. Record required software and commands.
6. If canonical snapshots apply, demonstrate how an authorised operator locates the relevant snapshot records, correlates them to documents/tenant ownership, and verifies canonical byte hashes without launching ThisTinti. If this cannot be done from documented standard tooling, mark canonical offline inspection as `GAP` rather than inferring PASS from reconstruction success.
7. Attempt to locate and interpret representative DOCUMENT, FACT, FINDING, GIUDIZIO and provenance relationships from the exported material using the documented schema/guide, without querying a live ThisTinti API or UI.
8. Record whether identifiers can be correlated across those records and whether evidence references remain traceable.
9. Record unsupported/opaque fields and any knowledge that exists only inside application code.

`semantic_records` is `PASS` only if a competent authorised operator can reproduce this inspection from the documented package and instructions. Requiring the ThisTinti service itself means this check is not an offline portability PASS.

## Compatibility, rollback and EOL boundary

RELEASE 1.0.x claims must stay narrow and evidence-based:

- record the package `format` exactly (`thistinti-backup-v1` where applicable);
- record the producer release and the consumer/restore release actually tested;
- do not promise forward/backward compatibility beyond tested combinations;
- do not promise downgrade of a migrated database unless a tested rollback procedure exists;
- preserve the original package before migration/restore tests so rollback of the *exercise* does not depend on a destructive conversion;
- document known prerequisites and unsupported paths;
- maintenance/EOL policy remains a governance/release-owner statement and must not be inferred from CI.

A future format or canonical-evidence schema change must either preserve a tested reader/migration path or explicitly declare the compatibility boundary before release.

## Findings and severity

Record portability/reconstruction findings separately from recovery findings when their root cause differs. At minimum classify:

- package cannot be opened or hash inventory fails → release-blocking;
- required source storage silently absent → release-blocking;
- canonical evidence snapshot missing, substituted, cross-tenant, hash-mismatched or not restorable on the qualified path → release-blocking;
- reconstruction loses or substitutes evidence-chain records → release-blocking;
- undocumented mandatory prerequisite or manual database repair → at least serious until assessed;
- canonical or semantic records cannot be inspected offline → `GAP` for exit portability, not a fabricated PASS;
- cosmetic/documentation defects that do not obstruct a competent operator → severity assessed with rationale.

Critical/high/serious release-blocking findings require correction and retest on the affected candidate/package. `ACCEPTED_RISK` alone cannot create a qualification PASS.

## Evidence record and final gate

Start from `docs/qualification/exit-portability-reconstruction-evidence.template.json`.

The record begins `PREPARATION_ONLY_NOT_EXECUTED`. Final review requires evidence references for candidate/package identity, clean-machine environment, linked recovery proof, canonical-snapshot preservation where applicable, offline inspection, tool versions, findings/retests and operator attestation.

The following are explicitly **not** PASS evidence by themselves:

- existence of `backup_system.py`;
- a ZIP that opens;
- a successful CI backup test;
- database rows existing before the exercise;
- this runbook or its template;
- screenshots without package/hash/command context;
- a restore performed on an environment already containing the source state;
- use of the live ThisTinti application to satisfy the offline inspection check.

## Handoff / exit condition

Internal preparation is ready for operational handoff when this contract and template are reviewed/merged and the release owner has chosen the exact candidate, clean target, authorised operator, evidence-retention location and documented prerequisite tools.

#168 itself remains **NOT EXECUTED / NOT PASS** until a real clean-machine reconstruction and a separate offline exit-inspection exercise have been run on the applicable candidate and reviewed. If the current 1.0 package cannot make canonical/semantic records meaningfully inspectable offline, record that as a real gap; do not add a feature in Qualification C merely to improve the result.