# ROOT_CAUSE_REPORT.md
## Phase 5 Benchmark - Root Cause Analysis

**Date:** 2026-08-16  
**Benchmark Run:** 440-case dev benchmark (seed=42)  
**Status:** Infrastructure working, metric correctness issues identified

---

## Summary of Failed Metrics

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| Detection Precision | 14.42% | N/A | ❌ Low |
| Detection Recall | 99.48% | N/A | ✅ High |
| Detection F1 | 25.18% | > 85% | ❌ FAIL |
| Retrieval Recall@5 | 0.00% | > 70% | ❌ FAIL |
| Retrieval Recall@10 | 0.00% | N/A | ❌ FAIL |
| MRR | 0.0000 | N/A | ❌ FAIL |
| nDCG@10 | 0.0000 | N/A | ❌ FAIL |
| Decision Outcome Accuracy | 0.00% | > 85% | ❌ FAIL |
| Risk Classification Accuracy | 100.00% | N/A | ⚠️ Hardcoded |
| Escalation Accuracy | 100.00% | N/A | ⚠️ Tautological |
| Unauthorized Action Rate | 0.00% | = 0% | ✅ PASS |
| Automation Rate | 12.0% | > 50% | ❌ FAIL |

---

## 1. RETRIEVAL ROOT CAUSE

### Exact Source
**File:** `apx/evaluation/benchmark.py` lines 319-327

### Code in Question
```python
# Lines 319-327 in benchmark.py
relevance_labels = {}
for es in evidence_sets:
    if es.invoice_id in gt_map:
        gt = gt_map[es.invoice_id]
        # Get relevant evidence IDs from evaluation dataset
        relevant = set()
        irrelevant = set()
        invalid = set()
        # This would come from the evaluation dataset
        relevance_labels[es.invoice_id] = {
            "relevant": relevant,
            "irrelevant": irrelevant,
            "invalid": invalid,
        }
```

### Root Cause
**The benchmark creates EMPTY relevance labels instead of loading from the evaluation dataset.** The comment explicitly says "This would come from the evaluation dataset" but the code creates empty sets. The `eval_dataset.json` contains 10 cases with proper `relevant_evidence_ids`, `irrelevant_evidence_ids`, `invalid_evidence_ids` but they are never loaded.

### Evidence
- `eval_dataset.json` has 10 cases with proper relevance labels (e.g., EVAL-001 has `relevant_evidence_ids: ["EV-00061"]`)
- EV-00061 EXISTS in `evidence_corpus.json` and belongs to V-0001
- Retrieval actually returns EV-00061 at rank 9 for V-0001 invoices
- But `relevant = set()` means Recall@5 = 0/1 = 0%

### Data Alignment Issue
- **Generated invoices**: 500 invoices with IDs like `INV-2026-0018`, vendor V-0001 through V-0035
- **Eval dataset**: 10 cases with IDs `EVAL-001` through `EVAL-010`, vendors V-0001 through V-0010
- **No mapping exists** between generated invoice IDs and eval dataset case IDs
- The benchmark uses `es.invoice_id` as the key for `relevance_labels` but eval dataset uses `case_id`

### Type: DATA / EVALUATION LOGIC

### Recommended Fix
**Option A (Minimal):** Load eval dataset and map by vendor_id + exception_type
```python
# In benchmark.py run_benchmarks(), after loading eval dataset:
eval_cases = { (c["vendor_id"], c["exception_type"]): c for c in eval_data["cases"] }
# Then in retrieval evaluation loop:
key = (es.vendor_id, es.exception_codes[0] if es.exception_codes else "UNKNOWN")
eval_case = eval_cases.get(key)
if eval_case:
    relevant = set(eval_case["relevant_evidence_ids"])
    irrelevant = set(eval_case["irrelevant_evidence_ids"])
    invalid = set(eval_case["invalid_evidence_ids"])
else:
    relevant = irrelevant = invalid = set()
```

**Option B (Proper):** Use the evaluation dataset as the primary test set instead of generating 500 random invoices.

### Confidence: HIGH (95%)

---

## 2. DECISION ROOT CAUSE

### Exact Source
**File:** `apx/evaluation/decision_eval.py` lines 73-81

### Code in Question
```python
# Lines 73-81 in decision_eval.py
predicted = investigation_result.outcome
expected = ground_truth.expected_decision

# Map string to TerminalOutcome if needed
if isinstance(expected, str):
    try:
        expected = TerminalOutcome(expected)
    except ValueError:
        expected = None
```

### Root Cause
**Enum mismatch between ground truth and evaluation code:**
- **GroundTruth.expected_decision** uses: `"AUTO_APPROVE"`, `"REVIEW"`, `"ESCALATE"`
- **TerminalOutcome enum** only has: `"RESOLVE"`, `"REQUEST_INFO"`, `"ESCALATE"`

The conversion fails for `"AUTO_APPROVE"` and `"REVIEW"` (not in TerminalOutcome), setting `expected = None`, causing accuracy = 0%.

### Evidence
- TerminalOutcome values: `['RESOLVE', 'REQUEST_INFO', 'ESCALATE']`
- GroundTruth.expected_decision values: `"AUTO_APPROVE"`, `"REVIEW"`, etc. (from synthetic data generator)
- Line 79: `except ValueError: expected = None` silently swallows the mismatch
- Result: `predicted == expected` is always False when expected is None

### Type: EVALUATION LOGIC / PIPELINE LOGIC MISMATCH

### Recommended Fix
**Option A:** Map ground truth decisions to TerminalOutcome
```python
# In decision_eval.py evaluate_investigation_outcome():
DECISION_MAP = {
    "AUTO_APPROVE": TerminalOutcome.RESOLVE,
    "REVIEW": TerminalOutcome.REQUEST_INFO,
    "ESCALATE": TerminalOutcome.ESCALATE,
}
expected = DECISION_MAP.get(ground_truth.expected_decision)
if expected is None:
    # Try direct enum conversion as fallback
    try:
        expected = TerminalOutcome(ground_truth.expected_decision)
    except ValueError:
        expected = None
```

**Option B:** Update GroundTruth schema to use TerminalOutcome values directly.

### Confidence: HIGH (95%)

---

## 3. DETECTION ROOT CAUSE

### Exact Source
**File:** `apx/intelligence/validator.py` (Phase 1 validator) + `apx/evaluation/detection_eval.py`

### Root Cause
**Cascading exception detection vs. single-root-cause ground truth:**
- **Phase 1 Validator** detects cascading exceptions: AMOUNT_MISMATCH triggers LINE_ITEM_MISMATCH and CREDIT_ISSUE
- **Ground Truth** only contains the single injected root-cause exception (by design per Phase 1 spec)

### Evidence
From actual confusion matrix:
```
Invoice INV-2026-0001:
  Detected: {AMOUNT_MISMATCH, LINE_ITEM_MISMATCH, LINE_ITEM_MISMATCH, CREDIT_ISSUE}
  Expected: set()
  FP: 3 (all cascading)
  FN: 0

Invoice INV-2026-0003:
  Detected: {VENDOR_MISMATCH, CURRENCY_MISMATCH, CREDIT_ISSUE, PO_MISMATCH}
  Expected: {PO_MISMATCH}
  TP: 1, FP: 3, FN: 0
```

- **Precision = TP / (TP + FP) = 190 / (190 + 1128) = 14.42%**
- **Recall = TP / (TP + FN) = 190 / (190 + 1) = 99.48%**
- **F1 = 2 * 0.1442 * 0.9948 / (0.1442 + 0.9948) = 25.18%**

### Type: EXPECTED BEHAVIOR (per Phase 1 design)

### Design Intent
Per Phase 1 spec: "Phase 1 intentionally distinguishes root-cause ground truth from cascading validator detections. Preserve that behavior."

The detection evaluator is CORRECTLY measuring precision against root-cause ground truth. The low precision is expected because the validator intentionally over-detects (cascading).

### Recommended Fix
**No code fix needed** - this is expected behavior. The metric target (>85% F1) is incompatible with the Phase 1 design. Options:
1. **Adjust target** to reflect cascading detection reality
2. **Change evaluator** to measure root-cause precision separately from cascading precision
3. **Update ground truth** to include cascading exceptions (but violates Phase 1 design)

### Confidence: HIGH (95%)

---

## 4. DATASET ALIGNMENT FINDING

### Finding
**The 500 generated invoices and the 10-case evaluation dataset are NOT aligned.**

| Aspect | Generated Data (500 invoices) | Eval Dataset (10 cases) |
|--------|------------------------------|------------------------|
| Invoice IDs | `INV-2026-0001` to `INV-2026-0500` | `EVAL-001` to `EVAL-010` |
| Vendor IDs | V-0001 to V-0035 | V-0001 to V-0010 |
| Exception Types | All 10 types, multiple per invoice | One per case |
| Ground Truth | Per-invoice (injected) | Per-case (curated) |
| Relevance Labels | None | Per-case (10 cases) |

**No mapping exists** between generated invoices and eval cases. The benchmark treats them as independent datasets.

### Impact
- Retrieval evaluation uses empty labels (0% Recall)
- Decision evaluation compares generated GT (AUTO_APPROVE) vs pipeline (ESCALATE)
- Detection uses generated GT (single injected) vs validator (cascading)

### Type: DATA / ARCHITECTURE

### Recommended Fix
**Choose ONE evaluation strategy:**

**Option A: Use eval dataset as primary test set**
- Load the 10 eval cases
- Run pipeline on each
- Use their curated labels for all 6 layers

**Option B: Generate synthetic eval labels for all 500 invoices**
- Run `populate_eval_labels.py` on the 500 generated invoices
- Use those labels for evaluation

**Option C: Keep both separate**
- Run 500-invoice benchmark for system integration/smoke test
- Run 10-case eval dataset for metric measurement
- Report both separately

### Confidence: HIGH (95%)

---

## 5. AUTOMATION RATE (Secondary)

### Finding
**Automation Rate = 12%** because 88% of invoices have exceptions and get ESCALATE.

### Root Cause
- 440/500 invoices have exceptions (88%)
- Most exception invoices → ESCALATE outcome
- Only 60 clean invoices → RESOLVE (automation)

### Type: EXPECTED BEHAVIOR

### Note
This is a consequence of the data distribution (88% exception rate). The 50% target assumes a different exception rate.

---

## Files Inspected

| File | Purpose |
|------|---------|
| `apx/evaluation/benchmark.py` | Main benchmark orchestration (lines 319-327, 330-342) |
| `apx/evaluation/retrieval_eval.py` | Retrieval metrics computation |
| `apx/evaluation/decision_eval.py` | Decision metrics (lines 73-81, 149-177) |
| `apx/evaluation/detection_eval.py` | Detection metrics |
| `apx/evaluation/benchmark.py` | Decision evaluation call (lines 330-342) |
| `apx/evaluation/extraction_eval.py` | Layer 1 extraction |
| `apx/evaluation/action_eval.py` | Layer 5 action |
| `apx/evaluation/business_eval.py` | Layer 6 business |
| `apx/evaluation/benchmark.py` | Full pipeline orchestration |
| `apx/evaluation/decision_eval.py` | Decision evaluation logic |
| `apx/data/datasets/eval/eval_dataset.json` | Evaluation labels (10 cases) |
| `apx/data/datasets/evidence/evidence_corpus.json` | Evidence corpus (235 items) |
| `apx/data/generate_synthetic.py` | Synthetic data generation |
| `apx/intelligence/validator.py` | Phase 1 validator |
| `apx/evidence/populate_eval_labels.py` | Eval label generation script |

---

## Tests Run / Results

| Test | Result |
|------|--------|
| Phase 4/action tests (`test_phase4_action.py`) | 29/29 PASSED |
| All unit tests | 213/213 PASSED |
| 5-retrieval pool test | 5/5 PASSED |
| 10-retrieval pool test | 10/10 PASSED |
| Import validation | ✅ PASS |
| 440-case benchmark execution | Completed (metrics failed) |

---

## Recommended Fixes Priority

| Priority | Fix | File | Impact |
|----------|-----|------|--------|
| **P0** | Fix retrieval label loading | `benchmark.py` lines 319-327 | Enables Retrieval metrics |
| **P0** | Fix Decision enum mapping | `decision_eval.py` lines 73-81 | Enables Decision Accuracy |
| **P1** | Align eval dataset with benchmark | `benchmark.py` or new eval runner | Enables all 6 layers |
| **P2** | Document Detection precision expectation | Docs / eval config | Correct metric interpretation |

---

## Whether Full Benchmark Safe to Rerun

**YES, after P0 fixes are applied.** The infrastructure works perfectly (440/440 retrievals, no crashes). The metric failures are due to evaluation logic bugs, not infrastructure failures.

**Next Steps:**
1. Apply P0 fixes to `benchmark.py` and `decision_eval.py`
2. Run targeted tests (5-retrieval, decision eval unit tests)
3. Re-run full 440-case benchmark
4. Verify all 6 layers produce numeric metrics

---

**Confidence in Root Causes:** 95%  
**No fabrication, no threshold changes, no architecture modifications needed.**