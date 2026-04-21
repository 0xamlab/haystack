"""
training/semantic/pipeline.py — End-to-end training pipeline runner.

Runs all five stages in sequence for a given schema and writes artifacts to a
user-local directory keyed by schema hash, so each user/machine maintains their
own trained model:

    ~/.decision-engine/semantic/<schema_hash>/
        vocab.json
        id_to_token.json
        train.jsonl
        model.pt
        embeddings.bin
        {intent,agg,family}_fc{1,2}_{weight,bias}.bin
        meta.json
        nn_ids.bin
        nn_scores.bin

The schema_hash is a stable 8-char hex derived from the schema content + domain
aliases, so adding a column or alias produces a new model directory rather than
silently overwriting a previously trained model.

Cold-start fallback — 3-tier resolution:
    Tier 1  schema model   ~/.decision-engine/semantic/<hash>/   (best quality)
    Tier 2  base model     ~/.decision-engine/semantic/_base/    (generic seed)
    Tier 3  no model       None                                  (resolver only)

Use resolve_artifacts() to select the best available tier, and train_async()
to kick off schema-model training in the background without blocking inference.

Usage:
    python3 training/semantic/pipeline.py \
        --schema  path/to/schema.json \
        --aliases path/to/domain_aliases.json   # optional

    # Build the global base model (run once per machine):
    python3 training/semantic/pipeline.py --build-base

    # Use an explicit output directory instead of user-local default:
    python3 training/semantic/pipeline.py \
        --schema  path/to/schema.json \
        --out-dir /path/to/artifacts/

Self-test:
    python3 training/semantic/pipeline.py --self-test
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import sys
import threading
from pathlib import Path
from typing import Literal

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

try:
    import torch
except ImportError:
    print("torch and numpy required: pip install torch numpy")
    sys.exit(1)

from training.semantic.build_dataset import build_dataset
from training.semantic.build_vocab import build_vocab_from_sources
from training.semantic.export_artifacts import export, verify_export
from training.semantic.precompute_neighbors import (
    compute_neighbors,
    load_embeddings,
    write_neighbors,
)
from training.semantic.train_thin_semantic import (
    SemanticDataset,
    ThinSemanticModel,
    train,
)

# ── User-local artifact root ──────────────────────────────────────────────────

# Reserved directory name for the schema-agnostic base model.
_BASE_HASH = "_base"

def default_artifact_root() -> Path:
    """Return ~/.decision-engine/semantic/ (created on demand)."""
    root = Path.home() / ".decision-engine" / "semantic"
    root.mkdir(parents=True, exist_ok=True)
    return root


def schema_hash(schema: dict, domain_aliases: dict | None) -> str:
    """
    Stable 8-char hex hash of (schema, domain_aliases).

    Sorting keys before hashing ensures the same schema always maps to the
    same hash regardless of dict insertion order.
    """
    payload = json.dumps(
        {"schema": schema, "aliases": domain_aliases or {}},
        sort_keys=True,
    ).encode()
    return hashlib.sha256(payload).hexdigest()[:8]


def artifact_dir_for(
    schema:         dict,
    domain_aliases: dict | None = None,
    base:           Path | None = None,
) -> Path:
    """
    Return (and create) the artifact directory for this schema.

    If base is given, returns base directly (no hash subdirectory).
    Otherwise returns ~/.decision-engine/semantic/<hash>/.
    """
    if base is not None:
        base.mkdir(parents=True, exist_ok=True)
        return base
    h   = schema_hash(schema, domain_aliases)
    out = default_artifact_root() / h
    out.mkdir(parents=True, exist_ok=True)
    return out


# ── Pipeline stages ───────────────────────────────────────────────────────────

def stage_vocab(
    schema:         dict,
    domain_aliases: dict | None,
    out_dir:        Path,
) -> tuple[dict[str, int], list[str]]:
    print("[1/5] Building vocabulary...")
    token_to_id, id_to_token = build_vocab_from_sources(schema, domain_aliases=domain_aliases)
    (out_dir / "vocab.json").write_text(json.dumps(token_to_id, indent=2))
    (out_dir / "id_to_token.json").write_text(json.dumps(id_to_token, indent=2))
    print(f"      vocab_size={len(id_to_token)}  → {out_dir / 'vocab.json'}")
    return token_to_id, id_to_token


def stage_dataset(
    vocab:          dict[str, int],
    schema:         dict,
    domain_aliases: dict | None,
    out_dir:        Path,
) -> list[dict]:
    print("[2/5] Building dataset...")
    records = build_dataset(vocab, schema, domain_aliases, augment=True)
    out = out_dir / "train.jsonl"
    with open(out, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    intent_counts = [sum(1 for r in records if r["intent"] == i) for i in range(4)]
    print(f"      {len(records)} examples  "
          f"column_like={intent_counts[0]}  meta={intent_counts[1]}  "
          f"weak={intent_counts[2]}  unsupported={intent_counts[3]}")
    return records


def stage_train(
    vocab_size: int,
    records:    list[dict],
    out_dir:    Path,
    epochs:     int = 80,
    batch_size: int = 32,
    val_split:  float = 0.15,
) -> ThinSemanticModel:
    print(f"[3/5] Training model ({epochs} epochs)...")
    val_n      = max(1, int(len(records) * val_split))
    val_recs   = records[-val_n:]
    train_recs = records[:-val_n]

    model  = ThinSemanticModel(vocab_size=vocab_size)
    ds_tr  = SemanticDataset(train_recs)
    ds_val = SemanticDataset(val_recs) if val_recs else None

    metrics = train(model, ds_tr, ds_val, epochs=epochs, batch_size=batch_size)

    ckpt_path = out_dir / "model.pt"
    torch.save(
        {"state_dict": model.state_dict(), "vocab_size": vocab_size, "metrics": metrics},
        ckpt_path,
    )
    best = metrics.get("best_val_acc", 0.0)
    print(f"      best_val_intent_acc={best:.3f}  → {ckpt_path}")
    return model


def stage_export(
    model:      ThinSemanticModel,
    vocab_size: int,
    out_dir:    Path,
) -> None:
    print("[4/5] Exporting binary artifacts...")
    meta = export(model, out_dir)
    ok   = verify_export(out_dir, vocab_size)
    if not ok:
        print("      WARNING: shape verification failed — check artifacts")
    else:
        print(f"      shape verification OK  emb_dim={meta['emb_dim']}")


def stage_neighbors(
    vocab_size: int,
    emb_dim:    int,
    out_dir:    Path,
    k:          int = 8,
    min_score:  float = 0.70,
) -> None:
    print(f"[5/5] Precomputing top-{k} token neighbors (min_score={min_score})...")
    emb_path = out_dir / "embeddings.bin"
    emb      = load_embeddings(emb_path, vocab_size, emb_dim)
    nn_ids, nn_scores = compute_neighbors(emb, k=k, min_score=min_score)
    write_neighbors(out_dir, nn_ids, nn_scores)
    has_nn = (nn_scores[:, 0] > 0).sum()
    print(f"      tokens with ≥1 neighbor above threshold: {has_nn}/{vocab_size}")


# ── Main pipeline ─────────────────────────────────────────────────────────────

def stage_column_embeddings(
    schema: dict,
    domain_aliases: dict | None,
    artifacts_dir: Path,
) -> Path:
    """
    Fast path: compute column embeddings from an existing model without training.

    Tokenizes every column name in schema, embeds each using the model in
    artifacts_dir, and writes col_embeddings.json:
        {col_name: [float, ...]}  (unit-norm, EMB_DIM values)

    This is O(num_cols × avg_tokens × EMB_DIM) ≈ microseconds per column.
    No gradient computation. Safe to call for schemas with millions of columns.
    """
    from training.semantic.fast_resolver import FastResolver
    try:
        resolver = FastResolver(artifacts_dir)
    except FileNotFoundError:
        return artifacts_dir  # No model yet — nothing to do

    col_embeddings: dict[str, list[float]] = {}
    for _src, cols in schema.items():
        for col_entry in cols:
            col_name = col_entry[0] if isinstance(col_entry, list | tuple) else col_entry
            vec = resolver.embed(col_name, domain_aliases)
            col_embeddings[col_name] = vec.tolist()

    out = artifacts_dir / "col_embeddings.json"
    out.write_text(json.dumps(col_embeddings))
    return artifacts_dir


def _merge_aliases_import():
    """Lazy import to avoid circular deps at module level."""
    from mojo.engine.vector_kernels.tokenizer import merge_aliases as _ma
    return _ma

merge_aliases = _merge_aliases_import()


def run_pipeline(
    schema:         dict,
    domain_aliases: dict | None = None,
    out_dir:        Path | None = None,
    epochs:         int = 80,
    batch_size:     int = 32,
    val_split:      float = 0.15,
    nn_k:           int = 8,
    nn_min_score:   float = 0.70,
    embed_only:     bool = False,
) -> Path:
    """
    Run the full pipeline and return the artifact directory path.

    Artifacts are written to out_dir if given, otherwise
    ~/.decision-engine/semantic/<schema_hash>/.

    Parameters
    ----------
    embed_only : bool
        If True and a compatible base model exists, skip training entirely and
        only compute column embeddings from the existing model.  Use this when
        called at source registration time for large schemas — column embeddings
        are computed in microseconds per column regardless of schema size.

        The caller should separately schedule train_async() to refine the model
        for schema-specific tokens in the background.
    """
    art_dir = artifact_dir_for(schema, domain_aliases, base=out_dir)
    print(f"\nArtifact directory: {art_dir}\n")

    # Fast path: if embed_only and artifacts already exist, just re-embed columns
    if embed_only and (art_dir / "embeddings.bin").exists():
        print("[fast] embed_only=True — computing column embeddings from existing model")
        stage_column_embeddings(schema, domain_aliases, art_dir)
        print("[fast] Column embeddings written → col_embeddings.json")
        return art_dir

    token_to_id, _ = stage_vocab(schema, domain_aliases, art_dir)
    records = stage_dataset(token_to_id, schema, domain_aliases, art_dir)
    model = stage_train(
        len(token_to_id),
        records,
        art_dir,
        epochs,
        batch_size,
        val_split,
    )
    stage_export(model, len(token_to_id), art_dir)

    from training.semantic.train_thin_semantic import EMB_DIM
    stage_neighbors(len(token_to_id), EMB_DIM, art_dir, k=nn_k, min_score=nn_min_score)

    # Compute column embeddings (fast lookup, no extra training)
    stage_column_embeddings(schema, domain_aliases, art_dir)

    # Write a manifest so callers can find the artifacts
    manifest = {
        "schema_hash":  schema_hash(schema, domain_aliases),
        "vocab_size":   len(token_to_id),
        "artifact_dir": str(art_dir),
    }
    (art_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

    print(f"\nPipeline complete. Artifacts: {art_dir}")
    return art_dir


def locate_artifacts(
    schema:         dict,
    domain_aliases: dict | None = None,
    base:           Path | None = None,
) -> Path | None:
    """
    Return the artifact directory for this schema if it exists, else None.

    Allows callers to check whether the model needs (re-)training before
    attempting to load artifacts.
    """
    if base is not None:
        return base if (base / "manifest.json").exists() else None
    h   = schema_hash(schema, domain_aliases)
    out = default_artifact_root() / h
    return out if (out / "manifest.json").exists() else None


# ── Base model ────────────────────────────────────────────────────────────────

def locate_base_model(base: Path | None = None) -> Path | None:
    """
    Return the base-model artifact directory if it exists, else None.

    The base model lives at ~/.decision-engine/semantic/_base/ and covers
    only the built-in seed vocabulary — no schema-specific columns.
    """
    if base is not None:
        return base if (base / "manifest.json").exists() else None
    out = default_artifact_root() / _BASE_HASH
    return out if (out / "manifest.json").exists() else None


def build_base_model(
    out_dir:    Path | None = None,
    epochs:     int = 80,
    batch_size: int = 32,
) -> Path:
    """
    Train and export the schema-agnostic base model (seed vocabulary only).

    The base model is keyed to _BASE_HASH so it is never confused with a
    schema-specific model.  It should be built once per machine:

        python3 training/semantic/pipeline.py --build-base

    Returns the artifact directory path.
    """
    art_dir = out_dir if out_dir is not None else (default_artifact_root() / _BASE_HASH)
    art_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n[Base model] Artifact directory: {art_dir}\n")

    # Empty schema → only built-in seed tokens and seed queries
    token_to_id, _ = stage_vocab({}, None, art_dir)
    records         = stage_dataset(token_to_id, {}, None, art_dir)
    model           = stage_train(len(token_to_id), records, art_dir,
                                  epochs=epochs, batch_size=batch_size)
    stage_export(model, len(token_to_id), art_dir)

    from training.semantic.train_thin_semantic import EMB_DIM
    stage_neighbors(len(token_to_id), EMB_DIM, art_dir, k=8, min_score=0.70)

    manifest = {
        "schema_hash":  _BASE_HASH,
        "vocab_size":   len(token_to_id),
        "artifact_dir": str(art_dir),
    }
    (art_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

    print(f"\n[Base model] Build complete. Artifacts: {art_dir}")
    return art_dir


# ── 3-tier artifact resolver ──────────────────────────────────────────────────

ModelTier = Literal["schema", "base", "none"]


def resolve_artifacts(
    schema:         dict,
    domain_aliases: dict | None = None,
    schema_base:    Path | None = None,
    base_model_dir: Path | None = None,
) -> tuple[Path | None, ModelTier]:
    """
    Return (artifact_dir, tier) using 3-tier fallback:

        Tier 1  "schema"  — schema-specific model (best quality)
        Tier 2  "base"    — generic base model (seed vocabulary)
        Tier 3  "none"    — no semantic layer; caller should run resolver-only

    Args:
        schema:         The schema dict for the current domain.
        domain_aliases: Optional domain-specific alias expansions.
        schema_base:    Override for the schema-model directory (tests / CI).
        base_model_dir: Override for the base-model directory (tests / CI).
    """
    schema_dir = locate_artifacts(schema, domain_aliases, base=schema_base)
    if schema_dir is not None:
        return schema_dir, "schema"

    base_dir = locate_base_model(base=base_model_dir)
    if base_dir is not None:
        return base_dir, "base"

    return None, "none"


# ── Async training ────────────────────────────────────────────────────────────

# Global executor — one background thread so two concurrent schema changes
# don't spawn unbounded threads.
_TRAIN_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=1)
_TRAIN_LOCKS: dict[str, threading.Lock] = {}
_TRAIN_LOCKS_MU = threading.Lock()


def _schema_lock(h: str) -> threading.Lock:
    """Return (creating if needed) a per-schema-hash lock."""
    with _TRAIN_LOCKS_MU:
        if h not in _TRAIN_LOCKS:
            _TRAIN_LOCKS[h] = threading.Lock()
        return _TRAIN_LOCKS[h]


def train_async(
    schema:         dict,
    domain_aliases: dict | None = None,
    out_dir:        Path | None = None,
    epochs:         int = 80,
    batch_size:     int = 32,
    val_split:      float = 0.15,
    nn_k:           int = 8,
    nn_min_score:   float = 0.70,
) -> concurrent.futures.Future[Path]:
    """
    Start schema-model training in the background and return a Future.

    Callers serve the current request immediately (using the base model or
    resolver-only path) while the schema-specific model trains.  Once the
    Future resolves, subsequent calls to resolve_artifacts() will return
    Tier 1.

    If training for this schema is already in progress, submits a no-op that
    returns the existing artifact directory so callers don't double-train.

    Usage::

        future = train_async(schema, domain_aliases)
        art_dir, tier = resolve_artifacts(schema, domain_aliases)
        # ... serve request with tier-2/3 fallback ...

        # Later, when future completes:
        art_dir = future.result()   # now Tier 1 is available
    """
    h    = schema_hash(schema, domain_aliases)
    lock = _schema_lock(h)

    def _task() -> Path:
        # Per-hash lock prevents concurrent duplicate training runs.
        if not lock.acquire(blocking=False):
            # Another thread is training this schema — wait and return path.
            lock.acquire(blocking=True)
            lock.release()
            existing = locate_artifacts(schema, domain_aliases, base=out_dir)
            if existing:
                return existing
        try:
            return run_pipeline(
                schema=schema,
                domain_aliases=domain_aliases,
                out_dir=out_dir,
                epochs=epochs,
                batch_size=batch_size,
                val_split=val_split,
                nn_k=nn_k,
                nn_min_score=nn_min_score,
            )
        finally:
            lock.release()

    return _TRAIN_EXECUTOR.submit(_task)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Run end-to-end semantic model pipeline")
    parser.add_argument("--schema", type=Path, default=None)
    parser.add_argument("--aliases", type=Path, default=None)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Override artifact directory (default: ~/.decision-engine/semantic/<hash>)",
    )
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument("--batch", type=int, default=32)
    parser.add_argument("--val-split", type=float, default=0.15)
    parser.add_argument("--nn-k", type=int, default=8)
    parser.add_argument("--nn-min-score", type=float, default=0.70)
    parser.add_argument("--build-base",   action="store_true",
                        help="Build the global base model (run once per machine)")
    parser.add_argument("--self-test",    action="store_true")
    args = parser.parse_args()

    if args.self_test:
        _run_self_test()
        return

    if args.build_base:
        build_base_model(out_dir=args.out_dir, epochs=args.epochs, batch_size=args.batch)
        return

    if not args.schema:
        parser.error("--schema is required (or use --build-base)")

    schema = json.loads(args.schema.read_text())
    domain_aliases: dict = {}
    if args.aliases and args.aliases.exists():
        domain_aliases = json.loads(args.aliases.read_text())

    run_pipeline(
        schema=schema,
        domain_aliases=domain_aliases or None,
        out_dir=args.out_dir,
        epochs=args.epochs,
        batch_size=args.batch,
        val_split=args.val_split,
        nn_k=args.nn_k,
        nn_min_score=args.nn_min_score,
    )


def _run_self_test():
    import tempfile

    schema = {
        "POS": [
            ["UNIT_PRICE",     "unit_measure"],
            ["EXT_PRICE",      "derived_measure"],
            ["QTY",            "base_measure"],
            ["ORDER_DATE",     "other"],
            ["CUSTOMER_NAME",  "other"],
        ],
        "Totals": [
            ["Net_Sales",  "derived_measure"],
            ["Guests",     "base_measure"],
            ["PPA",        "ratio"],
        ],
    }
    domain_aliases = {"ppa": ["per", "person", "average"]}
    unknown_schema = {"Other": [["UNKNOWN_COL", "other"]]}

    fast_opts = {
        "epochs": 5,
        "batch_size": 16,
        "val_split": 0.15,
        "nn_k": 8,
        "nn_min_score": 0.0,
    }

    all_bins = [
        "vocab.json", "id_to_token.json", "train.jsonl", "model.pt",
        "embeddings.bin",
        "intent_fc1_weight.bin", "intent_fc1_bias.bin",
        "intent_fc2_weight.bin", "intent_fc2_bias.bin",
        "agg_fc1_weight.bin",    "agg_fc1_bias.bin",
        "agg_fc2_weight.bin",    "agg_fc2_bias.bin",
        "family_fc1_weight.bin", "family_fc1_bias.bin",
        "family_fc2_weight.bin", "family_fc2_bias.bin",
        "meta.json", "nn_ids.bin", "nn_scores.bin", "manifest.json",
    ]

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        schema_dir = root / "schema_model"
        base_dir = root / "base_model"

        # ── Test 1: schema pipeline ───────────────────────────────────────────
        print("\n── Test 1: schema pipeline")
        art_dir = run_pipeline(
            schema=schema,
            domain_aliases=domain_aliases,
            out_dir=schema_dir,
            **fast_opts,
        )
        for fname in all_bins:
            assert (art_dir / fname).exists(), f"Missing: {fname}"
        manifest = json.loads((art_dir / "manifest.json").read_text())
        assert "schema_hash" in manifest and "vocab_size" in manifest
        found = locate_artifacts(schema, domain_aliases, base=art_dir)
        assert found is not None, "locate_artifacts should find schema model"
        vocab_size = manifest["vocab_size"]
        print(f"   PASSED  vocab_size={vocab_size}  files={len(all_bins)}")

        # ── Test 2: base model ────────────────────────────────────────────────
        print("\n── Test 2: base model")
        build_base_model(out_dir=base_dir, epochs=5, batch_size=16)
        assert locate_base_model(base=base_dir) is not None, "locate_base_model should find base"
        base_manifest = json.loads((base_dir / "manifest.json").read_text())
        assert base_manifest["schema_hash"] == _BASE_HASH
        print(f"   PASSED  base vocab_size={base_manifest['vocab_size']}")

        # ── Test 3: resolve_artifacts — 3-tier fallback ───────────────────────
        print("\n── Test 3: resolve_artifacts")

        # Tier 1: schema model present
        path, tier = resolve_artifacts(
            schema,
            domain_aliases,
            schema_base=schema_dir,
            base_model_dir=base_dir,
        )
        assert tier == "schema", f"Expected tier='schema', got {tier!r}"
        assert path == schema_dir

        # Tier 2: schema model absent, base present
        path, tier = resolve_artifacts(
            unknown_schema,
            None,
            schema_base=None,
            base_model_dir=base_dir,
        )
        assert tier == "base", f"Expected tier='base', got {tier!r}"
        assert path == base_dir

        # Tier 3: nothing present
        path, tier = resolve_artifacts(
            unknown_schema,
            None,
            schema_base=None,
            base_model_dir=None,
        )
        assert tier == "none", f"Expected tier='none', got {tier!r}"
        assert path is None
        print("   PASSED  schema→Tier1  unknown+base→Tier2  unknown+none→Tier3")

        # ── Test 4: train_async ───────────────────────────────────────────────
        print("\n── Test 4: train_async")
        async_out = root / "async_model"
        future = train_async(schema, domain_aliases, out_dir=async_out, **fast_opts)
        # Resolve immediately — should be Tier 2 (base) while training
        _, tier_before = resolve_artifacts(
            schema,
            domain_aliases,
            schema_base=async_out,
            base_model_dir=base_dir,
        )
        assert tier_before in ("schema", "base"), (
            f"Should be base or schema before future resolves, got {tier_before!r}"
        )
        result_path = future.result(timeout=120)
        assert result_path == async_out
        assert (async_out / "manifest.json").exists(), "async training must write manifest"
        path_after, tier_after = resolve_artifacts(
            schema,
            domain_aliases,
            schema_base=async_out,
            base_model_dir=base_dir,
        )
        assert tier_after == "schema", (
            f"After async training, expected Tier1, got {tier_after!r}"
        )
        print(f"   PASSED  async training complete  tier_after={tier_after!r}")

    print("\nSelf-test PASSED  (4/4 subtests)")


if __name__ == "__main__":
    main()
