# Qualified Windows signing handoff

Status: **PREPARATION ONLY — NOT SIGNED — NOT VERIFIED**

Scope: preparation for issue #20 and the bounded release claim `ThisTinti 1.0 Qualified — Procurement v1 — profile P1 — protocol E1`.

This document does not prove publisher identity, certificate ownership, Authenticode validity, timestamp validity, clean-host verification, or final release readiness. Those require the real certificate/key service and the final frozen artifacts.

## 1. Ownership decision before implementation

Record, outside source control where confidential:

- legal publisher name that Windows must display;
- certificate owner and authorised maintainers;
- certificate/provider type and expiry;
- whether signing uses a hardware-backed/cloud signing service or another non-exportable key arrangement;
- trusted RFC 3161 timestamp service selected for production;
- renewal owner and lead time;
- revocation/emergency rotation contacts.

Private keys, certificate passwords, provider credentials and signing tokens must never be committed, printed in Actions logs, embedded in artifacts, or exposed to pull-request jobs.

## 2. Pipeline trust boundary

Production signing must be reachable only from an explicitly trusted release path. At minimum:

1. resolve a full candidate SHA and prove it belongs to the intended protected `main` history;
2. require the exact qualification checks for that SHA before signing;
3. obtain the Windows artifacts produced for that exact SHA;
4. verify source/artifact provenance and pre-signing checksums before invoking the signer;
5. sign only the allowlisted executable artifacts;
6. timestamp every Authenticode signature;
7. verify signatures after signing and before publication;
8. compute and publish SHA-256 for the signed bytes, not the unsigned inputs;
9. preserve a machine-readable signing evidence record tied to candidate SHA, artifact hashes, certificate identity and verification result;
10. fail closed: unsigned, partially signed, wrongly published, expired-without-valid-timestamp, wrong-certificate, wrong-SHA or unverifiable artifacts cannot enter the official Qualified release.

A pull request from an untrusted context must not be able to obtain signing credentials merely by modifying workflow YAML or scripts.

## 3. Artifact allowlist

The final release job must explicitly enumerate what is signed. Expected minimum for the current Windows distribution:

- `ThisTinti-Setup-<version>-x64.exe`;
- application executable(s) contained in the installed payload;
- uninstaller where the packaging technology supports signing it before final installer assembly.

Portable/source ZIP files are not Authenticode-signed as ZIP containers; retain their SHA-256 and existing provenance/attestation evidence. If the portable ZIP contains executable files, record whether those inner executables are signed before archive creation.

Do not use wildcard discovery as the sole authority for what receives the production signature.

## 4. Required signing evidence record

For each final artifact preserve at least:

- bounded release name and version;
- exact source commit SHA and source tree;
- exact Windows build run/artifact identity;
- artifact path/name;
- SHA-256 of the final signed artifact;
- certificate subject / intended publisher;
- certificate thumbprint or stable provider certificate identifier;
- certificate validity interval;
- digest algorithm;
- timestamp presence, timestamp authority and timestamp verification result;
- Authenticode verification result;
- clean-Windows-host verification date/environment;
- verifier/operator identity where human execution is required;
- links/IDs for retained evidence.

Do not store private key material or secret values in this record.

## 5. Final-candidate verification procedure

Execute only after the final Qualified candidate/artifacts are frozen.

### Automated checks

- prove candidate SHA and Windows build identity are exact-current;
- verify all expected signed files exist and no unexpected executable is silently substituted;
- run Windows signature verification against each required executable;
- require the expected publisher/certificate identity rather than merely accepting "some valid signature";
- require a valid trusted timestamp;
- reject missing, invalid, untrusted or mismatched signatures;
- recompute SHA-256 after signing and bind it to publication evidence.

### Clean Windows observation

On a clean supported Windows system record evidence that:

- installer properties/signature UI shows the intended verified publisher;
- installer starts without being represented as an unknown publisher due to missing Authenticode identity;
- installed application executable verifies with the intended publisher;
- uninstaller verifies where applicable;
- signature validation succeeds with normal network/trust-chain conditions;
- timestamp information is visible/valid and supports verification after certificate expiry according to the selected signing model.

This observation must use the exact final published bytes or bytes proven identical by SHA-256.

## 6. Publication fail-closed requirements

The current Public Preview publication path explicitly states that the installer is unsigned. That statement must not simply be deleted when #20 is implemented. Replace it only when the publication job has mechanically verified the production signature on the exact artifacts being released.

For the Qualified release, publication must stop when any required signed artifact:

- is absent;
- differs from the expected candidate/build;
- has no Authenticode signature;
- has an invalid/untrusted signature;
- is signed by an unexpected certificate/publisher;
- lacks the required timestamp or fails timestamp verification;
- changes after signature/checksum verification.

Release notes must explain both publisher-signature verification and SHA-256 verification. GitHub attestations/checksums remain complementary evidence and do not substitute for the Windows publisher identity required by #20.

## 7. Renewal, revocation and emergency rotation

Before Qualified publication, document operational ownership for:

- renewal before expiry;
- provider/account recovery;
- revocation when key/service compromise is suspected;
- emergency certificate rotation;
- updating the expected certificate identity in the trusted release configuration;
- preserving verification of already timestamped releases;
- preventing old/revoked credentials from signing new official artifacts.

A certificate rotation is a release-pipeline security change and requires explicit review; it must not silently broaden which signer identities are accepted.

## 8. Handoff checklist

The implementation owner may begin when these external inputs exist:

- [ ] intended legal publisher name confirmed;
- [ ] code-signing certificate/provider selected and procured;
- [ ] certificate ownership/renewal responsibility assigned;
- [ ] secure signing mechanism available without exporting secrets to repository/PR jobs;
- [ ] RFC 3161 timestamp endpoint/service selected;
- [ ] final workflow trust boundary approved.

The final #20 gate may close only after:

- [ ] signing is integrated into the trusted release pipeline;
- [ ] all required executable artifacts are signed and timestamped;
- [ ] unsigned/mismatched artifacts are mechanically blocked from official publication;
- [ ] final signed-byte SHA-256 values are published;
- [ ] clean Windows verification is performed on the exact final artifacts;
- [ ] renewal/revocation/emergency rotation procedure is recorded;
- [ ] evidence is tied to the final/frozen Qualified candidate.

Until every final item is evidenced, status remains **PREPARATION ONLY / NOT SIGNED / NOT VERIFIED**.
