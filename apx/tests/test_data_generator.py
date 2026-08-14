from decimal import Decimal
from apx.data.generate_synthetic import SyntheticGenerator


class TestDataGenerator:
    def test_generate_vendors(self):
        gen = SyntheticGenerator(seed=42)
        vendors = gen.generate_vendors(10)
        assert len(vendors) == 10
        assert all(v.vendor_id.startswith("V-") for v in vendors)
        assert len({v.vendor_id for v in vendors}) == 10

    def test_generate_pos(self):
        gen = SyntheticGenerator(seed=42)
        gen.generate_vendors(5)
        pos = gen.generate_purchase_orders(10)
        assert len(pos) == 10
        assert all(p.po_id.startswith("PO-") for p in pos)
        assert all(p.vendor_id in [v.vendor_id for v in gen.vendors] for p in pos)

    def test_generate_grns(self):
        gen = SyntheticGenerator(seed=42)
        gen.generate_vendors(5)
        gen.generate_purchase_orders(10)
        grns = gen.generate_goods_receipts(5)
        # Now generates one GRN per open PO
        assert len(grns) >= 5
        assert all(g.grn_id.startswith("GRN-") for g in grns)
        assert all(g.po_id in [p.po_id for p in gen.purchase_orders] for g in grns)

    def test_generate_invoices(self):
        gen = SyntheticGenerator(seed=42)
        gen.generate_vendors(5)
        gen.generate_purchase_orders(10)
        gen.generate_goods_receipts(5)
        invoices = gen.generate_invoices(20)
        assert len(invoices) == 20
        assert all(i.invoice_id.startswith("INV-") for i in invoices)

    def test_generate_all(self):
        gen = SyntheticGenerator(seed=42)
        data = gen.generate_all(vendor_count=10, po_count=20, grn_count=10, invoice_count=50)
        assert len(data["vendors"]) == 10
        assert len(data["purchase_orders"]) == 20
        # GRN count is now based on open POs, not the requested count
        assert len(data["goods_receipts"]) >= 10
        assert len(data["invoices"]) == 50
        assert len(data["ground_truth"]) == 50

    def test_reproducibility(self):
        gen1 = SyntheticGenerator(seed=123)
        data1 = gen1.generate_all(vendor_count=5, po_count=10, grn_count=5, invoice_count=20)

        gen2 = SyntheticGenerator(seed=123)
        data2 = gen2.generate_all(vendor_count=5, po_count=10, grn_count=5, invoice_count=20)

        assert len(data1["invoices"]) == len(data2["invoices"])
        for i1, i2 in zip(data1["invoices"], data2["invoices"]):
            assert i1["invoice_id"] == i2["invoice_id"]
            assert i1["vendor_id"] == i2["vendor_id"]
            assert i1["total"] == i2["total"]

    def test_different_seeds_produce_different_data(self):
        gen1 = SyntheticGenerator(seed=111)
        data1 = gen1.generate_all(vendor_count=5, po_count=10, grn_count=5, invoice_count=30)

        gen2 = SyntheticGenerator(seed=222)
        data2 = gen2.generate_all(vendor_count=5, po_count=10, grn_count=5, invoice_count=30)

        total1 = sum(Decimal(str(i["total"])) for i in data1["invoices"])
        total2 = sum(Decimal(str(i["total"])) for i in data2["invoices"])
        assert total1 != total2, "Different seeds should produce different invoice totals"

    def test_exception_injection(self):
        gen = SyntheticGenerator(seed=999)
        gen.generate_vendors(5)
        gen.generate_purchase_orders(10)
        gen.generate_goods_receipts(5)
        invoices = gen.generate_invoices(50)
        gt = gen.ground_truth

        with_exceptions = [g for g in gt if g.expected_exceptions]
        assert len(with_exceptions) > 0

        for g in with_exceptions:
            assert len(g.expected_exceptions) > 0
            assert g.injected_exceptions is not None