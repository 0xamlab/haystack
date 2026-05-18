"""Spectroscopy Library — wavenumber, absorbance, Beer-Lambert, Raman shift."""

from std.math import sqrt, log, exp, abs


fn wavenumber_from_wavelength(wavelength_um: Float64) -> Float64:
    """nu = 10000 / lambda (cm^-1)."""
    if wavelength_um == 0.0:
        return 0.0
    return 10000.0 / wavelength_um


fn wavelength_from_wavenumber(wavenumber_cm: Float64) -> Float64:
    """lambda = 10000 / nu (um)."""
    if wavenumber_cm == 0.0:
        return 0.0
    return 10000.0 / wavenumber_cm


fn energy_from_wavelength(wavelength_m: Float64) -> Float64:
    """E = hc / lambda (J). h=6.626e-34, c=3e8."""
    if wavelength_m == 0.0:
        return 0.0
    comptime h: Float64 = 6.626e-34
    comptime c: Float64 = 3.0e8
    return h * c / wavelength_m


fn absorbance_from_transmittance(transmittance_pct: Float64) -> Float64:
    """A = -log10(T/100). log10(x) = log(x)/log(10)."""
    if transmittance_pct <= 0.0:
        return 0.0
    var t_frac = transmittance_pct / 100.0
    return -(log(t_frac) / log(10.0))


fn transmittance_from_absorbance(absorbance: Float64) -> Float64:
    """T = 10^(-A) * 100. 10^x = exp(x*ln10)."""
    var ln10 = log(10.0)
    return exp(-absorbance * ln10) * 100.0


fn beer_lambert_concentration(
    absorbance: Float64, path_length: Float64, molar_absorptivity: Float64
) -> Float64:
    """c = A / (epsilon * l)."""
    var denom = molar_absorptivity * path_length
    if denom == 0.0:
        return 0.0
    return absorbance / denom


fn resolution_spectrometer(wavelength: Float64, delta_wavelength: Float64) -> Float64:
    """R = lambda / delta_lambda."""
    if delta_wavelength == 0.0:
        return 0.0
    return wavelength / delta_wavelength


fn snr_coadd(snr_single: Float64, n_scans: Float64) -> Float64:
    """SNR = snr_single * sqrt(n_scans)."""
    return snr_single * sqrt(n_scans)


fn raman_shift(excitation_nm: Float64, scattered_nm: Float64) -> Float64:
    """Delta_nu = (1/lambda_ex - 1/lambda_sc) * 1e7 (cm^-1)."""
    if excitation_nm == 0.0 or scattered_nm == 0.0:
        return 0.0
    return (1.0 / excitation_nm - 1.0 / scattered_nm) * 1.0e7


fn fluorescence_quantum_yield(
    photons_emitted: Float64, photons_absorbed: Float64
) -> Float64:
    """QY = emitted / absorbed."""
    if photons_absorbed == 0.0:
        return 0.0
    return photons_emitted / photons_absorbed


fn stokes_shift(excitation_nm: Float64, emission_nm: Float64) -> Float64:
    """Shift = emission - excitation (nm)."""
    return emission_nm - excitation_nm


fn spectral_bandwidth(fwhm: Float64) -> Float64:
    """Returns FWHM directly (nm)."""
    return fwhm
