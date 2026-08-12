"""kv_i8_quant_driver.mojo -- standalone round-trip validation of `kv_i8_quant._kv_i8_quant_kernel`:
fill the f16 native-packed K/V caches with pseudo values, quantize on-device, read the int8 mirror +
scales back, dequantize host-side, and check (a) scales == per-key absmax/127 exactly, (b)
dequantized values within the quantization error bound (|x - dq| <= scale/2 + f16 eps), and
(c) the quantized BYTES match the host-side reference quant (round-half-away-from-zero) exactly.

    cd mma_forge
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo run -I . -I ../attention_forge ../attention_forge/kv_i8_quant_driver.mojo
"""
from max.gpu.host import DeviceContext
from kv_i8_quant import _kv_i8_quant_kernel


def _abs64(x: Float64) -> Float64:
    return -x if x < 0.0 else x


def _pseudo_f16(n: Int, seed: Int) -> List[Float64]:
    var o = List[Float64](capacity=n)
    for i in range(n):
        var raw = Float64(((i * 61 + seed * 17) % 47)) / 19.0 - 1.2
        o.append(Float64(Float16(raw)))
    return o^


def _round_i8_ref(x: Float64) -> Int:
    var r = Int(x + 0.5) if x >= 0.0 else -Int(-x + 0.5)
    if r > 127:
        r = 127
    if r < -127:
        r = -127
    return r


def main() raises:
    var ctx = DeviceContext()
    var h_kv = 8
    var d = 128
    var kbs = 32
    var n_keys = 96
    var n_blocks = (n_keys + kbs - 1) // kbs

    # Host f16 values per (key, hk, d).
    var k_flat = _pseudo_f16(n_keys * h_kv * d, 11)
    var v_flat = _pseudo_f16(n_keys * h_kv * d, 29)

    # Pack into the native layouts: K [hk][block][d][k], V [hk][block][k][d].
    var ck_host = List[Float64](capacity=h_kv * n_blocks * d * kbs)
    var cv_host = List[Float64](capacity=h_kv * n_blocks * kbs * d)
    for _ in range(h_kv * n_blocks * d * kbs):
        ck_host.append(0.0)
    for _ in range(h_kv * n_blocks * kbs * d):
        cv_host.append(0.0)
    for gk in range(n_keys):
        var block = gk // kbs
        var kk = gk % kbs
        for hk in range(h_kv):
            for dd in range(d):
                ck_host[((hk * n_blocks + block) * d + dd) * kbs + kk] = k_flat[(gk * h_kv + hk) * d + dd]
                cv_host[((hk * n_blocks + block) * kbs + kk) * d + dd] = v_flat[(gk * h_kv + hk) * d + dd]

    var ck_buf = ctx.enqueue_create_buffer[DType.float16](h_kv * n_blocks * d * kbs)
    var cv_buf = ctx.enqueue_create_buffer[DType.float16](h_kv * n_blocks * kbs * d)
    with ck_buf.map_to_host() as h:
        for i in range(h_kv * n_blocks * d * kbs):
            h[i] = Float16(ck_host[i])
    with cv_buf.map_to_host() as h:
        for i in range(h_kv * n_blocks * kbs * d):
            h[i] = Float16(cv_host[i])
    var cki_buf = ctx.enqueue_create_buffer[DType.int8](h_kv * n_keys * d)
    var cvi_buf = ctx.enqueue_create_buffer[DType.int8](h_kv * n_keys * d)
    var ks_buf = ctx.enqueue_create_buffer[DType.float32](h_kv * n_keys)
    var vs_buf = ctx.enqueue_create_buffer[DType.float32](h_kv * n_keys)

    # Quantize keys [0, 64) then [64, 96) -- exercises key0 != 0 (decode-style appends).
    ctx.enqueue_function[_kv_i8_quant_kernel](
        ck_buf.unsafe_ptr(), cv_buf.unsafe_ptr(), cki_buf.unsafe_ptr(), cvi_buf.unsafe_ptr(),
        ks_buf.unsafe_ptr(), vs_buf.unsafe_ptr(),
        Int64(0), Int64(64), Int64(h_kv), Int64(d), Int64(kbs), Int64(n_blocks),
        grid_dim=h_kv * 64, block_dim=32)
    ctx.enqueue_function[_kv_i8_quant_kernel](
        ck_buf.unsafe_ptr(), cv_buf.unsafe_ptr(), cki_buf.unsafe_ptr(), cvi_buf.unsafe_ptr(),
        ks_buf.unsafe_ptr(), vs_buf.unsafe_ptr(),
        Int64(64), Int64(32), Int64(h_kv), Int64(d), Int64(kbs), Int64(n_blocks),
        grid_dim=h_kv * 32, block_dim=32)
    ctx.synchronize()

    var cki_h = List[Int](capacity=h_kv * n_keys * d)
    var cvi_h = List[Int](capacity=h_kv * n_keys * d)
    var ks_h = List[Float64](capacity=h_kv * n_keys)
    var vs_h = List[Float64](capacity=h_kv * n_keys)
    with cki_buf.map_to_host() as h:
        for i in range(h_kv * n_keys * d):
            cki_h.append(Int(h[i]))
    with cvi_buf.map_to_host() as h:
        for i in range(h_kv * n_keys * d):
            cvi_h.append(Int(h[i]))
    with ks_buf.map_to_host() as h:
        for i in range(h_kv * n_keys):
            ks_h.append(Float64(h[i]))
    with vs_buf.map_to_host() as h:
        for i in range(h_kv * n_keys):
            vs_h.append(Float64(h[i]))

    # Host reference: per-key absmax + round-half-away-from-zero, per-key scales.
    var scale_bad = 0
    var byte_bad = 0
    var err_worst = 0.0
    for gk in range(n_keys):
        for hk in range(h_kv):
            var kmx = 0.0
            var vmx = 0.0
            for dd in range(d):
                var kv = _abs64(k_flat[(gk * h_kv + hk) * d + dd])
                var vv = _abs64(v_flat[(gk * h_kv + hk) * d + dd])
                if kv > kmx:
                    kmx = kv
                if vv > vmx:
                    vmx = vv
            var ksc_ref = kmx / 127.0
            var vsc_ref = vmx / 127.0
            if ksc_ref < 1.0e-12:
                ksc_ref = 1.0e-12
            if vsc_ref < 1.0e-12:
                vsc_ref = 1.0e-12
            var si = hk * n_keys + gk
            if _abs64(ks_h[si] - ksc_ref) > 1.0e-7 or _abs64(vs_h[si] - vsc_ref) > 1.0e-7:
                scale_bad += 1
            for dd in range(d):
                var oi = (hk * n_keys + gk) * d + dd
                var k_ref = _round_i8_ref(k_flat[(gk * h_kv + hk) * d + dd] / ksc_ref)
                var v_ref = _round_i8_ref(v_flat[(gk * h_kv + hk) * d + dd] / vsc_ref)
                if cki_h[oi] != k_ref or cvi_h[oi] != v_ref:
                    byte_bad += 1
                var kerr = _abs64(Float64(cki_h[oi]) * ks_h[si] - k_flat[(gk * h_kv + hk) * d + dd])
                var verr = _abs64(Float64(cvi_h[oi]) * vs_h[si] - v_flat[(gk * h_kv + hk) * d + dd])
                if kerr > err_worst:
                    err_worst = kerr
                if verr > err_worst:
                    err_worst = verr
    print("  [quant] keys=", n_keys, " h_kv=", h_kv, " d=", d)
    print("  [quant] scale mismatches: ", scale_bad, " / ", h_kv * n_keys)
    print("  [quant] byte mismatches:  ", byte_bad, " / ", h_kv * n_keys * d * 2)
    print("  [quant] worst dequant |err|: ", err_worst, " (bound: scale/2 ~ ", 1.2 / 127.0 / 2.0, ")")
    var ok = scale_bad == 0 and byte_bad == 0 and err_worst <= 1.2 / 127.0
    print("QUANT ROUND-TRIP: ", "OK" if ok else "FAILED")
    print("done")
