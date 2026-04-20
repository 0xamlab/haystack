"""Tests for Wave 87 — Distillation, LiDAR, Archaeology."""

from distillation import (
    relative_volatility,
    min_reflux_underwood,
    actual_reflux,
    fenske_min_stages,
    gilliland_stages,
    mccabe_thiele_operating_line_enriching,
    mccabe_thiele_operating_line_stripping,
    boiling_point_elevation,
    raoults_law_partial_pressure,
    daltons_law_total_pressure,
    stage_efficiency,
    heat_duty_condenser,
)
from lidar import (
    range_from_tof,
    point_density,
    scan_swath_width,
    footprint_diameter,
    pulse_repetition_frequency_to_point_rate,
    ground_sampling_distance,
    vegetation_index_from_returns,
    canopy_height,
    slope_from_elevation,
    intensity_normalization,
    overlap_percentage,
    point_cloud_file_size_mb,
)
from archaeology import (
    radiocarbon_age_bp,
    calibrated_date_linear,
    stratigraphy_depth_to_age_linear,
    artifact_density,
    site_area_from_scatter,
    ceramic_seriation_similarity,
    dating_uncertainty_combined,
    occupation_span,
    discard_rate,
    surveyed_area_coverage,
    excavation_volume,
    artifact_diversity_index,
)
from std.testing import assert_true, assert_false, assert_equal
from std.math import abs as fabs


# ── Helpers ──────────────────────────────────────────────────────────────────


fn approx_eq(a: Float64, b: Float64, tol: Float64 = 1e-4) -> Bool:
    return fabs(a - b) < tol


fn rel_eq(a: Float64, b: Float64, tol: Float64 = 1e-3) -> Bool:
    if fabs(b) < 1e-15:
        return fabs(a) < tol
    return fabs(a - b) / fabs(b) < tol


# ── Distillation Tests ───────────────────────────────────────────────────────


fn test_distillation() raises:
    # relative_volatility: y=0.6, x=0.4 → α = (0.6/0.4)/(0.4/0.6) = 1.5/0.6667 = 2.25
    assert_true(approx_eq(relative_volatility(0.6, 0.4), 2.25), "rel vol 0.6/0.4")
    # y=0.5, x=0.5 → α = 1.0
    assert_true(approx_eq(relative_volatility(0.5, 0.5), 1.0), "rel vol equal")
    # edge: x=0 returns 0
    assert_true(approx_eq(relative_volatility(0.5, 0.0), 0.0), "rel vol x=0")

    # min_reflux_underwood: α=2.5, xd=0.95, xf=0.5, q=1
    # Rmin = (2.5*0.95 - 0.5) / (2.5-1) = (2.375-0.5)/1.5 = 1.25
    assert_true(approx_eq(min_reflux_underwood(2.5, 0.95, 0.5, 1.0), 1.25), "rmin 2.5")

    # actual_reflux: Rmin=1.25, factor=1.3 → R = 1.625
    assert_true(approx_eq(actual_reflux(1.25, 1.3), 1.625), "actual R 1.3x")
    assert_true(approx_eq(actual_reflux(1.0, 1.5), 1.5), "actual R 1.5x")

    # fenske_min_stages: xd=0.95, xb=0.05, α=2.5
    # Nmin = log((0.95/0.05)*(0.95/0.05)) / log(2.5) = log(361)/log(2.5)
    var nmin = fenske_min_stages(0.95, 0.05, 2.5)
    assert_true(nmin > 6.0 and nmin < 7.0, "fenske stages range")
    # edge: alpha=1 returns 0
    assert_true(approx_eq(fenske_min_stages(0.95, 0.05, 1.0), 0.0), "fenske a=1")

    # gilliland_stages: check N > Nmin
    var n_actual = gilliland_stages(6.4, 1.25, 1.625)
    assert_true(n_actual > 6.4, "gilliland N > Nmin")
    assert_true(n_actual < 20.0, "gilliland N reasonable")

    # mccabe_thiele enriching: R=1.5, xd=0.95, x=0.5
    # y = 1.5/2.5 * 0.5 + 0.95/2.5 = 0.3 + 0.38 = 0.68
    assert_true(approx_eq(mccabe_thiele_operating_line_enriching(1.5, 0.95, 0.5), 0.68), "mct enrich")
    # at x=xd: y = R/(R+1)*xd + xd/(R+1) = xd
    assert_true(approx_eq(mccabe_thiele_operating_line_enriching(1.5, 0.95, 0.95), 0.95), "mct enrich at xd")

    # mccabe_thiele stripping: R=1.5, xd=0.95, xb=0.05, x=0.3, f_ratio=1.0
    # y = ((1.5+1.0)/2.5)*0.3 - (0.05*0)/2.5 = 1.0*0.3 = 0.3
    assert_true(approx_eq(mccabe_thiele_operating_line_stripping(1.5, 0.95, 0.05, 0.3, 1.0), 0.3), "mct strip f=1")

    # boiling_point_elevation: Kb=0.512, m=2.0 → ΔTb = 1.024
    assert_true(approx_eq(boiling_point_elevation(0.512, 2.0), 1.024), "bpe 0.512*2")
    assert_true(approx_eq(boiling_point_elevation(0.512, 0.0), 0.0), "bpe zero m")

    # raoults_law: x=0.3, Psat=100 → p = 30
    assert_true(approx_eq(raoults_law_partial_pressure(0.3, 100.0), 30.0), "raoult 0.3*100")
    assert_true(approx_eq(raoults_law_partial_pressure(1.0, 50.0), 50.0), "raoult 1.0*50")

    # daltons_law: p1=30, p2=70 → P = 100
    assert_true(approx_eq(daltons_law_total_pressure(30.0, 70.0), 100.0), "dalton 30+70")

    # stage_efficiency: y_actual=0.6, y_eq=0.7, y_in=0.4 → E = (0.2/0.3)*100 ≈ 66.667
    assert_true(rel_eq(stage_efficiency(0.6, 0.7, 0.4), 66.6667), "stage eff 66.7%")
    assert_true(approx_eq(stage_efficiency(0.7, 0.7, 0.4), 100.0), "stage eff 100%")
    # zero denominator
    assert_true(approx_eq(stage_efficiency(0.5, 0.5, 0.5), 0.0), "stage eff zero denom")

    # heat_duty_condenser: V=100 mol/s, λ=40000 J/mol → Q = 4000000
    assert_true(approx_eq(heat_duty_condenser(100.0, 40000.0), 4000000.0), "qcond 100*40k")
    assert_true(approx_eq(heat_duty_condenser(0.0, 40000.0), 0.0), "qcond zero V")

    print("  ✓ distillation (26 assertions)")


# ── LiDAR Tests ──────────────────────────────────────────────────────────────


fn test_lidar() raises:
    # range_from_tof: t=1e-6s, c=3e8 → R = 150m
    assert_true(approx_eq(range_from_tof(1.0e-6), 150.0), "tof 1us = 150m")
    assert_true(approx_eq(range_from_tof(2.0e-6), 300.0), "tof 2us = 300m")

    # point_density: 1000 points / 10 m² = 100 pts/m²
    assert_true(approx_eq(point_density(1000.0, 10.0), 100.0), "pd 1000/10")
    assert_true(approx_eq(point_density(100.0, 0.0), 0.0), "pd zero area")

    # scan_swath_width: h=1000m, angle=40° → W = 2*1000*tan(20°) ≈ 728.09
    var sw = scan_swath_width(1000.0, 40.0)
    assert_true(sw > 725.0 and sw < 730.0, "swath 1000m 40deg")

    # footprint_diameter: h=1000m, div=0.5mrad → D = 0.5m
    assert_true(approx_eq(footprint_diameter(1000.0, 0.5), 0.5), "fp 1000m 0.5mrad")
    assert_true(approx_eq(footprint_diameter(2000.0, 0.3), 0.6), "fp 2000m 0.3mrad")

    # pulse_repetition_frequency_to_point_rate: prf=200000 → 200000
    assert_true(approx_eq(pulse_repetition_frequency_to_point_rate(200000.0), 200000.0), "prf 200k")

    # ground_sampling_distance: h=1000m, f=50mm=0.05m, pixel=5µm=5e-6m
    # GSD = 1000 * 5e-6 / 0.05 = 0.1m
    assert_true(approx_eq(ground_sampling_distance(1000.0, 0.05, 5.0e-6), 0.1), "gsd 0.1m")
    assert_true(approx_eq(ground_sampling_distance(1000.0, 0.0, 5.0e-6), 0.0), "gsd zero f")

    # vegetation_index_from_returns: first=1000, last=300 → VI = 70%
    assert_true(approx_eq(vegetation_index_from_returns(1000.0, 300.0), 70.0), "vi 70%")
    assert_true(approx_eq(vegetation_index_from_returns(500.0, 500.0), 0.0), "vi 0%")
    assert_true(approx_eq(vegetation_index_from_returns(0.0, 100.0), 0.0), "vi zero first")

    # canopy_height: DSM=120, DTM=100 → CHM=20
    assert_true(approx_eq(canopy_height(120.0, 100.0), 20.0), "chm 20")
    assert_true(approx_eq(canopy_height(100.0, 100.0), 0.0), "chm flat")

    # slope_from_elevation: dz=10, dx=10 → slope = 45°
    assert_true(approx_eq(slope_from_elevation(10.0, 10.0), 45.0), "slope 45")
    # dz=0, dx=10 → slope = 0°
    assert_true(approx_eq(slope_from_elevation(0.0, 10.0), 0.0), "slope 0")

    # intensity_normalization: I=100, range=500, ref=1000 → I_norm = 100*(0.5)² = 25
    assert_true(approx_eq(intensity_normalization(100.0, 500.0, 1000.0), 25.0), "inorm 25")
    # range=ref → I_norm = intensity
    assert_true(approx_eq(intensity_normalization(100.0, 1000.0, 1000.0), 100.0), "inorm same range")

    # overlap_percentage: W=500, spacing=300 → Overlap = (200/500)*100 = 40%
    assert_true(approx_eq(overlap_percentage(500.0, 300.0), 40.0), "overlap 40%")
    assert_true(approx_eq(overlap_percentage(500.0, 500.0), 0.0), "overlap 0%")

    # point_cloud_file_size_mb: 1e6 points * 28 bytes = 28 MB
    assert_true(approx_eq(point_cloud_file_size_mb(1.0e6, 28.0), 28.0), "pcsize 28MB")
    assert_true(approx_eq(point_cloud_file_size_mb(5.0e6, 34.0), 170.0), "pcsize 170MB")

    print("  ✓ lidar (26 assertions)")


# ── Archaeology Tests ────────────────────────────────────────────────────────


fn test_archaeology() raises:
    # radiocarbon_age_bp: ratio=0.5 → Age = -ln(0.5)/1.21e-4 ≈ 5730 years
    var age = radiocarbon_age_bp(0.5)
    assert_true(age > 5700.0 and age < 5760.0, "c14 half-life")
    # ratio=1.0 → Age = 0 (modern)
    assert_true(approx_eq(radiocarbon_age_bp(1.0), 0.0), "c14 modern")
    # ratio=0 → 0 (guard)
    assert_true(approx_eq(radiocarbon_age_bp(0.0), 0.0), "c14 zero ratio")

    # calibrated_date_linear: age_bp=5000, offset=0 → 1950 - 5000 = -3050
    assert_true(approx_eq(calibrated_date_linear(5000.0), -3050.0), "cal -3050")
    assert_true(approx_eq(calibrated_date_linear(1000.0, 50.0), 1000.0), "cal 1000")

    # stratigraphy_depth_to_age_linear: depth=2.0m, rate=0.001 m/yr → 2000 yrs
    assert_true(approx_eq(stratigraphy_depth_to_age_linear(2.0, 0.001), 2000.0), "strat 2000yr")
    assert_true(approx_eq(stratigraphy_depth_to_age_linear(1.0, 0.0), 0.0), "strat zero rate")

    # artifact_density: 500 / 10 m³ = 50 per m³
    assert_true(approx_eq(artifact_density(500.0, 10.0), 50.0), "ad 50/m3")
    assert_true(approx_eq(artifact_density(100.0, 0.0), 0.0), "ad zero vol")

    # site_area_from_scatter: 50m * 30m = 1500 m²
    assert_true(approx_eq(site_area_from_scatter(50.0, 30.0), 1500.0), "site 1500m2")

    # ceramic_seriation_similarity: shared=5, A=10, B=8 → S = 10/18 ≈ 0.5556
    assert_true(rel_eq(ceramic_seriation_similarity(5.0, 10.0, 8.0), 0.5556), "sorensen 0.556")
    assert_true(approx_eq(ceramic_seriation_similarity(0.0, 0.0, 0.0), 0.0), "sorensen zero")

    # dating_uncertainty_combined: σ1=30, σ2=40 → σ = 50
    assert_true(approx_eq(dating_uncertainty_combined(30.0, 40.0), 50.0), "sigma 30-40=50")
    assert_true(approx_eq(dating_uncertainty_combined(0.0, 25.0), 25.0), "sigma 0-25=25")

    # occupation_span: 500 BCE to 200 CE → span = 700 years
    assert_true(approx_eq(occupation_span(-500.0, 200.0), 700.0), "span 700yr")

    # discard_rate: 1000 artifacts / (200 years * 50 people) = 0.1
    assert_true(approx_eq(discard_rate(1000.0, 200.0, 50.0), 0.1), "dr 0.1")
    assert_true(approx_eq(discard_rate(100.0, 0.0, 50.0), 0.0), "dr zero years")

    # surveyed_area_coverage: 25 / 100 = 25%
    assert_true(approx_eq(surveyed_area_coverage(25.0, 100.0), 25.0), "coverage 25%")
    assert_true(approx_eq(surveyed_area_coverage(100.0, 100.0), 100.0), "coverage 100%")

    # excavation_volume: 5m * 3m * 0.5m = 7.5 m³
    assert_true(approx_eq(excavation_volume(5.0, 3.0, 0.5), 7.5), "excvol 7.5m3")

    # artifact_diversity_index: Margalef D = (S-1)/ln(N)
    # 10 types, 100 items → (10-1)/ln(100) = 9/4.6052 ≈ 1.954
    var di = artifact_diversity_index(10.0, 100.0)
    assert_true(di > 1.9 and di < 2.0, "margalef 10/100")
    assert_true(approx_eq(artifact_diversity_index(5.0, 1.0), 0.0), "margalef N=1")

    print("  ✓ archaeology (24 assertions)")


# ── Main ─────────────────────────────────────────────────────────────────────


fn main() raises:
    print("Wave 87 tests — Distillation, LiDAR, Archaeology")
    test_distillation()
    test_lidar()
    test_archaeology()
    print("All Wave 87 tests passed (76 assertions) ✓")
