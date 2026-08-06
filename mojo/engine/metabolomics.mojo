"""
metabolomics.mojo — Metabolite profiling and pathway analysis calculations.
Zero Python imports.

Public API:
  metabolite_fold_change        — log2 ratio between conditions
  pathway_enrichment_score      — observed vs expected metabolites
  chemical_similarity_index     — Tanimoto coefficient
  metabolic_flux_ratio          — flux partitioning at branch point
  isotope_label_fraction        — enrichment from 13C labelling
  metabolite_half_life          — from turnover rate
  normalization_zscore           — z-score within sample
  principal_component_variance  — % variance explained
  vip_score                     — variable importance in PLS
  metabolic_distance            — Euclidean in feature space
"""
from std.math import log, sqrt, exp


def metabolite_fold_change(
    condition_conc: Float64, control_conc: Float64
) -> Float64:
    """Log2 fold change of metabolite abundance.

    log2FC = log2(condition / control)

    Args:
        condition_conc: Metabolite level in experimental condition.
        control_conc: Metabolite level in control.

    Returns:
        log2 fold change (>0 = upregulated).
    """
    if control_conc <= 0.0 or condition_conc <= 0.0:
        return 0.0
    return log(condition_conc / control_conc) / log(2.0)


def pathway_enrichment_score(
    observed_hits: Float64, pathway_size: Float64,
    total_detected: Float64, total_metabolome: Float64
) -> Float64:
    """Hypergeometric-based enrichment ratio for a metabolic pathway.

    score = (hits / pathway_size) / (detected / metabolome)

    Args:
        observed_hits: Significantly changed metabolites in pathway.
        pathway_size: Total metabolites mapped to pathway.
        total_detected: Total metabolites detected in study.
        total_metabolome: Total known metabolome size.

    Returns:
        Enrichment ratio (>1 = over-represented).
    """
    var expected = pathway_size * total_detected / total_metabolome
    if expected <= 0.0:
        return 0.0
    return observed_hits / expected


def chemical_similarity_index(
    common_bits: Float64, bits_a: Float64, bits_b: Float64
) -> Float64:
    """Tanimoto similarity coefficient between two fingerprints.

    T = common / (A + B - common)

    Args:
        common_bits: Bits set in both fingerprints.
        bits_a: Total bits set in fingerprint A.
        bits_b: Total bits set in fingerprint B.

    Returns:
        Tanimoto coefficient (0–1).
    """
    var denom = bits_a + bits_b - common_bits
    if denom <= 0.0:
        return 0.0
    return common_bits / denom


def metabolic_flux_ratio(
    branch_flux: Float64, total_flux: Float64
) -> Float64:
    """Flux partitioning ratio at a metabolic branch point.

    ratio = branch_flux / total_flux

    Args:
        branch_flux: Flux through one branch (μmol/g DW/h).
        total_flux: Total flux entering branch point.

    Returns:
        Flux ratio (0–1).
    """
    if total_flux <= 0.0:
        return 0.0
    return branch_flux / total_flux


def isotope_label_fraction(
    labelled_signal: Float64, total_signal: Float64
) -> Float64:
    """Isotope enrichment from ¹³C or ²H tracer experiments.

    fraction = labelled / total

    Args:
        labelled_signal: MS signal from labelled isotopologue.
        total_signal: Sum of all isotopologue signals.

    Returns:
        Labelling fraction (0–1).
    """
    if total_signal <= 0.0:
        return 0.0
    return labelled_signal / total_signal


def metabolite_half_life(turnover_rate: Float64) -> Float64:
    """Metabolite pool half-life from first-order turnover.

    t½ = ln2 / k

    Args:
        turnover_rate: First-order turnover rate constant k (h⁻¹).

    Returns:
        Half-life (h).
    """
    if turnover_rate <= 0.0:
        return 0.0
    return log(2.0) / turnover_rate


def normalization_zscore(
    value: Float64, mean: Float64, std_dev: Float64
) -> Float64:
    """Z-score normalisation of metabolite abundance.

    z = (x - μ) / σ

    Args:
        value: Metabolite intensity in sample.
        mean: Population or batch mean.
        std_dev: Population or batch standard deviation.

    Returns:
        Z-score.
    """
    if std_dev <= 0.0:
        return 0.0
    return (value - mean) / std_dev


def principal_component_variance(
    eigenvalue: Float64, total_variance: Float64
) -> Float64:
    """Fraction of total variance explained by a principal component.

    Args:
        eigenvalue: PC eigenvalue.
        total_variance: Sum of all eigenvalues.

    Returns:
        Variance explained (0–1).
    """
    if total_variance <= 0.0:
        return 0.0
    return eigenvalue / total_variance


def vip_score(
    weights_sq: Float64, q2: Float64, p_vars: Float64
) -> Float64:
    """Variable Importance in Projection (PLS-DA, simplified).

    VIP = sqrt(p × Σ(w²×Q²) / ΣQ²)

    Args:
        weights_sq: Sum of squared PLS weights for this variable × Q².
        q2: Total Q² of model (explained variance in Y).
        p_vars: Total number of variables.

    Returns:
        VIP score (>1 = important variable).
    """
    if q2 <= 0.0:
        return 0.0
    return sqrt(p_vars * weights_sq / q2)


def metabolic_distance(
    n_features: Float64, sum_sq_diff: Float64
) -> Float64:
    """Euclidean distance in metabolomics feature space.

    d = sqrt(Σ(xi - yi)²)

    Args:
        n_features: Number of metabolite features.
        sum_sq_diff: Sum of squared differences across features.

    Returns:
        Euclidean distance (metabolomics units).
    """
    return sqrt(sum_sq_diff)
