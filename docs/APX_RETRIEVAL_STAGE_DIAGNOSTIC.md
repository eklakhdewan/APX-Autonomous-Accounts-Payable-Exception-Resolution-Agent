# APX Retrieval Stage Diagnostic

## Scope

This is a read-only forensic diagnostic for the frozen retrieval pipeline. No production code was changed, and the purpose here is to localize where the corrected ground-truth evidence disappears between query construction and final validation.

## Frozen pipeline under inspection

The pipeline used for this audit is the architecture already frozen in the repository:

- QueryBuilder builds exception-specific query strings from the case exception type, vendor, and invoice context.
- BM25 retrieves top candidates from the vendor evidence corpus.
- Dense retriever retrieves the top semantic matches.
- RRF fuses the BM25 and dense rankings.
- Cross-encoder reranker reorders the fused set.
- EvidenceValidator filters by temporal validity, vendor scope, and outcome / scope validity.

This step intentionally does not modify any of these stages.

## Benchmark evidence used for the diagnosis

The latest corrected-dev benchmark artifact is:

- [apx/evaluation/results/phase5_dev_seed42_20260818_090830.json](apx/evaluation/results/phase5_dev_seed42_20260818_090830.json)

The relevant retrieval summary from that artifact shows:

- total_queries: 10
- recall_at_5: 0.16428571428571428
- recall_at_10: 0.16428571428571428
- mrr: 0.3
- ndcg_at_10: 0.3815464876785729
- valid_evidence_rate: 0.025
- invalid_evidence_rejection_rate: 0.8637698412698412
- vendor_scope_correctness: 0.065

Those aggregate values are the strongest signal in the diagnostic: the system is not failing only at the validator; it is failing earlier in the retrieval stack by surfacing the wrong evidence candidates, then discarding most of them during validation.

## Per-case failure matrix

The per-query retrieval metrics document the failure concentration:

| Case | Exception | Recall@5 | Recall@10 | MRR | Outcome |
| --- | --- | ---: | ---: | ---: | --- |
| EVAL-001 | AMOUNT_MISMATCH | 1.0 | 1.0 | 1.0 | Recovered |
| EVAL-002 | GRN_MISMATCH | 0.333 | 0.333 | 1.0 | Partial |
| EVAL-003 | VENDOR_MISMATCH | 0.143 | 0.143 | 0.5 | Weak |
| EVAL-004 | TAX_ERROR | 0.167 | 0.167 | 0.5 | Weak |
| EVAL-005 | CREDIT_ISSUE | 0.0 | 0.0 | 0.0 | Failed |
| EVAL-006 | PO_MISMATCH | 0.0 | 0.0 | 0.0 | Failed |
| EVAL-007 | CURRENCY_MISMATCH | 0.0 | 0.0 | 0.0 | Failed |
| EVAL-008 | DUPLICATE_INVOICE | 0.0 | 0.0 | 0.0 | Failed |
| EVAL-009 | DISCOUNT_ERROR | 0.0 | 0.0 | 0.0 | Failed |
| EVAL-010 | LINE_ITEM_MISMATCH | 0.0 | 0.0 | 0.0 | Failed |

This pattern is not random. It shows a sharp failure mode:

- the system succeeds only on the easier cases where generic vendor-linked text is sufficiently aligned to the exception vocabulary;
- it fails on the exception-specific cases whose relevant evidence is narrow, explicit, and often not lexically similar to generalized vendor policy language;
- the failure is concentrated in the cases where the corrected ground truth depends on explicit exception applicability rather than mere vendor ownership.

## Stage-level interpretation

### 1. Query generation

The query builder creates strings such as:

- vendor + invoice + exception keywords + general AP language

This is consistent with the intended exception-specific retrieval task. The query content is not the primary defect in isolation; it is simply general enough that it does not strongly bias toward the precise explicit-application evidence.

### 2. Retrieval stage (BM25 + dense)

The retrieval stage is the first major bottleneck. The evidence corpus contains a large number of vendor-owned policy / contract / historic records, but only a small number of records that are truly applicable to the exact exception code and vendor.

Because the query still contains vendor and invoice context, the retriever naturally rises generic vendor evidence before silent exception-applicability evidence. That creates a mismatch between query intent and the corrected relevance semantics.

### 3. RRF fusion

The RRF stage preserves the same bias: vendor-wide and broadly similar evidence is fused across both retrieval methods, while the explicit applicability records remain under-ranked because their lexical surface is narrower and less generic.

### 4. Reranking

The reranker does not correct the underlying mismatch. It reorders the fused list but cannot recover relevant evidence if it is already crowded out by generic vendor material.

### 5. Validation

The validator then rejects a large share of the remaining candidates for reasons such as vendor mismatch, stale dates, or invalid outcomes. The benchmark confirms this with:

- invalid_evidence_rejection_rate: 0.8637698412698412
- valid_evidence_rate: 0.025

This means the pipeline is not only missing the relevant evidence early; it also validates too little of the already-retrieved candidate pool. The result is severe loss of the corrected relevant evidence before final scoring.

## Root cause classification

The diagnostic supports this root-cause classification:

- Primary issue: retrieval-stage ranking bias toward vendor-owned, general-purpose evidence instead of exception-applicable evidence.
- Secondary issue: the validator is correctly rejecting many low-quality candidates, but that rejection rate cannot compensate for the earlier omission of the corrected evidence.
- Not a benchmark-metric bug: the measured retrieval failure is consistent with the corrected ground truth and the actual corpus distribution.
- Not a data-generation bug in Step 6B: the repaired corpus and dataset were already regenerated and validated in Step 5.

The failure is therefore architectural and semantic at the retrieval frontier, not a measurement artifact.

## Defensible conclusion

The corrected ground truth is the source of truth, and the evidence shows that the retrieval pipeline is still optimized for broad vendor-relevant matches rather than for explicit exception applicability. That is why the system retrieves a large pool of vendor-owned and temporally valid but semantically wrong evidence, and then fails to recover the corrected relevant items in the top ranks.

This is not a random retrieval failure; it is a consistent ranking failure against the repaired relevance semantics.

## Outcome

The Stage 6B forensic diagnostic is complete. The evidence is read-only, the pipeline remains frozen, and the main loss occurs before the final valid-evidence set is produced.
