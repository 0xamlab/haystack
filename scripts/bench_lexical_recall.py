#!/usr/bin/env python3
"""Dense vs lexical vs hybrid recall on the A-Z snapshot, using the memory-engine DEV stack.

The installed telys 0.1.0b3 stack is vector-only: a bare-qualname query lands its own unit at rank
~1933 of 53k (cosine dilution — the unit text is qualname+docstring+2000-char source slice, the
query is 60 chars). The dev tree (telys-sdk + memengine-py) adds an on-device per-partition
BM25-style lexical index. This bench measures, on the SAME extraction and the SAME 20 ground-truth
probes as bench_codna_telys_a2z.py:

  * recall@8 for mode=dense, mode=lexical, and a union hybrid
  * build_lexical cost on top of the vector ingest
  * per-query latency

Usage:
    python scripts/bench_lexical_recall.py --repo /tmp/a2z-localize/repo \
        --engine /Users/angel/Developer/memory-engine
"""

from __future__ import annotations

import argparse
import random
import sys
import time
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default="/tmp/a2z-localize/repo",
                    help="the snapshot bench_codna_telys_a2z.py extracted from")
    ap.add_argument("--engine", default="/Users/angel/Developer/memory-engine")
    ap.add_argument("--codna-cli", default="/Users/angel/Developer/codna/cli")
    ap.add_argument("--queries", type=int, default=20)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    engine = Path(args.engine).resolve()
    # dev SDK + dev memengine ahead of any installed telys/memengine
    sys.path.insert(0, str(engine / "packages" / "memengine-py"))
    sys.path.insert(0, str(engine / "packages" / "telys-sdk"))
    sys.path.append(str(Path(args.codna_cli).resolve()))

    import telys
    import memengine
    print(f"telys SDK: {telys.__file__} ({getattr(telys, '__version__', '?')})")
    print(f"memengine: {memengine.__file__}")
    from telys import Telys, scope_key  # noqa: E402
    from telys.embedding import AlgentaMultigramEmbedder  # noqa: E402
    from codna.codeunits import extract_repo  # noqa: E402

    t0 = time.perf_counter()
    units, stats = extract_repo(args.repo, "lexical-bench")
    print(f"extract: {stats.units} units in {time.perf_counter() - t0:.1f}s")

    emb = AlgentaMultigramEmbedder()
    db = "/tmp/lexical-bench-db"
    import shutil
    shutil.rmtree(db, ignore_errors=True)
    eng = Telys(db)
    col = eng.create_collection(
        "repo_symbols", dim=emb.profile.dimension, partition_by="scope_key", embedder=emb,
        filter_columns=["repo_id", "service", "language", "path", "symbol_type", "commit_sha", "branch"],
        lexical=True)

    repo_id = "lexical-bench"
    by_scope: dict[str, list] = {}
    for u in units:
        by_scope.setdefault(scope_key(repo_id, u.service or "", u.language), []).append(u)
    t0 = time.perf_counter()
    for scope, group in by_scope.items():
        col.upsert_texts([u.text for u in group], [u.id for u in group],
                          [dict(u.metadata(repo_id, scope), scope_key=scope) for u in group])
    dt_ingest = time.perf_counter() - t0
    t0 = time.perf_counter()
    lex_stats = col.build_lexical()
    dt_lex = time.perf_counter() - t0
    print(f"vector ingest: {dt_ingest:.1f}s   build_lexical: {dt_lex:.1f}s -> {lex_stats}")

    # same ground-truth protocol as bench_codna_telys_a2z.py
    rng = random.Random(args.seed)
    test_units = [u for u in units if u.symbol_type == "test" and len(u.qualname) > len("test_")]
    by_file: dict[str, list] = {}
    for u in test_units:
        by_file.setdefault(u.path, []).append(u)
    picked = rng.sample(sorted(by_file), min(args.queries, len(by_file)))
    probes = [(p, rng.choice(by_file[p])) for p in picked]

    def _eval(mode: str, top_k: int = 40, final_k: int = 8):
        hits, lat = 0, []
        for path, unit in probes:
            t0 = time.perf_counter()
            if mode == "hybrid":
                d = col.search_text(unit.qualname, top_k=top_k, with_metadata=True)
                l = col.search_text(unit.qualname, top_k=top_k, mode="lexical", with_metadata=True)
                seen, ranked = set(), []
                for res in (d, l):  # interleave by alternating rank (rank-fusion, no weights to tune)
                    for i, (uid, s) in enumerate(zip(res["ids"], res["scores"])):
                        if uid not in seen:
                            seen.add(uid)
                            ranked.append((uid, s, i))
                ranked.sort(key=lambda t: t[2])
                md = dict(zip(d["ids"], d.get("metadata") or [{}] * len(d["ids"])))
                ml = dict(zip(l["ids"], l.get("metadata") or [{}] * len(l["ids"])))
                got = {(md.get(uid) or ml.get(uid) or {}).get("path") for uid, _, _ in ranked[:final_k]}
            else:
                res = col.search_text(unit.qualname, top_k=final_k,
                                      **({"mode": mode} if mode == "lexical" else {}),
                                      with_metadata=True)
                md = res.get("metadata") or [{}] * len(res["ids"])
                got = {m.get("path") for m in md}
            lat.append(time.perf_counter() - t0)
            hits += int(path in got)
        return hits / len(probes), sorted(lat)[len(lat) // 2] * 1000

    print()
    for mode in ("dense", "lexical", "hybrid"):
        recall, med_ms = _eval(mode)
        print(f"recall@8 {mode:<8}: {recall:.3f}   median latency {med_ms:.0f}ms")
    return 0


if __name__ == "__main__":
    sys.exit(main())
