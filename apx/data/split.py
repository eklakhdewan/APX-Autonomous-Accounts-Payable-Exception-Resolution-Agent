from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set, Tuple
from collections import defaultdict

from apx.data.schemas import Invoice, PurchaseOrder, Vendor, GoodsReceipt, GroundTruth


@dataclass
class SplitConfig:
    """Configuration for dataset splitting."""
    train_vendor_ratio: float = 0.7
    validation_vendor_ratio: float = 0.15
    test_vendor_ratio: float = 0.15

    train_amount_range: Tuple[Decimal, Decimal] = (Decimal("100"), Decimal("50000"))
    test_amount_range: Tuple[Decimal, Decimal] = (Decimal("50000"), Decimal("150000"))

    train_policy_version: str = "v1.0"
    test_policy_version: str = "v1.1"

    seed: int = 42


@dataclass
class SplitResult:
    """Result of dataset splitting."""
    train_invoices: List[Invoice] = field(default_factory=list)
    validation_invoices: List[Invoice] = field(default_factory=list)
    test_invoices: List[Invoice] = field(default_factory=list)

    train_vendors: Set[str] = field(default_factory=set)
    validation_vendors: Set[str] = field(default_factory=set)
    test_vendors: Set[str] = field(default_factory=set)

    train_ground_truths: List[GroundTruth] = field(default_factory=list)
    validation_ground_truths: List[GroundTruth] = field(default_factory=list)
    test_ground_truths: List[GroundTruth] = field(default_factory=list)

    # Statistics
    vendor_leakage: bool = False
    novel_combinations_in_test: int = 0
    unseen_vendors_in_test: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "train_count": len(self.train_invoices),
            "validation_count": len(self.validation_invoices),
            "test_count": len(self.test_invoices),
            "train_vendors": list(self.train_vendors),
            "validation_vendors": list(self.validation_vendors),
            "test_vendors": list(self.test_vendors),
            "vendor_leakage": self.vendor_leakage,
            "novel_combinations_in_test": self.novel_combinations_in_test,
            "unseen_vendors_in_test": self.unseen_vendors_in_test,
        }


class ScenarioControlledSplit:
    """
    Multi-axis dataset split as per V1.1 specification.

    Split dimensions:
    - Vendors: Train (~70%), Validation (~15%), Test (~15% + unseen)
    - Exception types: All represented in all splits
    - Exception combinations: Novel combinations in test
    - Amount range: Train $100-$50K, Test $50K-$150K
    - Policy version: Train/Val v1.0, Test v1.1
    """

    def __init__(self, config: Optional[SplitConfig] = None):
        self.config = config or SplitConfig()
        self._rng = random.Random(self.config.seed)

    def split(
        self,
        invoices: List[Invoice],
        pos: List[PurchaseOrder],
        grns: List[GoodsReceipt],
        vendors: List[Vendor],
        ground_truths: List[GroundTruth],
    ) -> SplitResult:
        """Perform the multi-axis split."""
        if not invoices:
            return SplitResult()

        # Reset RNG for deterministic results even when called multiple times
        self._rng = random.Random(self.config.seed)

        # Group invoices by vendor
        vendor_invoices = defaultdict(list)
        vendor_gts = defaultdict(list)
        gt_map = {gt.invoice_id: gt for gt in ground_truths}
        for inv in invoices:
            vendor_invoices[inv.vendor_id].append(inv)
            if inv.invoice_id in gt_map:
                vendor_gts[inv.vendor_id].append(gt_map[inv.invoice_id])

        vendor_list = list(vendor_invoices.keys())
        self._rng.shuffle(vendor_list)

        # Split vendors
        n_vendors = len(vendor_list)
        n_train = int(n_vendors * self.config.train_vendor_ratio)
        n_val = int(n_vendors * self.config.validation_vendor_ratio)
        n_test = n_vendors - n_train - n_val

        train_vendors = set(vendor_list[:n_train])
        val_vendors = set(vendor_list[n_train:n_train + n_val])
        test_vendors = set(vendor_list[n_train + n_val:])

        # Assign invoices to splits based on vendor
        train_invoices = []
        val_invoices = []
        test_invoices = []

        for inv in invoices:
            if inv.vendor_id in train_vendors:
                train_invoices.append(inv)
            elif inv.vendor_id in val_vendors:
                val_invoices.append(inv)
            else:
                test_invoices.append(inv)

        # Assign ground truths for initial combination analysis (before amount filter)
        train_gts = [gt_map[inv.invoice_id] for inv in train_invoices if inv.invoice_id in gt_map]
        val_gts = [gt_map[inv.invoice_id] for inv in val_invoices if inv.invoice_id in gt_map]
        test_gts = [gt_map[inv.invoice_id] for inv in test_invoices if inv.invoice_id in gt_map]

        # Identify novel exception combinations in test (before amount filter)
        train_combos = self._get_exception_combinations(train_gts)
        val_combos = self._get_exception_combinations(val_gts)
        test_combos = self._get_exception_combinations(test_gts)

        known_combos = train_combos | val_combos
        novel_combos = test_combos - known_combos

        # Identify invoices in test that have novel combinations (to preserve during amount filter)
        novel_invoice_ids = set()
        for inv in test_invoices:
            gt = gt_map.get(inv.invoice_id)
            if gt and frozenset(gt.expected_exceptions) in novel_combos:
                novel_invoice_ids.add(inv.invoice_id)

        # If no novel combinations, try to create them by moving a vendor from train to test
        if len(novel_combos) == 0:
            train_vendors, val_vendors, test_vendors, train_invoices, val_invoices, test_invoices, train_gts, val_gts, test_gts = self._ensure_novel_combinations(
                vendor_invoices, vendor_gts, train_vendors, val_vendors, test_vendors,
                train_invoices, val_invoices, test_invoices, train_gts, val_gts, test_gts
            )

            # Recompute combinations and novel combinations after adjustment
            train_combos = self._get_exception_combinations(train_gts)
            val_combos = self._get_exception_combinations(val_gts)
            test_combos = self._get_exception_combinations(test_gts)
            known_combos = train_combos | val_combos
            novel_combos = test_combos - known_combos

            # Re-identify invoices with novel combinations
            novel_invoice_ids = set()
            for inv in test_invoices:
                gt = gt_map.get(inv.invoice_id)
                if gt and frozenset(gt.expected_exceptions) in novel_combos:
                    novel_invoice_ids.add(inv.invoice_id)

        # Now enforce amount range split for test, but PRESERVE invoices with novel combinations
        test_in_range = []
        test_out_of_range = []
        for inv in test_invoices:
            if self.config.test_amount_range[0] <= inv.total <= self.config.test_amount_range[1]:
                test_in_range.append(inv)
            elif inv.invoice_id in novel_invoice_ids:
                # Preserve invoices with novel combinations even if outside amount range
                test_in_range.append(inv)
            else:
                test_out_of_range.append(inv)

        # Move out-of-range test invoices to train
        train_invoices.extend(test_out_of_range)
        test_invoices = test_in_range

        # Assign final ground truths
        train_gts = [gt_map[inv.invoice_id] for inv in train_invoices if inv.invoice_id in gt_map]
        val_gts = [gt_map[inv.invoice_id] for inv in val_invoices if inv.invoice_id in gt_map]
        test_gts = [gt_map[inv.invoice_id] for inv in test_invoices if inv.invoice_id in gt_map]

        # Recompute final combinations
        train_combos = self._get_exception_combinations(train_gts)
        val_combos = self._get_exception_combinations(val_gts)
        test_combos = self._get_exception_combinations(test_gts)
        known_combos = train_combos | val_combos
        novel_combos = test_combos - known_combos

        # Check for vendor leakage
        vendor_leakage = bool(train_vendors & test_vendors) or bool(val_vendors & test_vendors)

        # Count unseen vendors in test (vendors not in train/val)
        unseen_vendors = test_vendors - train_vendors - val_vendors

        return SplitResult(
            train_invoices=train_invoices,
            validation_invoices=val_invoices,
            test_invoices=test_invoices,
            train_vendors=train_vendors,
            validation_vendors=val_vendors,
            test_vendors=test_vendors,
            train_ground_truths=train_gts,
            validation_ground_truths=val_gts,
            test_ground_truths=test_gts,
            vendor_leakage=vendor_leakage,
            novel_combinations_in_test=len(novel_combos),
            unseen_vendors_in_test=len(unseen_vendors),
        )

    def _ensure_novel_combinations(
        self,
        vendor_invoices: Dict[str, List[Invoice]],
        vendor_gts: Dict[str, List[GroundTruth]],
        train_vendors: Set[str],
        val_vendors: Set[str],
        test_vendors: Set[str],
        train_invoices: List[Invoice],
        val_invoices: List[Invoice],
        test_invoices: List[Invoice],
        train_gts: List[GroundTruth],
        val_gts: List[GroundTruth],
        test_gts: List[GroundTruth],
    ) -> Tuple[Set[str], Set[str], Set[str], List[Invoice], List[Invoice], List[Invoice], List[GroundTruth], List[GroundTruth], List[GroundTruth]]:
        """Move a vendor from train to test to ensure novel combinations."""
        # Get combinations in train and val
        train_combos = self._get_exception_combinations(train_gts)
        val_combos = self._get_exception_combinations(val_gts)
        known_combos = train_combos | val_combos

        # Find vendors in train that have multi-exception combinations not in known_combos
        # (i.e., combinations that are unique to that vendor)
        vendor_to_combos = {}
        for vendor_id in train_vendors:
            vendor_combos = self._get_exception_combinations(vendor_gts[vendor_id])
            # Only consider multi-exception combinations
            multi_combos = {c for c in vendor_combos if len(c) > 1}
            if multi_combos:
                vendor_to_combos[vendor_id] = multi_combos

        # Find vendors whose multi-combos are not in val (and ideally rare in train)
        candidate_vendors = []
        for vendor_id, combos in vendor_to_combos.items():
            novel_to_known = combos - known_combos
            if novel_to_known:
                # This vendor has combinations not in val
                # Count how many invoices have these combos
                count = sum(1 for gt in vendor_gts[vendor_id] if frozenset(gt.expected_exceptions) in novel_to_known)
                candidate_vendors.append((vendor_id, len(novel_to_known), count))

        if candidate_vendors:
            # Pick the vendor with the most novel combinations
            candidate_vendors.sort(key=lambda x: (-x[1], -x[2]))
            vendor_to_move = candidate_vendors[0][0]

            # Move vendor from train to test
            train_vendors.remove(vendor_to_move)
            test_vendors.add(vendor_to_move)

            # Move invoices and ground truths
            vendor_inv = vendor_invoices[vendor_to_move]
            vendor_gt = vendor_gts[vendor_to_move]

            train_invoices = [inv for inv in train_invoices if inv.vendor_id != vendor_to_move]
            test_invoices.extend(vendor_inv)
            train_gts = [gt for gt in train_gts if gt.invoice_id not in {inv.invoice_id for inv in vendor_inv}]
            test_gts.extend(vendor_gt)

        return train_vendors, val_vendors, test_vendors, train_invoices, val_invoices, test_invoices, train_gts, val_gts, test_gts

    def _get_exception_combinations(self, ground_truths: List[GroundTruth]) -> Set[frozenset]:
        """Get set of exception combinations from ground truths."""
        combos = set()
        for gt in ground_truths:
            codes = frozenset(gt.expected_exceptions)
            combos.add(codes)
        return combos

    def verify_split(self, result: SplitResult) -> Dict[str, Any]:
        """Verify split quality and return diagnostics."""
        diagnostics = {}

        # Vendor distribution
        diagnostics["vendor_distribution"] = {
            "train": len(result.train_vendors),
            "validation": len(result.validation_vendors),
            "test": len(result.test_vendors),
            "total": len(result.train_vendors) + len(result.validation_vendors) + len(result.test_vendors),
        }

        # Invoice distribution
        diagnostics["invoice_distribution"] = {
            "train": len(result.train_invoices),
            "validation": len(result.validation_invoices),
            "test": len(result.test_invoices),
            "total": len(result.train_invoices) + len(result.validation_invoices) + len(result.test_invoices),
        }

        # Amount ranges
        if result.train_invoices:
            train_amounts = [inv.total for inv in result.train_invoices]
            diagnostics["train_amount_range"] = {
                "min": float(min(train_amounts)),
                "max": float(max(train_amounts)),
                "avg": float(sum(train_amounts) / len(train_amounts)),
            }

        if result.test_invoices:
            test_amounts = [inv.total for inv in result.test_invoices]
            diagnostics["test_amount_range"] = {
                "min": float(min(test_amounts)),
                "max": float(max(test_amounts)),
                "avg": float(sum(test_amounts) / len(test_amounts)),
            }

        # Exception type coverage
        for split_name, gts in [("train", result.train_ground_truths),
                                 ("validation", result.validation_ground_truths),
                                 ("test", result.test_ground_truths)]:
            exception_counts = defaultdict(int)
            for gt in gts:
                for exc in gt.expected_exceptions:
                    exception_counts[exc.value] += 1
            diagnostics[f"{split_name}_exception_coverage"] = dict(exception_counts)

        # Novel combinations
        diagnostics["novel_combinations_in_test"] = result.novel_combinations_in_test
        diagnostics["unseen_vendors_in_test"] = result.unseen_vendors_in_test
        diagnostics["vendor_leakage"] = result.vendor_leakage

        return diagnostics


def create_scenario_split(
    invoices: List[Invoice],
    pos: List[PurchaseOrder],
    grns: List[GoodsReceipt],
    vendors: List[Vendor],
    ground_truths: List[GroundTruth],
    config: Optional[SplitConfig] = None,
) -> SplitResult:
    """Convenience function to create a scenario-controlled split."""
    splitter = ScenarioControlledSplit(config)
    return splitter.split(invoices, pos, grns, vendors, ground_truths)