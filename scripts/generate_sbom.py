#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.version import RELEASE_VERSION  # noqa: E402

LOCK = ROOT / "requirements-linux.lock.txt"
OUTPUT = ROOT / "docs" / "sbom.cdx.json"
VERSION = RELEASE_VERSION


def components() -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for raw_line in LOCK.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "==" not in line:
            continue
        name, version = line.split("==", 1)
        normalized = name.strip().lower().replace("_", "-")
        version = version.strip()
        result.append(
            {
                "type": "library",
                "name": normalized,
                "version": version,
                "purl": f"pkg:pypi/{normalized}@{version}",
                "bom-ref": f"pkg:pypi/{normalized}@{version}",
            }
        )
    return sorted(result, key=lambda item: item["name"])


def main() -> int:
    items = components()
    fingerprint = hashlib.sha256(LOCK.read_bytes()).hexdigest()
    application_ref = f"pkg:generic/thistinti@{VERSION}"
    payload = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:{fingerprint[:8]}-{fingerprint[8:12]}-{fingerprint[12:16]}-{fingerprint[16:20]}-{fingerprint[20:32]}",
        "version": 1,
        "metadata": {
            "component": {
                "type": "application",
                "name": "ThisTinti",
                "version": VERSION,
                "bom-ref": application_ref,
            },
            "properties": [
                {"name": "thistinti:source-lock", "value": LOCK.name},
                {"name": "thistinti:lock-sha256", "value": fingerprint},
                {
                    "name": "thistinti:vulnerability-audit",
                    "value": "not-included; requires an online vulnerability database",
                },
            ],
        },
        "components": items,
        "dependencies": [{"ref": application_ref, "dependsOn": [item["bom-ref"] for item in items]}],
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{OUTPUT} ({len(items)} components)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
