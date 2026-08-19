# APX Implementation Audit

> Audit of the existing repository. No source code was modified during this audit.
> Audit date: 2026-08-18. Audit environment: Python 3.14 venv (pyproject targets py311).

## Legend

- ✅ VERIFIED COMPLETE — exists, implemented, wired, tested, passing
- 🟡 PARTIAL — exists/implemented but incomplete or not fully wired
- 🔴 BROKEN — exists but defective
- ⬜ MISSING — does not exist
- ❓ NOT VERIFIED — cannot be confirmed from this audit
- ⚪ LEGACY / SUPERSEDED — old approach still present, no longer the target

Each component assessed against: EXISTS / IMPLEMENTED / WIRED / TESTED / PASSING / STATUS.

---

## 1. Repository Structure

```
/mnt/d/Opencode
├── README.md                  (describes Phase 1 only)
├── pyproject.toml             (apx v0.2.0)
├── APX_V1_1_*_BUILD_BRIEF.md  (Phase 1, 2, 5 build briefs)
├── PHASE1..5_REPORT.md        (phase reports)
├── ROOT_CAUSE_REPORT.md       (Aug 16 benchmark root-cause analysis)
├── run_validator_eval.py      (standalone Phase-1 eval script)
├── docs/APX_IMPLEMENTATION_AUDIT.md  (this file)
└── apx/
    ├── config/     settings.py, risk_policy.yaml, retrieval_profiles.yaml
    ├── data/       schemas.py, generate_synthetic.py, split.py, datasets/
    ├── intelligence/ validator.py  (Phase 1)
    ├── exceptions/  models.py, taxonomy.py
    ├── evidence/    engine.py, bm25.py, dense.py, rrf.py, reranker.py,
    │                query.py, validity.py, schemas.py, models.py,
    │                generate_evidence.py, generate_eval.py,
    │                populate_eval_labels.py, evaluate.py
    ├── agent/       controller.py, state_machine.py, models.py, llm/{base,mock}.py
    ├── risk/        engine.py, models.py
    ├── guardrail/   engine.py, models.py
    ├── action/      executor.py, pipeline.py, models.py
    ├── approval/    engine.py
    ├── observability/ langfuse_tracer.py, logger.py, metrics.py
    ├── evaluation/  extraction_eval, detection_eval, retrieval_eval,
    │                decision_eval, action_eval, business_eval, benchmark.py,
    │                results/ (2 benchmark runs)
    └── tests/       17 test modules
```

Notes:

- No top-level `apx/__init__.py`; package resolves via installed editable dist (`apx.egg-info`).
- Git history: only 2 commits (`baebb1e` Phase 1 foundation, `4b19385` Phase 2-4 decision pipeline). Phase 5 assets (observability/, evaluation/, split.py, ROOT_CAUSE_REPORT.md, PHASE5_REPORT.md, docs/) are UNTRACKED.
- 18,004 total Python lines; 213 tests.
- Git working tree was dirty at audit time (modified mock.py, PHASE2 brief; untracked phase-5 files). No code was modified during this audit.

Target architecture check:

| Stage | Exists? |
|---|---|
| INGESTION | ⬜ MISSING (no ingestion code; synthetic generator stands in) |
| DOCUMENT INTELLIGENCE | ⬜ MISSING (no OCR/PDF/extraction module) |
| DETERMINISTIC VALIDATION | ✅ `apx/intelligence/validator.py` |
| EXCEPTION REPORT | ✅ `apx/data/schemas.py:ExceptionReport` |
| HYBRID CONTEXT ENGINE | ✅ `apx/evidence/engine.py` |
| BOUNDED AGENT | ✅ `apx/agent/controller.py` + `state_machine.py` |
| DECISION / RISK | 🟡 decision logic is naive substring matching; risk engine ✅ |
| ACTION GUARDRAIL | ✅ `apx/guardrail/engine.py` |
| ACTION / HITL | 🟡 action execution ✅; HITL approval engine not wired into pipeline |
| OBSERVABILITY / EVALUATION | 🟡 components exist; observability not wired into runtime |

---

## 2. Existing Test Suite and Baseline

Command (run from repo root, `.venv`):

```
python -m pytest apx/tests -v
```

| Item | Value |
|---|---|
| command | `python -m pytest apx/tests -v` |
| total | 213 |
| passed | 213 |
| failed | 0 |
| skipped | 0 |
| errors | 0 |
| warnings | 335 (all `datetime.utcnow()` deprecations) |
| duration | 115.05s |
| **STATUS** | ✅ VERIFIED COMPLETE (suite green) |

Test modules (test counts): `test_schemas` 15, `test_data_generator` 8, `test_data_integrity` 15, `test_validator` 31, `test_phase2_evidence` 16, `test_phase3_state_machine` 8, `test_phase3_agent` 9, `test_phase3_budget` 7, `test_phase3_integration` 11, `test_phase4_guardrail` 14, `test_phase4_risk` 11, `test_phase4_action` 29, `test_tracing` 23, `test_benchmark` 12, `test_eval_dataset` 3.

**Important:** the green unit suite does NOT imply the Phase 5 benchmark passes. See §7.

---

## 3. Phase 1 — Deterministic Foundation

| Component | EXISTS | IMPLEMENTED | WIRED | TESTED | PASSING | STATUS |
|---|---|---|---|---|---|---|
| Schemas (Vendor/PO/GRN/Invoice/ExceptionReport/GroundTruth) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ VERIFIED COMPLETE |
| Synthetic dataset generator | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ VERIFIED COMPLETE |
| Ground truth | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ VERIFIED COMPLETE |
| R1 Vendor | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ VERIFIED COMPLETE |
| R2 PO | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ VERIFIED COMPLETE |
| R3 Amount tolerance | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ VERIFIED COMPLETE |
| R4 GRN | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ VERIFIED COMPLETE |
| R5 Duplicate | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ VERIFIED COMPLETE |
| R6 Tax | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ VERIFIED COMPLETE |
| R7 Currency | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ VERIFIED COMPLETE |
| R8 Line item | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ VERIFIED COMPLETE |
| R9 Early payment / discount | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ VERIFIED COMPLETE (implemented as `DISCOUNT_ERROR` per Phase-1 brief §R9) |
| R10 Vendor credit | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ VERIFIED COMPLETE (implemented as `CREDIT_ISSUE`) |
| ExceptionReport | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ VERIFIED COMPLETE |
| Phase 1 tests | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ VERIFIED COMPLETE |

Details:

- `apx/data/schemas.py` — canonical Pydantic v2 models; `Decimal` everywhere; model validators recompute and cross-check subtotal/tax/total; `ExceptionReport` accumulates exceptions and flips `validation_status`.
- `apx/exceptions/taxonomy.py` — severity map + messages for all 10 codes.
- `apx/intelligence/validator.py` — deterministic, zero-LLM, 10 rule checks; tolerances from `risk_policy.yaml` (amount 2% / abs 0.01, tax 1%, qty 0%, discount 1%).
- Duplicate detection via in-memory `_seen_invoices` set — deterministic within a run; `reset_seen_invoices()` exists for run isolation.
- Data artifacts (seed 42): 20 vendors, 50 POs, 47 GRNs, 200 invoices, 200 ground-truth records. Ground truth is single-root-cause by design; validator over-detects cascades (per Phase-1 spec) — the documented cause of low detection precision later.
- `run_validator_eval.py` — standalone per-rule eval script (not part of pytest).

---

## 4. Phase 2 — Hybrid Retrieval / Context

| Component | EXISTS | IMPLEMENTED | WIRED | TESTED | PASSING | STATUS |
|---|---|---|---|---|---|---|
| SQL retrieval | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ MISSING — no SQL/sqlite anywhere in repo |
| BM25 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ VERIFIED COMPLETE (`rank_bm25`; cache `bm25_index.pkl`) |
| Dense retrieval | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ VERIFIED COMPLETE (SentenceTransformer; cache `dense_index.pkl`) |
| RRF | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ VERIFIED COMPLETE |
| Cross-encoder reranking | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ VERIFIED COMPLETE (`bge-reranker-base`, cached) |
| Metadata filtering | 🟡 | 🟡 | 🟡 | ✅ | ✅ | 🟡 PARTIAL — no pre-retrieval filter; scope/vendor/policy filtering only post-hoc in `EvidenceValidator` |
| Evidence validation | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ VERIFIED COMPLETE (`validity.py`) |
| Provenance | 🟡 | 🟡 | ✅ | ✅ | ✅ | 🟡 PARTIAL — only `retrieval_sources` list (BM25/Dense/Reranker); no full source-graph provenance |
| Freshness | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ VERIFIED COMPLETE (effective_from/until vs reference_date) |
| Successful-resolution filtering | 🟡 | 🟡 | ✅ | ✅ | ✅ | 🟡 PARTIAL — `INVALID_OUTCOME` rejects REJECTED/EXPIRED/FAILED outcomes; no explicit "only previously successful resolutions" filter |
| Integration with agent | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ VERIFIED COMPLETE (`EvidenceSet` consumed by `BoundedInvestigationAgent`) |
| Query builder | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ VERIFIED COMPLETE (`query.py`) |

Details / findings:

- `HybridContextEngine.retrieve()` pipelines BM25 → Dense → RRF → cross-encoder rerank → validity filter, returns `EvidenceSet`. Indexes auto-built/loaded; corpus integrity verified by evidence-ID list comparison.
- Profile config in `retrieval_profiles.yaml`: DEV (bge-small-en-v1.5 / bge-reranker-base), EVAL and PROD (larger models). All 4 HF models cached locally (~5.4 GB), so retrieval runs offline.
- Evidence corpus: 235 items; types: historical_resolution 108, vendor_policy 56, contract 41, payment_term 30.
- **🔴 Freshness degradation (broken in practice):** corpus is time-stamped around 2026-08-14. As of audit date 2026-08-18, 204/235 items are STALE (outside `effective_from..effective_until`), only 31 valid. Live smoke test (V-0001 / AMOUNT_MISMATCH) returned 20 candidates, **0 valid / 20 invalid**. The validity gate therefore rejects almost everything at the current date, starving the agent of valid evidence (see §5).
- Eval dataset: 10 curated cases (`eval_dataset.json`) with relevant/irrelevant/invalid evidence labels.

---

## 5. Phase 3 — Bounded Agent + Risk

| Component | EXISTS | IMPLEMENTED | WIRED | TESTED | PASSING | STATUS |
|---|---|---|---|---|---|---|
| Bounded state machine | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ VERIFIED COMPLETE |
| States DETECTED→CONTEXT_RETRIEVED→INVESTIGATING→DECISION_READY | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ VERIFIED COMPLETE |
| Terminal outcomes RESOLVED/REQUESTED_INFO/ESCALATED | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ VERIFIED COMPLETE (`RESOLVE`/`REQUEST_INFO`/`ESCALATE`) |
| Transitions | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ VERIFIED COMPLETE (`PERMITTED_TRANSITIONS`) |
| Transition guards | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ VERIFIED COMPLETE (`transition()` raises `TransitionError`) |
| Investigation limits (budget) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ VERIFIED COMPLETE |
| Timeout handling | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ MISSING — only step-budget, no wall-clock timeout |
| Failure handling | 🟡 | 🟡 | ✅ | ✅ | ✅ | 🟡 PARTIAL — exceptions caught → ESCALATE; LLM errors swallowed and logged as steps |
| Tool registry | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ MISSING — agent has no tool layer |
| Decision engine | 🔴 | 🔴 | ✅ | ✅ | ✅ | 🔴 BROKEN — decision is naive substring search of `findings_log`; `_make_final_decision()` is an empty pass-through |
| Risk engine | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ VERIFIED COMPLETE (5-dimension compound risk) |
| Risk policy | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ VERIFIED COMPLETE (`risk_policy.yaml` + pydantic models) |
| Escalation logic | 🟡 | 🟡 | ✅ | ✅ | ✅ | 🟡 PARTIAL — always-escalate by exception code works; `condition: amount > 100000` branch in `risk/engine.py:_check_always_escalate` is a no-op `pass` (guardrail re-implements it) |
| Legacy ReAct/open-ended agent | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ MISSING — no legacy ReAct code found; nothing to mark superseded |

Details:

- `state_machine.py`: `AgentState` + `TerminalOutcome` + `PERMITTED_TRANSITIONS` + `transition()` guard. INVESTIGATING self-loop allowed.
- `controller.py` (`BoundedInvestigationAgent`): DETECTED → CONTEXT_RETRIEVED → INVESTIGATING loop → DECISION_READY → terminal. Budget enforced; evidence IDs validated against `EvidenceSet`; mock LLM drives findings.
- **Decision quality problem:** with no valid evidence retrieved (§4 staleness), `_should_make_decision()` never returns early on evidence, so the mock LLM hits its `call_count >= 3 → ESCALATE` branch; benchmark shows 88% ESCALATE rate.
- LLM abstraction: `LLMProvider` ABC + deterministic `MockLLMProvider`. No real LLM provider wired (default `mock`); only mock is tested.
- `apx/risk/engine.py` (`CompoundRiskEngine`): FINANCIAL / COMPLIANCE / VENDOR / OPERATIONAL / EVIDENCE_CONFIDENCE dimensions; weights validated to sum to 1.0; risk thresholds; auto-resolve / always-escalate rules. Financial-risk amount extraction relies on exception `details` keys; amount is often not present in `details` (details carry invoice_total/po_total), so financial risk frequently falls back to "0".

---

## 6. Phase 4 — Action Guardrail + HITL

| Component | EXISTS | IMPLEMENTED | WIRED | TESTED | PASSING | STATUS |
|---|---|---|---|---|---|---|
| Action guardrail | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ VERIFIED COMPLETE |
| Authorization | 🟡 | 🟡 | 🟡 | 🟡 | ✅ | 🟡 PARTIAL — risk-level authorization + `required_approvers` lists, but no user/role model, no identity check |
| Allowed actions | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ VERIFIED COMPLETE (per-policy `allowed_risk_levels`) |
| Blocked actions | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ VERIFIED COMPLETE (`blocked_risk_levels`) |
| Evidence requirements | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ VERIFIED COMPLETE (`required_evidence_min`) |
| Approval requirements | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ VERIFIED COMPLETE (risk-level + amount based) |
| Idempotency | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ VERIFIED COMPLETE (24h window, in-memory) |
| Rate limiting | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ VERIFIED COMPLETE (per-action, in-memory) |
| Audit logging | 🟡 | 🟡 | 🟡 | ✅ | ✅ | 🟡 PARTIAL — `record_action()` writes to in-memory `_action_history`; no durable audit trail, no observability wiring |
| HITL | 🟡 | 🟡 | 🟡 | ✅ | ✅ | 🟡 PARTIAL — `ApprovalEngine` (request/approve/reject, all-approvers rule) implemented and unit-tested, but `Phase4Pipeline.process()` never invokes `approval_engine`; PENDING approvals auto-approve in DEV mode, so no real human loop in the pipeline |
| Action executor | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ VERIFIED COMPLETE (retries, compensation, DLQ, dry-run) |
| Action tests | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ VERIFIED COMPLETE (29 tests) |

Details / findings:

- `guardrail/engine.py`: 9 checks per evaluation (risk level, action allowed, evidence sufficiency, amount, idempotency, rate limit, investigation-outcome compatibility, always-escalate, auto-resolve). Decision = ALLOW / REQUIRE_APPROVAL / BLOCK. Policies hardcoded in `_load_config()` for 8 action types.
- `action/executor.py`: mock adapters for all 8 actions + compensation adapters + dead-letter queue. **Code smell:** adapter methods are duplicated (defined twice, ~lines 228-309 and 392-474); functionally the later definitions win.
- `action/pipeline.py` (`Phase4Pipeline`): risk → action-type selection → guardrail → ActionPlan → approval/execution. Passes `evidence_set=None` to `risk_engine.assess()` (evidence dimension always sees "no evidence").
- Rate-limit / idempotency state is in-memory only (lost on restart). Not persistent.
- HITL: `ApprovalEngine` exists and is tested, but pipeline integration is mocked away — real HITL flow is NOT operational end-to-end.

---

## 7. Phase 5 — Observability + Evaluation

| Component | EXISTS | IMPLEMENTED | WIRED | TESTED | PASSING | STATUS |
|---|---|---|---|---|---|---|
| Tracing | ✅ | ✅ | ⬜ | ✅ | ✅ | 🟡 PARTIAL — built + tested, NOT wired into pipeline |
| Local / no-op tracing | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ VERIFIED COMPLETE (`NoOpTracer`) |
| Structured logs | ✅ | ✅ | ⬜ | ✅ | ✅ | 🟡 PARTIAL — built + tested, NOT called in validator/agent/action |
| Metrics | ✅ | ✅ | ⬜ | ✅ | ✅ | 🟡 PARTIAL — `MetricsCollector` + `APXMetrics` built + tested, NOT called anywhere in runtime |
| Langfuse (if present) | 🟡 | 🟡 | ⬜ | ✅ | ✅ | 🟡 PARTIAL — `LangfuseTracer` + `_LangfuseBackend` present (lazy import; falls back to no-op); no runtime usage |
| Extraction evaluation | ✅ | ✅ | ✅ | ✅ | ✅ | 🟡 PARTIAL — evaluator exists but benchmark hardcodes 100% ("we know it's correct") |
| Detection evaluation | ✅ | ✅ | ✅ | ✅ | ✅ | 🔴 BROKEN — F1 25.2% (target 85%); precision 14.4% is by design (cascading vs single-root-cause GT) |
| Retrieval evaluation | ✅ | ✅ | ✅ | ✅ | ❓ | 🔴 BROKEN — Recall@5 27.2% (target 70%); valid evidence rate 6% |
| Decision evaluation | ✅ | ✅ | ✅ | ✅ | ✅ | 🔴 BROKEN — outcome accuracy 5.6%; risk/escalation accuracy 100% are vacuous (below) |
| Action evaluation | ✅ | ✅ | ✅ | ✅ | ✅ | 🔴 BROKEN — action/guardrail accuracy 40.2%; approval/blocked accuracy 0% (no approvals/blocked produced) |
| Business evaluation | ✅ | ✅ | ✅ | ✅ | ✅ | 🟡 PARTIAL — automation rate 12% (target 50%) — consequence of 88% exception-rate data; latencies are placeholders |
| Benchmark | ✅ | ✅ | ✅ | ✅ | ❓ | 🔴 BROKEN — both saved runs FAILED |
| Leakage prevention | 🟡 | 🟡 | ⬜ | ⬜ | ⬜ | 🟡 PARTIAL — `apx/data/split.py` has vendor-leakage/novel-combination checks, but is UNTESTED and not used by benchmark |

Details / findings:

- Observability (tracer/logger/metrics) is implemented and unit-tested (`test_tracing.py`, 23 tests) but grep confirms it is NOT invoked from any runtime component (validator, agent, risk, guardrail, action, pipeline). Wire-in is missing.
- Benchmark results (both saved runs):
  - `benchmark_dev_20260816_120804.json` / `benchmark_dev_20260816_155306.json` — both `passed: false`.
  - Latest (15:53): Detection F1 25.2% (precision 14.4%, recall 99.5%); Retrieval Recall@5 27.2%, MRR 0.55, nDCG@10 0.54, valid-evidence rate 6.0%, vendor-scope correctness 13.5%; Decision outcome accuracy 5.6%; Action/guardrail accuracy 40.2%; Automation rate 12.0%.
  - `ROOT_CAUSE_REPORT.md` (2026-08-16) documents the root causes: (1) retrieval labels were empty (since partially fixed — `_run_retrieval_evaluation` now loads eval cases), (2) decision GT enum mismatch AUTO_APPROVE/REVIEW vs RESOLVE/REQUEST_INFO (since fixed via `_DECISION_MAP`), (3) detection precision low by design, (4) generated 500-invoice dataset not aligned to the 10-case eval dataset, (5) 88% exception-rate data caps automation at ~12%.
- Decision "Risk accuracy 100% / Escalation accuracy 100%" in the benchmark are vacuous/tautological (all 500 cases classified risk-correct; risk classification always matches itself).
- `benchmark.py` passes `evidence_set=None` through Phase 4 and uses placeholder latencies (`phase1: 10ms` etc.) and a hardcoded-perfect extraction result.
- Leakage prevention: `apx/data/split.py` implements a scenario-controlled vendor/amount/policy-version split with `vendor_leakage` detection, but it has NO tests and is not referenced by the benchmark; therefore not verified in practice.

---

## 8. End-to-End Integration

What actually runs end-to-end today:

`InvoiceValidator.validate_invoice()` → `ExceptionReport` → `HybridContextEngine.retrieve()` → `EvidenceSet` → `BoundedInvestigationAgent.run()` → `InvestigationResult` → `CompoundRiskEngine.assess()` → `RiskAssessment` → `ActionGuardrail.evaluate()` → `GuardrailDecisionResult` → `Phase4Pipeline.process()` → `ActionPlan` → `ActionExecutor.execute()` → `ActionResult`.

Evidence it works:

- `test_phase3_integration.py` (11 tests) exercises ExceptionReport → EvidenceSet → Agent.
- `test_phase4_action.py` includes `test_end_to_end_phase1_to_4_pipeline` (Validator → Evidence → Agent → Risk → Guardrail → Action), all passing.
- Live smoke test this audit: `HybridContextEngine.retrieve()` ran (15s incl. reranker load) and returned an `EvidenceSet`; `pytest` full suite green.

Integration weaknesses observed:

- 🔴 Valid-evidence starvation: with the current date vs corpus windows, retrieval returns ~0 valid evidence, so the agent's decision quality collapses (ESCALATE-heavy) and guardrail evidence checks (`required_evidence_min`) fail → BLOCK/ESCALATE.
- 🟡 `Phase4Pipeline` passes `evidence_set=None` to risk; operational/evidence risk dimension is computed on an empty view.
- 🟡 No real LLM provider; mock provider only.
- 🟡 Observability not wired into the running pipeline (no spans/logs/metrics emitted during a run).
- 🟡 Approval engine not invoked by pipeline (DEV auto-approve path only).

---

## 9. Documentation vs Actual Code

| Doc | Claims | Reality |
|---|---|---|
| README.md | Phase 1 only; R1–R10 table; acceptance criteria all `[x]` | Mostly accurate for Phase 1; does not describe Phases 2–5 (README is stale for the current repo) |
| PHASE1_FREEZE_REPORT.md | Phase 1 complete, per-rule recall 100% | ✅ Accurate; consistent with validator + tests |
| PHASE2_REPORT.md | Phase 2 complete/frozen, retrieval stack | ✅ Largely accurate; stack exists as described. Note: report's file list mentions `generate_evidence_labels.py` which does not exist (actual: `populate_eval_labels.py`) |
| PHASE3_REPORT.md | Bounded agent + compound risk complete | 🟡 Mostly accurate; does not flag naive decision logic or missing timeout/tool registry |
| PHASE4_REPORT.md | Guardrail + approval/HITL complete (e.g., "Human-in-the-loop approval workflow ✅ PASS") | 🟡 Overstates — ApprovalEngine tested in isolation but NOT wired into the pipeline; claims no durable audit trail |
| PHASE5_REPORT.md | Observability + evaluation; benchmark run | 🟡 Overstates completeness; benchmark FAILED; observability not wired; several metrics NOT VERIFIED |
| ROOT_CAUSE_REPORT.md | Documents benchmark metric failures + P0 fixes | ✅ Accurate; P0 fixes for retrieval labels + decision enum mapping are now partially applied in code |
| APX_V1_1_PHASE5_BUILD_BRIEF.md | Spec for Phase 5 | Spec; not an implementation claim |
| pyproject.toml `description` | "Phase 2" | Stale — repo now contains Phases 1–5 |

General rule applied: documentation presence does not imply implementation completeness. The phase reports are largely self-authored progress claims; the benchmark (the objective signal) fails.

---

## Final Status

### Verified Complete

- Phase 1 deterministic foundation (schemas, generator, ground truth, R1–R10, ExceptionReport) + Phase 1 tests
- Phase 2 retrieval stack: BM25, dense, RRF, cross-encoder reranking, query builder, evidence validity, freshness, evidence engine integration
- Phase 3 bounded state machine, transitions, guards, budget, risk engine + risk policy
- Phase 4 action guardrail (allowed/blocked actions, evidence/approval requirements, idempotency, rate limiting), action executor (retries/compensation/DLQ), action tests
- Phase 5 no-op tracer, structured logger and metrics as standalone tested components
- Full pytest suite: 213/213 passing

### Partial

- SQL retrieval (missing) — see below
- Metadata filtering, provenance, successful-resolution filtering (post-hoc only)
- Agent failure handling; escalation condition rules in risk engine
- Authorization model; audit logging (in-memory only); HITL approval engine (not wired into pipeline)
- Observability components (built/tested, not wired into runtime)
- Extraction/business evaluation (hardcoded/placeholder inputs)
- Leakage prevention (`split.py` untested, unused)

### Broken

- Decision engine in agent (`_make_final_decision` no-op; outcome by substring match)
- Evidence freshness at current date — corpus mostly stale; retrieval returns ~0 valid evidence
- Phase 5 benchmark — both runs FAILED (detection F1 25%, retrieval Recall@5 27%, decision accuracy 5.6%, automation 12%)
- Detection precision (14%) — by design (cascading vs root-cause GT), incompatible with the 85% F1 target

### Missing

- INGESTION stage; DOCUMENT INTELLIGENCE stage (OCR/PDF/extraction)
- SQL retrieval
- Timeout handling in agent
- Tool registry in agent
- Real LLM provider wiring (mock only)
- Durable rate-limit/idempotency/audit storage
- Runtime wiring of observability (tracing/logs/metrics) into the pipeline
- Tests for `split.py` (leakage prevention) and integration of the split into benchmark

### Legacy / Superseded

- None found. No ReAct/open-ended agent code exists; the bounded state machine is the only agent implementation.

### Not Verified

- Langfuse live export (no credentials/run evidence — falls back to no-op)
- Benchmark pass state (never observed passing)
- Real-world (non-synthetic) ingestion/extraction accuracy
- Production retrieval profile (EVAL/PROD) end-to-end results

## Recommended Next Action

Regenerate the evidence corpus (`python -m apx.evidence.generate_evidence --seed 42`) with effective windows that are valid at run-time (or drive `EvidenceValidator` with the corpus generation date as `reference_date`), then re-run the Phase 5 benchmark to confirm retrieval valid-evidence rate and decision/automation metrics move — the current stale-corpus state makes retrieval, decision, and automation metrics structurally unfixable regardless of evaluation-logic fixes.

# Post-Audit Update — Phase 5 Benchmark Validity Fixes

Date: 2026-08-18

## Validity fixes applied

These fixes correct how the Phase 5 benchmark measures the system. They change measurement only; no
runtime, agent, retrieval, validator, guardrail, test, or architectural code was modified.

- retrieval query construction now uses real APExceptions
- extraction now uses ExtractionEvaluator
- business latency uses measured timings
- detection evaluates all reports
- ERROR-path invoices are processed instead of dummy-resolved
- action evaluation uses real ground truths
- risk evaluation compares against GT-implied risk
- escalation evaluation compares outcomes against GT
- FP/FN attribution was corrected
- action evaluation uses real expected actions
- approval evaluation is no longer a dead placeholder
- hardcoded evaluation placeholders removed

## Verification

- 213 tests passed, 0 failed.

## Final benchmark results

Artifacts: `apx/evaluation/results/phase5_dev_seed42_20260818_090830.{json,txt}`

- Detection F1: 27.4%
- Detection precision: 15.9%
- Detection recall: 99.5%
- Retrieval Recall@5: 16.4%
- Risk accuracy: 16%
- Escalation accuracy: 2%
- Action accuracy: 2%
- Automation rate: 2%

## Runtime

- Full benchmark runtime: approximately 1391 seconds
- Phase 2 retrieval dominates measured latency at approximately 2737 ms/case

## Status

- Benchmark still fails its quality thresholds (Detection F1, Retrieval Recall@5, Automation rate).
- These remaining failures are NOT fixed in this task.
- Validator over-flagging, stale evidence corpus, and high exception prevalence remain open issues.

## Benchmark validity fixes vs. system quality fixes

Benchmark **validity** fixes correct how results are measured: they remove placeholders, hardcoded
values, label leaks, and pipeline short-circuits so reported metrics reflect the real system. They do
not change the system itself. **System quality** fixes — regenerating the evidence corpus with valid
effective windows, reducing validator false positives, improving decision/action accuracy, or lowering
exception prevalence — are out of scope for this task and remain open.