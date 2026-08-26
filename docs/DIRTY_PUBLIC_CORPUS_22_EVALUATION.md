# Dirty Public Corpus 22 — semantic evaluation protocol

This document defines the measurement layer that sits above the raw corpus characterization.

## Why this exists

A file reaching `parsed` is not evidence that the business document was understood correctly. OCR can be successful while document identity, currency, supplier, references or commercial lines are wrong. For financial review software, a plausible fabricated value is generally worse than an explicit abstention.

The evaluator therefore scores only facts written in the separate ground-truth file `samples/dirty_public_corpus_22_ground_truth.json`. A field omitted from ground truth is **unknown** and is not counted as either a pass or a failure.

## Metrics

The semantic report records, where independently knowable:

- document family;
- document number;
- issue date;
- supplier;
- currency;
- order/contract/delivery/invoice references;
- minimum or complete commercial-line coverage;
- line-item precision, recall and F1;
- line-derived subtotal and tax amount when that derivation is valid for the asserted case;
- document confidence on correct and incorrect cases;
- segmentation expectation;
- explicit hallucinations, defined narrowly as a non-null value produced for a field whose ground truth explicitly requires abstention/null.

The hallucination metric does **not** treat an unscored field as hallucinated. If the source truth is not known, the benchmark must not manufacture an answer simply to score it.

## Abstention policy

`None`, an empty value, or `UNK` can be the correct result when the source does not provide enough reliable evidence. The benchmark should reward that behavior when the ground truth explicitly marks a field as expected-null.

Example: if OCR contains tokens such as `LINK` or `DUTZ` but no reliable business identifier, `number: null` is preferable to selecting one of those tokens as a document number.

## Corpus 1 / Corpus 2 separation

Corpus 1 is the current 22-document dirty public corpus. It is allowed to drive parser hardening during discovery. Once its source assertions and semantic ground truth are reviewed, the following happens in order:

1. source SHA values and ground truth are frozen;
2. `frozen` is set to `true`;
3. expectations are no longer changed to accommodate parser output;
4. regressions become CI failures;
5. only after that freeze is a second, previously unseen corpus selected.

Corpus 2 is the generalization test. Its documents must not be used to shape parser rules before the first baseline run. The initial Corpus 2 result is recorded before any fixes are made. Subsequent fixes may improve the product, but the original unseen baseline remains immutable evidence of how the frozen parser generalized.

## Segmentation boundary

The current parser API returns one `ParsedDocument` for one uploaded file. Multi-document FOIA packets are therefore characterization material until a segmentation layer exists. A packet known to contain multiple logical documents must not be marked as a successful single-document semantic parse merely because text was extracted.

## Windows OCR proof

Linux CI OCR availability is not sufficient for the Local Edition. The frozen Windows smoke test must ingest a scan through the exact packaged executable and assert a known extracted document identifier. This proves that the bundled Tesseract runtime is actually reachable from the installed/frozen application rather than merely present in the build environment.

## Evidence boundary

Neither this corpus nor the future unseen corpus is a real-company pilot. They provide reproducible external-document evidence and generalization evidence respectively. A controlled authorized company pilot remains a separate gate.
