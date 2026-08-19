# APX V1.1 — Phase 5 Implementation Brief
## Observability & Evaluation

**Project:** APX — Autonomous Accounts Payable Exception Resolution Agent  
**Phase:** 5  
**Status:** Implementation contract  
**Dependency:** Phase 4  
**Architecture:** FROZEN — V1.1  
**Previous checkpoint:** `phase-4-frozen`

---

# 0. Purpose

You are implementing **Phase 5 only** of APX V1.1.

The APX V1.1 architecture has already been reviewed and frozen. Phase 1–4 are complete and frozen. Do **not** redesign, refactor, replace, or expand the architecture.

Phase 5 adds the **Observability + Evaluation layer** on top of the existing Phase 1–4 implementation.

The authoritative Phase 5 objectives are:

1. Implement tracing for agent/pipeline execution.
2. Build the six-layer evaluation hierarchy.
3. Generate/use the Tier 2 Development dataset of 500 invoices.
4. Run a complete benchmark.
5. Produce an evaluation report/dashboard artifact.
6. Make evaluation and observability deterministic and reproducible.

The implementation plan defines Phase 5 as **Observability & Evaluation**, dependent on Phase 4. It specifies tracing, custom metrics, structured JSON logging, six evaluation modules, a benchmark orchestrator, and a `ScenarioControlledSplit`. 

---

# 1. Frozen Architecture

The existing architecture is:

```text
INGESTION
    ↓
DOCUMENT INTELLIGENCE
    ↓
DETERMINISTIC VALIDATION
    ↓
EXCEPTION REPORT
    ↓
HYBRID CONTEXT ENGINE
    ↓
BOUNDED AGENT
    ↓
DECISION
    ↓
ACTION GUARDRAIL
    ↓
ACTION / HUMAN-IN-THE-LOOP
    ↓
OBSERVABILITY + EVALUATION
```

Phase 5 is the final measurement/observability layer.

**Do not modify the preceding architecture.**

In particular:

- Do not replace the bounded state machine.
- Do not introduce ReAct/LangGraph.
- Do not replace hybrid retrieval.
- Do not bypass the action guardrail.
- Do not introduce a knowledge graph.
- Do not replace existing schemas.
- Do not redesign the risk engine.
- Do not redesign Phase 4 approval/action behavior.
- Do not add production ERP/email integrations.
- Do not add a frontend.
- Do not turn Phase 5 into a production deployment phase.

If an implementation issue is encountered, solve it locally. If a genuine specification conflict exists, report it instead of silently changing architecture.

---

# 2. Phase 5 Scope

## BUILD NOW

Implement:

- observability package
- tracing abstraction
- Langfuse integration/wrapper
- structured JSON logging
- custom metrics collection
- six evaluation layers
- benchmark orchestrator
- Tier 2 development dataset generation/validation
- scenario-controlled dataset splitting
- evaluation report generation
- Phase 5 tests
- deterministic/reproducibility checks
- `PHASE5_REPORT.md`

## DO NOT BUILD NOW

Do NOT implement:

- FastAPI production API
- Docker production deployment
- production ERP/email/Slack/Jira integrations
- UI/frontend
- new agent architectures
- new retrieval architecture
- new risk architecture
- new action architecture
- autonomous capabilities beyond Phase 4
- unrelated Phase 1–4 refactoring
- benchmark Tier 3 unless required as a minimal interface for future Phase 6

Phase 6 is the production hardening/API phase and is outside this task.

---

# 3. Required Files

Create clean modules. Do not create a monolithic evaluation file.

Expected structure:

```text
apx/
├── observability/
│   ├── __init__.py
│   ├── langfuse_tracer.py
│   ├── metrics.py
│   └── logger.py
│
├── evaluation/
│   ├── __init__.py
│   ├── extraction_eval.py
│   ├── detection_eval.py
│   ├── retrieval_eval.py
│   ├── decision_eval.py
│   ├── action_eval.py
│   ├── business_eval.py
│   └── benchmark.py
│
├── data/
│   └── split.py
│
└── tests/
    ├── test_tracing.py
    ├── test_evaluation.py
    └── test_split.py
```

You may adjust exact import/package details if required by the existing repository structure, but preserve the separation of responsibilities.

---

# 4. Observability

## 4.1 Tracing

Implement:

```text
apx/observability/langfuse_tracer.py
```

The tracer must provide a clean abstraction for tracing APX execution.

It must be capable of representing at least:

- run/case ID
- invoice ID
- phase
- component/operation
- start time
- end time
- duration/latency
- input metadata
- output metadata
- status
- error information where applicable

Trace the important execution stages rather than only wrapping the top-level function.

At minimum, the trace model should be capable of representing:

```text
ExceptionReport
    ↓
Evidence Retrieval
    ↓
Agent Investigation
    ↓
Decision/Risk
    ↓
Guardrail
    ↓
Action/HITL
```

Do not leak secrets/API keys into traces.

---

# 4.2 Langfuse Integration

The implementation plan explicitly requires Langfuse tracing.

Use an adapter/wrapper so the rest of APX does not depend directly on Langfuse internals.

Requirements:

- Langfuse configuration must be external/configurable.
- Missing Langfuse credentials must not make deterministic local evaluation impossible.
- Tests must run without requiring a live external Langfuse service.
- Provide a no-op/local fallback for tests and offline development.
- Never hard-code credentials.
- Never commit secrets.

The observability abstraction should therefore support:

```text
Langfuse backend
        OR
Local/no-op backend
```

without changing the evaluation logic.

---

# 4.3 Structured JSON Logging

Implement:

```text
apx/observability/logger.py
```

Logs must be machine-readable JSON.

Each important event should contain enough context to correlate it with an evaluation case.

Suggested fields:

```text
timestamp
run_id
invoice_id
phase
component
event
status
duration_ms
metadata
error
```

Do not log secrets or unnecessary sensitive information.

---

# 4.4 Metrics

Implement:

```text
apx/observability/metrics.py
```

Metrics must support at least:

- latency
- execution duration
- success/failure count
- token/cost information where available
- action count
- escalation count
- automation count
- evaluation metrics

Metrics must be deterministic when their inputs are deterministic.

---

# 5. Six-Layer Evaluation Hierarchy

The V1.1 architecture explicitly freezes the six-layer evaluation hierarchy.

Implement six separate evaluation modules.

```text
Layer 1 — Extraction
        ↓
Layer 2 — Detection
        ↓
Layer 3 — Retrieval
        ↓
Layer 4 — Decision
        ↓
Layer 5 — Action
        ↓
Layer 6 — Business
```

Each evaluator must:

1. accept explicit inputs;
2. calculate deterministic metrics;
3. return structured results;
4. be independently testable;
5. avoid embedding benchmark-specific assumptions.

---

# 6. Layer 1 — Extraction Evaluation

File:

```text
apx/evaluation/extraction_eval.py
```

Evaluate extracted invoice/business fields against ground truth.

Where applicable, report:

- field-level accuracy
- precision
- recall
- F1
- exact-match rate

Do not invent extraction metrics for fields that do not exist in the current dataset/schema.

The evaluator must clearly distinguish:

```text
correct field
incorrect field
missing field
unexpected field
```

---

# 7. Layer 2 — Detection Evaluation

File:

```text
apx/evaluation/detection_eval.py
```

Evaluate deterministic exception detection against ground truth.

Report:

- exception precision
- exception recall
- exception F1
- per-exception-type metrics
- false positives
- false negatives

Use the existing Phase 1 ground-truth conventions.

Do not redefine Phase 1 ground truth.

Remember that Phase 1 intentionally distinguishes root-cause ground truth from cascading validator detections. Preserve that behavior.

---

# 8. Layer 3 — Retrieval Evaluation

File:

```text
apx/evaluation/retrieval_eval.py
```

Evaluate the existing Phase 2 retrieval system.

Required metrics:

- Recall@5
- Recall@10
- MRR
- nDCG@10

The evaluator must use explicit relevance labels.

Do NOT report `N/A` simply because labels are inconvenient.

Each evaluation case must contain enough ground truth to distinguish:

```text
relevant evidence
irrelevant evidence
invalid evidence
```

The existing Phase 2 evaluation design already requires relevance labeling. Preserve it.

The evaluator must operate on the existing retrieval outputs rather than creating a second retrieval implementation.

---

# 9. Layer 4 — Decision Evaluation

File:

```text
apx/evaluation/decision_eval.py
```

Evaluate the Phase 3/4 decision output.

At minimum support:

- decision accuracy
- expected vs actual terminal outcome
- risk classification correctness
- escalation correctness

Where appropriate, report:

```text
TP
TN
FP
FN
accuracy
precision
recall
F1
```

Do not treat raw LLM confidence as the decision metric.

The existing compound risk policy remains authoritative.

---

# 10. Layer 5 — Action Evaluation

File:

```text
apx/evaluation/action_eval.py
```

Evaluate Phase 4 action/guardrail behavior.

Measure:

- action correctness
- expected action vs actual action
- guardrail decision correctness
- unauthorized-action rate
- approval requirement correctness
- blocked-action correctness
- escalation correctness

A critical safety metric is:

```text
unauthorized_action_rate
```

Target:

```text
0 unauthorized actions
```

The action guardrail remains the authorization boundary.

Never bypass it for evaluation convenience.

---

# 11. Layer 6 — Business Evaluation

File:

```text
apx/evaluation/business_eval.py
```

Report business-level outcomes supported by the existing data.

At minimum:

- automation rate
- escalation rate
- estimated time saved
- cost
- latency

Clearly document how derived business metrics are calculated.

Do not invent financial savings claims without an explicit calculation basis.

If a business metric cannot be validly computed from available data, report it as unavailable and explain why rather than fabricating a number.

---

# 12. Benchmark Orchestrator

File:

```text
apx/evaluation/benchmark.py
```

Implement a single benchmark entry point that runs all six layers.

Target interface:

```bash
python -m apx.evaluation.benchmark --tier dev
```

or an equivalent repository-consistent command.

The benchmark must:

1. load the selected dataset;
2. apply the correct split;
3. execute the required evaluation layers;
4. collect metrics;
5. record failures;
6. produce a structured result;
7. generate a human-readable report.

The implementation plan specifies the milestone:

```text
python evaluation/benchmark.py --tier dev
```

→ six-layer report.

Preserve the equivalent functionality even if the module invocation differs.

---

# 13. Tier 2 Development Dataset

The implementation plan specifies:

```text
Tier 2 / Development
500 invoices
100+ POs
75+ GRNs
35+ vendors
```

Generate the Tier 2 dataset using the existing deterministic data-generation architecture.

Do not replace the existing generator with an unrelated system.

The generator should remain configurable and reproducible.

Use a fixed seed for benchmark reproducibility.

---

# 14. Dataset Split

Implement:

```text
apx/data/split.py
```

with a `ScenarioControlledSplit`.

The V1.1 specification explicitly defines a multi-axis split.

## Split dimensions

### Vendors

```text
Train:      known subset (~70%)
Validation: known subset (~15%)
Test:       remaining + unseen vendors (~15%)
```

### Exception types

All exception types should remain represented.

### Exception combinations

The test set must contain **novel combinations not seen during training**.

### Amount range

The specification defines a shifted test range:

```text
Train: $100–$50K
Test:  $50K–$150K
```

Implement this only where the existing data model supports it cleanly.

### Policy version

The specification defines:

```text
Train/Validation: policy v1.0
Test:             newer policy v1.1
```

Preserve the existing policy/version model and do not fabricate unsupported policy semantics.

The split must prevent leakage across its intended grouping dimensions.

---

# 15. Reproducibility

Phase 5 evaluation must be reproducible.

Requirements:

```text
same seed
+
same dataset
+
same configuration
=
same evaluation result
```

At minimum test:

- dataset split reproducibility
- metric reproducibility
- benchmark result reproducibility

If timestamps or external tracing IDs make byte-for-byte reports impossible, separate deterministic benchmark results from nondeterministic runtime metadata.

---

# 16. Test Requirements

Create:

```text
tests/test_tracing.py
tests/test_evaluation.py
tests/test_split.py
```

## test_tracing.py

Verify:

- every evaluated run can produce a complete trace representation;
- trace fields are present;
- errors are represented;
- local/no-op mode works without external credentials;
- secrets are not emitted.

## test_evaluation.py

Verify every evaluation layer against small known datasets.

Tests must check actual metric values.

Do not merely assert that a function returns a dictionary.

Example:

```python
result = evaluate_retrieval(...)

assert result.recall_at_5 == expected_value
assert result.mrr == expected_value
```

## test_split.py

Verify:

- deterministic split with fixed seed;
- vendor leakage prevention;
- expected train/validation/test structure;
- novel test combinations;
- unseen-vendor handling where applicable.

---

# 17. Integration Requirements

Phase 5 must consume the outputs of Phases 1–4.

Do not duplicate:

- deterministic validation;
- evidence retrieval;
- bounded agent logic;
- risk calculation;
- guardrail logic;
- action execution.

Evaluation should observe/evaluate those systems.

Conceptually:

```text
Phase 1 output ─────┐
Phase 2 output ─────┤
Phase 3 output ─────┼──→ Phase 5 Evaluation
Phase 4 output ─────┘
                         ↓
                    Metrics/Report
```

---

# 18. No Hidden Architecture Changes

The following are prohibited:

```text
❌ New agent
❌ ReAct
❌ LangGraph
❌ New database
❌ Knowledge graph
❌ New retrieval engine
❌ New risk engine
❌ New guardrail
❌ New action framework
❌ UI
❌ Production API
❌ Production deployment
```

If a component appears necessary, first determine whether it belongs to Phase 5 observability/evaluation. If not, leave it for the appropriate later phase.

---

# 19. Phase 5 Acceptance Criteria

Phase 5 is complete only when all of the following are true:

- [ ] Observability package exists.
- [ ] Tracing abstraction exists.
- [ ] Langfuse integration exists behind the abstraction.
- [ ] Local/no-op tracing works without external credentials.
- [ ] Structured JSON logging exists.
- [ ] Metrics collection exists.
- [ ] Layer 1 evaluator exists and is tested.
- [ ] Layer 2 evaluator exists and is tested.
- [ ] Layer 3 evaluator exists and reports Recall@5.
- [ ] Layer 3 reports Recall@10.
- [ ] Layer 3 reports MRR.
- [ ] Layer 3 reports nDCG@10.
- [ ] Layer 4 evaluator exists and is tested.
- [ ] Layer 5 evaluator exists and is tested.
- [ ] Unauthorized-action rate is measurable.
- [ ] Layer 6 evaluator exists and is tested.
- [ ] Tier 2 Dev dataset contains 500 invoices.
- [ ] Dataset has the required supporting AP records.
- [ ] ScenarioControlledSplit exists.
- [ ] Leakage tests pass.
- [ ] Novel-combination test behavior is verified.
- [ ] Benchmark orchestrator runs all six layers.
- [ ] Benchmark results are reproducible.
- [ ] Human-readable evaluation report is generated.
- [ ] Phase 1–4 tests remain passing.
- [ ] No frozen architecture component is redesigned.
- [ ] No secrets are committed.
- [ ] `PHASE5_REPORT.md` is generated.

---

# 20. Phase 5 Gate

The implementation plan defines the Phase 5 gate as:

> All 6 evaluation layers run without error. Metrics are reproducible (same seed → same results). Langfuse dashboard shows complete traces for every test case.

The implementation plan also specifies target reference values:

```text
Decision accuracy > 85%
Retrieval Recall@5 > 70%
Automation rate > 50%
```

Treat these as **evaluation targets/gates**, not numbers to manipulate the implementation to achieve.

If a target is missed:

1. report the actual result;
2. identify the failure;
3. do not fabricate or suppress metrics;
4. do not alter the benchmark merely to improve the score.

---

# 21. Required Final Report

Create:

```text
PHASE5_REPORT.md
```

It must contain:

1. implementation summary;
2. specification compliance table;
3. files created;
4. dataset statistics;
5. split statistics;
6. all six evaluation-layer results;
7. retrieval metrics;
8. decision metrics;
9. action/guardrail safety metrics;
10. business metrics;
11. latency/cost metrics;
12. observability/tracing verification;
13. reproducibility verification;
14. test results;
15. failures/limitations;
16. explicit pass/fail against every acceptance criterion;
17. freeze recommendation.

Do not mark Phase 5 complete merely because tests pass.

---

# 22. Final Verification Sequence

Before declaring Phase 5 complete:

```bash
python -m pytest apx/tests -q
```

Then run the Phase 5 benchmark.

Then verify:

```text
All six layers execute
        ↓
Metrics are populated
        ↓
Retrieval metrics are numeric
        ↓
No unauthorized actions
        ↓
Benchmark reproducible
        ↓
Traces/logs verified
        ↓
PHASE5_REPORT.md generated
```

Only after this should Phase 5 be considered **READY FOR FREEZE**.

---

# 23. Final Instruction to the Implementation Agent

You are an **implementation engineer**, not an architect.

APX V1.1 architecture is frozen.

Implement **Phase 5 only**.

Priorities:

1. correctness
2. deterministic evaluation
3. reproducibility
4. metric validity
5. observability
6. testability
7. clean separation of concerns
8. maintainability

Do not optimize metrics artificially.

Do not invent ground truth.

Do not report `N/A` for a required metric when the specification requires the corresponding ground truth to be created.

Do not silently modify Phases 1–4.

Start by inspecting the current repository and existing Phase 1–4 interfaces. Then implement Phase 5 incrementally, run tests after each major component, and finish with `PHASE5_REPORT.md`.

**The only architectural objective of this phase is:**

> **Make APX measurable, observable, reproducible, and honestly evaluable across all six layers.**
