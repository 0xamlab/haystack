"""bench_packaging.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from packaging import box_volume, box_surface_area, cylinder_volume, cylinder_surface_area, material_utilization, compression_strength_mckee, stacking_load, cushion_curve_g, pallet_efficiency, fill_percentage, shelf_life_arrhenius, dimensional_weight
from std.time import perf_counter_ns

def main() raises:
    var _lf5 = List[Float64]()
    _lf5.append(0.5); _lf5.append(0.6); _lf5.append(0.7)
    _lf5.append(0.4); _lf5.append(0.3)
    var _li5 = List[Int]()
    _li5.append(0); _li5.append(1); _li5.append(2)
    _li5.append(3); _li5.append(4)
    var _lb5 = List[Bool]()
    _lb5.append(True); _lb5.append(False); _lb5.append(True)
    _lb5.append(True); _lb5.append(False)
    var _lub5 = List[UInt8]()
    _lub5.append(1); _lub5.append(2); _lub5.append(3)
    _lub5.append(4); _lub5.append(5)
    var _llf3 = List[List[Float64]]()
    _llf3.append(List[Float64]()); _llf3.append(List[Float64]()); _llf3.append(List[Float64]())
    _llf3[0].append(4.0); _llf3[0].append(0.0); _llf3[0].append(5.0)
    _llf3[1].append(0.0); _llf3[1].append(3.0); _llf3[1].append(4.0)
    _llf3[2].append(3.0); _llf3[2].append(4.0); _llf3[2].append(0.0)
    var N: Int = 10000

    var _acc_box_volume: Float64 = 0.0
    var _t0_box_volume = perf_counter_ns()
    for _ in range(N):
        _acc_box_volume += box_volume(0.5, 0.5, 0.5)
    var _t1_box_volume = perf_counter_ns()
    var _ns_box_volume = Float64(_t1_box_volume - _t0_box_volume) / Float64(N)
    print("MOJO_TIMING packaging::box_volume", _ns_box_volume, _acc_box_volume)
    var _acc_box_surface_area: Float64 = 0.0
    var _t0_box_surface_area = perf_counter_ns()
    for _ in range(N):
        _acc_box_surface_area += box_surface_area(0.5, 0.5, 0.5)
    var _t1_box_surface_area = perf_counter_ns()
    var _ns_box_surface_area = Float64(_t1_box_surface_area - _t0_box_surface_area) / Float64(N)
    print("MOJO_TIMING packaging::box_surface_area", _ns_box_surface_area, _acc_box_surface_area)
    var _acc_cylinder_volume: Float64 = 0.0
    var _t0_cylinder_volume = perf_counter_ns()
    for _ in range(N):
        _acc_cylinder_volume += cylinder_volume(0.5, 0.5)
    var _t1_cylinder_volume = perf_counter_ns()
    var _ns_cylinder_volume = Float64(_t1_cylinder_volume - _t0_cylinder_volume) / Float64(N)
    print("MOJO_TIMING packaging::cylinder_volume", _ns_cylinder_volume, _acc_cylinder_volume)
    var _acc_cylinder_surface_area: Float64 = 0.0
    var _t0_cylinder_surface_area = perf_counter_ns()
    for _ in range(N):
        _acc_cylinder_surface_area += cylinder_surface_area(0.5, 0.5)
    var _t1_cylinder_surface_area = perf_counter_ns()
    var _ns_cylinder_surface_area = Float64(_t1_cylinder_surface_area - _t0_cylinder_surface_area) / Float64(N)
    print("MOJO_TIMING packaging::cylinder_surface_area", _ns_cylinder_surface_area, _acc_cylinder_surface_area)
    var _acc_material_utilization: Float64 = 0.0
    var _t0_material_utilization = perf_counter_ns()
    for _ in range(N):
        _acc_material_utilization += material_utilization(0.5, 0.5)
    var _t1_material_utilization = perf_counter_ns()
    var _ns_material_utilization = Float64(_t1_material_utilization - _t0_material_utilization) / Float64(N)
    print("MOJO_TIMING packaging::material_utilization", _ns_material_utilization, _acc_material_utilization)
    var _acc_compression_strength_mckee: Float64 = 0.0
    var _t0_compression_strength_mckee = perf_counter_ns()
    for _ in range(N):
        _acc_compression_strength_mckee += compression_strength_mckee(0.5, 0.5, 0.5)
    var _t1_compression_strength_mckee = perf_counter_ns()
    var _ns_compression_strength_mckee = Float64(_t1_compression_strength_mckee - _t0_compression_strength_mckee) / Float64(N)
    print("MOJO_TIMING packaging::compression_strength_mckee", _ns_compression_strength_mckee, _acc_compression_strength_mckee)
    var _acc_stacking_load: Float64 = 0.0
    var _t0_stacking_load = perf_counter_ns()
    for _ in range(N):
        _acc_stacking_load += stacking_load(0.5, 0.5)
    var _t1_stacking_load = perf_counter_ns()
    var _ns_stacking_load = Float64(_t1_stacking_load - _t0_stacking_load) / Float64(N)
    print("MOJO_TIMING packaging::stacking_load", _ns_stacking_load, _acc_stacking_load)
    var _acc_cushion_curve_g: Float64 = 0.0
    var _t0_cushion_curve_g = perf_counter_ns()
    for _ in range(N):
        _acc_cushion_curve_g += cushion_curve_g(0.5, 0.5, 0.5)
    var _t1_cushion_curve_g = perf_counter_ns()
    var _ns_cushion_curve_g = Float64(_t1_cushion_curve_g - _t0_cushion_curve_g) / Float64(N)
    print("MOJO_TIMING packaging::cushion_curve_g", _ns_cushion_curve_g, _acc_cushion_curve_g)
    var _acc_pallet_efficiency: Float64 = 0.0
    var _t0_pallet_efficiency = perf_counter_ns()
    for _ in range(N):
        _acc_pallet_efficiency += pallet_efficiency(0.5, 0.5, 0.5)
    var _t1_pallet_efficiency = perf_counter_ns()
    var _ns_pallet_efficiency = Float64(_t1_pallet_efficiency - _t0_pallet_efficiency) / Float64(N)
    print("MOJO_TIMING packaging::pallet_efficiency", _ns_pallet_efficiency, _acc_pallet_efficiency)
    var _acc_fill_percentage: Float64 = 0.0
    var _t0_fill_percentage = perf_counter_ns()
    for _ in range(N):
        _acc_fill_percentage += fill_percentage(0.5, 0.5)
    var _t1_fill_percentage = perf_counter_ns()
    var _ns_fill_percentage = Float64(_t1_fill_percentage - _t0_fill_percentage) / Float64(N)
    print("MOJO_TIMING packaging::fill_percentage", _ns_fill_percentage, _acc_fill_percentage)
    var _acc_shelf_life_arrhenius: Float64 = 0.0
    var _t0_shelf_life_arrhenius = perf_counter_ns()
    for _ in range(N):
        _acc_shelf_life_arrhenius += shelf_life_arrhenius(0.5, 0.5, 0.5, 0.5)
    var _t1_shelf_life_arrhenius = perf_counter_ns()
    var _ns_shelf_life_arrhenius = Float64(_t1_shelf_life_arrhenius - _t0_shelf_life_arrhenius) / Float64(N)
    print("MOJO_TIMING packaging::shelf_life_arrhenius", _ns_shelf_life_arrhenius, _acc_shelf_life_arrhenius)
    var _acc_dimensional_weight: Float64 = 0.0
    var _t0_dimensional_weight = perf_counter_ns()
    for _ in range(N):
        _acc_dimensional_weight += dimensional_weight(0.5, 0.5, 0.5, 0.5)
    var _t1_dimensional_weight = perf_counter_ns()
    var _ns_dimensional_weight = Float64(_t1_dimensional_weight - _t0_dimensional_weight) / Float64(N)
    print("MOJO_TIMING packaging::dimensional_weight", _ns_dimensional_weight, _acc_dimensional_weight)
