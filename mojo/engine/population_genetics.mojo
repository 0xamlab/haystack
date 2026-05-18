"""
population_genetics.mojo — Allele frequency and genetic diversity calculations. Zero Python imports.

Public API:
  hardy_weinberg_freq          — genotype frequencies from allele p
  allele_frequency_drift       — Δp from random genetic drift (Wright)
  selection_coefficient        — Δp per generation from fitness
  effective_population_size    — Ne from census and sex ratio
  nucleotide_diversity         — π from pairwise differences
  tajimas_d_simplified         — simplified Tajima's D statistic
  fst_wright                   — Wright's fixation index FST
  inbreeding_coefficient       — F from parent relatedness
  mutation_load                — genetic load from deleterious mutations
  linkage_disequilibrium       — D = p_AB - p_A * p_B
"""
from std.math import sqrt, log


fn hardy_weinberg_freq(p: Float64) -> Float64:
    """Hardy-Weinberg heterozygote frequency: H = 2·p·(1-p).

    Args:
        p: Frequency of dominant allele (0–1).

    Returns:
        Heterozygote frequency 2pq.
    """
    if p < 0.0 or p > 1.0:
        return 0.0
    return 2.0 * p * (1.0 - p)


fn allele_frequency_drift(
    p: Float64, effective_pop_size: Float64
) -> Float64:
    """Standard deviation of allele frequency change per generation from drift.

    σ(Δp) = √(p·q / 2Ne)

    Args:
        p: Current allele frequency.
        effective_pop_size: Effective population size Ne.

    Returns:
        Standard deviation of Δp per generation.
    """
    if effective_pop_size <= 0.0 or p < 0.0 or p > 1.0:
        return 0.0
    var q = 1.0 - p
    return sqrt(p * q / (2.0 * effective_pop_size))


fn selection_coefficient(
    p: Float64, s: Float64, h: Float64
) -> Float64:
    """Change in allele frequency Δp per generation from selection.

    Δp ≈ s·p·q·(p + h·q) / w_bar  (linearized, w_bar ≈ 1)

    Args:
        p: Current frequency of selected allele A.
        s: Selection coefficient (0–1, fitness of aa = 1-s).
        h: Dominance coefficient (0 = recessive, 0.5 = additive, 1 = dominant).

    Returns:
        Δp per generation (approximate).
    """
    if p < 0.0 or p > 1.0:
        return 0.0
    var q = 1.0 - p
    return s * p * q * (p + h * q)


fn effective_population_size(n_female: Float64, n_male: Float64) -> Float64:
    """Effective population size from census counts.

    Ne = 4·Nf·Nm / (Nf + Nm)

    Args:
        n_female: Number of breeding females.
        n_male: Number of breeding males.

    Returns:
        Effective population size Ne.
    """
    var denom = n_female + n_male
    if denom <= 0.0:
        return 0.0
    return 4.0 * n_female * n_male / denom


fn nucleotide_diversity(
    n_sequences: Float64, pairwise_differences: Float64
) -> Float64:
    """Nucleotide diversity π from average pairwise differences.

    π = Σ(differences) / C(n,2)

    Args:
        n_sequences: Number of sequences.
        pairwise_differences: Total pairwise nucleotide differences.

    Returns:
        Nucleotide diversity π.
    """
    if n_sequences < 2.0:
        return 0.0
    var n_pairs = n_sequences * (n_sequences - 1.0) / 2.0
    return pairwise_differences / n_pairs


fn tajimas_d_simplified(
    n: Float64, seg_sites: Float64, avg_pairwise_diff: Float64
) -> Float64:
    """Simplified Tajima's D (ignores variance correction factors).

    D ≈ (π - θ_W) / normalization

    Args:
        n: Sample size (number of sequences).
        seg_sites: Number of segregating sites.
        avg_pairwise_diff: Mean pairwise differences (π).

    Returns:
        Approximate Tajima's D statistic.
    """
    if n <= 1.0 or seg_sites <= 0.0:
        return 0.0
    # Watterson's theta per site approximation
    var a1: Float64 = 0.0
    var i: Float64 = 1.0
    while i < n:
        a1 += 1.0 / i
        i += 1.0
    var theta_w = seg_sites / a1
    # Simplified normalisation (approximate)
    var norm = sqrt(seg_sites * 0.05 + 0.001)
    return (avg_pairwise_diff - theta_w) / norm


fn fst_wright(
    ht: Float64, hs: Float64
) -> Float64:
    """Wright's FST from total and subpopulation heterozygosity.

    FST = (HT - HS) / HT

    Args:
        ht: Total expected heterozygosity.
        hs: Mean within-subpopulation expected heterozygosity.

    Returns:
        FST (0 = no differentiation, 1 = complete).
    """
    if ht <= 0.0:
        return 0.0
    var fst = (ht - hs) / ht
    if fst < 0.0:
        return 0.0
    return fst


fn inbreeding_coefficient(
    p: Float64, observed_het: Float64
) -> Float64:
    """Inbreeding coefficient F from observed vs. expected heterozygosity.

    F = 1 - (H_obs / H_exp)

    Args:
        p: Allele frequency (for computing H_exp = 2pq).
        observed_het: Observed heterozygote frequency.

    Returns:
        Inbreeding coefficient F.
    """
    var h_exp = 2.0 * p * (1.0 - p)
    if h_exp <= 0.0:
        return 0.0
    return 1.0 - observed_het / h_exp


fn mutation_load(
    mutation_rate: Float64, dominance_h: Float64
) -> Float64:
    """Genetic load from deleterious mutations (Haldane's principle).

    L ≈ μ for recessive, L ≈ 2hs for dominant acting.
    Simplified: L = μ / (2·h + ε)

    Args:
        mutation_rate: Per-gene mutation rate μ (per generation).
        dominance_h: Dominance coefficient (h) of deleterious allele.

    Returns:
        Approximate mutation load L.
    """
    if dominance_h < 0.0:
        return mutation_rate
    if dominance_h == 0.0:
        return mutation_rate
    return mutation_rate / (2.0 * dominance_h)


fn linkage_disequilibrium(
    p_ab: Float64, p_a: Float64, p_b: Float64
) -> Float64:
    """Linkage disequilibrium D = p_AB - p_A·p_B.

    Args:
        p_ab: Haplotype frequency of AB.
        p_a: Frequency of allele A.
        p_b: Frequency of allele B.

    Returns:
        D statistic (0 = linkage equilibrium).
    """
    return p_ab - p_a * p_b
