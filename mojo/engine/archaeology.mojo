"""Archaeology / Cultural Heritage Library.

Provides functions for archaeological dating, site analysis,
artifact statistics, and cultural heritage quantification.
"""

from std.math import sqrt, log, abs


fn radiocarbon_age_bp(ratio: Float64, lambda_val: Float64 = 1.21e-4) -> Float64:
    """Radiocarbon age before present: Age = -ln(ratio) / λ.

    ratio: C14/C12 ratio relative to modern standard (0-1).
    lambda_val: decay constant (default ≈1.21e-4 per year).
    """
    if ratio <= 0.0 or lambda_val <= 0.0:
        return 0.0
    return -log(ratio) / lambda_val


fn calibrated_date_linear(age_bp: Float64, offset: Float64 = 0.0) -> Float64:
    """Simplified linear calibrated date: Cal = 1950 - age_bp + offset."""
    return 1950.0 - age_bp + offset


fn stratigraphy_depth_to_age_linear(depth: Float64, sedimentation_rate: Float64) -> Float64:
    """Linear depth-to-age conversion: Age = depth / rate."""
    if sedimentation_rate <= 0.0:
        return 0.0
    return depth / sedimentation_rate


fn artifact_density(n_artifacts: Float64, excavation_volume: Float64) -> Float64:
    """Artifact density: AD = n / V (per m³)."""
    if excavation_volume <= 0.0:
        return 0.0
    return n_artifacts / excavation_volume


fn site_area_from_scatter(length: Float64, width: Float64) -> Float64:
    """Site area from scatter dimensions: A = L * W (m²)."""
    return length * width


fn ceramic_seriation_similarity(
    shared_types: Float64, total_types_a: Float64, total_types_b: Float64
) -> Float64:
    """Sørensen similarity coefficient: S = 2*shared / (A + B)."""
    var denom = total_types_a + total_types_b
    if denom <= 0.0:
        return 0.0
    return 2.0 * shared_types / denom


fn dating_uncertainty_combined(sigma1: Float64, sigma2: Float64) -> Float64:
    """Combined dating uncertainty: σ = sqrt(σ1² + σ2²)."""
    return sqrt(sigma1 * sigma1 + sigma2 * sigma2)


fn occupation_span(earliest_date: Float64, latest_date: Float64) -> Float64:
    """Occupation span: Span = latest - earliest."""
    return latest_date - earliest_date


fn discard_rate(n_artifacts: Float64, occupation_years: Float64, population: Float64) -> Float64:
    """Discard rate: DR = n / (years * pop)."""
    var denom = occupation_years * population
    if denom <= 0.0:
        return 0.0
    return n_artifacts / denom


fn surveyed_area_coverage(surveyed: Float64, total: Float64) -> Float64:
    """Surveyed area coverage: Coverage = surveyed / total * 100."""
    if total <= 0.0:
        return 0.0
    return surveyed / total * 100.0


fn excavation_volume(length: Float64, width: Float64, depth: Float64) -> Float64:
    """Excavation volume: V = L * W * D (m³)."""
    return length * width * depth


fn artifact_diversity_index(n_types: Float64, n_total: Float64) -> Float64:
    """Margalef diversity index: D = (S - 1) / ln(N)."""
    if n_total <= 1.0:
        return 0.0
    var ln_n = log(n_total)
    if abs(ln_n) < 1e-15:
        return 0.0
    return (n_types - 1.0) / ln_n
