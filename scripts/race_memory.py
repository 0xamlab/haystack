#!/usr/bin/env python3
"""Race memory — the llama.cpp race corpus as an on-device searchable memory (codna + telys).

One command builds the memory; ``ask`` answers campaign questions against it (hybrid dense+lexical
recall); ``probe`` scores it against known campaign answers; ``status`` inspects the index.

    python scripts/race_memory.py build
    python scripts/race_memory.py ask "split-K batched decode attention kernel"
    python scripts/race_memory.py probe
    python scripts/race_memory.py status

Corpus: the race itself — kernel variants (attention_forge), race harnesses + the results ledger
(benchmarks/llm_smoke), the Mojo runtime kernels (mojo/engine/algenta_runtime), and the competitor
reference (benchmarks/competitors/llama_cpp).

Extraction is two lanes:
  * codna codeunits for the languages its grammars cover (python, c, cpp, ts, ...)
  * the algenta repo-intelligence Mojo adapter (regex symbol/import extractor) for .mojo kernels
  * markdown heading-chunks for the ledger/docs (REALRACE_RESULTS.md)

Requires: codna (installed, or --codna-cli PATH to a checkout) + telys with the lexical lane
(local runtime + Mojo kernel; set TELYS_KERNEL to libame_kernel.dylib). State lives under
.race-memory/ (git-ignored). Measured on this repo: ~1,900 units, 4.2 MB artifact, 0-1 ms
queries, hybrid recall@8 9/10 on the campaign probe.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = REPO_ROOT / ".race-memory"
DB = STATE_DIR / "db"
ARTIFACT = STATE_DIR / "artifact"

CORPUS_DIRS = (
    "attention_forge",
    "benchmarks/llm_smoke",
    "mojo/engine/algenta_runtime",
    "benchmarks/competitors/llama_cpp",
)

# Campaign probe: (question, expected file suffix). Kept as regression memory for the race itself.
PROBES = (
    ("llama.cpp race harness measuring prefill and decode tokens per second", "realrace_llama_cpp.py"),
    ("MLX-LM decode race comparison harness", "realrace_mlx_lm.py"),
    ("long context race harness for llama cpp", "realrace_llama_cpp_longctx.py"),
    ("batched decode smoke test", "batched_decode_smoke.py"),
    ("race results ledger with measured token throughput", "REALRACE_RESULTS.md"),
    ("tinyllama prefill benchmark", "tinyllama_prefill_bench.py"),
    ("split-K batched decode attention kernel", "native_kv_decode_attn_splitk_batched.mojo"),
    ("batched KV producer kernel for decode", "kvprod_batched.mojo"),
    ("resident session pipeline for the mojo runtime", "session.mojo"),
    ("batched decode step kernel in the runtime", "batch.mojo"),
)


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _codeunits(cli_path: str | None):
    if cli_path:
        sys.path.insert(0, str(Path(cli_path).expanduser().resolve()))
    try:
        from codna import codeunits
        return codeunits
    except ImportError as exc:
        raise SystemExit("codna is required: pip install codna, or pass --codna-cli PATH") from exc


def _mojo_adapter():
    """The algenta repo-intelligence Mojo adapter, loaded standalone (it imports only the
    dataclass contracts). Returns None when unavailable (mojo files then stay unindexed)."""
    contracts = REPO_ROOT / "apps/api_server/services/repository_intelligence_contracts.py"
    mojo = REPO_ROOT / "apps/api_server/services/repository_intelligence_adapters/mojo_language.py"
    if not (contracts.is_file() and mojo.is_file()):
        return None
    try:
        _load_module("apps.api_server.services.repository_intelligence_contracts", contracts)
        return _load_module("apps.api_server.services.repository_intelligence_adapters.mojo_language",
                            mojo)
    except Exception:  # noqa: BLE001 — fail open: mojo stays unindexed
        return None


def _telys_env() -> bool:
    """Point at the LOCAL runtime + Mojo kernel when one is reachable (the lexical lane needs it):
    $TELYS_KERNEL first, then the repo's own mojo_build. Returns True when a kernel is configured;
    otherwise the default runtime is used and the memory degrades to dense-only."""
    if os.environ.get("TELYS_KERNEL") and Path(os.environ["TELYS_KERNEL"]).is_file():
        os.environ.setdefault("TELYS_RUNTIME", "local")
        return True
    cand = REPO_ROOT / "mojo_build" / "libame_kernel.dylib"
    if cand.is_file():
        os.environ["TELYS_KERNEL"] = str(cand)
        os.environ.setdefault("TELYS_RUNTIME", "local")
        return True
    return False


def _corpus(tmp: Path) -> None:
    for d in CORPUS_DIRS:
        src = REPO_ROOT / d
        if src.is_dir():
            shutil.copytree(src, tmp / d, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))


def build(cli_path: str | None) -> None:
    codeunits = _codeunits(cli_path)
    _telys_env()
    from telys import Telys, scope_key
    from telys.embedding import AlgentaMultigramEmbedder

    corpus = STATE_DIR / "corpus"
    if corpus.exists():
        shutil.rmtree(corpus)
    shutil.rmtree(DB, ignore_errors=True)
    shutil.rmtree(ARTIFACT, ignore_errors=True)
    STATE_DIR.mkdir(exist_ok=True)
    t0 = time.perf_counter()
    _corpus(corpus)
    print(f"corpus copied in {time.perf_counter() - t0:.1f}s")

    t0 = time.perf_counter()
    cu_units, stats = codeunits.extract_repo(str(corpus), "race")
    print(f"codna extract: {stats.files} files -> {stats.units} units in "
          f"{time.perf_counter() - t0:.1f}s")

    mojo = _mojo_adapter()
    mojo_symbols = []
    if mojo is not None:
        def stable_identifier(kind, payload):
            return hashlib.sha256(f"{kind}:{payload}".encode()).hexdigest()[:24]

        t0 = time.perf_counter()
        mojo_files = sorted(corpus.rglob("*.mojo"))
        module_index: dict[str, str] = {}
        for p in mojo_files:
            rel = str(p.relative_to(corpus))
            module_index[p.stem] = rel
            module_index[rel] = rel
        for p in mojo_files:
            rel = str(p.relative_to(corpus))
            text = p.read_text(encoding="utf-8", errors="replace")
            syms, _d, _r = mojo.parse_file(rel, text, module_index,
                                           stable_identifier=stable_identifier,
                                           resolve_import=lambda t, idx: idx.get(t))
            lines = text.splitlines()
            for s in syms:
                lo = max(0, s.start_line - 1)
                seg = "\n".join(lines[lo:lo + 40])[:1500]
                mojo_symbols.append((rel, s.symbol_name, s.symbol_kind, seg))
        print(f"mojo adapter: {len(mojo_files)} files -> {len(mojo_symbols)} symbols in "
              f"{time.perf_counter() - t0:.1f}s")

    texts, ids, metas = [], [], []
    for p in sorted(corpus.rglob("*.md")):          # ledger/docs: heading-chunked units
        rel = str(p.relative_to(corpus))
        chunks, cur = [], []
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("#") and cur:
                chunks.append("\n".join(cur))
                cur = []
            cur.append(line)
        if cur:
            chunks.append("\n".join(cur))
        for i, chunk in enumerate(chunks):
            texts.append(f"{rel}\n{chunk}"[:2000])
            ids.append(f"race:{rel}:chunk{i}")
            metas.append({"scope_key": scope_key("race", "", "markdown"), "path": rel,
                          "language": "markdown", "symbol_type": "module"})
    for u in cu_units:
        texts.append(u.text)
        ids.append(u.id)
        metas.append({"scope_key": scope_key("race", "", u.language), "path": u.path,
                      "language": u.language, "symbol_type": u.symbol_type})
    for rel, name, kind, seg in mojo_symbols:
        texts.append(f"{rel}\n{kind} {name}\n{seg}")
        ids.append(f"race:{rel}:{name}")
        metas.append({"scope_key": scope_key("race", "", "mojo"), "path": rel,
                      "language": "mojo",
                      "symbol_type": "test" if name.startswith("test_") else "function"})

    emb = AlgentaMultigramEmbedder()
    lexical = _telys_env()

    def _ingest(with_lexical: bool) -> None:
        eng = Telys(str(DB), embedding_providers={emb.profile.model_id: emb})
        col = eng.create_collection("race_memory", dim=emb.profile.dimension,
                                    partition_by="scope_key", embedder=emb, lexical=with_lexical,
                                    dtype="int8",
                                    filter_columns=["path", "language", "symbol_type"])
        col.upsert_texts(texts, ids, metas)
        col.compact()
        if with_lexical:
            col.build_lexical()
        col.save()

    t0 = time.perf_counter()
    try:
        _ingest(lexical)
    except TypeError:
        # native runtime without the lexical lane (texts= rejected): dense-only fallback
        print("# lexical lane unavailable on this runtime — falling back to dense-only")
        lexical = False
        shutil.rmtree(DB, ignore_errors=True)
        _ingest(False)
    print(f"ingest{' + lexical' if lexical else ''}: {len(texts)} units in "
          f"{time.perf_counter() - t0:.1f}s")
    STATE_DIR.mkdir(exist_ok=True)
    (STATE_DIR / "meta.json").write_text(json.dumps({"lexical": lexical}))

    t0 = time.perf_counter()
    eng = Telys(str(DB), embedding_providers={emb.profile.model_id: emb})
    eng.open_collection("race_memory", embedder=emb).export_compact(str(ARTIFACT), mode="int8")
    size = sum(f.stat().st_size for f in ARTIFACT.rglob("*") if f.is_file())
    print(f"artifact: {size / 1e6:.1f} MB -> {ARTIFACT} in {time.perf_counter() - t0:.1f}s")


def _open(cli_path: str | None):
    codeunits = _codeunits(cli_path)  # noqa: F841 — validates codna availability early
    _telys_env()
    from telys import Telys
    from telys.embedding import AlgentaMultigramEmbedder
    if not DB.is_dir():
        raise SystemExit("no race memory yet — run: python scripts/race_memory.py build")
    meta = {}
    if (STATE_DIR / "meta.json").is_file():
        meta = json.loads((STATE_DIR / "meta.json").read_text())
    emb = AlgentaMultigramEmbedder()
    eng = Telys(str(DB), embedding_providers={emb.profile.model_id: emb})
    return eng.open_collection("race_memory", embedder=emb), bool(meta.get("lexical"))


def _hybrid_paths(col, query: str, top_k: int, lexical: bool) -> list[tuple[str, str]]:
    dense = col.search_text(query, top_k=top_k, with_metadata=True)
    lanes = [dense]
    if lexical:
        try:
            lanes.append(col.search_text(query, top_k=top_k, mode="lexical", with_metadata=True))
        except Exception:  # noqa: BLE001 — lane built but query path unavailable -> dense only
            pass
    seen, rows = set(), []
    for res in lanes:
        for uid, m in zip(res["ids"], res.get("metadata") or [{}] * len(res["ids"])):
            if uid in seen:
                continue
            seen.add(uid)
            rows.append(((m or {}).get("path") or "-", (m or {}).get("symbol_type") or "-"))
    return rows


def ask(cli_path: str | None, query: str, top_k: int) -> None:
    col, lexical = _open(cli_path)
    t0 = time.perf_counter()
    rows = _hybrid_paths(col, query, top_k, lexical)
    dt = (time.perf_counter() - t0) * 1000
    print(f"# {'hybrid' if lexical else 'dense'} top-{top_k} in {dt:.0f} ms")
    for path, sym in rows[:top_k]:
        print(f"{path}  [{sym}]")


def probe(cli_path: str | None) -> None:
    col, lexical = _open(cli_path)
    hits, lats = 0, []
    for q, exp in PROBES:
        t0 = time.perf_counter()
        rows = _hybrid_paths(col, q, 8, lexical)
        lats.append(time.perf_counter() - t0)
        hit = any(p.endswith(exp) for p, _ in rows)
        hits += hit
        print(f"{'HIT ' if hit else 'MISS'} {exp[:56]:56} ({lats[-1]*1000:4.0f} ms)")
    med = sorted(lats)[len(lats) // 2] * 1000
    print(f"recall@8 = {hits}/{len(PROBES)} | median {med:.0f} ms"
          f" | {'hybrid' if lexical else 'dense-only'}")


def status(cli_path: str | None) -> None:
    if not DB.is_dir():
        print("no race memory yet — run: python scripts/race_memory.py build")
        return
    col, lexical = _open(cli_path)
    s = col.stats()
    print(json.dumps({"documents": s.get("external_ids"), "partitions": s.get("partitions"),
                      "lexical": lexical,
                      "artifact_mb": round(sum(f.stat().st_size for f in ARTIFACT.rglob("*")
                                               if f.is_file()) / 1e6, 1)
                      if ARTIFACT.is_dir() else None}, indent=2))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--codna-cli", default=os.environ.get("CODNA_CLI"),
                    help="codna checkout cli/ dir (default: installed codna, or $CODNA_CLI)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build", help="build the race memory (index + lexical lane + artifact)")
    p_ask = sub.add_parser("ask", help="hybrid recall against the race memory")
    p_ask.add_argument("query")
    p_ask.add_argument("--top-k", type=int, default=8)
    sub.add_parser("probe", help="score the memory against known campaign answers")
    sub.add_parser("status", help="index statistics")
    args = ap.parse_args()
    {"build": lambda: build(args.codna_cli),
     "ask": lambda: ask(args.codna_cli, args.query, args.top_k),
     "probe": lambda: probe(args.codna_cli),
     "status": lambda: status(args.codna_cli)}[args.cmd]()
    return 0


if __name__ == "__main__":
    sys.exit(main())
