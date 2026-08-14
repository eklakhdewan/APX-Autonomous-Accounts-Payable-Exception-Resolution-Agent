import json
from pathlib import Path
from collections import Counter
import pytest

BOOTSTRAP_DIR = Path("apx/data/datasets/bootstrap")
GT_DIR = Path("apx/data/datasets/ground_truth")


def load_bootstrap():
    with open(BOOTSTRAP_DIR / "vendors.json") as f:
        vendors = json.load(f)
    with open(BOOTSTRAP_DIR / "purchase_orders.json") as f:
        pos = json.load(f)
    with open(BOOTSTRAP_DIR / "goods_receipts.json") as f:
        grns = json.load(f)
    with open(BOOTSTRAP_DIR / "invoices.json") as f:
        invoices = json.load(f)
    return vendors, pos, grns, invoices


def load_ground_truth():
    with open(GT_DIR / "ground_truth.json") as f:
        return json.load(f)


class TestDataIntegrity:
    def test_vendors_exist(self):
        vendors, _, _, _ = load_bootstrap()
        assert len(vendors) == 20
        vendor_ids = {v["vendor_id"] for v in vendors}
        assert len(vendor_ids) == 20

    def test_pos_reference_valid_vendors(self):
        vendors, pos, _, _ = load_bootstrap()
        vendor_ids = {v["vendor_id"] for v in vendors}
        for po in pos:
            assert po["vendor_id"] in vendor_ids, f"PO {po['po_id']} references invalid vendor {po['vendor_id']}"

    def test_grns_reference_valid_pos(self):
        _, pos, grns, _ = load_bootstrap()
        po_ids = {po["po_id"] for po in pos}
        for grn in grns:
            assert grn["po_id"] in po_ids, f"GRN {grn['grn_id']} references invalid PO {grn['po_id']}"

    def test_grns_reference_valid_vendors(self):
        vendors, _, grns, _ = load_bootstrap()
        vendor_ids = {v["vendor_id"] for v in vendors}
        for grn in grns:
            assert grn["vendor_id"] in vendor_ids, f"GRN {grn['grn_id']} references invalid vendor {grn['vendor_id']}"

    def test_invoices_reference_valid_vendors(self):
        vendors, _, _, invoices = load_bootstrap()
        vendor_ids = {v["vendor_id"] for v in vendors}
        for inv in invoices:
            assert inv["vendor_id"] in vendor_ids, f"Invoice {inv['invoice_id']} references invalid vendor {inv['vendor_id']}"

    def test_invoices_reference_valid_pos(self):
        _, pos, _, invoices = load_bootstrap()
        gt = load_ground_truth()
        po_numbers = {po["po_number"] for po in pos if po.get("po_number")}
        gt_by_inv = {g["invoice_id"]: g for g in gt}

        for inv in invoices:
            if inv.get("po_number"):
                gt_entry = gt_by_inv.get(inv["invoice_id"])
                has_po_mismatch = gt_entry and "PO_MISMATCH" in gt_entry["expected_exceptions"]
                if not has_po_mismatch:
                    assert inv["po_number"] in po_numbers, f"Invoice {inv['invoice_id']} references invalid PO {inv['po_number']}"

    def test_grn_line_items_reference_valid_po_lines(self):
        _, pos, grns, _ = load_bootstrap()
        po_line_ids = set()
        for po in pos:
            for line in po["line_items"]:
                po_line_ids.add(line["line_id"])

        for grn in grns:
            for line in grn["line_items"]:
                assert line["po_line_id"] in po_line_ids, f"GRN {grn['grn_id']} line references invalid PO line {line['po_line_id']}"

    def test_invoice_line_items_reference_valid_po_lines(self):
        _, pos, _, invoices = load_bootstrap()
        po_line_ids = set()
        for po in pos:
            for line in po["line_items"]:
                po_line_ids.add(line["line_id"])

        for inv in invoices:
            for line in inv["line_items"]:
                if line.get("po_line_id"):
                    assert line["po_line_id"] in po_line_ids, f"Invoice {inv['invoice_id']} line references invalid PO line {line['po_line_id']}"

    def test_monetary_totals_internally_coherent(self):
        _, pos, _, invoices = load_bootstrap()
        gt = load_ground_truth()
        gt_by_inv = {g["invoice_id"]: g for g in gt}

        for po in pos:
            calc_subtotal = sum(
                (Decimal(str(l["quantity"])) * Decimal(str(l["unit_price"]))) - Decimal(str(l.get("discount", 0)))
                for l in po["line_items"]
            )
            calc_tax = sum(
                (((Decimal(str(l["quantity"])) * Decimal(str(l["unit_price"]))) - Decimal(str(l.get("discount", 0)))) * Decimal(str(l.get("tax_rate", 0))))
                for l in po["line_items"]
            )
            calc_total = calc_subtotal + calc_tax
            tolerance = Decimal("0.01")
            assert abs(Decimal(str(po["subtotal"])) - calc_subtotal) <= tolerance
            assert abs(Decimal(str(po["tax"])) - calc_tax) <= tolerance
            assert abs(Decimal(str(po["total"])) - calc_total) <= tolerance

        for inv in invoices:
            gt_entry = gt_by_inv.get(inv["invoice_id"])
            if gt_entry and gt_entry["expected_exceptions"]:
                continue

            calc_subtotal = sum(
                (Decimal(str(l["quantity"])) * Decimal(str(l["unit_price"]))) - Decimal(str(l.get("discount", 0)))
                for l in inv["line_items"]
            )
            calc_tax = sum(
                (((Decimal(str(l["quantity"])) * Decimal(str(l["unit_price"]))) - Decimal(str(l.get("discount", 0)))) * Decimal(str(l.get("tax_rate", 0))))
                for l in inv["line_items"]
            )
            calc_total = calc_subtotal + calc_tax - Decimal(str(inv.get("discount", 0)))
            tolerance = Decimal("0.01")
            assert abs(Decimal(str(inv["subtotal"])) - calc_subtotal) <= tolerance
            assert abs(Decimal(str(inv["tax"])) - calc_tax) <= tolerance
            assert abs(Decimal(str(inv["total"])) - calc_total) <= tolerance

    def test_ids_unique(self):
        vendors, pos, grns, invoices = load_bootstrap()

        vendor_ids = [v["vendor_id"] for v in vendors]
        assert len(vendor_ids) == len(set(vendor_ids))

        po_ids = [p["po_id"] for p in pos]
        assert len(po_ids) == len(set(po_ids))

        grn_ids = [g["grn_id"] for g in grns]
        assert len(grn_ids) == len(set(grn_ids))

        inv_ids = [i["invoice_id"] for i in invoices]
        assert len(inv_ids) == len(set(inv_ids))

    def test_duplicate_cases_are_intentional(self):
        _, _, _, invoices = load_bootstrap()
        gt = load_ground_truth()

        dup_keys = {}
        for inv in invoices:
            key = (inv["vendor_id"], inv["invoice_number"])
            if key in dup_keys:
                dup_keys[key].append(inv["invoice_id"])
            else:
                dup_keys[key] = [inv["invoice_id"]]

        for key, ids in dup_keys.items():
            if len(ids) > 1:
                gt_entries = [g for g in gt if g["invoice_id"] in ids]
                duplicate_entries = [g for g in gt_entries if "DUPLICATE_INVOICE" in g["expected_exceptions"]]
                original_entries = [g for g in gt_entries if "DUPLICATE_INVOICE" not in g["expected_exceptions"]]
                assert len(original_entries) == 1, f"Should have exactly one original for {key}, got {len(original_entries)}"
                assert len(duplicate_entries) == len(ids) - 1, f"All duplicates should be marked for {key}"

    def test_no_orphan_records(self):
        vendors, pos, grns, invoices = load_bootstrap()

        vendor_ids = {v["vendor_id"] for v in vendors}
        po_vendor_ids = {po["vendor_id"] for po in pos}
        assert po_vendor_ids.issubset(vendor_ids)

        grn_vendor_ids = {grn["vendor_id"] for grn in grns}
        assert grn_vendor_ids.issubset(vendor_ids)

        inv_vendor_ids = {inv["vendor_id"] for inv in invoices}
        assert inv_vendor_ids.issubset(vendor_ids)

    def test_ground_truth_matches_invoice_count(self):
        _, _, _, invoices = load_bootstrap()
        gt = load_ground_truth()
        assert len(gt) == len(invoices)

        inv_ids = {inv["invoice_id"] for inv in invoices}
        gt_ids = {g["invoice_id"] for g in gt}
        assert inv_ids == gt_ids

    def test_injected_exceptions_match_ground_truth(self):
        _, _, _, invoices = load_bootstrap()
        gt = load_ground_truth()

        for g in gt:
            if g["expected_exceptions"]:
                assert g["injected_exceptions"] is not None
                assert isinstance(g["injected_exceptions"], dict)

    def test_reproducibility_same_seed(self):
        import subprocess
        import tempfile
        import os

        with tempfile.TemporaryDirectory() as tmpdir:
            env = os.environ.copy()
            env["PATH"] = "/home/eklakhdewan/.local/bin:" + env["PATH"]

            result1 = subprocess.run(
                ["python3", "-m", "apx.data.generate_synthetic", "--seed", "42"],
                cwd="/mnt/d/Opencode",
                capture_output=True,
                text=True,
                env=env
            )
            assert result1.returncode == 0

            with open(BOOTSTRAP_DIR / "invoices.json") as f:
                invs1 = json.load(f)

            result2 = subprocess.run(
                ["python3", "-m", "apx.data.generate_synthetic", "--seed", "42"],
                cwd="/mnt/d/Opencode",
                capture_output=True,
                text=True,
                env=env
            )
            assert result2.returncode == 0

            with open(BOOTSTRAP_DIR / "invoices.json") as f:
                invs2 = json.load(f)

            assert len(invs1) == len(invs2)
            for i1, i2 in zip(invs1, invs2):
                assert i1["invoice_id"] == i2["invoice_id"]
                assert i1["vendor_id"] == i2["vendor_id"]
                assert i1["total"] == i2["total"]


from decimal import Decimal