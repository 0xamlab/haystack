"""
tensor.mojo — Basic 1D tensor operations. Zero Python imports.
Element-wise math, reductions, slicing, and functional transforms.

Public API:
  struct Tensor1D — 1D float array with math ops
  Factory: zeros, ones, arange, full, linspace
  Arithmetic: add, sub, mul, div_t, scale, neg
  Reductions: sum_t, mean_t, max_t, min_t, argmax, argmin, dot, norm
  Transforms: apply_fn, concat, slice_t, reverse, clip
"""
from std.math import sqrt, exp, log, abs as fabs


# ── Tensor1D struct ───────────────────────────────────────────────────────────


struct Tensor1D(Copyable, Movable):
    """1D tensor of Float64 values with basic math operations."""

    var data: List[Float64]
    var size: Int

    fn __init__(out self):
        """Create an empty 1D tensor."""
        self.data = List[Float64]()
        self.size = 0

    fn __init__(out self, data: List[Float64]):
        """Create a 1D tensor from a list of Float64 values."""
        self.data = List[Float64]()
        for i in range(len(data)):
            self.data.append(data[i])
        self.size = len(data)

    fn __init__(out self, size: Int, fill: Float64):
        """Create a 1D tensor of given size filled with a constant."""
        self.data = List[Float64]()
        self.size = size
        for i in range(size):
            self.data.append(fill)

    fn get(self, i: Int) -> Float64:
        """Get element at index i."""
        if i >= 0 and i < self.size:
            return self.data[i]
        return 0.0

    fn set(mut self, i: Int, val: Float64):
        """Set element at index i."""
        if i >= 0 and i < self.size:
            self.data[i] = val

    fn to_string(self) -> String:
        """Return string representation."""
        var s = String("Tensor1D([")
        for i in range(self.size):
            if i > 0:
                s += ", "
            s += String(self.data[i])
        s += "])"
        return s


# ── Factory functions ─────────────────────────────────────────────────────────


fn zeros(n: Int) -> Tensor1D:
    """Create a 1D tensor of n zeros."""
    return Tensor1D(n, 0.0)


fn ones(n: Int) -> Tensor1D:
    """Create a 1D tensor of n ones."""
    return Tensor1D(n, 1.0)


fn full(n: Int, val: Float64) -> Tensor1D:
    """Create a 1D tensor of n copies of val."""
    return Tensor1D(n, val)


fn arange(start: Float64, stop: Float64, step: Float64) -> Tensor1D:
    """Create a 1D tensor with values from start to stop (exclusive) by step.

    Similar to numpy.arange.
    """
    var data = List[Float64]()
    if step > 0.0:
        var v = start
        while v < stop - step * 1e-10:
            data.append(v)
            v += step
    elif step < 0.0:
        var v = start
        while v > stop - step * 1e-10:
            data.append(v)
            v += step
    return Tensor1D(data)


fn linspace(start: Float64, stop: Float64, n: Int) -> Tensor1D:
    """Create a 1D tensor with n evenly spaced values from start to stop (inclusive)."""
    var data = List[Float64]()
    if n <= 0:
        return Tensor1D(data)
    if n == 1:
        data.append(start)
        return Tensor1D(data)
    var step = (stop - start) / Float64(n - 1)
    for i in range(n):
        data.append(start + Float64(i) * step)
    return Tensor1D(data)


# ── Element-wise arithmetic ───────────────────────────────────────────────────


fn add(a: Tensor1D, b: Tensor1D) -> Tensor1D:
    """Element-wise addition. Tensors must have same size."""
    var n = a.size
    if b.size < n:
        n = b.size
    var data = List[Float64]()
    for i in range(n):
        data.append(a.data[i] + b.data[i])
    return Tensor1D(data)


fn sub(a: Tensor1D, b: Tensor1D) -> Tensor1D:
    """Element-wise subtraction."""
    var n = a.size
    if b.size < n:
        n = b.size
    var data = List[Float64]()
    for i in range(n):
        data.append(a.data[i] - b.data[i])
    return Tensor1D(data)


fn mul(a: Tensor1D, b: Tensor1D) -> Tensor1D:
    """Element-wise multiplication (Hadamard product)."""
    var n = a.size
    if b.size < n:
        n = b.size
    var data = List[Float64]()
    for i in range(n):
        data.append(a.data[i] * b.data[i])
    return Tensor1D(data)


fn div_t(a: Tensor1D, b: Tensor1D) -> Tensor1D:
    """Element-wise division. Division by zero yields 0.0."""
    var n = a.size
    if b.size < n:
        n = b.size
    var data = List[Float64]()
    for i in range(n):
        if b.data[i] != 0.0:
            data.append(a.data[i] / b.data[i])
        else:
            data.append(0.0)
    return Tensor1D(data)


fn scale(a: Tensor1D, s: Float64) -> Tensor1D:
    """Multiply every element by scalar s."""
    var data = List[Float64]()
    for i in range(a.size):
        data.append(a.data[i] * s)
    return Tensor1D(data)


fn neg(a: Tensor1D) -> Tensor1D:
    """Negate every element."""
    return scale(a, -1.0)


# ── Reduction operations ──────────────────────────────────────────────────────


fn dot(a: Tensor1D, b: Tensor1D) -> Float64:
    """Dot product of two 1D tensors."""
    var n = a.size
    if b.size < n:
        n = b.size
    var s: Float64 = 0.0
    for i in range(n):
        s += a.data[i] * b.data[i]
    return s


fn sum_t(a: Tensor1D) -> Float64:
    """Sum of all elements."""
    var s: Float64 = 0.0
    for i in range(a.size):
        s += a.data[i]
    return s


fn mean_t(a: Tensor1D) -> Float64:
    """Mean of all elements."""
    if a.size == 0:
        return 0.0
    return sum_t(a) / Float64(a.size)


fn max_t(a: Tensor1D) -> Float64:
    """Maximum element."""
    if a.size == 0:
        return 0.0
    var m = a.data[0]
    for i in range(1, a.size):
        if a.data[i] > m:
            m = a.data[i]
    return m


fn min_t(a: Tensor1D) -> Float64:
    """Minimum element."""
    if a.size == 0:
        return 0.0
    var m = a.data[0]
    for i in range(1, a.size):
        if a.data[i] < m:
            m = a.data[i]
    return m


fn argmax(a: Tensor1D) -> Int:
    """Index of the maximum element."""
    if a.size == 0:
        return -1
    var best_idx = 0
    var best_val = a.data[0]
    for i in range(1, a.size):
        if a.data[i] > best_val:
            best_val = a.data[i]
            best_idx = i
    return best_idx


fn argmin(a: Tensor1D) -> Int:
    """Index of the minimum element."""
    if a.size == 0:
        return -1
    var best_idx = 0
    var best_val = a.data[0]
    for i in range(1, a.size):
        if a.data[i] < best_val:
            best_val = a.data[i]
            best_idx = i
    return best_idx


fn norm(a: Tensor1D) -> Float64:
    """L2 norm (Euclidean length)."""
    return sqrt(dot(a, a))


fn prod_t(a: Tensor1D) -> Float64:
    """Product of all elements."""
    if a.size == 0:
        return 0.0
    var p: Float64 = 1.0
    for i in range(a.size):
        p *= a.data[i]
    return p


# ── Functional transforms ────────────────────────────────────────────────────


fn apply_fn(a: Tensor1D, fn_name: String) -> Tensor1D:
    """Apply a named function element-wise.

    Supported fn_name values:
      "exp"    — e^x
      "log"    — natural log (log(x), x>0)
      "sqrt"   — square root (x>=0)
      "abs"    — absolute value
      "square" — x^2
      "neg"    — -x
      "inv"    — 1/x (0 for x==0)
      "sigmoid" — 1/(1+exp(-x))
      "relu"   — max(0, x)

    Unknown fn_name returns a copy of the input.
    """
    var data = List[Float64]()
    for i in range(a.size):
        var x = a.data[i]
        if fn_name == "exp":
            data.append(exp(x))
        elif fn_name == "log":
            if x > 0.0:
                data.append(log(x))
            else:
                data.append(-1e300)  # -inf approximation
        elif fn_name == "sqrt":
            if x >= 0.0:
                data.append(sqrt(x))
            else:
                data.append(0.0)
        elif fn_name == "abs":
            data.append(fabs(x))
        elif fn_name == "square":
            data.append(x * x)
        elif fn_name == "neg":
            data.append(-x)
        elif fn_name == "inv":
            if x != 0.0:
                data.append(1.0 / x)
            else:
                data.append(0.0)
        elif fn_name == "sigmoid":
            if x >= 0.0:
                var ex = exp(-x)
                data.append(1.0 / (1.0 + ex))
            else:
                var ex = exp(x)
                data.append(ex / (1.0 + ex))
        elif fn_name == "relu":
            if x > 0.0:
                data.append(x)
            else:
                data.append(0.0)
        else:
            data.append(x)  # identity for unknown fn
    return Tensor1D(data)


# ── Slicing and reshaping ────────────────────────────────────────────────────


fn concat(a: Tensor1D, b: Tensor1D) -> Tensor1D:
    """Concatenate two 1D tensors."""
    var data = List[Float64]()
    for i in range(a.size):
        data.append(a.data[i])
    for i in range(b.size):
        data.append(b.data[i])
    return Tensor1D(data)


fn slice_t(a: Tensor1D, start: Int, end: Int) -> Tensor1D:
    """Slice tensor from start (inclusive) to end (exclusive).

    Negative indices not supported; out of bounds silently clamped.
    """
    var s = start
    var e = end
    if s < 0:
        s = 0
    if e > a.size:
        e = a.size
    if s >= e:
        return Tensor1D()

    var data = List[Float64]()
    for i in range(s, e):
        data.append(a.data[i])
    return Tensor1D(data)


fn reverse(a: Tensor1D) -> Tensor1D:
    """Return a reversed copy of the tensor."""
    var data = List[Float64]()
    for i in range(a.size - 1, -1, -1):
        data.append(a.data[i])
    return Tensor1D(data)


fn clip(a: Tensor1D, lo: Float64, hi: Float64) -> Tensor1D:
    """Clip (clamp) all elements to [lo, hi]."""
    var data = List[Float64]()
    for i in range(a.size):
        var x = a.data[i]
        if x < lo:
            x = lo
        elif x > hi:
            x = hi
        data.append(x)
    return Tensor1D(data)


# ── Comparison / mask operations ──────────────────────────────────────────────


fn equal(a: Tensor1D, b: Tensor1D) -> Bool:
    """Check if two tensors are element-wise equal."""
    if a.size != b.size:
        return False
    for i in range(a.size):
        if a.data[i] != b.data[i]:
            return False
    return True


fn allclose(a: Tensor1D, b: Tensor1D, atol: Float64 = 1e-8) -> Bool:
    """Check if two tensors are element-wise close within tolerance."""
    if a.size != b.size:
        return False
    for i in range(a.size):
        if fabs(a.data[i] - b.data[i]) > atol:
            return False
    return True


fn where_gt(a: Tensor1D, threshold: Float64) -> List[Int]:
    """Return indices where a[i] > threshold."""
    var indices = List[Int]()
    for i in range(a.size):
        if a.data[i] > threshold:
            indices.append(i)
    return indices^


fn count_nonzero(a: Tensor1D) -> Int:
    """Count number of non-zero elements."""
    var count = 0
    for i in range(a.size):
        if a.data[i] != 0.0:
            count += 1
    return count
