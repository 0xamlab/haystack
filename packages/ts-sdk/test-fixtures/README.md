# Synthetic test fixtures

This directory holds the CSV fixtures exercised by the TypeScript SDK test suite
(local CSV ingestion, header-alias detection, empty-source rejection, and metric
aggregation):

- `synthetic_orders_march_2026.csv` — item-level order export (6,097 data rows).
- `synthetic_financial_march_2026.csv` — payout-level export with a descriptive
  alias row preceding the real header (2,026 data rows after the SDK skips the
  alias row).
- `synthetic_store_pause_empty.csv` — header-only store-pause export (0 data
  rows; connecting it must fail with `empty_source`).

**All data is synthetic.** Store names are `Synthetic Store NNN`, payout
references are `SYNTH...` sequences, and every amount is a round number. No real
merchant, brand, or person appears in these files. The schemas (column names,
alias description row, row counts, and per-row shapes) intentionally match the
delivery-marketplace export format the SDK ingests, because the test suite
asserts on them — including exact row counts.

## Regenerating

From the repository root:

```sh
python3 scripts/generate_test_fixtures.py
```

The generator is deterministic (hard-coded seed, no time or environment
dependence); running it twice produces byte-identical files. To change the
fixtures, edit `scripts/generate_test_fixtures.py` and regenerate — do not edit
the CSVs by hand.
