"""
kalman.mojo — Kalman Filter with matrix utilities. Zero Python imports.

Replaces filterpy/pykalman with pure Mojo implementations for
Kalman prediction, update, smoothing, and basic matrix operations.

Public API:
  KalmanState          — State vector + covariance matrix
  kalman_predict       — Prediction step: x' = F*x, P' = F*P*F^T + Q
  kalman_update        — Update step with measurement
  kalman_smooth_1d     — 1D Kalman smoother over a sequence
  mat_mul              — Matrix multiplication
  mat_transpose        — Matrix transpose
  mat_add              — Matrix addition
  mat_sub              — Matrix subtraction
  mat_scale            — Scalar multiplication
  mat_identity         — n×n identity matrix
  mat_inv_2x2          — 2×2 matrix inverse
  matvec               — Matrix-vector product
"""
from std.math import abs as fabs


# ── KalmanState struct ───────────────────────────────────────────────────────


struct KalmanState(Copyable, Movable):
    """Kalman filter state: state vector x and covariance matrix P."""

    var x: List[Float64]
    var P: List[List[Float64]]

    fn __init__(out self, x: List[Float64], P: List[List[Float64]]):
        self.x = x.copy()
        self.P = P.copy()


# ── Matrix utilities ─────────────────────────────────────────────────────────


fn mat_identity(n: Int) -> List[List[Float64]]:
    """Create n×n identity matrix."""
    var result = List[List[Float64]]()
    for i in range(n):
        var row = List[Float64]()
        for j in range(n):
            if i == j:
                row.append(1.0)
            else:
                row.append(0.0)
        result.append(row^)
    return result^


fn mat_mul(a: List[List[Float64]], b: List[List[Float64]]) -> List[List[Float64]]:
    """Matrix multiplication: C = A * B."""
    var rows_a = len(a)
    var cols_a = len(a[0]) if rows_a > 0 else 0
    var cols_b = len(b[0]) if len(b) > 0 else 0
    var result = List[List[Float64]]()
    for i in range(rows_a):
        var row = List[Float64]()
        for j in range(cols_b):
            var s: Float64 = 0.0
            for k in range(cols_a):
                s += a[i][k] * b[k][j]
            row.append(s)
        result.append(row^)
    return result^


fn mat_transpose(a: List[List[Float64]]) -> List[List[Float64]]:
    """Transpose matrix."""
    var rows = len(a)
    var cols = len(a[0]) if rows > 0 else 0
    var result = List[List[Float64]]()
    for j in range(cols):
        var row = List[Float64]()
        for i in range(rows):
            row.append(a[i][j])
        result.append(row^)
    return result^


fn mat_add(a: List[List[Float64]], b: List[List[Float64]]) -> List[List[Float64]]:
    """Element-wise matrix addition."""
    var rows = len(a)
    var cols = len(a[0]) if rows > 0 else 0
    var result = List[List[Float64]]()
    for i in range(rows):
        var row = List[Float64]()
        for j in range(cols):
            row.append(a[i][j] + b[i][j])
        result.append(row^)
    return result^


fn mat_sub(a: List[List[Float64]], b: List[List[Float64]]) -> List[List[Float64]]:
    """Element-wise matrix subtraction."""
    var rows = len(a)
    var cols = len(a[0]) if rows > 0 else 0
    var result = List[List[Float64]]()
    for i in range(rows):
        var row = List[Float64]()
        for j in range(cols):
            row.append(a[i][j] - b[i][j])
        result.append(row^)
    return result^


fn mat_scale(a: List[List[Float64]], s: Float64) -> List[List[Float64]]:
    """Scalar multiplication of a matrix."""
    var rows = len(a)
    var cols = len(a[0]) if rows > 0 else 0
    var result = List[List[Float64]]()
    for i in range(rows):
        var row = List[Float64]()
        for j in range(cols):
            row.append(a[i][j] * s)
        result.append(row^)
    return result^


fn mat_inv_2x2(a: List[List[Float64]]) -> List[List[Float64]]:
    """Inverse of a 2×2 matrix. Returns zero matrix if singular."""
    var det = a[0][0] * a[1][1] - a[0][1] * a[1][0]
    if fabs(det) < 1e-15:
        # Singular — return zeros
        var result = List[List[Float64]]()
        for _ in range(2):
            var row = List[Float64]()
            row.append(0.0)
            row.append(0.0)
            result.append(row^)
        return result^
    var inv_det = 1.0 / det
    var result = List[List[Float64]]()
    var row0 = List[Float64]()
    row0.append(a[1][1] * inv_det)
    row0.append(-a[0][1] * inv_det)
    result.append(row0^)
    var row1 = List[Float64]()
    row1.append(-a[1][0] * inv_det)
    row1.append(a[0][0] * inv_det)
    result.append(row1^)
    return result^


fn matvec(a: List[List[Float64]], v: List[Float64]) -> List[Float64]:
    """Matrix-vector product: result = A * v."""
    var rows = len(a)
    var cols = len(a[0]) if rows > 0 else 0
    var result = List[Float64]()
    for i in range(rows):
        var s: Float64 = 0.0
        for j in range(cols):
            s += a[i][j] * v[j]
        result.append(s)
    return result^


# ── Scalar inverse for 1×1 "matrix" ─────────────────────────────────────────


fn _scalar_inv(a: List[List[Float64]]) -> List[List[Float64]]:
    """Inverse of a 1×1 matrix."""
    var result = List[List[Float64]]()
    var row = List[Float64]()
    if fabs(a[0][0]) < 1e-15:
        row.append(0.0)
    else:
        row.append(1.0 / a[0][0])
    result.append(row^)
    return result^


fn _mat_inv(a: List[List[Float64]]) -> List[List[Float64]]:
    """Invert a 1×1 or 2×2 matrix."""
    var n = len(a)
    if n == 1:
        return _scalar_inv(a)
    return mat_inv_2x2(a)


# ── Kalman predict ───────────────────────────────────────────────────────────


fn kalman_predict(
    state: KalmanState,
    F: List[List[Float64]],
    Q: List[List[Float64]],
) -> KalmanState:
    """Prediction step: x' = F*x, P' = F*P*F^T + Q."""
    var x_pred = matvec(F, state.x)
    var FP = mat_mul(F, state.P)
    var Ft = mat_transpose(F)
    var P_pred = mat_add(mat_mul(FP, Ft), Q)
    return KalmanState(x_pred^, P_pred^)


# ── Kalman update ────────────────────────────────────────────────────────────


fn kalman_update(
    state: KalmanState,
    z: List[Float64],
    H: List[List[Float64]],
    R: List[List[Float64]],
) -> KalmanState:
    """Update step: K = P*H^T*(H*P*H^T+R)^-1, x += K*(z-H*x), P = (I-K*H)*P."""
    var Ht = mat_transpose(H)
    var PHt = mat_mul(state.P, Ht)
    var S = mat_add(mat_mul(H, PHt), R)
    var S_inv = _mat_inv(S)
    var K = mat_mul(PHt, S_inv)

    # Innovation: y = z - H*x
    var Hx = matvec(H, state.x)
    var y = List[Float64]()
    for i in range(len(z)):
        y.append(z[i] - Hx[i])

    # Updated state: x + K*y
    var Ky = matvec(K, y)
    var x_new = List[Float64]()
    for i in range(len(state.x)):
        x_new.append(state.x[i] + Ky[i])

    # Updated covariance: (I - K*H)*P
    var n = len(state.x)
    var I = mat_identity(n)
    var KH = mat_mul(K, H)
    var IKH = mat_sub(I, KH)
    var P_new = mat_mul(IKH, state.P)

    return KalmanState(x_new^, P_new^)


# ── 1D Kalman smoother ──────────────────────────────────────────────────────


fn kalman_smooth_1d(
    measurements: List[Float64],
    process_var: Float64,
    measurement_var: Float64,
) -> List[Float64]:
    """Simple 1D Kalman smoother over scalar measurements.

    Uses a 1D state model: x_{k+1} = x_k + w, z_k = x_k + v
    where w ~ N(0, process_var), v ~ N(0, measurement_var).
    Returns filtered state estimates.
    """
    var n = len(measurements)
    if n == 0:
        return List[Float64]()

    var result = List[Float64]()

    # Initialize with first measurement
    var x = measurements[0]
    var p = measurement_var

    result.append(x)

    for i in range(1, n):
        # Predict
        var x_pred = x
        var p_pred = p + process_var

        # Update
        var k = p_pred / (p_pred + measurement_var)
        x = x_pred + k * (measurements[i] - x_pred)
        p = (1.0 - k) * p_pred

        result.append(x)

    return result^
