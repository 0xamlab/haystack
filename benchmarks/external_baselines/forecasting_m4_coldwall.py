#!/usr/bin/env python
"""Cold decision latency: exec -> answer, measured from OUTSIDE both processes.

This is the number a live decision path actually faces on its first request: the
operating system is handed a command and has to come back with a forecast. It includes
every fixed cost each stack pays before it can compute anything — for statsforecast that
is CPython startup plus `import statsforecast`/`import numpy`; for Algenta it is the
AOT-compiled binary's process launch.

One reading per process launch, strictly interleaved A/B, K launches each, min-of-K.
Both arms do the SAME job: read the frequency's blocks off disk, fit ONE series, forecast.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import statistics
import subprocess
import time

ROOT = os.environ.get('M4_REPO_ROOT',
        str(pathlib.Path(__file__).resolve().parents[2]))
DATA = os.environ.get('M4_DATA', '/tmp/m4work/s1/data')
REF_PYTHON = os.environ.get('M4_REF_PYTHON', '/tmp/bb/bin/python')
SPEC = {'Yearly': (1, 6, 23000), 'Quarterly': (4, 8, 24000), 'Monthly': (12, 18, 48000),
        'Weekly': (1, 13, 359), 'Daily': (1, 14, 4227), 'Hourly': (24, 48, 414)}
THREAD_ENV = {'OMP_NUM_THREADS': '1', 'OPENBLAS_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1',
              'VECLIB_MAXIMUM_THREADS': '1', 'NUMEXPR_NUM_THREADS': '1'}


def wall(cmd, env=None, cwd=None):
    e = dict(os.environ)
    if env:
        e.update(env)
    t = time.perf_counter()
    p = subprocess.run(cmd, capture_output=True, text=True, env=e, cwd=cwd)
    el = (time.perf_counter() - t) * 1000
    return el, p.returncode, p.stdout + p.stderr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('-K', type=int, default=7)
    ap.add_argument('--freq', default='Monthly')
    ap.add_argument('--method', default='ETSAAA')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    m, h, n = SPEC[a.freq]
    A = [f'{ROOT}/build/joint/forecasting_m4_h2h', DATA, a.freq, str(m), str(h), str(n),
         'sample', '1', '1', '1', a.method]
    B = [REF_PYTHON, '-P', f'{ROOT}/benchmarks/external_baselines/forecasting_m4_refs.py', '--dir', DATA,
         '--freq', a.freq, '--mode', 'sample', '--nsample', '1', '--reps', '1',
         '--methods', a.method]
    ra, rb, loads = [], [], []
    for _ in range(a.K):
        loads.append(os.getloadavg()[0])
        el, rc, out = wall(A)
        assert rc == 0, out[-2000:]
        ra.append(el)
        loads.append(os.getloadavg()[0])
        el, rc, out = wall(B, env=THREAD_ENV)
        assert rc == 0, out[-2000:]
        rb.append(el)
    res = dict(freq=a.freq, method=a.method, K=a.K,
               a_ms=dict(min=min(ra), median=statistics.median(ra), max=max(ra), all=ra),
               b_ms=dict(min=min(rb), median=statistics.median(rb), max=max(rb), all=rb),
               ratio_min=min(rb) / min(ra), ratio_median=statistics.median(rb) / statistics.median(ra),
               load_1m=dict(min=min(loads), median=statistics.median(loads), max=max(loads)))
    json.dump(res, open(a.out, 'w'), indent=1)
    print('COLDWALL ' + json.dumps({k: v for k, v in res.items() if k != 'load_1m'}),
          flush=True)
    print(f'  {a.freq}/{a.method}: algenta exec->answer min {min(ra):.1f} ms  '
          f'statsforecast min {min(rb):.1f} ms  ratio {min(rb) / min(ra):.1f}x  '
          f'load1m med {statistics.median(loads):.0f}', flush=True)


if __name__ == '__main__':
    main()
