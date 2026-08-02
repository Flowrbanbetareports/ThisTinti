# RC8 external validation gates

This document separates the completed Public Preview evidence from validation that cannot be truthfully produced by repository automation alone.

## Completed for the RC8 Public Preview

- exact source commit and Git tree bound to the release;
- CI, dependency, PostgreSQL, self-hosted and Windows gates;
- installed `ThisTinti.exe` diagnostics, numeric-integrity rejection, keyboard path, reflow and restart persistence;
- immutable release assets, checksums, provenance and GitHub attestations;
- local-first operation with no external telemetry in the diagnostic workflow.

## Open before stronger production or validated-beta claims

### Code signing

**Status: OPEN.** The Windows installer is not Authenticode-signed. Completion requires a certificate controlled by the publisher and a protected signing process. Automation must not mark this complete without a verifiable signature chain and timestamp.

### Independent security assessment

**Status: OPEN.** Internal tests and dependency checks do not replace an independent penetration test or security review. Completion requires a named independent assessor, scope, date, findings and remediation evidence.

### Authorized real-document pilot

**Status: OPEN.** Synthetic and repository test data do not establish performance on a real operational corpus. Completion requires an authorized, anonymized dataset with at least 30 representative scenarios, documented provenance, reviewer separation and recorded metrics.

### Human accessibility assessment

**Status: OPEN.** Browser automation verifies focus paths and reflow but does not replace a human assistive-technology assessment. Completion requires a documented review with NVDA or an equivalent supported screen reader and remediation of blocking findings.

### Legal and privacy review

**Status: OPEN.** Repository checks verify consistency of the distributed notices; they are not professional legal advice or a DPIA. Completion requires review by qualified parties against the intended deployment, data categories and jurisdiction.

## Claim boundary

RC8 may be described as a verified **Public Preview alpha/RC**. It must not be described as production-certified, independently pentested, legally approved, accessibility-certified or validated on real customer data until the relevant gate above is closed with evidence.
