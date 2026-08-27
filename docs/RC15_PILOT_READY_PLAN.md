# RC15 Pilot-Ready

## Release objective

RC15 turns the existing document-analysis, review and validation infrastructure into a complete supervised business-practice workflow for a non-technical operator.

The release acceptance target is that an operator can, without terminal access:

1. create or select a company profile;
2. create a supervised pilot;
3. import a practice;
4. understand every acquired, review-required, rejected or blocked document;
5. inspect the reconstructed document chain and source evidence;
6. correct and reprocess a document;
7. take a finding through review, confirmation/dismissal, resolution and reopening;
8. distinguish technical severity, evidence confidence, potential economic exposure and confirmed loss;
9. export, archive or deliberately delete a practice;
10. produce a reproducible pilot report tied to frozen ground truth, configuration and application version.

## In scope

### A. Intake and document quarantine

- Explicit intake classifications for parsed, review-required, not-acquired, blocked and out-of-scope documents.
- Structured failure phase/category/reason retained with the document.
- Failed documents remain visible in operational results.
- Safe retry/reprocess path; no silent fallback or fabricated extraction.

### B. Finding lifecycle and economic semantics

- Auditable state transitions including reopen.
- Mandatory rationale for consequential human decisions.
- Previous decisions remain immutable history after reanalysis.
- Separate technical severity, confidence, potential exposure and confirmed loss.
- Unknown economic impact is represented as unknown, never coerced to zero.

### C. Integrated pilot mode

- Pilot workspace created and managed in the application.
- Two independent reviewer references and authorization metadata.
- Ground truth can be frozen; later corrections require a new version.
- Dataset/config/application version and hashes recorded.
- Manual/assisted timing, TP/FP/FN, critical misses, reviewer disagreements and user score supported.
- Redacted JSON/Markdown final report generated from the exact frozen run.

### D. Company profile v1 and practice lifecycle

- User-editable supplier/item aliases, unit mappings and core tolerances.
- Configuration versioning: analyses record the profile version used.
- Practice archive, export and explicit delete operations.
- Export excludes source documents by default and includes a verification manifest.
- Deletion retains only a non-sensitive tombstone/audit record.
- Retention expiry is advisory in RC15; automatic destructive deletion is out of scope.

### E. Structured commercial text differences

- Surface deterministic differences in embedded numbers, units, model/SKU and configured significant attributes.
- No free-form cloud LLM decision engine in RC15.

## Explicitly out of scope

- chatbot;
- SaaS conversion;
- mobile app;
- large connector catalogue;
- autonomous emails, payments, accounting entries or supplier disputes;
- automatic business decisions;
- broad visual redesign;
- new document formats without pilot evidence.

## Release gates

RC15 must preserve every existing CI, benchmark, security, enterprise and Windows lifecycle gate. A dedicated end-to-end acceptance path must also cover intake failure visibility, correction/reprocessing, finding lifecycle, pilot report generation, export/archive/delete and application restart persistence.
