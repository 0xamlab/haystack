"""bench_dimensionality.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from dimensionality import column_means, center_data, covariance_matrix, power_iteration, eigenvalue_from_vector, deflate_matrix, pca, PCAResult
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

    var _acc_column_means: Float64 = 0.0
    var _t0_column_means = perf_counter_ns()
    for _ in range(N):
        var _r_column_means = column_means([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
        _acc_column_means += Float64(len(_r_column_means))
    var _t1_column_means = perf_counter_ns()
    var _ns_column_means = Float64(_t1_column_means - _t0_column_means) / Float64(N)
    print("MOJO_TIMING dimensionality::column_means", _ns_column_means, _acc_column_means)
    var _acc_center_data: Float64 = 0.0
    var _t0_center_data = perf_counter_ns()
    for _ in range(N):
        var _r_center_data = center_data([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
        _acc_center_data += Float64(len(_r_center_data))
    var _t1_center_data = perf_counter_ns()
    var _ns_center_data = Float64(_t1_center_data - _t0_center_data) / Float64(N)
    print("MOJO_TIMING dimensionality::center_data", _ns_center_data, _acc_center_data)
    var _acc_covariance_matrix: Float64 = 0.0
    var _t0_covariance_matrix = perf_counter_ns()
    for _ in range(N):
        var _r_covariance_matrix = covariance_matrix([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
        _acc_covariance_matrix += Float64(len(_r_covariance_matrix))
    var _t1_covariance_matrix = perf_counter_ns()
    var _ns_covariance_matrix = Float64(_t1_covariance_matrix - _t0_covariance_matrix) / Float64(N)
    print("MOJO_TIMING dimensionality::covariance_matrix", _ns_covariance_matrix, _acc_covariance_matrix)
    var _acc_power_iteration: Float64 = 0.0
    var _t0_power_iteration = perf_counter_ns()
    for _ in range(N):
        var _r_power_iteration = power_iteration([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], 5)
        _acc_power_iteration += Float64(len(_r_power_iteration))
    var _t1_power_iteration = perf_counter_ns()
    var _ns_power_iteration = Float64(_t1_power_iteration - _t0_power_iteration) / Float64(N)
    print("MOJO_TIMING dimensionality::power_iteration", _ns_power_iteration, _acc_power_iteration)
    var _acc_eigenvalue_from_vector: Float64 = 0.0
    var _t0_eigenvalue_from_vector = perf_counter_ns()
    for _ in range(N):
        _acc_eigenvalue_from_vector += eigenvalue_from_vector([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _lf5)
    var _t1_eigenvalue_from_vector = perf_counter_ns()
    var _ns_eigenvalue_from_vector = Float64(_t1_eigenvalue_from_vector - _t0_eigenvalue_from_vector) / Float64(N)
    print("MOJO_TIMING dimensionality::eigenvalue_from_vector", _ns_eigenvalue_from_vector, _acc_eigenvalue_from_vector)
    var _acc_deflate_matrix: Float64 = 0.0
    var _t0_deflate_matrix = perf_counter_ns()
    for _ in range(N):
        var _r_deflate_matrix = deflate_matrix([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], 0.5, _lf5)
        _acc_deflate_matrix += Float64(len(_r_deflate_matrix))
    var _t1_deflate_matrix = perf_counter_ns()
    var _ns_deflate_matrix = Float64(_t1_deflate_matrix - _t0_deflate_matrix) / Float64(N)
    print("MOJO_TIMING dimensionality::deflate_matrix", _ns_deflate_matrix, _acc_deflate_matrix)
    var _keeper_pca = List[PCAResult]()
    _keeper_pca.append(pca([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], 2))
    var _acc_pca: Float64 = 0.0
    var _t0_pca = perf_counter_ns()
    for _ in range(N):
        _keeper_pca[0] = pca([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], 2)
        _acc_pca += Float64(len(_keeper_pca))
    var _t1_pca = perf_counter_ns()
    var _ns_pca = Float64(_t1_pca - _t0_pca) / Float64(N)
    print("MOJO_TIMING dimensionality::pca", _ns_pca, _acc_pca)
