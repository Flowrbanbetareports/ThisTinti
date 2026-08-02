# RC8 publication record recovery

The immutable RC8 Public Preview already exists and targets the reviewed source commit. The publication workflow re-verified the complete release gate, exact Windows artifact, checksums, provenance and attestations, then stopped only while generating the repository's `latest` evidence records because the published asset inventory was not identical to the older expected-name set.

This recovery keeps the release immutable and changes no published bytes. It requires every provenance-manifested asset to be present, rejects any published asset that is absent from the exact verified artifact, and checks the local size, SHA-256 and GitHub digest for every published asset before updating `builds/release-latest.json` and `builds/publication-latest.json`.

The recovery request remains pinned to:

- version `3.4.0-alpha.7-rc.8`;
- source commit `a2a0d76121326bf08ba14de30ed32de379aa28b4`;
- source tree `5aee4fbafe37d4698c8a3691447fd41805982142`;
- Windows workflow run `30710864493`.

No external validation gate is converted to PASS by this administrative repair.
