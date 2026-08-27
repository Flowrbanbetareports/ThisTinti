from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LIMITS = {
    "app/main.py": 80,
    "app/api.py": 3300,
    "app/rc15_api.py": 900,
    "app/services/rc15.py": 1600,
    "app/services/intelligence.py": 1450,
    "app/services/rules.py": 1000,
    "app/services/discovery.py": 850,
    "app/static/app-core.js": 1150,
    "app/static/rc15.js": 1200,
}


def source_lines(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


def build_report() -> dict[str, object]:
    modules: list[dict[str, object]] = []
    failures: list[str] = []
    for relative, limit in LIMITS.items():
        path = ROOT / relative
        count = source_lines(path)
        remaining = limit - count
        modules.append(
            {
                "path": relative,
                "lines": count,
                "limit": limit,
                "remaining": remaining,
                "passed": remaining >= 0,
            }
        )
        if remaining < 0:
            failures.append(f"{relative}: {count} righe, limite {limit}")
    return {
        "schema": "thistinti.module-boundaries.v1",
        "passed": not failures,
        "modules": modules,
        "failures": failures,
        "policy": (
            "I moduli già grandi non possono continuare a crescere. "
            "Nuove responsabilità devono essere estratte in moduli separati e testabili."
        ),
    }


def main() -> int:
    report = build_report()
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
