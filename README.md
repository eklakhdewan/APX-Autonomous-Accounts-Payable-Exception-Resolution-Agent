# APX — Autonomous Accounts Payable Exception Resolution Agent

> **Research-grade autonomous exception-resolution system for Accounts Payable (AP)**  
> Deterministic validation → evidence retrieval → decision intelligence → risk controls → approval → guarded action execution → evaluation → observability.

[![Python](https://img.shields.io/badge/Python-3.12%2B-blue)](#)
[![Tests](https://img.shields.io/badge/tests-242%20passed-brightgreen)](#)
[![Status](https://img.shields.io/badge/status-Phase%205%20complete%20%2F%20Phase%206%20next-orange)](#)

---

## 1. Overview

**APX (Autonomous Accounts Payable Exception Resolution Agent)** is an engineering and research project for resolving Accounts Payable exceptions with a controlled autonomous workflow.

The system is designed around a strict principle:

> **Automation must be evidence-grounded, risk-aware, observable, reproducible, and auditable.**

Rather than treating an LLM as the source of truth, APX separates deterministic financial validation from retrieval, reasoning, risk assessment, approval, and action execution.

The current implementation has progressed well beyond the original Phase 1 deterministic foundation and now includes the Phase 1–5 platform, retrieval/evaluation infrastructure, temporal anchoring, and observability components.

---

## 2. Problem

Accounts Payable workflows frequently encounter exceptions such as:

- vendor mismatches
- purchase-order mismatches
- amount discrepancies
- goods-received mismatches
- duplicate invoices
- tax errors
- currency inconsistencies
- line-item discrepancies
- discount errors
- vendor credit issues

A useful autonomous system cannot simply generate an answer. It must determine:

1. **What is wrong?**
2. **What evidence proves it?**
3. **What policy applies?**
4. **How risky is the exception?**
5. **Can it be resolved automatically?**
6. **Does human approval remain necessary?**
7. **What action should be executed?**
8. **Can the entire decision be audited and evaluated?**

APX is built around that complete decision pipeline.

---

# 3. System Architecture

```text
                         ┌───────────────────────────┐
                         │        AP Exception       │
                         │          Input            │
                         └─────────────┬─────────────┘
                                       │
                                       ▼
                         ┌───────────────────────────┐
                         │ Deterministic Validation  │
                         │          R1–R10            │
                         └─────────────┬─────────────┘
                                       │
                                       ▼
                         ┌───────────────────────────┐
                         │     Evidence Retrieval    │
                         │                           │
                         │  ┌─────────┐ ┌─────────┐ │
                         │  │  BM25   │ │  Dense  │ │
                         │  │Retrieval│ │Retrieval│ │
                         │  └────┬────┘ └────┬────┘ │
                         │       └──────┬─────┘      │
                         │              ▼            │
                         │        Hybrid / RRF       │
                         │              │            │
                         │              ▼            │
                         │       Cross-Encoder       │
                         │          Reranking         │
                         └──────────────┬────────────┘
                                        │
                                        ▼
                         ┌───────────────────────────┐
                         │ Evidence Validation /     │
                         │ Temporal Anchoring        │
                         └─────────────┬─────────────┘
                                       │
                                       ▼
                         ┌───────────────────────────┐
                         │     Agent Investigation   │
                         │     + Decision Logic       │
                         └─────────────┬─────────────┘
                                       │
                                       ▼
                         ┌───────────────────────────┐
                         │       Risk Engine         │
                         │ Amount / Severity /       │
                         │ Confidence / Evidence /   │
                         │ Historical Risk           │
                         └─────────────┬─────────────┘
                                       │
                    ┌──────────────────┼──────────────────┐
                    │                  │                  │
                    ▼                  ▼                  ▼
              AUTO RESOLVE       HUMAN REVIEW        ESCALATE
                    │                  │                  │
                    └──────────────────┼──────────────────┘
                                       ▼
                         ┌───────────────────────────┐
                         │ Approval + Guardrails     │
                         └─────────────┬─────────────┘
                                       │
                                       ▼
                         ┌───────────────────────────┐
                         │   Guarded Action Engine   │
                         │ Retry / Compensation /    │
                         │ Idempotency / DLQ / Dry   │
                         │ Run                        │
                         └─────────────┬─────────────┘
                                       │
                                       ▼
                         ┌───────────────────────────┐
                         │ Observability + Evaluation│
                         │ Metrics / Tracing / Logs  │
                         └───────────────────────────┘
```

---

# 4. Core Engineering Principles

APX is intentionally designed around the following principles.

### 4.1 Deterministic financial truth

Financial validation is not delegated to an LLM.

The deterministic validation layer implements the AP exception taxonomy and performs structured comparisons using controlled business rules.

### 4.2 Evidence before reasoning

Retrieval exists to provide supporting evidence for decisions.

The system distinguishes between:

- retrieving candidate evidence
- ranking evidence
- validating evidence
- anchoring evidence temporally
- using evidence for downstream decisions

### 4.3 Risk-aware autonomy

Not every exception should be automatically resolved.

The system incorporates:

- monetary risk
- exception severity
- confidence
- evidence sufficiency
- historical success
- explicit always-escalate rules
- explicit auto-resolution rules

### 4.4 Human-in-the-loop controls

Human approval is treated as a control boundary rather than an afterthought.

### 4.5 Observable execution

Investigation and action execution should be traceable.

APX includes logging, metrics, and tracing infrastructure for this purpose.

### 4.6 Reproducible evaluation

Evaluation is treated as a first-class engineering component rather than a manual demonstration.

---

# 5. Exception Taxonomy — R1–R10

| Code | Exception | Description |
|---|---|---|
| R1 | `VENDOR_MISMATCH` | Invoice vendor is inconsistent with PO/vendor |
| R2 | `PO_MISMATCH` | Missing/invalid PO reference or wrong vendor |
| R3 | `AMOUNT_MISMATCH` | Invoice total differs from PO total within configured tolerance rules |
| R4 | `GRN_MISMATCH` | Invoiced quantity exceeds received quantity |
| R5 | `DUPLICATE_INVOICE` | Duplicate vendor + invoice number |
| R6 | `TAX_ERROR` | Tax calculation mismatch |
| R7 | `CURRENCY_MISMATCH` | Invoice/PO/vendor currency inconsistency |
| R8 | `LINE_ITEM_MISMATCH` | Line-item price/quantity differs from PO |
| R9 | `DISCOUNT_ERROR` | Discount differs from expected business data |
| R10 | `CREDIT_ISSUE` | Vendor credit status is HOLD/SUSPENDED/BLOCKED |

---

# 6. Implemented System Components

## 6.1 Data and Domain Layer

The project contains canonical domain schemas and synthetic data generation for reproducible development and testing.

Key capabilities include:

- vendors
- purchase orders
- goods receipts
- invoices
- ground-truth exception labels
- linked relational records
- deterministic synthetic generation
- data integrity validation
- dataset splitting

---

## 6.2 Deterministic Validation

The validation foundation implements the R1–R10 exception taxonomy without requiring an LLM.

Important properties:

- deterministic behavior
- reproducible outputs
- structured Pydantic models
- Decimal-based monetary comparisons
- configurable tolerances
- duplicate detection
- boundary-case testing
- multiple-exception handling

---

# 7. Agent Layer

APX includes an agent/state-machine layer for controlled investigation and decision execution.

The agent infrastructure includes:

- investigation steps
- state-machine transitions
- configurable investigation budgets
- mock LLM provider
- deterministic development behavior
- integration with retrieval/evidence components

The agent is intentionally constrained rather than being an unconstrained autonomous loop.

---

# 8. Retrieval and Evidence Pipeline

The retrieval stack is a major part of the current APX implementation.

```text
Query
  │
  ├───────────────► BM25 / Sparse Retrieval
  │
  └───────────────► Dense Semantic Retrieval
                         │
                         ▼
                   Hybrid Fusion
                         │
                         ▼
                    RRF Ranking
                         │
                         ▼
                 Cross-Encoder Reranker
                         │
                         ▼
                 Evidence Candidates
                         │
                         ▼
               Evidence Validity Checks
                         │
                         ▼
                 Temporal Anchoring
```

### Sparse retrieval

BM25 provides lexical retrieval and is useful when exact entities, invoice identifiers, vendor names, codes, and terminology matter.

### Dense retrieval

Dense retrieval provides semantic matching using Sentence Transformers.

The development profile currently uses:

```text
BAAI/bge-small-en-v1.5
```

### Hybrid retrieval

Sparse and dense retrieval are combined through reciprocal-rank fusion.

### Cross-encoder reranking

The current development profile uses:

```text
BAAI/bge-reranker-base
```

The reranker operates over the candidate set produced by retrieval.

### Local model control

Development and evaluation profiles support:

```yaml
local_files_only: true
```

This prevents accidental model downloads in environments where reproducibility or offline execution is required.

Production remains configurable.

---

# 9. Retrieval Profiles

Retrieval configuration is profile-driven.

Current profiles include:

| Profile | Dense Model | Reranker | Device | Local Only |
|---|---|---|---|---|
| DEV | `BAAI/bge-small-en-v1.5` | `BAAI/bge-reranker-base` | CPU | Yes |
| EVAL | `BAAI/bge-large-en-v1.5` | `BAAI/bge-reranker-large` | CPU | Yes |
| PROD | Environment-configurable | Environment-configurable | Environment-configurable | No |

Configuration is maintained under:

```text
apx/config/retrieval_profiles.yaml
```

---

# 10. Evidence Quality and Temporal Anchoring

APX does not treat every retrieved document as equally valid evidence.

The evidence subsystem includes:

- evidence schemas
- evidence validity checks
- evidence generation utilities
- evidence evaluation
- date extraction/handling
- temporal anchoring
- freshness-oriented analysis

This is important for AP because an apparently relevant policy or vendor record may be invalid if it was not applicable at the time of the transaction.

---

# 11. Risk and Decision Layer

The risk engine combines multiple signals.

Current policy dimensions include:

- amount risk
- severity risk
- confidence risk
- evidence risk
- historical risk

The configured compound weighting is:

| Signal | Weight |
|---|---:|
| Amount | 0.25 |
| Severity | 0.25 |
| Confidence | 0.20 |
| Evidence | 0.15 |
| Historical | 0.15 |

The project also defines:

- auto-resolve thresholds
- review thresholds
- escalation thresholds
- always-escalate rules
- explicit auto-resolution rules
- tolerance configuration

Examples of explicit escalation controls include:

- `CREDIT_ISSUE`
- `VENDOR_MISMATCH`
- high-value exceptions above the configured threshold

---

# 12. Action and Approval Controls

APX includes a guarded action execution subsystem.

Capabilities include:

- action planning
- approval workflow
- action execution
- retry handling
- compensation handling
- dead-letter queue behavior
- dry-run mode
- idempotency checks
- execution history
- approval history
- execution timestamps

This is a critical architectural boundary:

> **A model decision does not directly imply an irreversible business action.**

---

# 13. Guardrails

The guardrail layer provides additional protection around autonomous action execution.

Controls include:

- risk checks
- approval checks
- rate/window controls
- idempotency protection
- action constraints
- escalation behavior
- execution logging

---

# 14. Evaluation Framework

Evaluation has been expanded beyond simple unit tests.

The evaluation package currently contains components for:

```text
apx/evaluation/
├── action_eval.py
├── benchmark.py
├── business_eval.py
├── decision_eval.py
├── detection_eval.py
├── extraction_eval.py
└── retrieval_eval.py
```

This provides separate evaluation dimensions for different stages of the system.

### Evaluation dimensions

The project evaluates areas including:

- retrieval quality
- detection
- extraction
- decision quality
- business outcomes
- action behavior
- benchmark performance

Evaluation artifacts are stored under:

```text
apx/evaluation/results/
```

---

# 15. Current Verification

The current test suite has been executed successfully.

```text
242 passed
335 warnings
0 failed
```

Latest observed run:

```text
242 passed, 335 warnings in 150.44s
```

The warnings are primarily Python/Pydantic deprecation warnings related to `datetime.utcnow()` and are not test failures.

### Test coverage includes

- benchmark behavior
- synthetic data generation
- data integrity
- evaluation dataset
- evidence
- agent
- budget
- integration
- state machine
- actions
- guardrails
- risk
- schemas
- temporal anchoring
- tracing
- validation

Run:

```bash
python -m pytest apx/tests -q
```

or:

```bash
python -m pytest apx/tests -v
```

---

# 16. Observability

APX includes an observability subsystem:

```text
apx/observability/
├── langfuse_tracer.py
├── logger.py
└── metrics.py
```

The current implementation provides infrastructure for:

- structured logging
- metrics
- tracing
- trace lifecycle handling
- error handling
- secret-safe tracing behavior

Langfuse integration is designed so development/testing can operate without requiring an external tracing service.

---

# 17. Research and Forensic Engineering

The project includes extensive engineering documentation created during retrieval/evaluation debugging and validation.

Important documents include:

```text
PROJECT_STATUS_AUDIT.md
ROOT_CAUSE_REPORT.md
APX_RETRIEVAL_GROUND_TRUTH_REPAIR.md
PHASE5_REPORT.md
docs/APX_IMPLEMENTATION_AUDIT.md
docs/APX_RETRIEVAL_FORENSIC_AUDIT.md
docs/APX_RETRIEVAL_STAGE_DIAGNOSTIC.md
docs/APX_EVIDENCE_FRESHNESS_AUDIT.md
docs/APX_GROUND_TRUTH_REPAIR_REPORT.md
docs/APX_TEMPORAL_FIX_REPORT.md
```

These documents are part of the engineering record and explain how retrieval/evaluation problems were diagnosed and repaired rather than hidden.

---

# 18. Current Repository Structure

```text
APX/
├── apx/
│   ├── action/
│   ├── agent/
│   │   └── llm/
│   ├── approval/
│   ├── config/
│   │   ├── retrieval_profiles.yaml
│   │   ├── risk_policy.yaml
│   │   └── settings.py
│   ├── data/
│   │   ├── datasets/
│   │   │   ├── eval/
│   │   │   └── evidence/
│   │   ├── generate_synthetic.py
│   │   └── split.py
│   ├── evaluation/
│   │   ├── action_eval.py
│   │   ├── benchmark.py
│   │   ├── business_eval.py
│   │   ├── decision_eval.py
│   │   ├── detection_eval.py
│   │   ├── extraction_eval.py
│   │   └── retrieval_eval.py
│   ├── evidence/
│   │   ├── bm25.py
│   │   ├── dates.py
│   │   ├── dense.py
│   │   ├── engine.py
│   │   ├── evaluate.py
│   │   ├── generate_evidence.py
│   │   ├── reranker.py
│   │   ├── schemas.py
│   │   └── ...
│   ├── exceptions/
│   ├── guardrail/
│   ├── intelligence/
│   ├── observability/
│   │   ├── langfuse_tracer.py
│   │   ├── logger.py
│   │   └── metrics.py
│   └── tests/
├── docs/
├── APX_V1_1_PHASE2_BUILD_BRIEF.md
├── APX_V1_1_PHASE5_BUILD_BRIEF.md
├── PHASE5_REPORT.md
├── PROJECT_STATUS_AUDIT.md
├── ROOT_CAUSE_REPORT.md
├── APX_RETRIEVAL_GROUND_TRUTH_REPAIR.md
├── STEP_6C_REPAIR_EVIDENCE_CORPUS_GROUND_TRUTH_METADATA.ipynb
├── diag_stage6b.py
├── pyproject.toml
└── README.md
```

---

# 19. Installation

## Clone

```bash
git clone https://github.com/eklakhdewan/APX-Autonomous-Accounts-Payable-Exception-Resolution-Agent.git
cd APX-Autonomous-Accounts-Payable-Exception-Resolution-Agent
```

## Install

```bash
python -m pip install -e .
```

For development:

```bash
python -m pip install -e ".[dev]"
```

---

# 20. Generate Synthetic Data

The project supports deterministic synthetic dataset generation.

```bash
python -m apx.data.generate_synthetic --seed 42
```

Example custom generation:

```bash
python -m apx.data.generate_synthetic \
    --vendors 35 \
    --pos 100 \
    --grns 75 \
    --invoices 500 \
    --seed 42
```

The same seed is intended to produce reproducible logical data.

---

# 21. Run Tests

Full suite:

```bash
python -m pytest apx/tests -q
```

Verbose:

```bash
python -m pytest apx/tests -v
```

Selected areas:

```bash
python -m pytest apx/tests/test_validator.py -v
python -m pytest apx/tests/test_evaluation.py -v
python -m pytest apx/tests/test_temporal_anchoring.py -v
python -m pytest apx/tests/test_tracing.py -v
python -m pytest apx/tests/test_phase4_action.py -v
```

---

# 22. Retrieval Development

The retrieval system is profile-driven.

The active profile is currently:

```text
DEV
```

The DEV profile is configured for CPU-oriented development and local model loading.

Relevant configuration:

```text
apx/config/retrieval_profiles.yaml
apx/config/settings.py
```

Before running retrieval experiments, verify that required model artifacts are available locally when:

```yaml
local_files_only: true
```

is enabled.

---

# 23. Evaluation Artifacts

Benchmark and evaluation results are persisted rather than only printed to stdout.

Typical locations:

```text
apx/evaluation/results/
apx/data/datasets/eval/
apx/data/datasets/evidence/
```

This supports:

- reproducibility
- regression analysis
- benchmark comparison
- auditability
- historical experiment tracking

---

# 24. Development Environment

The project has been exercised in the following environment during current development:

```text
Platform: Linux / WSL
Python: 3.14.4
Pytest: 9.1.1
CPU-oriented execution
```

Windows development is also supported through the project filesystem, while WSL is currently used for the reproducible Linux test environment.

---

# 25. Known Issues / Technical Debt

The current test suite passes, but the project is not being represented as production-complete.

Known technical debt includes:

### Python datetime deprecations

The current codebase still contains usages of:

```python
datetime.utcnow()
```

Python now recommends timezone-aware UTC timestamps.

This currently appears as warnings rather than test failures.

### Model/resource constraints

Large retrieval models and cross-encoders are substantially more resource-intensive than the DEV profile.

The repository therefore distinguishes DEV, EVAL, and PROD retrieval configurations.

### Benchmark maturity

The evaluation infrastructure exists, but benchmark interpretation must continue to distinguish:

- retrieval quality
- evidence quality
- decision quality
- action safety
- end-to-end business performance

A passing test suite alone is not evidence of production-grade autonomous resolution.

---

# 26. Phase Status

| Phase | Area | Status |
|---|---|---|
| Phase 1 | Deterministic validation foundation | ✅ Implemented |
| Phase 2 | Evidence/data foundation | ✅ Implemented |
| Phase 3 | Agent/state-machine foundation | ✅ Implemented |
| Phase 4 | Action/approval/guardrail foundation | ✅ Implemented |
| Phase 5 | Evaluation, benchmarking, retrieval analysis, observability | ✅ Implemented / frozen |
| Phase 6 | Next engineering stage | ⏳ Next |

### Current freeze point

**Phase 5 is the current completed/frozen milestone.**

Phase 6 should begin only after:

- repository state is committed
- README reflects the actual system
- tests remain green
- benchmark artifacts are preserved
- current limitations are documented

---

# 27. Roadmap

The next phase should build on the frozen Phase 5 foundation rather than rewriting completed components.

Future work is expected to focus on increasing system capability while preserving:

- deterministic validation
- evidence grounding
- risk controls
- human approval boundaries
- reproducibility
- observability
- evaluation discipline

The project should not sacrifice these controls merely to improve apparent autonomy.

---

# 28. Reproducibility

Synthetic data:

```bash
python -m apx.data.generate_synthetic --seed 42
```

Tests:

```bash
python -m pytest apx/tests -q
```

The repository stores evaluation artifacts and diagnostic documentation so important experiments can be inspected after execution.

---

# 29. Engineering Quality Bar

APX is intended to demonstrate more than an LLM wrapper.

The target architecture requires the system to answer:

```text
What happened?
      ↓
Which rule detected it?
      ↓
What evidence supports the finding?
      ↓
Was that evidence valid at the relevant time?
      ↓
How confident is the system?
      ↓
What is the financial/business risk?
      ↓
Should the system resolve, request approval, or escalate?
      ↓
What action was authorized?
      ↓
What action was actually executed?
      ↓
Can the complete decision be audited?
      ↓
Can the behavior be measured and reproduced?
```

That chain is the core engineering objective of APX.

---

# 30. Project Status

**Current status: Phase 5 frozen; Phase 6 is next.**

The repository currently has:

- deterministic AP exception validation
- structured exception taxonomy
- synthetic/reproducible data
- agent/state-machine infrastructure
- risk-aware decisions
- approval workflows
- guarded action execution
- retrieval infrastructure
- hybrid search
- reranking
- evidence validation
- temporal anchoring
- evaluation framework
- benchmark artifacts
- observability infrastructure
- forensic/research documentation
- **242 passing automated tests**

The system is therefore substantially beyond the original Phase 1 README and is ready for the next controlled development stage.

---

## License

See the repository license file.

## Author

**Eklakh Dewan**

Artificial Intelligence & Data Science

GitHub: `eklakhdewan/APX-Autonomous-Accounts-Payable-Exception-Resolution-Agent`
