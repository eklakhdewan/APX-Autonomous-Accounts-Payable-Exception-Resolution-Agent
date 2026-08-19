# APX Retrieval Forensic Audit

**Status:** COMPLETE — forensic/evaluation audit only; no APX runtime or retrieval code modified.
**Date:** 2026-08-18
**Reference date:** 2026-08-29

## 1. Executive Summary

The current Retrieval Recall@5 of 6.7% cannot be treated as evidence that BM25, dense retrieval, RRF, or the cross-encoder is the primary defect.

The strongest, directly proven defect is **ground-truth relevance construction** in `apx/evidence/populate_eval_labels.py`. The label generator marks most valid vendor-owned `vendor_policy`, `contract`, and `payment_term` evidence as relevant regardless of whether it is applicable to the case's exception. It also marks every valid `historical_resolution` for the vendor as relevant even when its `metadata.exception_code` does not match the case exception.

This creates a mismatch:

```text
Query intent: exception-specific evidence
Ground truth: broad vendor-wide evidence
```

Several labeled-relevant evidence items are demonstrably unrelated to the exception and contain no meaningful exception-specific signal. Therefore a retriever that correctly ranks exception-specific evidence can still receive a recall penalty.

The evaluator itself is not using `validated_evidence`; it scores `evidence_set.candidates`, which are the reranked top-20 candidates. Thus the temporal-validity filter is not the cause of the 6.7% retrieval score. This matches the temporal audit's conclusion.

The available forensic bundle did not contain the generated dense index or the benchmark JSON, so exact Dense/RRF/Reranker per-evidence ranks cannot be independently recomputed here. Existing benchmark output confirms that 8/10 cases had zero labeled-relevant evidence in the final top-20. Those stage-level ranks must therefore be treated as **not independently reproduced**, not fabricated.

## 2. Pipeline Trace

Current implementation:

```text
ExceptionReport
  -> QueryBuilder
  -> BM25 top-50
  -> Dense top-50
  -> RRF fusion
  -> CrossEncoder rerank top-20
  -> EvidenceSet.candidates
  -> RetrievalEvaluator

Separately:

Reranked candidates
  -> EvidenceValidator
  -> EvidenceSet.validated_evidence
```

There is no SQL/SQLite/SQLAlchemy candidate-retrieval layer in the supplied implementation. Candidate generation is in-memory BM25 + dense retrieval over the evidence corpus.

## 3. Query Audit

`QueryBuilder.build_query()` creates a query from:

1. up to three exception-specific keywords per exception;
2. `vendor {vendor_id}`;
3. `invoice {invoice_id}`;
4. generic AP terms: `accounts payable`, `invoice validation`, `exception resolution`.

This is deterministic and exception-aware, but it does **not** explicitly request every evidence category that the current labels call relevant.

For example, a `CURRENCY_MISMATCH` query contains currency/exchange/conversion terms, while the labeled relevant contract `EV-00176` contains generic contract/payment/discount/tolerance language and no currency-specific content.

Therefore the query/label contract is inconsistent.

## 4. Ground Truth Audit

### Label-generation rule

`determine_labels_for_case()` currently does the following for valid vendor evidence:

- matching `historical_resolution` exception code -> relevant;
- **non-matching `historical_resolution` -> also relevant**;
- **all `vendor_policy` -> relevant**;
- **all non-stale `contract` -> relevant**;
- **all non-stale `payment_term` -> relevant**.

The last three rules are vendor-wide rather than exception-specific.

### Directly proven examples

#### EVAL-006 — PO_MISMATCH / V-0006

Labeled relevant:

`EV-00037`

Actual evidence:

```text
historical_resolution
scope_target = V-0006:LINE_ITEM_MISMATCH
metadata.exception_code = LINE_ITEM_MISMATCH
content = Historical resolution for LINE_ITEM_MISMATCH ... Quantity matched.
```

There is no PO_MISMATCH relationship. This is a direct false-positive relevance label.

#### EVAL-007 — CURRENCY_MISMATCH / V-0007

Labeled relevant:

`EV-00176`

Actual evidence:

```text
contract
scope = contractual_terms
content = Net 30, early payment discount, volume discounts,
amount/quantity/tax tolerance, governing law
```

No currency, exchange-rate, or currency-mismatch applicability is present. This is a direct false-positive relevance label.

#### EVAL-010 — DUPLICATE_INVOICE / V-0010

Labeled relevant:

`EV-00027`

Actual evidence:

```text
historical_resolution
metadata.exception_code = CURRENCY_MISMATCH
```

The case exception is `DUPLICATE_INVOICE`. The evidence is for another exception.

The remaining labeled items are predominantly generic vendor policies/contracts/payment terms rather than exception-specific evidence.

## 5. SQL Audit

**N/A.** No SQL candidate retrieval implementation was found in the supplied code.

## 6. BM25 Audit

Implementation is conventional BM25 over `Evidence.content` using whitespace tokenization.

The query contains exception keywords, vendor ID, invoice ID, and generic AP terms. The corpus contains many documents whose content is generic vendor policy/contract language.

The key forensic finding is not that BM25 is demonstrably defective. It is that the relevance labels require retrieval of evidence that often lacks the query's exception-specific terms.

Exact BM25 ranks were not independently reproduced because the supplied forensic bundle did not include the benchmark runtime/index environment.

## 7. Dense Audit

Dense retrieval encodes only `Evidence.content` and the query. It does not explicitly encode structured `exception_code`, `scope`, or `scope_target` fields unless those values appear in the content.

This is a potential representation limitation, but **not proven as the primary failure** from the supplied artifacts.

Exact dense ranks/similarities were not independently reproduced because the dense index/model runtime was not included in the forensic bundle.

## 8. RRF Audit

RRF combines BM25 and dense rankings using the configured rank-based formula.

No code defect was established from static inspection.

However, because both upstream rankers are limited to top-50, evidence absent from both top-50 lists cannot enter RRF.

## 9. Reranker Audit

The cross-encoder reranks only the fused candidate list's first `top_k` items, with DEV `top_k = 20`.

Therefore the system has an explicit retrieval boundary:

```text
BM25 top-50 + Dense top-50
        -> RRF
        -> rerank first 20
        -> final candidates = 20
```

This can contribute to misses when relevant evidence is below the fused top-20, but no evidence in the supplied bundle proves that this is the dominant cause.

## 10. Filtering Audit

The retrieval evaluator operates on `EvidenceSet.candidates`, not `validated_evidence`.

Consequently freshness/vendor validation does not remove a candidate before Recall@5 is calculated.

The temporal audit already established that freshness was a separate downstream starvation issue. The temporal fix is therefore not the explanation for the current retrieval Recall@5 failure.

## 11. Validation Audit

`EvidenceValidator` is applied after reranking and populates `validated_evidence` separately.

It is therefore not responsible for the retrieval Recall@5 calculation.

For the regenerated corpus, the labeled relevant items examined in this audit are temporally valid at 2026-08-29 and have matching vendors. The problem is semantic relevance, not freshness.

## 12. Evaluator Audit

`retrieval_eval.py`:

- reads `evidence_set.candidates`;
- marks an item relevant iff its ID is in `relevant_ids`;
- calculates Recall@5 from the first five candidates;
- calculates Recall@10 from the first ten;
- calculates MRR from the first relevant candidate;
- calculates nDCG@10 using the same binary relevance map.

This metric implementation is internally consistent with the supplied labels.

The problem is therefore **not primarily the arithmetic**. It is the semantic quality of the relevance labels.

## 13. 10-Case Failure Table

| Case | Exception | Relevant labels | Direct label contradictions | Final top-20 relevant | Classification |
|---|---|---:|---:|---:|---|
| EVAL-001 | AMOUNT_MISMATCH | 3 | 1+ | 1/3 (`Recall@5=0.333`) | B — GT/evaluator semantics |
| EVAL-002 | GRN_MISMATCH | 6 | multiple | 2/6 (`Recall@5=0.333`) | B — GT/evaluator semantics |
| EVAL-003 | VENDOR_MISMATCH | 6 | broad vendor-wide labels | 0/6 | B primary; A secondary |
| EVAL-004 | TAX_ERROR | 6 | multiple | 0/6 | B primary |
| EVAL-005 | CREDIT_ISSUE | 4 | broad generic labels | 0/4 | B primary |
| EVAL-006 | PO_MISMATCH | 1 | EV-00037 is LINE_ITEM_MISMATCH | 0/1 | B — direct contradiction |
| EVAL-007 | CURRENCY_MISMATCH | 1 | EV-00176 has no currency applicability | 0/1 | B — direct contradiction |
| EVAL-008 | LINE_ITEM_MISMATCH | 2 | generic vendor policy/contract | 0/2 | B primary |
| EVAL-009 | DISCOUNT_ERROR | 6 | historical resolutions for other exceptions | 0/6 | B primary |
| EVAL-010 | DUPLICATE_INVOICE | 6 | EV-00027 is CURRENCY_MISMATCH; others generic | 0/6 | B primary |

The final-top-20 values come from the recorded post-temporal benchmark. Stage-specific ranks are not claimed where the supplied bundle did not contain the runtime/index artifacts needed to reproduce them.

## 14. Root Cause

### PRIMARY ROOT CAUSE

**B — Ground-truth / evaluator semantics.**

The relevance-label generator is too broad and marks vendor-wide evidence as exception-relevant. It also marks non-matching historical resolutions as relevant. This creates labels that are not aligned with query intent or actual exception applicability.

### SECONDARY ROOT CAUSES

**A — Query construction mismatch.** The query is exception-specific, while the ground truth is partly vendor-wide. The query does not contain signals for many documents the evaluator demands.

**J — Corpus metadata/design limitation.** Generic policy/contract evidence lacks explicit exception-applicability metadata, making deterministic relevance labeling ambiguous for some document types.

**Reranker/candidate-boundary risk.** The top-20 reranking boundary may hide evidence that enters RRF below rank 20, but this is not proven as the primary issue.

### NOT ROOT CAUSES ESTABLISHED

- Temporal freshness — fixed in Step 3.
- SQL retrieval — no SQL layer exists.
- Retrieval evaluator arithmetic — no primary arithmetic defect found.
- RRF implementation — no static defect established.
- Evidence validation — downstream of candidate evaluation.

## 15. Recommended Fix — ONE

### Replace vendor-wide relevance labeling with explicit exception-applicability ground truth.

Do not tune BM25/dense/RRF/reranker against the current labels.

Implement one deterministic relevance policy in the evaluation-data generation layer:

```text
relevant = evidence that is both valid AND applicable to the case exception
```

For historical resolutions, applicability must require matching `exception_code`.
For policies/contracts/payment terms, applicability must be explicitly represented by evidence metadata/scope rather than inferred solely from vendor ownership.

Where the current corpus cannot express applicability unambiguously, extend the generated evidence metadata minimally so the generator can declare which exception classes a policy/contract/term supports. Do not use retrieval output to construct labels.

Then regenerate labels and rerun the retrieval benchmark **without changing the retrieval algorithms**. This produces a valid retrieval baseline before any retrieval optimization.

## 16. Files Affected by the Recommended Fix

Expected minimum scope:

- `apx/evidence/populate_eval_labels.py`
- potentially the evidence-generation metadata path if applicability must be represented explicitly
- regenerated `apx/data/datasets/eval/eval_dataset.json`
- focused tests for relevance-label semantics

Do not modify BM25, dense, RRF, reranker, agent, validator, or decision code in this fix.

## 17. Risks

1. **Benchmark comparability:** regenerating labels changes the meaning of Recall@5; the current 6.7% result must remain archived as the pre-fix label baseline.
2. **Over-correction:** making labels too narrow could exclude genuinely useful policy/contract evidence. Applicability rules must be documented and tested.
3. **Corpus-schema scope:** adding applicability metadata is a data-model change; keep it minimal and deterministic.
4. **Retrieval may still be poor after label correction:** this audit does not prove that BM25/dense/RRF/reranking are high quality. After ground-truth correction, retrieval must be re-measured.
5. **Stage-level attribution remains incomplete:** exact per-evidence Dense/RRF/Reranker ranks require the benchmark runtime/index artifacts; those were not included in the forensic bundle and are therefore not fabricated here.

## Final Verdict

**Step 4: COMPLETE for the evidence available.**

The benchmark's current low Recall@5 is **not yet a valid basis for retrieval optimization**. The first corrective action must be to repair the relevance-ground-truth semantics, regenerate the evaluation labels, and establish a clean retrieval baseline.
