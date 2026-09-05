# Agent coordination protocol

This document explains the lightweight coordination layer introduced for automated agents. It is intentionally small: it reduces repeated discovery work without becoming a second project-management system.

## Components

- `AGENTS.md`: stable operating rules and session bootstrap.
- `scripts/agent_status.py`: live read-only dashboard plus optional claim/release commands.
- GitHub issue titled exactly `Agent Lease Board — ThisTinti coordination`: append-only lease event log.

## Lease event model

Each claim or release is stored as a normal issue comment containing a machine-readable marker and JSON payload. The log is append-only; old events are never rewritten.

An active lease contains:

- `item`: stable identifier such as `issue:135` or `pr:140`;
- `owner`: agent identity;
- `claimed_at`: UTC timestamp;
- `expires_at`: UTC timestamp;
- `state`: `active` or `released`.

For each item, the newest valid event wins. An `active` event whose `expires_at` is in the past is ignored automatically. This prevents abandoned sessions from creating permanent ghost locks.

## Safety boundary

A lease is a coordination hint, not a mutex enforced by GitHub. It must never be used as evidence that a task is technically safe, dependency-ready, qualified or approved.

The agent must still inspect live GitHub state and obey #136, branch protection, workflow/check results and the exact current SHA.

## Typical use

```text
python scripts/agent_status.py
python scripts/agent_status.py claim --item issue:135 --owner qualification-c
# work on the coherent item
python scripts/agent_status.py release --item issue:135 --owner qualification-c
```

Claims default to 45 minutes and may be renewed by the same owner. `--ttl` accepts 5–180 minutes.

Claim/release requires `GITHUB_TOKEN`. Status is read-only and can use the public API without a token, subject to GitHub rate limits.

## Failure modes

- **Agent stops without release:** lease expires automatically.
- **Two agents claim simultaneously:** the second agent re-reads the board before posting, but the protocol remains advisory; agents must also check recent branches/PRs/commits before writes.
- **Dashboard is stale or wrong:** live GitHub state wins. Stop and investigate rather than acting on the dashboard.
- **Lease board unavailable:** coordination degrades to direct GitHub inspection; qualification must not fail open.
- **No token:** status still works; writes to the lease board are refused.

## Qualification interaction

This coordination layer does not change the product claim, P1/E1 protocol or evidence requirements. After the active #131 slice is merged, the coordination branch must be refreshed against the resulting `main` and pass the applicable gates on its own final SHA before merge.