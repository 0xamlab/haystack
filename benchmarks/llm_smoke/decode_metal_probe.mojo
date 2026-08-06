"""decode_metal_probe.mojo — does the existing Metal GEMM fit the decode step's shape?

Hand-written, throwaway measurement (not registered in `generate_mojo_tests.py`; this is a probe for
a design decision, not a golden-vector suite). REQUIRES the GPU build flag and a shader compiler:

    DEVELOPER_DIR=/Applications/Xcode-<version>.app/Contents/Developer \\
      pixi run mojo run -D ALGENTA_GPU -I../mojo/engine -I../benchmarks decode_metal_probe.mojo

Question being asked
---------------------
FastGEMV parallelized the CPU path for the decode step's 7 per-layer transposed projections
(`llmk.gemv_fast.gemv_transposed_parallel_flat`). `accel.gemm_metal` is a working, tested Metal GEMM
on this machine. Does routing those SAME 7 calls through the GPU win, at the SHAPES Qwen3-0.6B-Base's
decode step actually uses -- one token, so `m=1` on every single call?

`accel.gemm_metal`'s own benchmark (`bench_accel.mojo`) already measured that a 128-cube GEMM loses
end-to-end to the CPU, purely on fixed per-call overhead (buffer allocation, Float64<->Float32
conversion, launch, sync). Decode's `m=1` is a much smaller and much more lopsided shape than a
128-cube -- this probe measures that shape directly rather than extrapolating.

Shapes probed are Qwen3-0.6B-Base's real config (hidden_size=1024, intermediate_size=3072,
num_attention_heads=16, num_key_value_heads=8, head_dim=128):
  q_proj   m=1 k=1024 n=2048   (h_q * d_head)
  kv_proj  m=1 k=1024 n=1024   (h_kv * d_head)
  o_proj   m=1 k=2048 n=1024
  gate/up  m=1 k=1024 n=3072
  down     m=1 k=3072 n=1024
"""
from std.time import perf_counter_ns

from accel.contract import ACCEL_OK, accel_status_name
from accel.device import accel_device_probe
from accel.gemm_metal import ACCEL_GPU_BUILD, gemm_metal_flat
from gemm.blocked import gemv_flat, sgemm_flat
from llmk.gemv_fast import gemv_transposed_parallel_flat


def _ns_since(t0: UInt) -> Float64:
    return Float64(Int(perf_counter_ns() - t0))


def _pseudo(n: Int, seed: Int) -> List[Float64]:
    var o = List[Float64](capacity=n)
    for i in range(n):
        o.append(Float64(((i * 61 + seed * 17) % 23)) / 11.0 - 1.0)
    return o^


def _median_of(mut samples: List[Float64]) -> Float64:
    for i in range(1, len(samples)):
        var key = samples[i]
        var j = i - 1
        while j >= 0 and samples[j] > key:
            samples[j + 1] = samples[j]
            j -= 1
        samples[j + 1] = key
    return samples[len(samples) // 2]


def _probe_shape(name: String, m_in: Int, n_out: Int) raises:
    """One decode-shaped GEMV: `y[1, n_out] = x[1, m_in] @ W[m_in, n_out]`, exactly the reshape
    that makes `gemm_metal_flat`'s `C = A @ B` compute the same product `gemv_flat(..., trans=True)`
    and `gemv_transposed_parallel_flat` compute for this call site."""
    var x = _pseudo(m_in, 1)
    var w = _pseudo(m_in * n_out, 5)

    # GPU: cold (first touch at this shape) then hot (median of many, steady state).
    var t_cold = perf_counter_ns()
    var g_cold = gemm_metal_flat(x, w, 1, n_out, m_in)
    var cold_ns = _ns_since(t_cold)
    if g_cold.status != ACCEL_OK:
        print("  ", name, ": GPU call FAILED:", accel_status_name(g_cold.status))
        return

    for _ in range(5):
        var _wu = gemm_metal_flat(x, w, 1, n_out, m_in)
    var gpu_samples = List[Float64]()
    for _ in range(15):
        var t = perf_counter_ns()
        var _g = gemm_metal_flat(x, w, 1, n_out, m_in)
        gpu_samples.append(_ns_since(t))
    var gpu_hot_ns = _median_of(gpu_samples)

    # CPU: the two paths actually in `qwen3_generate.mojo` -- FastGEMV's parallel band, and the
    # pre-existing frozen scalar `gemv_flat` it replaced, so the probe shows the FULL before/after.
    for _ in range(5):
        var _wp = gemv_transposed_parallel_flat(w, x, m_in, n_out)
    var par_samples = List[Float64]()
    for _ in range(15):
        var t = perf_counter_ns()
        var _p = gemv_transposed_parallel_flat(w, x, m_in, n_out)
        par_samples.append(_ns_since(t))
    var par_hot_ns = _median_of(par_samples)

    for _ in range(5):
        var _ws = gemv_flat(w, x, m_in, n_out, True)
    var scalar_samples = List[Float64]()
    for _ in range(15):
        var t = perf_counter_ns()
        var _s = gemv_flat(w, x, m_in, n_out, True)
        scalar_samples.append(_ns_since(t))
    var scalar_hot_ns = _median_of(scalar_samples)

    print("  ", name, " m=1 k=", m_in, " n=", n_out)
    print("      GPU   cold:", cold_ns / 1e3, "us   hot (median/15):", gpu_hot_ns / 1e3, "us")
    print("      CPU par   hot (median/15):", par_hot_ns / 1e3, "us")
    print("      CPU scalar hot (median/15):", scalar_hot_ns / 1e3, "us")
    print("      GPU/CPU-par ratio:", gpu_hot_ns / par_hot_ns, "x  (>1 means GPU is SLOWER)")


def _probe_batched(name: String, m_rows: Int, k_in: Int, n_out: Int) raises:
    """The SAME q_proj weight shape, but with `m_rows` tokens at once -- prefill's shape, not
    decode's. Shows whether the crossover the doc predicts (bigger batch amortizes launch
    overhead) actually happens on this machine, rather than asserting it."""
    var a = _pseudo(m_rows * k_in, 1)
    var w = _pseudo(k_in * n_out, 5)

    var g0 = gemm_metal_flat(a, w, m_rows, n_out, k_in)
    if g0.status != ACCEL_OK:
        print("  ", name, ": GPU call FAILED:", accel_status_name(g0.status))
        return
    for _ in range(5):
        var _wu = gemm_metal_flat(a, w, m_rows, n_out, k_in)
    var gpu_samples = List[Float64]()
    for _ in range(15):
        var t = perf_counter_ns()
        var _g = gemm_metal_flat(a, w, m_rows, n_out, k_in)
        gpu_samples.append(_ns_since(t))
    var gpu_hot_ns = _median_of(gpu_samples)

    for _ in range(5):
        var _wc = sgemm_flat(a, w, m_rows, n_out, k_in, 1.0, 0.0, False, False)
    var cpu_samples = List[Float64]()
    for _ in range(15):
        var t = perf_counter_ns()
        var _c = sgemm_flat(a, w, m_rows, n_out, k_in, 1.0, 0.0, False, False)
        cpu_samples.append(_ns_since(t))
    var cpu_hot_ns = _median_of(cpu_samples)

    print("  ", name, " m=", m_rows, " k=", k_in, " n=", n_out)
    print("      GPU hot (median/15):", gpu_hot_ns / 1e3, "us   CPU (sgemm_flat) hot:", cpu_hot_ns / 1e3, "us")
    print("      GPU/CPU ratio:", gpu_hot_ns / cpu_hot_ns, "x  (<1 means GPU wins)")


def main() raises:
    print("=== decode-shaped GEMV: Metal GPU vs CPU, m=1 (one token) ===")
    print("")

    if not ACCEL_GPU_BUILD:
        print("Built WITHOUT -D ALGENTA_GPU: refusing to report timings (kernels compiled out).")
        return
    var probe = accel_device_probe()
    if probe.status != ACCEL_OK:
        print("No usable accelerator. Refusing to report timings.")
        return
    print("[accel.device] backend present, name length", probe.name_length)
    print("")

    _probe_shape(String("q_proj "), 1024, 2048)
    _probe_shape(String("kv_proj"), 1024, 1024)
    _probe_shape(String("o_proj "), 2048, 1024)
    _probe_shape(String("gate/up"), 1024, 3072)
    _probe_shape(String("down   "), 3072, 1024)

    print("")
    print("If every ratio above is >> 1, the GPU's fixed per-call overhead (buffer alloc,")
    print("Float64<->Float32 conversion, launch, sync) dominates a single-token matmul, and")
    print("routing decode through accel.gemm_metal would be a REGRESSION versus the CPU path")
    print("FastGEMV already shipped -- a real finding, not a tuning failure to chase further.")

    print("")
    print("=== the SAME q_proj weight shape, batched like PREFILL instead of decode ===")
    _probe_batched(String("prefill m=16  "), 16, 1024, 2048)
    _probe_batched(String("prefill m=64  "), 64, 1024, 2048)
    _probe_batched(String("prefill m=256 "), 256, 1024, 2048)
