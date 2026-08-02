# RC8 publication record recovery

## Outcome

The recovery is complete. The immutable RC8 Public Preview was not recreated and no published asset was replaced.

Workflow run `30768348013` repeated the complete release gate on the reviewed RC8 source, downloaded the exact Windows artifact from run `30710864493`, verified checksums, smoke reports, source provenance and GitHub attestations, and confirmed that the existing tag and release target the same reviewed commit.

The workflow then used the current hardened publication recorder to verify every published asset against the exact local artifact bytes and update:

- `builds/release-latest.json`;
- `builds/publication-latest.json`.

The final evidence was committed as `7cb63df298b650e3baddcdad6354028db4b75122`.

## Immutable identity

- version: `3.4.0-alpha.7-rc.8`;
- source commit: `a2a0d76121326bf08ba14de30ed32de379aa28b4`;
- source tree: `5aee4fbafe37d4698c8a3691447fd41805982142`;
- Windows workflow run: `30710864493`;
- published assets recorded: 23.

## Claim boundary

This administrative recovery closes the repository inconsistency and changes no external validation status. Authenticode signing, an authorized real-document pilot, independent security/legal review and human assistive-technology assessment remain open until supported by genuine external evidence.
