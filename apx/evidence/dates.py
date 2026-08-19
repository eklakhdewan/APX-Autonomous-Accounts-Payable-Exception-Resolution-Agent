"""Canonical temporal anchor for the APX simulated world.

The entire evidence/evaluation pipeline is anchored to ONE explicit reference
date so that evidence validity windows, evaluation labels, benchmark invoice
dates and run-time evidence validation are temporally coherent, and so that
benchmark evaluation never implicitly depends on the machine's wall-clock date.

Derivation of APX_REFERENCE_DATE (from apx/data/generate_synthetic.py):
- PO dates are generated in [2026-01-01, 2026-06-30].
- Invoice dates are generated in [po_date, po_date + 60 days].
- Therefore the latest date any benchmark invoice can exist is
  2026-06-30 + 60 days = 2026-08-29.

The benchmark temporal world is therefore defined "as of" 2026-08-29: evidence
must be current on that date to be trusted for the benchmark.
"""

from __future__ import annotations

from datetime import date

APX_REFERENCE_DATE: date = date(2026, 8, 29)
