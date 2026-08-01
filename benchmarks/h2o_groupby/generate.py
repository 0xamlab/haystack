"""H2O db-benchmark G1 groupby dataset, 0.5 GB tier: N=1e7 rows, K=100.

Follows the h2oai/db-benchmark _datagen spec (groupby-datagen.R):
  id1,id2: K distinct;  id3: N/K distinct;  id4,id5: K distinct ints;
  id6: N/K distinct ints;  v1: 1..5;  v2: 1..15;  v3: uniform(0,100) rounded to 6.
NAs=0, sorted=0. Categorical id1..id3 are emitted as integer dictionary codes
(1..K etc.) for every engine equally: our columnar plane stores dictionary codes
as Float64, and polars/duckdb receive the same integer codes.

Writes one .npy per column (for polars/duckdb) and one raw little-endian
float64 .bin per column (for the Mojo bench).
"""
import numpy as np
import os

N = 10_000_000
K = 100
rng = np.random.default_rng(108)

cols = {
    "id1": rng.integers(1, K + 1, N),
    "id2": rng.integers(1, K + 1, N),
    "id3": rng.integers(1, N // K + 1, N),
    "id4": rng.integers(1, K + 1, N),
    "id5": rng.integers(1, K + 1, N),
    "id6": rng.integers(1, N // K + 1, N),
    "v1": rng.integers(1, 6, N),
    "v2": rng.integers(1, 16, N),
    "v3": np.round(rng.uniform(0, 100, N), 6),
}

out = os.path.dirname(os.path.abspath(__file__))
for name, arr in cols.items():
    np.save(os.path.join(out, f"{name}.npy"), arr)
    arr.astype(np.float64).tofile(os.path.join(out, f"{name}.f64.bin"))
    print(name, arr.dtype, arr[:5], "distinct:", len(np.unique(arr[:100000])))
print("rows:", N)
