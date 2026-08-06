"""
fft.mojo — Fast Fourier Transform. Zero Python imports.

Replaces numpy.fft with pure Mojo implementations for Cooley-Tukey
radix-2 FFT, inverse FFT, magnitude, phase, and power spectrum.

Public API:
  Complex          — Complex number struct with arithmetic
  fft              — Cooley-Tukey radix-2 DIT FFT
  ifft             — Inverse FFT
  fft_magnitude    — |X[k]| for each frequency bin
  fft_phase        — Phase angle atan2(im, re) for each bin
  power_spectrum   — |FFT(x)|² / N
  next_power_of_2  — Smallest power of 2 >= n
  zero_pad         — Pad signal with zeros to target length
"""
from std.math import sqrt, abs as fabs, log


# ── Constants ─────────────────────────────────────────────────────────────────

comptime PI: Float64 = 3.141592653589793


# ── Trig helpers ──────────────────────────────────────────────────────────────


def _sin(x: Float64) -> Float64:
    """Sin via range reduction + Taylor series."""
    var v = x
    while v > PI:
        v -= 2.0 * PI
    while v < -PI:
        v += 2.0 * PI
    var x2 = v * v
    var x3 = v * x2
    var x5 = x3 * x2
    var x7 = x5 * x2
    var x9 = x7 * x2
    var x11 = x9 * x2
    return v - x3 / 6.0 + x5 / 120.0 - x7 / 5040.0 + x9 / 362880.0 - x11 / 39916800.0


def _cos(x: Float64) -> Float64:
    """Cos via range reduction + Taylor series."""
    var v = x
    while v > PI:
        v -= 2.0 * PI
    while v < -PI:
        v += 2.0 * PI
    var x2 = v * v
    var x4 = x2 * x2
    var x6 = x4 * x2
    var x8 = x6 * x2
    var x10 = x8 * x2
    return 1.0 - x2 / 2.0 + x4 / 24.0 - x6 / 720.0 + x8 / 40320.0 - x10 / 3628800.0


def _atan2(y: Float64, x: Float64) -> Float64:
    """atan2(y, x) approximation."""
    if fabs(x) < 1e-15 and fabs(y) < 1e-15:
        return 0.0
    if fabs(x) < 1e-15:
        return PI / 2.0 if y > 0.0 else -PI / 2.0
    var a = y / x
    # Polynomial approximation for atan, |a| <= 1
    var neg = a < 0.0
    if neg:
        a = -a
    var high = a > 1.0
    if high:
        a = 1.0 / a
    # Minimax polynomial for atan on [0,1]
    var a2 = a * a
    var r = a * (1.0 - a2 * (1.0 / 3.0 - a2 * (1.0 / 5.0 - a2 * (1.0 / 7.0 - a2 / 9.0))))
    if high:
        r = PI / 2.0 - r
    if neg:
        r = -r
    if x < 0.0:
        if y >= 0.0:
            r += PI
        else:
            r -= PI
    return r


# ── Complex struct ────────────────────────────────────────────────────────────


struct Complex(Copyable, Movable):
    """Complex number with re and im fields."""

    var re: Float64
    var im: Float64

    def __init__(out self, re: Float64, im: Float64):
        self.re = re
        self.im = im

    def __add__(self, other: Complex) -> Complex:
        return Complex(self.re + other.re, self.im + other.im)

    def __sub__(self, other: Complex) -> Complex:
        return Complex(self.re - other.re, self.im - other.im)

    def __mul__(self, other: Complex) -> Complex:
        return Complex(
            self.re * other.re - self.im * other.im,
            self.re * other.im + self.im * other.re,
        )


# ── next_power_of_2 ──────────────────────────────────────────────────────────


def next_power_of_2(n: Int) -> Int:
    """Smallest power of 2 >= n."""
    if n <= 1:
        return 1
    var p = 1
    while p < n:
        p *= 2
    return p


# ── zero_pad ─────────────────────────────────────────────────────────────────


def zero_pad(x: List[Float64], target_len: Int) -> List[Float64]:
    """Pad signal with zeros to target length."""
    var result = List[Float64]()
    for i in range(len(x)):
        result.append(x[i])
    for _ in range(len(x), target_len):
        result.append(0.0)
    return result^


# ── fft (Cooley-Tukey radix-2 DIT) ──────────────────────────────────────────


def _fft_recursive(x: List[Complex], invert: Bool) -> List[Complex]:
    """Recursive Cooley-Tukey radix-2 FFT/IFFT on complex input."""
    var n = len(x)
    if n == 1:
        var result = List[Complex]()
        result.append(Complex(x[0].re, x[0].im))
        return result^

    # Split even/odd
    var even = List[Complex]()
    var odd = List[Complex]()
    for i in range(0, n, 2):
        even.append(Complex(x[i].re, x[i].im))
    for i in range(1, n, 2):
        odd.append(Complex(x[i].re, x[i].im))

    var E = _fft_recursive(even, invert)
    var O = _fft_recursive(odd, invert)

    var result = List[Complex]()
    for _ in range(n):
        result.append(Complex(0.0, 0.0))

    var half = n // 2
    var angle_sign: Float64 = -1.0
    if invert:
        angle_sign = 1.0

    for k in range(half):
        var angle = angle_sign * 2.0 * PI * Float64(k) / Float64(n)
        var w = Complex(_cos(angle), _sin(angle))
        var t = w * O[k]
        result[k] = E[k] + t
        result[k + half] = E[k] - t

    return result^


def fft(x: List[Float64]) -> List[Complex]:
    """Cooley-Tukey radix-2 DIT FFT. Input length must be power of 2."""
    var n = len(x)
    # Empty input would recurse forever in _fft_recursive (n=0 splits into
    # two empty halves), a stack-overflow abort.
    if n == 0:
        return List[Complex]()
    var cx = List[Complex]()
    for i in range(n):
        cx.append(Complex(x[i], 0.0))
    return _fft_recursive(cx, False)


def ifft(X: List[Complex]) -> List[Complex]:
    """Inverse FFT. Returns complex time-domain signal."""
    var n = len(X)
    # Empty input would recurse forever in _fft_recursive (and divide by
    # n == 0 below).
    if n == 0:
        return List[Complex]()
    var result = _fft_recursive(X, True)
    var nf = Float64(n)
    for i in range(n):
        result[i] = Complex(result[i].re / nf, result[i].im / nf)
    return result^


# ── fft_magnitude ────────────────────────────────────────────────────────────


def fft_magnitude(X: List[Complex]) -> List[Float64]:
    """|X[k]| = sqrt(re² + im²) for each frequency bin."""
    var result = List[Float64]()
    for i in range(len(X)):
        result.append(sqrt(X[i].re * X[i].re + X[i].im * X[i].im))
    return result^


# ── fft_phase ────────────────────────────────────────────────────────────────


def fft_phase(X: List[Complex]) -> List[Float64]:
    """Phase angle atan2(im, re) for each bin."""
    var result = List[Float64]()
    for i in range(len(X)):
        result.append(_atan2(X[i].im, X[i].re))
    return result^


# ── power_spectrum ───────────────────────────────────────────────────────────


def power_spectrum(x: List[Float64]) -> List[Float64]:
    """|FFT(x)|² / N."""
    # Empty input would divide by N == 0 below.
    if len(x) == 0:
        return List[Float64]()
    var X = fft(x)
    var n = Float64(len(x))
    var result = List[Float64]()
    for i in range(len(X)):
        var mag2 = X[i].re * X[i].re + X[i].im * X[i].im
        result.append(mag2 / n)
    return result^
