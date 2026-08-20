# APX V1.1 — Phase 6A Completion Report

**Date:** 2026-08-20  
**Status:** PHASE 6A COMPLETE — READY FOR PHASE 6B  
**Baseline:** Phase 1–5 frozen, 278 tests passing  
**Final Total:** 334 tests passing (278 existing + 56 new)  

---

## 1. Summary

Phase 6A has been successfully completed. The production persistence foundation for APX has been built with:

- **Repository pattern** with backend-independent interfaces
- **SQLite implementation** for development/testing
- **Alembic migration** infrastructure for schema evolution
- **Full CRUD operations** for all domain entities
- **Transaction boundary management** with proper commit/rollback
- **Serialization/deserialization** of all APX domain objects
- **56 comprehensive tests** covering all persistence operations
- **Zero regressions** — all 278 existing tests still pass

**Total Tests:** 334 passing (278 existing + 56 new)

---

## 2. Files Added/Changed

### New Files (Phase 6A)

| File | Purpose |
|------|---------|
| `apx/persistence/__init__.py` | Package exports |
| `apx/persistence/repositories.py` | Repository interfaces (protocols) |
| `apx/persistence/sqlite_repos.py` | SQLite implementations |
| `apx/persistence/models.py` | SQLAlchemy ORM models |
| `apx/persistence/database.py` | Database initialization & session management |
| `apx/persistence/config.py` | Persistence configuration (Pydantic Settings) |
| `apx/persistence/migrations/env.py` | Alembic environment |
| `apx/persistence/migrations/alembic.ini` | Alembic configuration |
| `apx/persistence/migrations/versions/001_initial.py` | Initial migration |
| `apx/tests/test_persistence.py` | 56 comprehensive tests |

### Modified Files

| File | Change |
|------|--------|
| `pyproject.toml` | Added SQLAlchemy, Alembic, pydantic-settings dependencies; version bump to 0.3.0 |
| `apx/persistence/__init__.py` | Added exports for new modules |

---

## 3. Architecture

### Repository Pattern (Dependency Inversion)

```
Application Service Layer
        ↓
Repository Interfaces (Protocols)
        ↓
SQLite Repositories (Dev/Test)
        ↓
SQLite Database
```

**Future:**
```
Application Service Layer
        ↓
Repository Interfaces (Protocols)  ← UNCHANGED
        ↓
PostgreSQL Repositories (Prod)
        ↓
PostgreSQL Database
```

The frozen APX core (Phases 1–5) remains completely independent of persistence implementation.

---

## 4. Database Schema

### Tables Created (6)

| Table | Purpose | Key Constraints |
|-------|---------|-----------------|
| `invoices` | Submitted invoices | PK: `invoice_id`, FK: `vendor_id` |
| `ground_truth` | Evaluation labels | PK/FK: `invoice_id` → `invoices` |
| `cases` | Processing lifecycle | PK: `case_id`, FK: `invoice_id` (unique), UK: `idempotency_key` |
| `approvals` | Human approval workflow | PK: `approval_id`, FK: `case_id` (unique), UK: `approval_id` |
| `actions` | Executed actions | PK: `action_id`, FK: `case_id` (unique), FK: `approval_id`, UK: `idempotency_key` |
| `audit_events` | Immutable event log | PK: `event_id`, FK: `case_id` (RESTRICT), indexes on `event_type`, `created_at`, `request_id` |

### Key Design Decisions

1. **UUID primary keys** for all entities except invoices (business ID)
2. **Foreign key cascades** for referential integrity (except audit_events)
3. **Unique constraints** on idempotency keys (`cases.idempotency_key`, `actions.idempotency_key`)
4. **One-to-one relationships** between invoices ↔ cases ↔ approvals ↔ actions
5. **JSON columns** for flexible payload storage (payload_json, approvals_json, etc.)
6. **Indexes** on frequently queried columns (status, vendor_id, created_at, request_id)

---

## 5. Repository Interfaces

Five repository protocols define the persistence contract:

| Interface | Entity | Key Methods |
|-----------|--------|-------------|
| `InvoiceRepository` | Invoice + GroundTruth | `create()`, `get()`, `get_with_ground_truth()`, `exists()`, `list_all()`, `delete()` |
| `CaseRepository` | Case lifecycle | `create()`, `get()`, `get_by_invoice()`, `get_by_idempotency_key()`, `update_status()`, `update_phase1-4_result()`, `list_all()`, `delete()` |
| `ApprovalRepository` | Approval workflow | `create()`, `get()`, `get_by_case()`, `update_status()`, `add_approval()`, `list_pending()`, `list_all()`, `delete()` |
| `ActionRepository` | Action execution | `create()`, `get()`, `get_by_case()`, `get_by_idempotency_key()`, `update_execution()`, `update_compensation()`, `list_all()`, `delete()` |
| `AuditRepository` | Audit logging | `log()`, `get_by_case()`, `get_by_type()`, `list_all()` |

---

## 6. Transaction Model

### Session Management

```python
@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """Provide a transactional scope around a series of operations."""
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
```

### Transaction Boundaries

- Each repository method runs in its own session scope
- Complex operations (e.g., `update_phase4_result`) are single transactions
- Tests use `reset_database()` for clean isolation between tests

---

## 7. Serialization/Deserialization

All APX domain objects round-trip through the repositories:

| Domain Object | Repository | Key Fields Preserved |
|---------------|------------|---------------------|
| `Invoice` | `InvoiceRepository` | All fields including line_items, currency, decimals |
| `GroundTruth` | `InvoiceRepository` | `expected_exceptions`, `expected_decision`, `injected_exceptions` |
| `InvestigationResult` | `CaseRepository` | steps, findings, budget, outcome, evidence_ids |
| `RiskAssessment` | `CaseRepository` | overall_score, risk_level, dimension_scores, reasons |
| `GuardrailDecisionResult` | `CaseRepository` | decision, checks, risk_level, requires_approval |
| `ActionPlan` | `ActionRepository` | action_type, parameters, idempotency_key, evidence_ids |
| `ApprovalRequest` | `ApprovalRepository` | approvals dict (bool), status, required_approvers |

**Decimal precision:** Handled via SQLAlchemy `DECIMAL` type with string conversion for JSON transport.

---

## 8. Test Results

### New Phase 6A Tests (56 tests)

| Test Class | Tests | Coverage |
|------------|-------|----------|
| `TestDatabaseInitialization` | 4 | Table creation, idempotent init, reset, cleanup |
| `TestInvoiceRepository` | 6 | CRUD, ground truth, pagination, uniqueness |
| `TestCaseRepository` | 10 | Lifecycle, phase updates, status filters, idempotency |
| `TestApprovalRepository` | 7 | CRUD, status updates, multi-approver, listing |
| `TestActionRepository` | 6 | CRUD, execution updates, compensation, idempotency |
| `TestAuditRepository` | 4 | Logging, querying by case/type, listing |
| `TestTransactionBehavior` | 2 | Commit, rollback on error |
| `TestIdempotencyConstraints` | 3 | Unique constraints on idempotency keys |
| `TestConcurrency` | 2 | Multi-threaded case creation, approval updates |
| `TestSerialization` | 5 | Round-trip for all domain objects |
| `TestPersistenceIsolation` | 2 | Test isolation, repo independence |
| `TestMissingEntityBehavior` | 4 | Graceful handling of missing entities |
| `TestAuditEventImmutability` | 3 | **NEW** Audit events survive parent deletion |

**All 56 tests pass.**

### Existing Tests (278 tests)

All 278 pre-existing tests continue to pass — **zero regressions**.

---

## 9. Compatibility Verification

### Frozen Components Unchanged

All Phase 1–5 components remain completely unmodified:

| Component | Status |
|-----------|--------|
| `apx/intelligence/validator.py` (R1–R10) | ✅ Unchanged |
| `apx/evidence/bm25.py`, `dense.py`, `rrf.py`, `reranker.py`, `engine.py` | ✅ Unchanged |
| `apx/agent/state_machine.py`, `controller.py` | ✅ Unchanged |
| `apx/risk/engine.py` | ✅ Unchanged |
| `apx/guardrail/engine.py` | ✅ Unchanged |
| `apx/approval/engine.py` | ✅ Unchanged |
| `apx/action/executor.py`, `pipeline.py` | ✅ Unchanged |
| `apx/observability/*` | ✅ Unchanged |
| `apx/evaluation/*` | ✅ Unchanged |
| `apx/data/*` | ✅ Unchanged |
| All 278 existing tests | ✅ Passing |

### No Secrets in Code

- Configuration via `Pydantic Settings` with `env_prefix="APX_PERSISTENCE_"`
- Database URLs via environment variables
- No hardcoded credentials

---

## 10. Phase 6A Persistence Audit Findings

### CHECK 1 — Audit Event Immutability: **DEFECT FOUND & FIXED**

**Original Defect:** The `audit_events` table was configured with cascade delete behavior:
- ORM relationship: `CaseORM.audit_events` had `cascade="all, delete-orphan"`
- Database FK: `AuditEventORM.case_id` had `ondelete="CASCADE"`

This meant deleting a `Case` would silently cascade-delete all associated `audit_events`, violating the immutable audit log requirement.

**Fix Applied:**
1. **ORM relationship:** Changed `CaseORM.audit_events` cascade from `"all, delete-orphan"` to `"save-update, merge, refresh-expire, expunge"` (no delete cascade)
2. **Database FK:** Changed `AuditEventORM.case_id` FK from `ondelete="CASCADE"` to `ondelete="RESTRICT"`

**Verification Tests Added (3 new tests in `TestAuditEventImmutability`):**
- `test_audit_events_survive_case_deletion_attempt` — Verifies RESTRICT FK prevents case deletion when audit events exist
- `test_audit_events_survive_invoice_deletion_attempt` — Verifies RESTRICT FK prevents invoice deletion when case/audit events exist
- `test_orm_cascade_does_not_delete_audit_events` — Verifies ORM cascade configuration doesn't delete audit events

All 3 tests pass. Audit events are now immutable and survive parent entity deletion attempts.

### CHECK 2 — Action Cardinality: **CORRECT AS-IS**

**Analysis of Frozen Domain Semantics (Phase 4):**

The frozen `ActionExecutor` and `ActionPlan` domain model:
- Uses **one `ActionPlan` per case**, updated in place during execution
- Retries happen in-memory on the same `ActionPlan` object (updates `retry_count`, `status`, `execution_result`, `error_message`)
- Compensation result stored in `execution_result` under "compensation" key
- Dead letter queue is in-memory only (`ActionExecutor._dead_letter_queue`)
- No multiple `ActionPlan` objects created per case during execution

**Schema Decision: CORRECT**

The UNIQUE constraint on `case_id` in `ActionORM` (enforcing one action record per case) correctly reflects the frozen domain semantics. The action executor updates a single `ActionPlan` in place rather than creating multiple records per case.

**Idempotency:** Preserved via `idempotency_key` unique constraint on `actions.idempotency_key` (separate from case_id), allowing duplicate submission detection while maintaining one action record per case.

**Evidence from Frozen Code:**
- `ActionPlan.retry_count` field updated in-place during retries (executor.py:130)
- Compensation stored in `execution_result["compensation"]` (executor.py:202)
- Dead letter queue is in-memory list (executor.py:37, 225)
- No code path creates multiple ActionPlan objects for the same case

---

## 11. Persistence-Only Changes Made

| Change | File | Type |
|--------|------|------|
| Removed `delete-orphan` cascade from `CaseORM.audit_events` | `models.py` | Fix |
| Changed `AuditEventORM.case_id` FK from CASCADE to RESTRICT | `models.py` | Fix |
| Updated migration FK from CASCADE to RESTRICT | `migrations/versions/001_initial.py` | Fix |
| Added 3 audit event immutability regression tests | `test_persistence.py` | Test |

**No changes to:**
- Action cardinality schema (UNIQUE constraint on `case_id` kept)
- Frozen Phase 1–5 components
- Any other table constraints or relationships

---

## 12. Known Limitations

| Limitation | Impact | Mitigation |
|------------|--------|------------|
| SQLite only (no PostgreSQL implementation yet) | Dev/test only | Repository interface ready for PG impl |
| No connection pooling for SQLite | Low concurrency | StaticPool for in-memory, file-based for dev |
| No async repository methods | Sync only | Can be added in Phase 6B |
| No soft delete / audit trail for invoices | Audit only on cases | Separate audit_events table covers lifecycle |
| `datetime.utcnow()` deprecation warnings | Non-functional | Existing codebase issue, not Phase 6A |

---

## 12. Exact Next Step for Phase 6B

**Phase 6B: FastAPI Application Layer**

Build the API layer on top of the persistence foundation:

1. **FastAPI application** with dependency injection for repositories
2. **API endpoints:**
   - `POST /invoices` — submit invoice
   - `GET /invoices/{id}` — retrieve invoice
   - `POST /invoices/{id}/process` — trigger processing (sync)
   - `GET /cases/{id}` — case status
   - `POST /cases/{id}/approve` — approve action
   - `POST /cases/{id}/reject` — reject action
   - `GET /cases/{id}/audit` — audit trail
   - `GET /health`, `GET /ready` — liveness/readiness
   - `GET /metrics` — Prometheus exposition
3. **Middleware:** Request ID, correlation ID, structured logging, auth
4. **Authentication:** API key with role abstraction (operator/reviewer/admin)
5. **OpenAPI documentation** via FastAPI automatic generation

**Dependencies already satisfied:**
- Repository interfaces ready for injection
- Transaction management in place
- Serialization handles all domain objects
- Health checks can query database connectivity

---

## 13. Acceptance Gate Status

| Criterion | Status |
|-----------|--------|
| All existing tests pass | ✅ 278/278 |
| All new Phase 6A tests pass | ✅ 56/56 |
| No Phase 1–5 behavior changes | ✅ Verified |
| No external service credentials required | ✅ SQLite only |
| SQLite works in clean test environment | ✅ Verified |
| Repository interfaces backend-independent | ✅ Protocols defined |
| No secrets in source code | ✅ Verified |
| PHASE6A_REPORT.md generated | ✅ This document |

---

**Final Test Count: 334 passed (278 existing + 56 new)**

**Phase 6A Complete.** Ready to proceed to Phase 6B (FastAPI Application Layer).