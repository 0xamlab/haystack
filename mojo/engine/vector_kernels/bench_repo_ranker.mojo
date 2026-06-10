"""bench_repo_ranker — latency of run_repo_rank (target < 1 ms / batched call).

Run (from repo root, with the mojo_env toolchain + MODULAR env):
  mojo run -I mojo/engine mojo/engine/vector_kernels/bench_repo_ranker.mojo

Measured ~44 us/call for 50 candidates (≈22x under the 1 ms budget).
"""
from std.time import perf_counter_ns
from vector_kernels.repo_ranker import run_repo_rank


def main():
    var n = 50
    var payload = String('{"query_terms":["normalize","status","open"],"candidates":[')
    for i in range(n):
        if i > 0:
            payload += ","
        payload += '{"path":"src/mod' + String(i) + '.py","text":"src mod' + String(i) + ' normalize status helper"}'
    payload += '],"top_k":25}'

    var sample = run_repo_rank(payload)
    print("sample:", sample)

    var iters = 2000
    var total = 0
    var t0 = perf_counter_ns()
    for _ in range(iters):
        total += len(run_repo_rank(payload))
    var t1 = perf_counter_ns()
    var per_us = Float64(t1 - t0) / Float64(iters) / 1000.0
    print("checksum:", total)
    print("run_repo_rank:", per_us, "us/call  (N=", n, "iters=", iters, ")")
    if per_us < 1000.0:
        print("PASS: < 1 ms")
    else:
        print("FAIL: >= 1 ms")
