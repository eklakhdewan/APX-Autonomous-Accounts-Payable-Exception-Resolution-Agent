#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from apx.data.schemas import (
    Vendor,
    PurchaseOrder,
    PurchaseOrderLine,
    GoodsReceipt,
    GoodsReceiptLine,
    Invoice,
    InvoiceLine,
    Currency,
    CreditStatus,
    POStatus,
    GRNStatus,
    VendorStatus,
    ExceptionCode,
    GroundTruth,
)
from apx.config.settings import get_settings


class SyntheticGenerator:
    def __init__(self, seed: int = 42):
        self.seed = seed
        self.rng = random.Random(seed)
        self.settings = get_settings()
        self.tolerance = self.settings.get_tolerance()

        self.vendors: list[Vendor] = []
        self.purchase_orders: list[PurchaseOrder] = []
        self.goods_receipts: list[GoodsReceipt] = []
        self.invoices: list[Invoice] = []
        self.ground_truth: list[GroundTruth] = []
        self._clean_invoices: list[Invoice] = []

        self._vendor_id_seq = 0
        self._po_id_seq = 0
        self._grn_id_seq = 0
        self._invoice_id_seq = 0
        self._line_id_seq = 0

    def _next_vendor_id(self) -> str:
        self._vendor_id_seq += 1
        return f"V-{self._vendor_id_seq:04d}"

    def _next_po_id(self) -> str:
        self._po_id_seq += 1
        return f"PO-2026-{self._po_id_seq:04d}"

    def _next_grn_id(self) -> str:
        self._grn_id_seq += 1
        return f"GRN-2026-{self._grn_id_seq:04d}"

    def _next_invoice_id(self) -> str:
        self._invoice_id_seq += 1
        return f"INV-2026-{self._invoice_id_seq:04d}"

    def _next_line_id(self) -> str:
        self._line_id_seq += 1
        return f"L-{self._line_id_seq:04d}"

    def _random_date(self, start: date, end: date) -> date:
        delta = (end - start).days
        return start + timedelta(days=self.rng.randint(0, delta))

    def _random_decimal(self, min_val: float, max_val: float, places: int = 2) -> Decimal:
        val = self.rng.uniform(min_val, max_val)
        return Decimal(str(round(val, places)))

    def _quantize(self, value: Decimal) -> Decimal:
        return value.quantize(Decimal("0.01"))

    def generate_vendors(self, count: int) -> list[Vendor]:
        currencies = list(Currency)
        credit_statuses = list(CreditStatus)
        statuses = list(VendorStatus)

        for i in range(count):
            vendor = Vendor(
                vendor_id=self._next_vendor_id(),
                vendor_name=f"Vendor {self._vendor_id_seq:04d}",
                tax_id=f"TAX{self.rng.randint(10000000, 99999999)}",
                currency=self.rng.choice(currencies),
                payment_terms_days=self.rng.choice([15, 30, 45, 60]),
                credit_status=self.rng.choices(credit_statuses, weights=[0.7, 0.15, 0.1, 0.05])[0],
                status=self.rng.choices(statuses, weights=[0.85, 0.1, 0.05])[0],
            )
            self.vendors.append(vendor)
        return self.vendors

    def generate_purchase_orders(self, count: int) -> list[PurchaseOrder]:
        if not self.vendors:
            raise ValueError("Must generate vendors first")

        for _ in range(count):
            vendor = self.rng.choice(self.vendors)
            num_lines = self.rng.randint(1, 5)
            lines = []

            for _ in range(num_lines):
                qty = self._random_decimal(1, 100, 0)
                unit_price = self._random_decimal(10, 500)
                discount = self._random_decimal(0, float(qty * unit_price * Decimal("0.1")), 2)
                tax_rate = self._random_decimal(0, 0.2, 3)

                line = PurchaseOrderLine(
                    line_id=self._next_line_id(),
                    description=f"Item {self._line_id_seq}",
                    quantity=qty,
                    unit_price=unit_price,
                    discount=discount,
                    tax_rate=tax_rate,
                )
                lines.append(line)

            subtotal = sum(line.line_total() for line in lines)
            tax = sum(line.line_tax() for line in lines)
            total = subtotal + tax

            po = PurchaseOrder(
                po_id=self._next_po_id(),
                vendor_id=vendor.vendor_id,
                po_number=f"PO-{self._po_id_seq:06d}",
                po_date=self._random_date(date(2026, 1, 1), date(2026, 6, 30)),
                currency=vendor.currency,
                subtotal=self._quantize(subtotal),
                tax=self._quantize(tax),
                total=self._quantize(total),
                line_items=lines,
                status=self.rng.choices(list(POStatus), weights=[0.4, 0.3, 0.2, 0.1])[0],
            )
            self.purchase_orders.append(po)
        return self.purchase_orders

    def generate_goods_receipts(self, count: int) -> list[GoodsReceipt]:
        if not self.purchase_orders:
            raise ValueError("Must generate POs first")

        pos_with_open = [po for po in self.purchase_orders if po.status != POStatus.CANCELLED]

        # Generate GRN for every PO to ensure full coverage for GRN_MISMATCH
        for po in pos_with_open:
            vendor = next(v for v in self.vendors if v.vendor_id == po.vendor_id)

            lines = []
            for po_line in po.line_items:
                qty_received = (po_line.quantity * Decimal(str(self._random_decimal(0.8, 1.0, 2)))).quantize(Decimal("0.01"))
                lines.append(GoodsReceiptLine(
                    line_id=self._next_line_id(),
                    po_line_id=po_line.line_id,
                    quantity_received=qty_received,
                ))

            grn = GoodsReceipt(
                grn_id=self._next_grn_id(),
                po_id=po.po_id,
                vendor_id=vendor.vendor_id,
                receipt_date=self._random_date(po.po_date, po.po_date + timedelta(days=30)),
                line_items=lines,
                status=self.rng.choices(list(GRNStatus), weights=[0.7, 0.2, 0.1])[0],
            )
            self.goods_receipts.append(grn)
        return self.goods_receipts

    def _create_clean_invoice(self, po: PurchaseOrder, grn: GoodsReceipt | None, vendor: Vendor) -> Invoice:
        lines = []
        for po_line in po.line_items:
            qty = po_line.quantity
            if grn:
                grn_lines = [g for g in grn.line_items if g.po_line_id == po_line.line_id]
                if grn_lines:
                    qty = grn_lines[0].quantity_received

            line = InvoiceLine(
                line_id=self._next_line_id(),
                description=po_line.description,
                po_line_id=po_line.line_id,
                quantity=qty,
                unit_price=po_line.unit_price,
                discount=po_line.discount,
                tax_rate=po_line.tax_rate,
            )
            lines.append(line)

        subtotal = sum(l.line_total() for l in lines)
        tax = sum(l.line_tax() for l in lines)
        total = subtotal + tax

        return Invoice(
            invoice_id=self._next_invoice_id(),
            vendor_id=vendor.vendor_id,
            invoice_number=f"INV-{self._invoice_id_seq:06d}",
            po_number=po.po_number,
            invoice_date=self._random_date(po.po_date, po.po_date + timedelta(days=60)),
            due_date=self._random_date(po.po_date + timedelta(days=15), po.po_date + timedelta(days=90)),
            currency=vendor.currency,
            subtotal=self._quantize(subtotal),
            tax=self._quantize(tax),
            total=self._quantize(total),
            discount=Decimal("0"),
            line_items=lines,
        )

    def _recalc_invoice_totals(self, invoice: Invoice):
        subtotal = sum(l.line_total() for l in invoice.line_items)
        tax = sum(l.line_tax() for l in invoice.line_items)
        invoice.subtotal = self._quantize(subtotal)
        invoice.tax = self._quantize(tax)
        invoice.total = self._quantize(subtotal + tax - invoice.discount)

    def _inject_vendor_mismatch(self, invoice: Invoice, vendor: Vendor) -> dict:
        other_vendors = [v for v in self.vendors if v.vendor_id != vendor.vendor_id]
        if not other_vendors:
            return {}
        new_vendor = self.rng.choice(other_vendors)
        details = {"injected": True, "code": ExceptionCode.VENDOR_MISMATCH.value, "original_vendor_id": vendor.vendor_id, "injected_vendor_id": new_vendor.vendor_id}
        invoice.vendor_id = new_vendor.vendor_id
        return details

    def _inject_po_mismatch(self, invoice: Invoice, vendor: Vendor) -> dict:
        if self.rng.random() < 0.5:
            invoice.po_number = f"PO-INVALID-{self.rng.randint(100000, 999999)}"
            details = {"injected": True, "code": ExceptionCode.PO_MISMATCH.value, "type": "invalid_po_number"}
        else:
            other_pos = [p for p in self.purchase_orders if p.vendor_id != vendor.vendor_id]
            if other_pos:
                invoice.po_number = self.rng.choice(other_pos).po_number
                details = {"injected": True, "code": ExceptionCode.PO_MISMATCH.value, "type": "wrong_vendor_po"}
            else:
                invoice.po_number = f"PO-INVALID-{self.rng.randint(100000, 999999)}"
                details = {"injected": True, "code": ExceptionCode.PO_MISMATCH.value, "type": "invalid_po_number"}
        return details

    def _inject_amount_mismatch(self, invoice: Invoice) -> dict:
        pct_change = self._random_decimal(0.05, 0.5)
        if self.rng.random() < 0.5:
            invoice.total = self._quantize(invoice.total * (Decimal("1") + pct_change))
        else:
            invoice.total = self._quantize(invoice.total * (Decimal("1") - pct_change))
        invoice.subtotal = invoice.total - invoice.tax + invoice.discount
        details = {"injected": True, "code": ExceptionCode.AMOUNT_MISMATCH.value, "type": "total_mismatch"}
        return details

    def _inject_grn_mismatch(self, invoice: Invoice, grn: GoodsReceipt) -> dict:
        if not grn or not grn.line_items:
            return {}
        grn_line = self.rng.choice(grn.line_items)
        for inv_line in invoice.line_items:
            if inv_line.po_line_id == grn_line.po_line_id:
                inv_line.quantity = (grn_line.quantity_received * Decimal(str(self._random_decimal(1.1, 2.0)))).quantize(Decimal("0.01"))
                self._recalc_invoice_totals(invoice)
                details = {
                    "injected": True,
                    "code": ExceptionCode.GRN_MISMATCH.value,
                    "po_line_id": grn_line.po_line_id,
                    "grn_quantity": str(grn_line.quantity_received),
                    "invoice_quantity": str(inv_line.quantity),
                }
                return details
        return {}

    def _inject_duplicate_invoice(self) -> dict:
        return {"injected": True, "code": ExceptionCode.DUPLICATE_INVOICE.value, "type": "intentional_duplicate"}

    def _inject_tax_error(self, invoice: Invoice) -> dict:
        error_pct = self._random_decimal(0.02, 0.2)
        if self.rng.random() < 0.5:
            invoice.tax = self._quantize(invoice.tax * (Decimal("1") + error_pct))
        else:
            invoice.tax = self._quantize(invoice.tax * (Decimal("1") - error_pct))
        invoice.total = self._quantize(invoice.subtotal + invoice.tax - invoice.discount)
        details = {"injected": True, "code": ExceptionCode.TAX_ERROR.value, "type": "tax_calculation_error"}
        return details

    def _inject_currency_mismatch(self, invoice: Invoice, vendor: Vendor) -> dict:
        other_currencies = [c for c in Currency if c != vendor.currency]
        if not other_currencies:
            return {}
        invoice.currency = self.rng.choice(other_currencies)
        details = {"injected": True, "code": ExceptionCode.CURRENCY_MISMATCH.value, "original_currency": vendor.currency.value, "injected_currency": invoice.currency.value}
        return details

    def _inject_line_item_mismatch(self, invoice: Invoice, po: PurchaseOrder) -> dict:
        if not invoice.line_items or not po.line_items:
            return {}
        inv_line = self.rng.choice(invoice.line_items)
        po_line = self.rng.choice(po.line_items)
        inv_line.unit_price = self._quantize(po_line.unit_price * Decimal(str(self._random_decimal(0.5, 2.0))))
        self._recalc_invoice_totals(invoice)
        details = {
            "injected": True,
            "code": ExceptionCode.LINE_ITEM_MISMATCH.value,
            "po_line_id": po_line.line_id,
            "expected_price": str(po_line.unit_price),
            "invoiced_price": str(inv_line.unit_price),
        }
        return details

    def _inject_discount_error(self, invoice: Invoice) -> dict:
        if not invoice.line_items:
            return {}
        inv_line = self.rng.choice(invoice.line_items)
        max_discount = inv_line.quantity * inv_line.unit_price * Decimal("0.5")
        inv_line.discount = self._quantize(self._random_decimal(float(max_discount * Decimal("0.2")), float(max_discount)))
        self._recalc_invoice_totals(invoice)
        details = {"injected": True, "code": ExceptionCode.DISCOUNT_ERROR.value, "line_id": inv_line.line_id, "discount": str(inv_line.discount)}
        return details

    def _inject_credit_issue(self, vendor: Vendor) -> dict:
        vendor.credit_status = CreditStatus.HOLD
        details = {"injected": True, "code": ExceptionCode.CREDIT_ISSUE.value, "credit_status": CreditStatus.HOLD.value}
        return details

    _INJECTORS = {
        ExceptionCode.VENDOR_MISMATCH: "_inject_vendor_mismatch",
        ExceptionCode.PO_MISMATCH: "_inject_po_mismatch",
        ExceptionCode.AMOUNT_MISMATCH: "_inject_amount_mismatch",
        ExceptionCode.GRN_MISMATCH: "_inject_grn_mismatch",
        ExceptionCode.DUPLICATE_INVOICE: "_inject_duplicate_invoice",
        ExceptionCode.TAX_ERROR: "_inject_tax_error",
        ExceptionCode.CURRENCY_MISMATCH: "_inject_currency_mismatch",
        ExceptionCode.LINE_ITEM_MISMATCH: "_inject_line_item_mismatch",
        ExceptionCode.DISCOUNT_ERROR: "_inject_discount_error",
        ExceptionCode.CREDIT_ISSUE: "_inject_credit_issue",
    }

    def generate_invoices(self, count: int) -> list[Invoice]:
        if not self.purchase_orders:
            raise ValueError("Must generate POs first")

        pos_with_grn = []
        for po in self.purchase_orders:
            grns = [g for g in self.goods_receipts if g.po_id == po.po_id]
            if grns:
                pos_with_grn.append((po, self.rng.choice(grns)))
            else:
                pos_with_grn.append((po, None))

        if not pos_with_grn:
            pos_with_grn = [(po, None) for po in self.purchase_orders]

        min_per_exception = 10
        exception_codes = list(ExceptionCode)
        all_exceptions_needed = {code: min_per_exception for code in exception_codes}

        invoices_generated = 0

        while invoices_generated < count:
            remaining = count - invoices_generated
            still_needed = sum(1 for v in all_exceptions_needed.values() if v > 0)

            if still_needed > 0 and remaining > still_needed:
                available_exceptions = [c for c, v in all_exceptions_needed.items() if v > 0]
                exc_code = self.rng.choice(available_exceptions)
                all_exceptions_needed[exc_code] -= 1
                inject_exception = True
            elif still_needed > 0:
                available_exceptions = [c for c, v in all_exceptions_needed.items() if v > 0]
                exc_code = self.rng.choice(available_exceptions)
                all_exceptions_needed[exc_code] -= 1
                inject_exception = True
            else:
                inject_exception = self.rng.random() < 0.3
                if inject_exception:
                    exc_code = self.rng.choice(exception_codes)
                else:
                    exc_code = None

            po, grn = self.rng.choice(pos_with_grn)
            vendor = next(v for v in self.vendors if v.vendor_id == po.vendor_id)

            if exc_code == ExceptionCode.DUPLICATE_INVOICE:
                if not self._clean_invoices:
                    inject_exception = False
                    exc_code = None
                else:
                    original = self.rng.choice(self._clean_invoices)
                    dup_lines = []
                    for l in original.line_items:
                        dup_lines.append(InvoiceLine(
                            line_id=self._next_line_id(),
                            description=l.description,
                            po_line_id=l.po_line_id,
                            quantity=l.quantity,
                            unit_price=l.unit_price,
                            discount=l.discount,
                            tax_rate=l.tax_rate,
                        ))
                    dup = Invoice(
                        invoice_id=self._next_invoice_id(),
                        vendor_id=original.vendor_id,
                        invoice_number=original.invoice_number,
                        po_number=original.po_number,
                        invoice_date=original.invoice_date,
                        due_date=original.due_date,
                        currency=original.currency,
                        subtotal=original.subtotal,
                        tax=original.tax,
                        total=original.total,
                        discount=original.discount,
                        line_items=dup_lines,
                    )
                    self.invoices.append(dup)
                    self.ground_truth.append(GroundTruth(
                        invoice_id=dup.invoice_id,
                        expected_exceptions=[ExceptionCode.DUPLICATE_INVOICE],
                        expected_decision="REVIEW",
                        injected_exceptions={"DUPLICATE_INVOICE": {"injected": True, "original_invoice_id": original.invoice_id}},
                    ))
                    invoices_generated += 1
                    continue

            clean_invoice = self._create_clean_invoice(po, grn, vendor)
            injected_exceptions = {}
            expected_exceptions = []

            if inject_exception and exc_code:
                injector_method = getattr(self, self._INJECTORS[exc_code])
                if exc_code in (ExceptionCode.GRN_MISMATCH,):
                    details = injector_method(clean_invoice, grn)
                elif exc_code in (ExceptionCode.VENDOR_MISMATCH, ExceptionCode.PO_MISMATCH, ExceptionCode.CURRENCY_MISMATCH):
                    details = injector_method(clean_invoice, vendor)
                elif exc_code in (ExceptionCode.LINE_ITEM_MISMATCH,):
                    details = injector_method(clean_invoice, po)
                elif exc_code in (ExceptionCode.CREDIT_ISSUE,):
                    details = injector_method(vendor)
                else:
                    details = injector_method(clean_invoice)

                if details:
                    injected_exceptions[exc_code.value] = details
                    expected_exceptions.append(exc_code)

            self.invoices.append(clean_invoice)
            self.ground_truth.append(GroundTruth(
                invoice_id=clean_invoice.invoice_id,
                expected_exceptions=expected_exceptions,
                expected_decision="REVIEW" if expected_exceptions else "AUTO_APPROVE",
                injected_exceptions=injected_exceptions,
            ))
            if not expected_exceptions:
                self._clean_invoices.append(clean_invoice)
            invoices_generated += 1

        return self.invoices

    def generate_all(self, vendor_count: int = 20, po_count: int = 50,
                     grn_count: int = 30, invoice_count: int = 200) -> dict:
        self.generate_vendors(vendor_count)
        self.generate_purchase_orders(po_count)
        self.generate_goods_receipts(grn_count)
        self.generate_invoices(invoice_count)
        return self.export()

    def export(self) -> dict:
        return {
            "vendors": [v.model_dump(mode="json") for v in self.vendors],
            "purchase_orders": [p.model_dump(mode="json") for p in self.purchase_orders],
            "goods_receipts": [g.model_dump(mode="json") for g in self.goods_receipts],
            "invoices": [i.model_dump(mode="json") for i in self.invoices],
            "ground_truth": [g.model_dump(mode="json") for g in self.ground_truth],
        }

    def save(self, base_dir: Path | None = None):
        if base_dir is None:
            base_dir = self.settings.data_dir

        bootstrap_dir = base_dir / "bootstrap"
        ground_truth_dir = base_dir / "ground_truth"
        bootstrap_dir.mkdir(parents=True, exist_ok=True)
        ground_truth_dir.mkdir(parents=True, exist_ok=True)

        data = self.export()

        for key, items in data.items():
            if key == "ground_truth":
                continue
            file_path = bootstrap_dir / f"{key}.json"
            with file_path.open("w") as f:
                json.dump(items, f, indent=2, default=str)

        gt_path = ground_truth_dir / "ground_truth.json"
        with gt_path.open("w") as f:
            json.dump(data["ground_truth"], f, indent=2, default=str)

        print(f"Saved {len(self.vendors)} vendors")
        print(f"Saved {len(self.purchase_orders)} purchase orders")
        print(f"Saved {len(self.goods_receipts)} goods receipts")
        print(f"Saved {len(self.invoices)} invoices")
        print(f"Saved {len(self.ground_truth)} ground truth records")


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic AP data")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument("--vendors", type=int, default=20, help="Number of vendors")
    parser.add_argument("--pos", type=int, default=50, help="Number of purchase orders")
    parser.add_argument("--grns", type=int, default=30, help="Number of goods receipts")
    parser.add_argument("--invoices", type=int, default=200, help="Number of invoices")
    parser.add_argument("--output-dir", type=str, help="Output directory (default: apx/data/datasets)")

    args = parser.parse_args()

    generator = SyntheticGenerator(seed=args.seed)
    generator.generate_all(
        vendor_count=args.vendors,
        po_count=args.pos,
        grn_count=args.grns,
        invoice_count=args.invoices,
    )

    if args.output_dir:
        generator.save(Path(args.output_dir))
    else:
        generator.save()


if __name__ == "__main__":
    main()