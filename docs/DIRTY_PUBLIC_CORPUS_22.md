# Dirty Public Corpus 22

## Goal

This suite is intentionally different from `Public Evidence Benchmark 30`.

The first benchmark normalizes public facts into controlled inputs and measures anomaly detection against hidden ground truth. This corpus instead downloads **raw external files** and gives them directly to the current ThisTinti parser. The goal is to expose parser and ingestion weaknesses that controlled fixtures can hide.

It is not a real company pilot and it must never be described as one.

## Corpus composition

Discovery version `0.2` contains exactly 22 files:

- **15 raw public financial/procurement PDFs** from the Lucy Parsons Labs `1505-documents` repository. Its README describes the collection as mostly FOIA records received from Chicago-area law-enforcement agencies and specifically notes outgoing checks and purchases made from 1505/asset-forfeiture funds;
- **5 pinned OpenPeppol XML documents**, including current ViDA pilot material and a Peppol BIS Billing example;
- **1 pinned EN16931 credit-note example**;
- **1 pinned EN16931 negative/conformance example** used to document the boundary between structural UBL parsing and full business-rule validation.

The fifteen public PDFs are not copied into this repository. The manifest points to the external public repository at immutable Git commits and records each upstream Git blob SHA. They include clean vendor quotes as well as multi-document FOIA packets containing requisitions, checks, invoices, approvals and supporting material. That messiness is deliberate.

## Discovery first, frozen gate second

The initial corpus remains `frozen: false` while its behavior is characterized.

During discovery the workflow:

1. downloads every source without transforming it;
2. records final URL, response metadata, size and SHA-256;
3. runs the raw file through `app.parsers.parse_file`;
4. records structured parse output, structured `ParseError`, or an unhandled exception;
5. evaluates source-based assertions for files that can be annotated unambiguously;
6. marks mixed packets as `characterize`, so their parser behavior is recorded without inventing a fake single-document ground truth;
7. fails immediately on download failures or unhandled parser exceptions;
8. reports all source-assertion mismatches even before the corpus is frozen.

Discovery mode is not permission to weaken failures. It prevents us from pretending that a mixed FOIA packet has one obvious invoice/order answer when it does not.

After characterization:

- source-based expectations are reviewed against the upstream material, not against whatever ThisTinti happened to output;
- genuine parser gaps that fall inside product scope are fixed and turned into regressions;
- the corpus is set to `frozen: true`;
- from that point every source assertion and integrity requirement becomes a CI gate.

## What counts as useful failure

Useful failures include:

- a real public vendor quote is readable but its quote number is not recognized;
- USD is interpreted as EUR;
- a real quote table produces no business lines;
- a valid Peppol/EN16931 document is rejected;
- a credit note is classified as an invoice;
- a malformed external document causes an unhandled exception instead of a structured `ParseError`;
- a multi-document public packet shows that ThisTinti needs document segmentation before stronger assertions are possible.

Those failures are evidence. They should become parser improvements or explicit product boundaries, not disappear because the expectation was changed to make CI green.

## Important standards boundary

The current UBL parser is a **structural business-document parser**. It is not a complete EN16931/Peppol Schematron conformance engine. A file intentionally invalid under a standards rule may therefore still parse structurally. The corpus records that fact instead of incorrectly demanding `ParseError` from a validator that the product does not claim to contain.

## Governance boundary

A future PASS means only that the frozen assertions for these 22 raw public/external documents are satisfied and that the characterized packets do not crash the parser. It does **not** mean:

- 100% real-world accuracy;
- OCR robustness on arbitrary scans;
- a completed authorized company pilot;
- legal/accounting/tax validation;
- production readiness by itself.

The controlled company pilot remains a separate gate.
