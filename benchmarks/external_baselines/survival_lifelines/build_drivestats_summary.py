"""Turn a Backblaze Drive Stats quarterly release into a per-drive survival table.

Backblaze publishes one daily SMART-attribute snapshot per drive, per quarter, as a ZIP
of ~90 daily CSVs (https://www.backblaze.com/cloud-storage/resources/hard-drive-test-data
-- "Q4 2025" is the current release as of this writing, 12.17 GB uncompressed across 92
files, 30.9M rows, 341,664 distinct drives). This script is the one-time transform from
that raw per-day-per-drive form into the one-row-per-drive form survival analysis needs:
how long each drive was observed, and whether that observation ended in failure
(`failure=1` on its last row -- an event) or the quarter simply ending with the drive
still running (censored).

This is NOT run automatically by `drive_survival.py` -- unlike Rossi, which lifelines
already bundles as an installed package, Drive Stats is an ~1.2 GB external download,
and re-downloading or re-scanning 12 GB of CSV on every benchmark invocation would make
the benchmark itself slow to reproduce for no reason: this transform's OUTPUT (a compact
per-drive CSV, a few tens of MB) is what actually needs to exist for a run, and once
built it does not change until a newer quarter replaces it.

Usage:
    curl -o data_Q4_2025.zip https://f001.backblazeb2.com/file/Backblaze-Hard-Drive-Data/data_Q4_2025.zip
    python3 build_drivestats_summary.py data_Q4_2025.zip drivestats_summary.csv
    python3 prep_drivestats.py drivestats_summary.csv   # writes the raw f64 dump prep_rossi.py's siblings use
"""
import sys
import zipfile

import numpy as np
import pandas as pd

# The five raw SMART attributes Backblaze's own reliability team has publicly identified
# as the strongest predictors of failure (reallocated sectors, reported uncorrectable,
# current pending sector, offline uncorrectable), plus power-on hours as an age covariate.
COVARIATES = ["smart_9_raw", "smart_5_raw", "smart_187_raw", "smart_197_raw", "smart_198_raw"]
USECOLS = ["date", "serial_number", "failure"] + COVARIATES


def main() -> None:
    zip_path = sys.argv[1] if len(sys.argv) > 1 else "data_Q4_2025.zip"
    out_csv = sys.argv[2] if len(sys.argv) > 2 else "drivestats_summary.csv"

    zf = zipfile.ZipFile(zip_path)
    names = sorted(n for n in zf.namelist() if n.endswith(".csv"))
    print(f"{len(names)} daily files in {zip_path}", file=sys.stderr)

    frames = []
    for i, name in enumerate(names):
        with zf.open(name) as fh:
            df = pd.read_csv(
                fh, usecols=USECOLS,
                dtype={"serial_number": "string", "failure": "int8"},
            )
        frames.append(df)
        if (i + 1) % 20 == 0 or i == len(names) - 1:
            print(f"  read {i + 1}/{len(names)}  ({name})", file=sys.stderr)

    all_df = pd.concat(frames, ignore_index=True)
    del frames
    print(f"total rows: {len(all_df):,}  unique drives: {all_df['serial_number'].nunique():,}",
          file=sys.stderr)

    all_df["date"] = pd.to_datetime(all_df["date"])
    all_df.sort_values(["serial_number", "date"], inplace=True)

    grouped = all_df.groupby("serial_number", sort=False)
    first = grouped.first()
    summary = first[COVARIATES].copy()
    summary["first_date"] = first["date"]
    summary["last_date"] = grouped["date"].last()
    summary["failure"] = grouped["failure"].max()
    summary["days"] = (summary["last_date"] - summary["first_date"]).dt.days + 1

    n_events = int(summary["failure"].sum())
    print(
        f"drives: {len(summary):,}  failures(events): {n_events:,}  "
        f"censored: {len(summary) - n_events:,}  "
        f"censor_rate: {(len(summary) - n_events) / len(summary):.4f}",
        file=sys.stderr,
    )
    complete = summary.dropna(subset=COVARIATES)
    print(
        f"drives with all {len(COVARIATES)} covariates present at first sight: "
        f"{len(complete):,} ({len(complete) / len(summary):.1%}), "
        f"of those failures: {int(complete['failure'].sum()):,}",
        file=sys.stderr,
    )

    summary.reset_index().to_csv(out_csv, index=False)
    print(f"wrote {out_csv}", file=sys.stderr)


if __name__ == "__main__":
    main()
