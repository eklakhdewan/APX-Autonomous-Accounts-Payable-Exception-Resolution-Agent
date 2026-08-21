# APX --- Autonomous Accounts Payable Exception Resolution Agent

> **A controlled, evidence-grounded autonomous system for Accounts
> Payable exception resolution.**
>
> Deterministic validation → evidence retrieval → investigation → risk
> decision → approval → guarded action → persistence → API delivery →
> observability → evaluation.

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](#)
[![Version](https://img.shields.io/badge/version-0.4.0-informational)](#)
[![Status](https://img.shields.io/badge/status-Phase%206D%20complete-success)](#)
[![Tests](https://img.shields.io/badge/Phase%206D-verified-success)](#)

------------------------------------------------------------------------

## 1. What is APX?

**APX (Autonomous Accounts Payable Exception Resolution Agent)** is an
engineering and research system for resolving Accounts Payable
exceptions through a controlled, auditable workflow.

The central design principle is:

> **An autonomous decision is only useful when the system can explain,
> constrain, persist, observe, and evaluate it.**

APX therefore does **not** make an LLM the financial source of truth.
Deterministic business validation, evidence retrieval, temporal
validity, risk policy, approval boundaries, guarded execution,
persistence, and observability remain explicit system components.

### Current milestone

**Phase 6D --- Observability & Security is complete.**

Current repository checkpoint:

``` text
6e509df feat: complete phase 6D observability and security
```

`main` is synchronized with `origin/main` at this checkpoint.

------------------------------------------------------------------------

## 2. The APX Decision Pipeline

``` text
                    ┌─────────────────────────┐
                    │      AP Exception       │
                    │        / Invoice        │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │ Deterministic Validation│
                    │          R1–R10         │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │    Evidence Retrieval   │
                    │ BM25 + Dense + Hybrid   │
                    │ RRF + Cross-Encoder     │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │ Evidence Validation +   │
                    │ Temporal Anchoring      │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │ Agent Investigation +   │
                    │ Decision Logic          │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │ Risk Engine             │
                    │ amount / severity /     │
                    │ confidence / evidence / │
                    │ historical risk         │
                    └────────────┬────────────┘
                                 │
                   ┌─────────────┼─────────────┐
                   ▼             ▼             ▼
              AUTO-RESOLVE   HUMAN REVIEW   ESCALATE
                   │             │             │
                   └─────────────┼─────────────┘
                                 ▼
                    ┌─────────────────────────┐
                    │ Approval + Guardrails   │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │ Guarded Action Engine   │
                    │ retry / compensation /  │
                    │ idempotency / DLQ /     │
                    │ dry-run                 │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │ Persistence              │
                    │ SQLite / SQLAlchemy /    │
                    │ repositories / Alembic   │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │ FastAPI Delivery Layer   │
                    │ auth / RBAC / services   │
                    │ invoices / cases /       │
                    │ approvals / audit /      │
                    │ metrics / health         │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │ Observability +          │
                    │ Evaluation               │
                    └─────────────────────────┘
```

This architecture deliberately separates **decision**,
**authorization**, and **execution**.

> **A model decision does not directly imply an irreversible business
> action.**

------------------------------------------------------------------------

## 3. Engineering Principles

### 3.1 Deterministic financial truth

Core AP validation is explicit and reproducible. Financial correctness
is not delegated to generative text.

### 3.2 Evidence before reasoning

Retrieved evidence is treated as a first-class artifact. APX separates
retrieval, ranking, reranking, validity checks, and downstream use.

### 3.3 Risk-aware autonomy

The system distinguishes between cases that can be resolved
automatically, cases requiring human approval, and cases that must be
escalated.

### 3.4 Human approval as a control boundary

Approval is part of the architecture, not an afterthought added around
the agent.

### 3.5 Guarded execution

Actions are constrained by authorization, risk, idempotency,
retry/compensation behavior, and execution controls.

### 3.6 Persistent state

Invoices, cases, approvals, actions, and audit information have a
durable persistence boundary.

### 3.7 Observable execution

API requests, decisions, actions, and relevant system events are
designed to be traceable and measurable.

### 3.8 Reproducible evaluation

Benchmarking and evaluation artifacts are persisted so results can be
inspected and compared rather than treated as one-off demonstrations.

------------------------------------------------------------------------

# 4. Exception Taxonomy --- R1--R10

  -----------------------------------------------------------------------
  Code                    Exception               Meaning
  ----------------------- ----------------------- -----------------------
  R1                      `VENDOR_MISMATCH`       Invoice vendor is
                                                  inconsistent with the
                                                  expected vendor

  R2                      `PO_MISMATCH`           Purchase-order
                                                  reference is missing,
                                                  invalid, or
                                                  inconsistent

  R3                      `AMOUNT_MISMATCH`       Invoice amount differs
                                                  from expected PO amount
                                                  under configured rules

  R4                      `GRN_MISMATCH`          Invoiced quantity
                                                  exceeds received
                                                  quantity

  R5                      `DUPLICATE_INVOICE`     Duplicate
                                                  vendor/invoice
                                                  combination

  R6                      `TAX_ERROR`             Tax calculation or
                                                  expected tax data is
                                                  inconsistent

  R7                      `CURRENCY_MISMATCH`     Invoice, PO, or vendor
                                                  currency is
                                                  inconsistent

  R8                      `LINE_ITEM_MISMATCH`    Line-item
                                                  quantity/price differs
                                                  from expected data

  R9                      `DISCOUNT_ERROR`        Discount differs from
                                                  expected business data

  R10                     `CREDIT_ISSUE`          Vendor credit status is
                                                  HOLD, SUSPENDED, or
                                                  BLOCKED
  -----------------------------------------------------------------------

------------------------------------------------------------------------

# 5. Phase Status

  -----------------------------------------------------------------------
  Phase                   Scope                   Status
  ----------------------- ----------------------- -----------------------
  Phase 1                 Deterministic           ✅ Complete
                          validation foundation   

  Phase 2                 Evidence and data       ✅ Complete
                          foundation              

  Phase 3                 Agent and state-machine ✅ Complete
                          foundation              

  Phase 4                 Action, approval, risk, ✅ Complete
                          and guardrails          

  Phase 5                 Evaluation,             ✅ Complete / Frozen
                          benchmarking, retrieval 
                          analysis, temporal      
                          anchoring,              
                          observability           
                          foundation              

  Phase 6A                SQLite persistence      ✅ Complete
                          foundation              

  Phase 6B                Application services +  ✅ Complete
                          FastAPI API delivery    

  Phase 6C                Case and approval       ✅ Complete
                          lifecycle integration   

  Phase 6D                Observability and API   ✅ Complete
                          security                
  -----------------------------------------------------------------------

### Current freeze point

**Phase 6D is the latest completed milestone.**

``` text
6e509df (HEAD -> main, origin/main)
feat: complete phase 6D observability and security
```

No claim of production readiness is implied by this milestone.

------------------------------------------------------------------------

# 6. Phase 6D --- Observability & Security

Phase 6D hardens the API boundary without changing the core
deterministic decision architecture.

## Observability

Implemented capabilities include:

-   Structured JSON request lifecycle logging:
    -   `request.start`
    -   `request.end`
    -   `request.error`
-   `X-Request-ID` propagation
-   `X-Correlation-ID` propagation
-   W3C `traceparent` / `tracestate` propagation at the API boundary
-   Per-endpoint latency metrics
-   API request counters
-   API error counters
-   Centralized recursive sensitive-data redaction
-   Optional request/response body redaction
-   Redaction of audit payloads and metadata before persistence

## Security

Implemented capabilities include:

-   In-process token-bucket rate limiting
-   Configurable request-rate limits
-   `429 Too Many Requests` responses with `Retry-After`
-   Request-size enforcement using `Content-Length`
-   `413 Request Entity Too Large` handling
-   Security response headers
-   CSP configuration compatible with the development Swagger UI
-   `X-Content-Type-Options: nosniff`
-   `X-Frame-Options: DENY`
-   `X-XSS-Protection`
-   `Referrer-Policy`
-   `Permissions-Policy`
-   Conditional HSTS for HTTPS
-   Removal of the `Server` response header
-   Existing API-key authentication and RBAC preserved

### Important scope boundaries

Phase 6D rate limiting is **in-process**. It is not a distributed rate
limiter.

W3C trace context is implemented at the **API boundary**. This does not
claim a complete distributed tracing deployment.

HSTS is applied only when the deployment is operating over HTTPS. The
application itself does not provide TLS termination.

------------------------------------------------------------------------

# 7. Verification

Phase 6D verification was performed before generating and committing
`PHASE6D_REPORT.md`.

  Verification area                                                              Result
  ----------------------------------------------- -------------------------------------
  Phase 6D focused observability/security tests                           **30 passed**
  Tracing regression suite                                                **23 passed**
  Persistence regression suite                                            **56 passed**
  Validator regression suite                                              **31 passed**
  Phase 2 evidence regression                                             **16 passed**
  Phase 4 risk regression                                                 **11 passed**
  Phase 4 guardrail regression                                            **14 passed**
  Phase 4 action regression                                               **29 passed**
  API suite                                              **60 passed, 1 expected skip**
  Regression accounting                             **180 passed, 0 failed, 0 skipped**

Detailed Phase 6D verification record:

``` text
PHASE6D_REPORT.md
```

### Test commands

Full suite:

``` bash
python -m pytest apx/tests -q
```

API:

``` bash
python -m pytest apx/tests/test_api.py -q
```

Persistence:

``` bash
python -m pytest apx/tests/test_persistence.py -q
```

Tracing:

``` bash
python -m pytest apx/tests/test_tracing.py -q
```

------------------------------------------------------------------------

# 8. System Architecture by Layer

``` text
apx/
├── data/            Domain schemas + deterministic synthetic data
├── exceptions/      AP exception taxonomy
├── intelligence/    Validation / intelligence components
├── evidence/        Retrieval, ranking, evidence validation
├── agent/           Investigation and state-machine control
├── risk/             Risk scoring and policy
├── approval/         Approval decision boundary
├── guardrail/        Action safety controls
├── action/           Action planning and execution
├── persistence/      Durable state + repositories + migrations
├── application/      Application/service orchestration
├── api/              FastAPI delivery boundary
├── observability/    Logging, metrics, tracing, redaction
├── evaluation/       Benchmark and evaluation framework
└── tests/            Regression and integration coverage
```

The important architectural separation is:

``` text
Domain logic
    ↓
Application services
    ↓
API boundary
    ↓
Persistence / observability / external delivery
```

The API layer is therefore not the business-logic layer.

------------------------------------------------------------------------

# 9. Data and Domain Layer

APX contains canonical domain schemas and reproducible synthetic data
generation.

The development data model covers:

-   vendors
-   purchase orders
-   goods receipts
-   invoices
-   line items
-   exception labels
-   linked relational records
-   deterministic synthetic generation
-   dataset splitting
-   data-integrity validation

Synthetic data can be generated from a fixed seed for repeatable
experiments.

------------------------------------------------------------------------

# 10. Deterministic Validation

The validation layer implements the R1--R10 exception taxonomy without
requiring an LLM.

Key properties:

-   deterministic behavior
-   reproducible outputs
-   structured Pydantic models
-   Decimal-based monetary handling
-   configurable tolerance rules
-   duplicate detection
-   multiple-exception handling
-   boundary-condition testing

This layer establishes the financial facts that downstream reasoning
operates on.

------------------------------------------------------------------------

# 11. Evidence and Retrieval

APX uses a multi-stage retrieval pipeline:

``` text
Query
  │
  ├──────────────► BM25 / Sparse Retrieval
  │
  └──────────────► Dense Semantic Retrieval
                          │
                          ▼
                    Hybrid Fusion
                          │
                          ▼
                         RRF
                          │
                          ▼
                 Cross-Encoder Reranking
                          │
                          ▼
                   Evidence Candidates
                          │
                          ▼
                  Validity Checks
                          │
                          ▼
                 Temporal Anchoring
```

### Sparse retrieval

BM25 provides lexical retrieval and is useful for exact invoice IDs,
vendor names, PO references, codes, and domain terminology.

### Dense retrieval

Dense retrieval provides semantic matching using Sentence Transformers.

### Hybrid retrieval

Sparse and dense candidates are combined through reciprocal-rank fusion.

### Reranking

A cross-encoder reranker refines candidate ordering before evidence is
consumed downstream.

### Evidence validity

APX distinguishes between:

-   retrieved content
-   relevant content
-   valid evidence
-   temporally applicable evidence

That distinction is critical in financial workflows.

------------------------------------------------------------------------

# 12. Temporal Anchoring

A policy or business record can be semantically relevant while still
being invalid for the transaction date.

The evidence subsystem therefore includes:

-   date extraction
-   temporal anchoring
-   freshness-oriented analysis
-   evidence validity checks

This prevents retrieval relevance from being treated as automatic proof.

------------------------------------------------------------------------

# 13. Agent and State Machine

The agent layer provides controlled investigation rather than an
unconstrained autonomous loop.

It includes:

-   investigation steps
-   state-machine transitions
-   investigation budgets
-   LLM provider abstraction
-   mock LLM support for deterministic development
-   integration with evidence/retrieval components

The architecture intentionally constrains agent behavior around explicit
system state and decision boundaries.

------------------------------------------------------------------------

# 14. Risk and Decision Layer

The risk engine considers multiple signals, including:

-   monetary amount
-   exception severity
-   decision confidence
-   evidence sufficiency
-   historical risk

Current compound weighting:

  Signal         Weight
  ------------ --------
  Amount           0.25
  Severity         0.25
  Confidence       0.20
  Evidence         0.15
  Historical       0.15

The policy layer also supports:

-   auto-resolution thresholds
-   review thresholds
-   escalation thresholds
-   always-escalate conditions
-   explicit auto-resolution conditions
-   tolerance configuration

------------------------------------------------------------------------

# 15. Approval, Guardrails, and Action Execution

APX separates authorization from execution.

## Approval

Approval workflows provide a human control boundary for cases that
should not be autonomously finalized.

## Guardrails

Guardrails enforce constraints such as:

-   risk checks
-   approval checks
-   idempotency
-   rate/window controls
-   action constraints
-   escalation behavior

## Action execution

The action subsystem supports:

-   action planning
-   execution
-   retry handling
-   compensation handling
-   dead-letter queue behavior
-   dry-run mode
-   execution history
-   approval history
-   timestamps

The resulting flow is:

``` text
Decision
  ↓
Risk evaluation
  ↓
Approval requirement
  ↓
Guardrail validation
  ↓
Authorized action
  ↓
Execution
  ↓
Persisted/auditable result
```

------------------------------------------------------------------------

# 16. Phase 6A --- Persistence

Phase 6A established the durable storage boundary.

``` text
apx/persistence/
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

Technology:

-   SQLite
-   SQLAlchemy
-   Alembic
-   repository abstraction
-   SQLite repository implementations

The persistence boundary keeps storage concerns separate from
application services.

------------------------------------------------------------------------

# 17. Phase 6B --- API Delivery

Phase 6B introduced the application/service layer and FastAPI delivery
boundary.

``` text
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

Application services:

``` text
apx/application/services/
├── approval_service.py
├── audit_service.py
├── case_service.py
├── invoice_service.py
└── metrics_service.py
```

The API provides domain-oriented access for:

-   health/readiness
-   invoices
-   cases
-   approvals
-   audit
-   metrics

It also establishes:

-   API-key authentication
-   role-based access control
-   request identifiers
-   structured API error handling
-   service-layer boundaries

Test roles include:

``` text
admin
operator
approver
reader
```

------------------------------------------------------------------------

# 18. Observability Foundation

The observability package contains:

``` text
apx/observability/
├── langfuse_tracer.py
├── logger.py
├── metrics.py
└── redaction.py
```

The current stack covers:

-   structured logging
-   metrics
-   tracing
-   trace lifecycle handling
-   secret-safe tracing
-   centralized sensitive-data redaction
-   API observability
-   audit redaction

External tracing infrastructure is not required for local regression
testing.

------------------------------------------------------------------------

# 19. Evaluation Framework

Evaluation is separated into distinct dimensions rather than collapsed
into one score.

``` text
apx/evaluation/
├── action_eval.py
├── benchmark.py
├── business_eval.py
├── decision_eval.py
├── detection_eval.py
├── extraction_eval.py
└── retrieval_eval.py
```

Evaluation areas include:

-   retrieval quality
-   exception detection
-   extraction
-   decision quality
-   business outcomes
-   action behavior
-   benchmark performance

Artifacts are stored under:

``` text
apx/evaluation/results/
```

This supports regression analysis and historical experiment inspection.

------------------------------------------------------------------------

# 20. Retrieval Profiles

Retrieval configuration is profile-driven.

  ---------------------------------------------------------------------------------------------------------------
  Profile        Dense model                Reranker                    Device                     Local-only
  -------------- -------------------------- --------------------------- -------------------------- --------------
  DEV            `BAAI/bge-small-en-v1.5`   `BAAI/bge-reranker-base`    CPU                        Yes

  EVAL           `BAAI/bge-large-en-v1.5`   `BAAI/bge-reranker-large`   CPU                        Yes

  PROD           Environment-configurable   Environment-configurable    Environment-configurable   No
  ---------------------------------------------------------------------------------------------------------------

Relevant configuration:

``` text
apx/config/retrieval_profiles.yaml
apx/config/settings.py
```

The local-only setting supports reproducible/offline development when
required.

------------------------------------------------------------------------

# 21. Repository Structure

``` text
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
│   ├── evaluation/
│   ├── evidence/
│   ├── exceptions/
│   ├── guardrail/
│   ├── intelligence/
│   ├── observability/
│   ├── persistence/
│   │   └── migrations/
│   ├── risk/
│   └── tests/
├── docs/
├── PHASE5_REPORT.md
├── PHASE6A_REPORT.md
├── PHASE6_GAP_AUDIT.md
├── PHASE6B_REPORT.md
├── PHASE6C_REPORT.md
├── PHASE6D_REPORT.md
├── PROJECT_STATUS_AUDIT.md
├── ROOT_CAUSE_REPORT.md
├── pyproject.toml
└── README.md
```

The repository also contains historical forensic and research
documentation from earlier retrieval/evaluation work.

------------------------------------------------------------------------

# 22. Installation

## Clone

``` bash
git clone https://github.com/eklakhdewan/APX-Autonomous-Accounts-Payable-Exception-Resolution-Agent.git
cd APX-Autonomous-Accounts-Payable-Exception-Resolution-Agent
```

## Install

``` bash
python -m pip install -e .
```

Development dependencies:

``` bash
python -m pip install -e ".[dev]"
```

The project metadata declares:

``` text
Python >= 3.11
```

Phase 6 API dependencies include:

``` text
fastapi
uvicorn
python-multipart
httpx
```

Persistence dependencies include:

``` text
sqlalchemy
alembic
pydantic-settings
```

------------------------------------------------------------------------

# 23. Generate Synthetic Data

Deterministic synthetic generation:

``` bash
python -m apx.data.generate_synthetic --seed 42
```

Example:

``` bash
python -m apx.data.generate_synthetic \
    --vendors 35 \
    --pos 100 \
    --grns 75 \
    --invoices 500 \
    --seed 42
```

A fixed seed is intended to produce reproducible logical datasets.

------------------------------------------------------------------------

# 24. Run the API

Development:

``` bash
uvicorn apx.api.app:app --reload
```

If the application is exposed as a factory:

``` bash
uvicorn apx.api.app:create_app --factory --reload
```

Authentication is configured through the API configuration layer.

For local testing, use the API-key configuration expected by the test
suite rather than committing real credentials.

------------------------------------------------------------------------

# 25. Run Tests

Full suite:

``` bash
python -m pytest apx/tests -q
```

Verbose:

``` bash
python -m pytest apx/tests -v
```

API:

``` bash
python -m pytest apx/tests/test_api.py -q
```

Persistence:

``` bash
python -m pytest apx/tests/test_persistence.py -q
```

Tracing:

``` bash
python -m pytest apx/tests/test_tracing.py -q
```

Selected regression areas:

``` bash
python -m pytest apx/tests/test_validator.py -v
python -m pytest apx/tests/test_phase2_evidence.py -v
python -m pytest apx/tests/test_phase4_risk.py -v
python -m pytest apx/tests/test_phase4_guardrail.py -v
python -m pytest apx/tests/test_phase4_action.py -v
```

------------------------------------------------------------------------

# 26. Reproducibility

Synthetic data:

``` bash
python -m apx.data.generate_synthetic --seed 42
```

Tests:

``` bash
python -m pytest apx/tests -q
```

Evaluation artifacts:

``` text
apx/evaluation/results/
```

The project records important evaluation outputs in-repository to
support:

-   regression analysis
-   benchmark comparison
-   reproducibility
-   auditability
-   historical experiment tracking

------------------------------------------------------------------------

# 27. Verification Discipline

APX treats test results as evidence, not as a substitute for engineering
judgment.

A green test suite does not automatically establish:

-   production readiness
-   business correctness
-   retrieval quality
-   evidence validity
-   safe autonomous execution
-   distributed operational resilience

Those are separate engineering questions.

The project therefore preserves:

-   phase reports
-   forensic audits
-   benchmark artifacts
-   regression suites
-   implementation boundaries
-   explicit freeze points

When a regression is found, the intended process is:

``` text
Reproduce
   ↓
Localize
   ↓
Identify root cause
   ↓
Determine phase ownership
   ↓
Fix only within the permitted boundary
   ↓
Run focused tests
   ↓
Run regression tests
   ↓
Document evidence
```

------------------------------------------------------------------------

# 28. Known Technical Debt

The project is **not represented as production-complete**.

### Python datetime deprecations

Some components still use:

``` python
datetime.utcnow()
```

These can produce deprecation warnings under current Python versions.

### Retrieval resource requirements

Large evaluation models require materially more compute than the
CPU-oriented DEV profile.

The repository therefore distinguishes:

-   DEV
-   EVAL
-   PROD

retrieval configurations.

### Operational deployment

Phase 6D adds API-boundary controls, but production deployment concerns
such as external ingress controls, distributed rate limiting,
centralized log infrastructure, secrets management, TLS termination, and
multi-instance coordination remain deployment-level concerns.

### Benchmark maturity

The evaluation framework exists, but end-to-end autonomous AP
performance must be interpreted across separate dimensions:

-   retrieval
-   evidence quality
-   decision quality
-   action safety
-   business outcome

------------------------------------------------------------------------

# 29. What APX Can Demonstrate

The project is designed to demonstrate the engineering chain below:

``` text
What happened?
      ↓
Which deterministic rule detected it?
      ↓
What evidence supports the finding?
      ↓
Was that evidence valid at the relevant time?
      ↓
How confident is the decision?
      ↓
What is the financial/business risk?
      ↓
Should the system resolve, request approval, or escalate?
      ↓
What action was authorized?
      ↓
What state was persisted?
      ↓
What action actually executed?
      ↓
Can the decision be audited?
      ↓
Can the behavior be measured and reproduced?
```

That chain---not merely an LLM call---is the core engineering objective
of APX.

------------------------------------------------------------------------

# 30. Current Status

### Completed through Phase 6D

APX currently contains:

-   deterministic R1--R10 AP exception validation
-   reproducible synthetic data
-   controlled agent/state-machine infrastructure
-   hybrid BM25 + dense retrieval
-   reciprocal-rank fusion
-   cross-encoder reranking
-   evidence validity checks
-   temporal anchoring
-   risk-aware decision logic
-   approval workflows
-   guarded action execution
-   retry and compensation handling
-   dead-letter behavior
-   dry-run support
-   idempotency controls
-   SQLite/SQLAlchemy persistence
-   Alembic migration foundation
-   repository abstractions
-   application services
-   FastAPI API delivery
-   API-key authentication
-   role-based access control
-   invoice/case/approval/audit/metrics/health routes
-   structured API logging
-   request/correlation IDs
-   W3C trace context propagation
-   API metrics
-   sensitive-data redaction
-   request-size enforcement
-   in-process rate limiting
-   security headers
-   evaluation and benchmark infrastructure
-   research/forensic documentation

### Current Git state

``` text
HEAD -> main
origin/main -> main

6e509df feat: complete phase 6D observability and security
```

### Next step

**Phase 6D remains the current frozen milestone.**

The next phase should begin only after the Phase 6D repository state,
documentation, and verification evidence are preserved.

------------------------------------------------------------------------

# 31. Project Documentation

Key engineering records include:

``` text
PHASE5_REPORT.md
PHASE6A_REPORT.md
PHASE6_GAP_AUDIT.md
PHASE6B_REPORT.md
PHASE6C_REPORT.md
PHASE6D_REPORT.md
PROJECT_STATUS_AUDIT.md
ROOT_CAUSE_REPORT.md
```

Additional retrieval/evidence forensic material is maintained under
`docs/`.

For the most recent milestone, start with:

``` text
PHASE6D_REPORT.md
```

------------------------------------------------------------------------

# 32. License

See the repository license file.

# 33. Author

**Eklakh Dewan**\
Artificial Intelligence & Data Science

Repository:

https://github.com/eklakhdewan/APX-Autonomous-Accounts-Payable-Exception-Resolution-Agent
