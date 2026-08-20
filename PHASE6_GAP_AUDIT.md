# APX V1.1 — Phase 6 Gap Audit

**Date:** 2026-08-20  
**Status:** AUDIT COMPLETE — READY FOR PHASE 6 PLANNING  
**Baseline:** Phase 1–5 frozen, 278 tests passing  

---

## 1. Current Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         APX V1.1 PHASE 1–5 ARCHITECTURE                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  INVOICE INPUT                                                              │
│       │                                                                     │
│       ▼                                                                     │
│  ┌─────────────────┐     ┌──────────────────┐     ┌──────────────────┐    │
│  │  Phase 1        │────▶│  Phase 2         │────▶│  Phase 3         │    │
│  │  Deterministic  │     │  Hybrid Context  │     │  Bounded Agent   │    │
│  │  Validation     │     │  Engine          │     │  (State Machine) │    │
│  │  R1–R10         │     │  BM25 + Dense    │     │  Investigation   │    │
│  │  ExceptionReport│     │  RRF + Reranker  │     │  Result          │    │
│  └─────────────────┘     │  EvidenceSet     │     └────────┬─────────┘    │
│                          └──────────────────┘              │              │
│                                                           ▼              │
│  ┌─────────────────┐     ┌──────────────────┐     ┌──────────────────┐    │
│  │  Phase 5        │◀────│  Phase 4         │◀────│  Risk Engine     │    │
│  │  Observability  │     │  Action Pipeline │     │  Guardrail       │    │
│  │  Evaluation     │     │  Approval        │     │  Action Executor │    │
│  │  Benchmark      │     │  Guardrail       │     │  (Mock Adapters) │    │
│  └─────────────────┘     └──────────────────┘     └──────────────────┘    │
│                                                                             │
│  KEY PROPERTIES:                                                            │
│  • 278 tests passing                                                        │
│  • All core components FROZEN                                               │
│  • Deterministic, reproducible, auditable                                   │
│  • In-memory state only                                                     │
│  • No API layer, no persistence, no containerization                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Core Frozen Components (DO NOT MODIFY):**

| Component | Module | Status |
|-----------|--------|--------|
| R1–R10 Deterministic Validation | `apx/intelligence/validator.py` | FROZEN |
| Exception Taxonomy & Schemas | `apx/data/schemas.py`, `apx/exceptions/` | FROZEN |
| BM25 Retrieval | `apx/evidence/bm25.py` | FROZEN |
| Dense Retrieval | `apx/evidence/dense.py` | FROZEN |
| RRF Fusion | `apx/evidence/rrf.py` | FROZEN |
| Cross-Encoder Reranking | `apx/evidence/reranker.py` | FROZEN |
| Evidence Validity Logic | `apx/evidence/validity.py` | FROZEN |
| Temporal Anchoring | `apx/evidence/dates.py` | FROZEN |
| Agent State Machine | `apx/agent/state_machine.py`, `apx/agent/controller.py` | FROZEN |
| Compound Risk Engine | `apx/risk/engine.py` | FROZEN |
| Guardrail Engine | `apx/guardrail/engine.py` | FROZEN |
| Approval Engine | `apx/approval/engine.py` | FROZEN |
| Action Executor | `apx/action/executor.py` | FROZEN |
| Phase 4 Pipeline | `apx/action/pipeline.py` | FROZEN |
| Observability (Logging, Metrics, Tracing) | `apx/observability/` | FROZEN |
| Evaluation Framework (6 layers) | `apx/evaluation/` | FROZEN |
| Synthetic Data Generator | `apx/data/generate_synthetic.py` | FROZEN |
| Scenario-Controlled Split | `apx/data/split.py` | FROZEN |

---

## 2. Current API Status

**No production API layer exists.** Only CLI entry points:

| Entry Point | Module | Purpose |
|-------------|--------|---------|
| `python -m apx.data.generate_synthetic` | `apx/data/generate_synthetic.py` | Synthetic data generation |
| `python -m apx.evaluation.benchmark` | `apx/evaluation/benchmark.py` | Run 6-layer benchmark |
| `python -m pytest apx/tests` | `apx/tests/` | Test suite |

### Required API Endpoints — Current Status

| Endpoint | Exists? | Implemented? | Tested? | Persistence-Backed? | Error Handling? | Auth Boundary? | Idempotency? |
|----------|---------|--------------|---------|---------------------|-----------------|----------------|--------------|
| `POST /invoices` | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `GET /invoices/{id}` | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `POST /invoices/{id}/process` | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `GET /cases/{id}` | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `POST /cases/{id}/approve` | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `POST /cases/{id}/reject` | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `GET /cases/{id}/audit` | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `GET /metrics` | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `GET /health` | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

**Gap:** Entire API layer missing. This is the primary Phase 6 deliverable.

---

## 3. Current Persistence Status

| Aspect | Status | Details |
|--------|--------|---------|
| **Technology** | None | Pure in-memory state |
| **Invoice Persistence** | ❌ | Generated in memory, written to JSON files only for dataset generation |
| **Case Persistence** | ❌ | `InvestigationResult`, `ActionPlan` exist only in memory during execution |
| **Approval Persistence** | ❌ | `ApprovalEngine._pending_approvals` is in-memory dict |
| **Action/Audit Persistence** | ❌ | `ActionExecutor._dead_letter_queue` is in-memory list |
| **Evidence Index** | File-based | BM25/dense indexes saved as pickle/JSON in `apx/data/datasets/evidence/index/` |
| **Migration Strategy** | ❌ | None |
| **Transaction Boundaries** | ❌ | None — all operations are single-threaded in-memory |
| **Concurrency Concerns** | ❌ | Not addressed — no multi-process/thread safety |

### Current Data Flow (All In-Memory)

```
SyntheticGenerator.generate_*() 
    → List[Vendor], List[PO], List[GRN], List[Invoice], List[GroundTruth]
        → Validator.validate_invoice() → ExceptionReport
            → HybridContextEngine.retrieve() → EvidenceSet
                → run_investigation() → InvestigationResult
                    → Phase4Pipeline.process() → ActionPlan
                        → ActionExecutor.execute() → ActionResult
```

**Gap:** No persistence abstraction exists. Phase 6 must introduce a persistence layer with:
- Repository pattern for invoices, cases, approvals, actions, audit events
- Transaction boundary management
- Concurrency control (optimistic locking at minimum)
- Migration strategy for schema evolution

---

## 4. Current Observability Status

### Implemented (Phase 5)

| Component | File | Status |
|-----------|------|--------|
| Structured JSON Logging | `apx/observability/logger.py` | ✅ Complete |
| Metrics Collection | `apx/observability/metrics.py` | ✅ Complete |
| Tracing Abstraction | `apx/observability/langfuse_tracer.py` | ✅ Complete |
| Langfuse Integration (adapter pattern) | `apx/observability/langfuse_tracer.py` | ✅ Complete |
| No-Op Fallback for Tests | `NoOpTracer` class | ✅ Complete |
| Secret-Safe Tracing | Verified in tests | ✅ Complete |

### Logger Fields (Structured JSON)

```json
{
  "timestamp": "2026-08-20T10:00:00.000Z",
  "run_id": "uuid",
  "invoice_id": "INV-2026-0001",
  "phase": "phase1|phase2|phase3|phase4",
  "component": "validator|retriever|agent|risk|guardrail|action_executor",
  "event": "phase.start|phase.end|exception.detected|action.executed",
  "status": "info|warning|error|success",
  "duration_ms": 123.45,
  "metadata": {},
  "error": null
}
```

### Metrics Available

| Category | Metrics |
|----------|---------|
| Latency | `apx.phase1.validation.latency_ms`, `apx.phase2.retrieval.latency_ms`, `apx.phase3.investigation.latency_ms`, `apx.phase4.decision.latency_ms`, `apx.phase4.action.latency_ms`, `apx.pipeline.total.latency_ms` |
| Execution | `apx.invoices.processed`, `apx.exceptions.detected`, `apx.actions.executed`, `apx.actions.failed` |
| Business | `apx.escalation.count`, `apx.automation.count`, `apx.approval.required`, `apx.unauthorized_action_rate` |
| Accuracy | `apx.detection.precision/recall/f1`, `apx.decision.accuracy`, `apx.retrieval.recall_at_5/10`, `apx.retrieval.mrr/ndcg_at_10` |
| Cost | `apx.llm.tokens`, `apx.llm.cost_usd` |

### Missing for Phase 6 (API Layer)

| Capability | Status | Notes |
|------------|--------|-------|
| Request ID Correlation | ❌ | Need middleware to generate/propagate `X-Request-ID` |
| Correlation ID for Distributed Tracing | ❌ | Need W3C Trace Context support |
| Job ID for Async Processing | ❌ | Not applicable yet — all processing is synchronous |
| Structured API Access Logs | ❌ | Need FastAPI middleware for request/response logging |
| API Latency Metrics | ❌ | Per-endpoint latency histograms |
| API Error Metrics | ❌ | Per-endpoint error counters with status codes |
| Audit Event Logging | ❌ | Structured audit trail for approval/rejection/actions |
| Langfuse Production Integration | ⚠️ | Backend exists, but no production credentials configured |

**Gap:** Observability is complete for *batch/evaluation* workloads but needs extension for *request/response* API workloads.

---

## 5. Current Security Status

| Aspect | Status | Details |
|--------|--------|---------|
| **Environment Variable Handling** | Partial | Only `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST` |
| **Secret Handling** | Partial | Langfuse credentials only; no secret management for API keys, DB passwords |
| **API Authentication Boundary** | ❌ | No API layer exists |
| **Authorization Boundary** | ❌ | No API layer exists; guardrail provides *action-level* authorization only |
| **Input Validation** | ✅ (Core) | Pydantic models validate core domain objects; no API request validation |
| **Error Leakage** | ❌ | No API layer; core errors are structured but would leak if exposed via API |
| **Sensitive Data Logging** | ✅ | Logger tests verify secrets not emitted; but no API request/response body filtering |
| **CORS Configuration** | ❌ | Not applicable — no API |
| **Unsafe Debug Config** | ❌ | No debug endpoints |
| **Dependency Vulnerabilities** | Unknown | No dependency scanning configured |

**Gap:** Need to define the **authentication/authorization boundary** for the API layer:
- Minimal: API key or bearer token for service-to-service
- Standard: OAuth2/OIDC with role-based access (operator, reviewer, admin)
- Decision: Define boundary first, implement minimal viable auth, defer enterprise auth to later

---

## 6. Current Containerization Status

| Artifact | Exists? | Details |
|----------|---------|---------|
| `Dockerfile` | ❌ | |
| `.dockerignore` | ❌ | |
| `docker-compose.yml` | ❌ | |
| Healthcheck Endpoint | ❌ | |
| Startup Command | ❌ | No single entry point for production service |
| Environment Configuration | ⚠️ | YAML configs + env vars for Langfuse only |
| Non-Root Execution | ❌ | |

**Gap:** All containerization artifacts missing. Phase 6 must provide:
- Multi-stage `Dockerfile` (build → runtime)
- `.dockerignore` excluding tests, docs, eval results, model cache
- `docker-compose.yml` for local development (API + optional DB + optional Langfuse)
- Healthcheck endpoint (`GET /health`, `GET /ready`)
- Non-root user in container

---

## 7. Current CI/CD Status

| Artifact | Exists? | Details |
|----------|---------|---------|
| `.github/workflows/` | ❌ | No GitHub Actions |
| Test Workflow | ❌ | |
| Benchmark Workflow | ❌ | |
| Dependency Installation | ❌ | |
| Python Version Matrix | ❌ | |
| Secret Requirements | ❌ | Langfuse credentials only for optional tracing |

**Gap:** Complete CI/CD pipeline missing. Must support:
- Run 278 tests without external credentials (NoOpTracer)
- Optional benchmark run with model artifacts available
- Dependency caching
- Python 3.11+ matrix (currently 3.14.4 in dev)

---

## 8. Current Testing Status

### Existing Test Coverage (278 Tests)

| Module | Tests | Coverage |
|--------|-------|----------|
| `test_schemas.py` | 13 | Domain schemas |
| `test_data_generator.py` | 8 | Synthetic generation |
| `test_data_integrity.py` | 15 | Data integrity |
| `test_validator.py` | 31 | R1–R10 validation |
| `test_phase2_evidence.py` | 16 | Retrieval pipeline |
| `test_eval_dataset.py` | 9 | Evaluation dataset |
| `test_phase3_agent.py` | 9 | Agent logic |
| `test_phase3_budget.py` | 7 | Investigation budget |
| `test_phase3_integration.py` | 11 | Phase 1–3 integration |
| `test_phase3_state_machine.py` | 8 | State machine |
| `test_phase4_risk.py` | 11 | Risk engine |
| `test_phase4_guardrail.py` | 14 | Guardrail engine |
| `test_phase4_action.py` | 29 | Action/approval/pipeline |
| `test_tracing.py` | 23 | Observability |
| `test_temporal_anchoring.py` | 13 | Temporal logic |
| `test_benchmark.py` | 12 | Benchmark orchestration |
| `test_evaluation.py` | 21 | 6-layer evaluators |
| `test_split.py` | 15 | Dataset splitting |
| **TOTAL** | **278** | **All passing** |

### Missing Test Categories for Phase 6

| Category | Required Tests | Notes |
|----------|----------------|-------|
| Health/Readiness | `GET /health`, `GET /ready` | Liveness vs readiness distinction |
| API Validation | Request/response schema validation | Pydantic/FastAPI validation |
| Invoice Submission | `POST /invoices` success/invalid | 422 for invalid, 201 for created |
| Invalid Invoice | Malformed payload, missing fields | |
| Process Lifecycle | `POST /invoices/{id}/process` | Async or sync? |
| Case Retrieval | `GET /cases/{id}` | |
| Approval | `POST /cases/{id}/approve` | |
| Rejection | `POST /cases/{id}/reject` | |
| Audit Retrieval | `GET /cases/{id}/audit` | |
| Persistence | CRUD for invoices, cases, approvals, actions | |
| Transaction Failure | Rollback on partial failure | |
| Retry/Idempotency | Duplicate request handling | `Idempotency-Key` header |
| Authorization Boundary | 401/403 for unauth/unauthorized | |
| Structured Error Responses | RFC 7807 Problem Details | |

---

## 9. Missing Components Summary

| Area | Missing Components |
|------|-------------------|
| **API Layer** | FastAPI app, routers, request/response models, middleware, exception handlers |
| **Persistence** | Repository abstraction, SQLite dev impl, migration tooling, transaction management |
| **Job/Invoice Lifecycle** | Case state machine persistence, status transitions, audit trail |
| **Approval Persistence** | Approval request/decision storage, SLA tracking |
| **Audit Persistence** | Immutable event log for all state changes |
| **Observability (API)** | Request ID middleware, correlation ID, API metrics, audit logging |
| **Auth/Authorization** | Auth boundary definition, minimal auth implementation, RBAC |
| **Configuration** | API-specific config (host, port, workers, timeouts), env var validation |
| **Docker** | Dockerfile, docker-compose, .dockerignore, healthcheck |
| **CI/CD** | GitHub Actions workflows for test, lint, typecheck, build |
| **Error Handling** | Global exception handler, RFC 7807 responses, error codes |
| **Retry/Idempotency** | Idempotency key middleware, retry policies for external calls |
| **Security** | CORS, rate limiting, input sanitization, secret scanning |
| **Production Config** | Settings validation, feature flags, environment-specific overrides |

---

## 10. Integration Boundaries

### Phase 6 → Frozen Core Integration Points

```
┌─────────────────────────────────────────────────────────────────────┐
│                        PHASE 6 API LAYER                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌───────────┐  │
│  │ FastAPI     │  │ Persistence │  │ Auth/       │  │ Health/   │  │
│  │ Routers     │  │ Repositories│  │ Middleware  │  │ Ready     │  │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └─────┬─────┘  │
└─────────┼────────────────┼────────────────┼───────────────┼────────┘
          │                │                │               │
          ▼                ▼                ▼               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    FROZEN CORE (PHASE 1–5)                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌───────────┐  │
│  │ Phase 1     │  │ Phase 2     │  │ Phase 3     │  │ Phase 4   │  │
│  │ Validator   │  │ Retrieval   │  │ Agent       │  │ Pipeline  │  │
│  └─────────────┘  └─────────────┘  └─────────────┘  └───────────┘  │
│          │                │                │               │        │
│          └────────────────┼────────────────┼───────────────┘        │
│                           ▼                ▼                         │
│                    ┌─────────────┐  ┌─────────────┐                  │
│                    │ Phase 5     │  │ Phase 5     │                  │
│                    │ Observability│  │ Evaluation  │                  │
│                    └─────────────┘  └─────────────┘                  │
└─────────────────────────────────────────────────────────────────────┘
```

### Key Integration Rules

1. **API layer MUST NOT modify frozen core behavior** — only orchestrate
2. **Persistence is a new abstraction** — core components receive repository interfaces, not ORM models
3. **Observability extends** — add API-level metrics/logs/traces without changing core observability
4. **Auth is a boundary** — guardrail remains the *action* authorization; API auth is *access* authorization

---

## 11. Files That Must Remain Frozen

### Core Domain & Validation (Phase 1)
- `apx/data/schemas.py`
- `apx/intelligence/validator.py`
- `apx/exceptions/taxonomy.py`
- `apx/exceptions/models.py`
- `apx/config/risk_policy.yaml`

### Retrieval & Evidence (Phase 2)
- `apx/evidence/bm25.py`
- `apx/evidence/dense.py`
- `apx/evidence/rrf.py`
- `apx/evidence/reranker.py`
- `apx/evidence/engine.py`
- `apx/evidence/validity.py`
- `apx/evidence/schemas.py`
- `apx/evidence/dates.py`
- `apx/evidence/query.py`
- `apx/config/retrieval_profiles.yaml`

### Agent & Decision (Phase 3)
- `apx/agent/state_machine.py`
- `apx/agent/controller.py`
- `apx/agent/models.py`
- `apx/agent/llm/mock.py`

### Risk, Guardrail, Action (Phase 4)
- `apx/risk/engine.py`
- `apx/risk/models.py`
- `apx/guardrail/engine.py`
- `apx/guardrail/models.py`
- `apx/approval/engine.py`
- `apx/action/executor.py`
- `apx/action/pipeline.py`
- `apx/action/models.py`

### Observability & Evaluation (Phase 5)
- `apx/observability/logger.py`
- `apx/observability/metrics.py`
- `apx/observability/langfuse_tracer.py`
- `apx/evaluation/extraction_eval.py`
- `apx/evaluation/detection_eval.py`
- `apx/evaluation/retrieval_eval.py`
- `apx/evaluation/decision_eval.py`
- `apx/evaluation/action_eval.py`
- `apx/evaluation/business_eval.py`
- `apx/evaluation/benchmark.py`
- `apx/data/split.py`
- `apx/data/generate_synthetic.py`

### Tests (All)
- `apx/tests/test_*.py` (all 278 tests must remain passing)

---

## 12. Files Proposed for Phase 6 Changes

### New Files (API Layer)

| File | Purpose |
|------|---------|
| `apx/api/__init__.py` | API package |
| `apx/api/main.py` | FastAPI application factory |
| `apx/api/routes/invoices.py` | `POST /invoices`, `GET /invoices/{id}`, `POST /invoices/{id}/process` |
| `apx/api/routes/cases.py` | `GET /cases/{id}`, `POST /cases/{id}/approve`, `POST /cases/{id}/reject`, `GET /cases/{id}/audit` |
| `apx/api/routes/metrics.py` | `GET /metrics` (Prometheus exposition) |
| `apx/api/routes/health.py` | `GET /health`, `GET /ready` |
| `apx/api/models/requests.py` | Request Pydantic models |
| `apx/api/models/responses.py` | Response Pydantic models |
| `apx/api/middleware/request_id.py` | Request ID correlation middleware |
| `apx/api/middleware/auth.py` | Authentication/authorization middleware |
| `apx/api/middleware/logging.py` | Structured API request/response logging |
| `apx/api/exceptions.py` | RFC 7807 exception handlers |
| `apx/api/dependencies.py` | FastAPI dependency injection (repos, services) |

### New Files (Persistence Layer)

| File | Purpose |
|------|---------|
| `apx/persistence/__init__.py` | Persistence package |
| `apx/persistence/repositories.py` | Repository interfaces (protocols) |
| `apx/persistence/sqlite_repos.py` | SQLite implementation for dev/test |
| `apx/persistence/models.py` | SQLAlchemy/SQLModel ORM models |
| `apx/persistence/migrations/` | Alembic migration scripts |
| `apx/persistence/transaction.py` | Transaction boundary management |

### New Files (Configuration & Deployment)

| File | Purpose |
|------|---------|
| `apx/config/api_settings.py` | API-specific settings (host, port, workers, timeouts) |
| `Dockerfile` | Multi-stage production image |
| `.dockerignore` | Build context exclusions |
| `docker-compose.yml` | Local dev stack (API + DB + optional Langfuse) |
| `.github/workflows/ci.yml` | CI pipeline (test, lint, typecheck) |
| `.github/workflows/benchmark.yml` | Optional benchmark workflow |

### Modified Files (Minimal, Additive Only)

| File | Change |
|------|--------|
| `apx/config/settings.py` | Add API settings load (additive) |
| `pyproject.toml` | Add FastAPI, SQLModel, alembic, uvicorn, httpx dependencies |
| `README.md` | Add API usage, Docker, deployment docs |

---

## 13. Phase 6 Implementation Sequence

### Phase 6A: Foundation (Week 1)
1. **Add API dependencies** to `pyproject.toml` (FastAPI, uvicorn, pydantic-settings, python-multipart)
2. **Create persistence abstraction** — repository protocols + SQLite implementation
3. **Create database models** — Invoice, Case, Approval, Action, AuditEvent tables
4. **Add migration tooling** — Alembic with initial migration
5. **Verify**: All 278 existing tests still pass; new persistence tests pass

### Phase 6B: API Layer (Week 2)
6. **Create FastAPI application** — `apx/api/main.py` with middleware stack
7. **Implement health/readiness endpoints** — `GET /health`, `GET /ready`
8. **Implement invoice submission** — `POST /invoices` with validation, persistence
9. **Implement invoice retrieval** — `GET /invoices/{id}`
10. **Implement process trigger** — `POST /invoices/{id}/process` (sync or async)
11. **Verify**: API contract tests pass; integration with frozen core works

### Phase 6C: Case & Approval (Week 3)
12. **Implement case retrieval** — `GET /cases/{id}`
13. **Implement approval** — `POST /cases/{id}/approve`
14. **Implement rejection** — `POST /cases/{id}/reject`
15. **Implement audit retrieval** — `GET /cases/{id}/audit`
16. **Add idempotency middleware** — `Idempotency-Key` header support
17. **Verify**: Full lifecycle tests pass; approval workflow persists

### Phase 6D: Observability & Security (Week 4)
18. **Add request ID correlation** — middleware + context propagation to core
19. **Add API metrics** — latency, error rate, throughput per endpoint
20. **Add audit event logging** — structured events for all state changes
21. **Implement minimal auth** — API key or bearer token with role claims
22. **Add CORS, rate limiting, input validation**
23. **Verify**: Observability tests pass; security boundary tests pass

### Phase 6E: Containerization & CI/CD (Week 5)
24. **Create Dockerfile** — multi-stage, non-root, healthcheck
25. **Create docker-compose.yml** — API + SQLite + optional Postgres + optional Langfuse
26. **Create GitHub Actions CI** — test matrix, lint, typecheck, build
27. **Verify**: CI passes; Docker image builds and runs; healthcheck responds

### Phase 6F: Integration Testing & Hardening (Week 6)
28. **Add integration tests** — full API lifecycle, persistence, failure scenarios
29. **Add retry/idempotency tests** — duplicate requests, partial failures
30. **Add authorization boundary tests** — 401/403 scenarios
31. **Run benchmark via API** — verify end-to-end metrics unchanged
32. **Load test** — verify latency/throughput under concurrency
33. **Final verification** — all acceptance criteria met

---

## 14. Phase 6 Acceptance Criteria

| # | Criterion | Testable | Observable | Deterministic | Compatible w/ Frozen Core |
|---|-----------|----------|------------|---------------|---------------------------|
| 1 | `POST /invoices` accepts valid invoice, returns 201 with case ID | ✅ | ✅ | ✅ | ✅ |
| 2 | `POST /invoices` rejects invalid payload with 422 (RFC 7807) | ✅ | ✅ | ✅ | ✅ |
| 3 | `GET /invoices/{id}` returns invoice + case status | ✅ | ✅ | ✅ | ✅ |
| 4 | `POST /invoices/{id}/process` triggers Phase 1→4 pipeline | ✅ | ✅ | ✅ | ✅ |
| 5 | `GET /cases/{id}` returns case with investigation, risk, guardrail, action | ✅ | ✅ | ✅ | ✅ |
| 6 | `POST /cases/{id}/approve` records approval, transitions action | ✅ | ✅ | ✅ | ✅ |
| 7 | `POST /cases/{id}/reject` records rejection, blocks action | ✅ | ✅ | ✅ | ✅ |
| 8 | `GET /cases/{id}/audit` returns immutable event log | ✅ | ✅ | ✅ | ✅ |
| 9 | `GET /health` returns 200 OK (liveness) | ✅ | ✅ | ✅ | ✅ |
| 10 | `GET /ready` returns 200 only if deps (DB, models) available | ✅ | ✅ | ✅ | ✅ |
| 11 | `GET /metrics` exposes Prometheus metrics | ✅ | ✅ | ✅ | ✅ |
| 12 | All 278 existing tests still pass | ✅ | ✅ | ✅ | ✅ |
| 13 | New API/persistence tests added and passing | ✅ | ✅ | ✅ | ✅ |
| 14 | Request ID propagated through all phases in logs/traces | ✅ | ✅ | ✅ | ✅ |
| 15 | Correlation ID (W3C) supported for distributed tracing | ✅ | ✅ | ✅ | ✅ |
| 16 | Idempotency key prevents duplicate processing | ✅ | ✅ | ✅ | ✅ |
| 17 | Unauthorized requests return 401 | ✅ | ✅ | ✅ | ✅ |
| 18 | Forbidden actions return 403 | ✅ | ✅ | ✅ | ✅ |
| 19 | Docker image builds, runs, passes healthcheck | ✅ | ✅ | ✅ | ✅ |
| 20 | CI pipeline runs tests without external credentials | ✅ | ✅ | ✅ | ✅ |
| 21 | Benchmark results via API match direct benchmark (±1%) | ✅ | ✅ | ✅ | ✅ |
| 22 | No secrets in logs, config, or container images | ✅ | ✅ | ✅ | ✅ |
| 23 | SQLite dev DB works; Postgres config documented for prod | ✅ | ✅ | ✅ | ✅ |
| 24 | Migration from empty DB to current schema works | ✅ | ✅ | ✅ | ✅ |

---

## 15. Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **Frozen core integration breaks** | Medium | High | Add integration tests early; use dependency injection; don't modify core |
| **Persistence performance** | Medium | Medium | Use connection pooling; async DB driver; benchmark early |
| **Async vs sync processing** | Medium | High | Decide early: `POST /process` sync (blocks) vs async (returns job ID + poll) |
| **Model loading in containers** | High | Medium | Pre-bake model artifacts in Docker image or use volume mounts |
| **Langfuse credential handling** | Low | Low | Document clearly; NoOp fallback always works |
| **API auth scope creep** | Medium | Medium | Define minimal viable auth (API key + roles); defer OAuth2/OIDC |
| **Database migration strategy** | Low | High | Use Alembic from start; test migrations in CI |
| **Concurrency bugs** | Medium | High | Optimistic locking on case state; test concurrent approval/process |
| **Test environment divergence** | Low | Medium | Use same SQLite in tests and dev; document differences |

---

## 16. Recommended Architecture

### High-Level Structure

```
apx/
├── api/                    # NEW — Phase 6
│   ├── main.py
│   ├── routes/
│   ├── models/
│   ├── middleware/
│   ├── exceptions.py
│   └── dependencies.py
├── persistence/            # NEW — Phase 6
│   ├── repositories.py     # Protocols (interfaces)
│   ├── sqlite_repos.py     # Dev/test implementation
│   ├── models.py           # ORM models
│   ├── transaction.py
│   └── migrations/         # Alembic
├── config/
│   ├── settings.py         # Existing (frozen)
│   ├── api_settings.py     # NEW — API config
│   ├── retrieval_profiles.yaml
│   └── risk_policy.yaml
├── intelligence/           # FROZEN
├── evidence/               # FROZEN
├── agent/                  # FROZEN
├── risk/                   # FROZEN
├── guardrail/              # FROZEN
├── approval/               # FROZEN
├── action/                 # FROZEN
├── observability/          # FROZEN (extend via middleware)
├── evaluation/             # FROZEN
├── data/                   # FROZEN
├── exceptions/             # FROZEN
└── tests/                  # EXTEND with API/persistence tests
```

### Request Flow

```
POST /invoices
    │
    ▼
┌────────────────────────────────────────────────────────────────┐
│ FastAPI Request Validation (Pydantic)                         │
│   • Schema validation                                          │
│   • Idempotency-Key header check                               │
│   • Auth middleware (API key + role)                          │
│   • Request ID generation (X-Request-ID)                      │
└────────────────────────────┬───────────────────────────────────┘
                             │
                             ▼
┌────────────────────────────────────────────────────────────────┐
│ API Service Layer                                              │
│   • InvoiceRepository.create(invoice)                         │
│   • CaseRepository.create(case_id, invoice_id, status=NEW)    │
│   • AuditRepository.log(InvoiceSubmittedEvent)                │
└────────────────────────────┬───────────────────────────────────┘
                             │
                             ▼
┌────────────────────────────────────────────────────────────────┐
│ Background Task (or sync)                                      │
│   • Validator.validate_invoice()  ──▶ ExceptionReport          │
│   • HybridContextEngine.retrieve() ──▶ EvidenceSet             │
│   • run_investigation() ──▶ InvestigationResult               │
│   • Phase4Pipeline.process() ──▶ ActionPlan                   │
│   • Repository updates at each step                           │
│   • AuditRepository.log at each transition                    │
└────────────────────────────┬───────────────────────────────────┘
                             │
                             ▼
┌────────────────────────────────────────────────────────────────┐
│ Response                                                       │
│   • 202 Accepted (async) or 200 OK (sync)                     │
│   • Case ID, status, links to /cases/{id}                     │
└────────────────────────────────────────────────────────────────┘
```

### Persistence Schema (Logical)

```sql
-- Invoices (submitted for processing)
CREATE TABLE invoices (
    invoice_id       VARCHAR PRIMARY KEY,
    vendor_id        VARCHAR NOT NULL,
    invoice_number   VARCHAR NOT NULL,
    po_number        VARCHAR,
    invoice_date     DATE NOT NULL,
    due_date         DATE NOT NULL,
    currency         VARCHAR(3) NOT NULL,
    subtotal         DECIMAL(18,2) NOT NULL,
    tax              DECIMAL(18,2) NOT NULL,
    total            DECIMAL(18,2) NOT NULL,
    discount         DECIMAL(18,2) DEFAULT 0,
    payload_json     JSONB NOT NULL,        -- full invoice for replay
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    updated_at       TIMESTAMPTZ DEFAULT NOW()
);

-- Cases (processing lifecycle)
CREATE TABLE cases (
    case_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id       VARCHAR REFERENCES invoices(invoice_id),
    vendor_id        VARCHAR NOT NULL,
    status           VARCHAR NOT NULL,      -- NEW, VALIDATING, RETRIEVING, INVESTIGATING, DECIDING, APPROVING, EXECUTING, COMPLETED, FAILED
    current_phase    VARCHAR,               -- phase1, phase2, phase3, phase4
    exception_codes  TEXT[],                -- array of R1-R10 codes
    risk_level       VARCHAR,               -- LOW, MEDIUM, HIGH, CRITICAL
    risk_score       DECIMAL(4,3),
    investigation_outcome VARCHAR,          -- RESOLVE, REQUEST_INFO, ESCALATE
    action_type      VARCHAR,               -- AUTO_RESOLVE, ESCALATE_TO_HUMAN, etc.
    action_status    VARCHAR,               -- PENDING, APPROVED, REJECTED, EXECUTED, FAILED
    idempotency_key  VARCHAR UNIQUE,
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    updated_at       TIMESTAMPTZ DEFAULT NOW(),
    completed_at     TIMESTAMPTZ
);

-- Approvals (human-in-the-loop)
CREATE TABLE approvals (
    approval_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id          UUID REFERENCES cases(case_id),
    action_plan_id   UUID,
    action_type      VARCHAR NOT NULL,
    risk_level       VARCHAR NOT NULL,
    status           VARCHAR NOT NULL,      -- PENDING, APPROVED, REJECTED
    required_approvers TEXT[] NOT NULL,
    approvals_json   JSONB DEFAULT '{}',    -- approver_id -> {approved: bool, notes: str, at: timestamp}
    requested_by     VARCHAR DEFAULT 'system',
    requested_at     TIMESTAMPTZ DEFAULT NOW(),
    resolved_by      VARCHAR,
    resolved_at      TIMESTAMPTZ,
    notes            TEXT
);

-- Actions (executed actions)
CREATE TABLE actions (
    action_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id          UUID REFERENCES cases(case_id),
    approval_id      UUID REFERENCES approvals(approval_id),
    action_type      VARCHAR NOT NULL,
    target           VARCHAR NOT NULL,      -- invoice_id, vendor_id, etc.
    parameters_json  JSONB NOT NULL,
    risk_score       DECIMAL(4,3),
    guardrail_decision VARCHAR,            -- ALLOW, REQUIRE_APPROVAL, BLOCK
    status           VARCHAR NOT NULL,      -- PENDING, EXECUTING, EXECUTED, FAILED, COMPENSATED
    idempotency_key  VARCHAR UNIQUE,
    retry_count      INT DEFAULT 0,
    result_json      JSONB,
    error_message    TEXT,
    executed_at      TIMESTAMPTZ,
    created_at       TIMESTAMPTZ DEFAULT NOW()
);

-- Audit Events (immutable log)
CREATE TABLE audit_events (
    event_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id          UUID REFERENCES cases(case_id),
    event_type       VARCHAR NOT NULL,      -- INVOICE_SUBMITTED, VALIDATION_COMPLETE, RETRIEVAL_COMPLETE, INVESTIGATION_COMPLETE, RISK_ASSESSED, GUARDRAIL_EVALUATED, APPROVAL_REQUESTED, APPROVAL_GRANTED, APPROVAL_DENIED, ACTION_EXECUTED, ACTION_FAILED, ACTION_COMPENSATED
    phase            VARCHAR,               -- phase1, phase2, phase3, phase4
    component        VARCHAR,
    payload_json     JSONB NOT NULL,
    metadata_json    JSONB DEFAULT '{}',    -- request_id, correlation_id, user_id, duration_ms
    created_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_audit_case_created ON audit_events(case_id, created_at);
CREATE INDEX idx_cases_status ON cases(status);
CREATE INDEX idx_cases_idempotency ON cases(idempotency_key);
```

---

## 17. Next Steps

This audit is complete. **DO NOT IMPLEMENT PHASE 6 YET.**

**Awaiting instruction to proceed with Phase 6A (Foundation):**
1. Add API dependencies to `pyproject.toml`
2. Create persistence abstraction (repository protocols)
3. Create SQLite implementation
4. Create initial Alembic migration
5. Verify all 278 existing tests still pass

**Decision Points Requiring Clarification:**
1. **Sync vs Async Processing**: Should `POST /invoices/{id}/process` block until complete (sync) or return 202 with job ID for polling (async)?
2. **Auth Model**: API key with roles (operator/reviewer/admin) or defer to OAuth2/OIDC?
3. **Database**: SQLite for dev/test only, or support Postgres from Phase 6A?
4. **Model Artifacts**: Pre-bake BAAI models in Docker image, or download at runtime?

---

**Audit Complete.** Ready for Phase 6 planning approval.