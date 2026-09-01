# Qualification performance and capacity runbook — RELEASE 1.0.0

Status: `PREPARATION_ONLY_NOT_EXECUTED / NOT_A_PASS`

This runbook prepares the measured performance/capacity campaign required by #166 and #136. It does not claim any performance result until the procedure is executed on the exact applicable candidate and the recorded evidence is reviewed.

## Scope and evidence boundary

The campaign is limited to the bounded `ThisTinti 1.0 Qualified — Procurement v1 — P1 — E1` claim. Inputs MUST be synthetic, public `NOT_BLIND`, or otherwise explicitly authorised. E1 BLIND/HOLDOUT material MUST NOT be opened, copied, profiled or used for load generation.

Every result must name the full 40-hex source SHA, release/artifact identity, edition, OS, hardware, storage type, database configuration, Python/runtime versions where applicable, and qualification configuration. Results from another SHA or materially different deployment are supporting evidence only.

Hard product limits and merely tested limits must be recorded separately. A successful test at N documents does not establish a supported maximum of N, and results must not be extrapolated across orders of magnitude or from Local to Self-Hosted.

## Workload contract

Prepare one immutable workload manifest containing only non-BLIND material and record hashes for every input. The representative workload should exercise all six P1 controls where feasible and include realistic multi-document shapes such as multiple deliveries for one invoice, multiple invoices for one payment, partial deliveries/payments and ambiguous/degraded inputs when already supported by the frozen P1 scope.

Use at least three bounded workload sizes: `small`, `representative`, and `stress`. Their exact document/practice counts are recorded before execution and MUST NOT be silently changed after observing results. `stress` is deliberately beyond the normal representative workload and is used to observe degradation/failure behaviour, not to create a marketing claim.

## Measurement sequence

For each applicable edition/candidate:

1. Record machine/environment identity and exact candidate/artifact hashes.
2. Measure installer/package size and post-install disk footprint before loading test data.
3. Start the system with an empty dataset; after steady state, record idle RAM and CPU over a fixed observation window.
4. Execute each workload size from a clean, documented starting state.
5. Record per-practice latency plus batch elapsed time and throughput. Capture enough repetitions to report median and at least one dispersion indicator (for example p95 or min/max range); do not report a single best run.
6. Record peak and steady RAM/CPU during ingestion/analysis, together with any queue/backpressure, timeout, retry, abstention, degraded acquisition or failure state.
7. Measure storage growth after each workload, separating where practical database, canonical evidence/original content, logs, quarantine/temp and backup material.
8. Execute a verified backup of the representative populated dataset and record duration plus artifact size/hash.
9. Restore/reconstruct that dataset using the documented recovery path and record elapsed time. Cross-reference #168 rather than substituting a benchmark-only restore for its clean-machine evidence.
10. Execute the stress workload and record whether the system remains correct, becomes slow/degraded, rejects work fail-closed, or fails. Never convert a crash/timeout into a passing capacity claim.

## Canonical evidence snapshot accounting

The current 1.0 baseline stores canonical document evidence in `document_evidence_snapshots`. Capacity evidence must therefore include this storage surface explicitly rather than treating database growth as metadata-only. Record the contribution of canonical evidence bytes to database/backup growth and ensure backup/restore timings include them where the official recovery path does.

Integrity/hash controls are not confidentiality controls; this runbook measures resource/operability behaviour only. Data-protection conclusions belong to #167.

## Required raw observations

For each run preserve, at minimum:

- exact source SHA and artifact/checksum identity;
- workload manifest hash and workload size;
- start/end UTC timestamps;
- machine CPU model/core count, RAM, OS/build, disk/storage type and free space before run;
- edition/deployment topology and database version/configuration;
- idle CPU/RAM window;
- peak CPU/RAM and steady-state CPU/RAM during workload;
- per-practice latency observations and batch elapsed time/throughput;
- pre/post storage footprint by available category;
- observed hard rejection/size limits and configured limits;
- timeout, queue/backpressure, retry, degraded/abstain/fail-closed behaviour;
- verified backup duration, size and digest;
- restore/reconstruction duration and verification outcome;
- operator notes for anomalies or manual intervention.

## Result classification

Each measurement family is one of:

- `MEASURED`: raw evidence exists and is tied to the exact candidate/environment;
- `GAP`: required observation could not be collected or is not reproducible;
- `NOT_APPLICABLE`: justified by the bounded edition/scope;
- `BLOCKED`: a resource/performance defect makes the intended operating envelope unsafe or materially unusable.

`PREPARED`, `SCRIPTED`, `CI_GREEN`, or a historical benchmark are never synonyms for `MEASURED`.

## Claim discipline

The final customer-facing envelope may state only what the evidence directly supports, for example a tested workload range on a named hardware profile. Avoid words such as "unlimited", "enterprise scale", "handles millions", "real-time" or cross-edition equivalence unless separately measured and approved.

If the normal workload becomes materially slower or unstable before the intended envelope, reduce the declared operating envelope or remediate and rerun. If stress exceeds a product-enforced limit, record the exact fail-closed behaviour and distinguish that hard limit from resource exhaustion.

## Exit checklist for #166

#166 remains open until all of the following are true on the applicable exact candidate:

- a frozen non-BLIND workload manifest exists;
- Local and Self-Hosted are measured separately where architecture materially differs, otherwise the unmeasured edition is explicitly marked unqualified;
- installer/post-install footprint, idle and workload CPU/RAM, latency, throughput and storage growth are measured;
- hard limits are distinguished from tested limits;
- one controlled stress point is exercised and degradation/failure behaviour recorded;
- representative backup size/duration and restore duration are measured against the official recovery path;
- raw observations and derived summaries are traceable to the exact SHA/artifacts/environment;
- published requirements/recommendations do not exceed the measured envelope;
- no unresolved resource/performance blocker remains for the bounded P1/E1 release claim.

Until execution completes, this document remains preparation evidence only.