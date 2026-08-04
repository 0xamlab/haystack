"""H2O db-benchmark J1 join dataset, 0.5 GB tier: N=1e7 fact rows, no NAs, random order.

Ports h2oai/db-benchmark's `_data/join-datagen.R` (fetched from
github.com/h2oai/db-benchmark master, commit as of 2026-08) to numpy, seeded and
deterministic like `benchmarks/h2o_groupby/generate.py` already is for the groupby
track. This is NOT the R generator's actual RNG stream (numpy's `default_rng` and R's
`sample.int`/`sample` use different algorithms) -- it reproduces the SPEC: same table
shapes, same key-overlap structure (90% keys shared between the fact table and each
dimension table, 10% exclusive to each side), same value-column distributions.

Tables (mirrors `join-datagen.R` exactly):
  x (fact, N=1e7 rows):       id1 (10 distinct), id2 (10,000 distinct), id3 (N distinct,
                               i.e. a permutation -- one row per id3 value), v1.
  small (dimension, N/1e6=10 rows):     id1 (all 10 values, one row each), v2.
  medium (dimension, N/1e3=10,000 rows): id1, id2 (all 10,000 values, one row each), v2.
  big (dimension, N=1e7 rows):           id1, id2, id3 (all N values, one row each), v2.

Key-overlap construction (`split_xlr` in the R source): for each id column, draw a
random permutation of 1.1x the distinct-key count, split into a 90% "common" block, a
10% "left-only" block and a 10% "right-only" block. The fact table draws from
common+left-only; the matching dimension table draws from common+right-only. That is
why an inner join is not a 100% match rate even though most keys DO agree, and why a
left join on the same key (q3) has genuine unmatched rows to report on the bits.

id4/id5/id6 are the string forms `"id" + id1/id2/id3` in the official suite (q4 joins
on id5, the string form of id2). This project's columnar plane stores every join key as
Float64 -- dictionary codes, never strings, for every engine equally, exactly like the
groupby page's own disclosed convention. Since id5 is a strict bijection of id2
(same N always renders to the same string), joining on id5 and joining on id2 visit an
identical set of row pairs; q4 below is therefore run with id2 doing id5's job for
every engine, and this file emits no separate id4/id5/id6 arrays at all -- there is
nothing an integer-coded id4/id5/id6 would add that id1/id2/id3 do not already give.

Writes one .npy per column per table into /tmp/h2o_join, for polars/duckdb, and one
raw little-endian float64 .bin per column, for the Mojo bench (same convention as
`benchmarks/h2o_groupby/generate.py`).
"""
import os

import numpy as np

N = 10_000_000
SEED = 108
OUT = os.path.dirname(os.path.abspath(__file__)) or "."
DATA_DIR = "/tmp/h2o_join"


def split_xlr(n: int, rng: np.random.Generator):
    """A permutation of 1..1.1n split into common (90%) / left-only (10%) / right-only (10%)."""
    total = int(round(n * 1.1))
    key = rng.permutation(np.arange(1, total + 1, dtype=np.int64))
    n90 = int(round(n * 0.9))
    common = key[:n90]
    left_only = key[n90:n]
    right_only = key[n:total]
    return common, left_only, right_only


def sample_all(pool: np.ndarray, size: int, rng: np.random.Generator) -> np.ndarray:
    """Every value in `pool` appears >= 1 time in the result; result is shuffled.

    Mirrors R's `sample_all`: pad with replacement up to `size`, then shuffle the
    whole thing. Precondition (checked by the R source too): len(pool) <= size.
    """
    assert len(pool) <= size, (len(pool), size)
    if size == len(pool):
        out = pool.copy()
    else:
        pad = rng.choice(pool, size=size - len(pool), replace=True)
        out = np.concatenate([pool, pad])
    rng.shuffle(out)
    return out


def main() -> None:
    rng = np.random.default_rng(SEED)
    os.makedirs(DATA_DIR, exist_ok=True)

    n1 = N // 1_000_000  # 10
    n2 = N // 1_000  # 10,000
    n3 = N  # 10,000,000

    key1_common, key1_l, key1_r = split_xlr(n1, rng)
    key2_common, key2_l, key2_r = split_xlr(n2, rng)
    key3_common, key3_l, key3_r = split_xlr(n3, rng)

    lhs1_pool = np.concatenate([key1_common, key1_l])
    lhs2_pool = np.concatenate([key2_common, key2_l])
    lhs3_pool = np.concatenate([key3_common, key3_l])
    rhs1_pool = np.concatenate([key1_common, key1_r])
    rhs2_pool = np.concatenate([key2_common, key2_r])
    rhs3_pool = np.concatenate([key3_common, key3_r])
    assert len(lhs1_pool) == n1 and len(rhs1_pool) == n1
    assert len(lhs2_pool) == n2 and len(rhs2_pool) == n2
    assert len(lhs3_pool) == n3 and len(rhs3_pool) == n3

    print("generating fact table x ...")
    x_id1 = sample_all(lhs1_pool, N, rng)
    x_id2 = sample_all(lhs2_pool, N, rng)
    x_id3 = sample_all(lhs3_pool, N, rng)
    x_v1 = np.round(rng.uniform(0, 100, N), 6)
    assert len(np.unique(x_id1)) == n1
    assert len(np.unique(x_id2)) == n2
    assert len(np.unique(x_id3)) == n3  # every id3 value is unique -- one row each

    print("generating dimension table small (N/1e6 rows) ...")
    small_id1 = sample_all(rhs1_pool, n1, rng)
    small_v2 = np.round(rng.uniform(0, 100, n1), 6)
    assert len(np.unique(small_id1)) == n1

    print("generating dimension table medium (N/1e3 rows) ...")
    medium_id1 = sample_all(rhs1_pool, n2, rng)
    medium_id2 = sample_all(rhs2_pool, n2, rng)
    medium_v2 = np.round(rng.uniform(0, 100, n2), 6)
    assert len(np.unique(medium_id2)) == n2

    print("generating dimension table big (N rows) ...")
    big_id1 = sample_all(rhs1_pool, n3, rng)
    big_id2 = sample_all(rhs2_pool, n3, rng)
    big_id3 = sample_all(rhs3_pool, n3, rng)
    big_v2 = np.round(rng.uniform(0, 100, n3), 6)
    assert len(np.unique(big_id3)) == n3

    tables = {
        "x": {"id1": x_id1, "id2": x_id2, "id3": x_id3, "v1": x_v1},
        "small": {"id1": small_id1, "v2": small_v2},
        "medium": {"id1": medium_id1, "id2": medium_id2, "v2": medium_v2},
        "big": {"id1": big_id1, "id2": big_id2, "id3": big_id3, "v2": big_v2},
    }
    for table_name, cols in tables.items():
        for col_name, arr in cols.items():
            np.save(os.path.join(DATA_DIR, f"{table_name}_{col_name}.npy"), arr)
            arr.astype(np.float64).tofile(
                os.path.join(DATA_DIR, f"{table_name}_{col_name}.f64.bin")
            )
        print(table_name, "rows:", len(next(iter(cols.values()))), "cols:", list(cols))

    # Overlap sanity, printed rather than asserted: how many x rows will actually
    # find a partner on each key, computed here once so the Mojo/duckdb/polars
    # bench outputs have a ground truth to be checked against.
    for key_name, x_col, dim_ids in (
        ("id1 -> small", x_id1, small_id1),
        ("id2 -> medium", x_id2, medium_id2),
        ("id3 -> big", x_id3, big_id3),
    ):
        matchable = np.isin(x_col, dim_ids)
        print(
            f"overlap {key_name}: {matchable.sum()}/{N} x-rows have a partner "
            f"({100 * matchable.mean():.2f}%)"
        )


if __name__ == "__main__":
    main()
