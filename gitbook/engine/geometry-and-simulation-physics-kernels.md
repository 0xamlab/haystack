---
icon: shapes
description: 2D Euclidean geometry, rigid-body game-engine kinematics, chemical reaction-rate kinetics, and point-cloud topological data analysis -- four self-contained modules that share no code with each other or with the geospatial, biomechanics, pharmacokinetics, or network-topology modules their names might suggest.
---

# Geometry and simulation-physics kernels

Four modules, grouped on one page because each is small and self-contained rather than because
they call into one another. `geometry` is 2D Euclidean computational geometry on a plain
`Point(x, y)` struct -- distance, area, convex hull, point-in-polygon. `game_physics` is the
arithmetic underneath a 2D/1D game engine's physics step -- position and velocity integration,
elastic collisions, springs, drag, projectile range. `kinetics` is chemical reaction-rate theory --
Arrhenius activation energy, collision frequency, Michaelis-Menten enzyme kinetics. `topology` is
point-cloud topological data analysis -- Vietoris-Rips complexes, Betti numbers, persistence
diagrams. None of the four imports another, and (as the sections below verify against real source)
none of them is a duplicate of a same- or similar-sounding module documented elsewhere in this
corpus.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

triangle = [{"__algenta_struct": "Point", "v": [0.0, 0.0]},
            {"__algenta_struct": "Point", "v": [4.0, 0.0]},
            {"__algenta_struct": "Point", "v": [0.0, 3.0]}]
runtime.execute("geometry", "polygon_area", [triangle])["result"]
# 6.0 -- shoelace formula on a real 3-4-5 right triangle

runtime.execute("game_physics", "elastic_collision_1d", [2.0, 3.0, 1.0, 0.0])["result"]
# 1.0 -- a mass-2 object at 3 m/s hits a stationary mass-1 object head-on
```

## The modules

| Module | What it does |
| --- | --- |
| `geometry` | 2D Euclidean point/polygon primitives on a plain `Point(x, y)` struct: distance, 2D cross product, ray-cast point-in-polygon, shoelace area and perimeter, Andrew's monotone-chain convex hull, line-segment intersection, centroid, and axis-aligned bounding box. |
| `game_physics` | Rigid-body and particle kinematics for a game engine: Euler and Störmer-Verlet position/velocity integration, 1-D elastic collision and coefficient of restitution, kinetic energy, Newtonian gravity, projectile range, quadratic drag, Hooke's-law spring force, and a solid sphere's angular velocity and moment of inertia. |
| `kinetics` | Chemical reaction-rate kinetics: first- and second-order reaction rates and half-lives, the Arrhenius rate-constant equation, activation energy from two rate/temperature pairs, bimolecular collision frequency from kinetic theory, and Michaelis-Menten enzyme kinetics with turnover number. |
| `topology` | Point-cloud topological data analysis: pairwise distance matrices, Vietoris-Rips complexes, union-find connected components, the β₀ Betti number, sorted filtration values, a β₀ persistence diagram with its total persistence and a simplified bottleneck distance, plus the Euler characteristic and a triangle count for a fixed simplicial complex. |

## `geometry`: a `Point` struct, and the frozen kernel three other modules call unchanged

| Function | What it does |
| --- | --- |
| `distance_2d(a, b)` | Euclidean distance between two points. |
| `cross_product_2d(o, a, b)` | 2D cross product of `OA` and `OB` -- positive for counter-clockwise, negative for clockwise. |
| `point_in_polygon(p, polygon)` | Ray-casting (crossing-number) test; `False` for any polygon under 3 vertices. |
| `polygon_area(polygon)` | Shoelace formula, absolute value; `0.0` under 3 vertices. |
| `polygon_perimeter(polygon)` | Sum of edge lengths, wrapping last-to-first; `0.0` under 2 vertices. |
| `convex_hull(points)` | Andrew's monotone-chain hull, returned counter-clockwise; under 3 points it returns a plain copy of the input, not a real hull. |
| `line_intersection(p1, p2, p3, p4)` | Intersection of the infinite lines through `(p1,p2)` and `(p3,p4)` -- the only function on this page that `raises` rather than returning a sentinel, on parallel/coincident lines. |
| `centroid(polygon)` | Area-weighted polygon centroid; falls back to the plain arithmetic mean of the vertices when the signed area is degenerate (collinear points). |
| `bounding_box(points)` | `[min_x, min_y, max_x, max_y]`; an empty list for an empty input. |

Every argument and return value that isn't a plain `Float64`/`Bool`/`List[Float64]` here is a
`Point`, and the runtime's struct-marshaling convention wraps it as
`{"__algenta_struct": "Point", "v": [x, y]}` -- the same convention documented for `TomlDoc` and
`CSVRow` in [Config and data-parsing kernels](config-and-data-parsing-kernels.md). A `List[Point]`
argument (`polygon`, `points`) is a plain JSON array of that same wrapped-struct shape, and a
`List[Point]` return (`convex_hull`) comes back the same way.

**Real, hand-pinned values, traced against `tests/mojo/test_wave18.mojo`.** There is no
`test_geometry.mojo` auto-generated smoke test at all in `mojo/tests/libs/` -- unlike every other
module on this page, `geometry`'s functions take `Point`/`List[Point]` arguments the smoke-test
generator has no literal-`0.5` equivalent for, so it was skipped outright rather than partially
covered. The real coverage is Wave 18's 18 hand-written assertions instead:

```python
runtime.execute("geometry", "distance_2d",
    [{"__algenta_struct": "Point", "v": [0.0, 0.0]},
     {"__algenta_struct": "Point", "v": [3.0, 4.0]}])["result"]
# 5.0 -- a 3-4-5 right triangle's hypotenuse

square = [{"__algenta_struct": "Point", "v": [0.0, 0.0]},
          {"__algenta_struct": "Point", "v": [1.0, 0.0]},
          {"__algenta_struct": "Point", "v": [1.0, 1.0]},
          {"__algenta_struct": "Point", "v": [0.0, 1.0]}]
runtime.execute("geometry", "point_in_polygon",
    [{"__algenta_struct": "Point", "v": [0.5, 0.5]}, square])["result"]
# True -- centre of the unit square
runtime.execute("geometry", "polygon_area", [square])["result"]
# 1.0
runtime.execute("geometry", "polygon_perimeter", [square])["result"]
# 4.0
runtime.execute("geometry", "centroid", [square])["result"]
# {"__algenta_struct": "Point", "v": [0.5, 0.5]}

runtime.execute("geometry", "line_intersection",
    [{"__algenta_struct": "Point", "v": [0.0, 0.0]}, {"__algenta_struct": "Point", "v": [2.0, 2.0]},
     {"__algenta_struct": "Point", "v": [0.0, 2.0]}, {"__algenta_struct": "Point", "v": [2.0, 0.0]}])["result"]
# {"__algenta_struct": "Point", "v": [1.0, 1.0]} -- the X-pattern's centre
```

`cross_product_2d(O=(0,0), A=(1,0), B=(0,1))` is `+1.0` (counter-clockwise turn); with `A` and `B`
swapped it is `-1.0` (clockwise) -- both pinned in Wave 18. `convex_hull` on 5 hull points plus 3
strictly interior points (`(0.5,0.5)`, `(1,1)`, `(1.5,0.5)`) returns fewer than the 8 input points
and at least the 4 corners; `bounding_box` on that same 8-point set returns `[0.0, 0.0, 2.0, 2.0]`.

**Degenerate centroid: three collinear points fall back to a plain mean.** `centroid` on
`(0,0), (1,0), (2,0)` computes a shoelace signed area of exactly `0.0` (every cross term in the
loop is `0` for collinear points), which trips the `fabs(signed_area) < 1e-15` guard and returns
the arithmetic mean `(1.0, 0.0)` instead of dividing by a near-zero area -- read directly from
`geometry.mojo`'s `centroid` body, not a value asserted by Wave 18 but a straightforward trace of
the same code the passing test exercises for the non-degenerate square case.

{% hint style="info" %}
**`geospatial.polygon` calls four of these functions unchanged, and deliberately skips a fifth.**
`geospatial/polygon.mojo`'s own module docstring lists `geometry.polygon_area`,
`geometry.polygon_perimeter`, `geometry.cross_product_2d`, and `geometry.line_intersection` as
"frozen kernels called unchanged" underneath its lat/lon ring operations documented in
[Geospatial](geospatial.md). It explicitly does *not* call `geometry.point_in_polygon`, and says
why in its own comments: that function's `Bool` return can't express "exactly on the boundary," and
its ray-cast division (`(xj-xi)*(p.y-yi)/(yj-yi)`) can put a boundary point on either side depending
on rounding. `geospatial.polygon` reimplements a three-valued, division-free point-in-polygon test
for that reason -- a real, source-confirmed relationship (dependency plus one deliberate
non-reuse), not a duplicate.
{% endhint %}

## `game_physics`: kinematics, collisions, and forces for a game engine -- not `biomechanics`

| Function | What it does |
| --- | --- |
| `position_update(x, v, a, dt)` | Euler position step: `x + v*dt + 0.5*a*dt²`. |
| `velocity_update(v, a, dt)` | Euler velocity step: `v + a*dt`. |
| `verlet_position(x, x_prev, a, dt)` | Störmer-Verlet position: `2*x - x_prev + a*dt²`. |
| `elastic_collision_1d(m1, v1, m2, v2)` | Post-collision velocity of object 1: `((m1-m2)*v1 + 2*m2*v2)/(m1+m2)`; `0.0` if the total mass is ~0. |
| `coefficient_of_restitution(v_sep, v_approach)` | `v_sep / v_approach`; `0.0` if approach speed is ~0. |
| `kinetic_energy(mass, velocity)` | `0.5 * m * v²`. |
| `gravitational_force(m1, m2, r, g)` | `g * m1 * m2 / r²`; `0.0` if `r` is ~0. |
| `projectile_range(v0, angle, g)` | `v0² * sin(2·angle) / g`; `0.0` if `g` is ~0. |
| `drag_force_quadratic(cd, rho, a, v)` | `0.5 * Cd * ρ * A * v²`. |
| `spring_force(k, displacement)` | `k * \|displacement\|` -- Hooke's law, magnitude only, sign-agnostic. |
| `angular_velocity_from_linear(v, r)` | `v / r`; `0.0` if `r` is ~0. |
| `moment_of_inertia_sphere(mass, radius)` | `0.4 * m * r²` -- a solid sphere. |

Every guarded division returns a plain `0.0` sentinel on a near-zero denominator (`fabs(x) < 1e-30`)
rather than raising -- the same zero-sentinel convention `mixture_of_experts` and `moe_production`
use, and unlike `geometry.line_intersection`'s `raise` on the same kind of degeneracy.

**Real, hand-pinned values, traced against `tests/mojo/test_wave76.mojo`.**

```python
runtime.execute("game_physics", "position_update", [10.0, 5.0, 2.0, 0.1])["result"]
# 10.51 -- x=10, v=5, a=2, dt=0.1: 10 + 5*0.1 + 0.5*2*0.01

runtime.execute("game_physics", "verlet_position", [10.0, 9.8, 2.0, 0.1])["result"]
# 10.22 -- 2*10 - 9.8 + 2*0.01

runtime.execute("game_physics", "coefficient_of_restitution", [3.0, 5.0])["result"]
# 0.6

runtime.execute("game_physics", "projectile_range", [10.0, 0.7853981633974483, 10.0])["result"]
# 10.0 -- v0=10 m/s at 45 degrees, g=10 m/s^2

runtime.execute("game_physics", "moment_of_inertia_sphere", [5.0, 0.1])["result"]
# 0.02 -- a 5 kg, 0.1 m-radius solid sphere
```

`elastic_collision_1d` only returns object 1's post-collision velocity, not object 2's -- a caller
wanting both has to call it twice with the arguments swapped (`elastic_collision_1d(m2, v2, m1, v1)`
for object 2), since there is no paired-output variant in this module.

**This is not `biomechanics`, despite both being physics of moving bodies.**
[Biomedical, biomechanics, and psychoacoustics kernels](biomedical-engineering-kernels.md)'s
`biomechanics` module (`joint_torque`, `stride_length`, `metabolic_cost_walking`,
`muscle_force_hill`, and others) models human joint and gait mechanics -- reading both
`game_physics.mojo` and `biomechanics.mojo`, the two modules share zero function names and zero
formulas. `game_physics` is generic 2D/1D rigid-body and particle mechanics for a game engine (no
human anatomy anywhere in it); `biomechanics` is specifically joint torque, stride, and muscle force
for a human or animal body. The only thing they have in common is the word "physics" one docstring
away from the other's.

## `kinetics`: chemical reaction-rate theory -- not `pharmacokinetics`/`toxicokinetics`

| Function | What it does |
| --- | --- |
| `reaction_rate_first_order(rate_constant, concentration)` | `r = k·[A]`; `0.0` if either input is negative. |
| `reaction_rate_second_order(rate_constant, conc_a, conc_b)` | `r = k·[A]·[B]`; `0.0` if any input is negative. |
| `arrhenius_rate_constant(pre_exponential, activation_energy, temperature)` | `k = A·exp(-Ea/RT)`, `R = 8.314 J/(mol·K)`; `0.0` if `temperature <= 0` or `pre_exponential < 0`. |
| `half_life_first_order(rate_constant)` | `t½ = ln(2)/k`; `0.0` if `k <= 0`. |
| `half_life_second_order(rate_constant, initial_concentration)` | `t½ = 1/(k·[A]₀)`; `0.0` if either input is `<= 0`. |
| `concentration_first_order(c0, rate_constant, time)` | `[A](t) = [A]₀·exp(-k·t)`; returns `c0` **unchanged** (not `0.0`) if `c0`, `rate_constant`, or `time` is negative. |
| `activation_energy(k1, k2, t1_k, t2_k)` | `Ea = R·ln(k2/k1) / (1/T1 - 1/T2)`; `0.0` if any rate/temperature is `<= 0` or the two temperatures are equal. |
| `collision_frequency(n_density, diameter, temperature, mass)` | `Z = n²·π·σ²·√(8kT/(πm))` from kinetic theory; `0.0` if any input is `<= 0`. |
| `michaelis_menten_rate(vmax, substrate, km)` | `v = Vmax·[S] / (Km + [S])`; `0.0` if `Km + [S] <= 0`. |
| `turnover_number(vmax, enzyme_total)` | `kcat = Vmax / [E]T`; `0.0` if `[E]T <= 0`. |

**Only the auto-generated smoke test exists for this module -- no hand-pinned wave test.**
`mojo/tests/libs/test_kinetics.mojo` calls every function once with literal `0.5` arguments and
checks only that the result is finite; grepping every `tests/mojo/test_wave*.mojo` file in the repo
for `kinetics` finds nothing (Wave 65's `pharmacokinetics` tests are a different module entirely --
see below). The worked examples below were hand-traced independently against the real formulas in
`kinetics.mojo` and verified in plain Python before being presented here:

```python
runtime.execute("kinetics", "arrhenius_rate_constant", [1e13, 75000.0, 298.0])["result"]
# 0.7132194508208716 -- A=1e13 s^-1, Ea=75 kJ/mol, T=298K (room temperature)

runtime.execute("kinetics", "half_life_first_order", [0.0231])["result"]
# 30.006371452811486 -- ln(2)/0.0231

runtime.execute("kinetics", "michaelis_menten_rate", [10.0, 5.0, 2.0])["result"]
# 7.142857142857143 -- Vmax=10, [S]=5, Km=2: 10*5/(2+5)

runtime.execute("kinetics", "activation_energy", [1e-3, 1e-2, 300.0, 310.0])["result"]
# 178036.33990731786 -- J/mol, from a 10x rate increase over a 10K rise
```

**This is chemical reaction kinetics, not drug or toxicant kinetics.**
[Pharmacology and toxicology kernels](pharmacology-and-toxicology-kernels.md) documents
`pharmacokinetics` and `toxicokinetics` -- one-compartment absorption/distribution/elimination
models for a drug or toxicant's concentration over time in a body. The bare `kinetics` module here
is a different subject entirely: reaction-rate theory from physical chemistry (Arrhenius kinetics,
bimolecular collision frequency, enzyme kinetics) with no concept of a dose, a compartment, or a
body at all. Reading both `kinetics.mojo` and `pharmacokinetics.mojo`, the two modules share zero
function names; the only overlapping vocabulary is "half-life," and even that means something
different in each -- `kinetics.half_life_first_order` is a reaction's `ln(2)/k`, while
`pharmacokinetics`'s elimination half-life (documented on that page) is the same formula applied to
a drug's own first-order elimination rate constant, not a chemical reaction's.

**`concentration_first_order`'s invalid-input guard is inconsistent with its four siblings.**
Every other guarded function on this page returns a plain `0.0` for invalid input.
`concentration_first_order` instead returns `c0` completely unchanged when `c0`, `rate_constant`,
or `time` is negative -- reading the source, `if c0 < 0.0 or rate_constant < 0.0 or time < 0.0:
return c0` skips the exponential decay entirely rather than reporting `0.0`. A caller treating every
function on this page as "invalid input yields zero" will get a real, non-zero, non-decayed
concentration back from this one specific function instead.

## `topology`: point-cloud topological data analysis -- not network topology

| Function | What it does |
| --- | --- |
| `distance_matrix(points)` | Pairwise Euclidean distance matrix, symmetric with a zero diagonal. |
| `vietoris_rips_edges(distances, epsilon)` | `[i, j]` pairs with `dist(i,j) <= epsilon`, `i < j`. |
| `connected_components_from_edges(n, edges)` | Component count via union-find over an edge list. |
| `betti_0(n, edges)` | β₀ -- identical to `connected_components_from_edges`, under a topology-literature name. |
| `filtration_values(distances)` | Sorted, de-duplicated (within `1e-12`) edge weights. |
| `persistence_diagram_0(distances)` | `[birth, death]` pairs for β₀ -- every birth is `0.0`; the last surviving component's death is `1e18` (symbolic infinity). |
| `total_persistence(diagram)` | `Σ(death - birth)` over finite pairs, excluding any `death >= 1e18`. |
| `bottleneck_distance(d1, d2)` | A simplified (not literature-exact) bottleneck distance: the max, over both directions, of each point's nearest-neighbour L∞ distance in the other diagram. |
| `euler_characteristic(V, E, F)` | `χ = V - E + F`. |
| `rips_triangle_count(n, edges)` | Count of 3-cliques (triangles) in the edge set. |

**Real, hand-pinned values, traced against `tests/mojo/test_wave58.mojo`.**

```python
runtime.execute("topology", "betti_0", [4, []])["result"]
# 4 -- four points, zero edges: every point is its own component

runtime.execute("topology", "betti_0",
    [3, [[0, 1], [1, 2], [0, 2]]])["result"]
# 1 -- a fully-connected triangle of 3 points is one component

runtime.execute("topology", "euler_characteristic", [4, 6, 4])["result"]
# 2 -- a tetrahedron's V-E+F (also 8-12+6=2 for a cube's surface)

runtime.execute("topology", "rips_triangle_count",
    [4, [[0,1],[0,2],[0,3],[1,2],[1,3],[2,3]]])["result"]
# 4 -- a fully-connected 4-clique contains C(4,3)=4 triangles
```

At `epsilon = 0.0`, `vietoris_rips_edges` on 3 distinct points returns zero edges (no two distinct
points are ever exactly `0` apart); at a large enough `epsilon` the same 3 points return all 3
possible edges. `persistence_diagram_0` on 3 points always returns exactly 3 `[birth, death]`
pairs -- `n - 1` finite merge events plus the one immortal component -- and every birth is `0.0`,
both pinned in Wave 58.

**`bottleneck_distance` is explicitly "simplified," per its own docstring, not the literature's
optimal-matching bottleneck distance -- but the shared `1e18` sentinel doesn't break it.** The real
bottleneck distance from TDA is a minimum over all matchings (including matching points to the
diagonal, to discount short-lived "noise" features); this implementation instead does an
independent nearest-neighbour lookup for each point in each direction, which is not guaranteed
optimal for a general matching problem. Re-running the exact algorithm against two real
`persistence_diagram_0` outputs -- one from 3 points at `[0, 1, 5]`, one from 4 points at
`[0, 1, 2, 100]` -- confirms it behaves sensibly despite every diagram always carrying one `1e18`
death: `bottleneck_distance(d, d) = 0.0` (matches Wave 58's own `test_bottleneck_distance_same`),
and comparing the two differently-scaled diagrams returns a large but finite `94.0`, not `~1e18` --
because each diagram's own `1e18` entry is always its nearest match in the other diagram (distance
`0`), so the shared sentinel cancels out and the score is driven entirely by the finite,
topologically-meaningful pairs.

**Two functions cap how many vertices they'll actually process, silently.**
`connected_components_from_edges` allocates union-find storage sized to the highest vertex index
actually appearing in `edges` (not to the full `n`), capped at `1,000,000`; `rips_triangle_count`
does the same but caps at `1,024`, because it additionally builds an `n×n` adjacency matrix and
scans it in `O(n³)` for triangles. Past those caps, vertices beyond the limit are dropped from
consideration rather than raising -- a real, source-confirmed ceiling on both functions' inputs, not
a documented parameter.

{% hint style="info" %}
**This is mathematical topology (persistent homology), not the network topology documented
elsewhere in this corpus under other names.**
[Business operations and real estate kernels](business-operations-and-real-estate-kernels.md)'s own
section on `telecommunications` is titled "link budget and traffic-engineering formulas, **not
topology or HTTP**" -- confirming that module has nothing to do with graph/network topology either.
[Networking and social-graph kernels](networking-and-social-graph-kernels.md) states plainly that
its `network_protocol` module has "no socket, no packet, and no topology anywhere in it." Neither
page documents a module named bare `topology`, and grepping this whole `gitbook/` tree for "Betti,"
"persistence diagram," or "Vietoris" before writing this page turned up nothing -- this is the first
and only page covering it. It is also distinct from `graph.algorithms.connected_components(g:
Graph) -> List[Int]` (documented via the runtime library catalog), which BFS-labels every node of an
explicit `Graph` struct with its component index; `topology.connected_components_from_edges(n,
edges) -> Int`, by contrast, takes a bare edge list and a union-find pass to return only a count --
built for exactly one purpose, feeding `betti_0`, not general graph traversal.
{% endhint %}

**The auto-generated smoke test for this module only exercises 1 of its 10 functions.**
`mojo/tests/libs/test_topology.mojo` calls `euler_characteristic(5, 5, 5)` and nothing else -- every
other function in `topology` takes a `List[List[Float64]]` or `List[List[Int]]` argument, and the
smoke-test generator has no literal-`0.5` (or similar scalar) equivalent to synthesize for those
shapes, so it silently skipped them rather than failing to generate. The real coverage for the other
nine functions is Wave 58's 12 hand-written assertions, traced above.

## Verification

`geometry`, `game_physics`, and `topology` each have a real, hand-written, numerically-pinned test
suite in `tests/mojo/test_wave18.mojo`, `test_wave76.mojo`, and `test_wave58.mojo` respectively --
every worked example given for those three modules above is lifted directly from one of those
files' own assertions. `kinetics` has no such suite anywhere in the repository; its worked examples
above were computed independently in plain Python against `kinetics.mojo`'s real formulas (matching
every guard and constant, including the literal `R = 8.314`) before being presented as fact, and can
be reproduced by re-running the same arithmetic.

**Next:** see [Geospatial](geospatial.md) for the lat/lon layer built on top of four of `geometry`'s
functions, or browse the [Runtime library catalog](runtime-library-catalog.md) for every module and
function.
