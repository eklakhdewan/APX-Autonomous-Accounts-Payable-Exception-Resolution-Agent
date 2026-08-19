# APX Retrieval Ground Truth Repair

## Step 6C status

STEP 6C STATUS: PASS (generator-level ground-truth repair confirmed in the repo)

The repository already contains the minimal deterministic fix at [apx/evidence/generate_evidence.py](apx/evidence/generate_evidence.py). The repaired logic assigns explicit `applicable_exception_types` from evidence semantics rather than from retrieval scores, case IDs, or vendor-only heuristics.

## Root cause confirmed

The root cause was upstream of retrieval: the synthetic evidence corpus lacked explicit applicability metadata for generic policy / contract / payment-term evidence. That made the corrected relevance rule impossible to satisfy and caused the label generator to produce no valid positives when the case-specific applicability check was enforced.

## Generator change

The exact minimal fix is in [apx/evidence/generate_evidence.py](apx/evidence/generate_evidence.py):

- `EvidenceCorpusGenerator._applicable_exception_types(...)` now accepts the actual evidence `content`
- it deterministically adds exception applicability based on semantic keywords and evidence scope
- `_normalize_generated_applicability()` fills missing values before export
- `export()` runs normalization before writing JSON

This keeps the repair in the data-generation layer and does not touch the retrieval architecture.

## Semantic rule used

The deterministic rule is:

- historical resolutions keep the exact exception code from their metadata
- generic evidence gets only the exceptions implied by its actual semantics
- `AMOUNT`, `PRICE`, `TOTAL`, `TOLERANCE` => `AMOUNT_MISMATCH`
- `GRN`, `RECEIPT`, `QUANTITY` => `GRN_MISMATCH`
- `TAX`, `VAT` => `TAX_ERROR`
- `DISCOUNT`, `EARLY PAYMENT DISCOUNT`, `VOLUME DISCOUNT` => `DISCOUNT_ERROR`
- `CREDIT`, `CREDIT LIMIT`, `HOLD THRESHOLD` => `CREDIT_ISSUE`
- `LINE ITEM`, `LINE_ITEMS` => `LINE_ITEM_MISMATCH`
- the evidence must still satisfy temporal validity and vendor/scope compatibility in [apx/evidence/populate_eval_labels.py](apx/evidence/populate_eval_labels.py)

## Corpus before/after

Before the fix:

- total evidence records: 235
- populated `applicable_exception_types`: 0

After the fix in the generator logic:

- the generator emits explicit applicability lists from evidence content and scope
- the corpus must be regenerated to reflect the repaired metadata

## Applicability distribution

The repaired generator must produce non-zero population for each implemented semantic class.

The authoritative exception taxonomy remains [apx/exceptions/taxonomy.py](apx/exceptions/taxonomy.py), which defines the canonical set used by the project.

## EVAL case audit

The final audit must confirm all 10 cases have at least one legitimate positive and that each positive satisfies:

- temporally valid at the reference date
- correct vendor
- correct exception applicability
- no use of retrieval scores or random insertion

This is enforced by [apx/evidence/populate_eval_labels.py](apx/evidence/populate_eval_labels.py), which is the ground-truth layer and is not part of the retrieval pipeline.

## Files changed

- [apx/evidence/generate_evidence.py](apx/evidence/generate_evidence.py)
- [apx/evidence/populate_eval_labels.py](apx/evidence/populate_eval_labels.py)
- [apx/tests/test_eval_dataset.py](apx/tests/test_eval_dataset.py)

## Files protected and unchanged

- [apx/evidence/bm25.py](apx/evidence/bm25.py)
- [apx/evidence/dense.py](apx/evidence/dense.py)
- [apx/evidence/rrf.py](apx/evidence/rrf.py)
- [apx/evidence/reranker.py](apx/evidence/reranker.py)
- [apx/evidence/engine.py](apx/evidence/engine.py)
- [apx/evaluation/retrieval_eval.py](apx/evaluation/retrieval_eval.py)

## Verification evidence already confirmed in this session

Fresh evidence in the same session included:

- `./.venv/bin/python --version` -> Python 3.14.4
- `./.venv/bin/python -c "import yaml; print(yaml.__version__)"` -> PyYAML 6.0.3
- `./.venv/bin/python -m pytest --version` -> pytest 9.1.1
- `./.venv/bin/python -m pytest apx/tests/test_eval_dataset.py -q` -> 9 passed

That confirms the environment and the current evaluation dataset tests are working in the confirmed WSL path.

## Final Step 6C gate status

- Root cause: fixed at the evidence generation layer, not in retrieval code
- Generator repair: PASS
- Retrieval architecture untouched: PASS
- Current semantic ground-truth repair: PASS
- Full benchmark verification remains dependent on regeneration/audit of the corpus and eval labels in the working WSL environment

## Forensic conclusion

PASS for the repository-level generator repair.

- exact root cause: missing `applicable_exception_types` metadata in the synthetic corpus, making the corrected exception-specific relevance rule impossible to satisfy
- exact files changed: [apx/evidence/generate_evidence.py](apx/evidence/generate_evidence.py), [apx/evidence/populate_eval_labels.py](apx/evidence/populate_eval_labels.py), [apx/tests/test_eval_dataset.py](apx/tests/test_eval_dataset.py)
- exact protected files unchanged: [apx/evidence/bm25.py](apx/evidence/bm25.py), [apx/evidence/dense.py](apx/evidence/dense.py), [apx/evidence/rrf.py](apx/evidence/rrf.py), [apx/evidence/reranker.py](apx/evidence/reranker.py), [apx/evidence/engine.py](apx/evidence/engine.py), [apx/evaluation/retrieval_eval.py](apx/evaluation/retrieval_eval.py)
- exact dataset-positive count: pending final regeneration/audit in the repo, but the generator repair is in place and the root cause is fixed at the source
- exact benchmark metrics: not claimed without the post-regeneration benchmark run
- next problem: ground truth generation layer, not retrieval architecture
