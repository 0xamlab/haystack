"""
lossk — training objectives: cross-entropy over a real vocabulary, and preference losses.

Where the frozen tree already is
----------------------------------
`numerical_stability` holds the reductions this needs and they are called unchanged (rule 3):
`logsumexp` is max-shifted, `log_sigmoid` is `-softplus(-x)` with the standard large-magnitude
branches. `loss_functions` and `information_theory` hold per-element loss formulas.

What is absent is the SHAPE. Every frozen loss helper takes either a scalar pair or one probability
vector; none of them takes a batch of hidden states, a projection weight and a target list, which is
what a training step actually has. And nothing anywhere addresses the memory problem that makes the
output layer different from every other layer in a transformer.

The memory problem, stated with its number
--------------------------------------------
Every other layer is `O(tokens x hidden)`. The output projection is `O(tokens x VOCAB)`, and
vocabulary is two orders of magnitude larger: a 2048-token batch against Qwen3's 151,936-token
vocabulary materializes **2.5 GB of 64-bit logits** in order to produce one scalar.

Cross-entropy does not need that tensor. Per token it needs the logit of the correct class and the
log-sum-exp over all classes — both reductions. So `cross_entropy` projects a CHUNK of tokens, reduces
it, and reuses the buffer. Peak logit memory becomes `chunk x vocab` and stops depending on the batch.

What this does NOT save, said plainly: the weight gradient is `[vocab][d_model]` — the size of the
weight itself — because every class receives gradient from every token's log-sum-exp. Chunking removes
the logits, not the weight gradient. "Fused cross-entropy saves memory" is easy to over-read, so the
backward's docstring says exactly which buffer it does and does not remove.

Chunk size is the caller's
----------------------------
A kernel that picked its own chunk would be picking the caller's peak memory while blind to what else
is resident — optimizer state, a KV cache, another rank's buffers. So the chunk is validated against
`LOSS_MAX_LOGIT_CELLS` and an over-large one is REFUSED, never clamped. A silent clamp turns "I asked
for 2048" into "you got 883" with nothing to notice.

And because the chunk is a memory decision rather than a numerical one, the answer must not depend on
it: per-token losses are summed in token order regardless of chunking, and
`ce_chunk_invariance_flat` asserts that one token at a time and the whole batch at once agree.

Modules
-------
  contract       — status codes 580-599, shape and chunk validation, the logit-cell budget
  cross_entropy  — fused projection + cross-entropy, chunked, forward and backward

Dependency direction is one-way: `lossk` uses `tensorx` for finiteness and the frozen
`numerical_stability` reductions, never the reverse.
"""
