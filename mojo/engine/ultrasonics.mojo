"""
ultrasonics.mojo — Ultrasound physics and medical imaging calculations. Zero Python imports.

Public API:
  acoustic_impedance           — Z = ρ * c
  reflection_coefficient       — R = (Z2 - Z1)² / (Z2 + Z1)²
  attenuation_loss             — loss in dB from distance and coefficient
  doppler_frequency_shift      — Δf from velocity and angle
  pulse_repetition_frequency   — PRF from max depth
  axial_resolution             — res = c / (2 * BW)
  lateral_resolution           — approximation from frequency and aperture
  acoustic_pressure_spl        — SPL in water from pressure
  ultrasound_power             — P = I * A
  thermal_index                — TI from acoustic power and absorption
"""
from std.math import cos, sqrt, log, pow


fn _log10(x: Float64) -> Float64:
    return log(x) / log(10.0)


fn acoustic_impedance(density: Float64, sound_speed: Float64) -> Float64:
    """Acoustic impedance: Z = ρ·c.

    Args:
        density: Medium density (kg/m³).
        sound_speed: Speed of sound in medium (m/s).

    Returns:
        Acoustic impedance (Pa·s/m = Rayl).
    """
    return density * sound_speed


fn reflection_coefficient(z1: Float64, z2: Float64) -> Float64:
    """Intensity reflection coefficient at an interface.

    R = ((Z2 - Z1) / (Z2 + Z1))²

    Args:
        z1: Acoustic impedance of medium 1 (Rayl).
        z2: Acoustic impedance of medium 2 (Rayl).

    Returns:
        Intensity reflection coefficient (0–1).
    """
    var denom = z2 + z1
    if denom <= 0.0:
        return 0.0
    var ratio = (z2 - z1) / denom
    return ratio * ratio


fn attenuation_loss(
    attenuation_coeff: Float64, frequency_mhz: Float64, distance_cm: Float64
) -> Float64:
    """Attenuation in soft tissue: loss = α·f·d (dB).

    Args:
        attenuation_coeff: Attenuation coefficient α (dB/cm/MHz).
        frequency_mhz: Frequency (MHz).
        distance_cm: Path length (cm).

    Returns:
        Signal loss (dB).
    """
    return attenuation_coeff * frequency_mhz * distance_cm


fn doppler_frequency_shift(
    source_freq_mhz: Float64, velocity: Float64,
    angle_rad: Float64, sound_speed: Float64
) -> Float64:
    """Doppler shift: Δf = 2·f·v·cos(θ) / c.

    Args:
        source_freq_mhz: Transducer frequency (MHz).
        velocity: Blood flow velocity (m/s).
        angle_rad: Angle between beam and flow (rad).
        sound_speed: Speed of sound (m/s, ~1540 in tissue).

    Returns:
        Doppler frequency shift (MHz).
    """
    return 2.0 * source_freq_mhz * velocity * cos(angle_rad) / sound_speed


fn pulse_repetition_frequency(max_depth_cm: Float64, sound_speed: Float64) -> Float64:
    """Maximum PRF determined by imaging depth.

    PRF_max = c / (2 · d_max)

    Args:
        max_depth_cm: Maximum imaging depth (cm).
        sound_speed: Sound speed in tissue (m/s).

    Returns:
        Maximum PRF (Hz).
    """
    if max_depth_cm <= 0.0:
        return 0.0
    var d_m = max_depth_cm / 100.0
    return sound_speed / (2.0 * d_m)


fn axial_resolution(sound_speed: Float64, bandwidth_hz: Float64) -> Float64:
    """Axial (depth) resolution: res_ax = c / (2 · BW).

    Args:
        sound_speed: Sound speed (m/s).
        bandwidth_hz: Pulse bandwidth (Hz).

    Returns:
        Axial resolution (m).
    """
    if bandwidth_hz <= 0.0:
        return 0.0
    return sound_speed / (2.0 * bandwidth_hz)


fn lateral_resolution(
    wavelength_m: Float64, focal_depth_m: Float64, aperture_m: Float64
) -> Float64:
    """Lateral resolution at focal depth.

    res_lat ≈ λ · F / D  (F-number × λ)

    Args:
        wavelength_m: Acoustic wavelength (m).
        focal_depth_m: Focal distance (m).
        aperture_m: Transducer aperture (m).

    Returns:
        Lateral resolution (m).
    """
    if aperture_m <= 0.0:
        return 0.0
    return wavelength_m * focal_depth_m / aperture_m


fn acoustic_pressure_spl(pressure_pa: Float64) -> Float64:
    """Sound pressure level in water.

    SPL = 20·log10(p / p_ref)  with p_ref = 1 μPa in water.

    Args:
        pressure_pa: RMS acoustic pressure (Pa).

    Returns:
        SPL (dB re 1 μPa).
    """
    if pressure_pa <= 0.0:
        return 0.0
    var p_ref = 1e-6  # 1 μPa
    return 20.0 * _log10(pressure_pa / p_ref)


fn ultrasound_power(intensity: Float64, area: Float64) -> Float64:
    """Acoustic power: P = I × A.

    Args:
        intensity: Spatial-average temporal-average intensity (W/m²).
        area: Transducer aperture area (m²).

    Returns:
        Total acoustic power (W).
    """
    return intensity * area


fn thermal_index(
    acoustic_power_w: Float64, frequency_mhz: Float64, attenuation_coeff: Float64
) -> Float64:
    """Soft-tissue Thermal Index (simplified, TIS).

    TIS ≈ P · f · α / 210

    Args:
        acoustic_power_w: Acoustic output power (W).
        frequency_mhz: Frequency (MHz).
        attenuation_coeff: Attenuation (dB/cm/MHz).

    Returns:
        Thermal index TI (dimensionless; TI ≤ 1 for diagnostic use).
    """
    return acoustic_power_w * frequency_mhz * attenuation_coeff / 210.0
