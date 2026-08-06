"""Tests for Wave 82 — Printing, Fire Safety, Procurement."""

from printing import (
    dpi_to_lpi,
    pixel_count,
    file_size_uncompressed,
    bleed_area,
    spine_width,
    ink_coverage,
    paper_weight_gsm_to_lb,
    sheets_per_ream,
    cost_per_page,
    imposition_pages,
    color_delta_e,
    dot_gain_apparent,
)
from fire_safety import (
    fire_load_density,
    heat_release_rate,
    flashover_mfo,
    sprinkler_activation_time,
    smoke_layer_height,
    evacuation_time,
    safe_egress_time,
    fire_resistance_rating,
    ventilation_factor,
    fire_severity,
    co_concentration_danger,
    occupant_load,
)
from procurement import (
    total_cost_of_ownership,
    price_variance,
    purchase_price_variance_pct,
    inventory_turnover,
    days_inventory_outstanding,
    economic_order_quantity,
    reorder_point,
    safety_stock,
    supplier_score_weighted,
    savings_percentage,
    maverick_spend_ratio,
    payment_discount_annualized,
)
from std.testing import assert_true, assert_false, assert_equal
from std.math import abs as fabs, sqrt


# ── Helpers ──────────────────────────────────────────────────────────────────


def approx_eq(a: Float64, b: Float64, tol: Float64 = 1e-4) -> Bool:
    return fabs(a - b) < tol


def rel_eq(a: Float64, b: Float64, tol: Float64 = 1e-3) -> Bool:
    if fabs(b) < 1e-15:
        return fabs(a) < tol
    return fabs(a - b) / fabs(b) < tol


# ── Printing & Publishing Tests ──────────────────────────────────────────────


def test_printing() raises:
    # dpi_to_lpi: 300 DPI / 2 = 150 LPI
    assert_true(approx_eq(dpi_to_lpi(300.0, 2.0), 150.0), "dpi_to_lpi 300/2")
    assert_true(approx_eq(dpi_to_lpi(600.0, 2.0), 300.0), "dpi_to_lpi 600/2")
    assert_true(approx_eq(dpi_to_lpi(1200.0, 3.0), 400.0), "dpi_to_lpi 1200/3")
    # zero guard
    assert_true(approx_eq(dpi_to_lpi(300.0, 0.0), 0.0), "dpi_to_lpi zero factor")

    # pixel_count: 8.5 x 11 @ 300 DPI = (2550)*(3300) = 8415000
    assert_true(approx_eq(pixel_count(8.5, 11.0, 300.0), 8415000.0), "pixel_count 8.5x11@300")
    assert_true(approx_eq(pixel_count(4.0, 6.0, 150.0), 540000.0), "pixel_count 4x6@150")

    # file_size_uncompressed: 1000x1000 @ 8bit 3ch = 3000000 bytes
    assert_true(approx_eq(file_size_uncompressed(1000.0, 1000.0, 8.0, 3.0), 3000000.0), "file_size 1k")
    assert_true(approx_eq(file_size_uncompressed(2000.0, 1500.0, 16.0, 4.0), 24000000.0), "file_size 2k")

    # bleed_area: 210x297mm + 3mm bleed = 216x303 = 65448
    assert_true(approx_eq(bleed_area(210.0, 297.0, 3.0), 65448.0), "bleed_area A4+3mm")
    assert_true(approx_eq(bleed_area(100.0, 100.0, 5.0), 12100.0), "bleed_area 100x100+5mm")

    # spine_width: 200 pages * 0.1mm / 2 = 10mm
    assert_true(approx_eq(spine_width(200.0, 0.1), 10.0), "spine_width 200p")
    assert_true(approx_eq(spine_width(400.0, 0.05), 10.0), "spine_width 400p thin")

    # ink_coverage: 80+70+90+40 = 280%
    assert_true(approx_eq(ink_coverage(80.0, 70.0, 90.0, 40.0), 280.0), "ink_coverage")
    assert_true(approx_eq(ink_coverage(100.0, 100.0, 100.0, 100.0), 400.0), "ink_coverage max")

    # paper_weight_gsm_to_lb: 80gsm * 0.67/10 = 5.36
    assert_true(approx_eq(paper_weight_gsm_to_lb(80.0), 5.36), "gsm_to_lb 80")
    assert_true(approx_eq(paper_weight_gsm_to_lb(120.0), 8.04), "gsm_to_lb 120")

    # sheets_per_ream
    assert_equal(sheets_per_ream(), 500)

    # cost_per_page: $50 / 1000 pages = $0.05
    assert_true(approx_eq(cost_per_page(50.0, 1000.0), 0.05), "cost_per_page")
    assert_true(approx_eq(cost_per_page(100.0, 0.0), 0.0), "cost_per_page zero")

    # imposition_pages: 64 finished / 16 per sheet = 4 sheets
    assert_true(approx_eq(imposition_pages(64.0, 16.0), 4.0), "imposition_pages")
    assert_true(approx_eq(imposition_pages(32.0, 8.0), 4.0), "imposition 32/8")

    # color_delta_e: same colour = 0
    assert_true(approx_eq(color_delta_e(50.0, 20.0, -10.0, 50.0, 20.0, -10.0), 0.0), "delta_e same")
    # ΔE = sqrt(1+4+9) = sqrt(14) ≈ 3.7417
    assert_true(rel_eq(color_delta_e(50.0, 20.0, -10.0, 51.0, 22.0, -7.0), sqrt(14.0)), "delta_e diff")

    # dot_gain_apparent: 60 - 50 = 10
    assert_true(approx_eq(dot_gain_apparent(60.0, 50.0), 10.0), "dot_gain")
    assert_true(approx_eq(dot_gain_apparent(45.0, 50.0), -5.0), "dot_gain negative")

    print("  ✓ Printing & Publishing: all passed")


# ── Fire Safety Tests ────────────────────────────────────────────────────────


def test_fire_safety() raises:
    # fire_load_density: 500 MJ / 50 m² = 10 MJ/m²
    assert_true(approx_eq(fire_load_density(500.0, 50.0), 10.0), "fire_load_density")
    assert_true(approx_eq(fire_load_density(1000.0, 0.0), 0.0), "fld zero area")

    # heat_release_rate: 0.05 kg/s * 20000 kJ/kg = 1000 kW
    assert_true(approx_eq(heat_release_rate(0.05, 20000.0), 1000.0), "hrr")
    assert_true(approx_eq(heat_release_rate(0.1, 15000.0), 1500.0), "hrr 2")

    # flashover_mfo: Av=2, Hv=2.5, At=100
    # Q = 750*2*sqrt(2.5) + 378*100 = 1500*1.5811 + 37800 ≈ 40171.65
    var qfo = flashover_mfo(2.0, 2.5, 100.0)
    assert_true(rel_eq(qfo, 750.0 * 2.0 * sqrt(2.5) + 378.0 * 100.0), "flashover")

    # sprinkler_activation_time: RTI=100, v=4 → 100/sqrt(4) = 50
    assert_true(approx_eq(sprinkler_activation_time(100.0, 200.0, 20.0, 4.0), 50.0), "sprinkler")
    assert_true(approx_eq(sprinkler_activation_time(80.0, 300.0, 20.0, 16.0), 20.0), "sprinkler 2")

    # smoke_layer_height: H=3, t=100, HRR=100 → z=3 - 0.1*10*10/3 ≈ -0.333 → 0 (clamped)
    assert_true(approx_eq(smoke_layer_height(3.0, 100.0, 100.0), 0.0), "smoke clamp")
    # H=10, t=4, HRR=1 → z = 10 - 0.1*1*2/10 = 10 - 0.02 = 9.98
    assert_true(approx_eq(smoke_layer_height(10.0, 4.0, 1.0), 9.98), "smoke small")

    # evacuation_time: 200 people / (1.2m * 80p/m/min) = 200/96 ≈ 2.0833
    assert_true(rel_eq(evacuation_time(200.0, 1.2, 80.0), 200.0 / 96.0), "evac_time")

    # safe_egress_time: 30+10+60+120 = 220
    assert_true(approx_eq(safe_egress_time(30.0, 10.0, 60.0, 120.0), 220.0), "rset")

    # fire_resistance_rating: 100mm * 0.6 = 60 min
    assert_true(approx_eq(fire_resistance_rating(100.0, 0.6), 60.0), "frr")
    assert_true(approx_eq(fire_resistance_rating(200.0, 0.5), 100.0), "frr 2")

    # ventilation_factor: 2.0 * sqrt(2.0) ≈ 2.8284
    assert_true(rel_eq(ventilation_factor(2.0, 2.0), 2.0 * sqrt(2.0)), "vent_factor")

    # fire_severity: 500 / 2.8284 ≈ 176.78
    var vf = ventilation_factor(2.0, 2.0)
    assert_true(rel_eq(fire_severity(500.0, vf), 500.0 / vf), "fire_severity")

    # co_concentration_danger
    assert_equal(co_concentration_danger(10.0), 0)
    assert_equal(co_concentration_danger(34.9), 0)
    assert_equal(co_concentration_danger(35.0), 1)
    assert_equal(co_concentration_danger(100.0), 1)
    assert_equal(co_concentration_danger(200.0), 1)
    assert_equal(co_concentration_danger(201.0), 2)
    assert_equal(co_concentration_danger(500.0), 2)

    # occupant_load: 1000 m² / 10 m²/person = 100
    assert_true(approx_eq(occupant_load(1000.0, 10.0), 100.0), "occupant_load")
    assert_true(approx_eq(occupant_load(500.0, 0.0), 0.0), "occupant_load zero")

    print("  ✓ Fire Safety: all passed")


# ── Procurement Tests ────────────────────────────────────────────────────────


def test_procurement() raises:
    # total_cost_of_ownership: 10000+5000+3000+500 = 18500
    assert_true(approx_eq(total_cost_of_ownership(10000.0, 5000.0, 3000.0, 500.0), 18500.0), "tco")

    # price_variance: (12-10)*500 = 1000
    assert_true(approx_eq(price_variance(12.0, 10.0, 500.0), 1000.0), "pv")
    assert_true(approx_eq(price_variance(9.0, 10.0, 100.0), -100.0), "pv negative")

    # purchase_price_variance_pct: (12-10)/10*100 = 20%
    assert_true(approx_eq(purchase_price_variance_pct(12.0, 10.0), 20.0), "ppv%")
    assert_true(approx_eq(purchase_price_variance_pct(8.0, 10.0), -20.0), "ppv% neg")

    # inventory_turnover: 500000/100000 = 5
    assert_true(approx_eq(inventory_turnover(500000.0, 100000.0), 5.0), "inv_turn")

    # days_inventory_outstanding: 365/5 = 73
    assert_true(approx_eq(days_inventory_outstanding(5.0), 73.0), "dio")
    assert_true(approx_eq(days_inventory_outstanding(0.0), 0.0), "dio zero")

    # economic_order_quantity: sqrt(2*10000*50/2) = sqrt(500000) ≈ 707.107
    assert_true(rel_eq(economic_order_quantity(10000.0, 50.0, 2.0), sqrt(500000.0)), "eoq")

    # reorder_point: 100*7 + 150 = 850
    assert_true(approx_eq(reorder_point(100.0, 7.0, 150.0), 850.0), "rop")

    # safety_stock: 1.96 * 20 * sqrt(7) ≈ 103.72
    var ss = safety_stock(1.96, 20.0, 7.0)
    assert_true(rel_eq(ss, 1.96 * 20.0 * sqrt(7.0)), "safety_stock")

    # supplier_score_weighted: 850/10 = 85
    assert_true(approx_eq(supplier_score_weighted(850.0, 10.0), 85.0), "supplier_score")
    assert_true(approx_eq(supplier_score_weighted(100.0, 0.0), 0.0), "supplier zero")

    # savings_percentage: (100-80)/100*100 = 20%
    assert_true(approx_eq(savings_percentage(100.0, 80.0), 20.0), "savings%")
    assert_true(approx_eq(savings_percentage(50.0, 50.0), 0.0), "savings% zero")

    # maverick_spend_ratio: 50000/500000*100 = 10%
    assert_true(approx_eq(maverick_spend_ratio(50000.0, 500000.0), 10.0), "maverick")

    # payment_discount_annualized: 2/10 net 30 → (0.02/0.98)*(365/20)*100 ≈ 37.245%
    var apr = payment_discount_annualized(2.0, 30.0, 10.0)
    var expected_apr = (0.02 / 0.98) * (365.0 / 20.0) * 100.0
    assert_true(rel_eq(apr, expected_apr), "payment_discount")

    print("  ✓ Procurement: all passed")


# ── Main ─────────────────────────────────────────────────────────────────────


def main() raises:
    print("Wave 82 tests: Printing, Fire Safety, Procurement")
    test_printing()
    test_fire_safety()
    test_procurement()
    print("All Wave 82 tests passed ✅")
