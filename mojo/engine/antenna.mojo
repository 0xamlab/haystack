"""
antenna.mojo — Antenna Engineering Library. Zero Python imports.

Pure Mojo implementations of fundamental antenna and RF link-budget
equations including dipole sizing, Friis path loss, EIRP, directivity,
effective aperture, noise figure conversion, and beamwidth estimation.

Public API:
  dipole_length              — half-wave dipole length L = λ/2
  wavelength_from_freq       — λ = c / f
  friis_path_loss            — free-space path loss in dB
  eirp                       — effective isotropic radiated power (dBm)
  received_power             — Prx = EIRP - PL + Grx
  directivity_from_beamwidths — D ≈ 41253 / (θ_E * φ_E)
  antenna_efficiency         — η = G / D
  effective_aperture         — Ae = G * λ² / (4π)
  link_budget_margin         — margin = Prx - sensitivity
  noise_figure_to_noise_temp — Te = T0 * (10^(NF/10) - 1)
  free_space_loss_db         — FSL = 32.45 + 20*log10(d) + 20*log10(f)
  beamwidth_from_aperture    — θ ≈ 70 * λ / D
"""
from std.math import sqrt, exp, log, abs as fabs

comptime PI: Float64 = 3.141592653589793


# ── helpers ──────────────────────────────────────────────────────────────────


def _log10(x: Float64) -> Float64:
    return log(x) / log(10.0)


# ── dipole_length ────────────────────────────────────────────────────────────


def dipole_length(wavelength: Float64) -> Float64:
    """Half-wave dipole length: L = λ / 2 (metres)."""
    return wavelength / 2.0


# ── wavelength_from_freq ─────────────────────────────────────────────────────


def wavelength_from_freq(frequency: Float64, c: Float64 = 3.0e8) -> Float64:
    """Wavelength from frequency: λ = c / f (metres)."""
    return c / frequency


# ── friis_path_loss ──────────────────────────────────────────────────────────


def friis_path_loss(distance: Float64, wavelength: Float64) -> Float64:
    """Friis free-space path loss in dB: 20*log10(4π*d / λ)."""
    var ratio = 4.0 * PI * distance / wavelength
    return 20.0 * _log10(ratio)


# ── eirp ─────────────────────────────────────────────────────────────────────


def eirp(tx_power_dbm: Float64, antenna_gain_dbi: Float64) -> Float64:
    """EIRP = Ptx + Gant (dBm)."""
    return tx_power_dbm + antenna_gain_dbi


# ── received_power ───────────────────────────────────────────────────────────


def received_power(eirp_dbm: Float64, path_loss_db: Float64, rx_gain_dbi: Float64) -> Float64:
    """Prx = EIRP - PL + Grx (dBm)."""
    return eirp_dbm - path_loss_db + rx_gain_dbi


# ── directivity_from_beamwidths ─────────────────────────────────────────────


def directivity_from_beamwidths(theta_e: Float64, phi_e: Float64) -> Float64:
    """Directivity ≈ 41253 / (θ_E * φ_E) where angles are in degrees."""
    return 41253.0 / (theta_e * phi_e)


# ── antenna_efficiency ───────────────────────────────────────────────────────


def antenna_efficiency(gain: Float64, directivity: Float64) -> Float64:
    """Antenna efficiency η = G / D (linear scale)."""
    return gain / directivity


# ── effective_aperture ───────────────────────────────────────────────────────


def effective_aperture(gain: Float64, wavelength: Float64) -> Float64:
    """Effective aperture: Ae = G * λ² / (4π) (m²)."""
    return gain * wavelength * wavelength / (4.0 * PI)


# ── link_budget_margin ───────────────────────────────────────────────────────


def link_budget_margin(rx_power: Float64, rx_sensitivity: Float64) -> Float64:
    """Link budget margin = Prx - sensitivity (dB)."""
    return rx_power - rx_sensitivity


# ── noise_figure_to_noise_temp ───────────────────────────────────────────────


def noise_figure_to_noise_temp(nf_db: Float64, t0: Float64 = 290.0) -> Float64:
    """Equivalent noise temperature: Te = T0 * (10^(NF/10) - 1) (Kelvin)."""
    var factor = exp(nf_db / 10.0 * log(10.0))
    return t0 * (factor - 1.0)


# ── free_space_loss_db ───────────────────────────────────────────────────────


def free_space_loss_db(distance_km: Float64, freq_mhz: Float64) -> Float64:
    """Free-space loss: FSL = 32.45 + 20*log10(d_km) + 20*log10(f_MHz) (dB)."""
    return 32.45 + 20.0 * _log10(distance_km) + 20.0 * _log10(freq_mhz)


# ── beamwidth_from_aperture ─────────────────────────────────────────────────


def beamwidth_from_aperture(wavelength: Float64, aperture_dim: Float64) -> Float64:
    """Approximate half-power beamwidth: θ ≈ 70 * λ / D (degrees)."""
    return 70.0 * wavelength / aperture_dim
