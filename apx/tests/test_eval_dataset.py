import json
import pytest
from pathlib import Path

from apx.config.settings import get_settings
from apx.evidence.schemas import Evidence


class TestEvalDataset:
    def test_eval_dataset_has_ground_truth_labels(self):
        settings = get_settings()
        eval_path = settings.get_eval_path() / "eval_dataset.json"
        
        with eval_path.open("r") as f:
            data = json.load(f)
        
        cases = data["cases"]
        assert len(cases) == 10, f"Expected 10 eval cases, got {len(cases)}"
        
        for case in cases:
            # Check required fields exist
            assert "case_id" in case
            assert "exception_type" in case
            assert "vendor_id" in case
            assert "query" in case
            assert "relevant_evidence_ids" in case
            assert "irrelevant_evidence_ids" in case
            assert "invalid_evidence_ids" in case
            
            # Check all three label fields are populated (non-empty lists)
            assert isinstance(case["relevant_evidence_ids"], list)
            assert isinstance(case["irrelevant_evidence_ids"], list)
            assert isinstance(case["invalid_evidence_ids"], list)
            
            # At least one relevant item should exist for meaningful metrics
            assert len(case["relevant_evidence_ids"]) > 0, f"Case {case['case_id']} has no relevant evidence"
            
            # Check no duplicates within each category
            for cat_name in ["relevant_evidence_ids", "irrelevant_evidence_ids", "invalid_evidence_ids"]:
                ids = case[cat_name]
                assert len(ids) == len(set(ids)), f"Duplicate IDs in {cat_name} for {case['case_id']}"
            
            # Check no overlap between categories
            rel = set(case["relevant_evidence_ids"])
            irr = set(case["irrelevant_evidence_ids"])
            inv = set(case["invalid_evidence_ids"])
            assert rel.isdisjoint(irr), f"Overlap between relevant and irrelevant in {case['case_id']}"
            assert rel.isdisjoint(inv), f"Overlap between relevant and invalid in {case['case_id']}"
            assert irr.isdisjoint(inv), f"Overlap between irrelevant and invalid in {case['case_id']}"
    
    def test_eval_dataset_ids_exist_in_corpus(self):
        settings = get_settings()
        corpus_path = settings.get_corpus_path() / "evidence_corpus.json"
        eval_path = settings.get_eval_path() / "eval_dataset.json"
        
        with corpus_path.open("r") as f:
            corpus_data = json.load(f)
        corpus_ids = {e["evidence_id"] for e in corpus_data["evidence"]}
        
        with eval_path.open("r") as f:
            eval_data = json.load(f)
        
        for case in eval_data["cases"]:
            all_ids = (case["relevant_evidence_ids"] + 
                      case["irrelevant_evidence_ids"] + 
                      case["invalid_evidence_ids"])
            for eid in all_ids:
                assert eid in corpus_ids, f"Evidence ID {eid} in {case['case_id']} not found in corpus"
    
    def test_eval_dataset_deterministic(self):
        """Running the populate script twice with same seed produces identical labels."""
        import subprocess
        import os
        import tempfile
        
        env = os.environ.copy()
        env["PATH"] = "/home/eklakhdewan/.local/bin:" + env["PATH"]
        # Set PYTHONHASHSEED for deterministic hash() across processes
        env["PYTHONHASHSEED"] = "42"
        
        with tempfile.TemporaryDirectory() as tmpdir1, tempfile.TemporaryDirectory() as tmpdir2:
            # Run populate script twice
            subprocess.run(
                ["python3", "-m", "apx.evidence.populate_eval_labels", "--output-dir", tmpdir1],
                cwd="/mnt/d/Opencode", capture_output=True, env=env, check=True
            )
            subprocess.run(
                ["python3", "-m", "apx.evidence.populate_eval_labels", "--output-dir", tmpdir2],
                cwd="/mnt/d/Opencode", capture_output=True, env=env, check=True
            )
            
            # Compare outputs
            with open(f"{tmpdir1}/eval_dataset.json") as f1, open(f"{tmpdir2}/eval_dataset.json") as f2:
                data1 = json.load(f1)
                data2 = json.load(f2)
            
            # Cases should be identical
            for c1, c2 in zip(data1["cases"], data2["cases"]):
                assert c1["relevant_evidence_ids"] == c2["relevant_evidence_ids"], f"Relevant IDs differ for {c1['case_id']}"
                assert c1["irrelevant_evidence_ids"] == c2["irrelevant_evidence_ids"], f"Irrelevant IDs differ for {c1['case_id']}"
                assert c1["invalid_evidence_ids"] == c2["invalid_evidence_ids"], f"Invalid IDs differ for {c1['case_id']}"


def test_evaluation_metrics_are_numeric():
    """Verify that evaluation produces numeric metrics, not N/A."""
    from apx.evidence.evaluate import compute_recall_at_k, compute_mrr, compute_ndcg_at_k
    
    relevant = ["EV-001", "EV-002", "EV-003"]
    retrieved = ["EV-002", "EV-004", "EV-001", "EV-005", "EV-003"]
    
    r5 = compute_recall_at_k(relevant, retrieved, 5)
    r10 = compute_recall_at_k(relevant, retrieved, 10)
    mrr = compute_mrr(relevant, retrieved)
    ndcg = compute_ndcg_at_k(relevant, retrieved, 10)
    
    assert isinstance(r5, float) and 0 <= r5 <= 1
    assert isinstance(r10, float) and 0 <= r10 <= 1
    assert isinstance(mrr, float) and 0 <= mrr <= 1
    assert isinstance(ndcg, float) and 0 <= ndcg <= 1
    
    # With perfect retrieval
    perfect_retrieved = ["EV-001", "EV-002", "EV-003", "EV-004"]
    assert compute_recall_at_k(relevant, perfect_retrieved, 10) == 1.0
    assert compute_mrr(relevant, perfect_retrieved) == 1.0
    assert compute_ndcg_at_k(relevant, perfect_retrieved, 10) == 1.0
    
    # With empty relevant
    assert compute_recall_at_k([], retrieved, 5) == 1.0
    assert compute_mrr([], retrieved) == 1.0
    assert compute_ndcg_at_k([], retrieved, 10) == 1.0