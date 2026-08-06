"""
regression.mojo — Multiple regression utilities. Zero Python imports.

Replaces sklearn.linear_model (LinearRegression, Ridge) with pure Mojo
implementations for OLS, ridge regression, polynomial features, and
error metrics.

Public API:
  RegressionResult        — coefficients, intercept, r_squared, residuals
  ols_simple              — Simple OLS (1 predictor)
  ols_multiple            — Multiple OLS via normal equations
  ridge_regression        — Ridge regression with L2 penalty
  polynomial_features     — Generate [x, x², ..., x^degree]
  r_squared               — R² = 1 - SS_res / SS_tot
  predict                 — y = Xβ + intercept
  mse                     — Mean Squared Error
  rmse                    — Root Mean Squared Error
"""
from std.math import sqrt, abs as fabs


# ── RegressionResult ──────────────────────────────────────────────────────────


struct RegressionResult(Copyable, Movable):
    """Holds regression output."""

    var coefficients: List[Float64]
    var intercept: Float64
    var r_squared: Float64
    var residuals: List[Float64]

    def __init__(
        out self,
        coefficients: List[Float64],
        intercept: Float64,
        r_squared: Float64,
        residuals: List[Float64],
    ):
        self.coefficients = coefficients.copy()
        self.intercept = intercept
        self.r_squared = r_squared
        self.residuals = residuals.copy()


# ── Error metrics ─────────────────────────────────────────────────────────────


def r_squared(y_actual: List[Float64], y_predicted: List[Float64]) -> Float64:
    """R² = 1 - SS_res / SS_tot."""
    var n = len(y_actual)
    if n == 0 or len(y_predicted) != n:
        return 0.0
    var mean_y: Float64 = 0.0
    for i in range(n):
        mean_y += y_actual[i]
    mean_y /= Float64(n)

    var ss_tot: Float64 = 0.0
    var ss_res: Float64 = 0.0
    for i in range(n):
        var dt = y_actual[i] - mean_y
        ss_tot += dt * dt
        var dr = y_actual[i] - y_predicted[i]
        ss_res += dr * dr
    if ss_tot < 1e-15:
        return 1.0 if ss_res < 1e-15 else 0.0
    return 1.0 - ss_res / ss_tot


def mse(y_actual: List[Float64], y_predicted: List[Float64]) -> Float64:
    """Mean Squared Error."""
    var n = len(y_actual)
    if n == 0 or len(y_predicted) != n:
        return 0.0
    var total: Float64 = 0.0
    for i in range(n):
        var d = y_actual[i] - y_predicted[i]
        total += d * d
    return total / Float64(n)


def rmse(y_actual: List[Float64], y_predicted: List[Float64]) -> Float64:
    """Root Mean Squared Error."""
    return sqrt(mse(y_actual, y_predicted))


# ── predict ───────────────────────────────────────────────────────────────────


def predict(
    X: List[List[Float64]], coefficients: List[Float64], intercept: Float64
) -> List[Float64]:
    """Predict y = X * β + intercept."""
    var n = len(X)
    # A row wider than coefficients would read coefficients past its end (uncatchable abort).
    for i in range(n):
        if len(X[i]) > len(coefficients):
            return List[Float64]()
    var result = List[Float64]()
    for i in range(n):
        var val = intercept
        var p = len(X[i])
        for j in range(p):
            val += X[i][j] * coefficients[j]
        result.append(val)
    return result^


# ── Gaussian elimination solver ───────────────────────────────────────────────


def _solve_normal_equations(
    XtX: List[List[Float64]], Xty: List[Float64]
) -> List[Float64]:
    """Solve XtX * β = Xty via Gaussian elimination with partial pivoting."""
    var p = len(Xty)

    # Build augmented matrix [XtX | Xty]
    var aug = List[List[Float64]]()
    for i in range(p):
        var row = List[Float64]()
        for j in range(p):
            row.append(XtX[i][j])
        row.append(Xty[i])
        aug.append(row^)

    # Forward elimination with partial pivoting
    for col in range(p):
        # Find pivot
        var max_val: Float64 = fabs(aug[col][col])
        var max_row = col
        for row in range(col + 1, p):
            if fabs(aug[row][col]) > max_val:
                max_val = fabs(aug[row][col])
                max_row = row
        # Swap rows
        if max_row != col:
            var tmp = aug[col].copy()
            aug[col] = aug[max_row].copy()
            aug[max_row] = tmp^

        var pivot = aug[col][col]
        if fabs(pivot) < 1e-15:
            continue

        # Eliminate below
        for row in range(col + 1, p):
            var factor = aug[row][col] / pivot
            for j in range(col, p + 1):
                aug[row][j] -= factor * aug[col][j]

    # Back substitution
    var beta = List[Float64]()
    for _ in range(p):
        beta.append(0.0)
    for i in range(p - 1, -1, -1):
        var s = aug[i][p]
        for j in range(i + 1, p):
            s -= aug[i][j] * beta[j]
        if fabs(aug[i][i]) > 1e-15:
            beta[i] = s / aug[i][i]
    return beta^


# ── ols_simple ────────────────────────────────────────────────────────────────


def ols_simple(x: List[Float64], y: List[Float64]) -> RegressionResult:
    """Simple OLS regression (1 predictor). slope, intercept, R², residuals."""
    var n = len(x)
    if n == 0 or len(y) != n:
        return RegressionResult(List[Float64](), 0.0, 0.0, List[Float64]())

    var mean_x: Float64 = 0.0
    var mean_y: Float64 = 0.0
    for i in range(n):
        mean_x += x[i]
        mean_y += y[i]
    mean_x /= Float64(n)
    mean_y /= Float64(n)

    var ss_xy: Float64 = 0.0
    var ss_xx: Float64 = 0.0
    for i in range(n):
        var dx = x[i] - mean_x
        ss_xy += dx * (y[i] - mean_y)
        ss_xx += dx * dx

    var slope: Float64 = 0.0
    if fabs(ss_xx) > 1e-15:
        slope = ss_xy / ss_xx
    var intercept = mean_y - slope * mean_x

    # Residuals and R²
    var residuals = List[Float64]()
    var y_pred = List[Float64]()
    for i in range(n):
        var yp = slope * x[i] + intercept
        y_pred.append(yp)
        residuals.append(y[i] - yp)

    var r2 = r_squared(y, y_pred)

    var coeffs = List[Float64]()
    coeffs.append(slope)
    return RegressionResult(coeffs^, intercept, r2, residuals^)


# ── ols_multiple ──────────────────────────────────────────────────────────────


def ols_multiple(X: List[List[Float64]], y: List[Float64]) -> RegressionResult:
    """Multiple OLS via normal equations: β = (X^T X)^-1 X^T y.

    X is n×p (each row = one observation). Intercept added internally.
    """
    var n = len(X)
    if n == 0:
        return RegressionResult(List[Float64](), 0.0, 0.0, List[Float64]())
    var p_orig = len(X[0])
    # A short y or a ragged row would be read past its end in the accumulation loops
    # below (uncatchable abort), so refuse with the empty-fit result.
    if len(y) < n:
        return RegressionResult(List[Float64](), 0.0, 0.0, List[Float64]())
    for i in range(n):
        if len(X[i]) < p_orig:
            return RegressionResult(List[Float64](), 0.0, 0.0, List[Float64]())
    var p = p_orig + 1  # +1 for intercept column

    # Build augmented X with intercept column (column 0 = 1)
    # Compute X^T X (p×p) and X^T y (p)
    var XtX = List[List[Float64]]()
    for i in range(p):
        var row = List[Float64]()
        for _ in range(p):
            row.append(0.0)
        XtX.append(row^)
    var Xty = List[Float64]()
    for _ in range(p):
        Xty.append(0.0)

    for i in range(n):
        # Row: [1, X[i][0], X[i][1], ...]
        var xi = List[Float64]()
        xi.append(1.0)
        for j in range(p_orig):
            xi.append(X[i][j])
        for a in range(p):
            Xty[a] += xi[a] * y[i]
            for b in range(p):
                XtX[a][b] += xi[a] * xi[b]

    var beta = _solve_normal_equations(XtX, Xty)

    var intercept = beta[0]
    var coeffs = List[Float64]()
    for j in range(1, p):
        coeffs.append(beta[j])

    # Compute predictions
    var y_pred = predict(X, coeffs, intercept)
    var residuals = List[Float64]()
    for i in range(n):
        residuals.append(y[i] - y_pred[i])
    var r2 = r_squared(y, y_pred)

    return RegressionResult(coeffs^, intercept, r2, residuals^)


# ── ridge_regression ──────────────────────────────────────────────────────────


def ridge_regression(
    X: List[List[Float64]], y: List[Float64], alpha: Float64 = 1.0
) -> RegressionResult:
    """Ridge: β = (X^T X + αI)^-1 X^T y. Intercept column not penalized."""
    var n = len(X)
    if n == 0:
        return RegressionResult(List[Float64](), 0.0, 0.0, List[Float64]())
    var p_orig = len(X[0])
    # Same shape contract as ols_multiple: short y or ragged rows abort the accumulation
    # loops, so refuse with the empty-fit result.
    if len(y) < n:
        return RegressionResult(List[Float64](), 0.0, 0.0, List[Float64]())
    for i in range(n):
        if len(X[i]) < p_orig:
            return RegressionResult(List[Float64](), 0.0, 0.0, List[Float64]())
    var p = p_orig + 1

    var XtX = List[List[Float64]]()
    for i in range(p):
        var row = List[Float64]()
        for _ in range(p):
            row.append(0.0)
        XtX.append(row^)
    var Xty = List[Float64]()
    for _ in range(p):
        Xty.append(0.0)

    for i in range(n):
        var xi = List[Float64]()
        xi.append(1.0)
        for j in range(p_orig):
            xi.append(X[i][j])
        for a in range(p):
            Xty[a] += xi[a] * y[i]
            for b in range(p):
                XtX[a][b] += xi[a] * xi[b]

    # Add ridge penalty (skip intercept column 0)
    for j in range(1, p):
        XtX[j][j] += alpha

    var beta = _solve_normal_equations(XtX, Xty)

    var intercept = beta[0]
    var coeffs = List[Float64]()
    for j in range(1, p):
        coeffs.append(beta[j])

    var y_pred = predict(X, coeffs, intercept)
    var residuals = List[Float64]()
    for i in range(n):
        residuals.append(y[i] - y_pred[i])
    var r2 = r_squared(y, y_pred)

    return RegressionResult(coeffs^, intercept, r2, residuals^)


# ── polynomial_features ───────────────────────────────────────────────────────


def polynomial_features(x: List[Float64], degree: Int) -> List[List[Float64]]:
    """Generate polynomial features [x, x², ..., x^degree]. Returns n×degree."""
    var n = len(x)
    var result = List[List[Float64]]()
    for i in range(n):
        var row = List[Float64]()
        var val: Float64 = 1.0
        for d in range(degree):
            val *= x[i]
            row.append(val)
        result.append(row^)
    return result^
