# APX Evidence Freshness Forensic Audit

Status: AUDIT COMPLETE (read-only; no code/corpus/benchmark/schema/test modified)
Date: 2026-08-18
Scope: AUDIT ONLY — no code, corpus, benchmark, schema, or test modifications.
Authoritative artifacts (DO NOT MODIFY): `docs/APX_IMPLEMENTATION_AUDIT.md`,
`apx/evaluation/results/phase5_dev_seed42_20260818_090830.json`,
`apx/evaluation/results/phase5_dev_seed42_20260818_090830.txt`.

---

## 1. Executive Summary

The evidence corpus is stale because the pipeline contains **three independent, mutually
inconsistent date anchors**, and the one that decides run-time evidence validity is the
**wall clock**:

1. **Corpus generation** (`apx/evidence/generate_evidence.py`) anchors every
   `effective_from`/`effective_until` window to **fixed absolute calendar dates**
   (2023–2025 for the real evidence, 2020–2021 for the deliberately-irrelevant set,
   2022 for the deliberately-stale set). The generator never calls `date.today()` and
   writes **no `generated_at`/`created_at` field** into the corpus. The corpus is
   therefore frozen in time: it decays automatically as the wall clock advances.
2. **Eval-label generation + standalone Phase 2 eval tool** pin `reference_date` to a
   **hardcoded `date(2025, 12, 1)`** (`populate_eval_labels.py:212`, `evaluate.py:88`).
   Ground-truth `relevant_evidence_ids` were baked assuming evidence valid on 2025-12-01.
3. **End-to-end benchmark** (`apx/evaluation/benchmark.py:101`) constructs
   `HybridContextEngine()` with **no `reference_date`**, so
   `EvidenceValidator.__init__` falls back to **`date.today()`** (`validity.py:13`),
   which at run time was **2026-08-18**.

On 2026-08-18 exactly **204 / 235 (86.8%)** corpus items are expired; only **31** are
within their validity window and **30** pass the full validator. The benchmark also runs on
**2026-dated synthetic invoices** (`generate_synthetic.py:133,203`; PO dates 2026-01-01..
2026-06-30, invoice dates 2026-01-01..2026-08-29). Because `evidence_validity_enabled:
true` for the DEV profile (`retrieval_profiles.yaml:13`) and downstream phases consume only
`EvidenceSet.validated_evidence` (see `PHASE3_REPORT.md:137`), the near-empty valid
evidence starves detection/investigation/decision/action — the direct driver of the Phase 5
failures (Detection F1 0.27, Automation 0.02, risk/action accuracy ~0.02).

The retrieval-metric failure (Recall@5 0.16) is **NOT** a freshness symptom: the
benchmark's retrieval evaluator scores the unfiltered `EvidenceSet.candidates`
(`retrieval_eval.py:47`), which are unaffected by `reference_date`. That is a separate
retrieval-quality problem.

Recommended single fix strategy (NOT implemented): **drive the entire evidence pipeline
from one explicit, shared reference date** — anchor generator windows to it, pass it
explicitly to `HybridContextEngine` in the benchmark (instead of the `date.today()`
default), and regenerate corpus + labels from it.

## 2. Evidence Generation Audit

Source: `apx/evidence/generate_evidence.py` (359 lines, `seed=42`, class
`EvidenceGenerator`).

- **No time-awareness.** The generator contains **no** `date.today()`,
  `datetime.now()`, `as_of`, or `reference` usage. Every effective window is a
  hardcoded absolute range (verified by regex over the source):
  - `generate_historical_resolutions` (lines 36–89): `effective_from` in
    `date(2024,1,1)..date(2025,12,31)`; `effective_until = effective_from +
    randint(30,365)` days. So the latest possible window is
    `2025-12-31..2026-12-31`; typical windows expire during 2025.
  - `generate_vendor_policies` (lines 106–163): from `date(2024,1,1)..date(2025,6,30)`,
    until +`randint(180,730)` days (max `2027-06-30`).
  - `generate_contracts` (lines 164–211): from `date(2023,1,1)..date(2025,12,31)`,
    until +`randint(365,1095)` days (max `2028-12-31`).
  - `generate_payment_terms` (lines 212–260): from `date(2024,1,1)..date(2025,6,30)`,
    until +`randint(180,365)` days (max `2026-06-30`).
  - `generate_irrelevant_evidence` (lines 261–282): fixed `2020-01-01..2021-12-31`.
  - `generate_stale_evidence` (lines 283–304): fixed `2022-01-01..2022-12-31`.
- **Counts** (`generate_all`, lines 305–323): historical 100, vendor policies 50,
  contracts 30, payment terms 20, irrelevant 20, stale 15 → **235 items**.
- **Schema has no generation timestamp.** `Evidence` (schemas.py) has
  `effective_from`/`effective_until` (both required `date`) but **no** `created_at` /
  `generated_at`. Verified at run time: `model_dump(mode="json")` of a corpus item
  contains no `created_at` key.
- **Serialization round-trips correctly.** `save()` writes
  `json.dump(data, ..., default=str)` (`generate_evidence.py:334`); retrievers parse
  date strings back with `date.fromisoformat` (`bm25.py:20-21`, `dense.py:20-21`).
  Round-trip verified: `'2024-10-08'` ↔ `date(2024,10,8)`.

**Finding:** generation is anchored to a fixed 2023–2025 calendar with no run-time
or as-of reference and no timestamp; the corpus is a time-frozen snapshot that decays
with the wall clock.

## 3. Current Corpus Statistics

Source: `apx/data/datasets/evidence/evidence_corpus.json` (235 items, 166185 bytes,
mtime Aug 14 2026). Read-only analysis, reference `date.today() = 2026-08-18`.

| Metric | Value |
|---|---|
| Total items | 235 |
| Within validity window (from ≤ today ≤ until) | **31** |
| Expired (until < today) | **204 (86.8%)** |
| Future-dated (from > today) | 0 |
| Invalid ranges (from > until) | 0 |
| Missing from / missing until | 0 / 0 |

`effective_from` by year: {2020: 20, 2022: 15, 2023: 7, 2024: 98, 2025: 95}.
`effective_until` by year: {2021: 20, 2022: 15, 2024: 25, 2025: 98, 2026: 64, 2027: 7,
2028: 6}. Only the 2026–2028-until items (77 total) can still be valid today; of those,
only 31 have `until ≥ 2026-08-18` AND a `from ≤ 2026-08-18`.

Full `EvidenceValidator` (default reference, no vendor filter): **204 STALE, 30 VALID,
1 INVALID_OUTCOME** (a REJECTED historical resolution still within window).

Valid-evidence decay for the 10 eval vendors (validator with per-case `invoice_vendor_id`):

| Reference date | corpus-valid | per-eval-vendor valid |
|---|---|---|
| 2025-12-01 (label date) | 81 | [1,6,7,6,2,2,1,1,5,5] |
| 2026-03-15 (early invoice) | 52 | [1,3,4,4,2,1,1,1,3,5] |
| 2026-06-30 (late invoice) | 36 | [0,0,4,4,1,0,1,1,0,2] |
| 2026-08-29 (max invoice date) | 29 | [0,0,4,2,1,0,1,1,0,2] |
| 2026-08-18 (benchmark run) | 30 | [0,0,4,2,1,0,1,1,0,2] |

At benchmark run time **6 of 10 eval vendors have 0 valid evidence**; GT-relevant-now-valid
drops to 0 for EVAL-001/002/005/006/009 and to 1 for EVAL-010.

## 4. Reference Date Trace

Every `reference_date` touch-point in the codebase:

| Location | Value at run time | Effect |
|---|---|---|
| `validity.py:12-13` | `reference_date or date.today()` | Default = wall clock (2026-08-18) |
| `validity.py:16-18` | — | `set_reference_date` override (tests only) |
| `engine.py:36,51-53,71` | passed through to `EvidenceValidator` | string or `date` accepted; default None |
| `engine.py:186` `create_hybrid_context_engine` | no reference | date.today() |
| `benchmark.py:101` `HybridContextEngine()` | **no reference_date** | **date.today() = 2026-08-18** |
| `evaluate.py:88` `reference_date=date(2025,12,1)` | hardcoded | standalone Phase 2 tool |
| `populate_eval_labels.py:212` `date(2025,12,1)` | hardcoded | ground-truth labels baked at 2025-12-01 |
| `test_phase2_evidence.py:65,237,258` | fixed test dates | unit coverage |

Only the benchmark omits a reference date; everything else in the "eval" world pins
2025-12-01. This is the central inconsistency.

## 5. Date Semantics

There are **four different time frames** in play, none of which are reconciled:

1. **Evidence windows**: absolute 2020–2028, bulk 2024–2025 (generator).
2. **Eval-label reference**: `2025-12-01` (`populate_eval_labels.py:212`).
3. **Benchmark invoice period**: PO 2026-01-01..2026-06-30, invoice 2026-01-01..2026-08-29,
   due +15..90d (`generate_synthetic.py:133,167,203-204`).
4. **Runtime wall clock**: `date.today()` = 2026-08-18 (`validity.py:13`).

The intended semantic — "evidence that is current at the time the invoice is processed" —
is **not implemented anywhere**: no component computes `reference_date` from the invoice
date; the benchmark validates against the wall clock, which is unrelated to any business
date. No spec document defines the as-of date for run-time validation (see §10), so this
is partly a **SPECIFICATION AMBIGUITY** — but the concrete bug is the wall-clock default
being used in a benchmark that runs against 2026 invoices with 2024–2025-anchored evidence.

## 6. EvidenceValidator Audit

Source: `apx/evidence/validity.py` (86 lines).

- **Default reference**: `self.reference_date = reference_date or date.today()`
  (`validity.py:13`). This is the only place the wall clock enters validation.
- **Date window check** (`validity.py:25-30`): invalid if `effective_from > reference_date`
  (not yet effective) or `effective_until < reference_date` (expired). Boundaries are
  **inclusive**: evidence valid when `from ≤ reference ≤ until`.
- **Vendor match** (`validity.py:33-36`): only enforced when **both**
  `invoice_vendor_id` and `evidence.vendor_id` are present; a vendor-less evidence passes.
- **Policy version** (`validity.py:39-41`): invalid only for `v0.` prefixes; generator
  emits `v1.0`–`v5.9`, so this never fires on the current corpus.
- **Outcome** (`validity.py:44-47`): REJECTED/EXPIRED/FAILED/INVALID → invalid. Generator
  emits ~1/6 historical resolutions with `REJECTED`; policies/contracts/terms use `ACTIVE`.
- **Source authority** (`validity.py:50-52`): EXTERNAL is flagged in `reasons` but does
  **not** invalidate.
- **Scope** (`validity.py:55-57`): `irrelevant`/`stale_test` → invalid.
- **Status precedence** (`validity.py:60-71`): STALE (date-based) > VENDOR_MISMATCH >
  INVALID_OUTCOME > OUT_OF_SCOPE > INVALID.
- **Behavior is correct** for every rule individually; the problem is purely **which
  `reference_date` is supplied** (see §4/§8).

## 7. Retrieval Integration Audit

Source: `apx/evidence/engine.py`, `bm25.py`, `dense.py`, `retrieval_eval.py`.

- `HybridContextEngine.retrieve` (engine.py:87-183): BM25 (top 50) + dense (top 50) →
  RRF (k=60, c=60) → rerank (top 20) → validity filter → `EvidenceSet`.
- **Candidates are never validity-filtered** (`engine.py:169`:
  `candidates=reranked_candidates`); the filter only populates `validated_evidence`
  (`engine.py:110-138`).
- **Retrieval evaluation is validity-independent**: `retrieval_eval.py:47` reads
  `evidence_set.candidates`; Recall@5/10, MRR, nDCG and `valid_evidence_rate` are computed
  over candidates, not `validated_evidence`. Therefore the benchmark's
  **Recall@5 = 0.16 is NOT caused by the stale corpus** — it is a genuine retrieval-quality
  gap (the labeled-relevant evidence is not ranked in top-5). Downstream phases, however,
  consume `validated_evidence` only (`PHASE3_REPORT.md:137`), so freshness starvation hits
  detection/investigation/decision/action directly.
- **Index caches are consistent**: BM25/dense caches record `evidence_ids` and are
  discarded on mismatch (`bm25.py:84-90`, `dense.py:105-113`); no stale-index path found.
- **Serialization**: `_parse_evidence_data` restores dates/enums identically in both
  retrievers (`bm25.py:15-30`, `dense.py:16-31`). No defect.

## 8. Benchmark Date Audit

Source: `apx/evaluation/benchmark.py`.

- `benchmark.py:101`: `self.evidence_engine = HybridContextEngine()` — **no
  `reference_date` argument**, so validation runs at `date.today()` (2026-08-18 at the
  observed run).
- `_run_retrieval_evaluation` (`benchmark.py:201-238`) rebuilds exception reports from the
  eval cases and reuses the same engine, so retrieval eval runs on `candidates`
  (validity-independent) — the 0.16 Recall@5 is a retrieval-quality result, and the
  per-case labels are the ones baked at 2025-12-01.
- Synthetic invoices are 2026-dated (`generate_synthetic.py:133,203`); the benchmark never
  derives a reference date from them. The 2026-08-29 max invoice date has only 29
  corpus-valid items (see §3).
- No CLI/config knob surfaces a reference date to the benchmark; `HybridContextEngine`
  supports it (`engine.py:36`) but the benchmark never uses it.

**Finding:** the benchmark is the only consumer that leaves `reference_date` to the wall
clock, and it is the consumer whose downstream phases depend on non-empty
`validated_evidence`.

## 9. Existing Test Coverage

Source: `apx/tests/test_phase2_evidence.py` (468 lines).

Covered (lines 63–261): valid evidence accepted; vendor mismatch rejected; future
effective date rejected (STALE); expired evidence rejected (STALE); outdated policy
version rejected; invalid outcome rejected (INVALID_OUTCOME); EXTERNAL authority flagged
but still valid; out-of-scope rejected; reference-date injection via
`set_reference_date` (2025-01-01 valid, 2026-01-01 stale).

**Gaps**:
- No test asserts the **default** `reference_date = date.today()` behavior in a
  benchmark/run context (only the explicit injection path is tested).
- No test asserts that the **persisted corpus stays non-stale** for the benchmark's
  invoice period, or that generator windows overlap the benchmark's run date.
- No test pins a single reference date across generator → labels → benchmark.
- No test exercises `populate_eval_labels` vs `benchmark` consistency.

## 10. Specification Cross-Check

Sources: `APX_V1_1_PHASE2_BUILD_BRIEF.md`, `APX_V1_1_PHASE5_BUILD_BRIEF.md`,
`docs/APX_IMPLEMENTATION_AUDIT.md`.

| Question | Code | Data | Spec | Finding |
|---|---|---|---|---|
| Must evidence carry effective dates? | Yes — required `effective_from`/`effective_until` | All 235 items present | §P2 lines 263–265, 331, 347, 363 | CONFORMANT |
| Must stale evidence be rejected (not trusted)? | Yes — `EvidenceValidator` rejects outside window | 204/235 expired today | §P2 641, 865 | CONFORMANT (mechanism) |
| What is the as-of reference date at run time? | `date.today()` default; benchmark passes none | n/a | Not defined in either brief or audit doc | **SPECIFICATION AMBIGUITY** |
| Corpus must include deliberately stale/irrelevant items? | Yes — 20 irrelevant + 15 stale | Present | §P2 375–379 | CONFORMANT |
| Corpus windows must overlap the benchmark invoice period (2026)? | Generator anchors 2023–2025 | Mostly expired by 2026 | Not defined | **SPECIFICATION AMBIGUITY** |
| Eval labels and run-time validation must share one reference date? | Labels 2025-12-01 vs benchmark wall clock | Divergent | Not defined | INCONSISTENT |
| Is retrieval Recall@5 affected by validity? | Evaluated on unfiltered candidates | n/a | §P2 971–977 lists metrics only | NOT A FRESHNESS CAUSE |

## 11. Root Cause

**PRIMARY ROOT CAUSE** — The end-to-end benchmark constructs `HybridContextEngine()`
without a `reference_date` (`benchmark.py:101`), so `EvidenceValidator` defaults to
`date.today()` (`validity.py:13`). At the observed run (2026-08-18) that wall-clock date
lies beyond the expiry of 204/235 (86.8%) of the corpus, whose windows were fixed at
generation to absolute 2023–2025 dates (`generate_evidence.py`). The validity filter
(`engine.py:110-138`) therefore yields near-empty `validated_evidence` — 0 valid items for
6 of 10 eval vendors — starving the downstream phases that consume only
`validated_evidence`, which is the direct driver of the Phase 5 failures (Detection F1
0.27, Automation 0.02, risk/action accuracy ~0.02).

**SECONDARY ROOT CAUSES**
1. The generator anchors windows to a fixed historical calendar with **no relative /
   as-of anchoring and no `generated_at` field** (`generate_evidence.py`), so the corpus
   silently decays as the wall clock advances.
2. **Inconsistent date anchors**: eval labels + standalone eval pin `2025-12-01`
   (`populate_eval_labels.py:212`, `evaluate.py:88`) while the benchmark uses the wall
   clock; synthetic invoices are 2026-dated; nothing reconciles them.

**NOT A ROOT CAUSE**
- Retrieval **Recall@5 0.16** — computed over validity-unfiltered candidates
  (`retrieval_eval.py:47`); a retrieval-quality issue, independent of freshness.
- Corpus serialization round-trip and index-cache consistency — both verified correct.

## 12. Recommended Fix

Exactly **one** strategy: **date-anchor the entire evidence pipeline on a single explicit
reference date** instead of the wall clock.

1. `generate_evidence.py`: add a `reference_date: date | None = None` parameter to
   `EvidenceGenerator.__init__` (defaulting to `date.today()`); derive every effective
   window from it (e.g., `effective_from` ∈ `[reference-18m, reference]`,
   `effective_until = effective_from + per-type span`), keeping the deliberate
   irrelevant/stale sets anchored strictly in the past relative to `reference_date`.
   Write `"generated_at": reference_date.isoformat()` into the exported corpus metadata.
2. `benchmark.py`: construct `HybridContextEngine(reference_date=<explicit date>)`,
   reading the value from a CLI/config flag (default: the same reference used to generate
   corpus and labels), **never** `date.today()`.
3. Regenerate the corpus (`generate_evidence.py`) and labels (`populate_eval_labels.py`,
   which already accepts a reference date) using that same reference date so corpus
   windows, labels, and run-time validation all agree, and the benchmark's 2026 invoice
   period has stocked valid evidence.
4. Keep `EvidenceValidator` semantics unchanged (inclusive boundaries, rule set); only the
   supplied reference date changes. This preserves the spec-compliant rejection behavior.

**Why this strategy:** it fixes the actual mechanism (wrong reference date + time-frozen
windows) at the source rather than patching downstream metrics, and it makes the pipeline
reproducible across calendar time (a run in any month yields a stocked, internally
consistent corpus).

**Expected behavior:** `validated_evidence` becomes non-empty for benchmark invoices;
Detection/Automation/Risk/Action metrics can then be measured against real evidence. Note
the retrieval Recall@5 must be addressed separately as a retrieval-quality problem; it will
not move from the reference-date fix.

**Tests:** extend `test_phase2_evidence.py` with a generator test asserting windows are
relative to the injected reference; a benchmark-construction test asserting an explicit
reference is passed; a consistency test that label-relevant evidence is valid at the
benchmark reference.

**Comparability:** regenerating the corpus invalidates comparability with the frozen
authoritative artifacts (`phase5_dev_seed42_20260818_090830.{json,txt}`); run must be
recorded with the new reference date and marked as a fresh baseline.

## 13. Files Affected (if the fix were implemented)

- `apx/evidence/generate_evidence.py` — reference-date parameter + relative windows +
  `generated_at` metadata.
- `apx/evaluation/benchmark.py` — pass explicit `reference_date` to `HybridContextEngine`.
- `apx/data/datasets/evidence/evidence_corpus.json` (+ `index/*.pkl`) — regenerated.
- `apx/data/datasets/eval/eval_dataset.json` — labels regenerated at same reference.
- `apx/evidence/populate_eval_labels.py` — optionally surface reference date via CLI.
- `apx/evidence/evaluate.py` — align its hardcoded `2025-12-01` to the shared reference.
- `apx/tests/test_phase2_evidence.py` — new tests.
- Unchanged (verified correct): `validity.py`, `engine.py`, `bm25.py`, `dense.py`,
  `schemas.py`, `retrieval_eval.py`.

## 14. Risks

- **Reproducibility:** corpus/labels must be regenerated and committed alongside the run;
  otherwise two runs on different calendar dates disagree.
- **Comparability:** regenerating the corpus changes benchmark numbers; the frozen
  `090830` baseline becomes non-comparable (documented and superseded).
- **Scope creep:** `evidence_validity_enabled` + windowed expiry is a real policy feature;
  anchoring to a fixed reference must not silently disable freshness (deliberately-stale
  evidence must stay rejectable).
- **Retrieval-quality gap persists:** Recall@5 0.16 will remain after the date fix; do not
  misattribute it to freshness later.

## 15. Open Questions

1. What should the "as-of" date be in production — invoice date, processing date, or a
   configurable reference? The spec does not say (SPECIFICATION AMBIGUITY).
2. Should `Evidence` gain a `created_at`/`generated_at` field to make corpus generation
   self-describing (schema change — out of scope for this audit)?
3. Should the benchmark fail fast (warn/assert) when `validated_evidence` is empty for
   most invoices, instead of silently producing near-zero metrics?
4. Is the 6/10 eval-vendor zero-valid evidence a corpus-coverage problem or purely a
   date-anchor problem? (Regeneration at 2026 reference would confirm.)
5. Should retrieval evaluation switch to `validated_evidence` so that freshness is scored
   explicitly (behavior change — out of scope)?
