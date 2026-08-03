# RC9 internal candidate

Version: `3.4.0-alpha.7-rc.9`.

This identity is reserved for internal development after the immutable `3.4.0-alpha.7-rc.8` Public Preview. It contains the OCR labelled-line improvement and product-only pilot workflow. It is not a published release, does not replace RC8 assets and must not trigger the public-preview publication workflow.

## Required gates

- complete repository verification;
- PostgreSQL and self-hosted proofs;
- apparel OCR benchmark;
- Windows build, upgrade, installed diagnostics, uninstall and data-preservation lifecycle;
- no mutation of `builds/public-preview-request.json`, RC8 release records or GitHub release assets.
