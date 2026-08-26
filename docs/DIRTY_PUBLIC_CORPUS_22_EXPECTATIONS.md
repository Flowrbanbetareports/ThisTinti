# Dirty Public Corpus 22 — expectation policy

Expectations are intentionally source-based, not fitted to current parser output.

For valid external XML invoices, the minimum expectation is successful parsing with the correct document family, at least one business line (two where the source scenario explicitly contains two lines), and the declared currency where known.

For the Portland purchase orders, the source itself gives the expected document number, USD currency and visible line counts. The current PDF parser is given only the document type (`order`), because PDF parsing presently requires that hint. Number, currency and line extraction are not overridden: the corpus is supposed to reveal whether ThisTinti can recover those facts from the raw PDF.

For deliberately negative EN16931 samples and for non-transactional Portland PDFs, the expected outcome is a structured `ParseError`. The benchmark treats an unhandled exception as a harder failure than an ordinary expectation mismatch.

During `0.1-discovery`, expectation mismatches are reported but do not fail the workflow. Download failures and unhandled exceptions do fail immediately. Once source hashes and expectations are reviewed, the manifest becomes frozen and every mismatch becomes a CI failure.
