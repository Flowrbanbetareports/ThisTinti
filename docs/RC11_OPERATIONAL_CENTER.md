# RC11 operational center

This development pass turns ThisTinti from a list of document findings into a supervised operational review workspace.

## Scope implemented

- an operational home that answers what should be reviewed next;
- grouping of active findings by document practice/chain;
- a recommended next review based on severity, workflow status, indicative value and recency;
- a visible case workflow: new, under review, confirmed or false positive, resolved;
- review history backed by the existing append-only decision records;
- practice-level comparison through the existing linked-document comparison view;
- supervised correction of extracted line values with mandatory reason, before/after evidence, actor, timestamp, provenance and chain reanalysis;
- an operational JSON report plus a printable representation;
- learning suggestions derived only from a sufficient set of human decisions and never applied automatically.

## Truth boundary

The report does not invent manual baseline time, assisted time, known false negatives or user scores. Those fields remain unavailable until they are measured in an authorised real-document pilot.

Indicative amounts can overlap when multiple findings concern the same commercial difference. The interface states this explicitly and does not represent the sum as a guaranteed saving or recoverable amount.

## Safety boundary

- original files are never modified;
- corrections affect extracted data only and remain auditable;
- no payment, accounting, supplier, email or messaging action is introduced;
- no learning proposal changes a rule without explicit human approval;
- tenant isolation and existing reviewer permissions remain mandatory;
- this pass is not a legal, accounting, security, accessibility or production certification.

## Release boundary

The current public release remains the immutable `3.4.0-alpha.7-rc.10` Public Preview. This branch now carries the unreleased `3.4.0-alpha.7-rc.11` identity; publication remains a separate decision after the complete application, browser, PostgreSQL, self-hosted and Windows lifecycle gates pass on the exact final commit.
