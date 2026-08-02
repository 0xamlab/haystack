"""
llmk — the one forward-pass glue kernel a real transformer checkpoint needed that nothing else in
the tree supplied. Zero Python. Additive: nothing frozen moves, nothing in attnk/normk/mlpk/gemm
changes.

Why this package exists, stated exactly
------------------------------------------
Wiring a real Qwen3-0.6B-Base checkpoint through the existing LLM-plane kernels
(`benchmarks/llm_smoke/qwen3_forward.mojo`) found three candidate gaps. Two of them were already
closed by packages merged earlier in the same plane, and calling them (rule 3) rather than writing a
second copy under a different package's status codes was the correct move for both:

1. Embedding-table gather — `mlpk.embedding.embedding_fwd_flat` already does exactly this
   (bounds-checked row lookup by token id, parallel by token). Used as-is.
2. Half-split RoPE — `attnk.rope.rope_apply_flat(..., interleaved=False)` already implements the
   GPT-NeoX split-half pairing (`(0, d/2), (1, d/2+1), ...`), which is exactly Qwen3/Llama's
   `apply_rotary_pos_emb` convention. Used as-is, alongside `attnk.rope.rope_table` for the cos/sin
   cache and `attnk.mask.mask_causal_flat` for the additive causal bias `attnk.sdpa.sdpa_forward_flat`
   takes.
3. Elementwise residual-add-of-two-whole-buffers — genuinely absent. `transformer_blocks` and
   `fused_kernels` only have scalar, one-`Float64`-at-a-time residual helpers. This package supplies
   the missing driver.

Modules
-------
  contract   — status codes 560-579, the shape checks `residual_add_flat`/`generate.mojo` need
  residual   — residual_add_flat: y = a + b over two same-length flat buffers, parallel by band
  generate   — kv_cache_append_flat + greedy_argmax_flat: the two pieces a real decode loop needed
               that `residual_add_flat`'s forward-pass-only session did not yet reach. See
               `generate.mojo`'s own docstring for why exactly these two and nothing else — the
               actual per-layer decode step (which frozen kernel gets called at which shape, prefill
               vs. one-new-token) is the driver's job, `benchmarks/llm_smoke/qwen3_generate.mojo`,
               not this package's — this package supplies only what no frozen kernel already did.

Dependency direction is one-way: `llmk` uses `tensorx` for finiteness and `llm_sampling` for the
frozen greedy formula, and never the reverse, exactly like attnk/normk/mlpk.

What this package is NOT
--------------------------
Not a general transformer-forward-pass ABI (that is the enterprise plan's phases 2-8, explicitly out
of scope for this smoke test). Not an embedding or RoPE kernel — both of those already existed and
this package calls them rather than shadowing them. Not a sampling-formula package — `llm_sampling`
and `generation_loop` already own that surface (temperature, top-k/top-p, penalties); `generate.mojo`
calls `greedy_token_id` from the former, unmodified, rather than adding a second implementation.
"""
