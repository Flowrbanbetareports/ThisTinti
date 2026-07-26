from __future__ import annotations

import re

# Public artifacts must be built from the final clean commit on main.
RELEASE_VERSION = "3.4.0-alpha.7-rc.6"


def to_python_package_version(release_version: str) -> str:
    """Map the public release label to its equivalent PEP 440 package version."""
    match = re.fullmatch(r"(\d+\.\d+\.\d+)-alpha\.(\d+)-rc\.(\d+)", release_version)
    if not match:
        raise ValueError(f"Unsupported public release version: {release_version!r}")
    base, alpha, release_candidate = match.groups()
    # PEP 440 supports one pre-release phase, not the project's historical
    # nested ``alpha.N-rc.N`` label. Preserve the RC counter as a local segment.
    return f"{base}a{alpha}+rc.{release_candidate}"


PYTHON_PACKAGE_VERSION = to_python_package_version(RELEASE_VERSION)

MIN_AUTOMATION_VALIDATION_SCENARIOS = 30
