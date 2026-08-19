import json
from apx.data.schemas import ExceptionReport, ExceptionCode
from apx.evidence.engine import HybridContextEngine
from apx.evidence.query import create_query_from_exception_report
from apx.evidence.validity import EvidenceValidator
from apx.evidence.rrf import rrf_fuse
from apx.exceptions.taxonomy import create_exception
from apx.evidence.dates import APX_REFERENCE_DATE

engine = HybridContextEngine(profile_name='DEV', reference_date=APX_REFERENCE_DATE)
validator = EvidenceValidator(reference_date=APX_REFERENCE_DATE)

with open('d:/Opencode/apx/data/datasets/eval/eval_dataset.json', encoding='utf-8') as f:
    cases = json.load(f)['cases']
with open('d:/Opencode/apx/data/datasets/evidence/evidence_corpus.json', encoding='utf-8') as f:
    corpus = json.load(f)['evidence']
by_id = {e['evidence_id']: e for e in corpus}
stats = {'GT': 0, 'BM25': 0, 'Dense': 0, 'RRF': 0, 'Rerank': 0, 'Validated': 0}
rows = []
for case in cases:
    report = ExceptionReport(invoice_id=case['case_id'], vendor_id=case['vendor_id'], validation_status='EXCEPTIONS')
    for exc_name in case.get('exception_type', '').split(','):
        exc_name = exc_name.strip()
        if exc_name:
            try:
                report.exceptions.append(create_exception(ExceptionCode(exc_name)))
            except Exception:
                pass
    query = create_query_from_exception_report(report)
    bm25_candidates = engine.bm25_retriever.retrieve(query, top_k=engine.bm25_top_k)
    dense_candidates = engine.dense_retriever.retrieve(query, top_k=engine.dense_top_k)
    fused = rrf_fuse(bm25_candidates, dense_candidates, k=engine.rrf_k, rrf_constant=engine.rrf_constant)
    reranked = engine.reranker.rerank(query, fused, top_k=engine.reranker_top_k)
    validated_ids = []
    for cand in reranked:
        valid = validator.validate(cand.evidence, report.exception_codes, invoice_vendor_id=report.vendor_id)
        if valid.is_valid:
            validated_ids.append(cand.evidence.evidence_id)
    bm25_map = {c.evidence.evidence_id: c.bm25_rank for c in bm25_candidates}
    dense_map = {c.evidence.evidence_id: c.dense_rank for c in dense_candidates}
    rrf_map = {c.evidence.evidence_id: c.rrf_rank for c in fused}
    rerank_map = {c.evidence.evidence_id: c.final_rank for c in reranked}
    row = {
        'case_id': case['case_id'],
        'exception': case['exception_type'],
        'vendor_id': case['vendor_id'],
        'query': query,
        'gt': case['relevant_evidence_ids'],
        'bm25_top10': [(c.evidence.evidence_id, c.bm25_rank) for c in bm25_candidates[:10]],
        'dense_top10': [(c.evidence.evidence_id, c.dense_rank) for c in dense_candidates[:10]],
        'rrf_top10': [(c.evidence.evidence_id, c.rrf_rank) for c in fused[:10]],
        'rerank_top10': [(c.evidence.evidence_id, c.final_rank) for c in reranked[:10]],
        'validated_ids': validated_ids[:10],
        'details': []
    }
    for gt in case['relevant_evidence_ids']:
        e = by_id[gt]
        row['details'].append({
            'gt': gt,
            'type': e['evidence_type'],
            'vendor_id': e['vendor_id'],
            'scope': e.get('scope'),
            'scope_target': e.get('scope_target'),
            'applicable_exception_types': e.get('applicable_exception_types', []),
            'metadata': e.get('metadata', {}),
            'bm25_rank': bm25_map.get(gt, 'ABSENT'),
            'dense_rank': dense_map.get(gt, 'ABSENT'),
            'rrf_rank': rrf_map.get(gt, 'ABSENT'),
            'rerank_rank': rerank_map.get(gt, 'ABSENT'),
            'validated': gt in validated_ids,
        })
        stats['GT'] += 1
        if gt in bm25_map: stats['BM25'] += 1
        if gt in dense_map: stats['Dense'] += 1
        if gt in rrf_map: stats['RRF'] += 1
        if gt in rerank_map: stats['Rerank'] += 1
        if gt in validated_ids: stats['Validated'] += 1
    rows.append(row)

print(json.dumps({'stats': stats, 'rows': rows}, indent=2))
