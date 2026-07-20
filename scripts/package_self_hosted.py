#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import zipfile

from package_release import ROOT, VERSION, should_include, zip_info

OUTPUT = ROOT.parent / f"ThisTinti-{VERSION}-self-hosted-source.zip"
CHECKSUM = ROOT.parent / f"ThisTinti-{VERSION}-self-hosted-source.zip.sha256"


def main() -> int:
    files = sorted(path for path in ROOT.rglob("*") if should_include(path))
    OUTPUT.unlink(missing_ok=True)
    with zipfile.ZipFile(OUTPUT, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            relative = path.relative_to(ROOT)
            executable = path.stat().st_mode & 0o111 != 0 and path.suffix in {".py", ".sh"}
            archive.writestr(zip_info(relative, executable), path.read_bytes())
    with zipfile.ZipFile(OUTPUT) as archive:
        bad = archive.testzip()
        if bad:
            raise RuntimeError(f"Corrupted self-hosted ZIP member: {bad}")
        names = set(archive.namelist())
    required = {
        "ThisTinti/deploy/enterprise/docker-compose.enterprise.yml",
        "ThisTinti/docs/ENTERPRISE_SELF_HOSTED.md",
        "ThisTinti/docs/RESPONSIBILITY_MATRIX.md",
        "ThisTinti/TERMS_OF_USE.md",
    }
    missing = sorted(required - names)
    if missing:
        raise RuntimeError(f"Self-hosted package is incomplete: {missing}")
    leaked = []
    for name in sorted(names):
        relative = name.removeprefix("ThisTinti/")
        if relative in {"deploy/enterprise/.env", "deploy/enterprise/operator-acceptance.json"}:
            leaked.append(name)
            continue
        if relative.startswith(("deploy/enterprise/secrets/", "deploy/enterprise/backups/", "deploy/enterprise/logs/")):
            if not relative.endswith("/.gitkeep"):
                leaked.append(name)
    if leaked:
        raise RuntimeError(f"Generated operator material leaked into package: {leaked[:5]}")
    digest = hashlib.sha256(OUTPUT.read_bytes()).hexdigest()
    CHECKSUM.write_text(f"{digest}  {OUTPUT.name}\n", encoding="utf-8")
    print(f"Created {OUTPUT}")
    print(f"SHA-256 {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
