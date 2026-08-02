# Internal real-pilot handoff contract

This document defines what the product must export before an authorised organisation can execute a pilot. It is not an outreach document and contains no contact workflow.

## Required product output

The local toolkit must create:

- a manifest identifying the exact ThisTinti version and the single validated process;
- at least 30 isolated case directories;
- an authorisation record whose default state is `pending`;
- a file inventory with size and SHA-256;
- an inspection report for identifiers and binary files requiring manual redaction review;
- a measurement table for two distinct reviewers, manual time, assisted time, findings, false positives, false negatives, critical misses and user score;
- a final JSON and Markdown report with explicit limitations.

## Safety requirements

The product must:

- keep `safe_to_automate=false` unless the exact real dataset and run satisfy the existing validation governance;
- reject fewer than 30 cases;
- reject missing or duplicated reviewer identities;
- reject zero, negative or missing timings;
- stop on unauthorised documents, unresolved identifiers, cross-case contamination or critical silent misses;
- perform no email, messaging, accounting, payment or supplier action;
- retain original evidence links and record all derived values.

## Decision boundary

The internal summary may return only a limited technical decision for the tested process. It must never represent the pilot as a legal, accounting, privacy, security or production certification.
