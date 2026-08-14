"""grouped_fa_steel_d64_blob_driver.mojo -- forces codegen of the d_head=64 steel prefill kernel
(`_attn_grouped_fa_d64_kernel`, `grouped_fa_steel_d64.mojo`) for blob extraction via
`mojo build --emit object`, following `candidate_a_blob_driver.mojo`'s exact pattern (see that
file's own docstring for the mechanism this borrows verbatim). No GPU dispatch needs to actually
succeed for this step; `ctx.enqueue_function[kernel]` inside `main()` is what forces the compiler
to lower the kernel to AIR/metallib. Lands in the object file's `__TEXT,__const` as one `MTLB`
blob (`algenta_open_session`'s own scan loop already handles this).

DISCOVERY NAMING: the module name `grouped_fa_steel_d64` (20 chars) fits whole inside the ~32-char
AIR name truncation budget, so the engine discovers it by the substring `grouped_fa_steel_d64` --
distinct from the d128 steel kernel's module `grouped_fa_q8_k32_h2_sg8` (the shared
`_classify_attention_forge_pipeline` pattern), from `native_kv_producer`, and from every other
attention-forge module. ONE kernel per blob (the f2/f2u2 precedent), so discovery is unambiguous.

    cd mma_forge
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo build --emit object -I . -I ../attention_forge \
        -o /tmp/grouped_fa_steel_d64_forge.o ../attention_forge/grouped_fa_steel_d64_blob_driver.mojo
    python3 tools/extract_blob.py /tmp/grouped_fa_steel_d64_forge.o \
      ../attention_forge/generated/grouped_fa_steel_d64_blob.c --symbol algenta_grouped_fa_steel_d64_blob
"""
from max.gpu.host import DeviceContext
from grouped_fa_steel_d64 import _attn_grouped_fa_d64_kernel


def main() raises:
    var ctx = DeviceContext()

    var n_tok_q: Int64 = 8
    var n_tok_k: Int64 = 64
    var h_q: Int64 = 4
    var h_kv: Int64 = 1
    var d: Int64 = 64
    var key_block_size: Int64 = 32
    var n_blocks: Int64 = (n_tok_k + key_block_size - 1) // key_block_size  # = 2

    var q_buf = ctx.enqueue_create_buffer[DType.float16](Int(n_tok_q * h_q * d))
    var k_buf = ctx.enqueue_create_buffer[DType.float16](Int(h_kv * n_blocks * d * key_block_size))
    var v_buf = ctx.enqueue_create_buffer[DType.float16](Int(h_kv * n_blocks * key_block_size * d))
    var out_buf = ctx.enqueue_create_buffer[DType.float32](Int(n_tok_q * h_q * d))
    var lse_buf = ctx.enqueue_create_buffer[DType.float32](Int(h_q * n_tok_q))

    var n_q_blocks = (n_tok_q + 31) // 32
    var grid = n_q_blocks * h_q
    var scale64: Float64 = 1.0 / Float64(64) ** 0.5
    var scale: Float32 = Float32(scale64)

    ctx.enqueue_function[_attn_grouped_fa_d64_kernel](
        out_buf.unsafe_ptr(), lse_buf.unsafe_ptr(),
        q_buf.unsafe_ptr(), k_buf.unsafe_ptr(), v_buf.unsafe_ptr(),
        n_tok_q, n_tok_k, h_q, h_kv,
        scale, Int64(0), n_blocks,
        grid_dim=Int(grid), block_dim=128,
    )
    print("GROUPED FA STEEL D64 BLOB DRIVER: codegen forced")
