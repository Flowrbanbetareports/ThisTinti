# Repository-wide hardening audit — 2026-08-27

This pass reviewed the current repository as a system rather than treating one pull request in isolation.

## Corrected findings

- GitHub Actions benchmark workflows no longer commit generated evidence directly to `main`; evidence is retained as commit-bound workflow artifacts.
- The Public Preview publication workflow no longer advances `main` after publishing a release; publication records are immutable workflow artifacts.
- The runtime Docker image explicitly drops root privileges with `USER thistinti`.
- Frozen Windows OCR discovery fails closed on the bundled runtime instead of silently accepting an unrelated system Tesseract installation.
- Persistent worker failure bookkeeping rolls back an invalid transaction before recording retry/terminal state.
- SQLite restore is staged before target mutation, performs exact storage replacement under `--force`, and rolls back filesystem/database swaps on replacement failure. PostgreSQL restore uses a single database transaction and pre-validates/stages storage.
- Heuristic PDF parsing abstains on a bare dollar symbol and rejects weak OCR row alignments whose source totals contradict the proposed pairing.
- The dirty-public semantic evaluator verifies frozen source SHA-256 values before parsing, excludes manifest override fields from accuracy scoring, reports line precision only for complete line ground truth, and no longer treats `logical_document_count: 1` as an independently measured segmentation success.
- GitHub Pages write/OIDC permissions are scoped to the deploy job.
- The enterprise self-hosted probe pins the PyYAML version used by the repository lock.
- Repository governance regression tests reject direct Actions pushes to `main`, writable benchmark workflows, root container regressions, and publication-evidence commits to `main`.

## Boundary

This audit is an internal engineering hardening pass. It is not an independent penetration test, legal review, WCAG assistive-technology audit, real-company pilot, or production certification. Those external validation gates remain separate.
