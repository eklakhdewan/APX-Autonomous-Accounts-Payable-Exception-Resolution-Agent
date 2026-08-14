# APX V1.1 — Claude Code Phase 1 Implementation Brief

## 0. Purpose

You are implementing **Phase 1 only** of a project called **APX (Autonomous Accounts Payable Exception Resolution Agent)**.

You have no prior context about this project. Treat this document as the authoritative implementation brief for the current phase.

**Important:** The APX V1.1 architecture is already frozen. Do NOT redesign the architecture, introduce additional agents, replace the state-machine approach, add a knowledge graph, switch databases, or add unnecessary frameworks during Phase 1.

Your job now is to build a clean, deterministic, testable foundation.

---

# 1. What APX Is

APX is an evidence-grounded agentic accounts-payable system intended to:

1. ingest invoice information,
2. validate it against business records,
3. detect exceptions,
4. later retrieve relevant evidence,
5. later use a bounded agent to investigate exceptions,
6. later make a risk-aware decision,
7. later pass actions through an action guardrail,
8. later execute or escalate actions,
9. provide complete observability and evaluation.

The complete architecture is:

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

Phase 1 implements only the foundation through deterministic validation.

---

# 2. Current Phase Boundary

## BUILD NOW

Implement:

- repository structure
- configuration
- `risk_policy.yaml`
- canonical domain/data schemas
- bootstrap synthetic dataset generator
- deterministic validation engine
- R1–R10 validation rules
- ground-truth generation
- validation/data-integrity tests
- deterministic/reproducible generation
- documentation needed to run Phase 1

## DO NOT BUILD NOW

Do NOT implement:

- LLM calls
- OpenRouter integration
- agents
- ReAct
- LangGraph
- bounded agent state machine
- BM25 retrieval
- dense retrieval
- pgvector
- RRF
- cross-encoder reranking
- RAG
- historical-resolution retrieval
- action execution
- email sending
- ERP integration
- UI/frontend
- production deployment
- Docker unless required purely for the Phase 1 development environment
- observability/tracing infrastructure beyond simple local logging needed for debugging
- Phase 2+ evaluation infrastructure

If a future component needs a type/interface, define the smallest clean contract necessary, but do not implement the future system.

---

# 3. Architecture Freeze Rule

The APX V1.1 architecture has already been reviewed and frozen.

Do not reinterpret this as permission to redesign it.

If you encounter an implementation issue:

1. determine whether it is an ordinary implementation problem;
2. solve it locally without changing architecture;
3. add a test if appropriate;
4. only flag a specification conflict if the existing specification genuinely makes implementation impossible or contradictory.

Do not make architectural changes silently.

---

# 4. Phase 1 Repository Structure

Create a clean Python project approximately following:

```text
apx/
├── config/
│   ├── __init__.py
│   ├── settings.py
│   └── risk_policy.yaml
│
├── data/
│   ├── __init__.py
│   ├── schemas.py
│   ├── generate_synthetic.py
│   └── datasets/
│       ├── bootstrap/
│       └── ground_truth/
│
├── intelligence/
│   ├── __init__.py
│   └── validator.py
│
├── exceptions/
│   ├── __init__.py
│   ├── models.py
│   └── taxonomy.py
│
├── tests/
│   ├── test_schemas.py
│   ├── test_data_generator.py
│   ├── test_validator.py
│   └── test_data_integrity.py
│
├── pyproject.toml
├── README.md
└── .gitignore
```

You may adjust filenames slightly if necessary for clean Python packaging, but preserve the separation of:

- configuration
- data contracts
- synthetic data
- deterministic intelligence
- exceptions
- tests

Do not create a giant monolithic file.

---

# 5. Canonical Domain Entities

The project revolves around linked AP records.

At minimum implement typed schemas for:

## Vendor

Suggested fields:

```text
vendor_id
vendor_name
tax_id
currency
payment_terms_days
credit_status
status
```

## PurchaseOrder

Suggested fields:

```text
po_id
vendor_id
po_number
po_date
currency
subtotal
tax
total
line_items
status
```

## PurchaseOrderLine

Suggested fields:

```text
line_id
description
quantity
unit_price
discount
tax_rate
```

## GoodsReceipt

Suggested fields:

```text
grn_id
po_id
vendor_id
receipt_date
line_items
status
```

## GoodsReceiptLine

Suggested fields:

```text
line_id
po_line_id
quantity_received
```

## Invoice

Suggested fields:

```text
invoice_id
vendor_id
invoice_number
po_number
invoice_date
due_date
currency
subtotal
tax
total
discount
line_items
```

## InvoiceLine

Suggested fields:

```text
line_id
description
po_line_id
quantity
unit_price
discount
tax_rate
```

## Exception

Suggested fields:

```text
exception_code
severity
message
details
```

## ExceptionReport

Suggested fields:

```text
invoice_id
vendor_id
exceptions
validation_status
```

The exact schema can be refined during implementation, but it must be:

- typed
- explicit
- serializable
- deterministic
- shared by the generator and validator

Do not allow different modules to invent incompatible invoice representations.

---

# 6. Use a Strong Validation/Data Model

Use a suitable validation approach such as Pydantic if it is already part of the chosen Python stack.

Important properties:

- numeric fields should use appropriate numeric types
- IDs should be validated
- dates should use proper date/datetime types
- monetary calculations must avoid unsafe floating-point comparisons
- currencies must be explicit
- line items must be structured
- relationships between records must be validated

For money, prefer `Decimal` rather than binary floating-point arithmetic.

---

# 7. Synthetic Dataset — Bootstrap Tier

Generate the initial development dataset:

```text
200 invoices
50 purchase orders
30 goods receipts
20 vendors
```

This is the **Bootstrap Tier**.

It is NOT the final benchmark.

Later tiers are:

```text
Development Tier:
500 invoices
100+ POs
75+ GRNs
35+ vendors

Final Benchmark:
1,000+ invoices
200+ POs
150+ GRNs
50+ vendors
```

Do not attempt the full benchmark in Phase 1 unless it naturally falls out of a configurable generator.

The generator should support scaling later.

---

# 8. CRITICAL: Generate Linked Business Records

Do NOT generate independent random invoices, POs, and GRNs.

Create coherent relationships:

```text
Vendor
   │
   └── Purchase Order
          │
          └── Goods Receipt
                 │
                 └── Invoice
```

For example:

```text
Vendor V-0042
    ↓
PO-2026-0087
    ↓
GRN-2026-0114
    ↓
INV-2026-0331
```

The validator must be able to join these records through stable IDs.

---

# 9. Controlled Exception Injection

The generator must produce both:

- valid invoices
- deliberately corrupted invoices representing known exception cases

The ground truth must record what was intentionally injected.

The required initial exception taxonomy is:

```text
R1 Vendor mismatch
R2 PO mismatch
R3 Amount mismatch
R4 GRN mismatch
R5 Duplicate invoice
R6 Tax error
R7 Currency mismatch
R8 Line-item mismatch
R9 Discount error
R10 Credit issue
```

Do not rely on random corruption without recording the intended ground truth.

---

# 10. Ground Truth

Every generated invoice must have machine-readable ground truth.

For example:

```json
{
  "invoice_id": "INV-00142",
  "expected_exceptions": [
    "GRN_QUANTITY_MISMATCH"
  ],
  "expected_decision": "REQUEST_INFO"
}
```

Phase 1 primarily needs ground truth for deterministic detection.

The future decision field may be included if it can be generated reliably, but do not build the agent around it.

Ground truth must distinguish:

```text
NO_EXCEPTION
R1
R2
...
R10
```

and allow multiple simultaneous exceptions because the final benchmark will include novel exception combinations.

---

# 11. Deterministic Validator

Implement:

```text
intelligence/validator.py
```

with a clear API such as:

```python
validate_invoice(
    invoice,
    po,
    grn,
    vendor,
) -> ExceptionReport
```

or an equivalent class-based interface.

The validator must have:

## ZERO LLM DEPENDENCY

It must be:

- deterministic
- unit-testable
- reproducible
- explainable

The validator produces facts and violations.

It does NOT decide how an agent should resolve them.

---

# 12. R1–R10 Validation Rules

Implement the following as deterministic rules.

## R1 — Vendor mismatch

Detect when the invoice vendor is inconsistent with the relevant PO/vendor relationship.

Example:

```text
Invoice vendor = V-001
PO vendor      = V-002
→ exception
```

---

## R2 — PO mismatch

Detect:

- missing referenced PO
- invalid PO reference
- invoice referencing a PO belonging to a different vendor

Do not let an LLM determine whether a PO exists.

---

## R3 — Amount mismatch

Compare invoice financial totals with the expected PO-derived amount according to the project’s defined tolerance.

Use `Decimal`.

Do not use naive:

```python
invoice_total == po_total
```

if the specification defines a tolerance.

The tolerance should be configuration-driven where appropriate.

---

## R4 — GRN mismatch

Compare invoiced quantities with received quantities.

Example:

```text
Invoice quantity = 100
Received quantity = 95
→ GRN mismatch
```

This must be deterministic.

---

## R5 — Duplicate invoice

Detect duplicate invoice records using appropriate deterministic identity criteria such as:

- vendor
- invoice number
- relevant amount/reference fields

The exact deduplication key should be explicit and tested.

---

## R6 — Tax error

Validate tax calculation against the applicable structured tax information in the dataset.

Do not ask an LLM to calculate tax.

Use deterministic arithmetic and defined tolerance.

---

## R7 — Currency mismatch

Detect inconsistencies between:

- invoice currency
- PO currency
- vendor-supported currency

Do not silently convert currencies unless an explicit exchange-rate model exists.

---

## R8 — Line-item mismatch

Compare invoice lines against PO lines for relevant:

- item/reference
- quantity
- unit price
- line association

This is distinct from the aggregate amount check.

---

## R9 — Discount error

Validate discount values against the PO/business data.

Detect:

- unexpected discount
- incorrect discount amount
- discount exceeding allowed value

Keep the calculation deterministic.

---

## R10 — Credit issue

Detect vendor credit-status conditions that should become an exception.

For example:

```text
vendor credit_status = HOLD
→ CREDIT_ISSUE
```

This is a deterministic fact.

Do not let the future agent infer the vendor's credit status from prose.

---

# 13. Exception Taxonomy

Create canonical exception codes.

Use stable machine-readable names, for example:

```text
VENDOR_MISMATCH
PO_MISMATCH
AMOUNT_MISMATCH
GRN_MISMATCH
DUPLICATE_INVOICE
TAX_ERROR
CURRENCY_MISMATCH
LINE_ITEM_MISMATCH
DISCOUNT_ERROR
CREDIT_ISSUE
```

Each exception should contain:

```text
code
severity
message
details
```

Severity should be deterministic/configurable where possible.

Do not let exception strings vary randomly between runs.

---

# 14. Risk Policy Configuration

Create:

```text
config/risk_policy.yaml
```

This is the project's safety/policy contract.

It should contain configuration for:

```text
amount risk
severity risk
confidence risk
evidence risk
historical risk

compound risk weights

amount thresholds

confidence thresholds

evidence thresholds

historical success thresholds

always-escalate rules

auto-resolve rules
```

The five compound-risk dimensions are:

```text
amount
severity
confidence
evidence
historical
```

The final risk engine is future work.

Phase 1 only needs the policy file and configuration loader.

Do not implement the agent's compound-risk engine yet unless it is required for validating the configuration itself.

---

# 15. Configuration Loader

Implement a small typed configuration loader in:

```text
config/settings.py
```

Requirements:

- load YAML
- validate required fields
- expose configuration to Python
- fail clearly on malformed configuration
- avoid hard-coded policy values throughout the codebase

The YAML file should be the source of truth.

---

# 16. Reproducibility

Synthetic data generation MUST support a fixed seed.

Example:

```bash
python -m data.generate_synthetic --seed 42
```

Running the same command twice with the same seed should produce identical logical data.

If serialization ordering affects raw file bytes, ensure stable serialization/order so reproducibility is still meaningful.

The generator should allow the seed to be changed intentionally.

---

# 17. Data Integrity Tests

Before trusting the validator, test the generated dataset itself.

Tests should verify:

- every invoice references a valid vendor
- every PO references a valid vendor
- every GRN references a valid PO
- every invoice/PO relationship is valid unless intentionally corrupted
- line-item references are valid
- monetary totals are internally coherent where intended
- injected exceptions actually correspond to the ground truth
- no accidental orphan records exist
- IDs are unique
- duplicate cases are intentional rather than accidental
- the generator is reproducible with the same seed

---

# 18. Validator Test Strategy

For every R1–R10, create at least:

1. valid case
2. invalid case
3. boundary case where applicable
4. missing-data case where applicable

Examples:

```text
test_vendor_match
test_vendor_mismatch

test_po_match
test_po_missing

test_amount_match
test_amount_mismatch
test_amount_tolerance_boundary

test_grn_match
test_grn_quantity_mismatch

test_duplicate_invoice
test_unique_invoice

test_tax_valid
test_tax_error

test_currency_valid
test_currency_mismatch

test_line_items_match
test_line_items_mismatch

test_discount_valid
test_discount_error

test_credit_clear
test_credit_hold
```

Also test:

```text
multiple simultaneous exceptions
no exceptions
malformed input
missing optional fields
invalid references
```

---

# 19. Test Quality Requirements

Do not merely create tests that reproduce your implementation.

Tests must assert business behavior.

For example, this is weak:

```python
assert validator._check_grn(...) is False
```

Prefer:

```python
report = validator.validate(...)
assert "GRN_MISMATCH" in report.exception_codes
```

Test public behavior and domain contracts.

---

# 20. Expected Phase 1 Completion

At the end of Phase 1, the following flow must work:

```text
Synthetic generator
       ↓
200 coherent invoices/POs/GRNs/vendors
       ↓
Ground truth
       ↓
Deterministic validator
       ↓
ExceptionReport
       ↓
Automated tests
```

You should be able to answer:

```text
How many invoices were generated?
How many contained exceptions?
How many exceptions of each type?
How many did the validator detect correctly?
Which cases failed?
```

Do not proceed to RAG/agents until this foundation is trustworthy.

---

# 21. Phase 1 Acceptance Criteria

Phase 1 is complete only when:

- [ ] Repository structure exists
- [ ] Python project runs cleanly
- [ ] `risk_policy.yaml` exists and validates
- [ ] Canonical domain schemas exist
- [ ] 20 vendors can be generated
- [ ] 50 POs can be generated
- [ ] 30 GRNs can be generated
- [ ] 200 invoices can be generated
- [ ] Records are linked coherently
- [ ] Ground truth is generated
- [ ] R1–R10 are implemented
- [ ] Validator has zero LLM dependencies
- [ ] Validator is deterministic
- [ ] Duplicate detection is deterministic
- [ ] Monetary comparisons use safe numeric handling
- [ ] Data integrity tests pass
- [ ] Validator tests pass
- [ ] Boundary cases are tested
- [ ] Multiple-exception cases are tested
- [ ] Same seed produces reproducible results
- [ ] No future-phase components have been implemented
- [ ] README explains how to generate data and run tests

---

# 22. Development Discipline

Follow this sequence:

```text
Step 1
Create skeleton
       ↓
Step 2
Create schemas
       ↓
Step 3
Create risk policy
       ↓
Step 4
Implement generator
       ↓
Step 5
Validate generated data
       ↓
Step 6
Implement R1–R10
       ↓
Step 7
Write tests
       ↓
Step 8
Run complete Phase 1 test suite
       ↓
Step 9
Inspect failures
       ↓
Step 10
Fix implementation
```

Do not skip directly to agents.

---

# 23. Git/Commit Discipline

Prefer small logical commits:

```text
chore: initialize APX project structure
feat: add canonical AP domain schemas
feat: add risk policy configuration
feat: add deterministic synthetic dataset generator
feat: add R1-R10 deterministic validator
test: add APX validator and data integrity tests
docs: add Phase 1 implementation instructions
```

Do not make one giant commit containing everything if the repository is being version-controlled.

---

# 24. What You Must Report Back

When Phase 1 implementation is complete, report:

## Files created

List them.

## Tests

Report:

```text
pytest result
number passed
number failed
coverage if available
```

## Dataset

Report:

```text
vendors:
POs:
GRNs:
invoices:
exception distribution:
```

## Validator

Report detection performance against generated ground truth.

At minimum:

```text
per-rule detection
overall precision
overall recall
overall F1
false positives
false negatives
```

If these metrics are not yet meaningful because of the chosen test methodology, explain why instead of inventing numbers.

## Problems

List any implementation problems encountered.

## Architecture changes

This must explicitly say one of:

```text
Architecture changes: NONE
```

or, if something genuinely blocked implementation:

```text
Architecture changes proposed:
...
Reason:
...
```

Do not silently change the frozen architecture.

---

# 25. Important Future Architecture — Context Only

You are NOT implementing these now, but you must understand where Phase 1 fits.

## Phase 2 — Hybrid Context Engine

Future retrieval architecture:

```text
Query
  ↓
BM25 ─────────┐
              ├── RRF Fusion
Dense ────────┘
                  ↓
          Cross-Encoder Reranker
                  ↓
             Evidence Set
```

Target architecture uses:

- BM25 lexical retrieval
- dense retrieval
- RRF fusion
- cross-encoder reranking

The final evaluation profile may use:

```text
BAAI/bge-large-en-v1.5
BAAI/bge-reranker-large
```

Development environments may use lighter profiles.

---

# 26. Future Agent Architecture — Context Only

Later the agent will be bounded by an explicit state machine.

Conceptually:

```text
DETECTED
   ↓
CONTEXT_RETRIEVED
   ↓
INVESTIGATING
   ↓
DECISION_READY
   ↓
 ┌─────────┬─────────────┬──────────┐
 ↓         ↓             ↓
RESOLVE   REQUEST_INFO  ESCALATE
```

The system controls permitted transitions.

The LLM does NOT control arbitrary workflow state.

There will be a maximum investigation/tool-call budget.

---

# 27. Future Evidence Model — Context Only

Historical evidence will eventually include explicit scope and validity information such as:

```text
evidence_id
type
scope
vendor_id where applicable
effective_from
effective_until
policy_version
outcome
source_authority
```

Evidence must eventually be checked for:

- scope
- vendor applicability
- effective date
- policy version
- outcome
- authority

Do not implement this retrieval system during Phase 1.

---

# 28. Future Action Guardrail — Context Only

The future architecture includes:

```text
AGENT DECISION
      ↓
ACTION GUARDRAIL
      ├── permitted?
      ├── evidence sufficient?
      ├── risk acceptable?
      ├── approval required?
      ├── idempotency OK?
      └── rate limit OK?
      ↓
ACTION
```

An agent decision is NOT automatically an authorized action.

This boundary is important and must remain intact.

---

# 29. Final Instruction

You are acting as an implementation engineer, not an architect for this phase.

The architecture is already frozen.

Build **Phase 1 only**.

Priorities, in order:

1. correctness
2. deterministic behavior
3. clean domain contracts
4. reproducibility
5. testability
6. maintainability
7. simplicity

Do not optimize for flashy AI features.

The first milestone is deliberately boring:

> **Generate coherent AP data and prove that deterministic validation can reliably detect known invoice exceptions.**

Once that works, the project has a trustworthy foundation for the retrieval and agentic layers.

**Start by inspecting the repository/environment, then implement Phase 1 incrementally. Do not ask for the entire project to be built at once.**
