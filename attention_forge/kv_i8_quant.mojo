"""attention_forge.kv_i8_quant -- beat-llama.cpp campaign (2026-08-12): the KV-write-side
quantization kernel for the int8-KV decode mirror. Dispatched AFTER each kvprod in the prefill and
decode tables (separate dispatch by design: zero churn to the committed kvprod blob, and the mirror
stays an additive feature gated on the int8 blobs being linked).

One threadgroup per (kv-head, new key); 32 lanes x 4 dims = 128 dims. For the new key it reads the
f16 K COLUMN (the native K cache is the transposed QK^T layout [hk][block][d][k], so one key is 128
strided reads) and the f16 V ROW ([hk][block][k][d], 128 contiguous), computes each matrix's
per-KEY absmax with a threadgroup max-reduction, and writes the FLAT int8 mirror rows
([hk][key][d_head] -- exactly the layout `_native_kv_decode_splitk_partial_i8kv4` reads) plus the
per-key scales. Round-half-away-from-zero, clamp +/-127, scale guard 1e-12 -- byte-identical
quantization to the milestone driver's `_round_i8`.

    cd mma_forge
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \\
      pixi run mojo build --emit object -I . -I ../attention_forge \\
        -o /tmp/kv_i8_quant_forge.o ../attention_forge/kv_i8_quant_blob_driver.mojo
    python3 tools/extract_blob.py /tmp/kv_i8_quant_forge.o \\
      ../attention_forge/generated/kv_i8_quant_blob.c --symbol algenta_kv_i8_quant_blob
"""
from std.gpu import thread_idx, block_idx
from std.gpu.primitives.warp import shuffle_xor as _shuffle_xor

comptime _F16P = UnsafePointer[Float16, origin=MutAnyOrigin]
comptime _FP = UnsafePointer[Float32, origin=MutAnyOrigin]
comptime _I8P = UnsafePointer[Int8, origin=MutAnyOrigin]


def _tg_max(v: Float32) -> Float32:
    var t = v
    var x = _shuffle_xor(t, UInt32(16))
    t = t if t >= x else x
    x = _shuffle_xor(t, UInt32(8))
    t = t if t >= x else x
    x = _shuffle_xor(t, UInt32(4))
    t = t if t >= x else x
    x = _shuffle_xor(t, UInt32(2))
    t = t if t >= x else x
    x = _shuffle_xor(t, UInt32(1))
    t = t if t >= x else x
    return t


def _round_i8_kq(x: Float32) -> Int:
    var r = Int(x + Float32(0.5)) if x >= Float32(0.0) else -Int(-x + Float32(0.5))
    if r > 127:
        r = 127
    if r < -127:
        r = -127
    return r


def _kv_i8_quant_kernel(
    ck_f16: _F16P, cv_f16: _F16P,
    ck_i8: _I8P, cv_i8: _I8P,
    k_scale: _FP, v_scale: _FP,
    key0: Int64, m_new: Int64,
    h_kv: Int64, d_head: Int64, key_block_size: Int64, n_blocks: Int64,
):
    var idx = Int64(block_idx.x)
    var hk = idx // m_new
    var kk_new = idx % m_new
    var key = key0 + kk_new
    var block = key // key_block_size
    var kk = key % key_block_size
    var lane = Int64(thread_idx.x)
    var e0 = lane * 4

    # K column (transposed layout): element (d, kk) at block_base + d*kbs + kk.
    var k_base = (hk * n_blocks + block) * d_head * key_block_size + kk
    var k0v = Float32(ck_f16[Int(k_base + (e0 + 0) * key_block_size)])
    var k1v = Float32(ck_f16[Int(k_base + (e0 + 1) * key_block_size)])
    var k2v = Float32(ck_f16[Int(k_base + (e0 + 2) * key_block_size)])
    var k3v = Float32(ck_f16[Int(k_base + (e0 + 3) * key_block_size)])
    # V row (natural layout): element (kk, d) at row_base + e0..e0+3.
    var v_base = ((hk * n_blocks + block) * key_block_size + kk) * d_head + e0
    var v0v = Float32(cv_f16[Int(v_base + 0)])
    var v1v = Float32(cv_f16[Int(v_base + 1)])
    var v2v = Float32(cv_f16[Int(v_base + 2)])
    var v3v = Float32(cv_f16[Int(v_base + 3)])

    # Per-key absmax over the 128 dims (threadgroup reduction).
    var kabs = k0v if k0v >= -k0v else -k0v
    var t = k1v if k1v >= -k1v else -k1v
    if t > kabs:
        kabs = t
    t = k2v if k2v >= -k2v else -k2v
    if t > kabs:
        kabs = t
    t = k3v if k3v >= -k3v else -k3v
    if t > kabs:
        kabs = t
    var kmax = _tg_max(kabs)
    var vabs = v0v if v0v >= -v0v else -v0v
    t = v1v if v1v >= -v1v else -v1v
    if t > vabs:
        vabs = t
    t = v2v if v2v >= -v2v else -v2v
    if t > vabs:
        vabs = t
    t = v3v if v3v >= -v3v else -v3v
    if t > vabs:
        vabs = t
    var vmax = _tg_max(vabs)

    var ksc = kmax / Float32(127.0)
    if ksc < Float32(1.0e-12):
        ksc = Float32(1.0e-12)
    var vsc = vmax / Float32(127.0)
    if vsc < Float32(1.0e-12):
        vsc = Float32(1.0e-12)

    # Flat mirror row for this key: [hk][key][d].
    var out_base = (hk * (n_blocks * key_block_size) + key) * d_head + e0
    ck_i8[Int(out_base + 0)] = Int8(_round_i8_kq(k0v / ksc))
    ck_i8[Int(out_base + 1)] = Int8(_round_i8_kq(k1v / ksc))
    ck_i8[Int(out_base + 2)] = Int8(_round_i8_kq(k2v / ksc))
    ck_i8[Int(out_base + 3)] = Int8(_round_i8_kq(k3v / ksc))
    cv_i8[Int(out_base + 0)] = Int8(_round_i8_kq(v0v / vsc))
    cv_i8[Int(out_base + 1)] = Int8(_round_i8_kq(v1v / vsc))
    cv_i8[Int(out_base + 2)] = Int8(_round_i8_kq(v2v / vsc))
    cv_i8[Int(out_base + 3)] = Int8(_round_i8_kq(v3v / vsc))
    if lane == 0:
        var scale_idx = hk * (n_blocks * key_block_size) + key
        k_scale[Int(scale_idx)] = ksc
        v_scale[Int(scale_idx)] = vsc
