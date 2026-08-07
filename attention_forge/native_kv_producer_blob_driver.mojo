"""native_kv_producer_blob_driver.mojo -- forces codegen of the NATIVE-KV-PRODUCER's real GPU kernel
(`_native_kv_producer_kernel`, `native_kv_producer.mojo`) for blob extraction via `mojo build --emit
object`, following `candidate_a_blob_driver.mojo`'s exact pattern (itself following
`mma_forge/mm8_driver.mojo`'s own mechanism -- see that file's own docstring for the mechanism this
borrows verbatim). No GPU dispatch needs to actually succeed for this step; `ctx.enqueue_function
[kernel]` inside `main()` is what forces the compiler to lower the kernel to AIR/metallib. Lands in
the object file's `__TEXT,__const` as one `MTLB` blob (`algenta_open_session`'s own scan loop already
handles this -- Phase 0 mechanism, unmodified).

This is a Phase 2C wiring exercise (Attention Compiler Plan v1.0) -- the SECOND kernel (after
Candidate A's own `_attn_grouped_fa_kernel`) this session cross-compiles+extracts for real production
wiring into `_MBQwen3I8AllSimd7Prefill`, behind the new `use_native_grouped_fa_attn` flag. Standalone,
throwaway driver -- not wired into any production build itself, not imported by anything under
`mojo/engine/`; only its EXTRACTED BLOB (via `tools/extract_blob.py`) gets linked into a real binary.

Representative buffer sizes below mirror `candidate_a_blob_driver.mojo`'s own shape choice
(h_q=2, h_kv=1, d=128, key_block_size=32, n_blocks=2) so both blobs' driver shapes are directly
comparable -- `m_rows=8` prefill rows, GQA-valid (h_q even), native-KV-aligned (no ragged tail needed
for codegen purposes; codegen does not depend on runtime shape validity anyway).

    cd mma_forge
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo build --emit object -I . -I ../attention_forge \
        -o /tmp/native_kv_producer_forge.o ../attention_forge/native_kv_producer_blob_driver.mojo
    python3 tools/extract_blob.py /tmp/native_kv_producer_forge.o \
      ../attention_forge/generated/native_kv_producer_blob.c --symbol algenta_native_kv_producer_blob
"""
from max.gpu.host import DeviceContext
from native_kv_producer import _native_kv_producer_kernel


def main() raises:
    var ctx = DeviceContext()

    var m_rows: Int64 = 8
    var h_q: Int64 = 2
    var h_kv: Int64 = 1
    var d_head: Int64 = 128
    var key_block_size: Int64 = 32
    var n_tok_k: Int64 = 64
    var n_blocks: Int64 = (n_tok_k + key_block_size - 1) // key_block_size  # = 2
    var n_qkv = h_q * d_head + 2 * h_kv * d_head
    var n_pairs = d_head // 2

    var qkv_buf = ctx.enqueue_create_buffer[DType.float32](Int(m_rows * n_qkv))
    var qn_buf = ctx.enqueue_create_buffer[DType.float32](Int(d_head))
    var kn_buf = ctx.enqueue_create_buffer[DType.float32](Int(d_head))
    var cos_buf = ctx.enqueue_create_buffer[DType.float32](Int((n_tok_k + m_rows) * n_pairs))
    var sin_buf = ctx.enqueue_create_buffer[DType.float32](Int((n_tok_k + m_rows) * n_pairs))
    var q_rot_buf = ctx.enqueue_create_buffer[DType.float16](Int(m_rows * h_q * d_head))
    var k_native_buf = ctx.enqueue_create_buffer[DType.float16](Int(h_kv * n_blocks * d_head * key_block_size))
    var v_native_buf = ctx.enqueue_create_buffer[DType.float16](Int(h_kv * n_blocks * key_block_size * d_head))

    var n_units = h_q + h_kv
    var grid = n_units * m_rows
    var eps: Float32 = 1.0e-6

    ctx.enqueue_function[_native_kv_producer_kernel](
        q_rot_buf.unsafe_ptr(), k_native_buf.unsafe_ptr(), v_native_buf.unsafe_ptr(),
        qkv_buf.unsafe_ptr(), qn_buf.unsafe_ptr(), kn_buf.unsafe_ptr(),
        cos_buf.unsafe_ptr(), sin_buf.unsafe_ptr(),
        Int64(0), h_q, h_kv, d_head, key_block_size, n_blocks, eps, m_rows,
        grid_dim=Int(grid), block_dim=Int(d_head),
    )
    print("NATIVE KV PRODUCER BLOB DRIVER: codegen forced")
