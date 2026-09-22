"""Tab 2 — LLM output scorer: BLEU + chrF via sacrebleu-mojo, raced live.

Single-pair scoring works on any backend (the vendored pure-Python fallback is
bit-exact too); the *race* requires the native Mojo kernel — if it did not
load, the race is held rather than benchmarking the fallback as "mojo".

Correctness contract: sacrebleu-mojo matches the published sacrebleu 2.5.1
package within 1e-9 on both backends (BLEU bit-exact in practice); the race
re-verifies agreement live before showing any timing.
"""

from __future__ import annotations

import json
import random
import statistics
import time

from lab.hardware import hardware_footer

ORACLE_NAME = "sacrebleu 2.5.1"
GATE_TOL = 1e-9
RACE_REPS = 5
RACE_VOCAB = 12_000
RACE_SEED = 20260920


def _parse_references(references: str) -> list[str]:
    """Blank-line-separated reference texts → a clean list."""
    import re

    return [chunk.strip() for chunk in re.split(r"\n\s*\n", references or "") if chunk.strip()]


def score_pair(hypothesis: str, references: str) -> tuple[str, str]:
    """Score one hypothesis against one or more references. Never raises."""
    try:
        hypothesis = (hypothesis or "").strip()
        refs = _parse_references(references)
        if not hypothesis:
            return "", "⚠️ Paste a hypothesis (the model output to score)."
        if not refs:
            return "", "⚠️ Paste at least one reference text (blank line between multiple)."

        import sacrebleu
        import sacrebleu_mojo

        t0 = time.perf_counter()
        bleu = sacrebleu_mojo.corpus_bleu([hypothesis], [refs])
        chrf = sacrebleu_mojo.corpus_chrf([hypothesis], [refs])
        scored_ms = (time.perf_counter() - t0) * 1e3

        # Live cross-check against the oracle package (cheap for one pair).
        oracle_bleu = sacrebleu.corpus_bleu([hypothesis], [refs])
        oracle_chrf = sacrebleu.corpus_chrf([hypothesis], [refs])
        d_bleu = abs(bleu.score - oracle_bleu.score)
        d_chrf = abs(chrf.score - oracle_chrf.score)

        backend = sacrebleu_mojo.backend_info()
        backend_label = (
            "native Mojo kernel" if backend.get("native_available") else "pure-Python fallback"
        )
        body = {
            "bleu": {
                "score": round(bleu.score, 4),
                "precisions": [round(p, 2) for p in bleu.precisions],
                "brevity_penalty": round(bleu.bp, 4),
                "sys_len": bleu.sys_len,
                "ref_len": bleu.ref_len,
                "counts": list(bleu.counts),
                "totals": list(bleu.totals),
            },
            "chrf": {"score": round(chrf.score, 4), "char_order": 6, "word_order": 0, "beta": 2},
            "oracle_crosscheck": {
                "sacrebleu_bleu": round(oracle_bleu.score, 6),
                "abs_delta_bleu": d_bleu,
                "sacrebleu_chrf": round(oracle_chrf.score, 6),
                "abs_delta_chrf": d_chrf,
            },
        }
        verdict = (
            f"✅ **deterministic scoring** — same input → same score, every run. "
            f"Scored in {scored_ms:,.2f} ms on the {backend_label} "
            f"(sacrebleu-mojo 0.1.2); oracle {ORACLE_NAME} agreement: "
            f"|Δ BLEU| = {d_bleu:.1e}, |Δ chrF| = {d_chrf:.1e} "
            f"(kernel differential tests assert ≤ 1e-9; BLEU is bit-exact in practice).\n\n"
            f"<span class='card-hw'>{len(refs)} reference(s) · {hardware_footer()}</span>"
        )
        return json.dumps(body, indent=2), verdict
    except Exception as exc:
        return "", f"⏸️ **scoring held** — {type(exc).__name__}: {exc}. No numbers shown."


def _race_batch(n_pairs: int) -> tuple[list[str], list[str]]:
    """Seeded synthetic hypothesis/reference pairs (Zipf-ish vocab, 10-40 tokens)."""
    rng = random.Random(RACE_SEED + n_pairs)
    vocab = [f"w{i:05d}" for i in range(RACE_VOCAB)]
    weights = [1.0 / (i + 1) for i in range(RACE_VOCAB)]
    hyps, refs = [], []
    for _ in range(n_pairs):
        hyps.append(" ".join(rng.choices(vocab, weights, k=rng.randint(10, 40))))
        refs.append(" ".join(rng.choices(vocab, weights, k=rng.randint(10, 40))))
    return hyps, refs


def race_scorers(n_pairs: int) -> tuple[str, str]:
    """Race sacrebleu-mojo against the oracle on a seeded batch. Never raises."""
    try:
        n_pairs = int(n_pairs)
        if n_pairs <= 0 or n_pairs > 10_000:
            return "", "⚠️ Batch size must be between 1 and 10,000 pairs."

        import sacrebleu
        import sacrebleu_mojo

        backend = sacrebleu_mojo.backend_info()
        if not backend.get("native_available"):
            return "", (
                "⏸️ **race held** — the native sacrebleu-mojo kernel did not load on this host "
                f"({backend.get('error') or 'fallback active'}). The single-pair scorer above "
                "still works (the fallback is bit-exact), but per the harness rule the "
                "pure-Python fallback is never raced as 'mojo'."
            )

        hyps, refs = _race_batch(n_pairs)

        # --- gate first: scores must agree within 1e-9 before any timing ----
        oracle_bleu = sacrebleu.corpus_bleu(hyps, [refs])
        mojo_bleu = sacrebleu_mojo.corpus_bleu(hyps, [refs])
        oracle_chrf = sacrebleu.corpus_chrf(hyps, [refs])
        mojo_chrf = sacrebleu_mojo.corpus_chrf(hyps, [refs])
        d_bleu = abs(oracle_bleu.score - mojo_bleu.score)
        d_chrf = abs(oracle_chrf.score - mojo_chrf.score)
        if d_bleu > GATE_TOL or d_chrf > GATE_TOL:
            return "", (
                f"⏸️ **race held** — correctness gate failed: |Δ BLEU| = {d_bleu:.3e}, "
                f"|Δ chrF| = {d_chrf:.3e} exceed the 1e-9 gate vs {ORACLE_NAME}. No timing shown."
            )

        # --- warm median-of-5, lanes interleaved per rep --------------------
        samples = {"bleu_oracle": [], "bleu_mojo": [], "chrf_oracle": [], "chrf_mojo": []}
        for _ in range(RACE_REPS):
            t0 = time.perf_counter()
            sacrebleu.corpus_bleu(hyps, [refs])
            samples["bleu_oracle"].append(time.perf_counter() - t0)
            t0 = time.perf_counter()
            sacrebleu_mojo.corpus_bleu(hyps, [refs])
            samples["bleu_mojo"].append(time.perf_counter() - t0)
            t0 = time.perf_counter()
            sacrebleu.corpus_chrf(hyps, [refs])
            samples["chrf_oracle"].append(time.perf_counter() - t0)
            t0 = time.perf_counter()
            sacrebleu_mojo.corpus_chrf(hyps, [refs])
            samples["chrf_mojo"].append(time.perf_counter() - t0)

        med = {k: statistics.median(v) * 1e3 for k, v in samples.items()}
        bleu_speedup = med["bleu_oracle"] / med["bleu_mojo"] if med["bleu_mojo"] > 0 else 0.0
        chrf_speedup = med["chrf_oracle"] / med["chrf_mojo"] if med["chrf_mojo"] > 0 else 0.0

        table = (
            f"| metric | {ORACLE_NAME} warm (ms) | sacrebleu-mojo warm (ms) | speedup |\n"
            f"|---|---:|---:|---:|\n"
            f"| corpus BLEU (13a tokenizer) | {med['bleu_oracle']:,.1f} | {med['bleu_mojo']:,.1f} "
            f"| **{bleu_speedup:,.2f}×** |\n"
            f"| corpus chrF (char_order 6, β 2) | {med['chrf_oracle']:,.1f} | {med['chrf_mojo']:,.1f} "
            f"| **{chrf_speedup:,.2f}×** |\n"
        )
        verdict = (
            f"✅ **gate passed** — |Δ BLEU| = {d_bleu:.1e}, |Δ chrF| = {d_chrf:.1e} vs "
            f"{ORACLE_NAME} on {n_pairs:,} seeded pairs (≤ 1e-9 required; BLEU scores agreed "
            f"bit-for-bit on this run: {d_bleu == 0.0}).\n\n"
            f"Warm = median of {RACE_REPS}, lanes interleaved. Batch: {n_pairs:,} synthetic "
            f"pairs, 10–40 tokens, Zipf-ish {RACE_VOCAB:,}-term vocab, seed {RACE_SEED}. "
            f"BLEU's end-to-end speedup is bounded by the mteval-v13a tokenizer, which runs "
            f"in Python on both sides; the Mojo kernel computes the corpus n-gram statistics "
            f"~20× faster than the reference loops.\n\n"
            f"<span class='card-hw'>{hardware_footer()}</span>"
        )
        return table, verdict
    except Exception as exc:
        return "", f"⏸️ **race held** — {type(exc).__name__}: {exc}. No numbers shown."
