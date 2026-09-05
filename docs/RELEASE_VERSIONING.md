# ThisTinti release versioning

## Official product line

From the first Qualified product release onward, the public/product nomenclature is:

- `RELEASE 1.0.0` — first official Qualified release (`ThisTinti 1.0.0 Qualified — Procurement v1 — P1 — E1`);
- `RELEASE 1.0.x` — qualified 1.0 maintenance line for security/critical fixes, with revalidation appropriate to each change;
- `RELEASE 2.0.0` — Continuous Assurance product generation;
- `RELEASE 3.0.0` — future commercialisation/distribution generation unless a later explicit product decision changes that boundary.

GitHub keeps the conventional technical tags `v1.0.0`, `v1.0.x`, `v2.0.0`, `v3.0.0`, and so on. The human-facing `RELEASE X.Y.Z` name and the `vX.Y.Z` Git tag refer to the same official release.

Existing `v3.4.0-alpha.*` / RC tags are immutable **legacy development prereleases**. They remain part of the repository history and must not be numerically compared with the new official line to infer chronology or readiness. Moving from a legacy `3.4.x` prerelease to `RELEASE 1.0.0` / tag `v1.0.0` is a versioning-boundary reset, not a downgrade.

## Transition rule

Do **not** change `app.version.RELEASE_VERSION` to `1.0.0` merely because Stream A/FINE A is complete. The stable version belongs to the final release candidate and must be included in the exact-SHA qualification/release sweep required by #136.

When the final 1.0 candidate is legitimately ready for the official version transition:

1. set `RELEASE_VERSION` to `1.0.0` and align every version-bearing source required by `scripts/check_release_consistency.py` (including the PEP 440 package version in `pyproject.toml`);
2. regenerate release metadata and artifacts;
3. rerun the complete required qualification/release gates on the resulting exact final SHA;
4. build/verify the exact Windows and self-hosted artifacts from that SHA;
5. publish `RELEASE 1.0.0` with Git tag `v1.0.0` only through the official-release path as a non-draft, non-prerelease release;
6. record the release SHA/artifact evidence and only then allow the post-1.0 Supervisor activation contract to be evaluated.

A tag, RC, FINE A declaration, stale green run, or legacy prerelease is not an official release.

## Publication paths

`.github/workflows/publish-public-preview.yml` is retained for historical/development Public Preview prereleases and must not be used to publish the official stable line.

`.github/workflows/publish-qualified-release.yml` is the dedicated stable publication path. It is manual-only and fails closed unless the requested target is the exact current `main`, `RELEASE_VERSION` is a stable SemVer value, the complete release verification passes on that source, the required exact-commit workflows/Windows artifact are verified, and any pre-existing tag/release is consistent and already non-draft/non-prerelease.

The publication workflow is a technical release gate, not a substitute for the scientific, human, security, legal/privacy, recovery, signing and controlled-rollout evidence required by the applicable qualification master.

## 2.0 activation boundary

The existence of `RELEASE 1.0.0` / tag `v1.0.0` is necessary but not sufficient for peer agents to start 2.0. They must additionally validate the unique machine-readable activation block in the **body** of the central `ThisTinti 2.0.0 — Continuous Assurance Platform` master issue according to the `thistinti-phase:v1` contract. Mentions in comments, logs, quotes, prompts, tests, other issues/PRs or release notes are never activation markers.
