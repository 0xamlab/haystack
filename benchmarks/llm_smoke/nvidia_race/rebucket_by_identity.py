#!/usr/bin/env python3
"""Full re-bucket of the window15 rag4096 trace using the DIFFERENTIALLY-DERIVED kernel identity
table, instead of the extractor's name-substring rules. Reads the sqlite locally (no VM).

Region basis is identical to mr_extract_gemma3_round7.py --from-first-attn: start at the first
launch whose name matches 'fa_g3_window', so model load / weight staging is excluded.
"""
import json, sqlite3, sys, collections

DB = sys.argv[1] if len(sys.argv) > 1 else "/private/tmp/gemma_artifacts/window15_g3rag.sqlite"
IDENT = json.load(open(sys.argv[2]))["symbols"] if len(sys.argv) > 2 else {}

con = sqlite3.connect(DB)
cur = con.cursor()
# nsys stores kernel names in StringIds; the kernel table references them by id
tabs = {r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")}
kt = "CUPTI_ACTIVITY_KIND_KERNEL" if "CUPTI_ACTIVITY_KIND_KERNEL" in tabs else None
if kt is None:
    print("no kernel table found; tables:", sorted(tabs)[:20]); sys.exit(1)
cols = {r[1] for r in cur.execute(f"PRAGMA table_info({kt})")}
namecol = "demangledName" if "demangledName" in cols else ("shortName" if "shortName" in cols else None)
q = f"SELECT k.start, k.end, s.value FROM {kt} k JOIN StringIds s ON s.id = k.{namecol}"
rows = list(cur.execute(q))
rows.sort(key=lambda r: r[0])
print(f"total kernel records: {len(rows)}")

# region start = first fa_g3_window launch
start_i = next((i for i, r in enumerate(rows) if "fa_g3_window" in r[2]), None)
if start_i is None:
    print("NO fa_g3_window launch — region undefined"); sys.exit(1)
print(f"region starts at record {start_i} of {len(rows)} "
      f"(excluding {start_i} leading records = "
      f"{sum(r[1]-r[0] for r in rows[:start_i])/1e6:.3f} ms busy as model load)")
reg = rows[start_i:]
busy = sum(r[1] - r[0] for r in reg) / 1e6
print(f"region: n={len(reg)} busy={busy:.3f} ms\n")

per = collections.defaultdict(lambda: [0, 0.0])
for s, e, n in reg:
    per[n][0] += 1
    per[n][1] += (e - s) / 1e6

def ident(name):
    h = name.rsplit("_", 1)[-1]
    d = IDENT.get(name) or IDENT.get(h)
    if d and d.get("removed_by"):
        return "IDENTIFIED via -D removal of " + "/".join(d["removed_by"])
    return ""

print(f"{'ms':>9} {'%busy':>6} {'n':>5}  kernel / identity")
print("-" * 118)
tot_ident = 0.0
for name, (n, ms) in sorted(per.items(), key=lambda kv: -kv[1][1]):
    h = name.rsplit("_", 1)[-1]
    d = IDENT.get(name)
    tag = ""
    if d and d.get("removed_by"):
        tag = "  <= " + "/".join(d["removed_by"])
        tot_ident += ms
    short = name if len(name) < 74 else name[:71] + "..."
    print(f"{ms:9.3f} {100*ms/busy:6.2f} {n:5d}  {short}{tag}")
print("-" * 118)
print(f"differentially IDENTIFIED: {tot_ident:.3f} ms = {100*tot_ident/busy:.2f}% of region busy")
print(f"region busy total        : {busy:.3f} ms")
