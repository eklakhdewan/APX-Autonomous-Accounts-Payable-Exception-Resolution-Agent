# APX Temporal Fix Report

Date: 2026-08-18
Scope: Fix the temporal anchoring defect identified in `docs/APX_EVIDENCE_FRESHNESS_AUDIT.md`
(audit NOT modified). No retrieval, reranker, validator, agent, risk, guardrail, or
evaluation-metric changes.

---

## 1. Root Cause

The forensic audit established that the benchmark constructed `HybridContextEngine()`
without an explicit `reference_date` (`apx/evaluation/benchmark.py:101`), so
`EvidenceValidator` fell back to `date.today()` (`apx/evidence/validity.py:13`). At the
observed run (2026-08-18) that wall-clock date sat beyond the expiry of 204/235 (86.8%)
of the corpus, whose `effective_from`/`effective_until` windows were frozen to absolute
2023–2025 calendar dates at generation time (`apx/evidence/generate_evidence.py`). The
validity filter therefore produced near-empty `validated_evidence` for most invoices
(0 valid items for 6 of 10 eval vendors), and downstream phases were starved of evidence.

Secondary contributors (also fixed):
- The generator anchored every validity window to fixed absolute dates with no
  `reference_date` parameter, no `date.today()` and no `generated_at` metadata.
- Eval-label generation (`populate_eval_labels.py`) and the standalone eval tool
  (`evaluate.py`) pinned a hardcoded `date(2025, 12, 1)` while the benchmark used the
  wall clock — three mutually inconsistent date anchors.
- The benchmark invoice world is 2026 (`generate_synthetic.py` PO window
  2026-01-01..2026-06-30, invoice dates up to 2026-08-29), so evidence needed to be
  current in 2026, not 2025.

## 2. Temporal Model

One canonical simulated-world date now anchors the whole evidence pipeline:

```
APX_REFERENCE_DATE = 2026-08-29   (apx/evidence/dates.py)
```

Derivation (not an invented date): PO dates are generated in
[2026-01-01, 2026-06-30] and invoice dates in [po_date, po_date + 60 days]
(`generate_synthetic.py:133,203`), so the latest possible benchmark invoice date is
2026-06-30 + 60 days = **2026-08-29**. The benchmark temporal world is defined "as of"
that date: evidence must be current on 2026-08-29 to be trusted for benchmark invoices.

The four previously divergent time frames now agree:
| Time frame | Value |
|---|---|
| Evidence validity windows | relative to `APX_REFERENCE_DATE` (regenerated corpus) |
| Evaluation labels | regenerated at `APX_REFERENCE_DATE` |
| Benchmark invoice dates | 2026-01-01..2026-08-29 (unchanged, coherent with the anchor) |
| Benchmark run-time validation | explicit `reference_date = APX_REFERENCE_DATE` (never `date.today()`) |

## 3. Files Changed

| File | Change |
|---|---|
| `apx/evidence/dates.py` | NEW — canonical `APX_REFERENCE_DATE` constant with derivation docstring |
| `apx/evidence/generate_evidence.py` | `reference_date` param on generator; windows relative to it; corpus metadata (`reference_date`, `generated_at`); `--reference-date` CLI |
| `apx/evidence/populate_eval_labels.py` | `reference_date` default = `APX_REFERENCE_DATE` (was hardcoded 2025-12-01); `--reference-date` CLI |
| `apx/evidence/evaluate.py` | engine constructed with `APX_REFERENCE_DATE` (was hardcoded 2025-12-01) |
| `apx/evaluation/benchmark.py` | `reference_date` param on orchestrator (default `APX_REFERENCE_DATE`); `HybridContextEngine(reference_date=...)`; `reference_date` in result JSON + report; `--reference-date` CLI |
| `apx/tests/test_temporal_anchoring.py` | NEW — 13 focused temporal tests |
| `apx/data/datasets/evidence/evidence_corpus.json` | Regenerated at `APX_REFERENCE_DATE` (235 items; ids/content preserved) |
| `apx/data/datasets/eval/eval_dataset.json` | Labels regenerated at `APX_REFERENCE_DATE` |

Unchanged (verified): `validity.py`, `engine.py`, `bm25.py`, `dense.py`, `rrf.py`,
`reranker.py`, `schemas.py`, `retrieval_eval.py`, agent/risk/guardrail/action code,
validator rules, Phase 5 metrics, and all three authoritative artifacts.

## 4. Reference-Date Propagation

```
BenchmarkOrchestrator.__init__(reference_date=None)      benchmark.py
  └─ self.reference_date = reference_date or APX_REFERENCE_DATE
       └─ HybridContextEngine(reference_date=self.reference_date)   engine.py:71
            └─ EvidenceValidator(reference_date=...)                validity.py:12
                 └─ validate(e): from ≤ reference ≤ until (inclusive)
```

Every component consumes the single date: the benchmark passes it to the engine; the
engine passes it to the validator; the validator applies it to every candidate. The
retrieval evaluation and the 500-invoice pipeline share the same engine, so both run at
the same reference date. Labels and corpus were generated with the identical constant,
so validation, labels and data are coherent. No code path in benchmark execution reaches
`date.today()` (the validator default is only reachable when a caller passes no
reference; the benchmark always passes one).

## 5. Generator Changes

`EvidenceCorpusGenerator(seed=42, reference_date=APX_REFERENCE_DATE)`.

Window ranges became reference-relative while preserving the rng delta lengths so that
evidence_ids, vendor/exception/outcome assignments and content are bit-identical to the
prior corpus (verified: same 235 ids, same content; only dates shifted):

| Type | old window | new window | until span |
|---|---|---|---|
| historical_resolution | 2024-01-01..2025-12-31 | ref − 730d .. ref | +30..365d |
| vendor_policy | 2024-01-01..2025-06-30 | ref − 546d .. ref | +180..730d |
| contract | 2023-01-01..2025-12-31 | ref − 1095d .. ref | +365..1095d |
| payment_term | 2024-01-01..2025-06-30 | ref − 546d .. ref | +180..365d |
| irrelevant (deliberately invalid) | 2020-01-01..2021-12-31 | ref − 2192d .. ref − 1462d | fixed past |
| stale_test (deliberately stale) | 2022-01-01..2022-12-31 | ref − 1462d .. ref − 1097d | fixed past |

Preserved: seed reproducibility, type counts (100/50/30/20/20/15 = 235), vendor and
exception relationships, successful-resolution semantics, and deliberate irrelevant/stale
sets. Corpus now self-describes its anchor (`reference_date`, `generated_at`).

## 6. Test Results

- **Before:** 213 tests passed, 0 failed (full suite).
- **After:** **226 passed, 0 failed** (124.46s). All 213 existing tests still pass; no
  existing test was updated; **13 new** tests added in `apx/tests/test_temporal_anchoring.py`:
  1. explicit reference propagated to validator and (mocked) engine;
  2. benchmark default = `APX_REFERENCE_DATE` and custom reference propagated;
  3. evidence valid at reference accepted;
  4. evidence expired before reference rejected;
  5. future evidence rejected;
  6. boundary dates deterministic (from==ref, until==ref, from==ref+1, until==ref−1);
  7. explicit reference independent of wall clock;
  8. generator: no future-dated real evidence; deliberately-stale strictly in the past;
  9. generator: same seed + reference reproducible; reference shift keeps ids/content;
  10. corpus export records the reference date.

Freshness validation was not weakened (all validity rules unchanged).

## 7. Benchmark Before / After

Run: `python -m apx.evaluation.benchmark --tier dev --seed 42` (default reference
2026-08-29). New artifacts:
`apx/evaluation/results/benchmark_dev_20260818_103130.{json,txt}`.

| Metric | Baseline `090830` | After fix `103130` | Δ |
|---|---|---|---|
| reference_date | none (wall clock 2026-08-18) | 2026-08-29 (explicit) | fixed |
| Detection F1 | 0.2739 | 0.2739 | 0 |
| Detection precision | 0.1588 | 0.1588 | 0 |
| Detection recall | 0.9955 | 0.9955 | 0 |
| Retrieval Recall@5 | 0.1643 | 0.0667 | −0.0976 |
| Retrieval Recall@10 | 0.1643 | 0.0667 | −0.0976 |
| Retrieval MRR | 0.3000 | 0.2000 | −0.10 |
| Retrieval nDCG@10 | 0.3815 | 0.1815 | −0.20 |
| Risk accuracy | 0.16 | 0.178 | +0.018 |
| Escalation accuracy | 0.02 | 0.02 | 0 |
| Action accuracy | 0.02 | 0.02 | 0 |
| Automation rate | 0.02 (10/500) | 0.02 (10/500) | 0 |
| avg Phase 2 latency | 2736.9 ms | 2598.7 ms | −138 ms |

**The numbers did not materially improve. No improvement is claimed.** The temporal
defect is fixed (single explicit reference; reproducible; coherent corpus/labels/invoices),
but the Phase 5 quality gates still fail for unrelated reasons (see §8). Detection
TP/FP/FN (222/1176/1) are unchanged because Detection evaluates Phase-1 validator output,
which this task was forbidden to modify. Risk accuracy improved slightly (80→89 correct),
and retrieval latency improved, but neither clears a quality gate.

Retrieval Recall@5 moved because the evaluation labels were regenerated to be temporally
coherent (relevant = evidence valid at 2026-08-29). Candidates/ranking are unchanged
(corpus content preserved), so the drop is a label-semantics change, not a retrieval
regression — it exposes that the retriever surfaces few labeled-relevant items.

## 8. Remaining Issues

1. **Retrieval quality** (not addressed, out of scope): for 8 of 10 eval cases, zero
   labeled-relevant evidence appears in the top-20 candidates (`valid_count = 0`). Vendor
   scope correctness 6.5%, valid-evidence rate 1.5%. BM25/dense/RRF/reranker ranking does
   not surface the vendor's relevant evidence. This is the dominant blocker for Recall@5
   and for feeding the agent.
2. **Detection precision** (not addressed, out of scope): Detection F1 0.27 driven by
   1176 false positives from Phase-1 validation — a validator-precision issue.
3. **Automation** (not addressed, out of scope): mock LLM auto-resolves only when valid
   evidence has `relevance_score > 0.3` for auto-resolvable exception types; with poor
   retrieval ranking, 490/500 investigate to ESCALATE. Outcome accuracy 33.2% unchanged.
4. **Full-benchmark double-run** not performed (≈23 min each); reproducibility of the
   benchmark run is established by construction (deterministic corpus, labels, invoices,
   engine, and mock LLM under `seed + reference_date`) plus the generator/eval determinism
   tests. `test_eval_dataset.py::test_eval_dataset_deterministic` and
   `test_temporal_anchoring.py` cover the component determinism.

## 9. Recommended Next Action (exactly one)

**Fix retrieval relevance** (Phase 2 candidate generation / ranking), which is the single
largest unresolved blocker: it prevents Recall@5 (0.07 vs 0.70 target) and starves the
agent of usable evidence (limiting Automation 0.02 and Risk 0.178). Concretely: audit why
BM25/dense/RRF/reranker rank 0 relevant items in top-20 for 8/10 eval cases (query
construction in `apx/evidence/query.py`, corpus content fields, reranker scores, and
`evidence_validity` interactions), then improve ranking within the existing
architecture — leaving the temporal anchoring, validator rules, agent, risk, guardrail,
and Phase 5 metrics untouched. Detection precision (Phase 1) is the next independent item
after that.