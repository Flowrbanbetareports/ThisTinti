# RC8 completion status

## Public Preview release

The RC8 Public Preview is published as an immutable prerelease from source commit `a2a0d76121326bf08ba14de30ed32de379aa28b4` and tree `5aee4fbafe37d4698c8a3691447fd41805982142`.

Automated release evidence includes the complete repository gate, installed Windows diagnostics, numeric-integrity rejection, restart persistence, artifact provenance, checksums and GitHub attestations.

## Administrative closure

The remaining internal task is to replace the stale RC6 values in `builds/release-latest.json` and `builds/publication-latest.json` with records generated from the already-published RC8 asset inventory. The recovery must not recreate, overwrite or mutate any release asset.

## External work

External validation remains explicitly separate and open in `docs/RC8_EXTERNAL_VALIDATION_GATES.md`. Those gates require real credentials, authorized data or independent human review and cannot be truthfully self-certified by CI.
