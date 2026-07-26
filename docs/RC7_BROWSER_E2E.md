# RC7 real browser recovery and linking gate

## Scope

This RC7 gate replaces mocked API responses in the two browser checks that cover
error recovery and supervised chain correction.

Each check now starts an isolated ThisTinti server with:

- a temporary SQLite database;
- temporary upload, quarantine and rejected-file directories;
- a real cookie session and CSRF protection;
- real HTTP API calls;
- the real application JavaScript and CSS;
- Chromium interactions against the running application.

The recovery check also starts the persistent worker in separate processes. It
proves that a recorded failure can be inspected, retried, reprocessed with
corrected metadata and persisted as a successfully parsed document.

The linking check uploads an order and invoice, opens the real chain from the
keyboard, verifies the candidate confidence and explanation, attaches the
invoice, detaches it and checks database persistence after both actions.

## Evidence

The `Simplified Product Experience` workflow uploads `browser-evidence-*` for
every run, including:

- full-page screenshots before and after recovery;
- full-page screenshots of the proposed and detached link states;
- JSON reports that explicitly record `api_mocked: false`;
- local server logs for both isolated flows.

These tests are internal technical evidence. They do not replace a manual
Windows review at 125%, 150% and 200% zoom, keyboard-only review or testing with
authorised real company documents.
