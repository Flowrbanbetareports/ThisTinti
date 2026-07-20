#!/usr/bin/env python3
"""Check dependency consistency for ThisTinti's declared dependency graph.

Unlike ``pip check``, this deliberately ignores unrelated packages installed in a
shared Python environment. Every direct dependency from requirements-dev.txt and
all of its reachable runtime dependencies are still validated against the
installed versions and environment markers.
"""

from __future__ import annotations

import sys
from collections import deque
from importlib import metadata
from pathlib import Path

from packaging.requirements import Requirement

ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = ROOT / "requirements-dev.txt"


def load_requirements(path: Path, seen: set[Path] | None = None) -> list[Requirement]:
    seen = seen or set()
    path = path.resolve()
    if path in seen:
        return []
    seen.add(path)
    requirements: list[Requirement] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith(("-r ", "--requirement ")):
            included = line.split(maxsplit=1)[1]
            requirements.extend(load_requirements(path.parent / included, seen))
            continue
        requirements.append(Requirement(line))
    return requirements


def normalized(name: str) -> str:
    return name.lower().replace("_", "-").replace(".", "-")


def main() -> int:
    queue: deque[Requirement] = deque()
    queued: set[str] = set()
    expanded: set[str] = set()
    problems: list[str] = []

    def enqueue(requirement: Requirement) -> None:
        # Collapse duplicate dependency edges. Shared environments can expose a
        # very broad graph and enqueueing the same requirement repeatedly may
        # otherwise grow the queue exponentially before a package is expanded.
        identity = str(requirement)
        if identity not in queued:
            queued.add(identity)
            queue.append(requirement)

    for requirement in load_requirements(ENTRYPOINT):
        enqueue(requirement)

    while queue:
        requirement = queue.popleft()
        if requirement.marker and not requirement.marker.evaluate():
            continue
        key = normalized(requirement.name)
        try:
            distribution = metadata.distribution(requirement.name)
        except metadata.PackageNotFoundError:
            problems.append(f"Missing dependency: {requirement}")
            expanded.add(key)
            continue

        installed_version = distribution.version
        if requirement.specifier and installed_version not in requirement.specifier:
            problems.append(
                f"Version conflict: {requirement.name} {installed_version} does not satisfy {requirement.specifier}"
            )
        if key in expanded:
            continue
        expanded.add(key)
        for child in distribution.requires or []:
            parsed = Requirement(child)
            if parsed.marker and not parsed.marker.evaluate():
                continue
            enqueue(parsed)

    if problems:
        print("Dependency graph check failed:", file=sys.stderr)
        for problem in sorted(set(problems)):
            print(f"- {problem}", file=sys.stderr)
        return 1

    print(f"Dependency graph check passed ({len(expanded)} installed distributions validated)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
