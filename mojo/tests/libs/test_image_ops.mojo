"""test_image_ops.mojo — auto-generated tests for image_ops library."""
from std.math import isnan, isinf
from image_ops import sobel_x_kernel, sobel_y_kernel, gaussian_kernel_3x3, sharpen_kernel

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

    _ = sobel_x_kernel()
    passed += 1; print("  ✅ image_ops::sobel_x_kernel")
    _ = sobel_y_kernel()
    passed += 1; print("  ✅ image_ops::sobel_y_kernel")
    _ = gaussian_kernel_3x3()
    passed += 1; print("  ✅ image_ops::gaussian_kernel_3x3")
    _ = sharpen_kernel()
    passed += 1; print("  ✅ image_ops::sharpen_kernel")

    print("  [image_ops] Passed:", passed, "Failed:", failed)
