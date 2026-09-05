from __future__ import annotations

import pytest

from app.version import is_official_release_version, to_python_package_version


@pytest.mark.parametrize(
    "release_version",
    [
        "1.0.0",
        "1.0.1",
        "2.0.0",
        "3.0.0",
        "10.12.3",
    ],
)
def test_official_stable_release_versions_are_supported(release_version: str) -> None:
    assert is_official_release_version(release_version)
    assert to_python_package_version(release_version) == release_version


def test_legacy_development_release_remains_reproducible() -> None:
    release_version = "3.4.0-alpha.7-rc.15"

    assert not is_official_release_version(release_version)
    assert to_python_package_version(release_version) == "3.4.0a7+rc.15"


@pytest.mark.parametrize(
    "release_version",
    [
        "v1.0.0",
        "1.0",
        "01.0.0",
        "1.0.0-rc.1",
        "3.4.0-alpha.7",
        "not-a-version",
        "",
    ],
)
def test_unsupported_release_labels_fail_closed(release_version: str) -> None:
    assert not is_official_release_version(release_version)
    with pytest.raises(ValueError, match="Unsupported public release version"):
        to_python_package_version(release_version)
