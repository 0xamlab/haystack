"""kvprod_f1_blob_driver.mojo -- feat/llama-q80gap (2026-08-13): forces codegen of the
LANE-FUSED no-QK-norm native-KV producer (`kvprod_f1._kvprod_f1_kernel`) for blob extraction via
`mojo build --emit object`, following `native_kv_producer_blob_driver.mojo`'s exact pattern.
`ctx.enqueue_function[kernel]` inside `main()` forces the compiler to lower the kernel to
AIR/metallib; no GPU dispatch needs to actually succeed. Lands in the object file's
`__TEXT,__const` as one `MTLB` blob. MODULE NAMING: `kvprod_f1` (NOT `native_kv_producer_*`) so
the shared `_classify_attention_forge_pipeline` (which matches `native_kv_producer` for the
ORIGINAL producer role) never cross-wires the two -- same discipline `kvprod_batched` used.

    cd mma_forge
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo build --emit object -I . -I ../attention_forge \
        -o /tmp/kvprod_f1_forge.o ../attention_forge/kvprod_f1_blob_driver.mojo
    python3 tools/extract_blob.py /tmp/kvprod_f1_forge.o \
      ../attention_forge/generated/kvprod_f1_blob.c --symbol algenta_kvprod_f1_blob
"""

from max.gpu.host import DeviceContext
from kvprod_f1 import _kvprod_f1_kernel


def main() raises:
    var ctx = DeviceContext()

    var m_rows: Int64 = 1
    var h_q: Int64 = 32
    var h_kv: Int64 = 4
    var d_head: Int64 = 64
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
    # kvprod_f1 is the no-QK-norm (llama family) lane-fused producer -- codegen with qk_norm=0
    # (its only supported arm; the engine gates dispatch to qk_norm==0 models).
    var qk_norm: Int64 = 0

    ctx.enqueue_function[_kvprod_f1_kernel](
        q_rot_buf.unsafe_ptr(), k_native_buf.unsafe_ptr(), v_native_buf.unsafe_ptr(),
        qkv_buf.unsafe_ptr(), qn_buf.unsafe_ptr(), kn_buf.unsafe_ptr(),
        cos_buf.unsafe_ptr(), sin_buf.unsafe_ptr(),
        Int64(0), h_q, h_kv, d_head, key_block_size, n_blocks, eps, m_rows, qk_norm,
        grid_dim=Int(grid), block_dim=Int(d_head // 2),
    )
    print("KVPROD F1 BLOB DRIVER: codegen forced")
