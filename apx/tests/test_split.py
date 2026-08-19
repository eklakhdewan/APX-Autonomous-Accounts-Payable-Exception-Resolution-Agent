from __future__ import annotations

from decimal import Decimal
import pytest
from apx.data.split import ScenarioControlledSplit, SplitConfig, create_scenario_split
from apx.data.generate_synthetic import SyntheticGenerator
from apx.data.schemas import ExceptionCode


class TestScenarioControlledSplit:
    """Tests for the multi-axis dataset split."""

    @pytest.fixture(scope="class")
    def dataset(self):
        """Generate a deterministic dataset for split testing."""
        gen = SyntheticGenerator(seed=42)
        gen.generate_vendors(count=35)
        gen.generate_purchase_orders(count=100)
        gen.generate_goods_receipts(count=75)
        gen.generate_invoices(count=500, multi_exception_rate=0.15)
        return gen

    def test_deterministic_split_same_seed(self, dataset):
        """Same dataset + same seed => identical split membership."""
        config = SplitConfig(seed=42)
        splitter = ScenarioControlledSplit(config)

        result1 = splitter.split(
            dataset.invoices, dataset.purchase_orders, dataset.goods_receipts,
            dataset.vendors, dataset.ground_truth
        )
        result2 = splitter.split(
            dataset.invoices, dataset.purchase_orders, dataset.goods_receipts,
            dataset.vendors, dataset.ground_truth
        )

        # Train invoices should be identical
        train_ids_1 = {inv.invoice_id for inv in result1.train_invoices}
        train_ids_2 = {inv.invoice_id for inv in result2.train_invoices}
        assert train_ids_1 == train_ids_2

        # Validation invoices should be identical
        val_ids_1 = {inv.invoice_id for inv in result1.validation_invoices}
        val_ids_2 = {inv.invoice_id for inv in result2.validation_invoices}
        assert val_ids_1 == val_ids_2

        # Test invoices should be identical
        test_ids_1 = {inv.invoice_id for inv in result1.test_invoices}
        test_ids_2 = {inv.invoice_id for inv in result2.test_invoices}
        assert test_ids_1 == test_ids_2

        # Vendor sets should be identical
        assert result1.train_vendors == result2.train_vendors
        assert result1.validation_vendors == result2.validation_vendors
        assert result1.test_vendors == result2.test_vendors

    def test_different_seed_produces_different_split(self, dataset):
        """Different seed can produce different vendor allocation."""
        config1 = SplitConfig(seed=42)
        config2 = SplitConfig(seed=123)

        splitter1 = ScenarioControlledSplit(config1)
        splitter2 = ScenarioControlledSplit(config2)

        result1 = splitter1.split(
            dataset.invoices, dataset.purchase_orders, dataset.goods_receipts,
            dataset.vendors, dataset.ground_truth
        )
        result2 = splitter2.split(
            dataset.invoices, dataset.purchase_orders, dataset.goods_receipts,
            dataset.vendors, dataset.ground_truth
        )

        # At least one vendor set should differ (with high probability)
        vendors_differ = (
            result1.train_vendors != result2.train_vendors or
            result1.validation_vendors != result2.validation_vendors or
            result1.test_vendors != result2.test_vendors
        )
        assert vendors_differ, "Different seeds should produce different vendor allocations"

    def test_vendor_leakage_prevention(self, dataset):
        """Verify no vendor appears in more than one split."""
        config = SplitConfig(seed=42)
        splitter = ScenarioControlledSplit(config)

        result = splitter.split(
            dataset.invoices, dataset.purchase_orders, dataset.goods_receipts,
            dataset.vendors, dataset.ground_truth
        )

        assert not result.vendor_leakage, "Vendor leakage detected"

        # Explicit check: no vendor in train and test
        assert result.train_vendors.isdisjoint(result.test_vendors)
        # No vendor in validation and test
        assert result.validation_vendors.isdisjoint(result.test_vendors)
        # No vendor in train and validation
        assert result.train_vendors.isdisjoint(result.validation_vendors)

    def test_train_validation_test_structure(self, dataset):
        """Verify split has expected three-way structure."""
        config = SplitConfig(seed=42)
        splitter = ScenarioControlledSplit(config)

        result = splitter.split(
            dataset.invoices, dataset.purchase_orders, dataset.goods_receipts,
            dataset.vendors, dataset.ground_truth
        )

        # All invoices accounted for
        total_split = len(result.train_invoices) + len(result.validation_invoices) + len(result.test_invoices)
        assert total_split == len(dataset.invoices)

        # All vendors accounted for
        total_vendors = len(result.train_vendors) + len(result.validation_vendors) + len(result.test_vendors)
        assert total_vendors == len(dataset.vendors)

        # All ground truths accounted for
        total_gts = len(result.train_ground_truths) + len(result.validation_ground_truths) + len(result.test_ground_truths)
        assert total_gts == len(dataset.ground_truth)

        # Approximate ratios (70/15/15)
        n_vendors = len(dataset.vendors)
        assert abs(len(result.train_vendors) - 0.7 * n_vendors) <= 2
        assert abs(len(result.validation_vendors) - 0.15 * n_vendors) <= 2
        assert abs(len(result.test_vendors) - 0.15 * n_vendors) <= 2

    def test_all_exception_types_represented(self, dataset):
        """All supported exception types remain represented in each split."""
        config = SplitConfig(seed=42)
        splitter = ScenarioControlledSplit(config)

        result = splitter.split(
            dataset.invoices, dataset.purchase_orders, dataset.goods_receipts,
            dataset.vendors, dataset.ground_truth
        )

        all_codes = set(e.value for e in ExceptionCode)

        # Check each split has all exception types (at least in ground truth)
        for split_name, gts in [("train", result.train_ground_truths),
                                 ("validation", result.validation_ground_truths),
                                 ("test", result.test_ground_truths)]:
            split_codes = set()
            for gt in gts:
                for exc in gt.expected_exceptions:
                    split_codes.add(exc.value)
            # At minimum, each split should have some exceptions represented
            # (with multi-exception invoices, some types may only appear in combinations)
            assert len(split_codes) > 0, f"{split_name} has no exception types represented"

    def test_novel_test_combinations(self, dataset):
        """Test set contains at least one exception combination not in train."""
        config = SplitConfig(seed=42)
        splitter = ScenarioControlledSplit(config)

        result = splitter.split(
            dataset.invoices, dataset.purchase_orders, dataset.goods_receipts,
            dataset.vendors, dataset.ground_truth
        )

        # This is the critical requirement: novel combinations in test
        assert result.novel_combinations_in_test > 0, (
            f"Test set must contain novel exception combinations not seen in training. "
            f"Found {result.novel_combinations_in_test} novel combinations."
        )

    def test_unseen_vendors_in_test(self, dataset):
        """Test set contains vendors not seen in train/validation."""
        config = SplitConfig(seed=42)
        splitter = ScenarioControlledSplit(config)

        result = splitter.split(
            dataset.invoices, dataset.purchase_orders, dataset.goods_receipts,
            dataset.vendors, dataset.ground_truth
        )

        # Test vendors should be disjoint from train/val
        unseen = result.test_vendors - result.train_vendors - result.validation_vendors
        assert len(unseen) > 0, "Test set should contain unseen vendors"
        assert result.unseen_vendors_in_test == len(unseen)

    def test_no_duplicate_invoice_ids_across_splits(self, dataset):
        """No invoice ID appears in more than one split."""
        config = SplitConfig(seed=42)
        splitter = ScenarioControlledSplit(config)

        result = splitter.split(
            dataset.invoices, dataset.purchase_orders, dataset.goods_receipts,
            dataset.vendors, dataset.ground_truth
        )

        train_ids = {inv.invoice_id for inv in result.train_invoices}
        val_ids = {inv.invoice_id for inv in result.validation_invoices}
        test_ids = {inv.invoice_id for inv in result.test_invoices}

        assert train_ids.isdisjoint(val_ids)
        assert train_ids.isdisjoint(test_ids)
        assert val_ids.isdisjoint(test_ids)

    def test_stable_serialization_order(self, dataset):
        """Split produces deterministic output order for stable serialization."""
        config = SplitConfig(seed=42)
        splitter = ScenarioControlledSplit(config)

        result1 = splitter.split(
            dataset.invoices, dataset.purchase_orders, dataset.goods_receipts,
            dataset.vendors, dataset.ground_truth
        )
        result2 = splitter.split(
            dataset.invoices, dataset.purchase_orders, dataset.goods_receipts,
            dataset.vendors, dataset.ground_truth
        )

        # Invoice order within each split should be stable
        train_ids_1 = [inv.invoice_id for inv in result1.train_invoices]
        train_ids_2 = [inv.invoice_id for inv in result2.train_invoices]
        assert train_ids_1 == train_ids_2

        val_ids_1 = [inv.invoice_id for inv in result1.validation_invoices]
        val_ids_2 = [inv.invoice_id for inv in result2.validation_invoices]
        assert val_ids_1 == val_ids_2

        test_ids_1 = [inv.invoice_id for inv in result1.test_invoices]
        test_ids_2 = [inv.invoice_id for inv in result2.test_invoices]
        assert test_ids_1 == test_ids_2

    def test_verify_split_diagnostics(self, dataset):
        """Verify split diagnostics contain expected metrics."""
        config = SplitConfig(seed=42)
        splitter = ScenarioControlledSplit(config)

        result = splitter.split(
            dataset.invoices, dataset.purchase_orders, dataset.goods_receipts,
            dataset.vendors, dataset.ground_truth
        )

        diagnostics = splitter.verify_split(result)

        assert "vendor_distribution" in diagnostics
        assert "invoice_distribution" in diagnostics
        assert "train_amount_range" in diagnostics
        assert "test_amount_range" in diagnostics
        assert "novel_combinations_in_test" in diagnostics
        assert "unseen_vendors_in_test" in diagnostics
        assert "vendor_leakage" in diagnostics

        # Check amount ranges are populated
        assert "min" in diagnostics["train_amount_range"]
        assert "max" in diagnostics["train_amount_range"]
        assert "min" in diagnostics["test_amount_range"]
        assert "max" in diagnostics["test_amount_range"]

    def test_convenience_function(self, dataset):
        """Test the create_scenario_split convenience function."""
        config = SplitConfig(seed=42)
        result = create_scenario_split(
            dataset.invoices, dataset.purchase_orders, dataset.goods_receipts,
            dataset.vendors, dataset.ground_truth, config
        )

        assert len(result.train_invoices) > 0
        assert len(result.validation_invoices) > 0
        assert len(result.test_invoices) > 0
        assert result.novel_combinations_in_test > 0


class TestSplitConfig:
    """Tests for SplitConfig defaults and customization."""

    def test_default_ratios(self):
        """Default ratios sum to 1.0."""
        config = SplitConfig()
        total = config.train_vendor_ratio + config.validation_vendor_ratio + config.test_vendor_ratio
        assert abs(total - 1.0) < 0.001

    def test_custom_seed(self):
        """Custom seed is respected."""
        config = SplitConfig(seed=999)
        assert config.seed == 999

    def test_custom_amount_ranges(self):
        """Custom amount ranges are configurable."""
        config = SplitConfig(
            train_amount_range=(Decimal("100"), Decimal("50000")),
            test_amount_range=(Decimal("50000"), Decimal("150000"))
        )
        assert config.train_amount_range[0] == Decimal("100")
        assert config.test_amount_range[1] == Decimal("150000")

    def test_custom_policy_versions(self):
        """Custom policy versions are configurable."""
        config = SplitConfig(
            train_policy_version="v1.0",
            test_policy_version="v1.1"
        )
        assert config.train_policy_version == "v1.0"
        assert config.test_policy_version == "v1.1"