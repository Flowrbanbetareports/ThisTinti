# RC7 version syntax

ThisTinti keeps one semantic release identity in two required textual forms:

- public release, runtime, installer, OpenAPI, SBOM and artifact label:
  `3.4.0-alpha.7-rc.6`;
- Python project metadata (PEP 440):
  `3.4.0a7+rc.6`.

The historical public label contains two nested prerelease phases. PEP 440 allows
one prerelease phase, so the package form preserves the RC counter in a local
version segment. This does not create a different product release.

`app.version.to_python_package_version` defines the mapping. Both release gates
read `pyproject.toml` and reject any package version that is not the exact mapped
value. The RC7 finalization must therefore update the public label to
`3.4.0-alpha.7-rc.7` and the project metadata to `3.4.0a7+rc.7` in the same
candidate commit.

This syntax split affects package metadata only. Installer names, checksums,
release records, OpenAPI, SBOM and provenance continue to use the public release
label.
