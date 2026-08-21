---
icon: magnifying-glass-chart
description: Requirement-by-requirement data coverage audit — feed-availability eras, the 2025 frozen test season, single-source grid, and text-derived penalties.
---

# Data coverage audit — does every plan requirement have a source?

Every data-dependent requirement in the plan, checked against a probed source. Probed 2026-07-29.

**Verdict: the model is buildable, but the corpus is not homogeneous.** Two requirements need plan
changes, and one structural finding changes the Gate 3 season assignment.

---

## 1. THE STRUCTURAL FINDING — feed availability is a second era axis

The plan's era-aware design accounts for **regulation** eras. It does not account for **feed
availability** eras, and they do not align. Probed one Race session per season:

| Feed | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|---|---|
| `TimingData` `TimingAppData` `TimingStats` | ⚠ | ✅ | ✅ | ✅ | ✖ | ✅ | ✅ | ✅ | ✅ |
| `LapCount` `LapSeries` | ⚠ | ✅ | ✅ | ✅ | ✖ | ✅ | ✅ | ✅ | ✅ |
| `CurrentTyres` `TyreStintSeries` | ⚠ | ✅ | ✅ | ✅ | ✖ | ✅ | ✅ | ✅ | ✅ |
| `TrackStatus` `RaceControlMessages` | ⚠ | ✅ | ✅ | ✅ | ✖ | ✅ | ✅ | ✅ | ✅ |
| `CarData.z` `Position.z` | ⚠ | ✅ | ✅ | ✅ | ✖ | ✅ | ✅ | ✅ | ✅ |
| `WeatherData` `DriverRaceInfo` | ⚠ | ✅ | ✅ | ✅ | ✖ | ✅ | ✅ | ✅ | ✅ |
| **`PitStop` / `PitStopSeries`** | ✖ | ✖ | ✖ | ✖ | ✖ | ✖ | ✖ | **✅** | **✅** |
| **`OvertakeSeries`** | ✖ | ✖ | ✖ | ✖ | ✖ | ✖ | ✖ | **✅** | **✅** |
| `PitLaneTimeCollection` | ✖ | ✅ | ✅ | ✅ | ✖ | ✖ | ✅ | ✅ | ✅ |
| **feed count** | 28 | 29 | 31 | 31 | — | 29 | 29 | **33** | 32 |

- **2018 is partial.** The year index resolves and lists 20 race sessions, but early rounds (Bahrain,
  Chinese, Azerbaijan, Spanish) return HTTP errors on their session index; late rounds (Brazilian, Abu
  Dhabi) have 28 feeds. Coverage starts mid-season.
- **2022 is entirely unavailable** — `/static/2022/Index.json` returns an HTTP error. The plan excluded
  2022 for "unreliable timing data"; the real reason is that the archive is not served at all.
- **`PitStop` and `OvertakeSeries` exist only from 2025.** This is the consequential one.

### Consequence: the pit-loss claim narrows, and Gate 3's season assignment resolves

Officially published stationary time exists for **2025–2026 only** (~24 + ~13 ≈ 37 race sessions).
Earlier seasons have no `PitStop` feed at all, so pit-loss there must come from OpenF1 `/pit` (2023+) or
Jolpica `/pitstops` (full history) — different providers, different derivations, and the 33/44/45
discrepancy already recorded.

This gives a clean, well-motivated Gate 3 assignment rather than an arbitrary one:

```text title="Gate 3 season assignment"
Gate 3A development   2019–2021, 2023–2024   (no PitStop feed → pit-loss from Jolpica/OpenF1)
Gate 3B validation    subset of the above, held out by season
Gate 3D final test    2025  — complete season, full 33-feed surface, most recent finished era
Gate 3E prospective   2026  — shadow only, never tuned against
2018                  excluded (partial)   2022 excluded (unavailable)
```

**2025 is the right frozen final test season**: complete, richest feed surface, and the only finished
season where the official pit data exists. The manifest must record which feeds and which providers
were available per session, because triangulation depth is season-dependent.

---

## 2. Requirement-by-requirement coverage

| Plan requirement | Source | Status |
|---|---|---|
| **Lap time** `ℓ(t,a)` — lap/sector times | `TimingData` (71k rec), `LapSeries`; Jolpica `/laps` | ✅ 2019+ |
| **Compound** per stint | `CurrentTyres` (+`New` bool), `TyreStintSeries` | ✅ 2019+ |
| **Tyre age** | `TyreStintSeries`; OpenF1 `stints.tyre_age_at_start` (handles used sets) | ✅ 2019+ |
| **Fuel effect** | lap number from `LapCount`. Fuel load is **not observable** | ✅ as a calibrated constant, exactly as planned |
| **Cliff mining on green laps** | per-lap times + `TrackStatus` for SC/VSC exclusion | ✅ 2019+ |
| **SC / VSC regimes** | `TrackStatus` codes **1**=AllClear, **2**=Yellow, **4**=SCDeployed, **6**=VSCDeployed, **7**=VSCEnding | ✅ full SC confirmed in 4 of 8 sampled 2025 races |
| **Pit stop — stationary + lane time** | `PitStop` | ⚠️ **2025–2026 only**; earlier via OpenF1/Jolpica |
| **Dirty air window / loss** | OpenF1 `intervals` (29.6k rec: `gap_to_leader`, `interval`) + lap times | ✅ 2023+ dense; `TimingData` gaps earlier |
| **DNF probability** | OpenF1 `session_result.dnf`; Jolpica `status` ("Retired") | ✅ |
| **Target rival** (nearest ahead) | `intervals` / `Position.z` / `TimingData` | ✅ |
| **Grid position + `grid_spread`** | **Jolpica `results.grid`** and `/qualifying` (Q1/Q2/Q3) | ⚠️ **Jolpica only** — OpenF1 `starting_grid` 404s on both 2025 and 2026; the official archive has no grid feed |
| **Penalties** (RaceState field) | `RaceControlMessages` — 41 of 80 messages penalty-related | ⚠️ **free text only**, no structured penalty field |
| **Outcome truth** — position, points, laps | OpenF1 `session_result`; Jolpica `results` | ✅ both agree at 22 classified, 3 DNF |
| **Tyre-set feasibility cap** | derived from historical `TyreStintSeries` max stint per circuit×compound | ✅ 2019+ |
| **Track evolution** | lap times across the session | ✅ |
| **Metrics** — Brier/ECE/Spearman/BSS | realized outcomes above | ✅ |
| **Weather / rainfall** (Gate 5) | `WeatherData`: air+track temp, humidity, pressure, wind, `Rainfall` | ✅ 2019+ |
| **Overtake pair labels** | OpenF1 `/overtakes` (262 pairs) — **derived, not official** | ⚠️ 2023+, secondary derivation |
| **Archive completeness gate** | `ArchiveStatus` = `Complete` | ✅ 2019+ |
| **Telemetry proxies** (Gate 5) | `CarData.z` — RPM/speed/gear/throttle/brake, irregular ~4 Hz | ✅ with the sampling caveat |
| **2026 override mode** (Gate 5) | `RaceControlMessages` text `OVERTAKE ENABLED/DISABLED` — no telemetry channel | ✅ as a race-control signal only |

---

## 3. The two requirements needing plan changes

### 3a. Grid position has a single-source dependency

`grid_spread` and the pre-race oracle backtest both need starting grid. The official archive does not
publish it, and OpenF1's `starting_grid` returns 404 on every session probed. **Jolpica is the only
source**, via `results.grid` (verified: grid=1, 4, 7, 2 …) plus full qualifying with Q1/Q2/Q3 times.

That is a single point of failure for a Gate 3 requirement, with no triangulation partner. Options, in
order of preference:

1. Derive grid from the official archive's own qualifying-session data — we archive qualifying sessions
   anyway, so classification from the quali session gives an independent grid. *Requires handling grid
   penalties, which change the grid after qualifying.*
2. Accept Jolpica as sole source and record it in the manifest as un-triangulated.
3. Scrape formula1.com's official results pages (returns 200) as a second source.

**Recommendation: (1) with (2) as cross-check.** Deriving grid from the archived qualifying session keeps
grid inside the primary corpus, and disagreement with Jolpica then surfaces grid penalties — which is
itself information the model wants.

### 3b. Penalties are free text, not a structured field

`RaceControlMessages` fields are `Category, Flag, Lap, Message, Mode, RacingNumber, Scope, Sector,
Status, Utc`. Categories in the probe race: `Flag` 28, `Other` 50, `SafetyCar` 2. Penalty content lives
in `Message` as prose:

```text title="RaceControlMessages penalty prose"
CAR 43 (COL) LAP DELETED - TRACK LIMITS AT TURN 4 LAP 1 15:03:59
TURN 3 INCIDENT INVOLVING CARS 14 (ALO) AND 87 (BEA) NOTED - FORCING ANOTHER DRIVER OFF
INCIDENT INVOLVING CAR 11 (PER) NOTED - STARTING PROCEDURE INFRINGEMENT (15:02:39)
FIA STEWARDS: ... REVIEWED NO FURTHER INVESTIGATION
```

Extraction is string matching over phrasing that is not guaranteed stable across seasons. Two
implications:

1. **Penalties stay out of the decision path for the Monza slice.** The plan already treats stewarding as
   a scorer-side noise channel ("the simulator predicts on-road order"), so this is consistent — but the
   `RaceState.penalties` field must be marked *best-effort, text-derived* rather than observed.
2. If penalty parsing is ever needed, it requires its own per-season validation, because a silent parse
   failure looks identical to "no penalty".

`Category: SafetyCar` messages carry a `Mode` field, giving an independent cross-check on `TrackStatus`
regimes — worth using for the SC/VSC validation.

---

## 4. What is genuinely unobservable (confirms the class-3 boundary)

Nothing in this list has any source, which is why they sit behind the experimental boundary:

fuel load · brake pressure · wheel speeds · steering angle · brake temperature · tyre surface or carcass
temperature · tyre pressure · battery state of charge · MGU-K deploy/harvest power · fuel flow ·
suspension travel · ride height · torque · **remaining tyre inventory** · team orders · crew availability.

---

## 5. Actions arising

1. **Add feed-availability eras as a second axis** to the Gate 3 corpus structure, alongside regulation
   eras.
2. **Adopt 2025 as the frozen final retrospective test season** — complete, 33 feeds, official pit data.
3. **Development corpus = 2019–2021 + 2023–2024**; exclude 2018 (partial) and 2022 (archive unavailable).
4. **Narrow the pit-loss claim**: official stationary time is 2025–2026 only. For earlier seasons state
   the provider and its derivation. Resolve 33/44/45 before fitting (existing Gate 1 blocker).
5. **Derive grid from archived qualifying sessions**, cross-checked against Jolpica; record disagreements
   as candidate grid penalties.
6. **Mark `RaceState.penalties` as text-derived best-effort**, excluded from the decision path.
7. **Record per-session in the manifest**: feed list, provider availability per quantity, and
   triangulation depth. Season-dependent coverage must be data, not folklore.

## Related

* [DATA_SOURCES.md](DATA_SOURCES.md) — the source inventory this audit checks against.
* [FROZEN_SPECS.md](FROZEN_SPECS.md) — the frozen specs the covered requirements feed.
* [GATE0_VERIFICATION.md](GATE0_VERIFICATION.md) — the Gate 0 record this audit refines.
