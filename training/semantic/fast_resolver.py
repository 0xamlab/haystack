"""
training/semantic/fast_resolver.py — Numpy-only fast query resolver.

At inference time (no PyTorch, no LLM required):
  1. Load embeddings.bin + vocab.json from the artifact directory.
  2. Tokenize the user's hint string.
  3. Average-pool token embeddings → query vector.
  4. Cosine-similarity against every registered column's embedding.
  5. If best match > CONFIDENCE_THRESHOLD → return (col_name, confidence).
  6. Otherwise → return (None, best_confidence) to signal LLM fallback.

Usage (Python):
    from training.semantic.fast_resolver import FastResolver
    r = FastResolver("/Users/angel/.decision-engine/semantic/<hash>")
    col, conf = r.resolve("total revenue", ["EXT_PRICE", "NET_SALES", "UNIT_PRICE"])
    if col:   # fast path: <1ms, no LLM
        ...
    else:     # fallback: call LLM
        ...

Self-test:
    python3 training/semantic/fast_resolver.py --self-test
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np

from mojo.engine.vector_kernels.tokenizer import expand_tokens, merge_aliases, tokenize_name

CONFIDENCE_THRESHOLD = 0.75


class FastResolver:
    """
    Numpy-only resolver.  One instance per schema hash — load once, reuse.

    Parameters
    ----------
    artifacts_dir : str | Path
        Directory containing embeddings.bin and vocab.json
        (written by export_artifacts.py).
    """

    def __init__(self, artifacts_dir: str | Path):
        d = Path(artifacts_dir)
        vocab_path = d / "vocab.json"
        emb_path = d / "embeddings.bin"
        meta_path = d / "meta.json"

        if not vocab_path.exists() or not emb_path.exists():
            raise FileNotFoundError(f"Artifacts not found in {d}")

        self._vocab: dict[str, int] = json.loads(vocab_path.read_text())
        meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
        emb_dim = meta.get("emb_dim", 32)
        vocab_size = len(self._vocab)

        raw = np.frombuffer(emb_path.read_bytes(), dtype="<f4")
        self._emb = raw.reshape(vocab_size, emb_dim).copy()  # [V, D]
        self._unk = self._vocab.get("<UNK>", 1)

    # ── Public API ────────────────────────────────────────────────────────────

    def embed(
        self,
        token_str: str,
        domain_aliases: dict[str, list[str]] | None = None,
    ) -> np.ndarray:
        """
        Tokenize a string and average-pool its embeddings → [D] vector.
        Returns a zero vector if no tokens are recognized.
        """
        combined = merge_aliases(domain_aliases)
        tokens = tokenize_name(token_str)
        expanded = [t for t, _ in expand_tokens(tokens, combined)]
        ids = [self._vocab.get(t, self._unk) for t in expanded] or [self._unk]
        vecs = self._emb[ids]  # [T, D]
        avg = vecs.mean(axis=0)  # [D]
        norm = np.linalg.norm(avg)
        return avg / max(norm, 1e-8)

    def resolve(
        self,
        hint: str,
        column_names: list[str],
        domain_aliases: dict[str, list[str]] | None = None,
    ) -> tuple[str | None, float]:
        """
        Find the best-matching column name for a natural-language hint.

        Returns
        -------
        (col_name, confidence)
            col_name is None when confidence < CONFIDENCE_THRESHOLD,
            signalling that the LLM should handle this query.
        """
        if not column_names:
            return None, 0.0

        q_vec = self.embed(hint, domain_aliases)

        # Build [N, D] matrix of column embeddings
        col_vecs = np.stack([self.embed(c, domain_aliases) for c in column_names])
        sims = col_vecs @ q_vec  # [N] cosine sims

        best_idx = int(np.argmax(sims))
        best_conf = float(sims[best_idx])

        if best_conf >= CONFIDENCE_THRESHOLD:
            return column_names[best_idx], best_conf
        return None, best_conf

    def resolve_batch(
        self,
        hints: list[str],
        column_names: list[str],
        domain_aliases: dict[str, list[str]] | None = None,
    ) -> list[tuple[str | None, float]]:
        """Resolve multiple hints in one pass (precomputes column matrix once)."""
        if not column_names:
            return [(None, 0.0)] * len(hints)

        col_vecs = np.stack([self.embed(c, domain_aliases) for c in column_names])  # [N, D]
        results = []
        for hint in hints:
            q_vec = self.embed(hint, domain_aliases)
            sims = col_vecs @ q_vec
            best_idx = int(np.argmax(sims))
            conf = float(sims[best_idx])
            col = column_names[best_idx] if conf >= CONFIDENCE_THRESHOLD else None
            results.append((col, conf))
        return results


# ── Module-level convenience (for callers that don't want to manage instances) ─

_cache: dict[str, FastResolver] = {}


def get_resolver(artifacts_dir: str | Path) -> FastResolver:
    """Return a cached FastResolver for the given artifact directory."""
    key = str(artifacts_dir)
    if key not in _cache:
        _cache[key] = FastResolver(artifacts_dir)
    return _cache[key]


def resolve(
    hint: str,
    column_names: list[str],
    artifacts_dir: str | Path,
    domain_aliases: dict[str, list[str]] | None = None,
) -> tuple[str | None, float]:
    """
    Convenience wrapper: resolve a hint against column_names using artifacts
    from artifacts_dir.  Returns (col_name, confidence).
    """
    return get_resolver(artifacts_dir).resolve(hint, column_names, domain_aliases)


# ── Self-test ─────────────────────────────────────────────────────────────────


def _run_self_test():
    import tempfile

    # Build a tiny vocab + embedding table
    vocab = {
        "<PAD>": 0,
        "<UNK>": 1,
        "net": 2,
        "sales": 3,
        "revenue": 4,
        "unit": 5,
        "price": 6,
        "order": 7,
        "date": 8,
    }
    emb_dim = 8
    rng = np.random.default_rng(42)

    # Build embedding table: same tokens → similar vectors
    emb = rng.standard_normal((len(vocab), emb_dim)).astype("<f4")
    # Make "net" and "sales" tokens cluster near "revenue" (manual hint)
    emb[vocab["net"]] = emb[vocab["revenue"]] + rng.standard_normal(emb_dim) * 0.05
    emb[vocab["sales"]] = emb[vocab["revenue"]] + rng.standard_normal(emb_dim) * 0.05
    # Normalize each row
    norms = np.linalg.norm(emb, axis=1, keepdims=True)
    emb = emb / np.maximum(norms, 1e-8)

    meta = {"emb_dim": emb_dim}

    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        (d / "vocab.json").write_text(json.dumps(vocab))
        (d / "embeddings.bin").write_bytes(emb.tobytes())
        (d / "meta.json").write_text(json.dumps(meta))

        r = FastResolver(d)

        # Query "net sales" should match NET_SALES column best
        col, conf = r.resolve("net sales", ["NET_SALES", "UNIT_PRICE", "ORDER_DATE"])
        print(f"  resolve('net sales') → col={col}  conf={conf:.3f}")

        # Batch resolve
        results = r.resolve_batch(
            ["net sales", "unit price"],
            ["NET_SALES", "UNIT_PRICE", "ORDER_DATE"],
        )
        print(f"  batch results: {results}")

        # Verify embed returns unit vector
        vec = r.embed("net sales")
        norm = np.linalg.norm(vec)
        assert abs(norm - 1.0) < 1e-5, f"embed() not unit norm: {norm}"

    print("Self-test PASSED")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--artifacts", type=Path)
    parser.add_argument("--hint", type=str)
    parser.add_argument("--columns", type=str, help="Comma-separated column names")
    args = parser.parse_args()

    if args.self_test:
        _run_self_test()
        return

    if not args.artifacts or not args.hint or not args.columns:
        parser.error("--artifacts, --hint, and --columns are required")

    cols = [c.strip() for c in args.columns.split(",")]
    col, conf = resolve(args.hint, cols, args.artifacts)
    if col:
        print(f"FAST PATH  col={col}  confidence={conf:.3f}")
    else:
        print(f"FALLBACK   best_confidence={conf:.3f}  (below threshold {CONFIDENCE_THRESHOLD})")


if __name__ == "__main__":
    main()
