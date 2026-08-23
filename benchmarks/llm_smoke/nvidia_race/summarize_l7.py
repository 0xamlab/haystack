#!/usr/bin/env python3
"""summarize_l7.py — round-3 A100 race summary: pulls agg tok/s / TTFT p50 / TPOT p50 per
cell from enterprise_bench.json outputs of the named arms and prints one comparison table.

Usage: python3 summarize_l7.py <arms.json>
where arms.json maps arm-name -> output-dir, e.g.:
  {"ctl3": "~/leverpush3/out_ctl3_chat", "l7s2": "~/leverpush3/out_l7s2_chat", ...}
"""
import json, os, sys


def load(path: str):
    p = os.path.expanduser(os.path.join(path, "enterprise_bench.json"))
    if not os.path.exists(p):
        return None
    return json.load(open(p))


def main() -> int:
    arms = json.load(open(sys.argv[1]))
    tables = {}
    for arm, outdir in arms.items():
        rep = load(outdir)
        if rep is None:
            print(f"!! {arm}: no enterprise_bench.json under {outdir}")
            continue
        for row in rep.get("concurrency", []):
            c = row.get("concurrency")
            tables.setdefault(c, {})[arm] = row
    cells = sorted(tables.keys(), key=lambda x: (x is None, x))
    cols = list(arms.keys())
    print("| cell | metric | " + " | ".join(cols) + " |")
    print("|" + "---|" * (len(cols) + 2))
    for c in cells:
        label = f"C={c}"
        for metric, key in (
            ("agg tok/s", "agg_tok_s"),
            ("TTFT p50 ms", "ttft_ms_p50"),
            ("TPOT p50 ms", "tpot_ms_p50"),
            ("ok/reqs", None),
        ):
            vals = []
            for arm in cols:
                row = tables[c].get(arm)
                if row is None:
                    vals.append("—")
                    continue
                if key is None:
                    vals.append(f"{row.get('completed')}/{row.get('requests')}")
                else:
                    v = row.get(key)
                    vals.append("—" if v is None else f"{v:.1f}")
            print(f"| {label} | {metric} | " + " | ".join(vals) + " |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
