# Windows signing qualification — RELEASE 1.0.0

Status: **PREPARATION ONLY / NOT A QUALIFICATION PASS**.

This packet supports #20 and Stream C of #136. It prepares the evidence contract for official Windows Authenticode signing without claiming that a certificate exists, that a publisher has been verified, or that final artifacts have been signed.

## Candidate identity

Final evidence must identify exactly one official candidate:

- product version: `1.0.0`;
- release tag: `v1.0.0`;
- full 40-hex source SHA;
- immutable SHA-256 for every final artifact being evaluated.

Legacy `v3.4.0-alpha.*`/RC artifacts are historical prereleases and must not be relabelled as 1.0 evidence.

## Required signed surfaces

For each applicable Windows release artifact record whether signing is required and, when required, prove it separately:

1. application executable;
2. installer;
3. uninstaller when separately signable/persisted;
4. any other executable helper shipped as part of the official package.

A valid installer signature does not prove that embedded executables are signed. A checksum does not prove publisher identity.

## Evidence required for a final record

For every required signed artifact capture:

- artifact filename and SHA-256;
- Authenticode status from a clean Windows host;
- certificate subject/publisher displayed to Windows;
- certificate thumbprint and serial number;
- certificate validity interval;
- timestamp presence and timestamp authority;
- timestamp verification result;
- verification command/tool and version;
- UTC verification time;
- evidence reference (log/screenshot/report) tied to the exact artifact.

Verification must include both PowerShell `Get-AuthenticodeSignature` and Windows SDK `signtool verify /pa /all /v`, or a documented equivalent accepted before execution.

## Key and pipeline controls

The evidence package must separately record that:

- the private signing key is not committed to the repository;
- untrusted pull requests/forks cannot receive signing credentials;
- the signing environment is protected and access-controlled;
- logs do not print private-key material or certificate passwords;
- checksums are computed **after** signing and are the checksums published with the release;
- official publication fails closed when a required signature is absent, invalid, untrusted or untimestamped.

Do not put secret values in the manifest. Only record control/evidence references.

## Clean-machine verification

The final candidate must be checked on a clean supported Windows environment. Record OS edition/build and whether the machine had any project-local development certificates or trust-store modifications. A machine with a manually trusted test certificate cannot establish public publisher trust.

The clean-machine test must cover install, first launch and uninstallation where applicable and confirm the intended publisher presentation.

## Renewal, revocation and emergency rotation

Before release, document:

- certificate owner and renewal responsibility;
- renewal lead time;
- revocation procedure;
- emergency key compromise/rotation procedure;
- how previously timestamped releases are treated;
- how a revoked/compromised certificate is communicated to operators.

These are operational controls, not proof that an incident has occurred.

## Fail-closed interpretation

The validator in `scripts/validate_windows_signing_manifest.py` checks only evidence-package structure and obvious contradictions. Its strongest success result is:

`VALID_STRUCTURE_NOT_QUALIFICATION_PASS`

It cannot authenticate a certificate, run Windows verification, establish certificate ownership, prove trust-chain validity, or substitute for clean-machine observation.

#20 remains open until the real final artifacts satisfy its acceptance criteria.