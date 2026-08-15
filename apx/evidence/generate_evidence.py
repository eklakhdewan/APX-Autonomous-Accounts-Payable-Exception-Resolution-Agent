#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from apx.config.settings import get_settings
from apx.evidence.schemas import (
    Evidence,
    EvidenceType,
    SourceAuthority,
)


class EvidenceCorpusGenerator:
    def __init__(self, seed: int = 42):
        self.seed = seed
        self.rng = random.Random(seed)
        self.settings = get_settings()
        self.evidence: list[Evidence] = []
        self._evidence_id_seq = 0

    def _next_evidence_id(self) -> str:
        self._evidence_id_seq += 1
        return f"EV-{self._evidence_id_seq:05d}"

    def _random_date(self, start: date, end: date) -> date:
        delta = (end - start).days
        return start + timedelta(days=self.rng.randint(0, delta))

    def generate_historical_resolutions(
        self,
        vendors: list[str],
        exception_codes: list[str],
        count: int = 100,
    ) -> list[Evidence]:
        outcomes = [
            "AUTO_APPROVED",
            "MANUAL_REVIEW_APPROVED",
            "REQUEST_INFO_RESOLVED",
            "ESCALATED_RESOLVED",
            "REJECTED",
            "PARTIAL_PAYMENT",
        ]
        authorities = list(SourceAuthority)
        resolutions = []

        for _ in range(count):
            vendor_id = self.rng.choice(vendors)
            exception_code = self.rng.choice(exception_codes)
            effective_from = self._random_date(date(2024, 1, 1), date(2025, 12, 31))
            effective_until = effective_from + timedelta(days=self.rng.randint(30, 365))
            policy_version = f"v{self.rng.randint(1, 5)}.{self.rng.randint(0, 9)}"
            outcome = self.rng.choice(outcomes)
            authority = self.rng.choice(authorities)

            content = (
                f"Historical resolution for {exception_code} on vendor {vendor_id}. "
                f"Previous outcome: {outcome}. "
                f"Resolution action: {self._generate_resolution_action(exception_code, outcome)}. "
                f"Policy version {policy_version} applied."
            )

            evidence = Evidence(
                evidence_id=self._next_evidence_id(),
                evidence_type=EvidenceType.HISTORICAL_RESOLUTION,
                scope="vendor_exception",
                scope_target=f"{vendor_id}:{exception_code}",
                vendor_id=vendor_id,
                effective_from=effective_from,
                effective_until=effective_until,
                policy_version=policy_version,
                outcome=outcome,
                source_authority=authority,
                usage_count=self.rng.randint(0, 50),
                content=content,
                metadata={
                    "exception_code": exception_code,
                    "resolution_action": self._generate_resolution_action(exception_code, outcome),
                },
            )
            self.evidence.append(evidence)
            resolutions.append(evidence)
        return resolutions

    def _generate_resolution_action(self, exception_code: str, outcome: str) -> str:
        actions = {
            "VENDOR_MISMATCH": ["Vendor corrected", "Invoice rejected", "Escalated to procurement"],
            "PO_MISMATCH": ["PO corrected", "Invoice matched to correct PO", "Manual override"],
            "AMOUNT_MISMATCH": ["Amount corrected", "Tolerance applied", "Credit memo issued"],
            "GRN_MISMATCH": ["Quantity adjusted", "Partial receipt accepted", "Return initiated"],
            "DUPLICATE_INVOICE": ["Duplicate voided", "Original processed", "Manual verification"],
            "TAX_ERROR": ["Tax recalculated", "Invoice corrected", "Exemption applied"],
            "CURRENCY_MISMATCH": ["Currency converted", "Invoice reissued", "Rate locked"],
            "LINE_ITEM_MISMATCH": ["Line items corrected", "Price adjusted", "Quantity matched"],
            "DISCOUNT_ERROR": ["Discount corrected", "Contract terms applied", "Manual override"],
            "CREDIT_ISSUE": ["Credit hold released", "Payment terms adjusted", "Escalated to finance"],
        }
        return self.rng.choice(actions.get(exception_code, ["Resolved"]))

    def generate_vendor_policies(
        self,
        vendors: list[str],
        count: int = 50,
    ) -> list[Evidence]:
        policy_scopes = ["payment_terms", "exception_thresholds", "credit_limits", "discount_rules"]
        authorities = list(SourceAuthority)
        policies = []

        for _ in range(count):
            vendor_id = self.rng.choice(vendors)
            scope = self.rng.choice(policy_scopes)
            effective_from = self._random_date(date(2024, 1, 1), date(2025, 6, 30))
            effective_until = effective_from + timedelta(days=self.rng.randint(180, 730))
            policy_version = f"v{self.rng.randint(1, 5)}.{self.rng.randint(0, 9)}"
            authority = self.rng.choice(authorities)

            content = self._generate_policy_content(vendor_id, scope, policy_version)

            evidence = Evidence(
                evidence_id=self._next_evidence_id(),
                evidence_type=EvidenceType.VENDOR_POLICY,
                scope=scope,
                scope_target=vendor_id,
                vendor_id=vendor_id,
                effective_from=effective_from,
                effective_until=effective_until,
                policy_version=policy_version,
                outcome="ACTIVE",
                source_authority=authority,
                usage_count=self.rng.randint(0, 100),
                content=content,
                metadata={
                    "policy_scope": scope,
                    "thresholds": self._generate_thresholds(scope),
                },
            )
            self.evidence.append(evidence)
            policies.append(evidence)
        return policies

    def _generate_policy_content(self, vendor_id: str, scope: str, version: str) -> str:
        templates = {
            "payment_terms": f"Vendor {vendor_id} payment terms policy {version}. Standard terms: Net 30. Early payment discount: 2% Net 10.",
            "exception_thresholds": f"Vendor {vendor_id} exception thresholds policy {version}. Amount tolerance: 2%. Quantity tolerance: 0%.",
            "credit_limits": f"Vendor {vendor_id} credit limits policy {version}. Credit limit: $100,000. Hold threshold: $80,000.",
            "discount_rules": f"Vendor {vendor_id} discount rules policy {version}. Max early payment discount: 2%. Volume discounts per contract.",
        }
        return templates.get(scope, f"Policy {version} for {vendor_id}")

    def _generate_thresholds(self, scope: str) -> dict[str, Any]:
        return {
            "payment_terms": {"net_days": 30, "early_discount_pct": 2, "early_days": 10},
            "exception_thresholds": {"amount_pct": 0.02, "quantity_pct": 0.0, "tax_pct": 0.01},
            "credit_limits": {"credit_limit": 100000, "hold_threshold": 80000},
            "discount_rules": {"max_early_discount": 0.02, "volume_discount_tiers": [0.01, 0.02, 0.03]},
        }.get(scope, {})

    def generate_contracts(
        self,
        vendors: list[str],
        count: int = 30,
    ) -> list[Evidence]:
        authorities = list(SourceAuthority)
        contracts = []

        for _ in range(count):
            vendor_id = self.rng.choice(vendors)
            contract_id = f"CTR-{vendor_id}-{self.rng.randint(1000, 9999)}"
            effective_from = self._random_date(date(2023, 1, 1), date(2025, 12, 31))
            effective_until = effective_from + timedelta(days=self.rng.randint(365, 1095))
            policy_version = f"v{self.rng.randint(1, 3)}.0"
            authority = self.rng.choice(authorities)

            content = (
                f"Contract {contract_id} for vendor {vendor_id}. "
                f"Terms: Net 30 payment, 2% early payment discount, "
                f"volume discounts at 10k/50k/100k thresholds. "
                f"Exception tolerance: amount 2%, quantity 0%, tax 1%. "
                f"Governing law: State of Delaware. Version {policy_version}."
            )

            evidence = Evidence(
                evidence_id=self._next_evidence_id(),
                evidence_type=EvidenceType.CONTRACT,
                scope="contractual_terms",
                scope_target=contract_id,
                vendor_id=vendor_id,
                effective_from=effective_from,
                effective_until=effective_until,
                policy_version=policy_version,
                outcome="ACTIVE",
                source_authority=authority,
                usage_count=self.rng.randint(0, 200),
                content=content,
                metadata={
                    "contract_id": contract_id,
                    "payment_terms": "Net 30",
                    "early_discount": "2% Net 10",
                    "exception_tolerances": {"amount": 0.02, "quantity": 0.0, "tax": 0.01},
                },
            )
            self.evidence.append(evidence)
            contracts.append(evidence)
        return contracts

    def generate_payment_terms(
        self,
        vendors: list[str],
        count: int = 20,
    ) -> list[Evidence]:
        authorities = list(SourceAuthority)
        terms = []

        for _ in range(count):
            vendor_id = self.rng.choice(vendors)
            effective_from = self._random_date(date(2024, 1, 1), date(2025, 6, 30))
            effective_until = effective_from + timedelta(days=self.rng.randint(180, 365))
            policy_version = f"v{self.rng.randint(1, 3)}.0"
            authority = self.rng.choice(authorities)

            net_days = self.rng.choice([15, 30, 45, 60])
            early_pct = self.rng.choice([1, 2, 3])
            early_days = self.rng.choice([5, 10, 15])

            content = (
                f"Payment terms for vendor {vendor_id}. "
                f"Net {net_days} days. Early payment discount: {early_pct}% if paid within {early_days} days. "
                f"Late fee: 1.5% per month after due date. Version {policy_version}."
            )

            evidence = Evidence(
                evidence_id=self._next_evidence_id(),
                evidence_type=EvidenceType.PAYMENT_TERM,
                scope="payment_terms",
                scope_target=vendor_id,
                vendor_id=vendor_id,
                effective_from=effective_from,
                effective_until=effective_until,
                policy_version=policy_version,
                outcome="ACTIVE",
                source_authority=authority,
                usage_count=self.rng.randint(0, 500),
                content=content,
                metadata={
                    "net_days": net_days,
                    "early_discount_pct": early_pct,
                    "early_days": early_days,
                    "late_fee_pct": 1.5,
                },
            )
            self.evidence.append(evidence)
            terms.append(evidence)
        return terms

    def generate_irrelevant_evidence(self, count: int = 20) -> list[Evidence]:
        irrelevant = []
        for _ in range(count):
            evidence = Evidence(
                evidence_id=self._next_evidence_id(),
                evidence_type=self.rng.choice(list(EvidenceType)),
                scope="irrelevant",
                scope_target="N/A",
                vendor_id=None,
                effective_from=date(2020, 1, 1),
                effective_until=date(2021, 12, 31),
                policy_version="v1.0",
                outcome="EXPIRED",
                source_authority=SourceAuthority.INTERNAL,
                usage_count=0,
                content="This is deliberately irrelevant evidence for testing filtering.",
                metadata={"test_only": True},
            )
            self.evidence.append(evidence)
            irrelevant.append(evidence)
        return irrelevant

    def generate_stale_evidence(self, count: int = 15) -> list[Evidence]:
        stale = []
        for _ in range(count):
            evidence = Evidence(
                evidence_id=self._next_evidence_id(),
                evidence_type=self.rng.choice(list(EvidenceType)),
                scope="stale_test",
                scope_target="V-0001",
                vendor_id="V-0001",
                effective_from=date(2022, 1, 1),
                effective_until=date(2022, 12, 31),
                policy_version="v1.0",
                outcome="EXPIRED",
                source_authority=SourceAuthority.INTERNAL,
                usage_count=0,
                content="This evidence is stale (effective_until in the past) for testing date filtering.",
                metadata={"test_stale": True},
            )
            self.evidence.append(evidence)
            stale.append(evidence)
        return stale

    def generate_all(
        self,
        vendors: list[str],
        exception_codes: list[str],
        historical_count: int = 100,
        policy_count: int = 50,
        contract_count: int = 30,
        payment_term_count: int = 20,
        irrelevant_count: int = 20,
        stale_count: int = 15,
    ) -> dict:
        self.generate_historical_resolutions(vendors, exception_codes, historical_count)
        self.generate_vendor_policies(vendors, policy_count)
        self.generate_contracts(vendors, contract_count)
        self.generate_payment_terms(vendors, payment_term_count)
        self.generate_irrelevant_evidence(irrelevant_count)
        self.generate_stale_evidence(stale_count)
        return self.export()

    def export(self) -> dict:
        return {"evidence": [e.model_dump(mode="json") for e in self.evidence]}

    def save(self, base_dir: Path | None = None):
        if base_dir is None:
            base_dir = self.settings.get_corpus_path()
        base_dir.mkdir(parents=True, exist_ok=True)
        data = self.export()
        file_path = base_dir / "evidence_corpus.json"
        with file_path.open("w") as f:
            json.dump(data, f, indent=2, default=str)
        print(f"Saved {len(self.evidence)} evidence records to {file_path}")


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic evidence corpus")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument("--output-dir", type=str, help="Output directory")
    args = parser.parse_args()

    generator = EvidenceCorpusGenerator(seed=args.seed)
    generator.generate_all(
        vendors=[f"V-{i:04d}" for i in range(1, 21)],
        exception_codes=[
            "VENDOR_MISMATCH", "PO_MISMATCH", "AMOUNT_MISMATCH", "GRN_MISMATCH",
            "DUPLICATE_INVOICE", "TAX_ERROR", "CURRENCY_MISMATCH", "LINE_ITEM_MISMATCH",
            "DISCOUNT_ERROR", "CREDIT_ISSUE"
        ],
    )
    if args.output_dir:
        generator.save(Path(args.output_dir))
    else:
        generator.save()


if __name__ == "__main__":
    main()