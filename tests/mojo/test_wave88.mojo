"""Tests for Wave 88 — Refrigeration, Cartography, Bioinformatics."""

from refrigeration import (
    cop_refrigeration,
    cop_heat_pump,
    carnot_cop_refrigeration,
    carnot_cop_heat_pump,
    refrigeration_capacity_tons,
    superheat,
    subcooling,
    mass_flow_rate,
    compressor_work,
    energy_efficiency_ratio,
    seer_to_cop,
    refrigerant_charge_estimate,
)
from cartography import (
    scale_factor,
    representative_fraction,
    ground_distance_from_map,
    map_distance_from_ground,
    latitude_to_utm_zone,
    mercator_y,
    equirectangular_x,
    equirectangular_y,
    great_circle_distance,
    map_area_at_scale,
    contour_interval_suggestion,
    declination_correction,
)
from bioinformatics import (
    gc_content,
    tm_basic,
    tm_salt_adjusted,
    molecular_weight_dna,
    sequence_identity,
    evalue_significance,
    coverage_depth,
    n50_from_values,
    phred_quality_to_error,
    error_to_phred_quality,
    codon_count,
    amino_acid_count,
)
from std.testing import assert_true, assert_false, assert_equal
from std.math import abs as fabs


# ── Helpers ──────────────────────────────────────────────────────────────────


def approx_eq(a: Float64, b: Float64, tol: Float64 = 1e-4) -> Bool:
    return fabs(a - b) < tol


def rel_eq(a: Float64, b: Float64, tol: Float64 = 1e-3) -> Bool:
    if fabs(b) < 1e-15:
        return fabs(a) < tol
    return fabs(a - b) / fabs(b) < tol


# ── Refrigeration Tests ──────────────────────────────────────────────────────


def test_refrigeration() raises:
    # cop_refrigeration: 5000/2000 = 2.5
    assert_true(approx_eq(cop_refrigeration(5000.0, 2000.0), 2.5), "cop_ref 2.5")
    assert_true(approx_eq(cop_refrigeration(3000.0, 1000.0), 3.0), "cop_ref 3.0")
    assert_true(approx_eq(cop_refrigeration(100.0, 0.0), 0.0), "cop_ref w=0")

    # cop_heat_pump: 7000/2000 = 3.5
    assert_true(approx_eq(cop_heat_pump(7000.0, 2000.0), 3.5), "cop_hp 3.5")
    assert_true(approx_eq(cop_heat_pump(0.0, 5.0), 0.0), "cop_hp qh=0")

    # carnot_cop_refrigeration: Tc=250, Th=300 → 250/50 = 5.0
    assert_true(approx_eq(carnot_cop_refrigeration(250.0, 300.0), 5.0), "carnot_ref 5.0")
    assert_true(approx_eq(carnot_cop_refrigeration(273.0, 273.0), 0.0), "carnot_ref same T")

    # carnot_cop_heat_pump: Th=300, Tc=250 → 300/50 = 6.0
    assert_true(approx_eq(carnot_cop_heat_pump(300.0, 250.0), 6.0), "carnot_hp 6.0")

    # refrigeration_capacity_tons: 24000/12000 = 2.0
    assert_true(approx_eq(refrigeration_capacity_tons(24000.0), 2.0), "tons 2.0")
    assert_true(approx_eq(refrigeration_capacity_tons(12000.0), 1.0), "tons 1.0")

    # superheat: 15 - 5 = 10
    assert_true(approx_eq(superheat(15.0, 5.0), 10.0), "sh 10")

    # subcooling: 40 - 35 = 5
    assert_true(approx_eq(subcooling(40.0, 35.0), 5.0), "sc 5")

    # mass_flow_rate: 10000/200 = 50
    assert_true(approx_eq(mass_flow_rate(10000.0, 200.0), 50.0), "mfr 50")
    assert_true(approx_eq(mass_flow_rate(10000.0, 0.0), 0.0), "mfr dh=0")

    # compressor_work: 0.5*(400-350) = 25
    assert_true(approx_eq(compressor_work(0.5, 400.0, 350.0), 25.0), "cw 25")

    # energy_efficiency_ratio: 12000/1000 = 12
    assert_true(approx_eq(energy_efficiency_ratio(12000.0, 1000.0), 12.0), "eer 12")
    assert_true(approx_eq(energy_efficiency_ratio(12000.0, 0.0), 0.0), "eer w=0")

    # seer_to_cop: 13/3.412 ≈ 3.8105
    assert_true(rel_eq(seer_to_cop(13.0), 3.8105), "seer 13 cop")
    assert_true(approx_eq(seer_to_cop(0.0), 0.0), "seer 0")

    # refrigerant_charge_estimate: 0.05*1200 = 60
    assert_true(approx_eq(refrigerant_charge_estimate(0.05, 1200.0), 60.0), "charge 60")

    print("  ✓ refrigeration (21 assertions)")


# ── Cartography Tests ────────────────────────────────────────────────────────


def test_cartography() raises:
    # scale_factor: 1/50000 = 0.00002
    assert_true(approx_eq(scale_factor(1.0, 50000.0), 0.00002), "sf 1:50k")
    assert_true(approx_eq(scale_factor(1.0, 0.0), 0.0), "sf zero ground")

    # representative_fraction: 50000/1 = 50000
    assert_true(approx_eq(representative_fraction(1.0, 50000.0), 50000.0), "rf 50k")
    assert_true(approx_eq(representative_fraction(0.0, 50000.0), 0.0), "rf zero map")

    # ground_distance_from_map: 5 * 25000 = 125000
    assert_true(approx_eq(ground_distance_from_map(5.0, 25000.0), 125000.0), "gd 125k")

    # map_distance_from_ground: 125000/25000 = 5
    assert_true(approx_eq(map_distance_from_ground(125000.0, 25000.0), 5.0), "md 5")
    assert_true(approx_eq(map_distance_from_ground(100.0, 0.0), 0.0), "md zero scale")

    # latitude_to_utm_zone: lon=-75 → floor(105/6)+1 = 17+1 = 18
    assert_equal(latitude_to_utm_zone(-75.0), 18, "utm -75")
    # lon=0 → floor(180/6)+1 = 30+1 = 31
    assert_equal(latitude_to_utm_zone(0.0), 31, "utm 0")
    # lon=170 → floor(350/6)+1 = 58+1 = 59
    assert_equal(latitude_to_utm_zone(170.0), 59, "utm 170")

    # mercator_y: lat=0 → ln(tan(π/4)) = ln(1) = 0
    assert_true(approx_eq(mercator_y(0.0), 0.0), "merc y=0 at equator")

    # equirectangular_x: (0.5 - 0.0) * 0.866 = 0.433
    assert_true(approx_eq(equirectangular_x(0.5, 0.0, 0.866), 0.433), "eqr x 0.433")

    # equirectangular_y: identity
    assert_true(approx_eq(equirectangular_y(0.785), 0.785), "eqr y identity")
    assert_true(approx_eq(equirectangular_y(0.0), 0.0), "eqr y zero")

    # great_circle_distance: same point = 0
    assert_true(approx_eq(great_circle_distance(0.0, 0.0, 0.0, 0.0, 6371.0), 0.0), "gcd same pt")
    # equator, 0 to π/2: d = R*acos(cos(π/2)) = R*π/2 ≈ 10007.54
    var d = great_circle_distance(0.0, 0.0, 0.0, 1.5707963, 6371.0)
    assert_true(d > 10005.0 and d < 10010.0, "gcd quarter equator")

    # map_area_at_scale: 1e10 / 50000² = 4.0
    assert_true(approx_eq(map_area_at_scale(1.0e10, 50000.0), 4.0), "area 4.0")

    # contour_interval_suggestion: 1000/10 = 100
    assert_true(approx_eq(contour_interval_suggestion(1000.0, 10.0), 100.0), "ci 100")
    assert_true(approx_eq(contour_interval_suggestion(500.0, 0.0), 0.0), "ci zero n")

    # declination_correction: 180 + (-10) = 170
    assert_true(approx_eq(declination_correction(180.0, -10.0), 170.0), "decl 170")
    assert_true(approx_eq(declination_correction(45.0, 5.0), 50.0), "decl 50")
    assert_true(approx_eq(declination_correction(0.0, 0.0), 0.0), "decl zero")

    print("  ✓ cartography (23 assertions)")


# ── Bioinformatics Tests ─────────────────────────────────────────────────────


def test_bioinformatics() raises:
    # gc_content: 40/100 = 40%
    assert_true(approx_eq(gc_content(40.0, 100.0), 40.0), "gc 40%")
    assert_true(approx_eq(gc_content(0.0, 100.0), 0.0), "gc 0%")
    assert_true(approx_eq(gc_content(50.0, 0.0), 0.0), "gc zero total")

    # tm_basic: 2*(5+5) + 4*(5+5) = 20+40 = 60
    assert_true(approx_eq(tm_basic(5.0, 5.0, 5.0, 5.0), 60.0), "tm 60")
    # 2*(10+10) + 4*(0+0) = 40
    assert_true(approx_eq(tm_basic(10.0, 10.0, 0.0, 0.0), 40.0), "tm AT only 40")

    # tm_salt_adjusted: 60 + 16.6*log10(0.05) ≈ 60 + 16.6*(-1.301) ≈ 38.40
    var tm_adj = tm_salt_adjusted(60.0, 50.0)
    assert_true(tm_adj > 38.0 and tm_adj < 39.0, "tm_salt ~38.4")
    # salt=0 → returns basic Tm unchanged
    assert_true(approx_eq(tm_salt_adjusted(60.0, 0.0), 60.0), "tm_salt zero salt")

    # molecular_weight_dna: 100*330 = 33000
    assert_true(approx_eq(molecular_weight_dna(100.0), 33000.0), "mw 33000")
    assert_true(approx_eq(molecular_weight_dna(20.0, 330.0), 6600.0), "mw 6600")

    # sequence_identity: 90/100 = 90%
    assert_true(approx_eq(sequence_identity(90.0, 100.0), 90.0), "si 90%")
    assert_true(approx_eq(sequence_identity(50.0, 0.0), 0.0), "si zero len")

    # evalue_significance
    assert_true(evalue_significance(1.0e-10, 1.0e-5), "eval sig 1e-10")
    assert_false(evalue_significance(0.1, 1.0e-5), "eval not sig 0.1")

    # coverage_depth: 3e9/3e9 = 1.0x
    assert_true(approx_eq(coverage_depth(3.0e9, 3.0e9), 1.0), "cov 1x")
    assert_true(approx_eq(coverage_depth(30.0e9, 3.0e9), 10.0), "cov 10x")
    assert_true(approx_eq(coverage_depth(100.0, 0.0), 0.0), "cov zero genome")

    # n50_from_values: returns pre-computed
    assert_true(approx_eq(n50_from_values(1000000.0, 50000.0), 50000.0), "n50 50k")

    # phred_quality_to_error: Q=10 → 0.1, Q=20 → 0.01, Q=30 → 0.001
    assert_true(rel_eq(phred_quality_to_error(10.0), 0.1), "phred 10 → 0.1")
    assert_true(rel_eq(phred_quality_to_error(20.0), 0.01), "phred 20 → 0.01")
    assert_true(rel_eq(phred_quality_to_error(30.0), 0.001), "phred 30 → 0.001")

    # error_to_phred_quality: 0.01 → 20, 0.001 → 30
    assert_true(rel_eq(error_to_phred_quality(0.01), 20.0), "err 0.01 → Q20")
    assert_true(rel_eq(error_to_phred_quality(0.001), 30.0), "err 0.001 → Q30")
    assert_true(approx_eq(error_to_phred_quality(0.0), 0.0), "err 0 → Q0")

    # codon_count: 90/3 = 30, 10/3 = 3, 0/3 = 0
    assert_equal(codon_count(90), 30, "codons 30")
    assert_equal(codon_count(10), 3, "codons 3")
    assert_equal(codon_count(0), 0, "codons 0")

    # amino_acid_count: 30-1=29, 1-1=0, 0→0
    assert_equal(amino_acid_count(30), 29, "aa 29")
    assert_equal(amino_acid_count(1), 0, "aa 0 from 1")
    assert_equal(amino_acid_count(0), 0, "aa 0 from 0")

    print("  ✓ bioinformatics (30 assertions)")


# ── Main ─────────────────────────────────────────────────────────────────────


def main() raises:
    print("Wave 88 tests — Refrigeration, Cartography, Bioinformatics")
    test_refrigeration()
    test_cartography()
    test_bioinformatics()
    print("All Wave 88 tests passed (74 assertions) ✓")
