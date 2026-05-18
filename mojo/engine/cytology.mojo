"""
cytology.mojo — Cell biology calculations. Zero Python imports.

Public API:
  cell_volume_sphere           — V = (4/3)π r³
  nuclear_cytoplasmic_ratio    — NC = V_nucleus / V_cytoplasm
  membrane_permeability        — P from flux and concentration gradient
  cell_doubling_time           — Td = ln2 / μ
  mitotic_index                — MI = dividing cells / total cells
  cell_viability               — live fraction from dye exclusion
  apoptosis_rate               — from annexin-V positive fraction
  phagocytic_index             — particles per macrophage
  cell_adhesion_strength       — detachment force per area
  osmotic_fragility            — haemolysis from salt concentration
"""
from std.math import sqrt, log, exp, pow


fn cell_volume_sphere(radius_um: Float64) -> Float64:
    """Cell volume assuming spherical shape: V = (4/3)·π·r³.

    Args:
        radius_um: Cell radius (μm).

    Returns:
        Volume (μm³).
    """
    var pi = 3.141592653589793
    return (4.0 / 3.0) * pi * radius_um * radius_um * radius_um


fn nuclear_cytoplasmic_ratio(
    nucleus_volume: Float64, cell_volume: Float64
) -> Float64:
    """Nuclear-to-cytoplasmic volume ratio.

    Args:
        nucleus_volume: Nuclear volume (μm³).
        cell_volume: Total cell volume (μm³).

    Returns:
        N:C ratio (dimensionless; elevated in cancer cells).
    """
    var cytoplasm = cell_volume - nucleus_volume
    if cytoplasm <= 0.0:
        return 0.0
    return nucleus_volume / cytoplasm


fn membrane_permeability(
    flux: Float64, area: Float64, delta_conc: Float64
) -> Float64:
    """Membrane permeability coefficient: P = J / (A · ΔC).

    Args:
        flux: Molar flux (mol/s).
        area: Membrane area (cm²).
        delta_conc: Concentration gradient (mol/cm³).

    Returns:
        Permeability (cm/s).
    """
    var denom = area * delta_conc
    if denom <= 0.0:
        return 0.0
    return flux / denom


fn cell_doubling_time(growth_rate: Float64) -> Float64:
    """Cell population doubling time: Td = ln2 / μ.

    Args:
        growth_rate: Specific growth rate μ (per hour).

    Returns:
        Doubling time (h).
    """
    if growth_rate <= 0.0:
        return 0.0
    return log(2.0) / growth_rate


fn mitotic_index(dividing_cells: Float64, total_cells: Float64) -> Float64:
    """Mitotic index: fraction of cells in mitosis.

    Args:
        dividing_cells: Cells observed in mitosis.
        total_cells: Total cells counted.

    Returns:
        Mitotic index (0–1).
    """
    if total_cells <= 0.0:
        return 0.0
    return dividing_cells / total_cells


fn cell_viability(live_cells: Float64, total_cells: Float64) -> Float64:
    """Cell viability from dye exclusion assay.

    Args:
        live_cells: Dye-excluding (viable) cells.
        total_cells: Total cells counted.

    Returns:
        Viability fraction (0–1).
    """
    if total_cells <= 0.0:
        return 0.0
    return live_cells / total_cells


fn apoptosis_rate(
    annexin_positive: Float64, total_cells: Float64, time_h: Float64
) -> Float64:
    """Apoptosis rate from Annexin-V positive fraction over time.

    Args:
        annexin_positive: Annexin-V+ cells.
        total_cells: Total cells.
        time_h: Assay duration (h).

    Returns:
        Apoptosis rate (cells/h normalised to 1).
    """
    if total_cells <= 0.0 or time_h <= 0.0:
        return 0.0
    return (annexin_positive / total_cells) / time_h


fn phagocytic_index(
    particles_ingested: Float64, macrophage_count: Float64
) -> Float64:
    """Phagocytic index: particles engulfed per macrophage.

    Args:
        particles_ingested: Total particles phagocytosed.
        macrophage_count: Number of macrophages.

    Returns:
        Phagocytic index (particles/cell).
    """
    if macrophage_count <= 0.0:
        return 0.0
    return particles_ingested / macrophage_count


fn cell_adhesion_strength(
    detachment_force_pn: Float64, contact_area_um2: Float64
) -> Float64:
    """Cell adhesion strength: force per unit contact area.

    Args:
        detachment_force_pn: Force required to detach cell (pN).
        contact_area_um2: Contact area (μm²).

    Returns:
        Adhesion strength (pN/μm²).
    """
    if contact_area_um2 <= 0.0:
        return 0.0
    return detachment_force_pn / contact_area_um2


fn osmotic_fragility(
    nacl_conc_g_dl: Float64, median_conc: Float64
) -> Float64:
    """Osmotic fragility index relative to median haemolytic concentration.

    OFI = (median_conc - nacl_conc) / median_conc

    Args:
        nacl_conc_g_dl: NaCl concentration at test point (g/dL).
        median_conc: Concentration causing 50% haemolysis (g/dL).

    Returns:
        Fragility index (positive = more fragile than normal).
    """
    if median_conc <= 0.0:
        return 0.0
    return (median_conc - nacl_conc_g_dl) / median_conc
