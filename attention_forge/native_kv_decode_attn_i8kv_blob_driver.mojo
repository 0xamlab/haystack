"""native_kv_decode_attn_i8kv_blob_driver.mojo -- forces codegen of the INT8-KV split-K decode
partial v4 (`native_kv_decode_attn_i8kv._native_kv_decode_splitk_partial_i8kv4`), following
`native_kv_decode_attn_splitk_blob_driver.mojo`'s exact pattern. No GPU dispatch needs to actually
succeed; `ctx.enqueue_function[kernel]` inside `main()` forces the compiler to lower the kernel to
AIR/metallib. Lands in the object file's `__TEXT,__const` as one `MTLB` blob; the session discovers
it by `"native_kv_decode_attn_i8kv"` (longest-first, before the naive kernel's substring -- see
`native_kv_decode_attn_i8kv.mojo`'s module docstring for the collision analysis that makes this
module's name load-bearing).

    cd mma_forge
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo build --emit object -I . -I ../attention_forge \
        -o /tmp/native_kv_decode_attn_i8kv_forge.o \
        ../attention_forge/native_kv_decode_attn_i8kv_blob_driver.mojo
    python3 tools/extract_blob.py /tmp/native_kv_decode_attn_i8kv_forge.o \
      ../attention_forge/generated/native_kv_decode_attn_i8kv_blob.c \
      --symbol algenta_native_kv_decode_attn_i8kv_blob
"""
from max.gpu.host import DeviceContext
from native_kv_decode_attn_i8kv import _native_kv_decode_splitk_partial_i8kv4


def main() raises:
    var ctx = DeviceContext()

    var h_q: Int64 = 2
    var h_kv: Int64 = 1
    var d_head: Int64 = 128
    var key_block_size: Int64 = 32
    var n_tok_k: Int64 = 64
    var n_blocks: Int64 = (n_tok_k + key_block_size - 1) // key_block_size  # = 2
    var n_splits: Int64 = 16

    var q_buf = ctx.enqueue_create_buffer[DType.float16](Int(h_q * d_head))
    var k_i8_buf = ctx.enqueue_create_buffer[DType.int8](Int(h_kv * n_tok_k * d_head))
    var v_i8_buf = ctx.enqueue_create_buffer[DType.int8](Int(h_kv * n_tok_k * d_head))
    var k_scale_buf = ctx.enqueue_create_buffer[DType.float32](Int(h_kv * n_tok_k))
    var v_scale_buf = ctx.enqueue_create_buffer[DType.float32](Int(h_kv * n_tok_k))
    var m_buf = ctx.enqueue_create_buffer[DType.float32](Int(h_q * n_splits))
    var l_buf = ctx.enqueue_create_buffer[DType.float32](Int(h_q * n_splits))
    var o_buf = ctx.enqueue_create_buffer[DType.float32](Int(h_q * n_splits * d_head))

    var scale64: Float64 = 1.0 / Float64(128) ** 0.5
    var scale: Float32 = Float32(scale64)

    ctx.enqueue_function[_native_kv_decode_splitk_partial_i8kv4](
        m_buf.unsafe_ptr(), l_buf.unsafe_ptr(), o_buf.unsafe_ptr(),
        q_buf.unsafe_ptr(), k_i8_buf.unsafe_ptr(), v_i8_buf.unsafe_ptr(),
        k_scale_buf.unsafe_ptr(), v_scale_buf.unsafe_ptr(),
        n_tok_k, n_splits, h_q, h_kv, d_head, scale, key_block_size, n_blocks,
        grid_dim=Int(h_q * n_splits), block_dim=Int(d_head // 4),
    )
    print("NATIVE KV DECODE ATTN I8KV V4 BLOB DRIVER: codegen forced")
