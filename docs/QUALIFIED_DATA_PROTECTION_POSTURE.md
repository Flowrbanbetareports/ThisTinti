# RELEASE 1.0.0 data-protection posture — qualification draft

Status: **PREPARATION ONLY / NOT INDEPENDENTLY REVIEWED / NOT A QUALIFICATION PASS**

Scope: bounded `ThisTinti 1.0 Qualified — Procurement v1 — profile P1 — protocol E1` candidate, issue #167 under master #136.

This document makes the intended Local Edition and Self-Hosted Reference Edition protection boundary explicit before the final candidate is frozen. It must be reconciled with the exact release SHA/artifacts and independently reviewed under #134/#135 before any final claim is made.

## 1. Claim discipline

For RELEASE 1.0.0, integrity and confidentiality are separate properties.

- SHA-256 document/content hashes, provenance checks and evidence-chain validation are **integrity controls**. They do not encrypt content and do not by themselves protect confidentiality from a user, administrator or attacker who can read the underlying storage.
- No statement such as “encrypted at rest”, “secure at rest” or “zero data leaves the device” may be made unless the exact candidate and deployment satisfy the verification rows below.
- Deployment prerequisites are not product guarantees. If the Qualified posture depends on BitLocker, filesystem permissions, database TLS/storage encryption, backup encryption or operator key management, the release material must state that dependency explicitly.

## 2. Local Edition — current documented boundary

The existing data-lifecycle contract states that the standard Windows installation uses:

- program: `%LOCALAPPDATA%\\Programs\\ThisTinti`;
- local data: `%LOCALAPPDATA%\\ThisTinti`;
- local data may include database, original documents, quarantine, operational logs and backups;
- uninstall removes the program but deliberately preserves `%LOCALAPPDATA%\\ThisTinti`;
- complete deletion therefore requires a separate explicit deletion procedure, including backup/export copies.

The same contract states that the official Local Edition does not require a central account and does not send those stored contents to the author. That statement is a release claim to be re-verified on the exact RELEASE 1.0.0 candidate rather than inherited automatically from an older build.

### RELEASE 1.0.0 at-rest decision

Default qualification position unless a separately reviewed application-level encryption design is deliberately introduced before freeze:

**Option B — no application-level encryption-at-rest claim.**

Accordingly:

1. ThisTinti must not imply that application data are encrypted merely because hashes are present.
2. Qualified deployment guidance should require or strongly recommend appropriate host full-disk/device encryption for company data, for example BitLocker on supported Windows configurations, together with protected Windows accounts and controlled backup storage.
3. The release must not claim that BitLocker is enabled or correctly configured by ThisTinti unless the product actually checks and enforces it on the exact candidate.
4. Local administrators and anyone able to read the user's data directory remain inside the host-trust boundary unless a future, tested encryption/key-management control changes that boundary.
5. Copies placed in exports, backup archives, temp locations, quarantine or user-controlled sync folders must be evaluated separately; host disk encryption on one device does not protect an unencrypted copy moved elsewhere.

Introducing application-level encryption later is a material change: it requires explicit key generation/storage, backup/recovery, rotation, loss, corruption and incident behavior to be designed and tested. Home-grown cryptography is not an acceptable shortcut to close #167.

## 3. Self-Hosted Reference Edition — operator responsibility boundary

The existing lifecycle documentation states that database, storage, quarantine, backups and logs reside in operator-selected infrastructure. RELEASE 1.0.0 must therefore distinguish application behavior from deployment controls.

The final Self-Hosted posture must record, for the exact supported reference deployment:

- database technology/version and where persistent database files live;
- original-document/object-storage location;
- quarantine/temp/log locations;
- backup destination(s), including off-site copies;
- encryption-at-rest mechanism for each persistent store, if any;
- key owner, rotation/recovery model and whether keys are separated from encrypted data;
- transport/TLS termination boundary;
- service/database roles and minimum privileges;
- operator responsibilities for host hardening, filesystem permissions, secrets, retention, deletion and disaster recovery.

Until these rows are completed and reviewed, Self-Hosted encryption/storage protection is **DEPLOYMENT-DEPENDENT / NOT QUALIFIED AS A UNIVERSAL GUARANTEE**.

## 4. Threat-model boundary

The final candidate review must distinguish at least the following actors/failures.

| Threat / actor | Local Edition expected boundary | Self-Hosted expected boundary | Qualification status |
| --- | --- | --- | --- |
| ordinary unauthorised local user | OS account/filesystem controls are expected to restrict access | operator IAM/host controls | VERIFY ON FINAL CANDIDATE |
| local administrator / root | not assumed confidential without separately tested encryption/key separation | not assumed confidential unless deployment provides tested key separation | EXPLICIT LIMITATION |
| stolen powered-off disk/device | depends on host full-disk/device encryption | depends on infrastructure encryption/key controls | DEPLOYMENT PREREQUISITE |
| copied backup/export | protection follows the copy, not the source installation | protection follows backup/export destination and keys | VERIFY PROCEDURE |
| malicious/corrupt stored bytes | provenance/integrity controls may detect supported mutations; confidentiality unaffected | same distinction | TECHNICAL EVIDENCE SEPARATE |
| log/temp/quarantine leakage | must be inventoried and checked | must be inventoried and checked | OPEN VERIFICATION |
| outbound network transmission | must match the explicit outbound inventory below | must match deployment/integration inventory | OPEN VERIFICATION |

## 5. Outbound-data inventory and local-first verification

No release claim should rely only on documentation. Before final freeze, execute a reproducible outbound-network observation on the exact official Local Edition build.

### Inventory categories

For every reachable destination or attempted connection, record:

- destination hostname/IP and owner/purpose;
- triggering action (startup, normal analysis, update check, diagnostics, optional integration, crash path, etc.);
- protocol/port;
- whether enabled by default;
- data classes transmitted;
- whether document bytes, extracted text, findings, evidence/provenance, identifiers or operational metadata are present;
- consent/configuration mechanism where applicable;
- retention/subprocessor implications where known;
- decision: REQUIRED / OPTIONAL / REMOVE / BLOCK RELEASE.

### Fail-closed release rule

For the official Local Edition RELEASE 1.0.0:

- silent transmission of company documents, extracted document contents, findings/evidence or operational evidence to the author or third-party analytics is release-blocking;
- any update check, diagnostics or optional network feature must be explicitly inventoried and accurately described;
- absence of an observed connection in a short smoke run is not proof of universal absence: exercise startup, representative ingestion/analysis, diagnostics, update behavior if present, restart and failure/crash-relevant paths that can be tested safely;
- evidence should capture candidate SHA/artifact hash, Windows version, observation tool/configuration, test steps, timestamps and resulting destinations/flows.

## 6. Storage-surface verification matrix

Complete this matrix against the exact final candidate. `UNKNOWN` is intentional until observed.

| Surface | Expected location / owner | Contains potentially sensitive content? | App-level encryption claim | Required final evidence |
| --- | --- | --- | --- | --- |
| originals | Local data directory / operator storage | YES | NONE by default | path + permissions + at-rest posture + deletion behavior |
| database | Local data directory / operator DB | YES | NONE by default | engine/path + permissions + at-rest posture + backup behavior |
| quarantine | local/operator-controlled | POSSIBLY YES | NONE by default | path + retention + permissions + purge behavior |
| operational logs | local/operator-controlled | MAYBE | NONE by default | sample/redaction review + path + retention |
| temp/work files | implementation-dependent | MAYBE | NONE by default | runtime observation + cleanup/failure-path check |
| exports | user-selected | YES | NO UNIVERSAL CLAIM | format + warning + destination responsibility |
| backups | user/operator-selected | YES | NO UNIVERSAL CLAIM | backup format + storage guidance + restore test |
| crash/diagnostic material | implementation-dependent | MAYBE | NO CLAIM | exact data inventory and outbound behavior |

## 7. Manual final-candidate checklist

Record every item with exact SHA/artifact and evidence reference.

- [ ] Confirm actual Local Edition storage paths against documentation.
- [ ] Confirm originals/database/quarantine/log/backup/temp/export surfaces and identify any undocumented location.
- [ ] Confirm no UI/docs/release notes confuse SHA-256 integrity with encryption/confidentiality.
- [ ] Confirm the chosen at-rest decision is still Option B, or replace this section only with a separately reviewed/tested encryption design.
- [ ] Document supported-host encryption/account/backup prerequisites without claiming they are automatically enabled.
- [ ] Inspect representative logs/temp/quarantine/exports for unnecessary sensitive content.
- [ ] Execute outbound-network observation on the exact official Local build across the defined paths.
- [ ] Reconcile every observed network destination with the inventory; unexplained destination = BLOCKED pending resolution.
- [ ] Verify uninstall versus data-retention behavior and complete-deletion instructions.
- [ ] Verify backup copies are covered by the stated confidentiality/retention boundary.
- [ ] Complete the Self-Hosted responsibility/deployment table for the actual reference environment.
- [ ] Hand exact document/version and evidence packet to independent security #134 and privacy/legal/claims #135 reviewers.
- [ ] Record reviewer findings, remediation and retest/reference to corrected candidate where material.

## 8. What this preparation does not prove

This document does **not** prove that BitLocker is enabled, that Self-Hosted infrastructure is encrypted, that no network traffic exists, that logs contain no sensitive material, that backups are encrypted, or that an independent privacy/security review has passed. Those are final-candidate or external evidence obligations.

It also does not change parser, provenance, P1 rules, runtime behavior, qualification thresholds or E1 dataset handling.

## 9. Freeze record

Populate only when the applicable candidate exists.

- source SHA: `UNSET`
- release tag: `v1.0.0` (target; not evidence of publication)
- Windows artifact + SHA-256: `UNSET`
- Self-Hosted artifact/image + digest: `UNSET`
- data-protection posture version: `1.0-draft`
- outbound observation evidence: `UNSET`
- independent security review reference: `UNSET`
- independent privacy/legal/claims review reference: `UNSET`
- residual-risk decision: `UNSET`

Any material change to storage protection, telemetry/outbound behavior, backup semantics or deployment assumptions after this record is frozen requires evidence appropriate to the changed claim before qualification can inherit the result.
