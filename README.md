# APX — Autonomous Accounts Payable Exception Resolution Agent

> **Research-grade autonomous exception-resolution system for Accounts Payable (AP)**  
> Deterministic validation → evidence retrieval → decision intelligence → risk controls → approval → guarded action execution → persistence → API delivery → evaluation → observability.

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue)](#)
[![Version](https://img.shields.io/badge/version-0.4.0-informational)](#)
[![Phase](https://img.shields.io/badge/status-Phase%206B%20complete%20%2F%206C%20next-orange)](#)
[![Tests](https://img.shields.io/badge/Phase%206B-verified-brightgreen)](#)

---

## 1. Overview

**APX (Autonomous Accounts Payable Exception Resolution Agent)** is an engineering and research project for resolving Accounts Payable exceptions through a controlled, auditable autonomous workflow.

The system is built around one principle:

> **Automation must be evidence-grounded, risk-aware, observable, reproducible, persistent, and auditable.**

APX does **not** treat an LLM as the financial source of truth. Deterministic validation, evidence retrieval, risk policy, approval controls, persistence, and guarded action execution remain explicit system components.

### Current milestone

**Phase 6B is complete and pushed to `main`.**

Current Git checkpoint:

```text
dcefb95 feat: complete phase 6B API delivery
```

Phase 6A established the persistence foundation. Phase 6B added the application/service layer and HTTP API delivery on top of that foundation.

**Phase 6C has not started.**

---

# 2. Problem

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
8. **What was persisted?**
9. **Can the entire decision be audited and evaluated?**

APX is designed around that complete decision pipeline.

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
                         │          R1–R10           │
                         └─────────────┬─────────────┘
                                       │
                                       ▼
                         ┌───────────────────────────┐
                         │     Evidence Retrieval    │
                         │                           │
                         │  BM25 + Dense + Hybrid    │
                         │       RRF + Reranker      │
                         └─────────────┬─────────────┘
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
                         │     + Decision Logic      │
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
                         │ Run                       │
                         └─────────────┬─────────────┘
                                       │
                                       ▼
                         ┌───────────────────────────┐
                         │      Persistence Layer    │
                         │ SQLite / SQLAlchemy /     │
                         │ Repositories / Alembic    │
                         └─────────────┬─────────────┘
                                       │
                                       ▼
                         ┌───────────────────────────┐
                         │       FastAPI Layer       │
                         │ Auth / RBAC / Services /  │
                         │ Invoices / Cases /        │
                         │ Approvals / Audit /       │
                         │ Metrics / Health          │
                         └─────────────┬─────────────┘
                                       │
                                       ▼
                         ┌───────────────────────────┐
                         │ Evaluation + Observability│
                         │ Metrics / Tracing / Logs  │
                         └───────────────────────────┘
```

---

# 4. Engineering Principles

### 4.1 Deterministic financial truth

Financial validation is not delegated to an LLM.

The deterministic validation layer implements the AP exception taxonomy and performs structured comparisons using controlled business rules.

### 4.2 Evidence before reasoning

Retrieval provides supporting evidence for decisions.

APX separates:

- candidate retrieval
- ranking
- reranking
- evidence validation
- temporal anchoring
- downstream decision use

### 4.3 Risk-aware autonomy

Not every exception should be automatically resolved.

The system incorporates:

- monetary risk
- exception severity
- confidence
- evidence sufficiency
- historical success
- explicit escalation rules
- explicit auto-resolution rules

### 4.4 Human-in-the-loop controls

Human approval is a control boundary, not an afterthought.

### 4.5 Persistent state

Phase 6 introduces a persistence boundary so invoices, cases, approvals, actions, and audit information can survive beyond a single process execution.

### 4.6 API as a delivery boundary

Phase 6B exposes the application through a FastAPI layer with authentication, role-based access control, request tracing, and domain-oriented endpoints.

### 4.7 Observable execution

Investigation, decisions, API requests, and action execution are designed to be traceable.

### 4.8 Reproducible evaluation

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

# 6. Phase Status

| Phase | Area | Status |
|---|---|---|
| Phase 1 | Deterministic validation foundation | ✅ Complete |
| Phase 2 | Evidence/data foundation | ✅ Complete |
| Phase 3 | Agent/state-machine foundation | ✅ Complete |
| Phase 4 | Action/approval/guardrail foundation | ✅ Complete |
| Phase 5 | Evaluation, benchmarking, retrieval analysis, temporal anchoring, observability | ✅ Complete / Frozen |
| Phase 6A | SQLite persistence foundation | ✅ Complete |
| Phase 6B | Application services + FastAPI API delivery | ✅ Complete |
| Phase 6C | Next persistence/application integration stage | ⏳ Next |

### Current freeze point

**Phase 6B is the current completed milestone.**

The repository is clean and synchronized with GitHub at:

```text
dcefb95 (HEAD -> main, origin/main)
feat: complete phase 6B API delivery
```

---

# 7. Implemented System Components

## 7.1 Data and Domain Layer

The project contains canonical domain schemas and synthetic data generation for reproducible development and testing.

Capabilities include:

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

## 7.2 Deterministic Validation

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

# 8. Agent Layer

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

# 9. Retrieval and Evidence Pipeline

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

DEV currently uses:

```text
BAAI/bge-small-en-v1.5
```

### Hybrid retrieval

Sparse and dense retrieval are combined through reciprocal-rank fusion.

### Cross-encoder reranking

DEV currently uses:

```text
BAAI/bge-reranker-base
```

### Local model control

Development and evaluation profiles support:

```yaml
local_files_only: true
```

This prevents accidental model downloads where reproducibility or offline execution is required.

Production remains configurable.

---

# 10. Retrieval Profiles

| Profile | Dense Model | Reranker | Device | Local Only |
|---|---|---|---|---|
| DEV | `BAAI/bge-small-en-v1.5` | `BAAI/bge-reranker-base` | CPU | Yes |
| EVAL | `BAAI/bge-large-en-v1.5` | `BAAI/bge-reranker-large` | CPU | Yes |
| PROD | Environment-configurable | Environment-configurable | Environment-configurable | No |

Configuration:

```text
apx/config/retrieval_profiles.yaml
apx/config/settings.py
```

---

# 11. Evidence Quality and Temporal Anchoring

APX does not treat every retrieved document as equally valid evidence.

The evidence subsystem includes:

- evidence schemas
- evidence validity checks
- evidence generation utilities
- evidence evaluation
- date extraction/handling
- temporal anchoring
- freshness-oriented analysis

This is important for AP because a relevant policy or vendor record may be invalid if it was not applicable at the time of the transaction.

---

# 12. Risk and Decision Layer

The risk engine combines multiple signals.

Current policy dimensions include:

- amount risk
- severity risk
- confidence risk
- evidence risk
- historical risk

Configured compound weighting:

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

---

# 13. Action, Approval, and Guardrails

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

The guardrail layer adds:

- risk checks
- approval checks
- rate/window controls
- idempotency protection
- action constraints
- escalation behavior
- execution logging

> **A model decision does not directly imply an irreversible business action.**

---

# 14. Phase 6A — Persistence Foundation

Phase 6A introduced the durable persistence boundary.

Implemented components:

```text
apx/persistence/
├── __init__.py
├── config.py
├── database.py
├── models.py
├── repositories.py
├── sqlite_repos.py
└── migrations/
    ├── alembic.ini
    ├── env.py
    └── versions/
        └── 001_initial.py
```

### Persistence technology

- SQLite
- SQLAlchemy
- Alembic
- repository abstraction
- SQLite repository implementations

The persistence layer is designed to isolate storage concerns from business/application logic.

---

# 15. Phase 6B — API Delivery

Phase 6B added the application/service layer and HTTP API.

## API structure

```text
apx/api/
├── app.py
├── config.py
├── middleware.py
├── schemas.py
└── routes/
    ├── approvals.py
    ├── audit.py
    ├── cases.py
    ├── health.py
    ├── invoices.py
    └── metrics.py
```

## Application services

```text
apx/application/services/
├── approval_service.py
├── audit_service.py
├── case_service.py
├── invoice_service.py
└── metrics_service.py
```

### API capabilities

The Phase 6B delivery includes endpoints and service boundaries for:

- health/readiness
- invoice operations
- case operations
- approval operations
- audit access
- metrics
- authentication
- role-based access control
- request IDs
- structured request logging
- API error handling

### Authentication

API access supports configured API keys mapped to roles.

The test configuration uses roles such as:

```text
admin
operator
approver
reader
```

The API layer therefore provides an explicit authorization boundary instead of exposing domain operations directly.

---

# 16. Evaluation Framework

The evaluation package contains separate components for:

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

Evaluation dimensions include:

- retrieval quality
- detection
- extraction
- decision quality
- business outcomes
- action behavior
- benchmark performance

Artifacts are stored under:

```text
apx/evaluation/results/
```

---

# 17. Observability

APX includes:

```text
apx/observability/
├── langfuse_tracer.py
├── logger.py
└── metrics.py
```

Capabilities include:

- structured logging
- metrics
- tracing
- trace lifecycle handling
- error handling
- secret-safe tracing behavior

Development/testing can operate without requiring an external tracing service.

---

# 18. Verification and Test Discipline

The repository has been verified across the Phase 1–6 development cycle.

The Phase 6B verification work specifically covered:

- API authentication behavior
- invoice endpoints
- case endpoints
- approval endpoints
- audit endpoints
- metrics/health endpoints
- persistence behavior
- repository serialization
- UUID boundary behavior
- complete-suite regression checking

### Phase 6B baseline

During Phase 6B verification, the complete suite reached:

```text
365 collected
357 passed
8 remaining baseline failures
1 skipped
```

The remaining failures were investigated rather than blindly relabeled. Phase 6B work was constrained to its intended boundary, and frozen Phase 1–5 components were not rewritten to make the suite appear green.

Run the complete suite with:

```bash
python -m pytest apx/tests -q
```

For API tests:

```bash
python -m pytest apx/tests/test_api.py -q
```

For persistence:

```bash
python -m pytest apx/tests/test_persistence.py -q
```

> **Important:** A passing unit-test count is not, by itself, evidence of production-grade autonomous resolution. APX treats benchmark quality, evidence validity, decision quality, and action safety as separate concerns.

---

# 19. Research and Forensic Engineering

The repository contains engineering documentation produced during retrieval/evaluation debugging and Phase 6 implementation.

Important documents include:

```text
PROJECT_STATUS_AUDIT.md
ROOT_CAUSE_REPORT.md
APX_RETRIEVAL_GROUND_TRUTH_REPAIR.md
PHASE5_REPORT.md
PHASE6A_REPORT.md
PHASE6_GAP_AUDIT.md
PHASE6B_REPORT.md
docs/APX_IMPLEMENTATION_AUDIT.md
docs/APX_RETRIEVAL_FORENSIC_AUDIT.md
docs/APX_RETRIEVAL_STAGE_DIAGNOSTIC.md
docs/APX_EVIDENCE_FRESHNESS_AUDIT.md
docs/APX_GROUND_TRUTH_REPAIR_REPORT.md
docs/APX_TEMPORAL_FIX_REPORT.md
```

These documents preserve the engineering record, including root-cause analysis and verification decisions.

---

# 20. Repository Structure

```text
APX/
├── apx/
│   ├── action/
│   ├── agent/
│   │   └── llm/
│   ├── api/
│   │   └── routes/
│   ├── application/
│   │   └── services/
│   ├── approval/
│   ├── config/
│   ├── data/
│   │   └── datasets/
│   ├── evaluation/
│   ├── evidence/
│   ├── exceptions/
│   ├── guardrail/
│   ├── intelligence/
│   ├── observability/
│   ├── persistence/
│   │   └── migrations/
│   └── tests/
├── docs/
├── APX_V1_1_PHASE2_BUILD_BRIEF.md
├── APX_V1_1_PHASE5_BUILD_BRIEF.md
├── PHASE5_REPORT.md
├── PHASE6A_REPORT.md
├── PHASE6_GAP_AUDIT.md
├── PHASE6B_REPORT.md
├── PROJECT_STATUS_AUDIT.md
├── ROOT_CAUSE_REPORT.md
├── APX_RETRIEVAL_GROUND_TRUTH_REPAIR.md
├── pyproject.toml
└── README.md
```

---

# 21. Installation

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

The Phase 6 API stack includes:

```text
fastapi
uvicorn
python-multipart
httpx
```

Persistence includes:

```text
sqlalchemy
alembic
pydantic-settings
```

---

# 22. Generate Synthetic Data

The project supports deterministic synthetic dataset generation.

```bash
python -m apx.data.generate_synthetic --seed 42
```

Example:

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

# 23. Run Tests

Full suite:

```bash
python -m pytest apx/tests -q
```

Verbose:

```bash
python -m pytest apx/tests -v
```

API:

```bash
python -m pytest apx/tests/test_api.py -q
```

Persistence:

```bash
python -m pytest apx/tests/test_persistence.py -q
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

# 24. Running the API

The FastAPI application is exposed through the APX API package.

Typical development command:

```bash
uvicorn apx.api.app:app --reload
```

If the project exposes the application through its factory instead:

```bash
uvicorn apx.api.app:create_app --factory --reload
```

Authentication is configured through the API configuration layer rather than hard-coded business logic.

For local testing, use the API-key configuration expected by the test suite.

---

# 25. Retrieval Development

The retrieval system is profile-driven.

The active development profile is:

```text
DEV
```

The DEV profile is CPU-oriented and configured for local model loading.

Relevant configuration:

```text
apx/config/retrieval_profiles.yaml
apx/config/settings.py
```

Before running retrieval experiments, verify required model artifacts are available locally when:

```yaml
local_files_only: true
```

is enabled.

---

# 26. Evaluation Artifacts

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

# 27. Development Environment

The current development workflow has used:

```text
Windows host
WSL/Linux execution environment
Python 3.14.x for the current verification environment
CPU-oriented execution
```

The project metadata declares:

```text
Python >= 3.11
```

Use the environment in which the project's dependencies are installed when running tests and development commands.

---

# 28. Known Technical Debt

The project is **not being represented as production-complete**.

### Python datetime deprecations

The codebase still contains usages of:

```python
datetime.utcnow()
```

Python recommends timezone-aware UTC timestamps. These currently surface as warnings in parts of the test suite.

### Retrieval resource constraints

Large embedding and reranking models require substantially more resources than the DEV configuration.

The repository therefore distinguishes:

- DEV
- EVAL
- PROD

retrieval profiles.

### API verification baseline

The Phase 6B verification cycle exposed remaining test-suite failures that require careful classification and follow-up. They should not be hidden by modifying frozen components merely to obtain a green aggregate number.

### Benchmark maturity

The evaluation infrastructure exists, but benchmark interpretation must distinguish:

- retrieval quality
- evidence quality
- decision quality
- action safety
- end-to-end business performance

---

# 29. Roadmap

The next development stage is **Phase 6C**.

Phase 6C should build on the frozen Phase 6A/6B foundation rather than rewriting completed components.

The next work must preserve:

- deterministic validation
- evidence grounding
- risk controls
- human approval boundaries
- persistence integrity
- API authorization
- reproducibility
- observability
- evaluation discipline

The objective is to increase system capability without weakening safety or auditability.

---

# 30. Reproducibility

Synthetic data:

```bash
python -m apx.data.generate_synthetic --seed 42
```

Tests:

```bash
python -m pytest apx/tests -q
```

Evaluation artifacts are stored in-repository so important experiments can be inspected after execution.

Git checkpoint:

```text
dcefb95 feat: complete phase 6B API delivery
```

The `main` branch is currently synchronized with GitHub at this checkpoint.

---

# 31. Engineering Quality Bar

APX is intended to demonstrate more than an LLM wrapper.

The system must be able to answer:

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
What state was persisted?
      ↓
What action was actually executed?
      ↓
Can the complete decision be audited?
      ↓
Can the behavior be measured and reproduced?
```

That chain is the core engineering objective of APX.

---

# 32. Project Status

**Current status: Phase 6B complete and frozen; Phase 6C next.**

APX currently contains:

- deterministic AP exception validation
- R1–R10 exception taxonomy
- synthetic/reproducible data
- agent/state-machine infrastructure
- risk-aware decisions
- approval workflows
- guarded action execution
- retry/compensation/DLQ controls
- hybrid BM25 + dense retrieval
- reciprocal-rank fusion
- cross-encoder reranking
- evidence validation
- temporal anchoring
- evaluation and benchmark infrastructure
- observability infrastructure
- SQLite/SQLAlchemy persistence
- Alembic migration foundation
- repository abstractions
- application services
- FastAPI API delivery
- API authentication and RBAC
- health, invoice, case, approval, audit, and metrics routes
- forensic/research documentation
- Phase 6A and 6B verification reports

### Current Git state

```text
HEAD -> main
origin/main -> main

dcefb95 feat: complete phase 6B API delivery
```

**Phase 6C is the next controlled development milestone.**

---

## License

See the repository license file.

## Author

**Eklakh Dewan**

Artificial Intelligence & Data Science

Repository:

`https://github.com/eklakhdewan/APX-Autonomous-Accounts-Payable-Exception-Resolution-Agent`
