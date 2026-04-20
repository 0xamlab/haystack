"""test_svm_kernel.mojo — auto-generated tests for svm_kernel library."""
from std.math import isnan, isinf
from svm_kernel import kernel_linear, kernel_rbf, kernel_polynomial, kernel_sigmoid

fn is_finite(x: Float64) -> Bool:
    return not isnan(x) and not isinf(x)

def main() raises:
    var _lf5 = List[Float64]()
    _lf5.append(0.5); _lf5.append(0.6); _lf5.append(0.7)
    _lf5.append(0.4); _lf5.append(0.3)
    var _li5 = List[Int]()
    _li5.append(1); _li5.append(2); _li5.append(3)
    _li5.append(4); _li5.append(5)
    var _lb5 = List[Bool]()
    _lb5.append(True); _lb5.append(False); _lb5.append(True)
    _lb5.append(True); _lb5.append(False)
    var passed: Int = 0
    var failed: Int = 0

    var _v_kernel_linear = kernel_linear(_lf5, _lf5)
    if is_finite(_v_kernel_linear): passed += 1; print("  ✅ svm_kernel::kernel_linear =", _v_kernel_linear)
    else: failed += 1; print("  ❌ svm_kernel::kernel_linear → non-finite:", _v_kernel_linear)
    var _v_kernel_rbf = kernel_rbf(_lf5, _lf5, 0.5)
    if is_finite(_v_kernel_rbf): passed += 1; print("  ✅ svm_kernel::kernel_rbf =", _v_kernel_rbf)
    else: failed += 1; print("  ❌ svm_kernel::kernel_rbf → non-finite:", _v_kernel_rbf)
    var _v_kernel_polynomial = kernel_polynomial(_lf5, _lf5, 5, 0.5)
    if is_finite(_v_kernel_polynomial): passed += 1; print("  ✅ svm_kernel::kernel_polynomial =", _v_kernel_polynomial)
    else: failed += 1; print("  ❌ svm_kernel::kernel_polynomial → non-finite:", _v_kernel_polynomial)
    var _v_kernel_sigmoid = kernel_sigmoid(_lf5, _lf5, 0.5, 0.5)
    if is_finite(_v_kernel_sigmoid): passed += 1; print("  ✅ svm_kernel::kernel_sigmoid =", _v_kernel_sigmoid)
    else: failed += 1; print("  ❌ svm_kernel::kernel_sigmoid → non-finite:", _v_kernel_sigmoid)

    print("  [svm_kernel] Passed:", passed, "Failed:", failed)
