"""Duel registry — the 13 benchmark duels of the Algenta Speed Arena.

Every duel pairs a real native Mojo kernel (from the arena-wheels release)
with its incumbent library at the incumbent's best legitimate configuration
(rule R7), over seeded corpora (rule R2), with a correctness gate before any
timing (rule R1). Sizes are scaled so one full run (gate + cold + 5 warm
reps per lane) fits the HF cpu-basic time budget; the published repo harness
(benchmarks/bench_*.py at the harness commit) runs the full-size grid.

Parity statements are the packages' own documented tolerances — printed on
every card.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass

import numpy as np

from arena import corpora
from arena.harness import Lane, NativeUnavailable
from arena.vendor import (
    gaussgrid_fixtures,
    nuscenes_fixtures,
    oletools_fixtures,
    pe_fixtures,
    pydicom_fixtures,
    pyquante1_oracle,
    vol_fixtures,
)

SEED = corpora.BASE_SEED


def _require_native(pkg, dist_name: str) -> str:
    info = pkg.backend_info()
    if not info["native_available"]:
        raise NativeUnavailable(
            f"{dist_name}: native Mojo kernel unavailable "
            f"({info.get('error') or 'fallback active'}) — the pure-Python "
            "fallback is never benchmarked as 'mojo'"
        )
    return (
        f"{dist_name} {pkg.__version__} · native Mojo kernel · {info.get('native_source', 'wheel')}"
    )


@dataclass
class DuelSpec:
    duel_id: str
    title: str
    blurb: str
    metric_label: str
    unit_label: str
    config_note: str
    sizes: dict  # key -> (param, label)
    build: object  # size_key -> workload
    make_lanes: object  # workload -> (list[Lane], setup_note)
    gate: object  # outputs dict -> (ok, detail, parity_label)
    hero_mode: str = "best"  # "best": slowest-incumbent/mojo? no — best incumbent vs mojo
    unit_divisor: object = None  # size_key -> float, for per-item display (e.g. per query)
    divided_label: str = ""  # item name for the divided column (e.g. "query")
    default_size: str = "M"  # the preselected cell — the duel's most reliable winner
    variant: str = ""  # neutral config tag for swept cards (e.g. "batched")

    def size_label(self, size_key: str) -> str:
        return self.sizes[size_key][1]

    def size_param(self, size_key: str):
        return self.sizes[size_key][0]

    def divisor(self, size_key: str) -> float:
        if self.unit_divisor is None:
            return 1.0
        return float(self.unit_divisor(size_key))

    def seed_note(self, size_key: str) -> str:
        return f"seed {SEED}+size offset (fixed; same bytes to every lane)"

    def lanes(self, workload):
        return self.make_lanes(workload)

    def hero(self, lane_timings):
        """Speedup of the best incumbent lane vs the algenta lane (warm)."""
        inc = [t for t in lane_timings if t.side == "incumbent"]
        alg = [t for t in lane_timings if t.side == "algenta"]
        best_inc = min(t.warm_median_s for t in inc)
        best_alg = min(t.warm_median_s for t in alg)
        inc_name = next(t.name for t in inc if t.warm_median_s == best_inc)
        speedup = best_inc / best_alg if best_alg > 0 else 0.0
        return speedup, f"{speedup:,.2f}× vs {inc_name} (warm, median of {WARM_REPS})"


WARM_REPS = 5


def _held_gate(detail: str):
    return False, detail, ""


# ---------------------------------------------------------------------------
# 1. BM25 — three-way: bm25-mojo vs rank_bm25 vs bm25s (numba)
# ---------------------------------------------------------------------------

BM25_SIZES = {
    "S": (1_000, "1,000 docs · 10 queries × 10 terms"),
    "M": (5_000, "5,000 docs · 10 queries × 10 terms"),
    "L": (20_000, "20,000 docs · 10 queries × 10 terms"),
}
BM25_N_QUERIES = 10
BM25_Q_LEN = 10
BM25_ATOL = 1e-8


def _bm25_build(size_key: str):
    import bm25s  # noqa: F401  (presence check at workload build)

    n_docs = BM25_SIZES[size_key][0]
    corpus = corpora.bm25_corpus(SEED + n_docs, n_docs)
    terms = list({t for doc in corpus for t in doc})
    queries = corpora.bm25_queries(SEED + n_docs + BM25_Q_LEN, terms, BM25_Q_LEN, BM25_N_QUERIES)
    return {"corpus": corpus, "queries": queries, "n_docs": n_docs}


def _bm25_lanes(wl):
    import time

    import bm25_mojo
    import bm25s
    from bm25_mojo import BM25Okapi
    from rank_bm25 import BM25Okapi as RefBM25Okapi

    native_note = _require_native(bm25_mojo, "bm25-mojo")
    corpus, queries = wl["corpus"], wl["queries"]

    t0 = time.perf_counter()
    ref = RefBM25Okapi(corpus)
    t_ref = time.perf_counter() - t0

    t0 = time.perf_counter()
    bs = bm25s.BM25(dtype="float32")  # method='lucene' — the bm25s default
    bs.index(corpus, show_progress=False)
    bs.compile()  # numba scorer — the config bm25s recommends for speed
    t_bs = time.perf_counter() - t0

    t0 = time.perf_counter()
    ours = BM25Okapi(corpus)
    t_ours = time.perf_counter() - t0

    lanes = [
        Lane(
            "rank_bm25 0.2.2",
            "incumbent",
            lambda: np.stack([ref.get_scores(q) for q in queries]),
            "BM25Okapi defaults (k1=1.5, b=0.75), per-query get_scores",
        ),
        Lane(
            "bm25s 0.3.11 (numba)",
            "incumbent",
            lambda: np.stack([bs.get_scores(q) for q in queries]),
            "method='lucene' float32, compile()d numba scorer, per-query get_scores — "
            "the config bm25s' own published QPS table uses (single-threaded)",
        ),
        Lane(
            "bm25-mojo (Algenta)",
            "algenta",
            lambda: np.asarray(ours.get_scores_batch(queries)),
            "kernel-side idf-weighted CSR, batch get_scores_batch (its documented best path)",
        ),
    ]
    setup = (
        f"one-time index builds — rank_bm25 {t_ref:.2f}s · bm25s(+numba) {t_bs:.2f}s · "
        f"bm25-mojo {t_ours:.2f}s · bm25s numba scorer pre-warmed once at Space boot "
        f"(its one-time JIT cost is measured there, not in duel cells). {native_note}"
    )
    return lanes, setup


def _bm25_gate(outputs):
    ref = outputs["rank_bm25 0.2.2"]
    ours = outputs["bm25-mojo (Algenta)"]
    worst = float(np.max(np.abs(ours - ref)))
    if worst > BM25_ATOL:
        return _held_gate(f"bm25-mojo vs rank_bm25 max|diff| {worst:.3e} > {BM25_ATOL}")
    return (
        True,
        f"max|diff| {worst:.3e} vs rank_bm25",
        (
            f"bit-faithful to rank_bm25 (max|diff| {worst:.1e} ≤ {BM25_ATOL}); bm25s is not "
            "element-wise comparable by design (it floors idf differently — documented on the card)"
        ),
    )


# ---------------------------------------------------------------------------
# 2. pykalman — Kalman filter
# ---------------------------------------------------------------------------

PYKALMAN_SIZES = {
    "S": (1_000, "T=1,000 obs · dims (5,2) · filter()"),
    "M": (10_000, "T=10,000 obs · dims (5,2) · filter()"),
    "L": (30_000, "T=30,000 obs · dims (5,2) · filter()"),
}
PYKALMAN_ATOL = 1e-10


def _pykalman_build(size_key: str):
    T = PYKALMAN_SIZES[size_key][0]
    params, obs = corpora.kalman_system(SEED + T, 5, 2, T)
    return {"params": params, "obs": obs}


def _pykalman_lanes(wl):
    import pykalman
    import pykalman_mojo

    native_note = _require_native(pykalman_mojo, "pykalman-mojo")
    params, obs = wl["params"], wl["obs"]

    def oracle():
        kf = pykalman.KalmanFilter(**params)
        fm, fc = kf.filter(obs)
        return np.concatenate([fm.ravel(), fc.ravel()])

    def ours():
        kf = pykalman_mojo.KalmanFilter(**params)
        fm, fc = kf.filter(obs)
        return np.concatenate([fm.ravel(), fc.ravel()])

    return [
        Lane(
            "pykalman 0.11.2",
            "incumbent",
            oracle,
            "fresh KalmanFilter per call, filter() — construct + run end-to-end",
        ),
        Lane(
            "pykalman-mojo (Algenta)",
            "algenta",
            ours,
            "fresh KalmanFilter per call, filter() — identical construction semantics",
        ),
    ], f"fresh instance per call (construction included, end-to-end per R8). {native_note}"


def _pykalman_gate(outputs):
    diff = float(np.max(np.abs(outputs["pykalman-mojo (Algenta)"] - outputs["pykalman 0.11.2"])))
    if diff > PYKALMAN_ATOL:
        return _held_gate(f"max|diff| {diff:.3e} > {PYKALMAN_ATOL}")
    return True, f"max|diff| {diff:.3e}", f"element-wise ≤ {PYKALMAN_ATOL} (means + covariances)"


# ---------------------------------------------------------------------------
# 3. volatility3 — pool-header scan
# ---------------------------------------------------------------------------

VOL_POOL_SIZES = {
    "S": ((2 * 1024 * 1024, 500), "2 MiB buffer · 500 planted headers + decoys"),
    "M": ((8 * 1024 * 1024, 2000), "8 MiB buffer · 2,000 planted headers + decoys"),
    "L": ((16 * 1024 * 1024, 4000), "16 MiB buffer · 4,000 planted headers + decoys"),
}

_VOL_TAGS = [
    (b"Proc", 0x41, 2),
    (b"File", 0x10, 2),
    (b"Thre", 0x40, 2),
    (b"Muta", 0x08, 2),
    (b"Driv", 0x10, 2),
    (b"MmLd", 0x05, 2),
    (b"Symb", 0x05, 1),
    (b"CM10", 0x40, 1),
    (b"AtmT", 0x10, 1),
    (b"Pro\xe3", 0x41, 2),
    (b"Thr\xe5", 0x40, 2),
    (b"Fil\xe5", 0x10, 2),
    (b"Mut\xe1", 0x08, 2),
    (b"Dri\xf6", 0x10, 2),
    (b"Sym\xe2", 0x05, 1),
]


def _vol_pool_bin(pool_size: int, n_headers: int) -> bytes:
    buf = bytearray(b"\x00" * pool_size)
    stride = pool_size // (n_headers + 1) & ~0xF
    for i in range(n_headers):
        off = stride * (i + 1)
        tag, block, ptype = _VOL_TAGS[i % len(_VOL_TAGS)]
        if i % 7 == 3:
            block = 0x01  # undersized -> rejected
        if i % 11 == 5:
            ptype = 0  # free pool
        vol_fixtures.put_header_x64(buf, off, i & 0xFF, block, ptype, tag)
        if i % 5 == 2:  # decoy tag bytes with no valid header nearby
            buf[off + 0x800 : off + 0x804] = _VOL_TAGS[(i + 1) % len(_VOL_TAGS)][0]
    return bytes(buf)


def _vol_pool_build(size_key: str):
    pool_size, n_headers = VOL_POOL_SIZES[size_key][0]
    return {"buf": _vol_pool_bin(pool_size, n_headers)}


def _vol_pool_lanes(wl):
    # Import order matters (breaks the pool<->poolscanner cycle): the pool
    # extension module must be initialized before poolscanner is imported.
    import vol_mojo
    from volatility3.framework.symbols.windows.extensions import pool as _poolext  # noqa: F401
    from volatility3.plugins.windows import poolscanner

    native_note = _require_native(vol_mojo, "vol-mojo")
    buf = wl["buf"]
    workdir = tempfile.mkdtemp(prefix="arena_vol_")
    import os

    bin_path = os.path.join(workdir, "pool.bin")
    with open(bin_path, "wb") as fh:
        fh.write(buf)
    constraints = poolscanner.PoolScanner.builtin_constraints("nt_symbols")
    oracle_run = vol_fixtures.oracle_pool_scanner_factory(
        bin_path, constraints, "poolheader-x64", True, 0x10
    )
    lanes = [
        Lane(
            "volatility3 2.28.2",
            "incumbent",
            lambda: oracle_run(buf),
            "PoolHeaderScanner over a FileLayer, PoolScanner.builtin_constraints('nt_symbols'), "
            "scanner/context built once up front — the per-hit work a plugin pays for",
        ),
        Lane(
            "vol-mojo (Algenta)",
            "algenta",
            lambda: vol_mojo.scan_pool_headers(
                buf, constraints, alignment=0x10, layout="x64", vista_semantics=True
            ),
            "same constraints, same scan semantics, fused native pass",
        ),
    ]
    return (
        lanes,
        f"oracle scanner built once (untimed setup); unit = one full buffer scan. {native_note}",
    )


def _vol_pool_gate(outputs):
    ref = outputs["volatility3 2.28.2"]
    ours = outputs["vol-mojo (Algenta)"]
    if ours != ref:
        return _held_gate(f"pool-scan hit lists differ ({len(ours)} vs {len(ref)} hits)")
    return (
        True,
        f"{len(ref)} hits, exact ordered match",
        "exact hit-list equality (offsets + tags, in scan order)",
    )


# ---------------------------------------------------------------------------
# 4. volatility3 — registry hive walk
# ---------------------------------------------------------------------------

VOL_HIVE_SIZES = {
    "S": ((10, 20), "211-node registry hive (flat .dat)"),
    "M": ((15, 35), "541-node registry hive (flat .dat)"),
    "L": ((20, 50), "1,021-node registry hive (flat .dat)"),
}


def _vol_hive_dat(children: int, grandchildren: int) -> bytes:
    b = vol_fixtures.HiveBuilder()
    child_idxs = []
    for c in range(children):
        leaves = [
            b.add_cell(b.nk(f"LeafKey-{c:03d}-{g:04d}".encode())) for g in range(grandchildren)
        ]
        lhs = [
            b.add_cell(
                b.index(b"lh", [(cell, 0x1000 + i) for i, cell in enumerate(leaves[k : k + 40])])
            )
            for k in range(0, grandchildren, 40)
        ]
        ri = b.add_cell(b.index(b"ri", lhs))
        child_idxs.append(
            b.add_cell(
                b.nk(f"ChildKey-{c:03d}".encode(), subkey_count=grandchildren, subkey_list=ri)
            )
        )
    lhs = [
        b.add_cell(
            b.index(b"lh", [(cell, 0x5000 + i) for i, cell in enumerate(child_idxs[k : k + 40])])
        )
        for k in range(0, children, 40)
    ]
    ri = b.add_cell(b.index(b"ri", lhs))
    root = b.add_cell(b.nk(b"ROOT", flags=0x2C, subkey_count=children, subkey_list=ri))
    dat, _ = b.build_dat(root)
    return dat


def _vol_hive_build(size_key: str):
    children, grandchildren = VOL_HIVE_SIZES[size_key][0]
    return {"dat": _vol_hive_dat(children, grandchildren)}


def _vol_hive_lanes(wl):
    import os

    import vol_mojo

    native_note = _require_native(vol_mojo, "vol-mojo")
    dat = wl["dat"]
    workdir = tempfile.mkdtemp(prefix="arena_hive_")
    img, _ = vol_fixtures.add_management(dat, len(dat) - 0x1000)
    img_path = os.path.join(workdir, "hive.img")
    isf_path = os.path.join(workdir, "hive.isf.json")
    with open(img_path, "wb") as fh:
        fh.write(img)
    with open(isf_path, "w") as fh:
        fh.write(vol_fixtures.fake_nt_isf_json())
    hive = vol_fixtures._make_hive_layer(img_path, (len(dat) + 0xFFF) & ~0xFFF, isf_path)

    def oracle_walk():
        tuples = []
        hive.visit_nodes(
            lambda node: tuples.append(
                (node.vol.offset, node.vol.type_name.split("!")[-1], node.get_name())
            )
        )
        return tuples

    lanes = [
        Lane(
            "volatility3 2.28.2",
            "incumbent",
            oracle_walk,
            "RegistryHive.visit_nodes over the managed hive layer (context built once, untimed)",
        ),
        Lane(
            "vol-mojo (Algenta)",
            "algenta",
            lambda: vol_mojo.walk_hive(dat),
            "flat .dat bytes in, same (offset, type, name) tuples out",
        ),
    ]
    return lanes, f"unit = one full hive walk. {native_note}"


def _vol_hive_gate(outputs):
    ref = outputs["volatility3 2.28.2"]
    ours = outputs["vol-mojo (Algenta)"]
    if ours != ref:
        return _held_gate(f"hive-walk tuples differ ({len(ours)} vs {len(ref)})")
    return (
        True,
        f"{len(ref)} nodes, exact ordered match",
        "exact tuple-list equality (offset, type, name)",
    )


# ---------------------------------------------------------------------------
# 5. pefile — PE checksum
# ---------------------------------------------------------------------------

PEFILE_SIZES = {
    # Sized for the cpu-basic budget: the oracle's pure-Python dword loop is
    # linear in bytes and S (8 × 64 KB) already measures ~9 s of it per run.
    "S": ((8, 64 * 1024), "8 synthetic PEs × ~64 KB"),
    "M": ((8, 256 * 1024), "8 synthetic PEs × ~256 KB"),
    "L": ((8, 512 * 1024), "8 synthetic PEs × ~512 KB"),
}


def _pefile_build(size_key: str):
    n, text_bytes = PEFILE_SIZES[size_key][0]
    blobs = [
        pe_fixtures.make_big_pe(n_dlls=8, n_funcs=6, bits=64, text_bytes=text_bytes + i * 997)
        for i in range(n)
    ]
    return {"blobs": blobs}


def _pefile_lanes(wl):
    import pefile
    import pefile_mojo

    native_note = _require_native(pefile_mojo, "pefile-mojo")
    blobs = wl["blobs"]

    def oracle():
        out = []
        for blob in blobs:
            pe = pefile.PE(data=blob, fast_load=True)
            out.append(pe.generate_checksum())
        return out

    def ours():
        return [
            pefile_mojo.generate_checksum(b, pefile_mojo.checksum_field_offset(b)) for b in blobs
        ]

    lanes = [
        Lane(
            "pefile 2024.8.26",
            "incumbent",
            oracle,
            "PE(data=…, fast_load=True).generate_checksum() — fast_load skips the directory "
            "parse, isolating the checksum loop (pefile's fastest legitimate config)",
        ),
        Lane(
            "pefile-mojo (Algenta)",
            "algenta",
            ours,
            "SIMD dword-sum kernel, same checksum semantics",
        ),
    ]
    return (
        lanes,
        f"unit = checksums for the whole blob batch (materialized ints, R8). {native_note}",
    )


def _pefile_gate(outputs):
    ref = outputs["pefile 2024.8.26"]
    ours = outputs["pefile-mojo (Algenta)"]
    if ours != ref:
        bad = [i for i, (a, b) in enumerate(zip(ours, ref, strict=False)) if a != b][:5]
        return _held_gate(f"checksum mismatch on blobs {bad}")
    return True, f"{len(ref)} blobs, bit-exact", "bit-exact (tolerance 0) on every blob"


# ---------------------------------------------------------------------------
# 6. oletools — MS-OVBA VBA decompression
# ---------------------------------------------------------------------------

OLETOOLS_SIZES = {
    "S": (3_000, "VBA source ~210 KB (compressed container)"),
    "M": (12_000, "VBA source ~840 KB (compressed container)"),
    "L": (30_000, "VBA source ~2.1 MB (compressed container)"),
}


def _oletools_build(size_key: str):
    import random

    n_lines = OLETOOLS_SIZES[size_key][0]
    raw = oletools_fixtures.vba_like_source(random.Random(SEED + n_lines), n_lines)
    return {"container": oletools_fixtures.vba_compress(raw), "raw": raw}


def _oletools_lanes(wl):
    import oletools_mojo
    from oletools.olevba import decompress_stream as oracle_decompress

    native_note = _require_native(oletools_mojo, "oletools-mojo")
    container = wl["container"]
    lanes = [
        Lane(
            "oletools 0.60.2",
            "incumbent",
            lambda: oracle_decompress(container),
            "olevba.decompress_stream — the stock MS-OVBA decoder",
        ),
        Lane(
            "oletools-mojo (Algenta)",
            "algenta",
            lambda: oletools_mojo.decompress_stream(container),
            "same call shape, native LZ pass",
        ),
    ]
    return lanes, f"unit = one full container decompress (materialized bytes, R8). {native_note}"


def _oletools_gate(outputs):
    ref = outputs["oletools 0.60.2"]
    ours = outputs["oletools-mojo (Algenta)"]
    if ours != ref:
        return _held_gate(f"decompressed bytes differ ({len(ours)} vs {len(ref)} bytes)")
    return True, f"{len(ref):,} bytes, byte-identical", "byte-identical output (tolerance 0)"


# ---------------------------------------------------------------------------
# 7. ruptures — change-point detection
# ---------------------------------------------------------------------------

RUPTURES_SIZES = {
    # Sized for the HF cpu-basic budget: the ruptures oracle's exact (jump=1)
    # solvers are O(K·n²)-class in pure Python/NumPy — the published harness
    # runs the full grid up to n=100,000 on a workstation; here each cell must
    # finish its gate + cold + 5 warm reps in about a minute.
    "S": (("dynp", 400, {"n_bkps": 3}, 1), "Dynp n=400 K=3 jump=1 (exact)"),
    "M": (("pelt", 1_500, {"pen": 10.0}, 1), "PELT n=1,500 pen=10 jump=1 (exact)"),
    "L": (("binseg", 5_000, {"n_bkps": 10}, 1), "Binseg n=5,000 K=10 jump=1 (exact)"),
}


def _ruptures_build(size_key: str):
    method, n, kw, jump = RUPTURES_SIZES[size_key][0]
    return {"sig": corpora.ruptures_signal(n, SEED + n), "cfg": (method, kw, jump)}


def _ruptures_lanes(wl):
    import ruptures as rpt
    import ruptures_mojo

    native_note = _require_native(ruptures_mojo, "ruptures-mojo")
    sig = wl["sig"]
    method, kw, jump = wl["cfg"]

    def oracle():
        est_cls = {"dynp": rpt.Dynp, "pelt": rpt.Pelt, "binseg": rpt.Binseg}[method]
        est = est_cls(model="l2", min_size=2, jump=jump)
        if method == "pelt":
            return list(est.fit_predict(sig, kw["pen"]))
        return list(est.fit_predict(sig, kw["n_bkps"]))

    def ours():
        return list(ruptures_mojo.detect(sig, method, model="l2", min_size=2, jump=jump, **kw))

    lanes = [
        Lane(
            "ruptures 1.1.10",
            "incumbent",
            oracle,
            f"{method} model='l2' min_size=2 jump={jump} — jump=1 is the exact config "
            "(jump>1 subsamples the search grid for speed; we race the exact one)",
        ),
        Lane(
            "ruptures-mojo (Algenta)", "algenta", ours, "same estimator semantics, native DP pass"
        ),
    ]
    return (
        lanes,
        f"unit = one full detection call (materialized breakpoint list, R8). {native_note}",
    )


def _ruptures_gate(outputs):
    ref = outputs["ruptures 1.1.10"]
    ours = outputs["ruptures-mojo (Algenta)"]
    if ours != ref:
        return _held_gate(f"breakpoint lists differ ({ours} vs {ref})")
    return True, f"breakpoints {ours}, exact match", "exact breakpoint-set equality (tolerance 0)"


# ---------------------------------------------------------------------------
# 8. croniter — schedule roll-outs
# ---------------------------------------------------------------------------

CRONITER_SIZES = {
    "S": (100, "100-step chains × 5 expressions"),
    "M": (1_000, "1,000-step chains × 5 expressions"),
    "L": (5_000, "5,000-step chains × 5 expressions"),
}


def _croniter_build(size_key: str):
    return {"n": CRONITER_SIZES[size_key][0]}


def _croniter_lanes(wl):
    from datetime import datetime

    import croniter_mojo
    from croniter import croniter

    native_note = _require_native(croniter_mojo, "croniter-mojo")
    n = wl["n"]
    start = datetime(2026, 9, 19, 14, 30, 45)

    def chain(call):
        out = []
        for expr, _label in corpora.CRON_EXPRS:
            cur = start
            for _ in range(n):
                cur = call(expr, cur)
                out.append(cur)
        return out

    lanes = [
        Lane(
            "croniter 6.2.4",
            "incumbent",
            lambda: chain(lambda e, cur: croniter(e, cur).get_next(datetime)),
            "fresh croniter(expr, cur).get_next(datetime) per step — parse + seek every call",
        ),
        Lane(
            "croniter-mojo (Algenta)",
            "algenta",
            lambda: chain(lambda e, cur: croniter_mojo.get_next(e, cur)),
            "arithmetic leap-finding kernel, same semantics",
        ),
    ]
    return lanes, (
        f"unit = the full {n}-step × 5-expression roll-out "
        f"(all fire times materialized, R8). {native_note}"
    )


def _croniter_gate(outputs):
    ref = outputs["croniter 6.2.4"]
    ours = outputs["croniter-mojo (Algenta)"]
    if ours != ref:
        bad = next(i for i, (a, b) in enumerate(zip(ours, ref, strict=False)) if a != b)
        return _held_gate(f"fire time #{bad} differs ({ours[bad]} vs {ref[bad]})")
    return (
        True,
        f"{len(ref):,} fire times, exact datetime equality",
        "exact datetime equality on every fire time",
    )


# ---------------------------------------------------------------------------
# 9. obspy — Konno-Ohmachi smoothing
# ---------------------------------------------------------------------------

OBSPY_SIZES = {
    "S": ((512, 1), "1 spectrum · 512 bins"),
    "M": ((2048, 1), "1 spectrum · 2,048 bins"),
    "L": ((2048, 32), "32 spectra × 2,048 bins (batched)"),
}
OBSPY_RTOL, OBSPY_ATOL = 1e-9, 1e-12


def _obspy_build(size_key: str):
    n_bins, n_spec = OBSPY_SIZES[size_key][0]
    shape = (n_bins,) if n_spec == 1 else (n_spec, n_bins)
    return {
        "spec": corpora.konno_spectra(SEED + n_bins * n_spec, shape),
        "freqs": corpora.konno_freqs(n_bins),
    }


def _obspy_lanes(wl):
    import obspy_mojo
    from obspy.signal.konnoohmachismoothing import konno_ohmachi_smoothing as oracle_smooth

    native_note = _require_native(obspy_mojo, "obspy-mojo")
    spec, freqs = wl["spec"], wl["freqs"]
    batched = spec.ndim == 2
    lanes = [
        Lane(
            "obspy 1.5.1",
            "incumbent",
            lambda: oracle_smooth(spec, freqs, bandwidth=40, count=1, normalize=False),
            (
                "konno_ohmachi_smoothing on the 2-D batch — ObsPy auto-selects its matrix-"
                "multiply fast path (its genuine best config)"
                if batched
                else "konno_ohmachi_smoothing, defaults (bandwidth=40, count=1)"
            ),
        ),
        Lane(
            "obspy-mojo (Algenta)",
            "algenta",
            lambda: obspy_mojo.konno_ohmachi_smoothing(spec, freqs),
            "fused native pass, same defaults",
        ),
    ]
    return lanes, f"unit = one full smoothing call (materialized spectra, R8). {native_note}"


def _obspy_gate(outputs):
    ref = np.asarray(outputs["obspy 1.5.1"])
    ours = np.asarray(outputs["obspy-mojo (Algenta)"])
    worst = float(np.max(np.abs(ours - ref)))
    if not np.allclose(ours, ref, rtol=OBSPY_RTOL, atol=OBSPY_ATOL):
        return _held_gate(f"max|diff| {worst:.3e} beyond rtol={OBSPY_RTOL}")
    return True, f"max|diff| {worst:.3e}", f"float64, rtol {OBSPY_RTOL} / atol {OBSPY_ATOL}"


# ---------------------------------------------------------------------------
# 10. cclib — Gaussian grid evaluation (benzene 6-31G*)
# ---------------------------------------------------------------------------

CCLIB_SIZES = {
    "S": (("wf", 1, (10, 10, 10)), "wavefunction 1 MO · 10³ grid"),
    "M": (("wf", 1, (14, 14, 14)), "wavefunction 1 MO · 14³ grid"),
    "L": (("rho", 2, (12, 12, 12)), "density 2 MOs · 12³ grid"),
}
CCLIB_RTOL, CCLIB_ATOL = 1e-10, 1e-12


def _cclib_grid(shape):
    side = 7.0  # Angstrom; covers the benzene diameter with margin
    origin = (-side, -side, -side)
    step = tuple(2.0 * side / (n - 1) for n in shape)
    return origin, step, shape


def _cclib_build(size_key: str):
    kind, n_mo, shape = CCLIB_SIZES[size_key][0]
    gbasis, atomcoords = gaussgrid_fixtures.benzene_6_31g_star()
    return {"gbasis": gbasis, "atomcoords": atomcoords, "kind": kind, "shape": shape, "n_mo": n_mo}


def _cclib_lanes(wl):
    import cclib_mojo
    from cclib_mojo._basis import flatten_gbasis

    native_note = _require_native(cclib_mojo, "cclib-mojo")
    gbasis, atomcoords = wl["gbasis"], wl["atomcoords"]
    basis = flatten_gbasis(gbasis, atomcoords)
    n_bf = basis.n_bf
    coeff = gaussgrid_fixtures.seeded_coeffs(SEED + wl["n_mo"], wl["n_mo"], n_bf)
    origin, step, shape = _cclib_grid(wl["shape"])
    kind = wl["kind"]

    if kind == "wf":
        oracle = lambda: pyquante1_oracle.wavefunction(
            gbasis, atomcoords, coeff[0], origin, step, shape
        )
        ours = lambda: cclib_mojo.wavefunction_on_grid(
            gbasis, atomcoords, coeff[0], origin, step, shape
        )
        kind_label = "wavefunction"
    else:
        oracle = lambda: pyquante1_oracle.electrondensity_spin(
            gbasis, atomcoords, coeff, origin, step, shape
        )
        ours = lambda: cclib_mojo.density_on_grid(gbasis, atomcoords, coeff, origin, step, shape)
        kind_label = "electron density"

    lanes = [
        Lane(
            "cclib PyQuante1 path",
            "incumbent",
            oracle,
            "cclib's wavefunction() hot loop as written for the PyQuante-1 backend: pure-Python "
            "per-grid-point Gaussian amplitudes (verbatim transcription used by the published harness)",
        ),
        Lane("cclib-mojo (Algenta)", "algenta", ours, "flat-basis native grid kernel"),
    ]
    setup = (
        f"benzene 6-31G* ({len(gbasis)} atoms, {n_bf} contracted Cartesian bfs, "
        f"{basis.n_prims} primitives), {kind_label}. {native_note}"
    )
    return lanes, setup


def _cclib_gate(outputs):
    ref = np.asarray(outputs["cclib PyQuante1 path"])
    ours = np.asarray(outputs["cclib-mojo (Algenta)"])
    worst = float(np.max(np.abs(ours - ref)))
    if not np.allclose(ours, ref, rtol=CCLIB_RTOL, atol=CCLIB_ATOL):
        return _held_gate(f"max|diff| {worst:.3e} beyond rtol={CCLIB_RTOL}")
    return True, f"max|diff| {worst:.3e}", f"rtol {CCLIB_RTOL} / atol {CCLIB_ATOL} on the full grid"


# ---------------------------------------------------------------------------
# 11. pydicom — RLE Lossless decode
# ---------------------------------------------------------------------------

PYDICOM_SIZES = {
    "S": (4, "4 CT-style frames · 512×512 16-bit"),
    "M": (8, "8 CT-style frames · 512×512 16-bit"),
    "L": (16, "16 CT-style frames · 512×512 16-bit"),
}


def _pydicom_build(size_key: str):
    n = PYDICOM_SIZES[size_key][0]
    rows = cols = 512
    raws = [pydicom_fixtures.ct_like_frame(rows, cols, SEED + i) for i in range(n)]
    # The timed unit is DECODE; frames are RLE-encoded once up front by the
    # oracle's own encoder (untimed setup) so both lanes decode identical bytes.
    frames = [pydicom_fixtures.oracle_encode_frame(raw, cols, 1, 16) for raw in raws]
    return {"frames": frames, "rows": rows, "cols": cols}


def _pydicom_lanes(wl):
    import pydicom_mojo

    native_note = _require_native(pydicom_mojo, "pydicom-mojo")
    frames, rows, cols = wl["frames"], wl["rows"], wl["cols"]

    def oracle():
        return [pydicom_fixtures.oracle_decode_frame(f, rows, cols, 1, 16) for f in frames]

    def ours():
        return [
            pydicom_mojo.decode_frame(
                f, rows=rows, columns=cols, samples_per_pixel=1, bits_allocated=16
            )
            for f in frames
        ]

    lanes = [
        Lane(
            "pydicom 3.0.2",
            "incumbent",
            oracle,
            "pydicom's pure-Python _rle_decode_frame — the exact seam a pydicom decode plugin runs at",
        ),
        Lane("pydicom-mojo (Algenta)", "algenta", ours, "native PackBits + segment reassembly"),
    ]
    return (
        lanes,
        f"unit = decode of the whole frame batch (materialized pixel bytes, R8). {native_note}",
    )


def _pydicom_gate(outputs):
    ref = outputs["pydicom 3.0.2"]
    ours = outputs["pydicom-mojo (Algenta)"]
    if len(ours) != len(ref) or any(a != b for a, b in zip(ours, ref, strict=False)):
        return _held_gate("decoded pixel bytes differ")
    return True, f"{len(ref)} frames, byte-identical", "byte-identical pixels (tolerance 0)"


# ---------------------------------------------------------------------------
# 12. nuScenes — detection metrics
# ---------------------------------------------------------------------------

NUSCENES_SIZES = {
    "S": (60, "60 samples · ~8-20 gt boxes each"),
    "M": (200, "200 samples · ~8-20 gt boxes each"),
    "L": (500, "500 samples · ~8-20 gt boxes each"),
}
NUSCENES_ATOL = 1e-8


def _nuscenes_build(size_key: str):
    n = NUSCENES_SIZES[size_key][0]
    gt, pred = nuscenes_fixtures.make_corpus(
        seed=SEED + n,
        n_samples=n,
        gt_per_sample=(8, 20),
        pred_per_gt=1.35,
        fp_rate=1.0,
        ties=True,
    )
    return {"gt": gt, "pred": pred}


def _nuscenes_lanes(wl):
    import nuscenes_eval_mojo

    native_note = _require_native(nuscenes_eval_mojo, "nuscenes-eval-mojo")
    gt, pred = wl["gt"], wl["pred"]
    lanes = [
        Lane(
            "nuscenes-devkit 1.2.0",
            "incumbent",
            lambda: nuscenes_fixtures.reference_metrics(gt, pred),
            "the devkit's own post-DB-load chain: DetectionBox/EvalBoxes, add_center_dist, "
            "filter_eval_boxes, accumulate (10 classes × 4 thresholds), calc_ap/calc_tp, "
            "DetectionMetrics assembly",
        ),
        Lane(
            "nuscenes-eval-mojo (Algenta)",
            "algenta",
            lambda: nuscenes_eval_mojo.evaluate(gt, pred),
            "same chain, native matching + AP kernels",
        ),
    ]
    return lanes, f"unit = one full evaluation (materialized metrics dict, R8). {native_note}"


def _nuscenes_gate(outputs):
    ref = outputs["nuscenes-devkit 1.2.0"]
    ours = outputs["nuscenes-eval-mojo (Algenta)"]
    try:
        worst = nuscenes_fixtures.compare_metrics(ours, ref, atol=NUSCENES_ATOL)
    except AssertionError as exc:
        return _held_gate(str(exc))
    return (
        True,
        f"full metrics dict, max|diff| {worst:.3e}",
        f"metrics-dict agreement ≤ {NUSCENES_ATOL}",
    )


# ---------------------------------------------------------------------------
# 13. motmetrics — MOTChallenge metrics
# ---------------------------------------------------------------------------

MOTMETRICS_SIZES = {
    "S": ((100, 10, 11), "100 frames × 10 objects × 11 hyps"),
    "M": ((500, 25, 27), "500 frames × 25 objects × 27 hyps"),
    "L": ((1_000, 40, 44), "1,000 frames × 40 objects × 44 hyps"),
}
MOTMETRICS_ATOL = 1e-9
MOTCHALLENGE = [
    "idf1",
    "idp",
    "idr",
    "recall",
    "precision",
    "num_unique_objects",
    "mostly_tracked",
    "partially_tracked",
    "mostly_lost",
    "num_false_positives",
    "num_misses",
    "num_switches",
    "num_fragmentations",
    "mota",
    "motp",
    "num_transfer",
    "num_ascend",
    "num_migrate",
]


def _motmetrics_build(size_key: str):
    nf, no, nh = MOTMETRICS_SIZES[size_key][0]
    return {"frames": corpora.mot_stream(SEED, nf, no, nh)}


def _motmetrics_lanes(wl):
    import motmetrics as mm
    import motmetrics_mojo as M

    native_note = _require_native(M, "motmetrics-mojo")
    frames = wl["frames"]

    def oracle():
        acc = mm.MOTAccumulator(auto_id=True)
        for oids, hids, d in frames:
            acc.update(oids, hids, d)
        mh = mm.metrics.create()
        row = mh.compute(acc, metrics=MOTCHALLENGE, name="x").iloc[0]
        return {m: float(row[m]) for m in MOTCHALLENGE}

    def ours():
        acc = M.MOTAccumulator(auto_id=True)
        for oids, hids, d in frames:
            acc.update(oids, hids, d)
        summary = M.compute(acc, metrics=MOTCHALLENGE)
        return {m: float(summary[m]) for m in MOTCHALLENGE}

    lanes = [
        Lane(
            "motmetrics 1.4.0",
            "incumbent",
            oracle,
            "accumulate whole stream + MetricsHost compute (18 MOTChallenge metrics)",
        ),
        Lane(
            "motmetrics-mojo (Algenta)",
            "algenta",
            ours,
            "same accumulator/update shape, native matching kernel",
        ),
    ]
    return lanes, f"unit = one full accumulate+compute pipeline (R8). {native_note}"


def _motmetrics_gate(outputs):
    ref = outputs["motmetrics 1.4.0"]
    ours = outputs["motmetrics-mojo (Algenta)"]
    worst = 0.0
    for m in MOTCHALLENGE:
        a, b = ours[m], ref[m]
        if np.isnan(a) and np.isnan(b):
            continue
        worst = max(worst, abs(a - b))
    if worst > MOTMETRICS_ATOL:
        return _held_gate(f"metric diff {worst:.3e} > {MOTMETRICS_ATOL}")
    return (
        True,
        f"18 MOTChallenge metrics, max|diff| {worst:.3e}",
        f"counts exact, MOTP ≤ {MOTMETRICS_ATOL}",
    )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

DUELS = [
    DuelSpec(
        duel_id="bm25",
        title="BM25 lexical search — three-way",
        blurb="bm25-mojo vs rank_bm25 vs bm25s (numba) on a seeded Zipf corpus",
        metric_label="per-query latency (lower is better)",
        unit_label="batch of 10 queries",
        config_note="rank_bm25 defaults · bm25s 'lucene'+numba compile (its published config) · "
        "bm25-mojo batch path; identical tokenized corpus and queries for all three",
        sizes=BM25_SIZES,
        build=_bm25_build,
        make_lanes=_bm25_lanes,
        gate=_bm25_gate,
        unit_divisor=lambda sk: BM25_N_QUERIES,
        divided_label="query",
        default_size="L",
        variant="batched",
    ),
    DuelSpec(
        duel_id="pykalman",
        title="Kalman filter",
        blurb="pykalman-mojo vs pykalman on a seeded linear-Gaussian system",
        metric_label="per-call latency (lower is better)",
        unit_label="filter() call (fresh instance, construction included)",
        config_note="fresh KalmanFilter per call on both sides — identical semantics",
        sizes=PYKALMAN_SIZES,
        build=_pykalman_build,
        make_lanes=_pykalman_lanes,
        gate=_pykalman_gate,
    ),
    DuelSpec(
        duel_id="vol-pool",
        title="volatility3 pool-header scan",
        blurb="vol-mojo vs volatility3 PoolHeaderScanner on a planted-header buffer",
        metric_label="per-scan latency (lower is better)",
        unit_label="one full buffer scan",
        config_note="PoolScanner.builtin_constraints('nt_symbols'), x64 vista semantics, alignment 0x10",
        sizes=VOL_POOL_SIZES,
        build=_vol_pool_build,
        make_lanes=_vol_pool_lanes,
        gate=_vol_pool_gate,
    ),
    DuelSpec(
        duel_id="vol-hive",
        title="volatility3 registry-hive walk",
        blurb="vol-mojo vs volatility3 RegistryHive.visit_nodes on a synthetic hive",
        metric_label="per-walk latency (lower is better)",
        unit_label="one full hive walk",
        config_note="flat .dat hive generated locally (no copyrighted Windows hive)",
        sizes=VOL_HIVE_SIZES,
        build=_vol_hive_build,
        make_lanes=_vol_hive_lanes,
        gate=_vol_hive_gate,
        default_size="S",
    ),
    DuelSpec(
        duel_id="pefile",
        title="PE checksum",
        blurb="pefile-mojo vs pefile generate_checksum on synthetic PE images",
        metric_label="per-batch latency (lower is better)",
        unit_label="checksum batch (8 PEs)",
        config_note="pefile at fast_load=True (its fastest legitimate config); synthetic license-clean PEs",
        sizes=PEFILE_SIZES,
        build=_pefile_build,
        make_lanes=_pefile_lanes,
        gate=_pefile_gate,
        unit_divisor=lambda sk: PEFILE_SIZES[sk][0][0],
        divided_label="PE image",
    ),
    DuelSpec(
        duel_id="oletools",
        title="VBA macro decompression (MS-OVBA)",
        blurb="oletools-mojo vs oletools olevba.decompress_stream",
        metric_label="per-call latency (lower is better)",
        unit_label="one container decompress",
        config_note="seeded VBA-like source, MS-OVBA-compressed by the harness's pinned compressor",
        sizes=OLETOOLS_SIZES,
        build=_oletools_build,
        make_lanes=_oletools_lanes,
        gate=_oletools_gate,
    ),
    DuelSpec(
        duel_id="ruptures",
        title="Change-point detection",
        blurb="ruptures-mojo vs ruptures Dynp/Pelt/Binseg on seeded signals",
        metric_label="per-call latency (lower is better)",
        unit_label="one detection call",
        config_note="model='l2', jump=1 — the exact search grid (not the subsampled default)",
        sizes=RUPTURES_SIZES,
        build=_ruptures_build,
        make_lanes=_ruptures_lanes,
        gate=_ruptures_gate,
    ),
    DuelSpec(
        duel_id="croniter",
        title="Cron schedule roll-out",
        blurb="croniter-mojo vs croniter over 1k-5k-step chains, incl. leap-day",
        metric_label="per-chain latency (lower is better)",
        unit_label="full chain roll-out",
        config_note="fresh croniter(expr, cur) per step on both sides; 5 seeded expressions",
        sizes=CRONITER_SIZES,
        build=_croniter_build,
        make_lanes=_croniter_lanes,
        gate=_croniter_gate,
        unit_divisor=lambda sk: CRONITER_SIZES[sk][0] * len(corpora.CRON_EXPRS),
        divided_label="cron step",
    ),
    DuelSpec(
        duel_id="obspy",
        title="Konno-Ohmachi smoothing",
        blurb="obspy-mojo vs ObsPy konno_ohmachi_smoothing",
        metric_label="per-call latency (lower is better)",
        unit_label="one smoothing call",
        config_note="bandwidth=40 count=1 defaults; L cell runs ObsPy's batched matrix path (its best config)",
        sizes=OBSPY_SIZES,
        build=_obspy_build,
        make_lanes=_obspy_lanes,
        gate=_obspy_gate,
    ),
    DuelSpec(
        duel_id="cclib",
        title="Electron density on grids (benzene 6-31G*)",
        blurb="cclib-mojo vs cclib's pure-Python PyQuante1 grid loop",
        metric_label="per-call latency (lower is better)",
        unit_label="one grid evaluation",
        config_note="the exact hot loop cclib runs per grid point (published harness oracle)",
        sizes=CCLIB_SIZES,
        build=_cclib_build,
        make_lanes=_cclib_lanes,
        gate=_cclib_gate,
    ),
    DuelSpec(
        duel_id="pydicom",
        title="DICOM RLE Lossless decode",
        blurb="pydicom-mojo vs pydicom's pure-Python RLE decoder",
        metric_label="per-batch latency (lower is better)",
        unit_label="decode of a CT-style frame batch",
        config_note="512×512 16-bit frames, RLE-encoded by the oracle's own encoder up front",
        sizes=PYDICOM_SIZES,
        build=_pydicom_build,
        make_lanes=_pydicom_lanes,
        gate=_pydicom_gate,
        unit_divisor=lambda sk: PYDICOM_SIZES[sk][0],
        divided_label="frame",
    ),
    DuelSpec(
        duel_id="nuscenes",
        title="nuScenes detection metrics",
        blurb="nuscenes-eval-mojo vs nuscenes-devkit DetectionEval chain",
        metric_label="per-evaluation latency (lower is better)",
        unit_label="one full evaluation",
        config_note="the devkit's own post-DB-load chain, 10 classes × 4 distance thresholds",
        sizes=NUSCENES_SIZES,
        build=_nuscenes_build,
        make_lanes=_nuscenes_lanes,
        gate=_nuscenes_gate,
    ),
    DuelSpec(
        duel_id="motmetrics",
        title="MOTChallenge tracking metrics",
        blurb="motmetrics-mojo vs py-motmetrics on seeded MOT streams",
        metric_label="per-pipeline latency (lower is better)",
        unit_label="one accumulate+compute pipeline (18 metrics)",
        config_note="MOTAccumulator + MetricsHost, full MOTChallenge metric set",
        sizes=MOTMETRICS_SIZES,
        build=_motmetrics_build,
        make_lanes=_motmetrics_lanes,
        gate=_motmetrics_gate,
    ),
]

DUELS_BY_ID = {d.duel_id: d for d in DUELS}
