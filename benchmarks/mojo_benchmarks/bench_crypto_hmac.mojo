"""bench_crypto_hmac.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from crypto.hmac import hmac_sha256, hmac_sha256_verify
from std.time import perf_counter_ns

def main() raises:
    var _lf5 = List[Float64]()
    _lf5.append(0.5); _lf5.append(0.6); _lf5.append(0.7)
    _lf5.append(0.4); _lf5.append(0.3)
    var _li5 = List[Int]()
    _li5.append(0); _li5.append(1); _li5.append(2)
    _li5.append(3); _li5.append(4)
    var _lb5 = List[Bool]()
    _lb5.append(True); _lb5.append(False); _lb5.append(True)
    _lb5.append(True); _lb5.append(False)
    var _lub5 = List[UInt8]()
    _lub5.append(1); _lub5.append(2); _lub5.append(3)
    _lub5.append(4); _lub5.append(5)
    var _llf3 = List[List[Float64]]()
    _llf3.append(List[Float64]()); _llf3.append(List[Float64]()); _llf3.append(List[Float64]())
    _llf3[0].append(4.0); _llf3[0].append(0.0); _llf3[0].append(5.0)
    _llf3[1].append(0.0); _llf3[1].append(3.0); _llf3[1].append(4.0)
    _llf3[2].append(3.0); _llf3[2].append(4.0); _llf3[2].append(0.0)
    var N: Int = 10000

    var _acc_hmac_sha256: Float64 = 0.0
    var _t0_hmac_sha256 = perf_counter_ns()
    for _ in range(N):
        _ = hmac_sha256("test", "test")
    var _t1_hmac_sha256 = perf_counter_ns()
    var _ns_hmac_sha256 = Float64(_t1_hmac_sha256 - _t0_hmac_sha256) / Float64(N)
    print("MOJO_TIMING crypto_hmac::hmac_sha256", _ns_hmac_sha256, _acc_hmac_sha256)
    var _acc_hmac_sha256_verify: Float64 = 0.0
    var _t0_hmac_sha256_verify = perf_counter_ns()
    for _ in range(N):
        _acc_hmac_sha256_verify += Float64(hmac_sha256_verify("test", "test", "test"))
    var _t1_hmac_sha256_verify = perf_counter_ns()
    var _ns_hmac_sha256_verify = Float64(_t1_hmac_sha256_verify - _t0_hmac_sha256_verify) / Float64(N)
    print("MOJO_TIMING crypto_hmac::hmac_sha256_verify", _ns_hmac_sha256_verify, _acc_hmac_sha256_verify)
