#!/usr/bin/env python3
from __future__ import annotations

import csv
import importlib.metadata as metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "licenses-inventory.csv"


def normalized_license(distribution: metadata.Distribution) -> str:
    value = distribution.metadata.get("License-Expression") or distribution.metadata.get("License")
    if value and value.strip():
        return value.strip().replace("\n", " ")
    classifiers = [
        item.removeprefix("License :: ")
        for item in (distribution.metadata.get_all("Classifier") or [])
        if item.startswith("License :: ")
    ]
    return " | ".join(classifiers) or "UNKNOWN"


def main() -> int:
    rows = []
    for distribution in metadata.distributions():
        name = distribution.metadata.get("Name")
        if not name:
            continue
        rows.append((name, distribution.version, normalized_license(distribution)))
    rows.sort(key=lambda row: row[0].casefold())
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(("package", "version", "declared_license"))
        writer.writerows(rows)
    unknown = [name for name, _, license_value in rows if license_value == "UNKNOWN"]
    print(f"Wrote {OUTPUT} ({len(rows)} distributions)")
    if unknown:
        print("Packages requiring manual license verification: " + ", ".join(unknown))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
