"""Dump the professional car-racing retirement survival table to raw float64 files.

Second real-data source for this benchmark, alongside `prep_drivestats.py`. Different
domain (mechanical/athletic competition rather than data-center hardware), different
shape (heavily used at moderate n, 10% event rate, versus Drive Stats' huge n and <1%
event rate), same reason for existing: real, current (spans through the present season,
via a locally-archived corpus fetched by a separate, already-shipped ingest pipeline --
see `build_motorsport_survival.py`'s docstring for the retirement rule and why the raw
per-lap `retired` flag was not usable directly).

Usage: python3 prep_motorsport.py <summary_csv> [output_dir]
  (default output_dir: $SURV_DATA or /tmp/survival_lifelines_data)
"""
import os
import sys

import numpy as np
import pandas as pd

COVARIATES = ["grid_position", "prior_races"]


def dump_f64(path: str, values) -> None:
    np.asarray(values, dtype=np.float64).tofile(path)


def main() -> None:
    summary_csv = sys.argv[1] if len(sys.argv) > 1 else "/tmp/motorsport_survival.csv"
    out = sys.argv[2] if len(sys.argv) > 2 else os.environ.get(
        "SURV_DATA", "/tmp/survival_lifelines_data"
    )
    os.makedirs(out, exist_ok=True)

    df = pd.read_csv(summary_csv)
    n_all = len(df)

    dump_f64(os.path.join(out, "motorsport_laps.f64"), df["laps_completed"].to_numpy())
    dump_f64(os.path.join(out, "motorsport_retired.f64"), df["retired"].to_numpy())

    complete = df.dropna(subset=COVARIATES).reset_index(drop=True)
    n_complete = len(complete)
    dump_f64(os.path.join(out, "motorsport_cox_laps.f64"), complete["laps_completed"].to_numpy())
    dump_f64(os.path.join(out, "motorsport_cox_retired.f64"), complete["retired"].to_numpy())
    for col in COVARIATES:
        dump_f64(os.path.join(out, f"motorsport_cox_{col}.f64"), complete[col].to_numpy())

    print(f"KM:  wrote {n_all} car-races, event rate {df['retired'].mean():.4f}")
    print(f"Cox: wrote {n_complete} car-races with complete covariates "
          f"({n_complete / n_all:.1%}), event rate {complete['retired'].mean():.4f}")


if __name__ == "__main__":
    main()
