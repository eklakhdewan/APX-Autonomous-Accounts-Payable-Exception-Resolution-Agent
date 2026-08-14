#!/usr/bin/env python3
"""Run validator against generated dataset and report detection performance."""

import json
from decimal import Decimal
from collections import Counter

from apx.data.schemas import (
    Vendor, PurchaseOrder, PurchaseOrderLine,
    GoodsReceipt, GoodsReceiptLine, Invoice, InvoiceLine,
    Currency, CreditStatus, VendorStatus, POStatus, GRNStatus, ExceptionCode, GroundTruth,
    ExceptionSeverity, ValidationStatus
)
from apx.intelligence.validator import InvoiceValidator


def parse_decimal(value):
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    return Decimal(str(value))


def parse_date(value):
    if isinstance(value, str):
        return value
    return value


def load_model(model_class, data):
    if isinstance(data, list):
        return [load_model(model_class, item) for item in data]
    
    parsed = {}
    for k, v in data.items():
        if k in ('subtotal', 'tax', 'total', 'discount', 'unit_price', 'quantity', 
                 'quantity_received', 'tax_rate', 'amount_percentage', 'amount_absolute',
                 'tax_percentage', 'quantity_percentage', 'discount_percentage',
                 'low_threshold', 'medium_threshold', 'high_threshold', 'weight',
                 'high_threshold', 'medium_threshold', 'low_threshold',
                 'min_success_rate', 'auto_resolve_max', 'review_required_min',
                 'escalate_min', 'auto_resolve_min', 'human_review_max',
                 'auto_resolve_min', 'human_review_min', 'auto_resolve_min'):
            parsed[k] = parse_decimal(v)
        elif k in ('po_date', 'receipt_date', 'invoice_date', 'due_date'):
            parsed[k] = parse_date(v)
        elif k in ('currency',):
            parsed[k] = Currency(v)
        elif k in ('credit_status',):
            parsed[k] = CreditStatus(v)
        elif k in ('status',):
            if model_class == Vendor:
                parsed[k] = VendorStatus(v)
            elif model_class == PurchaseOrder:
                parsed[k] = POStatus(v)
            elif model_class == GoodsReceipt:
                parsed[k] = GRNStatus(v)
            else:
                parsed[k] = v
        elif k in ('severity',):
            parsed[k] = ExceptionSeverity(v)
        elif k in ('exception_code',):
            parsed[k] = ExceptionCode(v)
        elif k in ('validation_status',):
            parsed[k] = ValidationStatus(v)
        elif k == 'line_items':
            if model_class == PurchaseOrder:
                parsed[k] = [load_model(PurchaseOrderLine, item) for item in v]
            elif model_class == GoodsReceipt:
                parsed[k] = [load_model(GoodsReceiptLine, item) for item in v]
            elif model_class == Invoice:
                parsed[k] = [load_model(InvoiceLine, item) for item in v]
            else:
                parsed[k] = v
        else:
            parsed[k] = v
    
    return model_class.model_construct(**parsed)


def main():
    # Load generated data
    with open('apx/data/datasets/bootstrap/vendors.json') as f:
        vendors_data = json.load(f)
    with open('apx/data/datasets/bootstrap/purchase_orders.json') as f:
        pos_data = json.load(f)
    with open('apx/data/datasets/bootstrap/goods_receipts.json') as f:
        grns_data = json.load(f)
    with open('apx/data/datasets/bootstrap/invoices.json') as f:
        invoices_data = json.load(f)
    with open('apx/data/datasets/ground_truth/ground_truth.json') as f:
        gt_data = json.load(f)

    # Build lookup dicts
    vendors = {v['vendor_id']: load_model(Vendor, v) for v in vendors_data}
    pos = {p['po_id']: load_model(PurchaseOrder, p) for p in pos_data}
    pos_by_number = {p['po_number']: load_model(PurchaseOrder, p) for p in pos_data if p.get('po_number')}
    grns_by_po = {}
    for g in grns_data:
        if g['po_id'] not in grns_by_po:
            grns_by_po[g['po_id']] = []
        grns_by_po[g['po_id']].append(load_model(GoodsReceipt, g))

    gt_by_inv = {g['invoice_id']: g for g in gt_data}

    # Run validator
    validator = InvoiceValidator()
    validator.reset_seen_invoices()
    results = []

    for inv_data in invoices_data:
        invoice = load_model(Invoice, inv_data)
        po = pos_by_number.get(invoice.po_number) if invoice.po_number else None
        grn = grns_by_po.get(po.po_id, [None])[0] if po else None
        vendor = vendors.get(invoice.vendor_id)

        if not vendor:
            continue

        report = validator.validate_invoice(invoice, po, grn, vendor)
        expected = gt_by_inv.get(invoice.invoice_id, {}).get('expected_exceptions', [])
        detected = [e.exception_code.value for e in report.exceptions]

        results.append({
            'invoice_id': invoice.invoice_id,
            'expected': expected,
            'detected': detected,
        })

    # Calculate metrics
    total_invoices = len(results)
    invoices_with_exceptions = sum(1 for r in results if r['expected'])
    invoices_without_exceptions = total_invoices - invoices_with_exceptions

    all_codes = [c.value for c in ExceptionCode]
    tp = Counter()
    fp = Counter()
    fn = Counter()
    tn = Counter()

    for r in results:
        expected_set = set(r['expected'])
        detected_set = set(r['detected'])
        for code in all_codes:
            in_expected = code in expected_set
            in_detected = code in detected_set
            if in_expected and in_detected:
                tp[code] += 1
            elif not in_expected and in_detected:
                fp[code] += 1
            elif in_expected and not in_detected:
                fn[code] += 1
            else:
                tn[code] += 1

    print('=== VALIDATOR DETECTION PERFORMANCE ===')
    print(f'Total invoices: {total_invoices}')
    print(f'Invoices with exceptions (ground truth): {invoices_with_exceptions}')
    print(f'Invoices without exceptions (ground truth): {invoices_without_exceptions}')
    print()
    print('Per-rule detection:')
    print(f'{"Code":<30} {"TP":>4} {"FP":>4} {"FN":>4} {"Precision":>10} {"Recall":>8}')
    print('-' * 70)
    for code in all_codes:
        t = tp[code]
        f = fp[code]
        n = fn[code]
        prec = t / (t + f) if (t + f) > 0 else 1.0
        rec = t / (t + n) if (t + n) > 0 else 1.0
        print(f'{code:<30} {t:>4} {f:>4} {n:>4} {prec:>10.2%} {rec:>8.2%}')

    total_tp = sum(tp.values())
    total_fp = sum(fp.values())
    total_fn = sum(fn.values())
    overall_prec = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 1.0
    overall_rec = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 1.0
    overall_f1 = 2 * overall_prec * overall_rec / (overall_prec + overall_rec) if (overall_prec + overall_rec) > 0 else 1.0

    print()
    print('Overall:')
    print(f'  Precision: {overall_prec:.2%}')
    print(f'  Recall:    {overall_rec:.2%}')
    print(f'  F1:        {overall_f1:.2%}')
    print(f'  False Positives: {total_fp}')
    print(f'  False Negatives: {total_fn}')

    exc_dist = Counter()
    for r in results:
        for e in r['expected']:
            exc_dist[e] += 1
    print()
    print('Exception distribution (ground truth):')
    for code, count in exc_dist.most_common():
        print(f'  {code}: {count}')

    return results


if __name__ == '__main__':
    main()