#!/usr/bin/env python3
"""Small GitHub-backed coordination dashboard for ThisTinti agents.

Read-only status uses the public GitHub API. Claim/release operations require
GITHUB_TOKEN and record append-only lease events on the configured lease board.

The dashboard is a navigation aid only: live GitHub state and #136 remain the
qualification source of truth.
"""

from __future__ import annotations

import argparse
import configparser
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DEFAULT_REPO = "Flowrbanbetareports/ThisTinti"
DEFAULT_TTL_MINUTES = 45
MAX_TTL_MINUTES = 180
LEASE_HISTORY_HOURS = 6
LEASE_MARKER = "<!-- thistinti-agent-lease:v1 -->"
LEASE_BOARD_TITLE = "Agent Lease Board — ThisTinti coordination"
TRACKED = {
    "A": [131, 133],
    "B": [132, 19],
    "C": [20, 21, 32, 94, 134, 135],
}


@dataclass(frozen=True)
class Lease:
    item: str
    owner: str
    claimed_at: datetime
    expires_at: datetime
    state: str
    comment_id: int | None = None

    @property
    def active(self) -> bool:
        return self.state == "active" and self.expires_at > datetime.now(UTC)


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_from_git() -> str | None:
    config_path = Path(".git") / "config"
    try:
        parser = configparser.ConfigParser()
        parser.read(config_path, encoding="utf-8")
        remote = parser.get('remote "origin"', "url", fallback="").strip()
    except (OSError, configparser.Error):
        return None
    if not remote:
        return None
    if remote.startswith("git@github.com:"):
        value = remote.split(":", 1)[1]
    elif "github.com/" in remote:
        value = remote.split("github.com/", 1)[1]
    else:
        return None
    value = value.removesuffix(".git").strip("/")
    return value if value.count("/") == 1 else None


def resolve_repo(cli_repo: str | None) -> str:
    return cli_repo or os.getenv("GITHUB_REPOSITORY") or _repo_from_git() or DEFAULT_REPO


def _headers(write: bool = False) -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "ThisTinti-agent-status/1",
    }
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    elif write:
        raise RuntimeError("GITHUB_TOKEN is required for claim/release operations")
    return headers


def api(repo: str, path: str, *, method: str = "GET", payload: dict[str, Any] | None = None) -> Any:
    data = None
    if payload is not None:
        data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repo}{path}",
        data=data,
        method=method,
        headers=_headers(write=method != "GET"),
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API {exc.code} for {path}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"GitHub API unavailable for {path}: {exc.reason}") from exc
    return json.loads(body) if body else None


def paged(repo: str, path: str, *, per_page: int = 100, max_pages: int = 10) -> list[Any]:
    items: list[Any] = []
    separator = "&" if "?" in path else "?"
    for page in range(1, max_pages + 1):
        batch = api(repo, f"{path}{separator}per_page={per_page}&page={page}")
        if not isinstance(batch, list):
            raise RuntimeError(f"Expected list response for {path}")
        items.extend(batch)
        if len(batch) < per_page:
            break
    return items


def find_lease_board(repo: str) -> int:
    encoded = urllib.parse.quote(f'repo:{repo} is:issue is:open in:title "{LEASE_BOARD_TITLE}"')
    request = urllib.request.Request(
        f"https://api.github.com/search/issues?q={encoded}&per_page=10",
        headers=_headers(),
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            result = json.loads(response.read().decode("utf-8"))
    except (urllib.error.HTTPError, urllib.error.URLError) as exc:
        raise RuntimeError(f"Cannot locate lease board: {exc}") from exc
    exact = [item for item in result.get("items", []) if item.get("title") == LEASE_BOARD_TITLE]
    if not exact:
        raise RuntimeError(f'Lease board not found. Create an open issue titled exactly "{LEASE_BOARD_TITLE}".')
    exact.sort(key=lambda item: item["number"], reverse=True)
    return int(exact[0]["number"])


def recent_lease_comments(repo: str, board: int) -> list[dict[str, Any]]:
    since = _iso(_utc_now() - timedelta(hours=LEASE_HISTORY_HOURS))
    encoded_since = urllib.parse.quote(since, safe="")
    return paged(repo, f"/issues/{board}/comments?since={encoded_since}")


def parse_lease_comment(body: str, comment_id: int | None = None) -> Lease | None:
    if LEASE_MARKER not in body:
        return None
    payload_text = body.split(LEASE_MARKER, 1)[1].strip()
    if payload_text.startswith("```json"):
        payload_text = payload_text[len("```json") :]
        if "```" in payload_text:
            payload_text = payload_text.split("```", 1)[0]
    try:
        payload = json.loads(payload_text.strip())
        return Lease(
            item=str(payload["item"]),
            owner=str(payload["owner"]),
            claimed_at=_parse_time(str(payload["claimed_at"])),
            expires_at=_parse_time(str(payload["expires_at"])),
            state=str(payload["state"]),
            comment_id=comment_id,
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None


def current_leases(comments: list[dict[str, Any]]) -> dict[str, Lease]:
    latest: dict[str, Lease] = {}
    for comment in comments:
        lease = parse_lease_comment(str(comment.get("body", "")), comment.get("id"))
        if lease is None:
            continue
        previous = latest.get(lease.item)
        if previous is None or lease.claimed_at >= previous.claimed_at:
            latest[lease.item] = lease
    return {item: lease for item, lease in latest.items() if lease.active}


def lease_body(item: str, owner: str, state: str, ttl_minutes: int) -> str:
    now = _utc_now()
    expires = now if state == "released" else now + timedelta(minutes=ttl_minutes)
    payload = {
        "item": item,
        "owner": owner,
        "claimed_at": _iso(now),
        "expires_at": _iso(expires),
        "state": state,
    }
    return f"{LEASE_MARKER}\n```json\n{json.dumps(payload, sort_keys=True)}\n```"


def post_lease(repo: str, board: int, *, item: str, owner: str, state: str, ttl_minutes: int) -> None:
    active = current_leases(recent_lease_comments(repo, board))
    existing = active.get(item)
    if state == "active" and existing and existing.owner != owner:
        remaining = max(0, int((existing.expires_at - _utc_now()).total_seconds() // 60))
        raise RuntimeError(f"{item} is leased by {existing.owner} until {_iso(existing.expires_at)} (~{remaining} min)")
    if state == "released" and existing and existing.owner != owner:
        raise RuntimeError(f"Refusing to release {item}: active owner is {existing.owner}, not {owner}")
    api(
        repo,
        f"/issues/{board}/comments",
        method="POST",
        payload={"body": lease_body(item, owner, state, ttl_minutes)},
    )


def _snapshot(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "number": int(data["number"]),
        "title": data.get("title", ""),
        "state": data.get("state", "unknown"),
        "is_pr": "pull_request" in data,
        "updated_at": data.get("updated_at"),
    }


def tracked_snapshots(repo: str) -> dict[int, dict[str, Any]]:
    wanted = {number for numbers in TRACKED.values() for number in numbers}
    issues = paged(repo, "/issues?state=all&sort=created&direction=desc", max_pages=3)
    snapshots = {int(data["number"]): _snapshot(data) for data in issues if int(data["number"]) in wanted}
    for number in sorted(wanted - snapshots.keys()):
        snapshots[number] = _snapshot(api(repo, f"/issues/{number}"))
    return snapshots


def status(repo: str) -> int:
    repository = api(repo, "")
    default_branch = repository.get("default_branch", "main")
    branch = api(repo, f"/branches/{urllib.parse.quote(default_branch, safe='')}")
    main_sha = branch["commit"]["sha"]
    pulls = paged(repo, "/pulls?state=open&sort=updated&direction=desc", max_pages=3)
    board = find_lease_board(repo)
    leases = current_leases(recent_lease_comments(repo, board))
    snapshots = tracked_snapshots(repo)

    print("THISTINTI AGENT STATUS")
    print(f"repo: {repo}")
    print(f"{default_branch}: {main_sha}")
    print("master: #136 — live GitHub issue remains authoritative")
    print(f"lease board: #{board}")
    print()

    print("OPEN PULL REQUESTS")
    if not pulls:
        print("- none")
    for pull in pulls:
        print(
            f"- #{pull['number']} {pull['title']} | head={pull['head']['sha'][:12]} | "
            f"branch={pull['head']['ref']} | updated={pull['updated_at']}"
        )
    print()

    print("STREAMS")
    for stream, numbers in TRACKED.items():
        print(f"{stream}:")
        for number in numbers:
            snap = snapshots[number]
            item = f"issue:{number}"
            lease = leases.get(item)
            lease_text = f"LEASED {lease.owner} until {_iso(lease.expires_at)}" if lease else "unleased"
            kind = "PR" if snap["is_pr"] else "issue"
            print(f"  - #{number} [{snap['state']}] {kind}: {snap['title']} | {lease_text}")
    print()

    print("OTHER ACTIVE LEASES")
    tracked_items = {f"issue:{n}" for values in TRACKED.values() for n in values}
    extras = [(item, lease) for item, lease in sorted(leases.items()) if item not in tracked_items]
    if not extras:
        print("- none")
    for item, lease in extras:
        print(f"- {item}: {lease.owner} until {_iso(lease.expires_at)}")
    print()

    a_definitely_incomplete = any(snapshots[number]["state"] != "closed" for number in TRACKED["A"])
    print("CHECKPOINT GUARDS")
    if a_definitely_incomplete:
        print("- FINE A: NOT COMPLETE (at least one tracked A item is still open)")
    else:
        print("- FINE A: issue states no longer prove incompleteness; VERIFY every #136 condition manually")
    if snapshots[132]["state"] != "closed":
        print("- FREEZE E1: NOT READY (#132 is still open)")
    else:
        print("- FREEZE E1: #132 closure is necessary but NOT sufficient; verify #19 protocol evidence manually")
    print("- QUALIFIED: NEVER inferred automatically; verify the complete #136 exit criterion")
    print()
    print("NOTE: 'unleased' means only 'not currently claimed'. It does NOT mean safe or dependency-ready.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", help="owner/name; defaults to GITHUB_REPOSITORY, git remote, then ThisTinti")
    sub = parser.add_subparsers(dest="command")

    claim = sub.add_parser("claim", help="claim or renew a short-lived work lease")
    claim.add_argument("--item", required=True, help="stable work item, e.g. issue:135 or pr:140")
    claim.add_argument("--owner", required=True, help="agent identity, e.g. qualification-c")
    claim.add_argument("--ttl", type=int, default=DEFAULT_TTL_MINUTES, help="lease TTL in minutes")

    release = sub.add_parser("release", help="release a work lease")
    release.add_argument("--item", required=True)
    release.add_argument("--owner", required=True)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo = resolve_repo(args.repo)
    try:
        if args.command == "claim":
            if args.ttl < 5 or args.ttl > MAX_TTL_MINUTES:
                raise RuntimeError(f"TTL must be between 5 and {MAX_TTL_MINUTES} minutes")
            board = find_lease_board(repo)
            post_lease(repo, board, item=args.item, owner=args.owner, state="active", ttl_minutes=args.ttl)
            print(f"claimed {args.item} for {args.owner} ({args.ttl} min)")
            return 0
        if args.command == "release":
            board = find_lease_board(repo)
            post_lease(
                repo,
                board,
                item=args.item,
                owner=args.owner,
                state="released",
                ttl_minutes=DEFAULT_TTL_MINUTES,
            )
            print(f"released {args.item} for {args.owner}")
            return 0
        return status(repo)
    except RuntimeError as exc:
        print(f"agent_status: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
