"""Dump a real, current hard-drive-fleet survival dataset to raw float64 files.

Why this exists: the Rossi recidivism dataset (`prep_rossi.py`) is real but is a 1980
study -- a fair complaint about a "real data" claim on a benchmark published in 2026.
This script builds the real-data cells from Backblaze's own Drive Stats dataset instead:
daily SMART-attribute snapshots of every hard drive in Backblaze's production data
centers, published quarterly and continuously updated (https://www.backblaze.com/cloud-storage/resources/hard-drive-test-data).
This uses the Q4 2025 release (2025-10-01 through 2025-12-31) -- the most recent full
quarter published as of this writing.

The data is genuinely survival-shaped with no reframing needed: each drive is observed
from the day it enters the fleet (or the start of the quarter, if already running) until
either it fails (`failure=1` on its last observed day -- an event) or the quarter ends
with the drive still running (censored). That is exactly Kaplan-Meier's and Cox's input
shape, not something bent to fit.

Covariates for the Cox cells start from the raw SMART attributes Backblaze's own
reliability team has publicly identified as the strongest failure predictors --
reallocated sectors (5), reported uncorrectable errors (187), current pending sector
count (197), offline uncorrectable sector count (198) -- plus power-on hours (9) as an
age covariate. **198 is dropped**: checked directly on this quarter's data, its
log1p-transformed values correlate 1.000 with 197 (this fleet's firmware reports the two
identically), which makes the design matrix exactly singular -- lifelines' own
Newton-Raphson raises `ConvergenceError: ... Matrix is singular` on the 5-covariate
version, so this is a measured property of the data, not a modeling choice made for
convenience. The remaining four are real, distinct, and taken at the first day each
drive is observed in the quarter (a real baseline-covariate Cox setup, not covariates
re-measured over time).

This script does NOT re-derive the per-drive table from the raw daily CSVs (92 files,
~12GB uncompressed) -- that happens once, out of band, in `build_drivestats_summary.py`
(see that file's docstring), which writes a compact per-drive CSV. This script's only job
is the same one `prep_rossi.py` does for Rossi:
read a real table once and write each column as raw little-endian float64, so
`survival_h2h.mojo` (no pandas) and `lifelines_refs.py` (has pandas) read bit-identical
bytes instead of two loaders that are supposed to agree.

Usage: python3 prep_drivestats.py <summary_csv> [output_dir]
  (default output_dir: $SURV_DATA or /tmp/survival_lifelines_data)
"""
import os
import sys

import numpy as np
import pandas as pd

COVARIATES = ["smart_9_raw", "smart_5_raw", "smart_187_raw", "smart_197_raw"]


def dump_f64(path: str, values) -> None:
    np.asarray(values, dtype=np.float64).tofile(path)


def main() -> None:
    summary_csv = sys.argv[1] if len(sys.argv) > 1 else "/tmp/backblaze_q4_2025/drivestats_summary.csv"
    out = sys.argv[2] if len(sys.argv) > 2 else os.environ.get(
        "SURV_DATA", "/tmp/survival_lifelines_data"
    )
    os.makedirs(out, exist_ok=True)

    df = pd.read_csv(summary_csv)
    n_all = len(df)

    # KM uses every drive: no covariates needed, so no reason to drop a drive whose
    # SMART attributes happen to be missing.
    dump_f64(os.path.join(out, "drivestats_days.f64"), df["days"].to_numpy())
    dump_f64(os.path.join(out, "drivestats_failure.f64"), df["failure"].to_numpy())

    # Cox needs complete covariates. Some models (mostly SATA SSDs, a minority of the
    # fleet) do not report the classic-HDD SMART IDs at all -- dropped here, not
    # imputed, the same "refuse rather than guess" rule the kernel itself applies to
    # nulls elsewhere in this codebase.
    complete = df.dropna(subset=COVARIATES).reset_index(drop=True)
    n_complete = len(complete)
    dump_f64(os.path.join(out, "drivestats_cox_days.f64"), complete["days"].to_numpy())
    dump_f64(os.path.join(out, "drivestats_cox_failure.f64"), complete["failure"].to_numpy())
    for col in COVARIATES:
        # Raw SMART counts are heavy-tailed (the overwhelming majority of healthy drives
        # read exactly 0 reallocated/pending/uncorrectable sectors, with a long tail of
        # large counts on drives approaching failure). Fit on log1p(raw), the standard
        # transform for this exact family of counters: fit UNTRANSFORMED, both `cox_fit`
        # and lifelines' Newton-Raphson fail to converge (quasi-complete separation --
        # checked directly, not assumed: lifelines raises its own ConvergenceWarning on
        # the raw covariates, and `cox_fit` returns SA_ERR_SEPARATION). log1p is applied
        # identically before either arm sees the data, so both are fit on the same
        # transformed values.
        dump_f64(os.path.join(out, f"drivestats_cox_{col}.f64"), np.log1p(complete[col].to_numpy()))

    with open(os.path.join(out, "drivestats_meta.txt"), "w") as fh:
        fh.write(f"n_km {n_all}\n")
        fh.write(f"n_cox {n_complete}\n")
        fh.write(f"cox_covariates {','.join(COVARIATES)}\n")

    print(f"KM:  wrote {n_all} drives, event rate {df['failure'].mean():.4f}")
    print(f"Cox: wrote {n_complete} drives with complete covariates "
          f"({n_complete / n_all:.1%} of fleet), event rate {complete['failure'].mean():.4f}")


if __name__ == "__main__":
    main()
