"""
training/semantic/export_artifacts.py — Export trained model weights as flat
binary artifacts for the Mojo runtime loader.

Binary format contract (consumed by semantic_loader.mojo via from_buffers()):
  embeddings.bin            float32  [vocab_size × EMB_DIM]           row-major
  intent_fc1_weight.bin     float32  [HIDDEN_DIM × EMB_DIM]           row-major
  intent_fc1_bias.bin       float32  [HIDDEN_DIM]
  intent_fc2_weight.bin     float32  [INTENT_CLASSES × HIDDEN_DIM]    row-major
  intent_fc2_bias.bin       float32  [INTENT_CLASSES]
  agg_fc{1,2}_{weight,bias}.bin     — same pattern
  family_fc{1,2}_{weight,bias}.bin  — same pattern
  meta.json                 shape metadata + class label names
  vocab.json                token → id mapping (copied from build_vocab output)

All float32 arrays are written raw (little-endian, no header).
Python loads these with numpy.frombuffer / memoryview for FFI.

Usage:
    python3 training/semantic/export_artifacts.py \
        --checkpoint training/semantic/artifacts/model.pt \
        --vocab      training/semantic/artifacts/vocab.json \
        --out-dir    training/semantic/artifacts/

Self-test:
    python3 training/semantic/export_artifacts.py --self-test
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

try:
    import numpy as np
    import torch
except ImportError:
    print("torch and numpy required: pip install torch numpy")
    sys.exit(1)

from training.semantic.train_thin_semantic import (
    AGG_CLASSES,
    EMB_DIM,
    FAMILY_CLASSES,
    HIDDEN_DIM,
    INTENT_CLASSES,
    ThinSemanticModel,
)

# ── Class label metadata ──────────────────────────────────────────────────────

_META = {
    "emb_dim": EMB_DIM,
    "hidden_dim": HIDDEN_DIM,
    "intent_classes": INTENT_CLASSES,
    "agg_classes": AGG_CLASSES,
    "family_classes": FAMILY_CLASSES,
    "intent_labels": ["column_like", "meta_query", "weak_semantic", "unsupported"],
    "agg_labels": ["none", "count", "sum", "avg", "min", "max"],
    "family_labels": ["measure", "dimension", "date", "entity"],
}


def _write_f32(path: Path, tensor: torch.Tensor):
    """Write a tensor as raw float32 little-endian bytes."""
    arr = tensor.detach().cpu().float().numpy()
    path.write_bytes(arr.astype("<f4").tobytes())


def _read_f32(path: Path, shape: tuple) -> np.ndarray:
    """Read raw float32 bytes back into a numpy array."""
    import numpy as np

    raw = path.read_bytes()
    return np.frombuffer(raw, dtype="<f4").reshape(shape)


def export(
    model: ThinSemanticModel,
    out_dir: Path,
):
    """Export all weight tensors and metadata to out_dir."""
    out_dir.mkdir(parents=True, exist_ok=True)

    sd = model.state_dict()

    # ── Embeddings ────────────────────────────────────────────────────────
    _write_f32(out_dir / "embeddings.bin", sd["emb.weight"])

    # ── Intent head ───────────────────────────────────────────────────────
    _write_f32(out_dir / "intent_fc1_weight.bin", sd["intent.0.weight"])
    _write_f32(out_dir / "intent_fc1_bias.bin", sd["intent.0.bias"])
    _write_f32(out_dir / "intent_fc2_weight.bin", sd["intent.2.weight"])
    _write_f32(out_dir / "intent_fc2_bias.bin", sd["intent.2.bias"])

    # ── Aggregation head ──────────────────────────────────────────────────
    _write_f32(out_dir / "agg_fc1_weight.bin", sd["agg.0.weight"])
    _write_f32(out_dir / "agg_fc1_bias.bin", sd["agg.0.bias"])
    _write_f32(out_dir / "agg_fc2_weight.bin", sd["agg.2.weight"])
    _write_f32(out_dir / "agg_fc2_bias.bin", sd["agg.2.bias"])

    # ── Family head ───────────────────────────────────────────────────────
    _write_f32(out_dir / "family_fc1_weight.bin", sd["family.0.weight"])
    _write_f32(out_dir / "family_fc1_bias.bin", sd["family.0.bias"])
    _write_f32(out_dir / "family_fc2_weight.bin", sd["family.2.weight"])
    _write_f32(out_dir / "family_fc2_bias.bin", sd["family.2.bias"])

    # ── Metadata ──────────────────────────────────────────────────────────
    vocab_size = sd["emb.weight"].shape[0]
    meta = dict(_META)
    meta["vocab_size"] = vocab_size
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2))

    print(f"Exported {len(list(out_dir.glob('*.bin')))} binary files → {out_dir}")
    return meta


def verify_export(out_dir: Path, vocab_size: int):
    """
    Sanity-check: reload every binary file and verify shapes match meta.json.
    """
    meta = json.loads((out_dir / "meta.json").read_text())
    emb_dim = meta["emb_dim"]
    hidden_dim = meta["hidden_dim"]

    checks = [
        ("embeddings.bin", (vocab_size, emb_dim)),
        ("intent_fc1_weight.bin", (hidden_dim, emb_dim)),
        ("intent_fc1_bias.bin", (hidden_dim,)),
        ("intent_fc2_weight.bin", (meta["intent_classes"], hidden_dim)),
        ("intent_fc2_bias.bin", (meta["intent_classes"],)),
        ("agg_fc1_weight.bin", (hidden_dim, emb_dim)),
        ("agg_fc1_bias.bin", (hidden_dim,)),
        ("agg_fc2_weight.bin", (meta["agg_classes"], hidden_dim)),
        ("agg_fc2_bias.bin", (meta["agg_classes"],)),
        ("family_fc1_weight.bin", (hidden_dim, emb_dim)),
        ("family_fc1_bias.bin", (hidden_dim,)),
        ("family_fc2_weight.bin", (meta["family_classes"], hidden_dim)),
        ("family_fc2_bias.bin", (meta["family_classes"],)),
    ]

    all_ok = True
    for fname, expected_shape in checks:
        p = out_dir / fname
        if not p.exists():
            print(f"  MISSING  {fname}")
            all_ok = False
            continue
        arr = _read_f32(p, expected_shape)
        ok = arr.shape == expected_shape
        sym = "OK" if ok else "SHAPE_MISMATCH"
        if not ok:
            all_ok = False
            print(f"  {sym}  {fname}  got={arr.shape}  expected={expected_shape}")
    return all_ok


def main():
    parser = argparse.ArgumentParser(description="Export semantic model to Mojo-ready binaries")
    parser.add_argument("--checkpoint", type=Path, default=None)
    parser.add_argument("--vocab", type=Path, default=None)
    parser.add_argument("--out-dir", type=Path, default=Path("training/semantic/artifacts"))
    parser.add_argument("--verify", action="store_true", default=True)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        _run_self_test()
        return

    if not args.checkpoint or not args.vocab:
        parser.error("--checkpoint and --vocab are required")
    ckpt = torch.load(args.checkpoint, map_location="cpu", weights_only=True)
    vocab = json.loads(args.vocab.read_text())
    vocab_size = len(vocab)

    model = ThinSemanticModel(vocab_size=vocab_size)
    model.load_state_dict(ckpt["state_dict"])
    model.eval()

    export(model, args.out_dir)

    if args.verify:
        ok = verify_export(args.out_dir, vocab_size)
        print("Shape verification:", "PASSED" if ok else "FAILED")
        if not ok:
            sys.exit(1)

    # Copy vocab to artifacts dir for completeness
    dst = args.out_dir / "vocab.json"
    if not dst.exists():
        dst.write_text(args.vocab.read_text())


def _run_self_test():
    """Create a random model, export it, and verify the artifacts."""
    import tempfile

    vocab_size = 50
    model = ThinSemanticModel(vocab_size=vocab_size)
    model.eval()

    with tempfile.TemporaryDirectory() as tmp:
        out_dir = Path(tmp)
        export(model, out_dir)

        # Check all files present
        expected_bins = [
            "embeddings.bin",
            "intent_fc1_weight.bin",
            "intent_fc1_bias.bin",
            "intent_fc2_weight.bin",
            "intent_fc2_bias.bin",
            "agg_fc1_weight.bin",
            "agg_fc1_bias.bin",
            "agg_fc2_weight.bin",
            "agg_fc2_bias.bin",
            "family_fc1_weight.bin",
            "family_fc1_bias.bin",
            "family_fc2_weight.bin",
            "family_fc2_bias.bin",
        ]
        for f in expected_bins:
            assert (out_dir / f).exists(), f"Missing: {f}"

        ok = verify_export(out_dir, vocab_size)
        assert ok, "Shape verification failed"

        # Check embedding shape
        emb = _read_f32(out_dir / "embeddings.bin", (vocab_size, EMB_DIM))
        assert emb.shape == (vocab_size, EMB_DIM)

        # Check meta.json
        m = json.loads((out_dir / "meta.json").read_text())
        assert m["vocab_size"] == vocab_size
        assert m["emb_dim"] == EMB_DIM

    print("Self-test PASSED")


if __name__ == "__main__":
    main()
