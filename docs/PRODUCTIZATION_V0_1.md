# ThisTinti Productization v0.1

Status: **DRAFT / PRE-QUALIFICATION / NOT MARKET VALIDATION**

This document translates the existing Procurement P1/E1 work into a conservative company-facing package. It does not add product features, modify qualification scope, constitute legal review, establish product-market fit, or turn synthetic/public `NOT_BLIND` material into E1 BLIND/HOLDOUT evidence.

## 1. Working positioning

Preferred wording while #135 remains externally unreviewed:

> **Controllo documentale Procurement verificabile, a supporto della revisione umana.**

The product proposition is not autonomous accounting, automatic recovery, or an ERP replacement. The useful unit is a **reviewable practice**: documents are connected into an operation chain, machine observations become FACT/FINDING records with provenance, and a human records the final judgment against exact-current support.

### Evidence labels used in this document

- **FACT** — supported by current repository behavior, qualification artifacts, or inspected public material.
- **INFERENCE** — reasonable product interpretation of those facts, not independently validated with customers.
- **HYPOTHESIS** — proposition to test in customer discovery; never present as established demand, ROI, pricing, or market evidence.

## 2. Operational ICP v0.1

### Core fit signals

**FACT**
- ThisTinti is currently being qualified around Procurement document chains and six bounded P1 rules: `duplicate_document_number`, `currency_mismatch`, `delivered_over_order`, `invoiced_over_received`, `payment_over_invoice`, and `payment_without_invoice`.
- The architecture preserves a DOCUMENT -> FACT -> FINDING -> human JUDGMENT boundary and treats unsupported/degraded evidence fail-closed.
- Existing tooling supports local/self-hosted operation and explicit evidence/provenance handling.
- Public `NOT_BLIND` research already demonstrates that real procurement evidence can be fragmented across purchase-order references, invoice identifiers, payment records, approval packets, receiving/acceptance forms and PDF/document archives. Public sources are development/stress inputs only, not evidence of customer demand.

**INFERENCE**
The strongest early-fit organization is likely not defined primarily by industry or headcount. It is an organization where a meaningful number of procurement practices require manual reconciliation across multiple document sources and where reviewers need to explain **why** a discrepancy was surfaced.

Useful ICP signals to test:
- recurring purchase/receipt/invoice/payment reconciliation workload;
- ERP data plus PDFs, e-mail attachments, shared folders or exported files rather than one perfectly normalized source;
- manual spot checks or spreadsheet-based matching still present;
- audit, internal-control, procurement or finance reviewers who need readable supporting evidence;
- tolerance for a supervised/local processing model rather than a fully autonomous cloud workflow;
- enough repeated practices that reducing review time or missed exceptions could matter economically.

**HYPOTHESIS**
Initial discovery should prioritize teams with approximately hundreds to thousands of relevant practices per month over very low-volume environments, because the assisted-service model needs enough repetition to justify setup while remaining small enough for controlled onboarding. This range is intentionally unvalidated.

### Weak-fit / exclusion signals

**INFERENCE**
Early fit is weak where all relevant evidence is already normalized and reconciled inside a mature ERP process with little manual review, or where the buyer expects fully autonomous posting/payment decisions, universal OCR coverage, or guaranteed financial recovery.

## 3. Buying group hypotheses

These roles are intentionally separated because the economic buyer and day-to-day reviewer may differ.

- **Buyer — HYPOTHESIS:** Head of Procurement, Finance Operations leader, CFO/controller in a smaller organization, or Internal Controls leader. Motive to test: lower review effort, improve exception traceability, or standardize evidence.
- **User — HYPOTHESIS:** procurement analyst, AP specialist, finance operations analyst, internal-control reviewer, auditor or back-office operator who currently opens documents and reconciles records manually.
- **Influencer — HYPOTHESIS:** IT/security, DPO/privacy, internal audit, ERP owner, compliance, legal or external auditor. Motive: data boundary, evidence quality, deployment constraints, auditability.
- **Blocker — HYPOTHESIS:** security/privacy concerns, unclear data authorization, fear of replacing ERP controls, poor source-document quality, unsupported parser paths, lack of internal owner, or a demand for claims beyond qualified scope.

Discovery should record each role separately rather than treating one enthusiastic user as evidence of budget authority.

## 4. Problem and current alternatives

### Problem statement

**INFERENCE**
A practical problem to test is: procurement reviewers may have to reconstruct one business event from records spread across ERP exports, PDFs, e-mails and folders, then determine whether quantities, amounts, currencies and document relationships are coherent. The costly part is not only detecting a mismatch; it is finding and preserving the evidence required to review it.

### Current alternatives

| Alternative | What it does well | Where ThisTinti may complement it | Claim boundary |
|---|---|---|---|
| ERP suites such as SAP / Oracle / Coupa | transaction system, master data, workflow and approvals | examine/export a bounded practice and preserve reviewable evidence across heterogeneous documents | **HYPOTHESIS:** complement, not replace |
| Excel / manual reconciliation | flexible, familiar, low setup cost | structured repeatability, provenance and reusable review trail | no claim that automation is always faster |
| RPA / document intelligence | extraction and workflow automation | downstream evidence-aware controls and human judgment boundary | no claim of superior OCR/AI |
| Internal/external reviewers | contextual interpretation and accountability | pre-organize evidence and candidate exceptions for their review | humans remain authoritative for judgment |
| Do nothing | zero change cost | potential benefit only if current review burden or missed exceptions is meaningful | ROI must be measured, not assumed |

**FACT:** no current qualification artifact establishes superiority over SAP, Oracle, Coupa, Excel, RPA, document-intelligence vendors or human reviewers. Any comparison above is positioning structure for discovery, not benchmark evidence.

## 5. Initial offer: assisted Procurement review pilot

**HYPOTHESIS**
The safest initial commercial shape is an **assisted service**, not a self-serve autonomous product:

1. agree a bounded Procurement practice and supported document paths;
2. verify authorization/data-handling conditions;
3. configure the existing Practice Model / Company Profile as applicable without changing P1 claims;
4. process a limited set of authorized practices;
5. present findings with supporting evidence to company reviewers;
6. record human judgments and failure classes;
7. report measured review effort, confirmed anomalies and limitations separately;
8. only discuss expansion after the evidence package is reviewed.

This offer should not promise automatic recovery, accounting action, universal accuracy, or qualification outside P1.

## 6. Five-minute guided demo storyboard

Use only existing capabilities and synthetic or approved public `NOT_BLIND` material. The demo is **not** a blind test.

### 0:00-0:40 — The practice
Show a small synthetic/public Procurement practice with an order, receiving evidence, invoice and/or payment records. State explicitly that demo material is synthetic/public and `NOT_BLIND`.

### 0:40-1:30 — Document chain
Show how the records are linked into one operation/practice. Explain that the goal is not a generic chat answer but a reproducible evidence chain.

### 1:30-2:30 — Finding
Open one currently supported P1 example, preferably a simple amount/absence/duplicate case whose behavior exists in the current build. Show the finding without inventing a customer outcome.

### 2:30-3:30 — Provenance
Show the exact supporting document/field context and explain freshness: if supporting evidence changes, old support must not silently remain current.

### 3:30-4:20 — Human judgment
Show the reviewer boundary: the system surfaces evidence; a person records the judgment. Emphasize that ThisTinti does not autonomously approve payment or assert recoverable value.

### 4:20-5:00 — Pilot handoff
Show the existing E1-derived workflow: authorization/anonymization, bounded scope, evidence record, review, metrics and limitations. End with the proposed assisted pilot rather than a broad product promise.

If a desired demo step requires a feature not already present, mark it `POST-QUALIFICATION HYPOTHESIS` and do not implement it for the demo.

## 7. Company pilot kit — derivation map

Do not recreate a second methodology. The company-facing kit should be a thin wrapper around existing qualification artifacts.

| Company-facing item | Reuse source | Purpose |
|---|---|---|
| Pilot scope one-pager | #136 + #132 P1/E1 perimeter | what is / is not under test |
| Data authorization & anonymization checklist | existing real-pilot governance/tooling + #132 schema | ensure only permitted cases enter the pilot |
| Case inventory & hash record | existing pilot dataset tooling | immutable case identity and reproducibility |
| Reviewer instructions | #132/#19 reviewer and adjudication protocol | independent reference before product exposure |
| Result sheet | #19 metrics model | FP/FN, degraded/abstention, provenance correctness, failure class |
| Economic result sheet | #19 three-level separation | potential exposure vs reviewer-confirmed anomaly vs company-validated recoverable/avoided value |
| Security/privacy handoff | #134/#135 preparation | route independent review; never substitute it |
| Human operability/accessibility record | #32/#94 shared campaign | record real-user observations on applicable candidate |
| Final evidence index | E1 manifest/release evidence artifacts | bind results to exact candidate and limitations |

A pilot customer should receive one coherent package, not the repository's internal qualification vocabulary without translation.

## 8. ROI / pricing calculator v0.1

All input values are **HYPOTHETICAL USER-SUPPLIED ASSUMPTIONS** until measured with a real organization.

### Inputs

- `N` = relevant practices reviewed per month
- `T0` = current average manual review minutes per practice
- `T1` = average assisted review minutes per practice during pilot
- `C` = fully loaded reviewer cost per hour
- `S` = one-time setup/onboarding cost
- `F` = recurring monthly service/software fee
- `V` = company-validated monthly avoided/recoverable value attributable under an agreed method

### Formulas

`hours_saved = N * max(T0 - T1, 0) / 60`

`labor_value = hours_saved * C`

`validated_monthly_benefit = labor_value + V`

`monthly_net_benefit = validated_monthly_benefit - F`

`first_period_net_benefit = validated_monthly_benefit - F - S`

`payback_months = S / monthly_net_benefit` only when `monthly_net_benefit > 0`

### Guardrails

- Do not populate `V` from raw system findings.
- Do not count `potential exposure` as recovered money.
- Use measured `T0/T1` where possible; otherwise label them **HYPOTHETICAL**.
- Pricing should initially be tested as a range or pilot fee, not justified by invented willingness-to-pay data.

**HYPOTHESIS:** a practical early pricing experiment could separate a fixed assisted-pilot fee from a later recurring fee, because setup/review effort is front-loaded. No amount is recommended here because no willingness-to-pay evidence exists yet.

## 9. Discovery questions that can falsify the ICP

The first interviews should try to disprove the positioning, not confirm it:

1. Walk through the last procurement mismatch or manual reconciliation you actually handled. Where did the evidence live?
2. How many relevant practices are reviewed in a normal month, and which are sampled versus exhaustively checked?
3. Who performs the work and how long does a representative case take?
4. What already catches duplicate numbers, quantity mismatches, amount mismatches or missing invoice/payment relationships?
5. When an exception is found, what evidence must be shown before someone acts?
6. Which errors are expensive enough to matter, and which are merely annoying?
7. Would local/self-hosted/supervised processing solve a real constraint or add friction?
8. Who would have to approve a pilot: procurement, finance, IT/security, privacy/legal, internal audit?
9. What would make a pilot a failure even if the software detects some valid anomalies?
10. What outcome would justify paying, and how would the company validate that outcome independently?

A material negative result — for example, target teams already have reliable native three-way matching and very little manual evidence reconstruction — should narrow or change the ICP rather than being explained away.

## 10. Claim-safe messaging

### Preferred

> ThisTinti organizza una pratica Procurement come oggetto verificabile: collega documenti, segnala controlli supportati da evidenza e mantiene il giudizio finale in mano al revisore.

> Stiamo qualificando un perimetro P1 limitato e misurabile. Il pilot serve a verificare, con casi autorizzati e revisori reali, dove riduce lavoro manuale e dove invece deve astenersi o richiedere revisione.

### Avoid until independently supported

- "recupera automaticamente denaro";
- "elimina gli errori Procurement";
- "sostituisce SAP/Oracle/Coupa";
- "AI che approva fatture/pagamenti";
- "accuratezza 100%" based on synthetic/public corpora;
- "Qualified" as a broad product-wide claim before #136 closes;
- any assertion that public `NOT_BLIND` corpus results represent customer or market validation.

## 11. Post-qualification hypotheses, not implementation tasks

Potential future ideas may be recorded here but must not alter the qualification candidate merely to improve the demo:

- connectors/import helpers for common ERP/DMS exports;
- guided company-profile setup;
- buyer-facing aggregate dashboards;
- additional rules outside P1;
- more acquisition/parser paths;
- workflow integrations for routing reviewed findings.

Each requires separate discovery and validation after the current qualification critical path.

## 12. Exit condition for Productization v0.1

This draft is sufficient for the next customer-discovery phase when:

- the company-facing proposition remains bounded to existing capabilities;
- every market/economic assumption is visibly distinguished from repository facts;
- the demo can be executed without a new feature;
- the pilot kit points to existing E1 artifacts rather than inventing a second protocol;
- pricing/ROI uses formulas and customer-supplied/measured inputs rather than fabricated benchmarks;
- any final public wording is rechecked after the independent #135 claims/legal/trademark review.

Productization v0.1 is **not** evidence that these hypotheses are correct. Its purpose is to make them testable.