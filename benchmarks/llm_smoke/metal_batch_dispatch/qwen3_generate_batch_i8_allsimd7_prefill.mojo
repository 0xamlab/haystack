"""qwen3_generate_batch_i8_allsimd7_prefill.mojo — real-checkpoint smoke driver + benchmark for
`metaldispatch.qwen3_prefill_decode.qwen3_i8_allsimd7_prefill_decode_flat`.

    cd /Users/angel/Developer/decision-engine/mojo_env
    clang -c -fobjc-arc -O2 ../benchmarks/llm_smoke/metal_batch_dispatch/batch_shim.m -o /tmp/batch_shim.o
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      clang -c -O2 ../mma_forge/generated/mm8_blob.c -o /tmp/mm8_blob.o
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo build -D ALGENTA_GPU -I ../mojo/engine \
        ../benchmarks/llm_smoke/metal_batch_dispatch/qwen3_generate_batch_i8_allsimd7_prefill.mojo \
        -o /tmp/qwen3_prefill_gen \
        -Xlinker /tmp/batch_shim.o -Xlinker /tmp/mm8_blob.o -Xlinker -framework -Xlinker Metal \
        -Xlinker -framework -Xlinker Foundation -Xlinker -framework -Xlinker IOKit
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer /tmp/qwen3_prefill_gen
"""

from metaldispatch.contract import metaldispatch_status_name, MB_OK
from metaldispatch.qwen3_prefill_decode import qwen3_i8_allsimd7_prefill_decode_flat


def main() raises:
    var r = qwen3_i8_allsimd7_prefill_decode_flat("/tmp/qwen3smoke", 16)
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
