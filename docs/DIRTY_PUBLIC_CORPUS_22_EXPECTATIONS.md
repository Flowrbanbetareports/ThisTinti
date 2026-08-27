# Dirty Public Corpus 22 — expectation policy

Expectations are source-based, not fitted to current parser output.

## `parse`

Use `parse` only when the source has an unambiguous business-document identity that we can assert independently.

For the two Pen-Link public quotes the upstream records identify the quote numbers, USD denomination and commercial rows. ThisTinti receives only the document-type hint (`proposal`); quote number, currency and lines must come from the raw PDF.

For valid external XML invoices/credit notes, the minimum expectation is successful structural parsing with the correct document family, at least the declared minimum number of business lines, and currency where known.

## `characterize`

Use `characterize` for real public packets containing multiple logical documents or otherwise ambiguous boundaries. A characterization case is successful only in the narrow robustness sense that the source downloads and the parser returns either a normal parsed result or a structured `ParseError`; an unhandled exception always fails the workflow.

`characterize` is not a correctness PASS. Its output exists to tell us where document segmentation, OCR or a more specific parser is needed before stronger ground truth can be written.

## Standards-negative material

The current UBL parser parses document structure. It is not a complete Peppol/EN16931 Schematron conformance validator. Therefore an upstream standards-negative invoice may structurally parse. The manifest records that limitation explicitly rather than expecting a `ParseError` for a capability the product does not claim.

## Freeze rule

Discovery mode reports every `parse` assertion mismatch but does not fail solely because of those mismatches. It does fail on missing sources or unhandled exceptions.

Before `frozen: true`:

1. each assertion must be checked against the upstream source;
2. genuine in-scope parser weaknesses must be fixed or explicitly narrowed as product scope;
3. characterization-only cases must stay labelled as such unless independent ground truth exists.

After freeze, every `parse` assertion mismatch is a CI failure. Characterization cases continue to gate only on reproducibility and crash-free handling unless separately promoted to stronger source assertions.
