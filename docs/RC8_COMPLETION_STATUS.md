# RC8 completion status

## Public Preview release

The RC8 Public Preview is published as an immutable prerelease from source commit `a2a0d76121326bf08ba14de30ed32de379aa28b4` and tree `5aee4fbafe37d4698c8a3691447fd41805982142`.

Automated release evidence includes the complete repository gate, installed Windows diagnostics, numeric-integrity rejection, restart persistence, artifact provenance, checksums and GitHub attestations.

## Administrative closure

The internal publication record is complete. Workflow run `30768348013` re-verified the exact RC8 source and Windows artifact, reused the existing immutable release without uploading or replacing assets, and successfully regenerated the canonical evidence records.

- `builds/release-latest.json` records RC8, the exact release source, Windows run `30710864493`, all mandatory assets and the verified installer, portable and self-hosted hashes.
- `builds/publication-latest.json` records the complete set of 23 published assets and their exact SHA-256 values.
- evidence commit: `7cb63df298b650e3baddcdad6354028db4b75122`.

There is no remaining internal publication blocker for RC8 as a **Public Preview alpha/RC**.

## External work

External validation remains explicitly separate and open in `docs/RC8_EXTERNAL_VALIDATION_GATES.md`. Those gates require real credentials, authorized data or independent human review and cannot be truthfully self-certified by CI.
