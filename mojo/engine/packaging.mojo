"""
packaging.mojo — Packaging Engineering Library. Zero Python imports.

Provides box/cylinder geometry, material utilization, McKee compression
strength, stacking load, cushion curve G-factor, pallet efficiency,
Arrhenius shelf-life, fill percentage, and dimensional weight.

Public API:
  box_volume                  — V = L*W*H
  box_surface_area            — SA = 2*(LW + WH + LH)
  cylinder_volume             — V = π*r²*h
  cylinder_surface_area       — SA = 2π*r*(r+h)
  material_utilization        — MU = product/blank * 100
  compression_strength_mckee  — CS = 5.87*ECT*√(perimeter*thickness)
  stacking_load               — F = weight*(layers-1)
  cushion_curve_g             — G ≈ 2h/(t*(1+σ/10))
  pallet_efficiency           — η = (boxes*box_area)/pallet_area*100
  shelf_life_arrhenius        — k = A*exp(-Ea/(R*T))
  fill_percentage             — FP = prod/container * 100
  dimensional_weight          — DW = L*W*H / factor
"""
from std.math import sqrt, exp


# ── Box geometry ─────────────────────────────────────────────────────────────


fn box_volume(length: Float64, width: Float64, height: Float64) -> Float64:
    """Box volume: V = L * W * H."""
    return length * width * height


fn box_surface_area(
    length: Float64, width: Float64, height: Float64
) -> Float64:
    """Box surface area: SA = 2*(L*W + W*H + L*H)."""
    return 2.0 * (length * width + width * height + length * height)


# ── Cylinder geometry ────────────────────────────────────────────────────────


fn cylinder_volume(radius: Float64, height: Float64) -> Float64:
    """Cylinder volume: V = π*r²*h."""
    var pi: Float64 = 3.141592653589793
    return pi * radius * radius * height


fn cylinder_surface_area(radius: Float64, height: Float64) -> Float64:
    """Cylinder total surface area: SA = 2*π*r*(r + h)."""
    var pi: Float64 = 3.141592653589793
    return 2.0 * pi * radius * (radius + height)


# ── Material & strength ──────────────────────────────────────────────────────


fn material_utilization(
    product_area: Float64, blank_area: Float64
) -> Float64:
    """Material utilization percentage: MU = (product / blank) * 100."""
    return product_area / blank_area * 100.0


fn compression_strength_mckee(
    ect: Float64, perimeter: Float64, thickness: Float64
) -> Float64:
    """McKee box compression strength: CS = 5.87 * ECT * √(perimeter * thickness).

    ect = edge crush test value (kN/m or lbf/in).
    """
    return 5.87 * ect * sqrt(perimeter * thickness)


# ── Stacking & cushioning ───────────────────────────────────────────────────


fn stacking_load(weight: Float64, layers: Float64) -> Float64:
    """Static stacking load on bottom box: F = weight * (layers - 1)."""
    return weight * (layers - 1.0)


fn cushion_curve_g(
    drop_height: Float64,
    cushion_thickness: Float64,
    static_stress: Float64,
) -> Float64:
    """Simplified cushion curve G-factor.

    G ≈ 2*h / (t * (1 + σ_s/10)).
    drop_height h, cushion_thickness t, static_stress σ_s.
    """
    return 2.0 * drop_height / (
        cushion_thickness * (1.0 + static_stress / 10.0)
    )


# ── Pallet & fill ───────────────────────────────────────────────────────────


fn pallet_efficiency(
    box_area: Float64,
    pallet_area: Float64,
    boxes_per_layer: Float64,
) -> Float64:
    """Pallet area efficiency: η = (boxes * box_area) / pallet_area * 100."""
    return boxes_per_layer * box_area / pallet_area * 100.0


fn fill_percentage(
    product_volume: Float64, container_volume: Float64
) -> Float64:
    """Fill percentage: FP = (product / container) * 100."""
    return product_volume / container_volume * 100.0


# ── Shelf life & shipping ───────────────────────────────────────────────────


fn shelf_life_arrhenius(
    a: Float64, ea: Float64, r: Float64, temperature: Float64
) -> Float64:
    """Arrhenius reaction rate: k = A * exp(-Ea / (R * T)).

    a = pre-exponential factor, ea = activation energy (J/mol),
    r = gas constant (8.314 J/(mol·K)), temperature in Kelvin.
    """
    return a * exp(-ea / (r * temperature))


fn dimensional_weight(
    length: Float64,
    width: Float64,
    height: Float64,
    dim_factor: Float64,
) -> Float64:
    """Dimensional (volumetric) weight: DW = L*W*H / factor.

    Dimensions typically in cm, factor in cm³/kg (e.g. 5000 or 6000).
    """
    return length * width * height / dim_factor
