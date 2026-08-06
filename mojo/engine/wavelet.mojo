"""
wavelet.mojo — Wavelet transforms. Zero Python imports.

Replaces pywt with pure Mojo implementations for Haar discrete wavelet
transform (forward/inverse, single/multi-level), thresholding, denoising,
and energy analysis.

Public API:
  haar_forward              — 1-level Haar DWT
  haar_inverse              — Inverse 1-level Haar DWT
  haar_multilevel           — Multi-level Haar DWT
  haar_multilevel_inverse   — Multi-level inverse Haar DWT
  threshold_hard            — Hard thresholding
  threshold_soft            — Soft thresholding
  denoise_haar              — Denoise via DWT → threshold → inverse
  energy_ratio              — Detail energy / total energy
  detail_coefficients       — Extract detail half
  approx_coefficients       — Extract approximation half
"""
from std.math import sqrt, abs as fabs


# ── haar_forward ──────────────────────────────────────────────────────────────


def haar_forward(data: List[Float64]) -> List[Float64]:
    """1-level Haar DWT: output = [averages..., details...].

    Input length must be even. Uses normalised Haar coefficients:
    a_k = (x[2k] + x[2k+1]) / sqrt(2)
    d_k = (x[2k] - x[2k+1]) / sqrt(2)
    """
    var n = len(data)
    var half = n // 2
    var out = List[Float64]()
    var s2 = sqrt(2.0)
    # Approximation coefficients (first half)
    for i in range(half):
        out.append((data[2 * i] + data[2 * i + 1]) / s2)
    # Detail coefficients (second half)
    for i in range(half):
        out.append((data[2 * i] - data[2 * i + 1]) / s2)
    return out^


# ── haar_inverse ──────────────────────────────────────────────────────────────


def haar_inverse(coeffs: List[Float64]) -> List[Float64]:
    """Inverse 1-level Haar DWT.

    Input = [averages..., details...] of length 2*half.
    """
    var n = len(coeffs)
    var half = n // 2
    var out = List[Float64]()
    var s2 = sqrt(2.0)
    for i in range(half):
        var a = coeffs[i]
        var d = coeffs[half + i]
        out.append((a + d) / s2)
        out.append((a - d) / s2)
    return out^


# ── haar_multilevel ───────────────────────────────────────────────────────────


def haar_multilevel(data: List[Float64], levels: Int) -> List[Float64]:
    """Multi-level Haar DWT.

    Recursively transforms the approximation part.
    Output layout: [approx_L, detail_L, detail_{L-1}, ..., detail_1]
    stored flat as the approximation portion keeps shrinking.
    """
    var current = data.copy()
    var n = len(current)
    var result = List[Float64]()
    # Pre-allocate with zeros
    for i in range(n):
        result.append(0.0)
    var length = n
    for lev in range(levels):
        if length < 2:
            break
        var half = length // 2
        var s2 = sqrt(2.0)
        var approx = List[Float64]()
        var detail = List[Float64]()
        for i in range(half):
            approx.append((current[2 * i] + current[2 * i + 1]) / s2)
            detail.append((current[2 * i] - current[2 * i + 1]) / s2)
        # Store detail coefficients at position half..length-1 in result
        for i in range(half):
            result[half + i] = detail[i]
        # Replace current with approximation for next level
        current = List[Float64]()
        for i in range(half):
            current.append(approx[i])
        length = half
    # Store final approximation at the beginning
    for i in range(length):
        result[i] = current[i]
    return result^


# ── haar_multilevel_inverse ───────────────────────────────────────────────────


def haar_multilevel_inverse(coeffs: List[Float64], levels: Int) -> List[Float64]:
    """Multi-level inverse Haar DWT."""
    var n = len(coeffs)
    # Find the length of the approximation part at deepest level
    var length = n
    for lev in range(levels):
        length = length // 2
    # Start with approximation coefficients
    var current = List[Float64]()
    for i in range(length):
        current.append(coeffs[i])
    var s2 = sqrt(2.0)
    for lev in range(levels):
        var half = len(current)
        var detail_start = half  # detail coefficients start at this offset in coeffs
        var reconstructed = List[Float64]()
        for i in range(half):
            var a = current[i]
            var d = coeffs[detail_start + i]
            reconstructed.append((a + d) / s2)
            reconstructed.append((a - d) / s2)
        current = reconstructed^
    return current^


# ── threshold_hard ────────────────────────────────────────────────────────────


def threshold_hard(coeffs: List[Float64], threshold: Float64) -> List[Float64]:
    """Hard thresholding: zero out |c| < threshold."""
    var out = List[Float64]()
    for i in range(len(coeffs)):
        if fabs(coeffs[i]) < threshold:
            out.append(0.0)
        else:
            out.append(coeffs[i])
    return out^


# ── threshold_soft ────────────────────────────────────────────────────────────


def threshold_soft(coeffs: List[Float64], threshold: Float64) -> List[Float64]:
    """Soft thresholding: sign(c) * max(|c| - threshold, 0)."""
    var out = List[Float64]()
    for i in range(len(coeffs)):
        var val = fabs(coeffs[i])
        if val <= threshold:
            out.append(0.0)
        else:
            var sign: Float64 = 1.0
            if coeffs[i] < 0.0:
                sign = -1.0
            out.append(sign * (val - threshold))
    return out^


# ── denoise_haar ──────────────────────────────────────────────────────────────


def denoise_haar(
    data: List[Float64], threshold: Float64, levels: Int = 1
) -> List[Float64]:
    """Denoise: forward DWT → soft threshold → inverse DWT."""
    var coeffs = haar_multilevel(data, levels)
    var thresholded = threshold_soft(coeffs, threshold)
    return haar_multilevel_inverse(thresholded, levels)


# ── energy_ratio ──────────────────────────────────────────────────────────────


def energy_ratio(coeffs: List[Float64]) -> Float64:
    """Ratio of detail energy to total energy.

    Assumes coeffs = [approx..., detail...] from haar_forward.
    """
    var n = len(coeffs)
    if n == 0:
        return 0.0
    var half = n // 2
    var total_energy: Float64 = 0.0
    var detail_energy: Float64 = 0.0
    for i in range(n):
        total_energy += coeffs[i] * coeffs[i]
    for i in range(half, n):
        detail_energy += coeffs[i] * coeffs[i]
    if total_energy < 1e-15:
        return 0.0
    return detail_energy / total_energy


# ── detail_coefficients ───────────────────────────────────────────────────────


def detail_coefficients(coeffs: List[Float64]) -> List[Float64]:
    """Extract detail part (second half of Haar output)."""
    var n = len(coeffs)
    var half = n // 2
    var out = List[Float64]()
    for i in range(half, n):
        out.append(coeffs[i])
    return out^


# ── approx_coefficients ──────────────────────────────────────────────────────


def approx_coefficients(coeffs: List[Float64]) -> List[Float64]:
    """Extract approximation part (first half of Haar output)."""
    var n = len(coeffs)
    var half = n // 2
    var out = List[Float64]()
    for i in range(half):
        out.append(coeffs[i])
    return out^
