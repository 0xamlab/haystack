"""
cytometry.mojo — Flow and mass cytometry analysis calculations. Zero Python imports.

Public API:
  percent_positive_gate         — percentage in positive gate
  median_fluorescence_intensity — MFI ratio to control
  staining_index                — separation quality metric
  coefficient_of_variation_peak — CV% for peak width
  cell_cycle_g1_fraction        — G1 fraction from DNA content
  apoptosis_annexin_pi          — early/late apoptosis fractions
  lymphocyte_subset_ratio       — CD4/CD8 ratio
  absolute_count                — from relative fraction and CBC
  compensation_spillover        — spectral overlap correction
  sensitivity_lod_cytometry     — limit of detection in events
"""
from std.math import sqrt, log, exp


def percent_positive_gate(
    positive_events: Float64, total_events: Float64
) -> Float64:
    """Percentage of cells within a positive gate.

    Args:
        positive_events: Events above threshold or in gate.
        total_events: Total acquired events.

    Returns:
        % positive (0–100).
    """
    if total_events <= 0.0:
        return 0.0
    return positive_events / total_events * 100.0


def median_fluorescence_intensity(
    sample_mfi: Float64, control_mfi: Float64
) -> Float64:
    """MFI ratio: sample relative to unstained control.

    Args:
        sample_mfi: Sample median fluorescence intensity (AU).
        control_mfi: Unstained or FMO control MFI (AU).

    Returns:
        MFI ratio (>2 = considered positive expression).
    """
    if control_mfi <= 0.0:
        return 0.0
    return sample_mfi / control_mfi


def staining_index(
    positive_mfi: Float64, negative_mfi: Float64, negative_sd: Float64
) -> Float64:
    """Staining index: separation between positive and negative populations.

    SI = (MFI_pos - MFI_neg) / (2 × SD_neg)

    Args:
        positive_mfi: Median of positive population.
        negative_mfi: Median of negative population.
        negative_sd: Standard deviation of negative population.

    Returns:
        Staining index (>3 = well-separated).
    """
    var denom = 2.0 * negative_sd
    if denom <= 0.0:
        return 0.0
    return (positive_mfi - negative_mfi) / denom


def coefficient_of_variation_peak(
    std_dev: Float64, mean_mfi: Float64
) -> Float64:
    """CV% for flow cytometry peak width assessment.

    CV% = (SD / mean) × 100

    Args:
        std_dev: Peak standard deviation.
        mean_mfi: Peak mean fluorescence.

    Returns:
        CV% (<5% = good instrument alignment).
    """
    if mean_mfi <= 0.0:
        return 0.0
    return (std_dev / mean_mfi) * 100.0


def cell_cycle_g1_fraction(
    g1_events: Float64, s_events: Float64, g2m_events: Float64
) -> Float64:
    """G1 fraction from DNA content histogram.

    Args:
        g1_events: Events in G1 peak (2N DNA).
        s_events: Events in S phase.
        g2m_events: Events in G2/M peak (4N DNA).

    Returns:
        G1 fraction (0–1).
    """
    var total = g1_events + s_events + g2m_events
    if total <= 0.0:
        return 0.0
    return g1_events / total


def apoptosis_annexin_pi(
    annexin_only: Float64, annexin_pi: Float64, total: Float64
) -> Float64:
    """Combined apoptosis percentage (early + late).

    Args:
        annexin_only: Annexin-V+/PI- events (early apoptosis).
        annexin_pi: Annexin-V+/PI+ events (late apoptosis).
        total: Total acquired events.

    Returns:
        Total apoptosis fraction (%).
    """
    if total <= 0.0:
        return 0.0
    return (annexin_only + annexin_pi) / total * 100.0


def lymphocyte_subset_ratio(
    cd4_count: Float64, cd8_count: Float64
) -> Float64:
    """CD4:CD8 T cell ratio (HIV monitoring).

    Args:
        cd4_count: CD4+ T cell count (cells/μL or %).
        cd8_count: CD8+ T cell count.

    Returns:
        CD4/CD8 ratio (normal 1.5–2.5; <1 in HIV disease).
    """
    if cd8_count <= 0.0:
        return 0.0
    return cd4_count / cd8_count


def absolute_count(
    relative_percent: Float64, total_leukocytes_ul: Float64
) -> Float64:
    """Absolute cell count from relative percentage and WBC count.

    count = % × WBC_count / 100

    Args:
        relative_percent: Cell type percentage (%).
        total_leukocytes_ul: Total white blood cell count (cells/μL).

    Returns:
        Absolute count (cells/μL).
    """
    return relative_percent * total_leukocytes_ul / 100.0


def compensation_spillover(
    detector_signal: Float64, spillover_fraction: Float64,
    reference_signal: Float64
) -> Float64:
    """Spectral spillover correction: corrected = signal - SF × reference.

    Args:
        detector_signal: Raw signal in detector (AU).
        spillover_fraction: Fraction spilling from reference channel.
        reference_signal: Signal in the reference (primary) channel.

    Returns:
        Spillover-corrected signal (AU).
    """
    return detector_signal - spillover_fraction * reference_signal


def sensitivity_lod_cytometry(
    blank_mean: Float64, blank_sd: Float64, n_sigma: Float64
) -> Float64:
    """Limit of detection for cytometry assay.

    LOD = blank_mean + n_sigma × blank_sd

    Args:
        blank_mean: Mean signal of blank/negative control.
        blank_sd: SD of blank.
        n_sigma: Number of standard deviations above blank (3 for 99.7%).

    Returns:
        LOD in fluorescence units.
    """
    return blank_mean + n_sigma * blank_sd
