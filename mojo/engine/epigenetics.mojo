"""
epigenetics.mojo — Epigenetic and gene regulation calculations. Zero Python imports.

Public API:
  methylation_index            — average CpG methylation fraction
  dna_methylation_age          — Horvath clock simplified
  histone_acetylation_ratio    — acetylated vs total histone
  chromatin_accessibility      — ATAC-seq normalised score
  imprinting_ratio             — allelic expression asymmetry
  cpg_observed_expected        — CpG O/E ratio for island detection
  gene_silencing_efficiency    — from reporter assay
  enhancer_activity_index      — H3K27ac signal ratio
  polycomb_enrichment          — H3K27me3 fold over input
  transcription_factor_occupancy — ChIP-seq occupancy score
"""
from std.math import log, exp, sqrt


fn methylation_index(
    methylated_reads: Float64, total_reads: Float64
) -> Float64:
    """Average CpG methylation level (β-value).

    β = methylated / (methylated + unmethylated)

    Args:
        methylated_reads: Methylated cytosine read count.
        total_reads: Total reads covering the locus.

    Returns:
        Methylation fraction β (0–1).
    """
    if total_reads <= 0.0:
        return 0.0
    return methylated_reads / total_reads


fn dna_methylation_age(
    beta_value: Float64, intercept: Float64, slope: Float64
) -> Float64:
    """Simplified epigenetic clock age estimate (Horvath-style linear model).

    age = intercept + slope × β

    Args:
        beta_value: Methylation β-value at clock CpG.
        intercept: Model intercept (years).
        slope: Model slope (years per β unit).

    Returns:
        Predicted biological age (years).
    """
    return intercept + slope * beta_value


fn histone_acetylation_ratio(
    acetylated_signal: Float64, total_histone_signal: Float64
) -> Float64:
    """Fraction of histone H3/H4 that is acetylated.

    Args:
        acetylated_signal: ChIP signal for acetylated histone.
        total_histone_signal: ChIP signal for total histone.

    Returns:
        Acetylation ratio (0–1).
    """
    if total_histone_signal <= 0.0:
        return 0.0
    return acetylated_signal / total_histone_signal


fn chromatin_accessibility(
    atac_reads: Float64, background_reads: Float64, library_size: Float64
) -> Float64:
    """Normalised chromatin accessibility score from ATAC-seq.

    score = (atac - background) / sqrt(library_size)

    Args:
        atac_reads: Reads in open chromatin region.
        background_reads: Expected background reads.
        library_size: Total library size (millions of reads).

    Returns:
        Accessibility score (z-score-like).
    """
    if library_size <= 0.0:
        return 0.0
    return (atac_reads - background_reads) / sqrt(library_size)


fn imprinting_ratio(
    maternal_expr: Float64, paternal_expr: Float64
) -> Float64:
    """Allelic expression ratio for imprinted gene analysis.

    ratio = maternal / (maternal + paternal)

    Args:
        maternal_expr: Maternal allele expression (reads or FPKM).
        paternal_expr: Paternal allele expression.

    Returns:
        Maternal fraction (0–1; 0.5 = biallelic, >0.8 = imprinted).
    """
    var total = maternal_expr + paternal_expr
    if total <= 0.0:
        return 0.5
    return maternal_expr / total


fn cpg_observed_expected(
    cpg_count: Float64, c_count: Float64, g_count: Float64, length: Float64
) -> Float64:
    """CpG observed/expected ratio for island detection.

    O/E = (CpG × N) / (C × G)

    Args:
        cpg_count: Observed CpG dinucleotides.
        c_count: Cytosine count.
        g_count: Guanine count.
        length: Sequence length (bp).

    Returns:
        O/E ratio (>0.6 for CpG islands).
    """
    var denom = c_count * g_count
    if denom <= 0.0 or length <= 0.0:
        return 0.0
    return (cpg_count * length) / denom


fn gene_silencing_efficiency(
    control_expression: Float64, treated_expression: Float64
) -> Float64:
    """Gene silencing efficiency from reporter or RT-qPCR.

    efficiency = 1 - (treated / control)

    Args:
        control_expression: Expression in control condition.
        treated_expression: Expression after silencing (siRNA, miRNA, etc.).

    Returns:
        Silencing efficiency (0–1; 1 = complete silencing).
    """
    if control_expression <= 0.0:
        return 0.0
    var eff = 1.0 - treated_expression / control_expression
    if eff < 0.0:
        return 0.0
    return eff


fn enhancer_activity_index(
    h3k27ac_signal: Float64, h3k4me3_signal: Float64
) -> Float64:
    """Enhancer vs promoter index from histone marks.

    index = H3K27ac / (H3K27ac + H3K4me3)

    Args:
        h3k27ac_signal: H3K27ac ChIP enrichment (enhancer mark).
        h3k4me3_signal: H3K4me3 ChIP enrichment (promoter mark).

    Returns:
        Enhancer activity index (>0.7 = strong enhancer).
    """
    var total = h3k27ac_signal + h3k4me3_signal
    if total <= 0.0:
        return 0.0
    return h3k27ac_signal / total


fn polycomb_enrichment(
    h3k27me3_chip: Float64, h3k27me3_input: Float64
) -> Float64:
    """Polycomb repression enrichment: H3K27me3 fold over input.

    Args:
        h3k27me3_chip: H3K27me3 ChIP-seq reads at locus.
        h3k27me3_input: Input control reads at locus.

    Returns:
        Fold enrichment (>3 = enriched Polycomb domain).
    """
    if h3k27me3_input <= 0.0:
        return 0.0
    return h3k27me3_chip / h3k27me3_input


fn transcription_factor_occupancy(
    chip_enrichment: Float64, motif_score: Float64, accessibility: Float64
) -> Float64:
    """Composite TF occupancy score from ChIP, motif, and accessibility.

    score = enrichment × motif_score × accessibility

    Args:
        chip_enrichment: Fold enrichment over input.
        motif_score: Position weight matrix score (0–1).
        accessibility: ATAC-seq score (normalised 0–1).

    Returns:
        Occupancy score (higher = more likely bound).
    """
    return chip_enrichment * motif_score * accessibility
