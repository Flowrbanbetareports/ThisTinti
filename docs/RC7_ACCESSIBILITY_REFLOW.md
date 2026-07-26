# RC7 keyboard and reflow evidence

The RC7 browser gate exercises the implemented application in pinned Chromium
against the real local API, database and worker.

It verifies:

- opening a document chain with the keyboard and the `Enter` key;
- persistent recovery errors and actions at the 1366 × 768 reference viewport;
- readable minimum widths for error and recovery-action columns;
- absence of page-level horizontal overflow at effective CSS viewports equivalent
  to 125%, 150% and 200% zoom from the reference viewport;
- continued visibility of the Activities navigation and upload action;
- a screenshot at the 200%-equivalent viewport.

These effective viewport checks are automated reflow evidence. They do not claim
to reproduce browser-specific zoom rendering, Windows display scaling, a screen
reader or every keyboard sequence. Lorenzo's Windows acceptance must still run
actual 125%, 150% and 200% browser zoom, keyboard-only navigation and assistive
technology checks before RC7 is published.
