"""
neurophysics.mojo — Biophysics of neurons and neural signals. Zero Python imports.

Public API:
  nernst_potential             — reversal potential for single ion
  goldman_equation             — resting membrane potential (GHK)
  membrane_time_constant       — τ = Rm * Cm
  cable_length_constant        — λ = sqrt(Rm/Ri) (passive dendrite)
  action_potential_threshold   — Iθ = (Vm_threshold - Vrest) / Rm
  firing_rate_simple           — rate = 1 / (refractory + integration_time)
  synaptic_current             — I_syn = g_syn * (Vm - E_syn)
  integrate_and_fire_voltage   — sub-threshold V(t) = Vrest + IR*(1-exp(-t/τ))
  eeg_spectral_power           — 1/f^β power for neural oscillations
  conduction_velocity          — v = d_axon^0.5 * 5.5 m/s (myelinated estimate)
"""
from std.math import sqrt, exp, log, pow


def nernst_potential(
    z: Float64, conc_outside: Float64, conc_inside: Float64, temperature: Float64
) -> Float64:
    """Nernst equation: reversal potential for a single ion.

    E = (RT/zF) · ln([X]out / [X]in)

    Args:
        z: Ion valence (e.g. +1 for K+, -1 for Cl-).
        conc_outside: Extracellular ion concentration (mM).
        conc_inside: Intracellular ion concentration (mM).
        temperature: Temperature (K).

    Returns:
        Nernst potential (mV).
    """
    if conc_inside <= 0.0 or conc_outside <= 0.0 or z == 0.0:
        return 0.0
    var R = 8.314
    var F = 96485.0
    return (R * temperature / (z * F)) * log(conc_outside / conc_inside) * 1000.0


def goldman_equation(
    pk: Float64, pna: Float64, pcl: Float64,
    k_out: Float64, na_out: Float64, cl_in: Float64,
    k_in: Float64, na_in: Float64, cl_out: Float64
) -> Float64:
    """Goldman-Hodgkin-Katz resting potential.

    Vm = (RT/F)·ln((Pk·[K+]o + PNa·[Na+]o + PCl·[Cl-]i)
                   / (Pk·[K+]i + PNa·[Na+]i + PCl·[Cl-]o))

    Args:
        pk, pna, pcl: Relative permeabilities.
        k_out, na_out, cl_in: Extracellular K+, Na+ and intracellular Cl- (mM).
        k_in, na_in, cl_out: Intracellular K+, Na+ and extracellular Cl- (mM).

    Returns:
        Resting membrane potential (mV).
    """
    var num = pk * k_out + pna * na_out + pcl * cl_in
    var den = pk * k_in  + pna * na_in  + pcl * cl_out
    if num <= 0.0 or den <= 0.0:
        return 0.0
    var R = 8.314; var T = 310.15; var F = 96485.0
    return (R * T / F) * log(num / den) * 1000.0


def membrane_time_constant(r_membrane: Float64, c_membrane: Float64) -> Float64:
    """Membrane time constant: τm = Rm·Cm.

    Args:
        r_membrane: Membrane resistance (Ω·cm²).
        c_membrane: Membrane capacitance (μF/cm²).

    Returns:
        Time constant (ms).
    """
    if r_membrane < 0.0 or c_membrane < 0.0:
        return 0.0
    return r_membrane * c_membrane / 1000.0  # to ms (if Rm in Ω·cm², Cm in μF/cm²)


def cable_length_constant(r_membrane: Float64, r_internal: Float64) -> Float64:
    """Dendritic cable length constant: λ = sqrt(Rm/Ri).

    Args:
        r_membrane: Membrane resistance per unit length (Ω·cm).
        r_internal: Internal resistance per unit length (Ω/cm).

    Returns:
        Length constant (cm).
    """
    if r_internal <= 0.0 or r_membrane < 0.0:
        return 0.0
    return sqrt(r_membrane / r_internal)


def action_potential_threshold(
    v_threshold: Float64, v_rest: Float64, r_input: Float64
) -> Float64:
    """Minimum current to reach action potential threshold.

    Iθ = (Vθ - Vrest) / Rin

    Args:
        v_threshold: Threshold membrane potential (mV).
        v_rest: Resting potential (mV).
        r_input: Input resistance (MΩ).

    Returns:
        Threshold current (nA).
    """
    if r_input <= 0.0:
        return 0.0
    return (v_threshold - v_rest) / r_input


def firing_rate_simple(
    refractory_ms: Float64, integration_time_ms: Float64
) -> Float64:
    """Maximum firing rate from refractory period.

    rate = 1000 / (t_ref + t_int)

    Args:
        refractory_ms: Absolute refractory period (ms).
        integration_time_ms: Time to threshold from rest (ms).

    Returns:
        Maximum firing rate (Hz).
    """
    var total = refractory_ms + integration_time_ms
    if total <= 0.0:
        return 0.0
    return 1000.0 / total


def synaptic_current(
    conductance: Float64, v_membrane: Float64, e_synapse: Float64
) -> Float64:
    """Synaptic current: I_syn = g·(Vm - Esyn).

    Args:
        conductance: Synaptic conductance (nS).
        v_membrane: Membrane potential (mV).
        e_synapse: Synaptic reversal potential (mV).

    Returns:
        Synaptic current (pA).
    """
    return conductance * (v_membrane - e_synapse)


def integrate_and_fire_voltage(
    v_rest: Float64, i_input: Float64, r_input: Float64,
    tau: Float64, time: Float64
) -> Float64:
    """Sub-threshold voltage in leaky integrate-and-fire model.

    V(t) = Vrest + I·Rin·(1 - exp(-t/τ))

    Args:
        v_rest: Resting potential (mV).
        i_input: Injected current (nA).
        r_input: Input resistance (MΩ).
        tau: Membrane time constant (ms).
        time: Time since step onset (ms).

    Returns:
        Membrane voltage V(t) (mV).
    """
    if tau <= 0.0:
        return v_rest
    return v_rest + i_input * r_input * (1.0 - exp(-time / tau))


def eeg_spectral_power(frequency: Float64, beta: Float64) -> Float64:
    """Power spectral density following 1/f^β law.

    Args:
        frequency: Frequency (Hz).
        beta: Spectral exponent (typically 1–3 for EEG).

    Returns:
        Relative power (arbitrary units).
    """
    if frequency <= 0.0:
        return 0.0
    return 1.0 / pow(frequency, beta)


def conduction_velocity(axon_diameter_um: Float64) -> Float64:
    """Myelinated axon conduction velocity estimate.

    v ≈ 5.5 · √(d_axon)

    Args:
        axon_diameter_um: Axon outer diameter including myelin (μm).

    Returns:
        Conduction velocity (m/s).
    """
    if axon_diameter_um <= 0.0:
        return 0.0
    return 5.5 * sqrt(axon_diameter_um)
