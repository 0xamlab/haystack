---
icon: atom
description: Nanoscale surface/transport physics, plasma and fusion parameters, dry and lubricated contact mechanics with wear-corrosion coupling, and antenna/RF link-budget equations across five independent kernel modules.
---

# Nanoscale physics, plasma, and surface-contact engineering kernels

Five modules for five formula-driven domains that share no code with each other: nanoscale surface,
transport and colloidal physics (`nanotechnology`); plasma and fusion parameters (`plasma_physics`);
dry and lubricated contact mechanics (`tribology`); a second, overlapping contact-mechanics module
with two genuinely chemical additions (`tribochemistry`); and antenna sizing plus RF link budgets
(`antenna`). Every function is a single closed-form equation — no iteration, no fitting, no Python —
taking plain `Float64` scalars in SI or the field's conventional units (eV for plasma temperatures,
dB/dBm/dBi for RF) and returning one `Float64` back.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# Two independent derivations of free-space path loss for the same 2.4 GHz link at 10 m.
wl = runtime.execute("antenna", "wavelength_from_freq", [2.4e9, 3.0e8])["result"]
wl   # 0.125 m

runtime.execute("antenna", "friis_path_loss", [10.0, wl])["result"]
# 60.0459970202808 dB -- 20*log10(4*pi*d/lambda)

runtime.execute("antenna", "free_space_loss_db", [0.01, 2400.0])["result"]
# 60.054224834232116 dB -- 32.45 + 20*log10(d_km) + 20*log10(f_MHz), same 10 m / 2.4 GHz link

# Same physics, two different closed-form parameterizations of the same constant --
# they agree to within 0.01 dB, the residual coming from the fixed c and rounded
# constant each formula bakes in.
```

## The modules

| Module | What it does |
| --- | --- |
| `nanotechnology` | Sphere geometry at the nanoscale (surface area, volume, surface-to-volume ratio, specific surface area), particle-in-a-box quantum confinement energy, gas-kinetic mean free path and Knudsen number, sphere-flat van der Waals force, Stokes-Einstein diffusion, Smoluchowski zeta-potential mobility, nanorod/nanotube aspect ratio, and the exact FCC sphere-packing fraction. |
| `plasma_physics` | Debye length, electron plasma frequency, thermal velocity, Larmor (gyro) radius, Coulomb logarithm, Spitzer resistivity, Alfvén speed, MHD beta, the Lawson nτ ignition criterion, and Bremsstrahlung radiated power density. |
| `tribology` | Coulomb/kinetic/static friction force, coefficient of friction, Hertz contact pressure, Archard wear volume, bearing pressure, Sommerfeld number, Stribeck parameter, flash temperature rise, a proportional EHD film-thickness estimate, and friction power loss. |
| `tribochemistry` | A second Hertz-contact and Archard-wear implementation (contact radius from force, max pressure, wear rate, wear volume, flash temperature), the Hamrock-Dowson EHD film thickness and lambda ratio, plus two functions with no `tribology` counterpart: work of adhesion from surface energy, and a wear-corrosion tribocorrosion synergy rate. |
| `antenna` | Half-wave dipole length, wavelength from frequency, Friis and ITU-form free-space path loss, EIRP, received power, directivity from beamwidths, antenna efficiency, effective aperture, link-budget margin, noise-figure-to-noise-temperature conversion, and aperture-based beamwidth estimation. |

## Nanoscale physics: sizes, transport, and colloidal forces

`nanotechnology.mojo` has no guard clauses anywhere in the file — every function is one line of
direct arithmetic on the formula in its docstring. The worked examples below are hand-computed from
those formulas (not the module's own smoke test, which only checks finiteness — see
[Verification](#verification)) and checked against known real-world reference values where one
exists.

```python
runtime.execute("nanotechnology", "packing_fraction_fcc", [])["result"]
# 0.740480489693061 -- pi*sqrt(2)/6, the exact maximum sphere-packing density
# (Kepler's conjecture, proved 2017) -- not an approximation
```

A 5 nm-radius sphere (roughly a CdSe quantum dot or a small gold nanoparticle):

```python
runtime.execute("nanotechnology", "nanoparticle_volume", [5e-9])["result"]
# 5.235987755982989e-25 m^3
runtime.execute("nanotechnology", "nanoparticle_surface_area", [5e-9])["result"]
# 3.1415926535897933e-16 m^2
runtime.execute("nanotechnology", "surface_to_volume_sphere", [5e-9])["result"]
# 600000000.0 m^-1 -- 3/r; a 500 nm sphere would be 100x smaller, the reason
# nanoparticles dominate surface-driven behavior (catalysis, adsorption) that
# bulk material of the same composition does not show
```

For a gold sphere that size (density 19,300 kg/m³, mass ≈1.0105e-20 kg), specific surface area
(`SA / mass`) comes out to **31.09 m²/g** — the right order of magnitude for real engineered
nanoparticle powders, which are typically quoted in the tens of m²/g.

**Quantum confinement.** A particle-in-a-box estimate for a 5 nm CdSe dot (electron effective mass
≈0.13·mₑ, mₑ = 9.1093837015e-31 kg, h = 6.62607015e-34 J·s):

```python
runtime.execute("nanotechnology", "quantum_confinement_energy",
                [6.62607015e-34, 0.13 * 9.1093837015e-31, 5e-9])["result"]
# 1.8537438160730985e-20 J = 0.1157 eV
```

Real CdSe quantum dots at this size show confinement shifts in the tenths-of-an-eV range, so the
formula's magnitude is physically sensible even though it is the textbook infinite-square-well
approximation, not the finite-well or effective-mass-mismatch correction a real optical-properties
calculation would add.

**Mean free path and the Knudsen number.** Nitrogen at STP (T = 298.15 K, collision diameter
d ≈ 3.7e-10 m, P = 101,325 Pa):

```python
mfp = runtime.execute("nanotechnology", "mean_free_path",
                       [1.380649e-23, 298.15, 3.7e-10, 101325.0])["result"]
mfp   # 6.679334067503744e-08 m = 66.8 nm -- matches the commonly cited ~68 nm
      # mean free path of air at STP to within the collision-diameter estimate used

runtime.execute("nanotechnology", "knudsen_number", [mfp, 100e-9])["result"]
# 0.6679334067503744 -- for a 100 nm pore, Kn ~0.1-10 is the transition-flow
# regime: neither continuum (Kn << 1) nor free-molecular (Kn >> 1) flow applies
```

**Van der Waals force and Stokes-Einstein diffusion.** A 50 nm sphere at 0.3 nm separation from a
flat surface (Hamaker constant 1e-19 J, a typical condensed-matter value) feels
`van_der_waals_force` = **9.259e-9 N**. The same particle diffusing in water at 298 K
(η = 8.9e-4 Pa·s) has `diffusion_coefficient_stokes_einstein` = **4.907e-11 m²/s** — the right order
of magnitude for nanoparticle tracking measurements at this size and viscosity.

**Zeta potential.** Given an electrophoretic mobility of 1e-8 m²/(V·s) in water (η = 8.9e-4 Pa·s,
ε = 80·ε₀ = 7.0832e-10 F/m), `zeta_potential_mobility` (the Smoluchowski relation η·μ/ε) returns
**0.01256 V ≈ 12.6 mV**, inside the ±10-100 mV range real colloidal suspensions typically show.

## Plasma and fusion parameters

`plasma_physics.mojo` is the opposite of `nanotechnology.mojo` in posture: every function that
divides by a physical quantity guards it first and returns `0.0` (or, for `coulomb_logarithm`,
a documented fallback of `10.0`) rather than letting a non-positive temperature or density produce
`inf`/`NaN`. Only `fusion_lawson_criterion` has no guard, because it is a plain product with no
division to protect.

The worked examples use tokamak-core-scale parameters — T = 10 keV (1e4 eV), n = 1e20 m⁻³, and a
5.3 T field (ITER's design-scale toroidal field, used here only to pick a realistic magnitude, not
to claim these are ITER's published operating numbers):

```python
runtime.execute("plasma_physics", "debye_length", [1e4, 1e20])["result"]
# 7.43427296256316e-05 m -- ~74 micrometers, the right order for a tokamak core

runtime.execute("plasma_physics", "plasma_frequency", [1e20])["result"]
# 564101691367.8705 rad/s
```

That plasma frequency is independently checkable: the NRL Plasma Formulary's textbook constant is
ω_pe ≈ 5.64e4 · √(n[cm⁻³]) rad/s. At n = 1e20 m⁻³ = 1e14 cm⁻³, that gives
`5.64e4 * sqrt(1e14)` = **5.64e11 rad/s**, matching the kernel's 5.641e11 to 4 significant figures.

```python
# Larmor radius, electron vs. deuteron, both at their own thermal velocity in a 5.3 T field
v_th_e = runtime.execute("plasma_physics", "thermal_velocity", [1e4, 9.109e-31])["result"]
v_th_e   # 41936859.52 m/s
runtime.execute("plasma_physics", "larmor_radius", [9.109e-31, v_th_e, 1.602e-19, 5.3])["result"]
# 4.499126721226822e-05 m -- ~45 micrometers

v_th_d = runtime.execute("plasma_physics", "thermal_velocity", [1e4, 3.344e-27])["result"]
v_th_d   # 692146.65 m/s
runtime.execute("plasma_physics", "larmor_radius", [3.344e-27, v_th_d, 1.602e-19, 5.3])["result"]
# 0.002726000988038259 m -- ~2.7 mm, ~60x the electron radius, tracking the
# ~60x lighter electron mass at similar B and comparable thermal energy
```

Electron and deuteron gyroradii differing by roughly the square root of their mass ratio at equal
temperature is the expected physical relationship, not a coincidence of the chosen numbers.

```python
runtime.execute("plasma_physics", "coulomb_logarithm", [1e4, 1e20])["result"]
# 17.092244721017863 -- inside the "typically 10-20" range the function's own docstring claims

runtime.execute("plasma_physics", "spitzer_resistivity", [1e4, 1.5])["result"]
# 1.17e-09 ohm.m -- lower than copper's ~1.7e-8 ohm.m at room temperature;
# a fusion-grade plasma is a better electrical conductor than copper

runtime.execute("plasma_physics", "mhd_beta", [1e20, 1e4, 5.3])["result"]
# 0.014333023851904594 -- beta << 1, the low-beta regime the docstring says
# corresponds to magnetic (not just thermal-pressure) confinement

runtime.execute("plasma_physics", "fusion_lawson_criterion", [1e20, 3.0])["result"]
# 3e+20 m^-3.s -- above the ~2e20 m^-3.s ignition threshold the source cites in
# its own docstring comment; n=1e20 held for 3 seconds clears that bar

runtime.execute("plasma_physics", "bremsstrahlung_power", [1e20, 1e20, 1e4, 1.0])["result"]
# 535000.0 W/m^3
```

## Two modules, one wear law: `tribology` and `tribochemistry`

The Archard wear equation (`V = k·F·d / H`) appears **three times** across these two modules:
`tribology.archard_wear_volume`, `tribochemistry.archard_wear_rate`, and
`tribochemistry.wear_volume` are all the same formula, byte-for-byte identical bodies apart from a
parameter name (`hardness` vs. `hardness_pa`). Two more formulas are duplicated once each:
`tribology.coefficient_of_friction` / `tribochemistry.friction_coefficient` (μ = Ff/Fn) and
`tribology.hertz_contact_pressure` / `tribochemistry.hertz_max_pressure` (p₀ = 3F/(2πa²)).

Two things differ between the twins, and both matter to a caller switching between the modules:

**Parameter order is not the same.** `tribology.archard_wear_volume(k, load, sliding_distance,
hardness)` takes load before distance; `tribochemistry.archard_wear_rate(wear_coefficient,
sliding_distance, normal_force, hardness)` and `wear_volume` take distance before load. The product
`load * distance` is commutative, so passing the same two numbers in the position the *other*
module expects still gives the right answer by accident — but passing genuinely different-valued
load and distance figures into the wrong module's argument order silently swaps them.

**Guard posture is opposite.** `tribology`'s functions have no guard clauses at all — dividing by a
zero `contact_radius`, `hardness`, or `normal_force` produces IEEE `inf`, not an error.
`tribochemistry`'s equivalents all guard: `hertz_max_pressure` returns `0.0` for
`contact_radius <= 0.0`, `archard_wear_rate` and `wear_volume` return `0.0` for `hardness <= 0.0`,
and `friction_coefficient` returns `0.0` for `normal_force <= 0.0`. Concretely:

```python
runtime.execute("tribology", "hertz_contact_pressure", [1000.0, 0.0])["result"]
# inf -- 3*1000/(2*pi*0.0^2), unguarded

runtime.execute("tribochemistry", "hertz_max_pressure", [1000.0, 0.0])["result"]
# 0.0 -- same formula, guarded
```

`tribochemistry` also adds two functions with no `tribology` equivalent, both of which are the
module's genuinely chemical content (see the note below): `surface_energy_work` (thermodynamic work
of adhesion, `W = 2γ`) and `tribocorrosion_rate` (wear-corrosion synergy). Water's surface tension
(γ = 72.8 mJ/m² at 20°C) gives a textbook cross-check:

```python
runtime.execute("tribochemistry", "surface_energy_work", [72.8])["result"]
# 145.6 -- the standard-reference work of cohesion of water, 2*72.8 mJ/m^2

runtime.execute("tribochemistry", "tribocorrosion_rate", [10.0, 5.0, 0.2])["result"]
# 18.0 -- (wear_rate + corrosion_rate) * (1 + synergy_factor); mechanical wear (10)
# plus chemical corrosion (5) plus a 20% mutual-acceleration term on top of both
```

`tribology`-only worked examples, all steel-on-steel dry-sliding order of magnitude:

```python
Ff = runtime.execute("tribology", "coulomb_friction_force", [0.3, 1000.0])["result"]
Ff   # 300.0 N

runtime.execute("tribology", "hertz_contact_pressure", [1000.0, 0.001])["result"]
# 477464829.27568597 Pa = 477 MPa -- a 1 mm Hertzian contact radius under 1 kN

runtime.execute("tribology", "sommerfeld_number", [0.05, 10.0, 1e6, 0.001])["result"]
# 0.5 -- (eta*N/P)/(c/r)^2 for a journal bearing

runtime.execute("tribology", "flash_temperature_rise", [0.3, 100.0, 1.0, 50.0, 0.001])["result"]
# 600.0 -- mu*F*v/(k*L)

runtime.execute("tribology", "friction_power_loss", [Ff, 1.0])["result"]
# 300.0 W
```

## A full antenna link budget

Chaining `antenna`'s functions end to end for a 2.4 GHz link over 1 km, 20 dBm transmit power, 6 dBi
transmit gain, 2 dBi receive gain, and an EIRP-referenced -85 dBm receiver sensitivity:

```python
wl = runtime.execute("antenna", "wavelength_from_freq", [2.4e9, 3.0e8])["result"]
wl   # 0.125 m
runtime.execute("antenna", "dipole_length", [wl])["result"]
# 0.0625 m -- a quarter-wave monopole would be half that again

pl = runtime.execute("antenna", "free_space_loss_db", [1.0, 2400.0])["result"]
pl   # 100.05422483423212 dB

e = runtime.execute("antenna", "eirp", [20.0, 6.0])["result"]
e   # 26.0 dBm

rx = runtime.execute("antenna", "received_power", [e, pl, 2.0])["result"]
rx   # -72.05422483423212 dBm

runtime.execute("antenna", "link_budget_margin", [rx, -85.0])["result"]
# 12.945775165767884 dB of headroom above the receiver's sensitivity floor

runtime.execute("antenna", "noise_figure_to_noise_temp", [3.0, 290.0])["result"]
# 288.62607134097505 K -- for a receiver front end with a 3 dB noise figure

D = runtime.execute("antenna", "directivity_from_beamwidths", [30.0, 30.0])["result"]
D   # 45.836666666666666 -- a 30x30 degree beam, from the 41253/(theta*phi) estimator
runtime.execute("antenna", "antenna_efficiency", [30.0, D])["result"]
# 0.6544978547014763 -- linear gain 30 against that directivity implies ~65% efficiency

runtime.execute("antenna", "effective_aperture", [1.0, wl])["result"]
# 0.0012433979929054324 m^2 -- G=1 (isotropic) recovers the textbook Ae = lambda^2/(4*pi)

runtime.execute("antenna", "beamwidth_from_aperture", [wl, 1.0])["result"]
# 8.75 degrees -- the 70*lambda/D rule of thumb for a 1 m aperture at 2.4 GHz
```

## Guard posture varies sharply by module

Reading all five `.mojo` files rather than assuming a shared convention turns up a clean, verifiable
split. Three modules never guard a division against a zero or negative input:
`nanotechnology`, `tribology`, and `antenna` contain no `if` statements at all — every formula is
computed directly, so a zero `radius`, `contact_radius`, `normal_force`, `frequency`, or
`aperture_dim` produces IEEE `inf`/`-inf`/`NaN` rather than a caught error or a sentinel value. Two
modules guard every function that divides: `plasma_physics` returns `0.0` (or `10.0` for
`coulomb_logarithm`) for a non-positive temperature, density, charge, or field; `tribochemistry`
returns `0.0` for a non-positive hardness, contact radius, effective modulus/radius, or roughness.
Neither posture is validated by the modules' own tests — the auto-generated smoke suites (see
[Verification](#verification)) call every function once with a fixed `0.5` for every argument, which
never crosses zero and so never exercises either the guarded or unguarded branch.

## A note on the name: `tribochemistry` is mostly a second contact-mechanics module

`tribochemistry.mojo`'s docstring calls it "Surface chemistry of sliding contacts," but eight of its
ten functions are contact-mechanics and wear formulas — three of them are literal duplicates of
`tribology` functions (above) and the rest (`hertz_contact_radius`, `flash_temperature`,
`film_thickness_ehd`, `lambda_ratio`) are Hertzian-contact and elastohydrodynamic-lubrication math
with no reaction chemistry in them. Real tribochemistry, as a field, is about the chemical
reactions a sliding contact drives — tribofilm formation, oxidative wear, additive decomposition —
none of which appears here. Only two of the ten functions carry a genuinely chemical quantity:
`surface_energy_work` (an interfacial thermodynamics term, the work needed to separate two adhered
surfaces) and `tribocorrosion_rate` (the mechanical-plus-chemical wear-corrosion synergy that gives
the real field of tribocorrosion its name). The module is real, working physics — it is just closer
to "`tribology`, plus two chemistry-adjacent functions" than to a chemical-kinetics module.

## Verification

All five `mojo/tests/libs/test_*.mojo` files behind this page
(`test_nanotechnology.mojo`, `test_plasma_physics.mojo`, `test_tribology.mojo`,
`test_tribochemistry.mojo`, `test_antenna.mojo`) are auto-generated coverage smoke tests: each calls
every function once with a fixed `0.5` (or `0.5, 0.5, ...`) for every argument and checks only that
the result is finite — they pin no specific numeric output and never probe a zero, negative, or
boundary input. Every number in this page was instead hand-computed independently from the real
formulas in `mojo/engine/nanotechnology.mojo`, `plasma_physics.mojo`, `tribology.mojo`,
`tribochemistry.mojo`, and `antenna.mojo`, cross-checked against known reference values where one
exists: the exact FCC packing fraction (Kepler's conjecture), the ~68 nm mean free path of air at
STP, the NRL Plasma Formulary's electron-plasma-frequency constant (5.64e4·√n[cm⁻³]), water's
145.6 mJ/m² work of cohesion, and the textbook isotropic effective aperture Ae = λ²/4π. Every
number given can be reproduced by re-running the same arithmetic.

**Next:** see [Classical ML algorithms](ml-classical-algorithms.md) for another page of small,
self-contained formula modules verified the same way by hand, or browse the
[Runtime library catalog](runtime-library-catalog.md) for every module and function in the engine.
