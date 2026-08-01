#!/usr/bin/env python
"""statsforecast 2.1.1 arm of the M4 joint-axis latency measurement.

Reads the SAME /tmp/m4work/s1/data blocks the Mojo arm reads, applies the SAME stride
sample, and calls the SAME three models the accuracy run established equality against:

  Holt   = AutoETS(season_length=1, model='AAN', damped=False)   on the deseasonalised series
  Damped = AutoETS(season_length=1, model='AAN', damped=True)    on the deseasonalised series
  ETSAAA = AutoETS(season_length=m, model='AAA', damped=False)   on the raw series

Emits the same COLD_WARM_HOT grammar as the Mojo arm. Data load is outside every timed
region. Every thread-affecting env var is asserted, not assumed.

argv: --dir --freq --m --h --n --mode --nsample --reps --workers --dispatch
  dispatch = percall  -> per-series `model.forecast(y, h)`, the cheapest sf path
             batch    -> StatsForecast(n_jobs=workers).forecast(df=..., h=...), sf's own
                         product path (pandas frame in, frame out)
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import platform
import sys
import time

import numpy as np

H = {'Yearly': 6, 'Quarterly': 8, 'Monthly': 18, 'Weekly': 13, 'Daily': 14, 'Hourly': 48}
M = {'Yearly': 1, 'Quarterly': 4, 'Monthly': 12, 'Weekly': 1, 'Daily': 1, 'Hourly': 24}
NSER = {'Yearly': 23000, 'Quarterly': 24000, 'Monthly': 48000, 'Weekly': 359,
        'Daily': 4227, 'Hourly': 414}
NAMES = ['Holt', 'Damped', 'ETSAAA']


def versions():
    import statsforecast
    out = {
        'python': sys.version.split()[0],
        'implementation': platform.python_implementation(),
        'numpy': np.__version__,
        'statsforecast': statsforecast.__version__,
    }
    try:
        import coreforecast
        out['coreforecast'] = coreforecast.__version__
    except Exception:
        out['coreforecast'] = 'ABSENT'
    try:
        import numba
        out['numba'] = numba.__version__
    except Exception:
        out['numba'] = 'ABSENT'
    assert out['statsforecast'] == '2.1.1', out
    assert out['implementation'] == 'CPython', out
    return out


def make(name, m):
    from statsforecast.models import AutoETS
    if name == 'Holt':
        return AutoETS(season_length=1, model='AAN', damped=False)
    if name == 'Damped':
        return AutoETS(season_length=1, model='AAN', damped=True)
    if name == 'ETSAAA':
        return AutoETS(season_length=m, model='AAA', damped=False)
    raise KeyError(name)


def load(d, freq, mode, nsample):
    n, h, m = NSER[freq], H[freq], M[freq]
    lens = np.fromfile(f'{d}/{freq}_lens.i64', dtype=np.int64)
    assert len(lens) == n, (len(lens), n)
    offs = np.concatenate(([0], np.cumsum(lens)))[:-1]
    raw = np.fromfile(f'{d}/{freq}_raw.f64', dtype=np.float64)
    des = np.fromfile(f'{d}/{freq}_des.f64', dtype=np.float64)
    if mode == 'full':
        idx = list(range(n))
    else:
        stride = max(1, n // nsample)
        idx = list(range(0, n, stride))[:nsample]
    R = [np.ascontiguousarray(raw[offs[i]:offs[i] + lens[i]]) for i in idx]
    D = [np.ascontiguousarray(des[offs[i]:offs[i] + lens[i]]) for i in idx]
    return R, D, m, h


def emit(label, reps, ns, workers, dispatch):
    cold, warm = reps[0], (reps[1] if len(reps) > 1 else reps[0])
    tail = reps[2:] if len(reps) > 2 else reps[1:2] if len(reps) > 1 else reps[:1]
    hot, hmax = min(tail), max(tail)
    print(f"COLD_WARM_HOT {label} {cold:.4f} {warm:.4f} {hot:.4f} ms", flush=True)
    print(f"  ROW {label} series={ns} workers={workers} dispatch={dispatch} "
          f"reps={len(reps)} cold_per_series_ms={cold / ns:.6f} "
          f"hot_per_series_ms={hot / ns:.6f} hot_disp={hmax / hot:.4f} "
          f"load1m={os.getloadavg()[0]:.1f}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', default='/tmp/m4work/s1/data')
    ap.add_argument('--freq', required=True)
    ap.add_argument('--mode', default='sample', choices=('sample', 'full'))
    ap.add_argument('--nsample', type=int, default=50)
    ap.add_argument('--reps', type=int, default=3)
    ap.add_argument('--workers', type=int, default=1)
    ap.add_argument('--dispatch', default='percall', choices=('percall', 'batch'))
    ap.add_argument('--methods', default=','.join(NAMES))
    ap.add_argument('--out-prefix', default='')
    a = ap.parse_args()

    v = versions()
    thr = {k: os.environ.get(k, '<unset>') for k in
           ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS',
            'VECLIB_MAXIMUM_THREADS', 'NUMEXPR_NUM_THREADS')}
    print('# ENV ' + json.dumps({'versions': v, 'thread_env': thr,
                                 'load1m': os.getloadavg()[0]}), flush=True)

    t0 = time.perf_counter()
    R, D, m, h = load(a.dir, a.freq, a.mode, a.nsample)
    print(f"COLD_WARM_HOT {a.freq}_load unresolved unresolved unresolved ms "
          f"load_ms={(time.perf_counter() - t0) * 1000:.3f}", flush=True)
    ns = len(R)

    if a.dispatch == 'batch':
        import pandas as pd
        from statsforecast import StatsForecast
        frames = {}
        for src, tag in ((R, 'raw'), (D, 'des')):
            ids = np.repeat(np.arange(ns), [len(y) for y in src])
            frames[tag] = pd.DataFrame({
                'unique_id': ids,
                'ds': np.concatenate([np.arange(1, len(y) + 1) for y in src]),
                'y': np.concatenate(src)})

    buf = np.empty((ns, h), dtype=np.float64)
    for name in a.methods.split(','):
        src = R if name == 'ETSAAA' else D
        reps = []
        for _ in range(a.reps):
            if a.dispatch == 'percall':
                mo = make(name, m)
                t = time.perf_counter()
                for i, y in enumerate(src):
                    try:
                        buf[i] = mo.forecast(y, h)['mean']
                    except Exception:
                        buf[i] = np.nan
                reps.append((time.perf_counter() - t) * 1000)
            else:
                from statsforecast import StatsForecast
                sf = StatsForecast(models=[make(name, m)], freq=1, n_jobs=a.workers)
                df = frames['raw' if name == 'ETSAAA' else 'des']
                t = time.perf_counter()
                sf.forecast(df=df, h=h)
                reps.append((time.perf_counter() - t) * 1000)
        emit(f"{a.freq}_{name}", reps, ns, a.workers, a.dispatch)
        if a.out_prefix and a.dispatch == 'percall':
            buf.tofile(f'{a.out_prefix}_{a.freq}_{name}.f64')
    print(f"ARM_DONE statsforecast {a.freq} {a.mode}", flush=True)


if __name__ == '__main__':
    main()
