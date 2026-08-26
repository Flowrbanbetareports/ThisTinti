# Dirty Public Corpus 22

## Goal

This suite is intentionally different from `Public Evidence Benchmark 30`.

The first benchmark normalizes public facts into controlled inputs and measures anomaly detection against hidden ground truth. This corpus instead downloads **raw external files** and gives them directly to the current ThisTinti parser. The goal is to expose parser and ingestion weaknesses that controlled fixtures can hide.

It is not a real company pilot and it must never be described as one.

## Corpus composition

The discovery version contains 22 files:

- 2 genuine City of Portland purchase-order PDFs published for supplier/procurement guidance;
- 2 other genuine Portland public PDFs that are not transaction documents and should be rejected safely when no document type is supplied;
- 13 pinned OpenPeppol XML invoice examples, including current ViDA pilot files and Peppol BIS Billing examples;
- 3 pinned EN16931 edge examples;
- 2 pinned negative/invalid EN16931 examples that should be rejected with a structured `ParseError`, never crash the parser.

The Portland purchase orders are important because they are not formatted for ThisTinti. They use a real public-sector SAP-style layout, multi-page tables, English labels, thousands separators and line structures that differ substantially from the app's own fixtures.

## Discovery first, gate second

Version `0.1-discovery` deliberately has `frozen: false`.

During discovery the workflow:

1. downloads every source without transforming it;
2. records final URL, response metadata, size and SHA-256;
3. runs the raw file through `app.parsers.parse_file`;
4. records structured parse output or structured `ParseError`;
5. evaluates manually declared expectations;
6. fails immediately on download failures or unhandled parser exceptions;
7. does **not** fail merely because a declared parser expectation is missed while the corpus is still being characterized.

This is not a way to hide failures. The report prints every mismatch. It exists so external-source hashes and genuine parser limitations can be observed before the corpus is frozen.

After discovery:

- the four mutable Portland URLs receive their observed SHA-256 values in the manifest;
- expectations are reviewed against source truth, not weakened to match the software;
- `frozen` becomes `true`;
- from that point every expectation mismatch fails CI.

## What counts as useful failure

Examples of useful failures include:

- a Portland purchase order is readable but the number is not recognized;
- line tables are not extracted;
- the currency defaults incorrectly;
- a valid Peppol/EN16931 invoice is rejected;
- a credit note is classified as an invoice;
- an intentionally invalid example is accepted without warning;
- a malformed external document causes an unhandled exception instead of a structured `ParseError`.

Those failures are the point of this suite. They should become parser improvements and permanent regressions, not be removed by weakening the benchmark.

## Governance boundary

A future PASS means only that the frozen assertions for these 22 raw public/external documents are satisfied. It does **not** mean:

- 100% real-world accuracy;
- OCR robustness on arbitrary scans;
- a completed authorized company pilot;
- legal/accounting validation;
- production readiness by itself.

The controlled company pilot remains a separate gate.
