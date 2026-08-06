"""
proteomics.mojo — Protein analysis and mass spectrometry calculations. Zero Python imports.

Public API:
  molecular_weight_da          — MW from residue masses
  isoelectric_point_approx     — pI from charge state model
  extinction_coefficient       — ε from Trp/Tyr content
  protein_concentration_a280   — from absorbance and extinction
  sequence_coverage            — fraction of protein identified
  peptide_mass_monoisotopic    — from amino acid formula
  peak_area_ratio              — label-free quantification
  protein_abundance_index      — PAI from peptide count
  empa_score                   — exponentially modified PAI
  fdr_target_decoy             — false discovery rate estimate
"""
from std.math import log, exp


def molecular_weight_da(
    residue_count: Float64, avg_residue_mass: Float64
) -> Float64:
    """Protein molecular weight estimate.

    MW ≈ n_residues × avg_mass + 18  (water)

    Args:
        residue_count: Number of amino acid residues.
        avg_residue_mass: Average residue mass (Da, typical ~111 Da).

    Returns:
        Approximate molecular weight (Da).
    """
    return residue_count * avg_residue_mass + 18.0


def isoelectric_point_approx(
    positive_residues: Float64, negative_residues: Float64
) -> Float64:
    """Approximate isoelectric point from charged residue counts.

    Simplified model: pI ≈ (pK_pos + pK_neg) / 2

    Args:
        positive_residues: Number of Arg + Lys residues.
        negative_residues: Number of Asp + Glu residues.

    Returns:
        Approximate pI.
    """
    var ratio = positive_residues / (negative_residues + 1.0)
    return 7.0 + log(ratio) * 1.5


def extinction_coefficient(
    trp_count: Float64, tyr_count: Float64, cys_pairs: Float64
) -> Float64:
    """Molar extinction coefficient at 280 nm (Pace 1995).

    ε = 5500·Trp + 1490·Tyr + 125·Cys(SS)

    Args:
        trp_count: Number of tryptophan residues.
        tyr_count: Number of tyrosine residues.
        cys_pairs: Number of disulfide bonds.

    Returns:
        ε₂₈₀ (M⁻¹cm⁻¹).
    """
    return 5500.0 * trp_count + 1490.0 * tyr_count + 125.0 * cys_pairs


def protein_concentration_a280(
    absorbance_280: Float64, extinction_coeff: Float64, path_cm: Float64
) -> Float64:
    """Protein concentration from Beer-Lambert at 280 nm.

    C = A / (ε × l)

    Args:
        absorbance_280: Absorbance at 280 nm.
        extinction_coeff: Molar extinction coefficient (M⁻¹cm⁻¹).
        path_cm: Cuvette path length (cm).

    Returns:
        Protein concentration (M).
    """
    var denom = extinction_coeff * path_cm
    if denom <= 0.0:
        return 0.0
    return absorbance_280 / denom


def sequence_coverage(
    identified_residues: Float64, total_residues: Float64
) -> Float64:
    """Sequence coverage from identified peptides.

    Args:
        identified_residues: Residues covered by observed peptides.
        total_residues: Total residues in protein sequence.

    Returns:
        Sequence coverage fraction (0–1).
    """
    if total_residues <= 0.0:
        return 0.0
    return identified_residues / total_residues


def peptide_mass_monoisotopic(
    formula_mass: Float64, charge: Float64
) -> Float64:
    """m/z of a peptide ion.

    m/z = (M + z × 1.00728) / z

    Args:
        formula_mass: Neutral monoisotopic mass (Da).
        charge: Ion charge state z.

    Returns:
        m/z value.
    """
    if charge <= 0.0:
        return 0.0
    return (formula_mass + charge * 1.00728) / charge


def peak_area_ratio(
    sample_area: Float64, reference_area: Float64
) -> Float64:
    """Label-free quantification ratio from peak areas.

    Args:
        sample_area: Chromatographic peak area in sample.
        reference_area: Peak area in reference/control.

    Returns:
        Abundance ratio (>1 = upregulated in sample).
    """
    if reference_area <= 0.0:
        return 0.0
    return sample_area / reference_area


def protein_abundance_index(
    observed_peptides: Float64, theoretical_peptides: Float64
) -> Float64:
    """Protein Abundance Index: PAI = observed / theoretical peptides.

    Args:
        observed_peptides: Number of unique peptides observed by MS.
        theoretical_peptides: Theoretical tryptic peptides in MW range.

    Returns:
        PAI score.
    """
    if theoretical_peptides <= 0.0:
        return 0.0
    return observed_peptides / theoretical_peptides


def empa_score(pai: Float64) -> Float64:
    """Exponentially modified PAI (emPAI) for absolute quantification.

    emPAI = 10^PAI - 1

    Args:
        pai: Protein Abundance Index.

    Returns:
        emPAI score (proportional to molar protein amount).
    """
    return (10.0 ** pai) - 1.0


def fdr_target_decoy(
    decoy_hits: Float64, target_hits: Float64
) -> Float64:
    """False discovery rate by target-decoy strategy.

    FDR = 2 × decoy_hits / (target_hits + decoy_hits)

    Args:
        decoy_hits: Peptide-spectrum matches to decoy database.
        target_hits: Matches to target database.

    Returns:
        FDR estimate (0–1).
    """
    var total = target_hits + decoy_hits
    if total <= 0.0:
        return 0.0
    return 2.0 * decoy_hits / total
