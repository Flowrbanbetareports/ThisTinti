# ThisTinti Agent Operating Contract

This file is the short, stable operating contract for automated agents working on this repository. It is a navigation aid, not a substitute for the live GitHub state.

## Source of truth

1. GitHub `main`, open pull requests, workflow/check results and repository rules are authoritative for live state.
2. Qualification master issue `#136` defines the current bounded target: `ThisTinti 1.0 Qualified — Procurement v1 — P1 — E1`.
3. This file defines stable coordination rules only. Never treat cached status output as fresher than GitHub.

## Core product invariants

- Preserve `DOCUMENTO → FACT → FINDING → GIUDIZIO umano`.
- Fail closed when exact current evidence is missing, stale, unavailable, ambiguous or unsupported.
- Provenance and findings are immutable/versioned; human judgment binds to the exact current finding version.
- Do not inherit green qualification from an earlier SHA.
- A matrix/provenance promotion changes the candidate SHA and requires the applicable qualification gates again on that final SHA.
- Never lower thresholds, disable tests or bypass required controls to make a candidate pass.
- Never invent external evidence: design partners, authorised real cases, reviewers, ground truth, pentest, legal/privacy review, accessibility participants, signing evidence or company-validated value.
- Never inspect, tune against or contaminate BLIND/HOLDOUT material before the protocol permits it.
- Any public corpus inspected by development agents is `NOT_BLIND` and cannot silently become E1 BLIND/HOLDOUT evidence.

## Current qualification streams

Use `#136` for the detailed current checklist.

- **A — technical candidate:** current provenance slice, complete P1 provenance matrix, same-SHA qualification, repository enforcement (`#133`).
- **B — scientific E1:** `#132` + `#19`, P1 scope, pool segregation, calibration, freeze, blind evaluation and holdout.
- **C — final qualification preparation/evidence:** `#20`, `#21`, `#32`, `#94`, `#134`, `#135` and related release/recovery/handoff work.
- **D — Evidence Factory:** `#140`, public/authorised Procurement source discovery, linked-practice reconstruction, deduplicated manifests/hashes and coverage mapping. This stream supplies stress/regression/pre-calibration material only unless a future protocol explicitly says otherwise.
- **E — Qualification Breaker:** `#141`, adversarial/differential attempts to disprove readiness, reproduce blockers and hand them to the owning stream without opening competing fixes.

## Session bootstrap

Before changing anything:

1. Read this file.
2. Run `python scripts/agent_status.py` when shell access is available. If shell access is unavailable, reproduce the same checks directly against GitHub.
3. Inspect the exact PR/issue/workflow state for the object you intend to touch.
4. Check active leases. An unleased object is **not automatically safe**; dependency and qualification rules still apply.
5. Claim the smallest coherent work item before modifying shared B/C/D/E work when lease tooling is available.
6. Re-check the live head SHA immediately before a write, merge, matrix promotion or qualification decision.

## Work leases

Work leases are coordination hints stored on the GitHub Agent Lease Board as append-only comments. They are not repository locks and they are not qualification evidence.

- Default lease TTL is intentionally short and expires automatically.
- A lease owned by another agent means: choose another independent task unless there is explicit evidence the lease is obsolete.
- A same-owner claim renews the lease.
- Release the lease when work finishes normally.
- If a session dies, the lease expires by time; no manual cleanup is required.
- Never use a lease to override GitHub branch protection, checks, review requirements or #136 dependencies.

When the coordination PR that introduced this file is merged, use:

```text
python scripts/agent_status.py
python scripts/agent_status.py claim --item issue:135 --owner qualification-c
python scripts/agent_status.py release --item issue:135 --owner qualification-c
```

`GITHUB_TOKEN` is required for claim/release. Read-only status works against this public repository without a token, subject to GitHub rate limits.

## Concurrency rule

Do not open or modify concurrent branches/PRs for the same coherent work item. Before entering B, C, D or E, check whether another agent has produced a branch, PR, commit or active lease on that same object recently. If so, leave that object alone and choose independent work.

The current technical provenance slice owned by the main operational agent must not be duplicated by the qualification-preparation agent. Evidence Factory does not own product fixes. Qualification Breaker should prefer a minimal reproducer/finding report and hand confirmed defects to the owning stream rather than creating a competing implementation.

## Checkpoints

Never infer these checkpoints only from a dashboard label:

- **FINE A:** must be verified against every condition in `#136`, including same-final-SHA gates and real enforcement required by `#133`.
- **FREEZE E1:** requires the real preconditions in `#132`/`#19`, including authorised segregated pools, actual calibration, reviewer evidence and an immutable manifest for the exact candidate.
- **Qualified:** requires the complete bounded release evidence named in `#136`.

If live GitHub state conflicts with this file or with `agent_status.py`, stop using the stale information and trust the live GitHub state.