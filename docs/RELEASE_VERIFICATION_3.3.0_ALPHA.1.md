# ThisTinti 3.3.0-alpha.1 — Local Free Edition verification

## Verified in the source checkout

- 138 tests passed.
- Application coverage meets the blocking 90% threshold.
- Ruff, formatting, Bandit, Python compilation and JavaScript syntax passed.
- The declared dependency graph passed for 63 installed distributions.
- SQLite/Alembic completed upgrade, schema check, downgrade to base, second
  upgrade and final schema check.
- The synthetic Validation Gate completed with precision, recall and F1 equal
  to 1.0. It remains technically unable to authorize production automation.
- The HTTP smoke created a local organization, loaded the demo, verified the
  dashboard, readiness and audit chain.
- Backup, manifest verification and restore passed, including a stored file and
  SQLite integrity check.

## Local distribution proof

The source Local Edition was exercised as a user-facing distribution:

1. launcher started the API and persistent worker;
2. a local organization was registered;
3. a proposal document was uploaded;
4. the worker completed the ingestion job;
5. both processes were stopped;
6. the application was restarted with the same data directory;
7. the same document was present after restart.

The machine-readable evidence is in
`docs/evidence/local-distribution-smoke-3.3.0-alpha.1.json`.

## Distribution design completed

- Windows per-user installer definition using Inno Setup;
- Windows portable archive build;
- PyInstaller onedir specification with local application, worker, static UI,
  source snapshot and PDFium;
- local Tesseract OCR bundle with English and Italian models;
- automated frozen executable smoke test before packaging;
- SHA-256 generation for installer and portable archive;
- GitHub Actions workflow for tests, build, smoke and GitHub Release;
- static GitHub Pages download site without project analytics;
- Apache 2.0 license, NOTICE, privacy, support and customization documents.

## Not yet claimed as verified

No Windows executable was generated in this Linux environment. PyInstaller
analysis was started but the available command execution window ended before the
freeze completed; PyInstaller cannot create a Windows executable from Linux.
The actual installer, portable archive and frozen-runtime smoke therefore remain
blocking outputs of `.github/workflows/windows-release.yml` on a clean Windows
runner.

The first public release must not be called stable until that workflow is green
and installation/uninstallation have also been tried on real Windows 10 and 11
machines. The build is not digitally signed, so Windows SmartScreen may warn.

The local `pip-audit` request timed out because the vulnerability service was not
reachable. A separate blocking dependency-audit job remains in GitHub CI.

## Product boundary

The Local Edition has no central ThisTinti account, project telemetry or cloud
requirement and binds only to the loopback interface. It is provided without
warranty and cannot eliminate all legal or operational responsibility. Companies
remain responsible for their data, custom forks and decisions; human review is
required for payments, accounting and legal actions.
