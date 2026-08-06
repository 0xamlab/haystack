"""
bioinformatics.mojo — Bioinformatics Library. Zero Python imports.

Pure Mojo implementations of basic bioinformatics calculations including
GC content, melting temperature, molecular weight, sequence identity,
coverage depth, Phred quality scores, and codon counting.

Public API:
  gc_content                — GC% = gc/total * 100
  tm_basic                  — Tm = 2*(A+T) + 4*(G+C) (Wallace rule)
  tm_salt_adjusted          — Tm_adj = Tm + 16.6*log10(salt/1000)
  molecular_weight_dna      — MW = n * avg (~330 Da/nt)
  sequence_identity         — ID = matches/length * 100
  evalue_significance       — True if evalue < threshold
  coverage_depth            — Coverage = total/genome
  n50_from_values           — N50 approximation (pass pre-computed)
  phred_quality_to_error    — P_error = 10^(-Q/10)
  error_to_phred_quality    — Q = -10*log10(P)
  codon_count               — Codons = length / 3 (integer division)
  amino_acid_count          — AA = codons - 1 (simplified full ORF)
"""
from std.math import abs as fabs, log, pow

comptime LN10: Float64 = 2.302585092994046


# ── gc_content ───────────────────────────────────────────────────────────────


def gc_content(gc_count: Float64, total_bases: Float64) -> Float64:
    """GC content percentage: GC% = (gc_count / total_bases) * 100.

    Args:
        gc_count:    Number of G + C bases.
        total_bases: Total number of bases.

    Returns:
        GC content as a percentage (0–100).
    """
    if fabs(total_bases) < 1e-30:
        return 0.0
    return (gc_count / total_bases) * 100.0


# ── tm_basic ─────────────────────────────────────────────────────────────────


def tm_basic(a_count: Float64, t_count: Float64, g_count: Float64, c_count: Float64) -> Float64:
    """Basic melting temperature (Wallace rule): Tm = 2*(A+T) + 4*(G+C).

    Args:
        a_count: Number of adenine bases.
        t_count: Number of thymine bases.
        g_count: Number of guanine bases.
        c_count: Number of cytosine bases.

    Returns:
        Melting temperature in °C.
    """
    return 2.0 * (a_count + t_count) + 4.0 * (g_count + c_count)


# ── tm_salt_adjusted ─────────────────────────────────────────────────────────


def tm_salt_adjusted(tm_basic_val: Float64, salt_mm: Float64) -> Float64:
    """Salt-adjusted melting temperature: Tm_adj = Tm + 16.6*log10(salt/1000).

    Args:
        tm_basic_val: Basic Tm from Wallace rule (°C).
        salt_mm:      Salt concentration in millimolar.

    Returns:
        Adjusted melting temperature in °C.
    """
    if salt_mm <= 0.0:
        return tm_basic_val
    # log10(x) = log(x) / ln(10)
    var log10_salt = log(salt_mm / 1000.0) / LN10
    return tm_basic_val + 16.6 * log10_salt


# ── molecular_weight_dna ────────────────────────────────────────────────────


def molecular_weight_dna(n_bases: Float64, avg_mw: Float64 = 330.0) -> Float64:
    """Approximate molecular weight of single-stranded DNA: MW = n * avg.

    Args:
        n_bases: Number of nucleotides.
        avg_mw:  Average molecular weight per nucleotide (~330 Da).

    Returns:
        Molecular weight in Daltons.
    """
    return n_bases * avg_mw


# ── sequence_identity ────────────────────────────────────────────────────────


def sequence_identity(matches: Float64, alignment_length: Float64) -> Float64:
    """Sequence identity: ID = (matches / alignment_length) * 100.

    Args:
        matches:          Number of matching positions.
        alignment_length: Total alignment length.

    Returns:
        Identity percentage (0–100).
    """
    if fabs(alignment_length) < 1e-30:
        return 0.0
    return (matches / alignment_length) * 100.0


# ── evalue_significance ──────────────────────────────────────────────────────


def evalue_significance(evalue: Float64, threshold: Float64) -> Bool:
    """Check E-value significance: returns True if evalue < threshold.

    Args:
        evalue:    E-value from BLAST or similar.
        threshold: Significance threshold (e.g., 1e-5).

    Returns:
        True if evalue is below threshold (significant).
    """
    return evalue < threshold


# ── coverage_depth ───────────────────────────────────────────────────────────


def coverage_depth(total_bases_sequenced: Float64, genome_size: Float64) -> Float64:
    """Sequencing coverage depth: Coverage = total_bases / genome_size.

    Args:
        total_bases_sequenced: Total bases sequenced.
        genome_size:           Reference genome size in bases.

    Returns:
        Coverage depth (fold coverage).
    """
    if fabs(genome_size) < 1e-30:
        return 0.0
    return total_bases_sequenced / genome_size


# ── n50_from_values ──────────────────────────────────────────────────────────


def n50_from_values(total_assembly: Float64, half_total: Float64) -> Float64:
    """N50 approximation: returns pre-computed half_total value.

    In practice, N50 is the contig length at which 50% of assembly is covered.
    This function accepts a pre-computed value for pipeline use.

    Args:
        total_assembly: Total assembly size (for context/validation).
        half_total:     Pre-computed N50 value.

    Returns:
        N50 value.
    """
    return half_total


# ── phred_quality_to_error ───────────────────────────────────────────────────


def phred_quality_to_error(phred: Float64) -> Float64:
    """Convert Phred quality to error probability: P = 10^(-Q/10).

    Args:
        phred: Phred quality score.

    Returns:
        Error probability (0 to 1).
    """
    # 10^(-Q/10) = exp((-Q/10) * ln(10))
    return pow(10.0, -phred / 10.0)


# ── error_to_phred_quality ───────────────────────────────────────────────────


def error_to_phred_quality(error_prob: Float64) -> Float64:
    """Convert error probability to Phred quality: Q = -10*log10(P).

    Args:
        error_prob: Error probability (0 to 1).

    Returns:
        Phred quality score.
    """
    if error_prob <= 0.0:
        return 0.0
    return -10.0 * log(error_prob) / LN10


# ── codon_count ──────────────────────────────────────────────────────────────


def codon_count(sequence_length: Int) -> Int:
    """Count codons: Codons = sequence_length / 3 (integer division).

    Args:
        sequence_length: Length of nucleotide sequence.

    Returns:
        Number of complete codons.
    """
    return sequence_length // 3


# ── amino_acid_count ─────────────────────────────────────────────────────────


def amino_acid_count(codon_count_val: Int) -> Int:
    """Amino acid count for full ORF: AA = codons - 1 (minus stop codon).

    Args:
        codon_count_val: Number of codons.

    Returns:
        Number of amino acids (simplified).
    """
    if codon_count_val <= 0:
        return 0
    return codon_count_val - 1
