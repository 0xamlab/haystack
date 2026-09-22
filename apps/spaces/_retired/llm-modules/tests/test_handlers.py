"""Exercise every live handler the Space exposes — against the real runtime.

Run inside the Space image (linux/amd64 py3.14, algenta + algenta-runtime-native
installed). No mocks: each test asserts on real kernel outputs whose values were
verified during Phase-1 probing.
"""

from __future__ import annotations

import json
import math

import app
from space_core import MODULES_22, catalog_rows


def test_tokenize_live():
    out, meta, trace, snippet = app.on_tokenize("Mojo kernels run live in this Space.")
    display = json.loads(out)
    assert display["tokens"] == ["mojo", "kernels", "run", "live", "in", "this", "space"]
    assert display["bpe_tokenizer_metrics_from_real_counts"]["chars"] == len(
        "Mojo kernels run live in this Space."
    )
    assert display["bpe_tokenizer_metrics_from_real_counts"]["tokens"] == 7
    assert math.isclose(
        display["bpe_tokenizer_metrics_from_real_counts"]["compression_ratio_chars_per_token"],
        len("Mojo kernels run live in this Space.") / 7.0,
    )
    assert "live kernel calls" in meta
    calls = json.loads(trace)
    assert {c["module"] for c in calls} == {"text.tokenizer", "bpe_tokenizer"}
    assert all(c["latency_ms"] >= 0 for c in calls)
    assert "MojoRuntime" in snippet


def test_retrieve_live():
    rows, scores_json, meta, trace, _snippet = app.on_retrieve(
        "how does flash attention save memory?"
    )
    assert len(rows) == 3
    flash_row = rows[0]
    assert flash_row[1] == "flash-attention"  # the demo hash-embedder must rank it first
    assert flash_row[2] > 0.0  # cosine similarity from the kernel
    scores = json.loads(scores_json)
    assert "flash-attention" in scores["all_cosine_scores"]
    # sparse cross-check equals the dense cosine (row displays dense rounded to 6dp)
    assert abs(float(rows[0][3]) - float(rows[0][2])) < 1e-6
    assert "not a neural model" in meta


def test_attention_parity_live():
    out, meta, trace, _snippet = app.on_attention()
    report = json.loads(out)
    assert report["verdict"] == "✅ outputs match"
    assert report["parity_max_abs_diff"] < 1e-9
    assert report["live_kernel_calls_this_run"] > 500
    assert report["mojo_path_wall_ms"] > 0 and report["numpy_reference_wall_ms"] > 0
    assert report["mojo_output_last_row"] == report["numpy_output_last_row"]  # rounded to 1e-6
    assert "honesty note" in meta


def test_ranker_live():
    rows, extra_json, meta, trace, _snippet = app.on_ranker(
        "user_email", "user_email\norder_total\ncreated_at"
    )
    assert rows[0][0] == "user_email"
    assert rows[0][1] > rows[1][1] > rows[2][1]  # score ordering
    extra = json.loads(extra_json)
    assert extra["ambiguous"] is False
    assert extra["confidence_gap"] > 0.5
    assert extra["query_vector_built_by_kernel"]["dim"] == 64
    assert extra["query_vector_built_by_kernel"]["nnz"] > 0


def test_serving_live():
    out, meta, trace, _snippet = app.on_serving(32, 8, 128, 4096, 8, 2.0, 16, 0.7, 5)
    display = json.loads(out)
    kv = display["kv_cache"]
    assert kv["per_layer_bytes"] == 8 * 4096 * 8 * 128 * 2 * 2  # batch·seq·heads·dim·dtype·(K+V)
    assert kv["total_bytes"] == kv["per_layer_bytes"] * 32
    assert kv["crosscheck_matches"] is True
    assert kv["paged_blocks_per_sequence"] == 4096 / 16
    assert display["speculative_decoding"]["expected_tokens_per_step"] > 1.0
    assert display["attention_flops_per_forward_pass"] > 0


def test_sampling_live():
    out, meta, trace, _snippet = app.on_sampling(2.0, 0.7, 0.15, 0.42, 0.05, 0.80, 0.90, 3, 5)
    pipe = json.loads(out)
    assert math.isclose(pipe["temperature_scaled_logit"], 2.0 / 0.7)
    assert math.isclose(pipe["min_p_threshold"], 0.42 * 0.05)
    assert pipe["min_p_accept(1=yes)"] == 1.0
    assert pipe["top_k_accept(1=yes)"] == 1.0
    assert pipe["top_p_accept(1=yes)"] == 1.0
    assert pipe["survives_all_gates"] is True
    # a token outside every gate must be rejected
    out2, *_ = app.on_sampling(2.0, 0.7, 0.01, 0.42, 0.05, 0.95, 0.90, 30, 5)
    pipe2 = json.loads(out2)
    assert pipe2["survives_all_gates"] is False


def test_eval_live():
    out, meta, trace, _snippet = app.on_eval("1,0,1,1,0", 3)
    metrics = json.loads(out)
    assert metrics["hit_rate_at_k"] == 1.0
    assert math.isclose(metrics["precision_at_k"], 2 / 3)
    assert math.isclose(metrics["recall_at_k"], 2 / 3)
    assert math.isclose(metrics["vector_similarity_cosine_from_parts"], 1.0)


def test_alignment_live():
    out, meta, trace, _snippet = app.on_alignment(0.8, -0.3, 0.1, 1.2, 1.5, 0.2, 1.2, 0.9, 0.4)
    losses = json.loads(out)
    assert math.isclose(losses["dpo_loss"], math.log1p(math.exp(-0.1 * (0.8 + 0.3))), rel_tol=1e-9)
    assert math.isclose(losses["ppo_clip_objective"], min(1.2 * 1.5, 1.2 * 1.5))
    assert math.isclose(losses["grpo_group_advantage"], (1.2 - 0.9) / 0.4)


def test_catalog_and_probes_live():
    rows = catalog_rows()
    assert len(rows) == 22
    assert {r[0] for r in rows} == set(MODULES_22)
    for module in MODULES_22:
        out, meta = app.on_probe(module)
        probe = json.loads(out)
        assert "error" not in probe, f"{module}: {out}"
        assert probe["module"] == module
        assert probe["envelope"]["result"] is not None or probe["result"] is not None


def test_eval_rejects_bad_input():
    out, meta, _trace, _snippet = app.on_eval("not,numbers", 3)
    assert "error" in json.loads(out)
