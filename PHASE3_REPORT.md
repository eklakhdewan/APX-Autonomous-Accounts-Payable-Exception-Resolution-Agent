# APX V1.1 — Phase 3 Freeze Report

**Date:** 2026-08-14
**Status:** PHASE 3 COMPLETE — FROZEN
**Architecture Changes:** NONE

---

## 1. Summary

Phase 3 implements the **Bounded Investigation Agent** — the deterministic, evidence-grounded investigation layer that sits between the Phase 2 Hybrid Context Engine and the future Phase 4 Decision/Risk/Action layers.

The agent consumes a Phase 1 `ExceptionReport` and a Phase 2 `EvidenceSet`, performs a bounded investigation using a deterministic state machine with configurable budget, and produces a structured `InvestigationResult` with one of three terminal outcomes: `RESOLVE`, `REQUEST_INFO`, or `ESCALATE`.

**Key guarantees:**
- Zero LLM control over workflow state (state machine is deterministic)
- Evidence validation boundary respected (no bypass)
- Budget-bounded investigation (configurable max steps, safe exhaustion handling)
- Fully reproducible with mock LLM provider
- No action execution, risk engine, or guardrail logic (Phase 4+)

---

## 2. Files Created/Modified

### New Files (Phase 3)

| File | Purpose |
|------|---------|
| `apx/agent/__init__.py` | Package exports |
| `apx/agent/state_machine.py` | AgentState, TerminalOutcome, PERMITTED_TRANSITIONS, transition logic |
| `apx/agent/models.py` | InvestigationStep, InvestigationResult, InvestigationContext |
| `apx/agent/controller.py` | BoundedInvestigationAgent, run_investigation() |
| `apx/agent/llm/__init__.py` | LLM package exports |
| `apx/agent/llm/base.py` | LLMProvider abstract base, InvestigationFindings |
| `apx/agent/llm/mock.py` | MockLLMProvider (deterministic, no network) |
| `apx/tests/test_phase3_state_machine.py` | 8 state machine tests |
| `apx/tests/test_phase3_budget.py` | 7 budget enforcement tests |
| `apx/tests/test_phase3_agent.py` | 9 agent/LLM/model tests |
| `apx/tests/test_phase3_integration.py` | 11 end-to-end integration tests |

### Modified Files

| File | Change |
|------|--------|
| `apx/config/retrieval_profiles.yaml` | Added `agent` section with `max_investigation_steps` and `default_llm_provider` |
| `apx/config/settings.py` | Added `AgentSettings`, updated `Settings.load()` to load agent config |

---

## 3. State Machine

### States (AgentState)
```
DETECTED
    ↓
CONTEXT_RETRIEVED
    ↓
INVESTIGATING
    ↓
DECISION_READY
```

### Terminal Outcomes (TerminalOutcome)
```
RESOLVE
REQUEST_INFO
ESCALATE
```

### Permitted Transitions (PERMITTED_TRANSITIONS)
| Current State | Allowed Next |
|---------------|--------------|
| DETECTED | CONTEXT_RETRIEVED |
| CONTEXT_RETRIEVED | INVESTIGATING |
| INVESTIGATING | INVESTIGATING, DECISION_READY |
| DECISION_READY | RESOLVE, REQUEST_INFO, ESCALATE |

**All other transitions are rejected with `TransitionError`.** Terminal outcomes have no outgoing transitions.

---

## 4. Investigation Budget

| Parameter | Value | Source |
|-----------|-------|--------|
| Default max steps | 10 | `agent.max_investigation_steps` in `retrieval_profiles.yaml` |
| Configurable | Yes | Via `agent.max_investigation_steps` in retrieval profile |
| Minimum | 1 | Enforced by `Field(ge=1)` |

**Budget exhaustion behavior:**
- When `budget_used >= budget_limit`, investigation terminates
- Termination reason: "Budget exhausted"
- Outcome: `ESCALATE` (safe default)
- No infinite loops possible (enforced by controller)

---

## 5. LLM Boundary

### Provider Interface (`LLMProvider`)
```python
class LLMProvider(ABC):
    @abstractmethod
    def investigate(
        self,
        exception_report: str,
        evidence_summaries: list[dict],
        current_state: str,
        budget_remaining: int,
    ) -> InvestigationFindings:
        pass
```

### Mock Provider (`MockLLMProvider`)
- **Deterministic** — Same seed produces identical output
- **No network/API** — Pure Python, zero dependencies
- **Structured output** — Returns `InvestigationFindings` (Pydantic model)
- **Test-only** — Used by default in DEV profile

### Output Validation
- `InvestigationFindings` validated by Pydantic before use
- Evidence IDs validated against `EvidenceSet` (invalid IDs rejected)
- Confidence threshold gates decision (0.7 default)

### Arbitrary State Prevention
- LLM output → `InvestigationFindings` validation → Controller policy → State transition
- LLM **cannot** directly set agent state
- Invalid transitions rejected by `transition()` function

---

## 6. Evidence Boundary

### Consumption
- Agent receives `EvidenceSet` from `HybridContextEngine.retrieve()`
- Only `validated_evidence` (post-validity filtering) is consumed
- Agent **never** accesses raw corpus or bypasses Phase 2 validation

### Validation
- Evidence IDs referenced by LLM validated against `EvidenceSet.validated_evidence`
- Invalid/missing IDs silently dropped (logged, not fatal)
- Agent cannot invent evidence or reference non-existent IDs

### Separation Maintained
- `RetrievedCandidate` = raw retrieval results (pre-validation)
- `ValidatedEvidence` = post-validity filtering (trusted)
- `EvidenceSet` exposes both, agent only uses `validated_evidence`

---

## 7. Test Results

| Test Suite | Tests | Passed | Failed |
|------------|-------|--------|--------|
| test_benchmark.py | 12 | 12 | 0 |
| test_data_generator.py | 8 | 8 | 0 |
| test_data_integrity.py | 15 | 15 | 0 |
| test_eval_dataset.py | 4 | 4 | 0 |
| test_phase2_evidence.py | 16 | 16 | 0 |
| **test_phase3_state_machine.py** | **8** | **8** | **0** |
| **test_phase3_budget.py** | **7** | **7** | **0** |
| **test_phase3_agent.py** | **9** | **9** | **0** |
| **test_phase3_integration.py** | **11** | **11** | **0** |
| test_schemas.py | 15 | 15 | 0 |
| test_validator.py | 31 | 31 | 0 |
| **Total** | **136** | **136** | **0** |

**Phase 1 tests:** 81 passed  
**Phase 2 tests:** 20 passed  
**Phase 3 tests:** 35 passed  
**All tests:** 136 passed

---

## 8. Integration Verification

### End-to-End Pipeline Verified
```
ExceptionReport (Phase 1)
        ↓
HybridContextEngine (Phase 2)
        ↓
EvidenceSet (validated)
        ↓
BoundedInvestigationAgent (Phase 3)
        ↓
InvestigationResult
```

### Verified Behaviors
- ✅ Phase 1 ExceptionReport consumed and preserved in result
- ✅ Phase 2 EvidenceSet consumed; validated_evidence used
- ✅ Evidence validation boundary respected (no bypass)
- ✅ Invalid evidence IDs rejected (not used)
- ✅ Multiple exception types handled
- ✅ Empty evidence set handled gracefully
- ✅ Deterministic execution (same seed = identical result)
- ✅ All terminal outcomes reachable (RESOLVE, REQUEST_INFO, ESCALATE)
- ✅ Mock LLM deterministic (same seed = identical findings)
- ✅ Budget enforced (steps counted, limit enforced)
- ✅ Budget exhaustion → safe ESCALATE
- ✅ No action execution (only InvestigationResult produced)
- ✅ Structured result with steps, findings, budget usage

---

## 9. Non-Goals Preserved

| Non-Goal | Status |
|----------|--------|
| LLM calls (production) | ❌ Not implemented (mock only) |
| OpenRouter integration | ❌ Not implemented |
| ReAct / LangGraph | ❌ Not used |
| Bounded state-machine execution | ✅ Implemented (deterministic) |
| Risk-policy decision engine | ❌ Not implemented (Phase 4) |
| Compound risk scoring | ❌ Not implemented (Phase 4) |
| Action execution | ❌ Not implemented (Phase 4) |
| ERP integration | ❌ Not implemented |
| Email/Slack/Jira actions | ❌ Not implemented |
| UI/Frontend | ❌ Not implemented |
| Production deployment | ❌ Not implemented |
| Action Guardrail | ❌ Not implemented (Phase 4) |
| Compound Risk Engine | ❌ Not implemented (Phase 4) |

---

## 10. Architecture Changes

**Architecture changes: NONE**

The implementation strictly follows the frozen APX V1.1 architecture:
- Phase 1 (Deterministic Validator) unchanged
- Phase 2 (Hybrid Context Engine) unchanged
- Phase 3 adds only the bounded agent layer between Phase 2 and future Phase 4
- No modifications to Phase 1 schemas, validator, or Phase 2 engine/schemas

---

## 11. Phase 4 Handoff

Phase 3 produces the following for Phase 4 consumption:

| Output | Description |
|--------|-------------|
| `InvestigationResult` | Structured investigation outcome with evidence trail |
| `TerminalOutcome` | One of: RESOLVE, REQUEST_INFO, ESCALATE |
| `evidence_ids` | List of evidence IDs supporting the conclusion |
| `findings` | Human-readable investigation summary |
| `steps` | Full audit trail of investigation steps |
| `budget_usage` | Steps used vs. limit |
| `termination_reason` | Why investigation ended |

**Phase 4 will implement:**
- Compound Risk Engine (5 dimensions)
- Action Guardrail (permitted/approval/idempotency/rate-limit)
- Action execution (ERP, email, payment, etc.)
- Human-in-the-loop review workflow

---

## 12. Final Verification Checklist

- [x] Bounded state machine implemented
- [x] Explicit permitted transitions implemented
- [x] Invalid transitions rejected with `TransitionError`
- [x] Maximum investigation budget enforced
- [x] Budget exhaustion handled safely (ESCALATE)
- [x] ExceptionReport consumed from Phase 1
- [x] EvidenceSet consumed from Phase 2
- [x] No evidence-validation bypass
- [x] Evidence references validated against EvidenceSet
- [x] Typed InvestigationResult implemented
- [x] Investigation steps represented structurally
- [x] LLM provider abstraction implemented
- [x] Deterministic mock LLM implemented
- [x] Production provider isolated behind interface
- [x] LLM cannot control arbitrary workflow state
- [x] LLM cannot execute actions
- [x] No risk engine implemented
- [x] No action guardrail implemented
- [x] No ERP/email/Slack/Jira/action execution
- [x] No UI
- [x] No LangGraph/ReAct/agent frameworks
- [x] Unit tests pass (136 total)
- [x] Integration tests pass
- [x] Deterministic mock execution reproducible
- [x] Phase 3 report generated
- [x] Architecture changes: NONE

---

## 13. Final Recommendation

**Phase 3 is FROZEN. Ready for Phase 4 handoff.**

```bash
git add -A
git commit -m "feat: APX Phase 3 complete — Bounded Investigation Agent

- Bounded state machine (DETECTED → CONTEXT_RETRIEVED → INVESTIGATING → DECISION_READY)
- Terminal outcomes: RESOLVE, REQUEST_INFO, ESCALATE
- Configurable investigation budget (default 10 steps, safe exhaustion → ESCALATE)
- LLM abstraction with deterministic mock provider
- Evidence-grounded investigation (Phase 2 EvidenceSet consumed, no bypass)
- Structured InvestigationResult with steps, findings, budget usage
- 35 new tests + 101 existing = 136 total passing
- Architecture frozen per APX V1.1 spec — no Phase 4 components
"
```

**PHASE 3 FROZEN. READY FOR PHASE 4 HANDOFF.**