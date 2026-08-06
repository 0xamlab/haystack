"""
telecommunications.mojo — Telecommunications Library. Zero Python imports.

Provides Shannon capacity, Erlang-B blocking, BER estimation, spectral
efficiency, link margin, thermal noise, SNR conversions, Nyquist data rate,
propagation delay, throughput, and availability calculations.

Public API:
  shannon_capacity        — Channel capacity C = B*log2(1+SNR)
  erlang_b                — Blocking probability (small N)
  bit_error_rate_bpsk     — BER ≈ 0.5*exp(-SNR) simplified
  spectral_efficiency     — η = R/B (bits/s/Hz)
  link_margin             — Margin = Prx - sensitivity (dB)
  thermal_noise_power     — N = kTB
  signal_to_noise_ratio   — SNR = S/N
  snr_db                  — SNR_dB = 10*log10(SNR)
  data_rate_nyquist       — R = 2*B*log2(M)
  propagation_delay       — delay = d/v
  throughput              — T = bits/time
  availability_percentage — A = uptime/total * 100
"""
from std.math import log, exp


# ── Helpers ───────────────────────────────────────────────────────────────────


def _log2(x: Float64) -> Float64:
    return log(x) / log(2.0)


def _log10(x: Float64) -> Float64:
    return log(x) / log(10.0)


def _factorial(n: Int) -> Float64:
    var result: Float64 = 1.0
    for i in range(1, n + 1):
        result *= Float64(i)
    return result


# ── Channel capacity ─────────────────────────────────────────────────────────


def shannon_capacity(bandwidth: Float64, snr: Float64) -> Float64:
    """Shannon channel capacity: C = B * log2(1 + SNR) bits/s."""
    if bandwidth <= 0.0:
        return 0.0
    return bandwidth * _log2(1.0 + snr)


# ── Erlang B ──────────────────────────────────────────────────────────────────


def erlang_b(n: Int, a: Float64) -> Float64:
    """Erlang-B blocking probability: A^N/N! / Σ(A^k/k!, k=0..N).

    Simplified iterative computation suitable for small N.
    """
    if n < 0:
        return 0.0
    var inv_b: Float64 = 1.0
    for i in range(1, n + 1):
        inv_b = 1.0 + inv_b * Float64(i) / a
    return 1.0 / inv_b


# ── Bit error rate ────────────────────────────────────────────────────────────


def bit_error_rate_bpsk(snr_linear: Float64) -> Float64:
    """BER for BPSK (simplified): BER ≈ 0.5 * exp(-SNR)."""
    if snr_linear < 0.0:
        return 0.5
    return 0.5 * exp(-snr_linear)


# ── Spectral efficiency ──────────────────────────────────────────────────────


def spectral_efficiency(data_rate: Float64, bandwidth: Float64) -> Float64:
    """Spectral efficiency η = R / B  (bits/s/Hz)."""
    if bandwidth <= 0.0:
        return 0.0
    return data_rate / bandwidth


# ── Link margin ──────────────────────────────────────────────────────────────


def link_margin(rx_power: Float64, rx_sensitivity: Float64) -> Float64:
    """Link margin = received power - receiver sensitivity (dB)."""
    return rx_power - rx_sensitivity


# ── Thermal noise ─────────────────────────────────────────────────────────────


def thermal_noise_power(bandwidth: Float64, temperature: Float64) -> Float64:
    """Thermal noise power N = k * T * B  (watts).

    k = 1.38e-23 J/K (Boltzmann constant).
    """
    comptime k: Float64 = 1.38e-23
    return k * temperature * bandwidth


# ── SNR ───────────────────────────────────────────────────────────────────────


def signal_to_noise_ratio(signal_power: Float64, noise_power: Float64) -> Float64:
    """Signal-to-noise ratio SNR = S / N."""
    if noise_power <= 0.0:
        return 0.0
    return signal_power / noise_power


def snr_db(snr_linear: Float64) -> Float64:
    """Convert linear SNR to dB: SNR_dB = 10 * log10(SNR)."""
    if snr_linear <= 0.0:
        return 0.0
    return 10.0 * _log10(snr_linear)


# ── Nyquist data rate ─────────────────────────────────────────────────────────


def data_rate_nyquist(bandwidth: Float64, levels: Float64) -> Float64:
    """Nyquist data rate: R = 2 * B * log2(M) bits/s."""
    if bandwidth <= 0.0 or levels <= 1.0:
        return 0.0
    return 2.0 * bandwidth * _log2(levels)


# ── Propagation & throughput ──────────────────────────────────────────────────


def propagation_delay(distance: Float64, speed: Float64) -> Float64:
    """Propagation delay = distance / speed (seconds)."""
    if speed <= 0.0:
        return 0.0
    return distance / speed


def throughput(data_bits: Float64, total_time: Float64) -> Float64:
    """Throughput T = data_bits / total_time (bits/s)."""
    if total_time <= 0.0:
        return 0.0
    return data_bits / total_time


def availability_percentage(uptime: Float64, total_time: Float64) -> Float64:
    """Availability A = uptime / total_time * 100 (%)."""
    if total_time <= 0.0:
        return 0.0
    return uptime / total_time * 100.0
