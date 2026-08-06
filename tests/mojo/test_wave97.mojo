"""Wave 97 tests -- aquaculture, adhesives, traffic_signal (70+ assertions)."""

from std.testing import assert_true, assert_false, assert_equal
from std.math import abs, log, exp, cos

# -- aquaculture imports --
from aquaculture import (
    stocking_density,
    feed_conversion_ratio,
    specific_growth_rate,
    dissolved_oxygen_consumption,
    water_exchange_rate,
    ammonia_production,
    carrying_capacity,
    harvest_weight,
    survival_rate,
    production_per_cycle,
    biofilter_capacity,
    cost_per_kg_produced,
)

# -- adhesives imports --
from adhesives import (
    lap_shear_strength,
    peel_strength,
    bond_line_thickness,
    coverage_rate,
    pot_life_temperature_adjusted,
    cure_time_temperature,
    joint_efficiency,
    thermal_cycle_life,
    viscosity_temperature,
    surface_energy_contact_angle,
    open_time_estimate,
    bond_area_from_load,
)

# -- traffic_signal imports --
from traffic_signal import (
    cycle_length_webster,
    effective_green,
    green_ratio,
    capacity_lane,
    volume_to_capacity,
    delay_uniform,
    pedestrian_crossing_time,
    yellow_interval,
    all_red_interval,
    level_of_service_delay,
    intersection_capacity_utilization,
    peak_hour_factor,
)


def approx(a: Float64, b: Float64, tol: Float64 = 1e-6) -> Bool:
    if abs(b) < 1e-12:
        return abs(a - b) < tol
    return abs(a - b) / abs(b) < tol


def main() raises:
    print("=== Wave 97 Tests ===")
    var n: Int = 0

    # -- aquaculture -------------------------------------------------------

    # stocking_density: 500 kg / 10 m3 = 50 kg/m3
    assert_true(approx(stocking_density(500.0, 10.0), 50.0), "stocking_density basic")
    n += 1
    assert_true(approx(stocking_density(1200.0, 100.0), 12.0), "stocking_density large")
    n += 1

    # feed_conversion_ratio: 100 kg feed / 60 kg gain = 1.6667
    assert_true(approx(feed_conversion_ratio(100.0, 60.0), 100.0 / 60.0), "fcr basic")
    n += 1
    assert_true(approx(feed_conversion_ratio(80.0, 50.0), 1.6), "fcr 1.6")
    n += 1

    # specific_growth_rate: (ln(50)-ln(10))/30 * 100
    var sgr_exp = (log(50.0) - log(10.0)) / 30.0 * 100.0
    assert_true(approx(specific_growth_rate(50.0, 10.0, 30.0), sgr_exp), "sgr basic")
    n += 1
    assert_true(approx(specific_growth_rate(100.0, 100.0, 10.0), 0.0), "sgr zero growth")
    n += 1

    # dissolved_oxygen_consumption: 200 kg * 300 mg/kg/hr = 60000 mg/hr
    assert_true(approx(dissolved_oxygen_consumption(200.0, 300.0), 60000.0), "do basic")
    n += 1

    # water_exchange_rate: 5 m3/hr / 50 m3 * 100 = 10 %/hr
    assert_true(approx(water_exchange_rate(5.0, 50.0), 10.0), "exchange rate basic")
    n += 1
    assert_true(approx(water_exchange_rate(2.0, 20.0), 10.0), "exchange rate 10pct")
    n += 1

    # ammonia_production: 10 kg/day * 35/100 * 0.03 = 0.105
    assert_true(approx(ammonia_production(10.0, 35.0), 0.105), "ammonia basic")
    n += 1
    assert_true(approx(ammonia_production(20.0, 40.0), 0.24), "ammonia 20kg 40pct")
    n += 1

    # carrying_capacity: 60000 mg/hr / 300 mg/kg/hr = 200 kg
    assert_true(approx(carrying_capacity(60000.0, 300.0), 200.0), "cc basic")
    n += 1

    # harvest_weight: 10 * exp(sgr*90/100)
    var sgr_val = sgr_exp  # ~5.365
    var hw_exp = 10.0 * exp(sgr_val * 90.0 / 100.0)
    assert_true(approx(harvest_weight(10.0, sgr_val, 90.0), hw_exp), "harvest_weight basic")
    n += 1
    # With sgr=0, harvest = initial
    assert_true(approx(harvest_weight(25.0, 0.0, 60.0), 25.0), "harvest_weight zero sgr")
    n += 1

    # survival_rate: 900/1000 * 100 = 90%
    assert_true(approx(survival_rate(900.0, 1000.0), 90.0), "survival 90pct")
    n += 1
    assert_true(approx(survival_rate(1000.0, 1000.0), 100.0), "survival 100pct")
    n += 1

    # production_per_cycle: 0.5 kg * 10000 * 90/100 = 4500 kg
    assert_true(approx(production_per_cycle(0.5, 10000.0, 90.0), 4500.0), "production basic")
    n += 1

    # biofilter_capacity: 500 m2 * 0.5 g/m2/day = 250 g/day
    assert_true(approx(biofilter_capacity(500.0, 0.5), 250.0), "biofilter basic")
    n += 1

    # cost_per_kg_produced: 50000 / 4500
    assert_true(approx(cost_per_kg_produced(50000.0, 4500.0), 50000.0 / 4500.0), "cost/kg basic")
    n += 1

    # -- adhesives ---------------------------------------------------------

    # lap_shear_strength: 5000 N / 625 mm2 = 8.0 MPa
    assert_true(approx(lap_shear_strength(5000.0, 625.0), 8.0), "shear basic")
    n += 1
    assert_true(approx(lap_shear_strength(10000.0, 500.0), 20.0), "shear 20MPa")
    n += 1

    # peel_strength: 50 N / 25 mm = 2.0 N/mm
    assert_true(approx(peel_strength(50.0, 25.0), 2.0), "peel basic")
    n += 1

    # bond_line_thickness: identity
    assert_true(approx(bond_line_thickness(0.15), 0.15), "blt 0.15")
    n += 1
    assert_true(approx(bond_line_thickness(0.05), 0.05), "blt 0.05")
    n += 1

    # coverage_rate: 50 mL / 0.5 m2 = 100 mL/m2
    assert_true(approx(coverage_rate(50.0, 0.5), 100.0), "coverage basic")
    n += 1

    # pot_life_temperature_adjusted: 60 * 2^((25-35)/10) = 30
    assert_true(approx(pot_life_temperature_adjusted(60.0, 35.0, 25.0, 2.0), 30.0), "pot life hot")
    n += 1
    # At ref temp: pot life = ref
    assert_true(approx(pot_life_temperature_adjusted(60.0, 25.0, 25.0, 2.0), 60.0), "pot life ref")
    n += 1
    # Cold: 60 * 2^((25-15)/10) = 120
    assert_true(approx(pot_life_temperature_adjusted(60.0, 15.0, 25.0, 2.0), 120.0), "pot life cold")
    n += 1

    # cure_time_temperature: 120 / 2^((35-25)/10) = 60
    assert_true(approx(cure_time_temperature(120.0, 35.0, 25.0, 2.0), 60.0), "cure hot")
    n += 1
    # At ref: base
    assert_true(approx(cure_time_temperature(120.0, 25.0, 25.0, 2.0), 120.0), "cure ref")
    n += 1
    # Cold: 120 / 2^(-1) = 240
    assert_true(approx(cure_time_temperature(120.0, 15.0, 25.0, 2.0), 240.0), "cure cold")
    n += 1

    # joint_efficiency: 15 / 25 * 100 = 60%
    assert_true(approx(joint_efficiency(15.0, 25.0), 60.0), "je 60pct")
    n += 1

    # thermal_cycle_life: 1000 / (50 * 1e-5 * 0.2) = 1e7
    assert_true(approx(thermal_cycle_life(1000.0, 50.0, 1e-5, 0.2), 1e7), "thermal cycle life")
    n += 1

    # viscosity_temperature: 10 * exp(40000/8.314*(1/373 - 1/298))
    var visc_exp = 10.0 * exp(40000.0 / 8.314 * (1.0 / 373.0 - 1.0 / 298.0))
    assert_true(approx(viscosity_temperature(10.0, 40000.0, 8.314, 373.0, 298.0), visc_exp), "visc temp")
    n += 1
    # Same temp -> same viscosity
    assert_true(approx(viscosity_temperature(10.0, 40000.0, 8.314, 298.0, 298.0), 10.0), "visc same T")
    n += 1

    # surface_energy_contact_angle: gamma_l=72.8, theta=0 -> 72.8*(1+1)^2/4 = 72.8
    assert_true(approx(surface_energy_contact_angle(72.8, 0.0), 72.8), "surface energy 0deg")
    n += 1
    # theta=90 -> 72.8*(1+0)^2/4 = 18.2
    assert_true(approx(surface_energy_contact_angle(72.8, 90.0), 18.2), "surface energy 90deg")
    n += 1
    # theta=60 -> 72.8*(1+0.5)^2/4 = 72.8*2.25/4 = 40.95
    assert_true(approx(surface_energy_contact_angle(72.8, 60.0), 72.8 * 2.25 / 4.0), "surface energy 60deg")
    n += 1

    # open_time_estimate: 500/100 * (1+(25-20)*0.05) = 5 * 1.25 = 6.25
    assert_true(approx(open_time_estimate(500.0, 20.0), 6.25), "open time 20C")
    n += 1
    # At 25C: 500/100 * 1.0 = 5.0
    assert_true(approx(open_time_estimate(500.0, 25.0), 5.0), "open time 25C")
    n += 1
    # At 35C: 500/100 * (1+(25-35)*0.05) = 5*0.5 = 2.5
    assert_true(approx(open_time_estimate(500.0, 35.0), 2.5), "open time 35C")
    n += 1

    # bond_area_from_load: 10000 * 2.0 / 20 = 1000 mm2
    assert_true(approx(bond_area_from_load(10000.0, 20.0, 2.0), 1000.0), "bond area basic")
    n += 1
    assert_true(approx(bond_area_from_load(5000.0, 10.0, 1.5), 750.0), "bond area sf1.5")
    n += 1

    # -- traffic_signal ----------------------------------------------------

    # cycle_length_webster: (1.5*12+5)/(1-0.85) = 23/0.15 ~ 153.333
    assert_true(approx(cycle_length_webster(12.0, 0.85), 23.0 / 0.15), "webster basic")
    n += 1
    # L=16, Y=0.9 -> (29)/(0.1) = 290
    assert_true(approx(cycle_length_webster(16.0, 0.9), 290.0), "webster Y=0.9")
    n += 1

    # effective_green: 30 - 2.5 + 1.5 = 29
    assert_true(approx(effective_green(30.0, 2.5, 1.5), 29.0), "eff green basic")
    n += 1

    # green_ratio: 29/153.333
    var cyc = 23.0 / 0.15
    assert_true(approx(green_ratio(29.0, cyc), 29.0 / cyc), "green ratio basic")
    n += 1

    # capacity_lane: 1800 * 0.5 = 900 veh/hr
    assert_true(approx(capacity_lane(1800.0, 0.5), 900.0), "capacity basic")
    n += 1
    assert_true(approx(capacity_lane(1900.0, 0.4), 760.0), "capacity 760")
    n += 1

    # volume_to_capacity: 800/900
    assert_true(approx(volume_to_capacity(800.0, 900.0), 800.0 / 900.0), "vc basic")
    n += 1

    # delay_uniform: C=90, g/C=0.4, X=0.8
    # d1 = 0.5*90*(0.6)^2/(1-0.8*0.4) = 0.5*90*0.36/0.68
    var d1_exp = 0.5 * 90.0 * 0.36 / 0.68
    assert_true(approx(delay_uniform(90.0, 0.4, 0.8), d1_exp), "delay uniform basic")
    n += 1
    # X > 1 capped: C=120, g/C=0.5, X=1.2 -> d1 = 0.5*120*0.25/(1-1.0*0.5) = 15/0.5=30
    assert_true(approx(delay_uniform(120.0, 0.5, 1.2), 30.0), "delay uniform X>1")
    n += 1

    # pedestrian_crossing_time: 18m / 1.2 m/s = 15s
    assert_true(approx(pedestrian_crossing_time(18.0, 1.2), 15.0), "ped cross basic")
    n += 1

    # yellow_interval: t=1.0, v=16.67 m/s, a=3.05, G=0.02
    var y_exp = 1.0 + 16.67 / (2.0 * (3.05 + 9.81 * 0.02))
    assert_true(approx(yellow_interval(1.0, 16.67, 3.05, 0.02), y_exp), "yellow basic")
    n += 1
    # Grade=0
    var y_flat = 1.0 + 16.67 / (2.0 * 3.05)
    assert_true(approx(yellow_interval(1.0, 16.67, 3.05, 0.0), y_flat), "yellow flat")
    n += 1

    # all_red_interval: (24 + 6)/16.67
    assert_true(approx(all_red_interval(24.0, 6.0, 16.67), 30.0 / 16.67), "all red basic")
    n += 1

    # level_of_service_delay
    assert_equal(level_of_service_delay(5.0), 1, "LOS A")
    n += 1
    assert_equal(level_of_service_delay(10.0), 1, "LOS A boundary")
    n += 1
    assert_equal(level_of_service_delay(15.0), 2, "LOS B")
    n += 1
    assert_equal(level_of_service_delay(20.0), 2, "LOS B boundary")
    n += 1
    assert_equal(level_of_service_delay(25.0), 3, "LOS C")
    n += 1
    assert_equal(level_of_service_delay(35.0), 3, "LOS C boundary")
    n += 1
    assert_equal(level_of_service_delay(45.0), 4, "LOS D")
    n += 1
    assert_equal(level_of_service_delay(55.0), 4, "LOS D boundary")
    n += 1
    assert_equal(level_of_service_delay(70.0), 5, "LOS E")
    n += 1
    assert_equal(level_of_service_delay(80.0), 5, "LOS E boundary")
    n += 1
    assert_equal(level_of_service_delay(100.0), 6, "LOS F")
    n += 1

    # intersection_capacity_utilization: 0.75 + 12/120 = 0.85
    assert_true(approx(intersection_capacity_utilization(0.75, 12.0, 120.0), 0.85), "ICU basic")
    n += 1

    # peak_hour_factor: 1000 / (4*280) = 1000/1120
    assert_true(approx(peak_hour_factor(1000.0, 280.0), 1000.0 / 1120.0), "PHF basic")
    n += 1
    # Perfect uniformity: PHF = 1.0
    assert_true(approx(peak_hour_factor(1000.0, 250.0), 1.0), "PHF perfect")
    n += 1

    print("All", n, "Wave 97 assertions passed.")
