"""kv_i8_quant_blob_driver.mojo -- forces codegen of `kv_i8_quant._kv_i8_quant_kernel` (the
KV-write-side quant for the int8-KV decode mirror), following the established blob-driver pattern.
Discovery substring: `kv_i8_quant` (unique -- no other kernel family contains it; checked in the
session's discovery loop, see the wiring PR).

    cd mma_forge
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo build --emit object -I . -I ../attention_forge \
        -o /tmp/kv_i8_quant_forge.o ../attention_forge/kv_i8_quant_blob_driver.mojo
    python3 tools/extract_blob.py /tmp/kv_i8_quant_forge.o \
      ../attention_forge/generated/kv_i8_quant_blob.c --symbol algenta_kv_i8_quant_blob
"""
from max.gpu.host import DeviceContext
from kv_i8_quant import _kv_i8_quant_kernel


def main() raises:
    var ctx = DeviceContext()

    var h_kv: Int64 = 1
    var d_head: Int64 = 128
    var key_block_size: Int64 = 32
    var n_keys: Int64 = 64
    var n_blocks: Int64 = (n_keys + key_block_size - 1) // key_block_size
    var m_new: Int64 = 32

    var ck_f16 = ctx.enqueue_create_buffer[DType.float16](Int(h_kv * n_blocks * d_head * key_block_size))
    var cv_f16 = ctx.enqueue_create_buffer[DType.float16](Int(h_kv * n_blocks * key_block_size * d_head))
    var ck_i8 = ctx.enqueue_create_buffer[DType.int8](Int(h_kv * n_keys * d_head))
    var cv_i8 = ctx.enqueue_create_buffer[DType.int8](Int(h_kv * n_keys * d_head))
    var k_scale = ctx.enqueue_create_buffer[DType.float32](Int(h_kv * n_keys))
    var v_scale = ctx.enqueue_create_buffer[DType.float32](Int(h_kv * n_keys))

    ctx.enqueue_function[_kv_i8_quant_kernel](
        ck_f16.unsafe_ptr(), cv_f16.unsafe_ptr(), ck_i8.unsafe_ptr(), cv_i8.unsafe_ptr(),
        k_scale.unsafe_ptr(), v_scale.unsafe_ptr(),
        Int64(0), m_new, h_kv, d_head, key_block_size, n_blocks,
        grid_dim=Int(h_kv * m_new), block_dim=32,
    )
    print("KV I8 QUANT BLOB DRIVER: codegen forced")
