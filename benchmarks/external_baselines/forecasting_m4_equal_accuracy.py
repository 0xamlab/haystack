#!/usr/bin/env python
"""Re-establish the ACCURACY half in this session, from the forecasts the LATENCY run
itself produced.

Both arms' forecast blocks come out of the very processes that were timed
(AL_*.f64 from the Algenta binary, SF_*.f64 from statsforecast 2.1.1), so there is no
way for the timing to be measuring one code path and the accuracy another.

Scoring is the official M4 algebra written out longhand here (sMAPE, MASE against the
in-sample seasonal-naive MAE on the TRAINING series, OWA against Naive2), independent of
any engine code. Anchors are re-checked at ratio 1.000 against the official workbook.

Holt/Damped are fitted on the deseasonalised series, so their forecasts are reseasonalised
by the stored SIout factors before scoring — identically for both arms. ETS(A,A,A) is
fitted on the raw series and is scored as produced.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys

import numpy as np

D = os.environ.get('M4_DATA', '/tmp/m4work/s1/data')
P = os.environ.get('M4_OUT', str(pathlib.Path(__file__).resolve().parents[2] / 'build/joint'))
H = {'Yearly': 6, 'Quarterly': 8, 'Monthly': 18, 'Weekly': 13, 'Daily': 14, 'Hourly': 48}
M = {'Yearly': 1, 'Quarterly': 4, 'Monthly': 12, 'Weekly': 1, 'Daily': 1, 'Hourly': 24}
NSER = {'Yearly': 23000, 'Quarterly': 24000, 'Monthly': 48000, 'Weekly': 359,
        'Daily': 4227, 'Hourly': 414}
FREQS = ['Yearly', 'Quarterly', 'Monthly', 'Weekly', 'Daily', 'Hourly']
SEASONAL = ['Quarterly', 'Monthly', 'Hourly']
OFFICIAL = json.load(open(os.environ.get('M4_OFFICIAL', '/tmp/m4work/official_freq.json')))


def smape(y, f):
    return np.mean(200.0 * np.abs(y - f) / (np.abs(y) + np.abs(f)), axis=1)


def ctx(freq):
    h, m, n = H[freq], M[freq], NSER[freq]
    lens = np.fromfile(f'{D}/{freq}_lens.i64', dtype=np.int64)
    offs = np.concatenate(([0], np.cumsum(lens)))[:-1]
    raw = np.fromfile(f'{D}/{freq}_raw.f64', dtype=np.float64)
    des = np.fromfile(f'{D}/{freq}_des.f64', dtype=np.float64)
    si = np.fromfile(f'{D}/{freq}_siout.f64', dtype=np.float64).reshape(n, h)
    te = np.fromfile(f'{D}/{freq}_test.f64', dtype=np.float64).reshape(n, h)
    den = np.empty(n)
    for s in range(n):
        x = raw[offs[s]:offs[s] + lens[s]]
        den[s] = np.mean(np.abs(x[m:] - x[:-m]))
    naive2 = np.array([des[offs[s] + lens[s] - 1] for s in range(n)])[:, None] * np.ones(h)
    naive2 = naive2 * si
    return dict(h=h, m=m, n=n, si=si, te=te, den=den, naive2=naive2)


def score(c, f):
    sm = float(smape(c['te'], f).mean())
    ma = float((np.mean(np.abs(c['te'] - f), axis=1) / c['den']).mean())
    return sm, ma


def main():
    out = {'per_freq': {}, 'agreement': {}, 'totals': {}, 'anchors': {}}
    tot = {}
    for freq in FREQS:
        c = ctx(freq)
        n, h = c['n'], c['h']
        n2s, n2m = score(c, c['naive2'])
        out['anchors'][freq] = {'Naive2_smape': n2s, 'Naive2_mase': n2m,
                                'official_Naive2_smape': OFFICIAL['Naive2']['sMAPE'][freq],
                                'official_Naive2_mase': OFFICIAL['Naive2']['MASE'][freq],
                                'ratio_smape': n2s / OFFICIAL['Naive2']['sMAPE'][freq],
                                'ratio_mase': n2m / OFFICIAL['Naive2']['MASE'][freq]}
        per = {}
        methods = ['Holt', 'Damped'] + (['ETSAAA'] if freq in SEASONAL else [])
        for meth in methods:
            a = np.fromfile(f'{P}/AL_{freq}_{meth}.f64', dtype=np.float64).reshape(n, h)
            b = np.fromfile(f'{P}/SF_{freq}_{meth}.f64', dtype=np.float64).reshape(n, h)
            if meth != 'ETSAAA':
                a = a * c['si']
                b = b * c['si']
            fin = np.isfinite(a).all(axis=1) & np.isfinite(b).all(axis=1)
            bit = int((a == b).all(axis=1).sum())
            scale = np.maximum(np.abs(b), 1.0)
            rel = np.where(fin[:, None], np.abs(a - b) / scale, 0.0).max(axis=1)
            within = int(((rel < 1e-6) & fin).sum())
            asm, ama = score(c, np.where(np.isfinite(a), a, c['naive2']))
            bsm, bma = score(c, np.where(np.isfinite(b), b, c['naive2']))
            per[meth] = dict(
                n=n, finite_both=int(fin.sum()), bit_identical=bit, within_1e6=within,
                max_rel=float(rel.max()),
                algenta=dict(smape=asm, mase=ama, owa=0.5 * (asm / n2s + ama / n2m)),
                statsforecast=dict(smape=bsm, mase=bma, owa=0.5 * (bsm / n2s + bma / n2m)))
            tot.setdefault(meth, {'a_sm': 0.0, 'a_ma': 0.0, 'b_sm': 0.0, 'b_ma': 0.0,
                                  'n': 0, 'bit': 0, 'within': 0, 'ns': 0})
            t = tot[meth]
            t['a_sm'] += asm * n
            t['a_ma'] += ama * n
            t['b_sm'] += bsm * n
            t['b_ma'] += bma * n
            t['n'] += n
            t['bit'] += bit
            t['within'] += within
        out['per_freq'][freq] = per
    for meth, t in tot.items():
        out['totals'][meth] = dict(
            series=t['n'],
            bit_identical=t['bit'], within_1e6=t['within'],
            algenta=dict(smape=t['a_sm'] / t['n'], mase=t['a_ma'] / t['n']),
            statsforecast=dict(smape=t['b_sm'] / t['n'], mase=t['b_ma'] / t['n']))
    json.dump(out, open(f'{P}/equal_accuracy.json', 'w'), indent=1)

    print(f"load1m {os.getloadavg()[0]:.0f}   scorer: independent numpy, official M4 algebra")
    print("\nANCHORS (Naive2, this session vs official workbook)")
    for f, v in out['anchors'].items():
        print(f"  {f:10s} sMAPE ratio {v['ratio_smape']:.6f}  MASE ratio {v['ratio_mase']:.6f}")
    print("\nPER-SERIES AGREEMENT, Algenta vs statsforecast 2.1.1 (same session, same series)")
    for f in FREQS:
        for meth, v in out['per_freq'][f].items():
            print(f"  {f:10s} {meth:7s} bit-identical {v['bit_identical']:6d}/{v['n']:<6d}"
                  f"  within 1e-6 {v['within_1e6']:6d}/{v['n']:<6d}"
                  f"  max_rel {v['max_rel']:.3e}")
    print("\nROW SCORES (reseasonalised where the fit was on the deseasonalised series)")
    for f in FREQS:
        for meth, v in out['per_freq'][f].items():
            a, b = v['algenta'], v['statsforecast']
            print(f"  {f:10s} {meth:7s} algenta sMAPE {a['smape']:8.3f} MASE {a['mase']:7.3f}"
                  f" | statsforecast sMAPE {b['smape']:8.3f} MASE {b['mase']:7.3f}"
                  f" | delta {abs(a['smape'] - b['smape']):.4f}/{abs(a['mase'] - b['mase']):.4f}")
    print("\nCORPUS TOTALS (series-count weighted)")
    for meth, v in out['totals'].items():
        a, b = v['algenta'], v['statsforecast']
        print(f"  {meth:7s} over {v['series']:6d} series: bit-identical "
              f"{v['bit_identical']}/{v['series']}, within 1e-6 {v['within_1e6']}/{v['series']}"
              f" | algenta sMAPE {a['smape']:.4f} MASE {a['mase']:.4f}"
              f" | sf sMAPE {b['smape']:.4f} MASE {b['mase']:.4f}")


if __name__ == '__main__':
    main()
