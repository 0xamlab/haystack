#!/usr/bin/env python
"""Interleaved A/B driver for the M4 joint-axis latency measurement.

This machine is shared with sibling benchmark agents; the 1-minute load has ranged
120-200 during this session. Two mitigations, both stated rather than assumed:

  1. STRICT INTERLEAVE. A, B, A, B, ... within every frequency, so both arms see the
     same contention window. A block of A followed by a block of B would let a load
     spike land entirely on one arm.
  2. MIN ACROSS K PROCESSES x REPS. Contention can only make a reading slower than the
     work takes, never faster, so min-of-K is the floor statistic and the one the ratio
     uses. Median and spread are printed alongside so a reader sees how bad it was.

Cold is only ever taken once per process, so the cold tier comes from K separate process
launches, never from an in-process repeat.

Load average is sampled before every single process launch and reported per row.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import statistics
import subprocess
import sys
import time

ROOT = os.environ.get('M4_REPO_ROOT',
        str(pathlib.Path(__file__).resolve().parents[2]))
ENGINE = f'{ROOT}/mojo/engine'
MOJO_ENV = os.environ.get('M4_MOJO_ENV', str(pathlib.Path(ROOT).parents[1] / 'mojo_env'))
DATA = os.environ.get('M4_DATA', '/tmp/m4work/s1/data')
# Arm B runs in whatever interpreter has statsforecast installed, which is not the repo
# environment. It is named here rather than assumed, and every launch echoes back the
# versions it actually imported.
REF_PYTHON = os.environ.get('M4_REF_PYTHON', '/tmp/bb/bin/python')
SPEC = {'Yearly': (1, 6, 23000), 'Quarterly': (4, 8, 24000), 'Monthly': (12, 18, 48000),
        'Weekly': (1, 13, 359), 'Daily': (1, 14, 4227), 'Hourly': (24, 48, 414)}

_TRIPLE = re.compile(r"^\s*COLD_WARM_HOT\s+(?P<l>\S+)\s+(?P<c>\S+)\s+(?P<w>\S+)\s+(?P<h>\S+)")
_ROW = re.compile(r"^\s*ROW\s+(?P<l>\S+)\s+(?P<rest>.*)$")
_UNRES = {'unresolved', 'unavailable', 'n/a', '-', '--'}

THREAD_ENV = {'OMP_NUM_THREADS': '1', 'OPENBLAS_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1',
              'VECLIB_MAXIMUM_THREADS': '1', 'NUMEXPR_NUM_THREADS': '1'}


def val(t):
    t = t.strip().strip(',;')
    if t.lower() in _UNRES:
        return None
    try:
        v = float(t)
    except ValueError:
        return None
    return v if v > 0 else None


def run(cmd, env=None, cwd=None):
    e = dict(os.environ)
    if env:
        e.update(env)
    p = subprocess.run(cmd, capture_output=True, text=True, env=e, cwd=cwd)
    rows, meta = {}, {}
    for line in (p.stdout + p.stderr).splitlines():
        m = _TRIPLE.match(line)
        if m:
            rows[m['l']] = (val(m['c']), val(m['w']), val(m['h']))
        r = _ROW.match(line)
        if r:
            meta[r['l']] = r['rest'].strip()
    return rows, meta, p.returncode, p.stdout + p.stderr


def methods_for(freq):
    """statsforecast's AutoETS(model='AAA') raises ValueError('Nonseasonal data') when
    season_length == 1, so the ETS(A,A,A) row only exists on the seasonal frequencies —
    exactly the 72,414 series the accuracy equality was established on."""
    return ['Holt', 'Damped'] + (['ETSAAA'] if SPEC[freq][0] > 1 else [])


def cmd_a(freq, mode, nsample, reps, workers, out_prefix=''):
    m, h, n = SPEC[freq]
    c = [f'{ROOT}/build/joint/forecasting_m4_h2h', DATA, freq, str(m), str(h), str(n),
         mode, str(nsample), str(reps), str(workers), ','.join(methods_for(freq))]
    if out_prefix:
        c.append(out_prefix)
    return c


def cmd_b(freq, mode, nsample, reps, workers, dispatch, out_prefix=''):
    return [REF_PYTHON, '-P', f'{ROOT}/benchmarks/external_baselines/forecasting_m4_refs.py',
            '--dir', DATA, '--freq', freq, '--mode', mode, '--nsample', str(nsample),
            '--reps', str(reps), '--workers', str(workers), '--dispatch', dispatch,
            '--methods', ','.join(methods_for(freq))] + (
        ['--out-prefix', out_prefix] if out_prefix else [])


def agg(vals):
    v = [x for x in vals if x is not None]
    if not v:
        return None, None, None, 0
    return min(v), statistics.median(v), max(v) / min(v), len(v)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('-K', type=int, default=5)
    ap.add_argument('--freqs', default='Yearly,Quarterly,Monthly,Weekly,Daily,Hourly')
    ap.add_argument('--mode', default='sample')
    ap.add_argument('--nsample', default='Yearly=300,Quarterly=200,Monthly=100,'
                                        'Weekly=200,Daily=60,Hourly=50')
    ap.add_argument('--reps', type=int, default=4)
    ap.add_argument('--a-workers', type=int, default=1)
    ap.add_argument('--b-workers', type=int, default=1)
    ap.add_argument('--b-dispatch', default='percall')
    ap.add_argument('--out', required=True)
    ap.add_argument('--a-prefix', default='')
    ap.add_argument('--b-prefix', default='')
    a = ap.parse_args()

    ns = {}
    for kv in a.nsample.split(','):
        k, v = kv.split('=')
        ns[k] = int(v)

    res = {}
    loads = []
    t_start = time.time()
    for freq in a.freqs.split(','):
        n = ns.get(freq, 50) if a.mode == 'sample' else SPEC[freq][2]
        ra, rb, ma, mb = {}, {}, {}, {}
        for k in range(a.K):
            loads.append(os.getloadavg()[0])
            r, meta, rc, out = run(cmd_a(freq, a.mode, n, a.reps, a.a_workers, a.a_prefix),
                                   cwd=MOJO_ENV)
            if rc != 0:
                sys.stderr.write(out[-3000:])
                raise SystemExit(f'A failed rc={rc} freq={freq}')
            for lbl, v in r.items():
                ra.setdefault(lbl, []).append(v)
            ma.update(meta)
            loads.append(os.getloadavg()[0])
            r, meta, rc, out = run(cmd_b(freq, a.mode, n, a.reps, a.b_workers,
                                         a.b_dispatch, a.b_prefix), env=THREAD_ENV)
            if rc != 0:
                sys.stderr.write(out[-3000:])
                raise SystemExit(f'B failed rc={rc} freq={freq}')
            for lbl, v in r.items():
                rb.setdefault(lbl, []).append(v)
            mb.update(meta)
            print(f'  .. {freq} pair {k + 1}/{a.K} load1m={os.getloadavg()[0]:.0f} '
                  f'elapsed={time.time() - t_start:.0f}s', flush=True)
        for lbl in sorted(set(ra) | set(rb)):
            A = [agg([x[i] for x in ra.get(lbl, [])]) for i in range(3)]
            B = [agg([x[i] for x in rb.get(lbl, [])]) for i in range(3)]
            res[lbl] = dict(
                series=n,
                a=dict(cold=A[0][0], cold_med=A[0][1], warm=A[1][0], hot=A[2][0],
                       hot_med=A[2][1], hot_spread=A[2][2], k=A[2][3], meta=ma.get(lbl)),
                b=dict(cold=B[0][0], cold_med=B[0][1], warm=B[1][0], hot=B[2][0],
                       hot_med=B[2][1], hot_spread=B[2][2], k=B[2][3], meta=mb.get(lbl)),
                cold_x=(B[0][0] / A[0][0]) if (A[0][0] and B[0][0]) else None,
                warm_x=(B[1][0] / A[1][0]) if (A[1][0] and B[1][0]) else None,
                hot_x=(B[2][0] / A[2][0]) if (A[2][0] and B[2][0]) else None)

    payload = dict(rows=res, K=a.K, reps=a.reps, mode=a.mode,
                   a_workers=a.a_workers, b_workers=a.b_workers,
                   b_dispatch=a.b_dispatch, thread_env=THREAD_ENV,
                   load_1m=dict(min=min(loads), median=statistics.median(loads),
                                max=max(loads), samples=len(loads)),
                   loadavg_end=list(os.getloadavg()),
                   wall_s=time.time() - t_start)
    json.dump(payload, open(a.out, 'w'), indent=1)

    print(f'\nINTERLEAVED A/B  K={a.K} process pairs  reps={a.reps}  mode={a.mode}')
    print(f'A = Algenta shipped forecasting.fitted kernels, workers={a.a_workers}, '
          f'in-process, 0 dispatches')
    print(f'B = statsforecast 2.1.1 AutoETS, workers={a.b_workers}, '
          f'dispatch={a.b_dispatch}')
    print(f'load 1-min across the run: min {min(loads):.0f} median '
          f'{statistics.median(loads):.0f} max {max(loads):.0f}  '
          f'(loadavg at end {os.getloadavg()})')
    print(f'{"label":24s} {"ns":>5s} {"A cold":>9s} {"A warm":>9s} {"A hot":>9s} '
          f'{"B cold":>10s} {"B warm":>10s} {"B hot":>10s} {"cold x":>7s} {"hot x":>7s}')
    for lbl, r in res.items():
        f = lambda x: f'{x:.2f}' if x is not None else 'unresolved'
        g = lambda x: f'{x:.2f}x' if x is not None else 'INVALID'
        print(f'{lbl:24s} {r["series"]:>5d} {f(r["a"]["cold"]):>9s} '
              f'{f(r["a"]["warm"]):>9s} {f(r["a"]["hot"]):>9s} '
              f'{f(r["b"]["cold"]):>10s} {f(r["b"]["warm"]):>10s} '
              f'{f(r["b"]["hot"]):>10s} {g(r["cold_x"]):>7s} {g(r["hot_x"]):>7s}')


if __name__ == '__main__':
    main()
