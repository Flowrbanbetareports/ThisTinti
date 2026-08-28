# Provenance Contract v0

Status: **internal / experimental**  
Contract: `contracts/provenance/v0.contract.json`  
Scope: Engineering Hardening Sprint 1. This is not a public stable API and does not introduce a database migration by itself.

## Purpose

ThisTinti must be able to reconstruct why a fact, finding, or human conclusion exists without inventing missing history.

The contract is intentionally narrower than a full PROV-O implementation. It defines the minimum provenance invariants required before runtime persistence is redesigned or migrated.

The governing rule is:

> Every new fact has an explicit typed origin. Derived facts identify their inputs and transformation. Findings identify supporting facts and rule version. Human judgments identify the finding, reviewer, reason, and previous state.

A fact does **not** need to originate from a document. Legitimate origins include human assertions, master data, system observations, and deterministic derivations.

## Origin types

`DOCUMENT_EVIDENCE` — information supported by an original or derived document source.

`HUMAN_ASSERTION` — information supplied or confirmed by a person. It must preserve actor, time, and reason.

`MASTER_DATA_IMPORT` — information imported from an authoritative or configured external dataset.

`SYSTEM_OBSERVATION` — information observed by ThisTinti itself, such as a runtime or processing state.

`DETERMINISTIC_DERIVATION` — information calculated from one or more prior facts using an identified transformation.

`LEGACY_ORIGIN_UNKNOWN` — pre-contract information whose exact origin cannot be reconstructed. This is an explicit limitation, not a placeholder to be silently repaired later.

## Source locators

Source location depends on source format:

| Source | Locator |
| --- | --- |
| PDF | page + bounding box |
| image | image index + bounding box |
| text | character range |
| CSV | row + column |
| XLSX | sheet + cell |
| JSON | JSON Pointer |
| XML | XPath |

A locator and source availability are separate concepts.

`source_availability=available` means the source can currently be opened.

A source may later become unavailable because of retention, access policy, external dependency, or deletion. In that case the known locator is not erased merely because the source cannot be opened.

Conversely, `locator_status=missing` means the system never had enough location information. This must not be represented as if the source simply became unavailable later.

## Four provenance-bearing records

### Fact

Minimum identity:

- fact id and type;
- value;
- explicit origin type;
- creation time;
- version.

Origin-specific metadata is then required. Examples:

- document fact → source id, source availability, locator status;
- human assertion → actor, assertion time, reason;
- system observation → engine id/version and observation time;
- deterministic fact → derivation id;
- legacy value → explicit legacy marker.

### Derivation

A deterministic derivation records:

- input fact ids;
- transformation id;
- engine id and version;
- configuration hash;
- creation time.

The same transformation and the same frozen inputs should therefore be explainable and reproducible independently of UI state.

### Finding

A finding records:

- supporting fact ids;
- rule id;
- rule version;
- rule configuration hash;
- creation time.

A finding is not allowed to point only to a free-text explanation when structured supporting facts are available.

### Human judgment

A judgment records:

- finding id;
- reviewer id;
- decision;
- reason;
- previous state;
- creation time.

A later correction creates another judgment/version. It does not rewrite the earlier decision.

## Mapping to the current RC15 model

This contract is designed around the current implementation rather than around an invented replacement architecture.

Current `Document` already stores source filename, storage path, MIME type, file hash, parse status, confidence, references, and metadata. `DocumentLine` stores source-derived line data plus `raw_json`. These are useful evidence carriers, but they are not yet a uniform field-level provenance model.

The parsers already preserve partial provenance in `metadata`, `raw`, confidence, extraction method, and selected numeric provenance. OCR additionally records the local OCR engine, PDF renderer, language, page count, DPI, and evidence class.

Current `DiscrepancyCase` is the closest runtime equivalent to a finding. `EvidenceLink` already links a case to a document/document line and observed/expected values, but it does not yet guarantee a typed fact origin, structured locator, fact identity, or rule version/configuration.

Current `ReviewDecision` already appends review records, while the case status is also updated. Provenance v0 requires future persistence to record the previous state explicitly on each judgment rather than trying to reconstruct it later.

The SHA-256 chained `AuditEvent` stream remains a separate control. Audit-chain integrity answers whether recorded audit events were altered; provenance answers why a semantic fact/finding/judgment exists. Neither replaces the other.

RC15 company-profile and pilot versioning are compatible with the direction of the contract, but the contract does not declare existing historical rows to have provenance fields they do not actually contain.

## Legacy rule

No migration is allowed to manufacture historical provenance.

If an existing RC15 value cannot be tied to a defensible origin, it must remain `LEGACY_ORIGIN_UNKNOWN` until superseded by a new observation, assertion, import, or derivation with complete provenance.

This rule is deliberately conservative: an explicit unknown is preferable to a false chain of evidence.

## Versioning and corrections

Provenance history is append-oriented.

A correction must create a new version and link or mark the previous version as superseded. The previous record remains reconstructable unless normal retention/deletion policy legally requires its removal.

The contract does not claim cryptographic immutability of semantic facts. It requires historical traceability and forbids silent overwrite of provenance-bearing history.

## Privacy, export, and deletion

Document hashes, source locators, and other provenance fields can themselves be sensitive.

Private source hashes do not need to appear in public reports. A public pilot report may identify dataset/run/version without publishing document fingerprints.

Exports must include the provenance the recipient is authorized to receive. Deletion and retention must remove or preserve source material according to policy while retaining only the provenance metadata that is legally and operationally allowed.

A deleted source must not be represented as if it never had a locator. A locator that was never captured must not be represented as a retention deletion.

## Completion criteria for v0

Provenance v0 is considered implemented only when all of the following are true for **new** records created after its runtime introduction:

1. every fact has an explicit typed origin;
2. every deterministic derivation identifies inputs, transformation, engine version, and configuration;
3. every finding identifies supporting facts and rule version/configuration;
4. every human judgment identifies finding, reviewer, reason, and previous state;
5. corrections append a new version instead of overwriting history;
6. source locators open the source when available or explicitly explain why it is unavailable;
7. no new fact, derivation, finding, or judgment is orphaned from required provenance links;
8. export/deletion behavior respects provenance and confidentiality requirements;
9. legacy incomplete provenance remains explicitly marked and is never invented retroactively;
10. source-unavailable and locator-missing states remain distinct.

## Explicit non-goals

This v0 does **not**:

- implement full W3C PROV-O;
- introduce a graph database;
- create a public stable API;
- add a new Procurement feature;
- backfill invented provenance into RC15 history;
- add a cloud OCR fallback;
- require a database migration in this specification commit.

The next implementation step, after this contract is qualified, is to design the smallest additive persistence model that can enforce these invariants without changing RC15 business semantics.
