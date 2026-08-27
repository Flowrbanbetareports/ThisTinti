# Dirty Public Corpus 22 — source provenance

The corpus deliberately separates real public financial packets from interoperability/standards test material.

## Lucy Parsons Labs public-record collection

Fifteen PDFs are referenced from `lucyparsons/1505-documents` at immutable commit:

`8a47f5029547dd35aaa523b55706bfbaa596635c`

The upstream README says the repository is storage for records received during Lucy Parsons Labs research, mostly FOIA documents obtained from Chicago-area law-enforcement agencies. It also describes outgoing checks and purchases from 1505/asset-forfeiture funds. The selected files contain vendor quotes, requisitions, check requests, invoices, approvals and supporting financial records.

The two most strongly annotated real-public cases are:

- Pen-Link quote `QUO-01487-5Z12C3`;
- Pen-Link quote `QUO-04689-V8Y5D0`.

Their companion text records upstream make the quote identifiers, USD denomination and visible commercial-line structure independently inspectable.

The remaining thirteen PDFs are intentionally messier FOIA packets. Several contain more than one logical document. They are used first as robustness/segmentation characterization cases rather than being assigned invented single-document ground truth.

The external PDF bytes are **not vendored into ThisTinti**. The manifest stores pinned raw URLs and upstream Git blob SHAs; CI downloads the files temporarily for characterization.

## OpenPeppol ViDA pilot material

Files are fetched from `OpenPEPPOL/vida-pilot-testing` at immutable commit:

`4a2506b2671d8811d469bd1190ff586d5d3d119e`

Selected files exercise cross-border invoices and credit notes. They are external interoperability test material, not real company transactions.

## Peppol BIS Billing example

The base example is fetched from `OpenPEPPOL/peppol-bis-invoice-3` at immutable commit:

`261c458474e27d58a25be629cccac28883171c92`

## EN16931 examples

Files are fetched from `ConnectingEurope/eInvoicing-EN16931` at immutable commit:

`b6c9e06a59812fb1a83585da40923b3678a649ad`

The corpus includes a credit note and a conformance-negative example. The latter is not expected to raise a parser error because ThisTinti currently performs structural UBL parsing, not complete EN16931 Schematron/business-rule validation.

## Integrity policy

Every source URL is pinned to a full Git commit SHA. The manifest records upstream Git blob SHAs where discovered, and each run independently records the downloaded byte-stream SHA-256 in its evidence report. A future frozen corpus must keep those source identities immutable.
