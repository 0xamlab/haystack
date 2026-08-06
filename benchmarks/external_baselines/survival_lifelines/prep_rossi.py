"""Dump lifelines' bundled Rossi recidivism dataset to raw float64 files.

Why this exists: `survival_h2h.mojo` and `lifelines_refs.py` both need EXACTLY the same
432-row real dataset, bit for bit. Rather than trust two independent loaders (a Mojo one
that has no pandas, and a Python one that does) to agree on row order and dtype coercion,
this script loads the dataset ONCE, through the reference library's own loader
(`lifelines.datasets.load_rossi`), and writes each column as a raw little-endian float64
array (`read_f64` in `survival_h2h.mojo` reads the identical layout, copied verbatim from
`forecasting_m4_h2h.mojo`'s helper of the same name). Both consumers then read the same
bytes, so there is no cross-language re-derivation to disagree.

Rossi (Rossi, Bock and Berk 1980; "Recidivism of Felons") is the canonical real-world
teaching dataset for both Kaplan-Meier and Cox regression: it is the exact example
lifelines' own tutorial and R's `survival::rossi` use. 432 subjects, `week` = time to
arrest or end of a 52-week observation window, `arrest` = 1 if rearrested, 0 if censored
at week 52 (322 of 432 rows -- the heaviest tie in the dataset, and a real "everyone left
gets censored at the boundary" case, not a synthetic one). Seven covariates: fin, age,
race, wexp, mar, paro, prio -- the same seven the tutorial's Cox model uses.

Usage: python3 prep_rossi.py [output_dir]   (default: $SURV_DATA or /tmp/survival_lifelines_data)
"""
import os
import sys

import numpy as np
from lifelines.datasets import load_rossi

OUT = sys.argv[1] if len(sys.argv) > 1 else os.environ.get(
    "SURV_DATA", "/tmp/survival_lifelines_data"
)
COLUMNS = ["week", "arrest", "fin", "age", "race", "wexp", "mar", "paro", "prio"]


def dump_f64(path: str, values) -> None:
    arr = np.asarray(values, dtype=np.float64)
    arr.tofile(path)


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    df = load_rossi()
    assert list(df.columns) == COLUMNS, f"unexpected rossi columns: {df.columns.tolist()}"
    n = len(df)
    for col in COLUMNS:
        dump_f64(os.path.join(OUT, f"rossi_{col}.f64"), df[col].to_numpy())
    with open(os.path.join(OUT, "rossi_meta.txt"), "w") as fh:
        fh.write(f"n {n}\n")
        fh.write(f"columns {','.join(COLUMNS)}\n")
    print(f"wrote {n} rows x {len(COLUMNS)} columns to {OUT}")
    print(f"arrest (event) rate: {df['arrest'].mean():.4f}")
    print(f"censoring rate: {1.0 - df['arrest'].mean():.4f}")


if __name__ == "__main__":
    main()
