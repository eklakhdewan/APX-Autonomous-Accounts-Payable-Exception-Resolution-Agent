# APX - Autonomous Accounts Payable Exception Resolution Agent

Phase 1 Implementation: Deterministic validation foundation.

## Quick Start

```bash
# Install dependencies
pip install -e .

# Generate synthetic dataset (bootstrap tier)
python -m apx.data.generate_synthetic --seed 42

# Run all tests
python -m pytest apx/tests -v
```

## Commands

### Generate Data
```bash
# Default bootstrap tier (20 vendors, 50 POs, 30 GRNs, 200 invoices)
python -m apx.data.generate_synthetic --seed 42

# Custom counts
python -m apx.data.generate_synthetic --vendors 35 --pos 100 --grns 75 --invoices 500 --seed 42

# Custom output directory
python -m apx.data.generate_synthetic --seed 42 --output-dir /path/to/output
```

### Run Tests
```bash
# All tests
python -m pytest apx/tests -v

# Specific test modules
python -m pytest apx/tests/test_validator.py -v
python -m pytest apx/tests/test_data_integrity.py -v
python -m pytest apx/tests/test_data_generator.py -v
python -m pytest apx/tests/test_schemas.py -v
```

## Project Structure

```
apx/
├── config/
│   ├── __init__.py
│   ├── settings.py          # Configuration loader
│   └── risk_policy.yaml     # Risk policy configuration
├── data/
│   ├── __init__.py
│   ├── schemas.py           # Canonical domain schemas (Pydantic)
│   ├── generate_synthetic.py # Synthetic dataset generator
│   └── datasets/
│       ├── bootstrap/       # Generated bootstrap data
│       └── ground_truth/    # Ground truth for validation
├── intelligence/
│   ├── __init__.py
│   └── validator.py         # Deterministic R1-R10 validator
├── exceptions/
│   ├── __init__.py
│   ├── models.py            # Exception models
│   └── taxonomy.py          # Exception taxonomy & codes
��── tests/
    ├── test_schemas.py
    ├── test_data_generator.py
    ├── test_validator.py
    └── test_data_integrity.py
```

## Validation Rules (R1-R10)

| Code | Rule | Description |
|------|------|-------------|
| R1 | VENDOR_MISMATCH | Invoice vendor inconsistent with PO/vendor |
| R2 | PO_MISMATCH | Missing/invalid PO reference or wrong vendor |
| R3 | AMOUNT_MISMATCH | Invoice total vs PO total (with tolerance) |
| R4 | GRN_MISMATCH | Invoiced qty > received qty |
| R5 | DUPLICATE_INVOICE | Duplicate vendor + invoice number |
| R6 | TAX_ERROR | Tax calculation mismatch |
| R7 | CURRENCY_MISMATCH | Invoice/PO/vendor currency inconsistency |
| R8 | LINE_ITEM_MISMATCH | Line item price/qty vs PO |
| R9 | DISCOUNT_ERROR | Discount vs PO/business data |
| R10 | CREDIT_ISSUE | Vendor credit status HOLD/SUSPENDED/BLOCKED |

## Reproducibility

Same seed produces identical logical data:
```bash
python -m apx.data.generate_synthetic --seed 42
python -m apx.data.generate_synthetic --seed 42  # Identical output
```

## Configuration

Risk policy in `apx/config/risk_policy.yaml`:
- Amount/severity/confidence/evidence/historical risk weights
- Tolerance thresholds for amount, tax, quantity, discount
- Auto-resolve and always-escalate rules

## Phase 1 Acceptance Criteria

- [x] Repository structure exists
- [x] Python project runs cleanly
- [x] `risk_policy.yaml` exists and validates
- [x] Canonical domain schemas exist
- [x] 20 vendors / 50 POs / 30 GRNs / 200 invoices generated
- [x] Records linked coherently
- [x] Ground truth generated
- [x] R1-R10 implemented
- [x] Validator has zero LLM dependencies
- [x] Validator is deterministic
- [x] Duplicate detection deterministic
- [x] Monetary comparisons use Decimal
- [x] Data integrity tests pass
- [x] Validator tests pass
- [x] Boundary cases tested
- [x] Multiple-exception cases tested
- [x] Same seed produces reproducible results
- [x] No future-phase components implemented
- [x] README explains usage