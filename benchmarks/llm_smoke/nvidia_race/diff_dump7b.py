"""diff_dump7b.py — diff the engine's DUMP7B checksum lines against dump_transformers_cpu.py's
DUMPTF lines and report the FIRST diverging stage (the 7B-lane correctness bisection).

Usage:
    python3 diff_dump7b.py --engine /tmp/w7b/gate/engine_dump.log --tf /tmp/w7b/gate/dump_tf.txt

The engine file may be a full driver log; only lines starting with DUMP7B are read. Two stages
AGREE when sum/max/v0/v1 all match within REL_TOL relative (f32-vs-f32 math through 28 layers
drifts ~1e-5..1e-4 relatively; a real divergence is many orders past that).
"""

import argparse
from pathlib import Path

REL_TOL = 5e-3


def _parse(lines, tag):
    rows = {}
    for raw in lines:
        raw = raw.strip()
        if not raw.startswith(tag + "|"):
            continue
        f = raw.split("|")
        if len(f) < 8:
            continue  # the logits_top / token0 specials
        try:
            layer, stage = int(f[1]), f[2]
            n, s, mx, v0, v1 = int(f[3]), float(f[4]), float(f[5]), float(f[6]), float(f[7])
        except ValueError:
            continue  # non-checksum specials (logits_top carries idx:val pairs)
        rows[(layer, stage)] = (n, s, mx, v0, v1)
    return rows


def _rel(a, b):
    denom = max(abs(b), 1e-30)
    return abs(a - b) / denom


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", required=True)
    ap.add_argument("--tf", required=True)
    args = ap.parse_args()

    eng = _parse(Path(args.engine).read_text().splitlines(), "DUMP7B")
    tf = _parse(Path(args.tf).read_text().splitlines(), "DUMPTF")
    print(f"engine stages: {len(eng)} | tf stages: {len(tf)}")

    layers = sorted({k[0] for k in tf if k[0] >= 0})
    seq = [(-1, "embed")] + [
        (lyr, st)
        for lyr in layers
        for st in ("xn1", "qkv", "qrot", "attn", "post_attn", "xn2", "act", "post_mlp")
    ]

    first_bad = None
    checked = 0
    for key in seq:
        if key not in tf:
            continue
        if key not in eng:
            print(f"MISSING in engine dump: layer={key[0]} stage={key[1]}")
            continue
        checked += 1
        (ne, se, me, e0, e1) = eng[key]
        (nt, st_, mt, t0, t1) = tf[key]
        if ne != nt:
            print(f"WIDTH MISMATCH layer={key[0]} stage={key[1]}: engine n={ne} tf n={nt}")
        ds, dm, d0, d1 = _rel(se, st_), _rel(me, mt), _rel(e0, t0), _rel(e1, t1)
        worst = max(ds, dm, d0, d1)
        ok = worst <= REL_TOL
        if not ok and first_bad is None:
            first_bad = key
        if not ok or key[0] < 1 or key[1] in ("post_attn", "post_mlp"):
            print(f"{'ok' if ok else 'DIVERGED':>8} layer={key[0]:>2} stage={key[1]:<9} "
                  f"sum_rel={ds:.2e} max_rel={dm:.2e} v0_rel={d0:.2e} v1_rel={d1:.2e} "
                  f"| eng sum={se:.6g} tf sum={st_:.6g}")
        if not ok:
            break

    if first_bad is None:
        print(f"ALL {checked} compared stages AGREE within rel tol {REL_TOL}")
    else:
        print(f"FIRST DIVERGENCE: layer={first_bad[0]} stage={first_bad[1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
