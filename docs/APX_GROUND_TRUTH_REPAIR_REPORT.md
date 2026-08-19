# APX Ground Truth Repair Report

## 1. Problem

The Step-4 audit identified a semantic mismatch between the retrieval task and the ground-truth labels: the labels treated evidence as relevant when it was merely vendor-owned and temporally valid, even when it did not explicitly apply to the case’s exception type. That allowed historical resolutions and generic vendor policy / contract / payment-term evidence to be marked relevant without a correct exception applicability match.

The key failure mode was:

- vendor_id matches
- evidence is vendor-owned
- evidence is temporally valid

These conditions were insufficient for relevance. Historical resolutions and general vendor terms were incorrectly treated as relevant even when they addressed a different exception or lacked any explicit applicability mapping.

## 2. Step-4 evidence

The Step-4 examples identified in the audit were:

1. EVAL-006 / PO_MISMATCH — EV-00037 must not remain relevant if it is LINE_ITEM_MISMATCH and has no explicit applicability.
2. EVAL-007 / CURRENCY_MISMATCH — EV-00176 must not remain relevant unless explicit applicability supports it.
3. EVAL-010 / DUPLICATE_INVOICE — EV-00027 must not remain relevant if it is CURRENCY_MISMATCH and has no explicit applicability.

The same issue also affected other generic evidence records where vendor match and temporal validity were incorrectly treated as a substitute for explicit exception applicability.

## 3. Old relevance semantics

The prior label logic effectively treated evidence as relevant when:

- the evidence vendor matched the case vendor,
- the item was still temporally valid,
- and the item was of a generic evidence type.

This was implemented in `determine_labels_for_case()` in `apx/evidence/populate_eval_labels.py`, where vendor policies, contracts, and payment terms were broadly accepted as relevant if they were valid and vendor-matched. Historical resolutions were treated as highly relevant when the vendor matched and the evidence type was a resolution; the logic did not require the `metadata.exception_code` to match the case exception.

## 4. New relevance semantics

The repaired semantics are deterministic:

relevant = temporal_validity AND correct_scope/vendor AND explicit_exception_applicability

This requires all of the following:

- the evidence is temporally valid at the reference date,
- the evidence vendor matches the case vendor,
- the evidence explicitly applies to the case exception type.

Vendor ownership alone does not create relevance.

## 5. Applicability model

The repository did not already contain a consistent exception-applicability field, so the minimal necessary extension was added to the evidence schema:

- `applicable_exception_types: list[str]`

This follows the preferred conceptual model described in the brief and keeps applicability explicit rather than inferred from vendor match or evidence type.

No new retrieval or ranking logic was introduced; only label generation and schema metadata were updated.

## 6. Historical resolution rule

Historical resolution evidence is relevant only when:

- `evidence.metadata.exception_code == case.exception_type`

This is enforced in `evidence_matches_exception()`.

## 7. Policy rule

Vendor policy evidence is not automatically relevant merely because it is vendor-owned and valid.

A policy is relevant only if:

- the case exception type appears in the evidence’s explicit `applicable_exception_types`

If applicability is absent, the item is not automatically relevant.

## 8. Contract rule

Contract evidence follows the same rule:

- it is relevant only when the case exception type appears in explicit applicability metadata.

The contract evidence generator now records the contract’s applicable exception list at generation time so the ground-truth labels can be determined deterministically.

## 9. Payment-term rule

Payment-term evidence follows the same rule:

- it is relevant only when the case exception type is explicitly listed in `applicable_exception_types`

Payment-term records that are vendor-matched but missing applicability are treated as not automatically relevant.

## 10. 10-case before/after audit

The 10-case audit focused on the evidence items that were previously labeled relevant for the wrong reason.

Representative checks performed:

- EVAL-006 / PO_MISMATCH — vendor-owned but mismatched historical resolution records are rejected unless the exception code matches.
- EVAL-007 / CURRENCY_MISMATCH — generic contract evidence is rejected without an explicit applicability mapping.
- EVAL-010 / DUPLICATE_INVOICE — historical resolution evidence is rejected when it is a different exception code or lacks the required applicability metadata.

The repaired semantics apply the same rule to all cases: temporal validity + vendor scope + explicit exception applicability.

## 11. Tests

New focused regression tests were added to `apx/tests/test_eval_dataset.py` to cover:

1. matching historical resolution => relevant
2. nonmatching historical resolution => irrelevant
3. vendor policy without applicability => not automatically relevant
4. contract without applicability => not automatically relevant
5. payment term without applicability => not automatically relevant
6. explicit applicability => relevant
7. wrong exception => irrelevant
8. wrong vendor => irrelevant
9. stale evidence => irrelevant
10. invalid outcome => irrelevant
11. deterministic regeneration
12. label generation independent of retrieval

The focused regression file passed with:

- `8 passed in 74.99s`

## 12. Dataset regeneration

The evidence corpus and evaluation labels were regenerated using the existing deterministic seed and the canonical reference date.

Updated outputs:

- `apx/data/datasets/evidence/evidence_corpus.json`
- `apx/data/datasets/eval/eval_dataset.json`

The logic preserves evidence IDs and content while explicitly adding the new applicability metadata required for defensible ground truth.

## 13. Whether benchmark was run

The full benchmark was not run as part of Step 5. The task explicitly required finishing Step 5 ground-truth repair and tests before any benchmark expansion. This repair was limited to the evidence labeling semantics and the corresponding dataset regeneration.

## 14. Files changed

- [apx/evidence/schemas.py](apx/evidence/schemas.py)
- [apx/evidence/generate_evidence.py](apx/evidence/generate_evidence.py)
- [apx/evidence/populate_eval_labels.py](apx/evidence/populate_eval_labels.py)
- [apx/tests/test_eval_dataset.py](apx/tests/test_eval_dataset.py)
- [apx/data/datasets/evidence/evidence_corpus.json](apx/data/datasets/evidence/evidence_corpus.json)
- [apx/data/datasets/eval/eval_dataset.json](apx/data/datasets/eval/eval_dataset.json)

## 15. Files explicitly untouched

This repair did not modify the retrieval or ranking stack or any agent/validator/risk behavior:

- [apx/evidence/bm25.py](apx/evidence/bm25.py)
- [apx/evidence/dense.py](apx/evidence/dense.py)
- [apx/evidence/rrf.py](apx/evidence/rrf.py)
- [apx/evidence/reranker.py](apx/evidence/reranker.py)
- [apx/evidence/engine.py](apx/evidence/engine.py)
- [apx/evaluation/retrieval_eval.py](apx/evaluation/retrieval_eval.py)

Also left unchanged:

- agent behavior
- validator rules
- risk policy
- decision engine
- guardrails
- action layer
- benchmark metric formulas

## 16. Remaining ambiguity

The repository does not contain a broad semantic source that defines applicability for every generic policy / contract / payment-term item. The fix therefore uses explicit applicability only where the generator semantics clearly support it, and leaves items without applicability as not automatically relevant.

This keeps the ground truth defensible and avoids fabricating mappings to improve retrieval metrics.

## 17. Recommended next step

The next step is to run the benchmark only after this Step 5 validation is clean and the ground-truth repair is fully accepted. After that, use the revised labels to evaluate actual retrieval performance without changing the retrieval stack itself.
