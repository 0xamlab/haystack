"""
genomics.mojo — Genome analysis calculations. Zero Python imports.

Public API:
  gc_content                   — G+C fraction of a sequence
  genome_size_from_cot         — reassociation kinetics
  coverage_depth               — sequencing depth from reads
  n50_approximation            — assembly quality metric
  snp_density                  — variants per kb
  indel_rate                   — insertion-deletion frequency
  repeat_fraction              — repetitive element content
  gene_density                 — genes per Mb
  read_mapping_efficiency      — fraction of reads mapped
  sequencing_error_rate        — from phred quality score
"""
from std.math import log, exp, pow


def gc_content(g_count: Float64, c_count: Float64, total_bp: Float64) -> Float64:
    """GC content of a sequence.

    GC% = (G + C) / N × 100

    Args:
        g_count: Number of guanine bases.
        c_count: Number of cytosine bases.
        total_bp: Total sequence length (bp).

    Returns:
        GC content (%).
    """
    if total_bp <= 0.0:
        return 0.0
    return (g_count + c_count) / total_bp * 100.0


def genome_size_from_cot(
    cot_half: Float64, reassociation_rate: Float64
) -> Float64:
    """Genome complexity from Cot½ reassociation kinetics.

    size ∝ Cot½ / k₂  (arbitrary units)

    Args:
        cot_half: C₀t½ value (mol·s/L).
        reassociation_rate: Second-order reassociation rate k₂.

    Returns:
        Relative genome size (nucleotide pairs × 1e-9 = Gbp scale).
    """
    if reassociation_rate <= 0.0:
        return 0.0
    return cot_half / reassociation_rate


def coverage_depth(
    read_count: Float64, read_length: Float64, genome_size_bp: Float64
) -> Float64:
    """Average sequencing coverage depth.

    Depth = (N × L) / G

    Args:
        read_count: Number of sequencing reads.
        read_length: Average read length (bp).
        genome_size_bp: Target genome size (bp).

    Returns:
        Mean coverage depth (×).
    """
    if genome_size_bp <= 0.0:
        return 0.0
    return (read_count * read_length) / genome_size_bp


def n50_approximation(
    total_assembly_bp: Float64, contig_count: Float64
) -> Float64:
    """N50 approximation assuming uniform contig size distribution.

    N50 ≈ total_bp / (2 × n_contigs)

    Args:
        total_assembly_bp: Total assembled base pairs.
        contig_count: Number of contigs/scaffolds.

    Returns:
        Approximate N50 (bp).
    """
    if contig_count <= 0.0:
        return 0.0
    return total_assembly_bp / (2.0 * contig_count)


def snp_density(
    snp_count: Float64, region_bp: Float64
) -> Float64:
    """SNP density per kilobase.

    density = SNPs / (length_bp / 1000)

    Args:
        snp_count: Number of SNPs in region.
        region_bp: Region length (bp).

    Returns:
        SNP density (per kb).
    """
    if region_bp <= 0.0:
        return 0.0
    return snp_count / (region_bp / 1000.0)


def indel_rate(
    indel_count: Float64, callable_bp: Float64
) -> Float64:
    """Insertion/deletion rate.

    rate = indels / callable_bp

    Args:
        indel_count: Number of insertion/deletion variants.
        callable_bp: Base pairs with sufficient coverage.

    Returns:
        Indel rate (per bp).
    """
    if callable_bp <= 0.0:
        return 0.0
    return indel_count / callable_bp


def repeat_fraction(
    repeat_bp: Float64, genome_size_bp: Float64
) -> Float64:
    """Fraction of genome composed of repetitive elements.

    Args:
        repeat_bp: Bases annotated as repetitive.
        genome_size_bp: Total genome size (bp).

    Returns:
        Repeat fraction (0–1).
    """
    if genome_size_bp <= 0.0:
        return 0.0
    return repeat_bp / genome_size_bp


def gene_density(
    gene_count: Float64, genome_size_bp: Float64
) -> Float64:
    """Gene density per megabase.

    Args:
        gene_count: Total annotated genes.
        genome_size_bp: Genome size (bp).

    Returns:
        Gene density (genes/Mb).
    """
    if genome_size_bp <= 0.0:
        return 0.0
    return gene_count / (genome_size_bp / 1e6)


def read_mapping_efficiency(
    mapped_reads: Float64, total_reads: Float64
) -> Float64:
    """Fraction of reads that mapped to the reference.

    Args:
        mapped_reads: Reads with valid alignment.
        total_reads: Total input reads.

    Returns:
        Mapping efficiency (0–1).
    """
    if total_reads <= 0.0:
        return 0.0
    return mapped_reads / total_reads


def sequencing_error_rate(phred_q: Float64) -> Float64:
    """Base-call error probability from Phred quality score.

    P_error = 10^(-Q/10)

    Args:
        phred_q: Phred quality score Q (0–40+).

    Returns:
        Error probability (0–1).
    """
    return pow(10.0, -phred_q / 10.0)
