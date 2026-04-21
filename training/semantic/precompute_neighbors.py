"""
training/semantic/precompute_neighbors.py — Precompute top-K token neighbors.

For each token in the vocabulary, computes the K nearest neighbors in
embedding space (by cosine similarity) and saves them as flat binary arrays
that the Mojo expand_tokens_topk() kernel reads directly.

Output files:
  nn_ids.bin      uint32  [vocab_size × K]   neighbor token IDs, sorted desc by score
  nn_scores.bin   float32 [vocab_size × K]   cosine similarity scores

The computation is a full vocab_size × vocab_size cosine matrix, which is
fast for small vocabularies (< 5K tokens, < 0.5 s on CPU).
For larger vocabularies use approximate nearest neighbors (annoy / hnswlib).

Usage:
    python3 training/semantic/precompute_neighbors.py \
        --embeddings training/semantic/artifacts/embeddings.bin \
        --vocab      training/semantic/artifacts/vocab.json \
        --out-dir    training/semantic/artifacts/ \
        --k 8 \
        --min-score 0.70

Self-test:
    python3 training/semantic/precompute_neighbors.py --self-test
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

try:
    import numpy as np
except ImportError:
    print("numpy required: pip install numpy")
    sys.exit(1)


# Default: NN_K must match semantic_types.mojo  alias NN_K = 8
DEFAULT_K = 8
DEFAULT_MIN_SCORE = 0.70   # conservative; runtime uses 0.82 to expand


def load_embeddings(path: Path, vocab_size: int, emb_dim: int) -> np.ndarray:
    """Load raw float32 binary and reshape to [vocab_size, emb_dim]."""
    raw = path.read_bytes()
    arr = np.frombuffer(raw, dtype="<f4")
    expected = vocab_size * emb_dim
    if len(arr) != expected:
        raise ValueError(
            f"Embedding file has {len(arr)} floats, expected {expected} "
            f"({vocab_size} × {emb_dim})"
        )
    return arr.reshape(vocab_size, emb_dim).copy()


def l2_normalize(mat: np.ndarray) -> np.ndarray:
    """Row-wise L2 normalization."""
    norms = np.linalg.norm(mat, axis=1, keepdims=True).clip(min=1e-8)
    return mat / norms


def compute_neighbors(
    embeddings: np.ndarray,
    k:          int = DEFAULT_K,
    min_score:  float = DEFAULT_MIN_SCORE,
    batch_size: int = 512,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Compute top-K cosine neighbors for every token.

    Args:
        embeddings:  [vocab_size × emb_dim] float32 (will be normalized internally)
        k:           number of neighbors to keep per token
        min_score:   neighbors below this cosine threshold are stored as 0
        batch_size:  rows per batch (reduces peak memory)

    Returns:
        (nn_ids, nn_scores)
          nn_ids:    uint32  [vocab_size × k]
          nn_scores: float32 [vocab_size × k]
    """
    vocab_size = embeddings.shape[0]
    normed     = l2_normalize(embeddings.astype(np.float32))

    nn_ids    = np.zeros((vocab_size, k), dtype=np.uint32)
    nn_scores = np.zeros((vocab_size, k), dtype=np.float32)

    for start in range(0, vocab_size, batch_size):
        end   = min(start + batch_size, vocab_size)
        chunk = normed[start:end]                    # [B, D]
        sim   = chunk @ normed.T                     # [B, vocab_size]

        # Exclude self-similarity: set diagonal to -1
        for i in range(end - start):
            sim[i, start + i] = -1.0

        # Top-K per row (argpartition is faster than full sort for large vocab)
        if vocab_size >= k + 1:
            top_k_idx = np.argpartition(sim, -k, axis=1)[:, -k:]
        else:
            top_k_idx = np.tile(np.arange(vocab_size), (end - start, 1))[:, :k]

        for i in range(end - start):
            row_idx    = top_k_idx[i]
            row_scores = sim[i, row_idx]
            order      = np.argsort(-row_scores)          # descending
            sorted_idx = row_idx[order]
            sorted_sc  = row_scores[order]
            # Apply min_score floor: replace sub-threshold with 0
            sorted_sc  = np.where(sorted_sc >= min_score, sorted_sc, 0.0)
            nn_ids[start + i]    = sorted_idx[:k].astype(np.uint32)
            nn_scores[start + i] = sorted_sc[:k].astype(np.float32)

    return nn_ids, nn_scores


def write_neighbors(
    out_dir:   Path,
    nn_ids:    np.ndarray,
    nn_scores: np.ndarray,
):
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "nn_ids.bin").write_bytes(nn_ids.astype("<u4").tobytes())
    (out_dir / "nn_scores.bin").write_bytes(nn_scores.astype("<f4").tobytes())


def main():
    parser = argparse.ArgumentParser(description="Precompute token nearest neighbors")
    parser.add_argument("--embeddings", type=Path, default=None, help="embeddings.bin")
    parser.add_argument("--vocab",      type=Path, default=None, help="vocab.json")
    parser.add_argument("--out-dir",    type=Path, default=Path("training/semantic/artifacts"))
    parser.add_argument("--k",          type=int,  default=DEFAULT_K)
    parser.add_argument("--min-score",  type=float, default=DEFAULT_MIN_SCORE)
    parser.add_argument("--emb-dim",    type=int,  default=32)
    parser.add_argument("--self-test",  action="store_true")
    args = parser.parse_args()

    if args.self_test:
        _run_self_test()
        return

    if not args.embeddings or not args.vocab:
        parser.error("--embeddings and --vocab are required")
    vocab      = json.loads(args.vocab.read_text())
    vocab_size = len(vocab)

    print(f"Loading embeddings: vocab_size={vocab_size}  emb_dim={args.emb_dim}")
    emb = load_embeddings(args.embeddings, vocab_size, args.emb_dim)

    print(f"Computing top-{args.k} neighbors (min_score={args.min_score})...")
    nn_ids, nn_scores = compute_neighbors(emb, k=args.k, min_score=args.min_score)

    write_neighbors(args.out_dir, nn_ids, nn_scores)

    # Report: how many tokens have at least one neighbor above threshold
    has_neighbor = (nn_scores[:, 0] > 0).sum()
    print(f"Tokens with ≥1 neighbor above threshold: {has_neighbor}/{vocab_size}")
    print(f"Written nn_ids.bin + nn_scores.bin → {args.out_dir}")


def _run_self_test():
    import tempfile

    vocab_size = 40
    emb_dim    = 32
    k          = 8

    rng = np.random.default_rng(42)
    emb = rng.standard_normal((vocab_size, emb_dim)).astype(np.float32)

    nn_ids, nn_scores = compute_neighbors(emb, k=k, min_score=0.0)

    assert nn_ids.shape    == (vocab_size, k), f"nn_ids shape {nn_ids.shape}"
    assert nn_scores.shape == (vocab_size, k), f"nn_scores shape {nn_scores.shape}"
    assert nn_ids.dtype    == np.uint32
    assert nn_scores.dtype == np.float32

    # Scores should be sorted descending within each row
    for i in range(vocab_size):
        row = nn_scores[i]
        assert all(row[j] >= row[j + 1] for j in range(k - 1)), \
            f"Row {i} not sorted: {row}"

    # No self-neighbor
    for i in range(vocab_size):
        assert i not in nn_ids[i], f"Token {i} is its own neighbor"

    with tempfile.TemporaryDirectory() as tmp:
        out_dir = Path(tmp)
        write_neighbors(out_dir, nn_ids, nn_scores)
        assert (out_dir / "nn_ids.bin").exists()
        assert (out_dir / "nn_scores.bin").exists()
        # Round-trip check
        reloaded_ids = np.frombuffer(
            (out_dir / "nn_ids.bin").read_bytes(),
            dtype="<u4",
        ).reshape(vocab_size, k)
        reloaded_scores = np.frombuffer(
            (out_dir / "nn_scores.bin").read_bytes(),
            dtype="<f4",
        ).reshape(vocab_size, k)
        assert np.array_equal(nn_ids, reloaded_ids)
        assert np.allclose(nn_scores, reloaded_scores)

    print(f"Self-test PASSED  vocab={vocab_size}  k={k}")


if __name__ == "__main__":
    main()
