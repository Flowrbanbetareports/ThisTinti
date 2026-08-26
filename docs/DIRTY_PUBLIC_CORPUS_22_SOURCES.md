# Dirty Public Corpus 22 — source provenance

The corpus deliberately separates genuine public transaction documents from external standards/test material.

## Genuine City of Portland public files

1. Purchase Order `20009330` — City of Portland Procurement Services. Public PDF published by the City's Inclusive Contracting pages. Source page/document: `https://www.portland.gov/procurement/inclusivecontracting/documents/purchase-order-example/download`.
2. Distributed Purchase Order `22356099` — City of Portland Procurement Services. Public PDF: `https://www.portland.gov/procurement/inclusivecontracting/documents/distributed-purchase-order-example/download`.
3. Standard Purchase Order Terms and Conditions — public City document: `https://www.portland.gov/sites/default/files/2020-06/purchase-order-terms-and-conditions.pdf`.
4. Portland Building Construction Contract audit report — public City Auditor document: `https://www.portland.gov/sites/default/files/2021/portland-building-construction-contract-report-10-3-2019.pdf`.

The two purchase orders are the only files above treated as transaction documents. The other two are intentionally non-transactional and should not silently become invoices or orders.

## OpenPeppol ViDA pilot material

Files are fetched from `OpenPEPPOL/vida-pilot-testing` at immutable commit:

`4a2506b2671d8811d469bd1190ff586d5d3d119e`

The selected files exercise cross-border invoices, differing tax jurisdictions, reverse-charge/related cases, and larger invoice payloads. They are external interoperability test material, not real company transactions.

## Peppol BIS Billing examples

Files are fetched from `OpenPEPPOL/peppol-bis-invoice-3` at immutable commit:

`261c458474e27d58a25be629cccac28883171c92`

Selected examples cover a base invoice, allowances/charges and VAT category O.

## EN16931 examples

Files are fetched from `ConnectingEurope/eInvoicing-EN16931` at immutable commit:

`b6c9e06a59812fb1a83585da40923b3678a649ad`

The corpus includes ordinary examples, a credit note, and two negative/edge examples used to verify that invalid or problematic inputs are handled deliberately rather than causing crashes.

## Integrity policy

GitHub-hosted files are pinned to immutable commit SHAs. Portland URLs are public mutable endpoints; discovery mode records their SHA-256 values. The corpus must not be marked `frozen: true` until those four hashes are written into the manifest and rechecked successfully.
