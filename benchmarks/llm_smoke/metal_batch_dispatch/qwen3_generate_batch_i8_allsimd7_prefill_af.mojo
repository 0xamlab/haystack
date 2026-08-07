"""qwen3_generate_batch_i8_allsimd7_prefill_af.mojo — real-checkpoint smoke driver + benchmark for
`metaldispatch.qwen3_prefill_decode.qwen3_i8_allsimd7_prefill_decode_flat_af`, the Attention Compiler
Plan v1.0 Phase 2C entry point that exposes `_MBQwen3I8AllSimd7Prefill.use_native_grouped_fa_attn`.

NOT a modification of `qwen3_generate_batch_i8_allsimd7_prefill.mojo` -- a new, analogous file, per
this task's own instruction not to overwrite the existing benchmark. `USE_AF` below is the ONE
hand-edited toggle this driver exposes (mirroring `use_block8_attn`'s own source-level-toggle
discipline in `session_prefill.mojo` itself) -- set `False` to reproduce the existing, unmodified
benchmark's own behavior byte-for-byte (via the new `_af` entry point, which is provably identical to
the original for `use_native_grouped_fa_attn=False`), or `True` to exercise Candidate A + the
native-KV-producer.

Needs TWO more forged blobs linked in than the original benchmark, in addition to the existing
`mm8_blob.c` -- `attention_forge/generated/candidate_a_blob.c` and `attention_forge/generated/
native_kv_producer_blob.c` (built via `mma_forge`'s nightly toolchain + `tools/extract_blob.py`,
exactly `candidate_a_blob_driver.mojo`'s/`native_kv_producer_blob_driver.mojo`'s own proven recipe --
see those files' own docstrings). Safe to link even with `USE_AF = False`: `_MBQwen3I8AllSimd7Prefill.
__init__`'s own AF-pipeline discovery is non-fatal either way (see `_classify_attention_forge_
pipeline`'s docstring in `metaldispatch.session`), so linking these two blobs never changes the
OFF-path's own behavior, only makes the ON path AVAILABLE.

    cd /Users/angel/Developer/decision-engine/mojo_env
    clang -c -fobjc-arc -O2 ../benchmarks/llm_smoke/metal_batch_dispatch/batch_shim.m -o /tmp/batch_shim.o
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      clang -c -O2 ../mma_forge/generated/mm8_blob.c -o /tmp/mm8_blob.o
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      clang -c -O2 ../attention_forge/generated/candidate_a_blob.c -o /tmp/candidate_a_blob.o
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      clang -c -O2 ../attention_forge/generated/native_kv_producer_blob.c -o /tmp/native_kv_producer_blob.o
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo build -D ALGENTA_GPU -I ../mojo/engine \
        ../benchmarks/llm_smoke/metal_batch_dispatch/qwen3_generate_batch_i8_allsimd7_prefill_af.mojo \
        -o /tmp/qwen3_prefill_gen_af \
        -Xlinker /tmp/batch_shim.o -Xlinker /tmp/mm8_blob.o \
        -Xlinker /tmp/candidate_a_blob.o -Xlinker /tmp/native_kv_producer_blob.o \
        -Xlinker -framework -Xlinker Metal -Xlinker -framework -Xlinker Foundation \
        -Xlinker -framework -Xlinker IOKit
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer /tmp/qwen3_prefill_gen_af
"""

from metaldispatch.contract import metaldispatch_status_name, MB_OK
from metaldispatch.qwen3_prefill_decode import qwen3_i8_allsimd7_prefill_decode_flat_af

comptime USE_AF: Bool = False
"""Hand-edit and rebuild to switch arms -- see module docstring. `False` reproduces the existing
`qwen3_generate_batch_i8_allsimd7_prefill.mojo` benchmark's own behavior via the new `_af` entry
point (non-regression check); `True` exercises Candidate A + the native-KV-producer."""

comptime MAX_NEW_TOKENS: Int = 1 if USE_AF else 16
"""Historically `1` when `USE_AF`, to issue ZERO `step()` (decode) calls (`range(1, 1)` is empty)
and sidestep what was then a documented, not-yet-closed gap: `step()` reading the natural `ck`/`cv`
cache the AF prefill path never populated. That gap is now CLOSED (`_MBQwen3I8AllSimd7Prefill`'s own
AF descriptor table double-writes `ck`/`cv` via an additional `_pf_ropewrt_kernel` dispatch --  see
`use_native_grouped_fa_attn`'s field docstring in `session_prefill.mojo`, and `qwen3_i8_allsimd7_
prefill_decode_flat_af`'s own docstring, for the full account), proven for single-chunk prefill
(this benchmark's own prompt fits in one `PREFILL_MAX_TILE` chunk) followed by decode. Left at `1`
here anyway: this file measures PREFILL throughput specifically (`prefill_tokens_per_sec`), and this
session has not re-run this exact benchmark binary with `MAX_NEW_TOKENS > 1` under `USE_AF=True` to
re-confirm end-to-end decode speed/correctness through the full real-checkpoint smoke path (as
opposed to the golden-vector test, which does) -- raising this value is a reasonable, low-risk next
step, not something this change claims to have already done. `16`, matching the ORIGINAL benchmark's
own value, when `USE_AF=False`, so the two runs are comparable beyond just `prefill_tokens_per_sec`."""


def main() raises:
    var r = qwen3_i8_allsimd7_prefill_decode_flat_af("/tmp/qwen3smoke", MAX_NEW_TOKENS, USE_AF)
    print("USE_AF:", USE_AF)
    print("status:", metaldispatch_status_name(r.status))
    if r.status != MB_OK:
        print("error:", r.error_message)
        return
    print("n_prompt:", r.n_prompt)
    print("prefill_chunks:", r.prefill_chunks)
    print("prefill_tokens_per_sec:", r.prefill_tokens_per_sec)
    print("decode_tokens_per_sec:", r.decode_tokens_per_sec)
    print("dispatches_per_token(decode):", r.dispatches_per_token)
    print("stopped_on_eos:", r.stopped_on_eos)
    print("total token_ids:", len(r.token_ids))
    var tail = List[Int]()
    var start = len(r.token_ids) - 20
    if start < 0:
        start = 0
    for i in range(start, len(r.token_ids)):
        tail.append(r.token_ids[i])
    print("last ~20 token ids:", tail)
