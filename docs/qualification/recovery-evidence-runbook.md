# P1/E1 recovery evidence handoff — preparation only

Status: **PREPARATION ONLY / NOT EXECUTED / NOT PASS**

Refs: #136, #21. This runbook prepares the real backup/recovery exercise required for the bounded `ThisTinti 1.0 Qualified — Procurement v1 — profile P1 — protocol E1` release. It does not prove that a backup has been restored, that an intended release environment exists, or that RPO/RTO targets have been met.

## Existing backup boundary

The repository already contains `scripts/backup_system.py`. It creates a `thistinti-backup-v1` ZIP containing a database snapshot, optional application storage, an internal manifest with per-entry SHA-256 values, and an outer bundle SHA-256. PostgreSQL snapshots use `pg_dump --format=custom --no-owner --no-privileges`; SQLite snapshots use the SQLite backup API and integrity check.

That is backup tooling, not recovery evidence. Qualification additionally requires a real restore on an isolated target representative of the intended release environment, verification of the restored evidence chain and preserved logs/attestations.

Do not treat a successful backup command, a ZIP that can be opened, CI, or this runbook as a recovery PASS.

## Candidate and environment binding

Before the exercise, record in `recovery-evidence.template.json`:

- exact source SHA and candidate/release identifier;
- applicable release artifact references;
- intended deployment model and environment identifier;
- database engine and exact version observed on the exercise environment;
- storage model actually used by the release;
- an isolated restore target that cannot overwrite production/pilot source data;
- RPO and RTO targets explicitly chosen by the release owner before observing the result.

Do not invent generic RPO/RTO thresholds after the exercise. If the release owner has not defined them, the final evidence is incomplete.

## Backup capture

1. Establish the candidate/environment binding before taking the backup.
2. Capture UTC start/end timestamps and the exact command/procedure reference.
3. For the final qualification exercise, include application storage unless the release architecture has formally established that no release-relevant storage exists outside the database. The current validator therefore fails closed when `storage_included` is not explicitly `true`.
4. Preserve the emitted backup manifest and the outer bundle SHA-256 from `scripts/backup_system.py`.
5. Store logs and evidence outside the backup bundle as well, so evidence of the exercise is not available only from the object being tested.
6. Do not place credentials, database URLs containing secrets, private keys, or access tokens in the evidence package.

A database-only convenience backup may still be useful operationally, but it is not sufficient by default for the final P1/E1 recovery gate because source-document storage is part of the evidence system.

## Restore execution

The repository does not currently claim that `backup_system.py` is a restore command. Use the real restore procedure appropriate to the intended release environment and record its exact command/procedure/log references.

The restore target must be isolated and disposable or otherwise explicitly safe for recovery testing. Never test qualification recovery by overwriting the live pilot/release data set.

For PostgreSQL custom-format dumps, the operator must use the environment's approved `pg_restore` procedure and record tool/server versions and command logs. For SQLite, restore must likewise use an approved isolated procedure. The concrete deployment owner is responsible for choosing the production-compatible command and credentials handling; this preparation intentionally does not fabricate them.

Record the SHA-256 of the bundle actually consumed by the restore. It must equal the SHA-256 recorded at backup time.

## Required verification after restore

A final evidence package must independently record `PASS` plus evidence references for all of these checks:

- `bundle_integrity`: backup bundle/hash/manifest identity is intact and the restored bundle is exactly the recorded bundle;
- `database_integrity`: the restored database is structurally readable and passes the database-engine-appropriate integrity checks;
- `schema_migration_state`: schema/migration state is the expected state for the candidate;
- `storage_integrity`: release-relevant stored source documents/files are present and correspond to the recorded backup manifest;
- `tenant_workspace_isolation`: restored tenant/workspace boundaries remain intact on the restored environment;
- `document_fact_finding_judgment_integrity`: representative persisted DOCUMENT, FACT, FINDING and GIUDIZIO/provenance relationships survive restoration without silent substitution or loss;
- `application_smoke`: the candidate can start against the restored state and the applicable reviewer path can read evidence without modifying the qualification record merely to make the smoke test pass.

The verification step should prefer factual counts, identifiers, hashes and invariant checks over screenshots alone. Sensitive customer/pilot contents should not be copied into a public evidence package; use pseudonymous identifiers and protected evidence references where needed.

## Recovery objectives

Measure rather than infer:

- `recovery_point_age_seconds`: age of the restored recovery point according to the release owner's defined measurement rule;
- `recovery_time_seconds`: elapsed recovery duration according to the release owner's defined measurement rule.

The validator requires the measured values to be within the predeclared RPO/RTO targets before a final structure can validate. This is a structural guard only; it does not independently verify clocks, logs or operator truthfulness.

## Findings, remediation and retest

Record each recovery finding with an ID, severity, state, description and evidence references. Use the same release discipline as #136:

- blocker/critical/high/serious findings cannot be cleared by `ACCEPTED_RISK` alone in the final recovery evidence;
- a release-blocking recovery finding must reach `RETESTED_PASS` on the applicable corrected candidate/environment;
- `OPEN` and `FIXED_PENDING_RETEST` remain non-final;
- a code/configuration change is not itself restore evidence;
- if a material fix changes the candidate or deployment/recovery path, bind the retest to that changed identity rather than carrying an old PASS forward.

## Evidence package

Start from:

`docs/qualification/recovery-evidence.template.json`

Validate preparation shape:

```text
python scripts/validate_recovery_evidence.py path/to/recovery-evidence.json
```

Only after the real exercise and evidence collection, run the stricter structural gate:

```text
python scripts/validate_recovery_evidence.py --final path/to/recovery-evidence.json
```

`--final` requires, among other things:

- `RECOVERY_VERIFIED` status rather than `PREPARATION_ONLY`;
- exact 40-hex source SHA;
- named candidate/artifacts/environment;
- isolated restore target;
- release-owner-defined positive RPO/RTO targets and measured non-negative results within those targets;
- full-storage backup;
- matching 64-hex backup/restore bundle hashes;
- all seven verification families at `PASS` with evidence references;
- no unresolved finding and `RETESTED_PASS` for release-blocking findings;
- real operator attestation/evidence references rather than placeholders.

Passing this validator means the evidence record is structurally complete enough for review. It does **not** cryptographically prove every referenced artifact, execute a restore, authenticate an operator or turn internal preparation into external/human evidence.

## Handoff checklist

Before scheduling the real exercise, confirm the release/deployment owner has supplied the environment identity, approved restore procedure, safe isolated target, backup/storage locations, RPO/RTO targets and evidence-retention location. Confirm credentials can be used without being copied into logs or the repository.

After the exercise, retain the backup manifest/hash, restore logs, verification outputs, timestamps, operator attestation, findings and retest evidence. Link the resulting record from the final qualification evidence index for #136.

## Exit condition

This preparation is ready for operational handoff once merged. The recovery lane itself remains **NOT EXECUTED / NOT PASS** until the intended release environment has undergone a real backup-and-restore exercise and the resulting evidence has been reviewed against #136. Any final-candidate change that materially affects database schema, storage, deployment, backup or restore semantics requires an applicability decision and, where affected, fresh recovery evidence.
