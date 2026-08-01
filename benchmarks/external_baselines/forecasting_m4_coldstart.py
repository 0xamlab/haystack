#!/usr/bin/env python
"""What statsforecast 2.1.1 pays before its first forecast, in a FRESH process.

The protocol assumed a Numba JIT cost. This asserts what is actually there:
  * numba present/absent
  * the compiled extension modules that back AutoETS
  * import wall clock, split into `import statsforecast` and first-model construction
  * first-call vs second-call on ONE series, so any lazy per-shape compilation would show
    up as first >> second

Run one measurement per process launch (a cold reading cannot be repeated in-process).
argv: --freq --idx
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import time

t_proc = time.perf_counter()
import numpy as np  # noqa: E402

t_np = time.perf_counter()

H = {'Yearly': 6, 'Quarterly': 8, 'Monthly': 18, 'Weekly': 13, 'Daily': 14, 'Hourly': 48}
M = {'Yearly': 1, 'Quarterly': 4, 'Monthly': 12, 'Weekly': 1, 'Daily': 1, 'Hourly': 24}
D = os.environ.get('M4_DATA', '/tmp/m4work/s1/data')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--freq', default='Monthly')
    ap.add_argument('--idx', type=int, default=0)
    ap.add_argument('--method', default='ETSAAA')
    a = ap.parse_args()

    t0 = time.perf_counter()
    import statsforecast
    from statsforecast.models import AutoETS
    t1 = time.perf_counter()

    has_numba = True
    try:
        import numba  # noqa: F401
    except Exception:
        has_numba = False

    ext = []
    for mod in ('statsforecast._lib', 'coreforecast._lib'):
        try:
            __import__(mod)
            ext.append({'module': mod, 'file': sys.modules[mod].__file__})
        except Exception as e:
            ext.append({'module': mod, 'error': repr(e)})

    freq, h, m = a.freq, H[a.freq], M[a.freq]
    lens = np.fromfile(f'{D}/{freq}_lens.i64', dtype=np.int64)
    offs = np.concatenate(([0], np.cumsum(lens)))[:-1]
    src = 'raw' if a.method == 'ETSAAA' else 'des'
    flat = np.fromfile(f'{D}/{freq}_{src}.f64', dtype=np.float64)
    y0 = np.ascontiguousarray(flat[offs[a.idx]:offs[a.idx] + lens[a.idx]])
    y1 = np.ascontiguousarray(flat[offs[a.idx + 1]:offs[a.idx + 1] + lens[a.idx + 1]])

    t2 = time.perf_counter()
    if a.method == 'ETSAAA':
        mo = AutoETS(season_length=m, model='AAA', damped=False)
    elif a.method == 'Holt':
        mo = AutoETS(season_length=1, model='AAN', damped=False)
    else:
        mo = AutoETS(season_length=1, model='AAN', damped=True)
    t3 = time.perf_counter()

    t4 = time.perf_counter()
    mo.forecast(y0, h)
    t5 = time.perf_counter()
    mo.forecast(y1, h)
    t6 = time.perf_counter()
    # third call, back on the FIRST series: isolates per-shape work from per-series work
    mo.forecast(y0, h)
    t7 = time.perf_counter()

    out = {
        'freq': freq, 'method': a.method, 'idx': a.idx,
        'series_len_first': int(lens[a.idx]), 'series_len_second': int(lens[a.idx + 1]),
        'numba_installed': has_numba,
        'compiled_extensions': ext,
        'statsforecast': statsforecast.__version__,
        'numpy': np.__version__, 'python': sys.version.split()[0],
        'ms': {
            'interpreter_to_numpy_imported': (t_np - t_proc) * 1000,
            'import_statsforecast': (t1 - t0) * 1000,
            'model_construct': (t3 - t2) * 1000,
            'first_forecast_call': (t5 - t4) * 1000,
            'second_forecast_call_other_series': (t6 - t5) * 1000,
            'third_forecast_call_first_series_again': (t7 - t6) * 1000,
        },
        'load1m': os.getloadavg()[0],
    }
    print('COLDSTART ' + json.dumps(out), flush=True)


if __name__ == '__main__':
    main()
