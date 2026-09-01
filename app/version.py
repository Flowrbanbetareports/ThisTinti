from __future__ import annotations

import re

# Public artifacts must be built from the final clean commit on main.
#
# The current 3.4.x alpha/RC label belongs to the legacy development-preview
# line. The first official Qualified release will start the stable product
# line at 1.0.0; do not change this value to 1.0.0 before qualification.
RELEASE_VERSION = "3.4.0-alpha.7-rc.15"

_STABLE_RELEASE_RE = re.compile(r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)")
_LEGACY_DEVELOPMENT_RELEASE_RE = re.compile(r"(\d+\.\d+\.\d+)-alpha\.(\d+)-rc\.(\d+)")


def is_official_release_version(release_version: str) -> bool:
    """Return whether *release_version* belongs to the official stable line."""
    return _STABLE_RELEASE_RE.fullmatch(release_version) is not None


def to_python_package_version(release_version: str) -> str:
    """Map a public release label to its equivalent PEP 440 package version.

    Official product releases use ordinary stable SemVer labels (for example
    ``1.0.0`` and ``2.0.0``) and map to the same PEP 440 version. Historical
    development previews keep the legacy ``X.Y.Z-alpha.N-rc.N`` mapping so
    already-published artifacts remain reproducible.
    """
    if is_official_release_version(release_version):
        return release_version

    match = _LEGACY_DEVELOPMENT_RELEASE_RE.fullmatch(release_version)
    if not match:
        raise ValueError(f"Unsupported public release version: {release_version!r}")

    base, alpha, release_candidate = match.groups()
    # PEP 440 supports one pre-release phase, not the project's historical
    # nested ``alpha.N-rc.N`` label. Preserve the RC counter as a local segment.
    return f"{base}a{alpha}+rc.{release_candidate}"


PYTHON_PACKAGE_VERSION = to_python_package_version(RELEASE_VERSION)

MIN_AUTOMATION_VALIDATION_SCENARIOS = 30
