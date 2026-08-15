\# APX V1.1 — Phase 2 Build Brief

\## Hybrid Evidence Retrieval Foundation



\*\*Status:\*\* Implementation contract  

\*\*Phase:\*\* 2  

\*\*Architecture:\*\* FROZEN  

\*\*Previous checkpoint:\*\* `phase-1-frozen`



---



\# 1. Mission



Implement APX V1.1 Phase 2: the deterministic/evidence retrieval layer that sits immediately after the Phase 1 deterministic validator.



Phase 2 transforms an `ExceptionReport` into a ranked, validated evidence set that later phases can consume.



The Phase 1 validator remains authoritative for deterministic exception detection.



Phase 2 must NOT replace, weaken, or modify the R1–R10 validator semantics.



---



\# 2. Frozen Architecture Boundary



Current architecture:



Invoice / PO / GRN

&nbsp;       |

&nbsp;       v

Deterministic Validator R1-R10

&nbsp;       |

&nbsp;       v

ExceptionReport

&nbsp;       |

&nbsp;       v

========== PHASE 2 ==========

Evidence / Context Engine

&nbsp;       |

&nbsp;       +--> BM25 lexical retrieval

&nbsp;       |

&nbsp;       +--> Dense retrieval

&nbsp;       |

&nbsp;       +--> RRF fusion

&nbsp;       |

&nbsp;       +--> Cross-encoder reranking

&nbsp;       |

&nbsp;       +--> Evidence validity filtering

&nbsp;       |

&nbsp;       v

Validated EvidenceSet

&nbsp;       |

&nbsp;       v

========== FUTURE ==========

Bounded Agent / Decision / Action layers



Do NOT redesign this architecture.



---



\# 3. Phase 2 Objective



Build a reproducible HybridContextEngine capable of:



1\. accepting an APX ExceptionReport;

2\. constructing a deterministic retrieval query;

3\. retrieving candidate evidence using BM25;

4\. retrieving candidate evidence using dense embeddings;

5\. fusing rankings using Reciprocal Rank Fusion (RRF);

6\. reranking candidates using a cross-encoder;

7\. validating evidence scope/version/outcome/authority;

8\. returning a ranked EvidenceSet;

9\. producing deterministic evaluation results.



---



\# 4. Explicit NON-GOALS



Do NOT implement:



\- LLM calls

\- OpenRouter

\- GPT/Claude/Gemini reasoning

\- ReAct

\- LangGraph

\- bounded state-machine execution

\- risk-policy decision engine

\- compound risk scoring

\- action execution

\- ERP integration

\- email integration

\- frontend

\- production deployment

\- autonomous resolution



These belong to later phases.



If implementation appears to require one of these, STOP and report the dependency instead of implementing it.



---



\# 5. Phase 1 Integration Contract



Phase 2 must consume existing Phase 1 outputs.



Do not duplicate the deterministic validator.



Do not change R1-R10 behavior.



The primary input should be the existing exception representation produced by Phase 1.



Before implementation:



\- inspect existing schemas;

\- inspect validator output;

\- inspect existing tests;

\- identify the exact import/API boundary;

\- reuse existing models where appropriate.



If a required Phase 1 interface is missing, add only the smallest backward-compatible interface necessary and document it.



---



\# 6. Evidence Model



Implement a canonical evidence representation containing, at minimum:



\- evidence\_id

\- evidence\_type

\- scope

\- scope\_target

\- vendor\_id

\- effective\_from

\- effective\_until

\- policy\_version

\- outcome

\- source\_authority

\- usage\_count

\- content

\- metadata



Evidence types should support at least:



\- historical\_resolution

\- vendor\_policy

\- contract

\- payment\_term



Do not create fake production semantics beyond what is required.



---



\# 7. Evidence Corpus



Create a deterministic synthetic evidence corpus suitable for development and evaluation.



Evidence must be linked to AP entities through explicit metadata.



Examples:



Historical resolution:



\- vendor

\- exception type

\- previous outcome

\- resolution action

\- effective dates

\- evidence content



Vendor policy:



\- vendor

\- policy scope

\- payment/exception rules

\- effective dates

\- policy version



Contract:



\- vendor

\- contract identifier

\- contractual terms

\- effective dates

\- authority



The corpus must contain both:



\- relevant evidence

\- deliberately irrelevant/stale/out-of-scope evidence



This is required to test evidence validation.



Use a fixed seed.



---



\# 8. Retrieval Profiles



Implement configurable retrieval profiles.



\## DEV



Dense model:



`BAAI/bge-small-en-v1.5`



Reranker:



`BAAI/bge-reranker-base`



Execution target:



CPU



\## EVAL



Dense model:



`BAAI/bge-large-en-v1.5`



Reranker:



`BAAI/bge-reranker-large`



\## PROD



Models must be configurable.



Do NOT hard-code the production model.



Configuration must allow model replacement without modifying retrieval logic.



If the EVAL models are impractical in the current environment, do not silently substitute them. Use the DEV profile and document the limitation.



---



\# 9. BM25 Retrieval



Implement lexical retrieval over the evidence corpus.



Requirements:



\- deterministic;

\- reproducible;

\- configurable top-K;

\- metadata preserved;

\- evidence IDs preserved;

\- no LLM dependency.



Unit tests must verify that known lexical queries retrieve expected evidence.



---



\# 10. Dense Retrieval



Implement dense retrieval using the configured embedding model.



Requirements:



\- deterministic for the same corpus/configuration;

\- persistent/reusable index;

\- evidence metadata mapping;

\- configurable top-K;

\- no LLM dependency.



The index must be rebuildable from the evidence corpus.



Do not introduce a database requirement unless the existing specification/repository requires it.



Prefer a simple local implementation appropriate for Phase 2 development.



---



\# 11. RRF Fusion



Implement Reciprocal Rank Fusion.



The fusion layer must:



\- accept BM25 rankings;

\- accept dense rankings;

\- combine them using configurable RRF parameters;

\- preserve evidence IDs;

\- produce a deterministic fused ranking.



Unit-test RRF independently with small known rankings.



---



\# 12. Cross-Encoder Reranking



Rerank the fused candidate set using the configured cross-encoder.



The reranker must:



\- operate only on retrieved candidates;

\- preserve evidence metadata;

\- return scores;

\- return deterministic ordering;

\- support configurable candidate count.



Do not allow the reranker to invent evidence.



---



\# 13. Evidence Validity



Retrieved evidence must pass validation before appearing in the final trusted EvidenceSet.



Implement validation for:



\### Scope



Evidence must apply to the relevant entity/context.



\### Vendor match



Vendor-specific evidence must match the invoice vendor.



\### Effective dates



Evidence outside its validity window must not be treated as current evidence.



\### Policy version



Where applicable, the correct policy version must be selected.



\### Outcome



Historical resolutions with unsuccessful outcomes must not be treated as successful precedents.



\### Source authority



Evidence source authority must be represented and evaluated.



\### Usage



Usage count must be available for later evidence-decay logic.



Do not let invalid evidence silently become trusted evidence.



---



\# 14. EvidenceSet



Create a final EvidenceSet representation containing ranked evidence.



Each result should expose enough information for later phases:



\- evidence\_id

\- evidence\_type

\- relevance\_score

\- reranker\_score

\- retrieval\_sources

\- rank

\- validity status

\- validity reasons

\- scope metadata

\- source authority

\- content/reference



Separate:



1\. retrieved candidate evidence

2\. validated/trusted evidence



Do not conflate these.



---



\# 15. Query Construction



Implement deterministic query construction from an ExceptionReport.



The query should incorporate relevant structured information such as:



\- exception type;

\- vendor;

\- relevant AP entity;

\- detected mismatch/context;

\- relevant terms.



Do NOT use an LLM for query rewriting.



The same ExceptionReport + same configuration must produce the same query.



---



\# 16. Testing Requirements



Add tests for:



\### Evidence schema



\- required fields

\- serialization

\- validation



\### Corpus



\- deterministic generation

\- referential integrity

\- vendor linkage

\- date validity



\### BM25



\- known relevant retrieval

\- top-K

\- deterministic ordering



\### Dense retrieval



\- index creation

\- retrieval

\- metadata mapping

\- deterministic rebuild



\### RRF



\- ranking fusion

\- tie behavior

\- deterministic output



\### Reranker



\- candidate preservation

\- score propagation

\- ordering



\### Evidence validation



\- vendor mismatch rejected

\- stale evidence rejected

\- invalid outcome rejected

\- incorrect scope rejected

\- valid evidence accepted



\### End-to-end



ExceptionReport

→ query

→ BM25

→ dense

→ RRF

→ reranker

→ evidence validation

→ EvidenceSet



---



\# 17. Evaluation Dataset



Create a dedicated Phase 2 retrieval evaluation set.



Do NOT use only random examples.



Include known query/evidence relationships.



Each evaluation case should contain:



\- case\_id

\- exception\_type

\- vendor\_id

\- query/context

\- relevant\_evidence\_ids

\- irrelevant\_evidence\_ids

\- invalid\_evidence\_ids



Keep evaluation data separate from development data.



Avoid leakage between development and evaluation evidence.



---



\# 18. Retrieval Metrics



Evaluate at minimum:



\- Recall@5

\- Recall@10

\- MRR

\- nDCG@10



Also report:



\- valid-evidence rate

\- invalid-evidence rejection rate

\- vendor-scope correctness

\- retrieval latency



Do not use an LLM judge.



---



\# 19. Acceptance Criteria



Phase 2 is complete only when:



\- \[ ] Phase 1 tests remain 100% passing.

\- \[ ] Phase 1 validator behavior is unchanged.

\- \[ ] Evidence schema exists.

\- \[ ] Deterministic evidence corpus exists.

\- \[ ] BM25 works.

\- \[ ] Dense retrieval works.

\- \[ ] RRF works.

\- \[ ] Cross-encoder reranking works.

\- \[ ] Evidence validity filtering works.

\- \[ ] EvidenceSet exists.

\- \[ ] End-to-end retrieval pipeline works.

\- \[ ] Phase 2 evaluation dataset exists.

\- \[ ] Recall@5, Recall@10, MRR and nDCG@10 are reported.

\- \[ ] Development profile works on the available CPU environment.

\- \[ ] Retrieval is reproducible.

\- \[ ] No LLM dependency exists.

\- \[ ] No agent/state-machine/action functionality has been introduced.

\- \[ ] No Phase 1 architecture changes were made.



---



\# 20. Backward Compatibility



Phase 1 is frozen.



Any modification to:



\- R1-R10 rules

\- Phase 1 schemas

\- ground-truth semantics

\- deterministic generator behavior

\- risk policy behavior



requires explicit reporting and approval.



Prefer additive changes.



---



\# 21. Repository Discipline



Before implementation:



```bash

git status

git log --oneline --decorate -5

git tag

