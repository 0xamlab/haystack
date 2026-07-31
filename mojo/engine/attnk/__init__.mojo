"""
attnk — attention positional encoding, masks and score kernels. Zero Python.

Where the frozen tree already is
----------------------------------
`transformer_attention`, `flash_attention`, `sparse_attention` and `transformer_blocks` between them
hold about forty scalar helpers covering exactly the arithmetic an attention kernel needs: one
rotation angle, one mask value, one online-softmax max update, one block rescale. They are frozen,
correct, and this package calls them rather than restating their formulas — `flash.mojo` in
particular drives the frozen online-softmax recurrence one block at a time rather than writing its
own.

What is genuinely absent is the loop around them: nothing in the tree takes a Q, a K and a V and
returns attention over a real sequence, and nothing decides *which* of two disagreeing frozen
conventions a caller gets.

Three frozen pairs, measured rather than assumed
--------------------------------------------------
Each of these quantities has two frozen spellings. All six functions stay reachable and unchanged;
what this package adds is a stated choice and a reported delta, so a caller comparing against another
implementation gets a number instead of a surprise. Measured on 2026-07-31:

| Quantity | The two spellings | Result |
|---|---|---|
| Causal mask | `transformer_attention.causal_mask_value` vs `transformer_blocks.causal_mask_logit` | **Not a disagreement — different functions.** The first returns an additive bias (`0.0` / `-1e9`); the second returns the masked *logit*. Both are right for their own callers. |
| RoPE theta scaling | `model_abi.rope_theta_scale` vs `model_interop.hf_rope_theta_scale` | **A real 4x disagreement.** Extending 2048 to 8192 gives 160000 and 40000 respectively — one scales theta by the squared factor, the other linearly. Both conventions exist in the wild. |
| GQA group size | `flash_attention.grouped_query_attention_scale` vs `model_abi.kv_head_group_size` | **They agree** (32 query heads over 8 KV heads gives 4.0 either way). Recorded because "two spellings" does not imply "two answers", and assuming it does would have been its own error. |

The RoPE one is the dangerous member of the set. A model loaded with the wrong theta convention does
not fail — it produces fluent text that degrades with context length, which reads as a bad model
rather than a bad constant.

Modules
-------
  contract  — status codes 360-379, shape and work budgets for attention
  rope      — rotary position embedding: tables, application, and the theta convention
  mask      — causal, sliding-window, padding and packed-sequence masks as additive bias

Dependency direction is one-way: `attnk` uses `tensorx` for tolerances and finiteness and `gemm` for
the score and context products, never the reverse.
"""
