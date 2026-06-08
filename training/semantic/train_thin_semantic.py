"""
training/semantic/train_thin_semantic.py — Train the ultra-thin semantic model.

Architecture (mirrors semantic_types.mojo exactly):
  EmbeddingTable:  vocab_size × EMB_DIM (32)
  Intent head:     EMB_DIM → HIDDEN_DIM (24) → INTENT_CLASSES (4)
  Agg head:        EMB_DIM → HIDDEN_DIM (24) → AGG_CLASSES (6)
  Family head:     EMB_DIM → HIDDEN_DIM (24) → FAMILY_CLASSES (4)

Training:
  Loss = CE(intent) + CE(agg) + 0.5 × CE(family)
        + CONTRASTIVE_ALPHA × (1 − cos_sim(q_emb, col_emb))  [only for schema examples]

  The contrastive term pulls query embeddings toward their target column's
  embedding.  At inference, fast_resolver.py computes cosine similarity
  between the query embedding and all registered column embeddings — if
  confidence > 0.75, the LLM call is skipped entirely.

  Optimizer: AdamW, lr=3e-3, weight_decay=1e-4
  Schedule: cosine warmup (10% steps) + cosine decay
  Epochs: configurable (default 80), early stop on val plateau

All artifacts are written to --out-dir and can be memory-mapped by the Mojo
loader via export_artifacts.py.

Usage:
    python3 training/semantic/train_thin_semantic.py \
        --train training/semantic/train.jsonl \
        --vocab training/semantic/artifacts/vocab.json \
        --out-dir training/semantic/artifacts/ \
        --epochs 80

Self-test (no GPU needed, tiny dataset):
    python3 training/semantic/train_thin_semantic.py --self-test
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as functional
    from torch.utils.data import DataLoader, Dataset
except ImportError:
    print("PyTorch not found. Install with: pip install torch")
    sys.exit(1)


# ── Model dimensions (mirror semantic_types.mojo) ─────────────────────────────

EMB_DIM = 32
HIDDEN_DIM = 24
INTENT_CLASSES = 4
AGG_CLASSES = 6
FAMILY_CLASSES = 4

# Weight of contrastive alignment loss vs classification loss
CONTRASTIVE_ALPHA = 0.3


# ── Dataset ───────────────────────────────────────────────────────────────────


class SemanticDataset(Dataset):
    def __init__(self, records: list[dict], max_len: int = 16):
        self.records = records
        self.max_len = max_len

    def __len__(self):
        return len(self.records)

    def __getitem__(self, idx: int):
        r = self.records[idx]
        tids = r["tokens"][: self.max_len]
        pad_len = self.max_len - len(tids)
        tids = tids + [0] * pad_len
        mask = [1.0] * len(r["tokens"][: self.max_len]) + [0.0] * pad_len

        # col_tokens: contrastive alignment target (present for schema-derived examples)
        col_tids_raw = r.get("col_tokens") or []
        has_col = 1 if col_tids_raw else 0
        col_tids = col_tids_raw[: self.max_len]
        col_pad = self.max_len - len(col_tids)
        col_tids = col_tids + [0] * col_pad
        col_mask = [1.0] * len(col_tids_raw[: self.max_len]) + [0.0] * col_pad

        return {
            "token_ids": torch.tensor(tids, dtype=torch.long),
            "mask": torch.tensor(mask, dtype=torch.float),
            "col_ids": torch.tensor(col_tids, dtype=torch.long),
            "col_mask": torch.tensor(col_mask, dtype=torch.float),
            "has_col": torch.tensor(has_col, dtype=torch.float),
            "intent": torch.tensor(r["intent"], dtype=torch.long),
            "agg": torch.tensor(r["agg"], dtype=torch.long),
            "family": torch.tensor(r["family"], dtype=torch.long),
        }


# ── Model ─────────────────────────────────────────────────────────────────────


class ThinSemanticModel(nn.Module):
    """
    Ultra-thin semantic model.
    All weight shapes match the Mojo runtime layout exactly:
      emb.weight:  [vocab_size × EMB_DIM]
      head.fc1.weight: [HIDDEN_DIM × EMB_DIM]  (fc1.in_dim = EMB_DIM)
      head.fc2.weight: [n_classes × HIDDEN_DIM]
    """

    def __init__(self, vocab_size: int):
        super().__init__()
        self.emb = nn.Embedding(vocab_size, EMB_DIM, padding_idx=0)
        nn.init.normal_(self.emb.weight, std=0.02)
        self.emb.weight.data[0].zero_()  # <PAD> = zero

        def _head(n_out: int) -> nn.Sequential:
            return nn.Sequential(
                nn.Linear(EMB_DIM, HIDDEN_DIM, bias=True),
                nn.ReLU(),
                nn.Linear(HIDDEN_DIM, n_out, bias=True),
            )

        self.intent = _head(INTENT_CLASSES)
        self.agg = _head(AGG_CLASSES)
        self.family = _head(FAMILY_CLASSES)

    def encode(self, token_ids: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
        """Average-pool token embeddings, weighted by mask."""
        x = self.emb(token_ids)  # [B, T, D]
        w = mask.unsqueeze(-1)  # [B, T, 1]
        denom = w.sum(dim=1).clamp(min=1.0)
        return (x * w).sum(dim=1) / denom  # [B, D]

    def forward(self, token_ids: torch.Tensor, mask: torch.Tensor) -> dict:
        q = self.encode(token_ids, mask)
        return {
            "emb": q,  # [B, EMB_DIM] — query embedding for contrastive loss
            "intent": self.intent(q),
            "agg": self.agg(q),
            "family": self.family(q),
        }


# ── Cosine warmup + decay schedule ───────────────────────────────────────────


def cosine_schedule(step: int, total: int, warmup: int, min_lr: float = 1e-4) -> float:
    if step < warmup:
        return step / max(1, warmup)
    pct = (step - warmup) / max(1, total - warmup)
    return min_lr + 0.5 * (1.0 - min_lr) * (1.0 + math.cos(math.pi * pct))


# ── Training loop ─────────────────────────────────────────────────────────────


def train(
    model: ThinSemanticModel,
    train_ds: SemanticDataset,
    val_ds: SemanticDataset | None,
    epochs: int = 80,
    batch_size: int = 32,
    lr: float = 3e-3,
    patience: int = 12,
    device: str = "cpu",
) -> dict:
    """
    Train the model.  Returns metrics dict.
    """
    model = model.to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)

    total_steps = epochs * math.ceil(len(train_ds) / batch_size)
    warmup_steps = max(1, total_steps // 10)

    scheduler = torch.optim.lr_scheduler.LambdaLR(
        opt,
        lr_lambda=lambda s: cosine_schedule(s, total_steps, warmup_steps),
    )

    loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)

    best_val_acc = 0.0
    best_state = None
    patience_left = patience
    history: list[dict] = []

    for epoch in range(1, epochs + 1):
        model.train()
        total_loss = 0.0
        total_n = 0
        correct = 0

        for batch in loader:
            tids = batch["token_ids"].to(device)
            mask = batch["mask"].to(device)
            col_ids = batch["col_ids"].to(device)
            col_msk = batch["col_mask"].to(device)
            has_col = batch["has_col"].to(device)  # [B] float 0/1
            labels = {k: batch[k].to(device) for k in ("intent", "agg", "family")}

            out = model(tids, mask)
            loss = (
                functional.cross_entropy(out["intent"], labels["intent"])
                + functional.cross_entropy(out["agg"], labels["agg"])
                + 0.5 * functional.cross_entropy(out["family"], labels["family"])
            )

            # Contrastive alignment: pull query embedding toward column embedding
            # Only applies to schema-derived examples (has_col == 1)
            if has_col.sum() > 0:
                col_emb = model.encode(col_ids, col_msk)  # [B, D]
                cos_sim = functional.cosine_similarity(out["emb"], col_emb, dim=-1)  # [B]
                contrastive = ((1.0 - cos_sim) * has_col).sum() / has_col.sum().clamp(min=1)
                loss = loss + CONTRASTIVE_ALPHA * contrastive

            opt.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            scheduler.step()

            bs = tids.size(0)
            total_loss += loss.item() * bs
            total_n += bs
            correct += (out["intent"].argmax(1) == labels["intent"]).sum().item()

        train_acc = correct / max(1, total_n)
        avg_loss = total_loss / max(1, total_n)
        val_intent = _eval_intent_acc(model, val_ds, device) if val_ds else None

        row = {"epoch": epoch, "loss": avg_loss, "train_acc": train_acc, "val_acc": val_intent}
        history.append(row)

        if epoch % 10 == 0 or epoch == epochs:
            vs = f"val_acc={val_intent:.3f}" if val_intent is not None else ""
            print(f"  epoch {epoch:3d}  loss={avg_loss:.4f}  train_intent={train_acc:.3f}  {vs}")

        # Early stopping on val intent accuracy
        if val_intent is not None:
            if val_intent > best_val_acc + 1e-4:
                best_val_acc = val_intent
                best_state = {k: v.clone() for k, v in model.state_dict().items()}
                patience_left = patience
            else:
                patience_left -= 1
                if patience_left <= 0:
                    print(f"  Early stop at epoch {epoch} (best val_acc={best_val_acc:.3f})")
                    break

    if best_state is not None:
        model.load_state_dict(best_state)

    return {"history": history, "best_val_acc": best_val_acc}


def _eval_intent_acc(
    model: ThinSemanticModel,
    ds: SemanticDataset,
    device: str,
) -> float:
    model.eval()
    correct = 0
    total = 0
    loader = DataLoader(ds, batch_size=64, shuffle=False)
    with torch.no_grad():
        for batch in loader:
            tids = batch["token_ids"].to(device)
            mask = batch["mask"].to(device)
            labels = batch["intent"].to(device)
            out = model(tids, mask)
            correct += (out["intent"].argmax(1) == labels).sum().item()
            total += tids.size(0)
    return correct / max(1, total)


# ── Entry point ───────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Train thin semantic model")
    parser.add_argument("--train", type=Path, default=None)
    parser.add_argument("--vocab", type=Path, default=None)
    parser.add_argument("--out-dir", type=Path, default=Path("training/semantic/artifacts"))
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument("--batch", type=int, default=32)
    parser.add_argument("--val-split", type=float, default=0.15)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        _run_self_test()
        return

    if not args.train or not args.vocab:
        parser.error("--train and --vocab are required")
    vocab = json.loads(args.vocab.read_text())
    records = [json.loads(line) for line in args.train.read_text().splitlines() if line.strip()]
    val_n = max(1, int(len(records) * args.val_split))
    val_recs = records[-val_n:]
    train_recs = records[:-val_n]

    print(f"Training: {len(train_recs)}  Validation: {len(val_recs)}")

    model = ThinSemanticModel(vocab_size=len(vocab))
    ds_tr = SemanticDataset(train_recs)
    ds_val = SemanticDataset(val_recs)

    metrics = train(model, ds_tr, ds_val, epochs=args.epochs, batch_size=args.batch)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    ckpt_path = args.out_dir / "model.pt"
    torch.save(
        {"state_dict": model.state_dict(), "vocab_size": len(vocab), "metrics": metrics}, ckpt_path
    )
    print(f"Saved checkpoint: {ckpt_path}")
    print(f"Best val intent accuracy: {metrics['best_val_acc']:.3f}")


def _run_self_test():
    """Tiny dataset, 5 epochs — verifies classification + contrastive loss runs."""
    import random

    random.seed(42)
    torch.manual_seed(42)

    vocab_size = 100
    records = []
    for i in range(60):
        col_tids = [random.randint(2, vocab_size - 1) for _ in range(2)] if i % 3 == 0 else None
        records.append(
            {
                "tokens": [random.randint(2, vocab_size - 1) for _ in range(4)],
                "col_tokens": col_tids,
                "intent": random.randint(0, INTENT_CLASSES - 1),
                "agg": random.randint(0, AGG_CLASSES - 1),
                "family": random.randint(0, FAMILY_CLASSES - 1),
            }
        )

    model = ThinSemanticModel(vocab_size=vocab_size)
    ds = SemanticDataset(records)
    metrics = train(model, ds, val_ds=None, epochs=5, batch_size=16)

    assert "history" in metrics
    assert len(metrics["history"]) > 0
    final_loss = metrics["history"][-1]["loss"]
    assert final_loss < 5.0, f"Loss too high: {final_loss}"

    # Verify forward returns emb
    model.eval()
    sample = ds[0]
    with torch.no_grad():
        out = model(
            sample["token_ids"].unsqueeze(0),
            sample["mask"].unsqueeze(0),
        )
    assert "emb" in out and out["emb"].shape == (1, EMB_DIM), "emb missing from forward()"

    print(f"Self-test PASSED  final_loss={final_loss:.4f}")


if __name__ == "__main__":
    main()
