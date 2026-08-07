"""candidate_a_blob_driver.mojo -- forces codegen of CANDIDATE A's real GPU kernel
(`_attn_grouped_fa_kernel`, `grouped_fa_q8_k32_h2_sg8.mojo`) for blob extraction via
`mojo build --emit object`, following `mma_forge/mm8_driver.mojo`'s exact pattern (see that file's
own docstring for the mechanism this borrows verbatim). No GPU dispatch needs to actually succeed
for this step; `ctx.enqueue_function[kernel]` inside `main()` is what forces the compiler to lower
the kernel to AIR/metallib. Lands in the object file's `__TEXT,__const` as one `MTLB` blob
(`algenta_open_session`'s own scan loop already handles this -- Phase 0 mechanism, unmodified).

This is a Phase 2C VALIDATION exercise (Attention Compiler Plan v1.0) -- proving the cross-toolchain
blob-extraction-and-link mechanism (proven so far ONLY for `mm8.mojo`'s 7-argument GEMM kernels)
also carries Candidate A's 12-argument attention kernel (5 pointers + 7 scalars). Standalone,
throwaway driver -- not wired into any production build, not imported by anything under
`mojo/engine/`.

Representative buffer sizes below match the "tiny aligned" shape
`grouped_fa_q8_k32_h2_sg8_driver.mojo`'s own `test_correctness` already uses (n_tok_q=8, n_tok_k=64,
h_q=2, h_kv=1, d=128) -- small, GQA-valid (h_q even, group=2), native-packed KV sized for
key_block_size=32 with zero remainder (n_blocks=2, 64/32 exact).

    cd mma_forge
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo build --emit object -I . -I ../attention_forge \
        -o /tmp/candidate_a_forge.o ../attention_forge/candidate_a_blob_driver.mojo
    python3 tools/extract_blob.py /tmp/candidate_a_forge.o \
      ../attention_forge/generated/candidate_a_blob.c --symbol algenta_candidate_a_blob
"""
from max.gpu.host import DeviceContext
from grouped_fa_q8_k32_h2_sg8 import _attn_grouped_fa_kernel


def main() raises:
    var ctx = DeviceContext()

    var n_tok_q: Int64 = 8
    var n_tok_k: Int64 = 64
    var h_q: Int64 = 2
    var h_kv: Int64 = 1
    var d: Int64 = 128
    var key_block_size: Int64 = 32
    var n_blocks: Int64 = (n_tok_k + key_block_size - 1) // key_block_size  # = 2

    var q_buf = ctx.enqueue_create_buffer[DType.float16](Int(n_tok_q * h_q * d))
    var k_buf = ctx.enqueue_create_buffer[DType.float16](Int(h_kv * n_blocks * d * key_block_size))
    var v_buf = ctx.enqueue_create_buffer[DType.float16](Int(h_kv * n_blocks * key_block_size * d))
    var out_buf = ctx.enqueue_create_buffer[DType.float32](Int(n_tok_q * h_q * d))
    var lse_buf = ctx.enqueue_create_buffer[DType.float32](Int(h_q * n_tok_q))

    var n_q_blocks = (n_tok_q + 7) // 8
    var grid = n_q_blocks * (h_q // 2)
    var scale64: Float64 = 1.0 / Float64(128) ** 0.5
    var scale: Float32 = Float32(scale64)

    ctx.enqueue_function[_attn_grouped_fa_kernel](
        out_buf.unsafe_ptr(), lse_buf.unsafe_ptr(),
        q_buf.unsafe_ptr(), k_buf.unsafe_ptr(), v_buf.unsafe_ptr(),
        n_tok_q, n_tok_k, h_q, h_kv,
        scale, Int64(0), n_blocks,
        grid_dim=Int(grid), block_dim=256,
    )
    print("CANDIDATE A BLOB DRIVER: codegen forced")
