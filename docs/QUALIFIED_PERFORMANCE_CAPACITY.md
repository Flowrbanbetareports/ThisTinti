# RELEASE 1.0.0 performance and capacity qualification

Status: **PREPARATION ONLY — NOT EXECUTED — NOT A QUALIFICATION PASS**

This runbook prepares the operational evidence required by #166 and #136. It does not publish a universal benchmark, does not infer production scale from CI, and does not convert development load tests into evidence for the final Qualified candidate.

## 1. Claim boundary

A performance/capacity statement is valid only for the exact tuple recorded in the evidence manifest:

- source SHA and release/artifact identity;
- edition (`local` or `self-hosted`);
- OS, CPU, RAM, disk and relevant runtime configuration;
- workload identity and data classification;
- product hard limits actually enforced;
- measured operating point and controlled stress point;
- repetition count and raw result references.

Changing the candidate, storage architecture, edition, material runtime settings or workload semantics invalidates automatic carry-over.

## 2. Allowed workload material

Use only synthetic, public `NOT_BLIND`, or otherwise authorised material that is explicitly outside E1 BLIND/HOLDOUT. Public corpus material from #140 remains `NOT_BLIND` and may be used for repeatable stress/pre-qualification only.

Never inspect, copy, hash into this package, or use BLIND/HOLDOUT cases for capacity preparation.

## 3. Reuse existing probes

This qualification lane reuses `scripts/beta_load_probe.py` for bounded HTTP latency/throughput observations. That probe is development instrumentation; its thresholds are not customer requirements and its output is not a final PASS by itself.

`scripts/qualification_capacity_probe.py` aggregates exact-candidate evidence and fails closed in `--final` mode when required identity, repetitions or measurement families are absent. It does not generate missing evidence.

## 4. Required measurement campaign

Run the applicable campaign on the exact candidate and intended release environment.

### Identity and installation

Record source SHA, artifact SHA-256, artifact size, installed footprint and edition. For Windows Local Edition, use the actual signed/final installer candidate when available; do not substitute a source checkout for installer footprint.

### Idle envelope

After a documented steady-state interval, capture idle RAM and CPU with the service/application started but no active workload. Record the measurement tool and sampling window.

### Representative workload

Use a versioned workload definition and at least three repetitions. Record:

- practice/document count and byte volume;
- latency distribution, including median and p95 where meaningful;
- bounded throughput;
- peak and steady RAM/CPU;
- errors, timeouts and rejected inputs;
- storage growth split, where practical, into originals, database, logs/quarantine and backup.

Do not report only the fastest run.

### Supported operating point and stress point

Exercise the proposed supported operating point, then at least one controlled point beyond the normal workload. A stress run is evidence about degradation/failure behaviour, not proof that the stress point is supported.

Record backpressure, queueing, timeout, memory pressure, disk pressure, corruption protection or fail-closed behaviour observed.

### Backup/recovery coupling

Reuse #21/#168 methodology. On a representative populated dataset record backup duration, verified package size and restore/reconstruction duration. Do not claim portability merely from backup timing.

## 5. Hard limits versus tested limits

Every limit in the final report must be classified as one of:

- `HARD_ENFORCED`: product code/configuration rejects values beyond this boundary;
- `TESTED_ONLY`: campaign exercised this value successfully, but the product does not enforce it as a maximum;
- `UNQUALIFIED`: not measured for the named candidate/environment.

Never turn a `TESTED_ONLY` value into a product maximum or extrapolate beyond it.

## 6. Local versus Self-Hosted

If Local and Self-Hosted materially differ in process model, database, storage, deployment or hardware control, maintain separate evidence records. Evidence from one edition must not silently qualify the other.

## 7. Fail-closed finalisation

The template `docs/templates/qualified-performance-capacity-evidence.v0.1.json` starts as `PREPARATION_ONLY_NOT_EXECUTED` / `NOT_A_PASS`.

A final evidence record may move to an executed state only after real measurements exist. `scripts/qualification_capacity_probe.py --final` is a structural validator/aggregator, not a scientific oracle. It rejects missing candidate identity, missing workload identity, fewer than three representative repetitions, absent resource observations, absent storage observations, absent backup/restore measurements, absent stress observations, or unresolved release-blocking defects.

A structurally complete file still requires human review against #166/#136 and the exact release candidate.

## 8. Minimum report table

The final report should expose, without marketing extrapolation:

| Family | Minimum output |
| --- | --- |
| Candidate | source SHA, artifact SHA-256, edition, version |
| Environment | OS, CPU, RAM, disk, runtime/config |
| Install | artifact bytes, installed footprint |
| Idle | CPU/RAM sampling window and range |
| Representative | repetitions, latency p50/p95/range, throughput, CPU/RAM, errors |
| Storage | originals, DB, logs/quarantine, backup where applicable |
| Limits | hard-enforced vs tested-only |
| Stress | workload point, degradation/failure mode |
| Recovery | backup duration/size, restore duration |
| Residual risk | unresolved defects/limitations and owner |

## 9. Acceptance boundary

This preparation can be merged before the final candidate because it does not assert measured values. #166 itself remains open until the exact release candidate has real, repeatable measurements and any incompatible performance/resource defect is resolved or explicitly removes the affected claim from RELEASE 1.0.0.
