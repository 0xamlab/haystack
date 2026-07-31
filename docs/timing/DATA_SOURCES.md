# Data source inventory and triangulation matrix

Engineering record. Probed 2026-07-29 against the Hungarian GP race, 2026-07-26 — the last completed
round. Session identity is consistent across sources: official `SessionInfo.Key = 11342`,
OpenF1 `session_key = 11342`, `meeting_key = 1291`. **The same session keys join all sources**, so
triangulation needs no fuzzy matching.

---

## 1. Official F1 live-timing archive — PRIMARY, 33 feeds

`https://livetiming.formula1.com/static/{year}/{meeting}/{session}/`

### Ingested (26 feeds)

| Feed | Content |
|---|---|
| `SessionInfo` `SessionStatus` `SessionData` | session identity, status transitions |
| `DriverList` | 22 drivers with number, TLA, name, team, colour |
| `LapCount` `LapSeries` | lap progression |
| `TimingData` (71,303 rec) `TimingDataF1` (40,878) | the richest feeds — lap/sector times, gaps |
| `TimingAppData` `TimingStats` | stint/compound annotations, bests |
| `CurrentTyres` | compound + `New` bool per car |
| `TyreStintSeries` | stint compound, length, new/used |
| `PitStop` | **stationary time + pit-lane time per stop** |
| `PitStopSeries` | accumulating pit series |
| `PitLaneTimeCollection` | live transient, uses `_deleted` retraction |
| `OvertakeSeries` | per-car overtake **counts** (no pairing) |
| `TrackStatus` | SC/VSC/flag regimes, codes 1/2/6/7 observed |
| `RaceControlMessages` | 80 messages incl. `OVERTAKE ENABLED/DISABLED` (2026 override signal) |
| `WeatherData` `WeatherDataSeries` | air/track temp, humidity, pressure, wind, **rainfall** |
| `DriverRaceInfo` (30,428 rec) | dense per-driver race info |
| `ExtrapolatedClock` `Heartbeat` | clock and liveness |
| `CarData.z` `Position.z` | telemetry (767,448 samples) and positions (786,060) |
| **`ArchiveStatus`** | **`{"Status":"Complete"}` — the ingest completeness gate** |

**`ArchiveStatus` was initially excluded and is now included.** It is the only signal that a session's
archive is finished; ingesting a session whose status is not `Complete` would silently produce a
truncated corpus entry. It belongs in the session manifest as a precondition.

### Deliberately excluded (7 feeds)

| Feed | Shape | Why excluded |
|---|---|---|
| `TeamRadio` | `Captures[]` → `{Utc, RacingNumber, Path}` mp3 paths | audio; legal surface. *Note the metadata alone (who radioed, when) is strategy-adjacent — revisit only with a legal finding* |
| `AudioStreams` `ContentStreams` | HLS / commentary URIs | broadcast plumbing |
| `ChampionshipPrediction` | `{Drivers,Teams}` → `CurrentPosition, PredictedPosition, CurrentPoints, PredictedPoints` | **F1's own predictive model.** Must never enter the feature path — it would contaminate our probabilities with another model's output. *But it is a legitimate external baseline to compare against, kept strictly outside ingest* |
| `DriverTracker` `TopThree` | `Lines[]` with position, lap time, `DiffToAhead/Leader`, `LapState` bitfield | duplicative of `TimingData`. `LapState` (e.g. 1088) is an undocumented bitfield worth decoding later |
| `TlaRcm` | single race-control text | negligible |

---

## 2. OpenF1 — SECONDARY, triangulation and two unique surfaces

`https://api.openf1.org/v1/` · no auth on the free tier · 3 req/s, 30 req/min · **2023+**

`session_key=latest` returns 404 outside a live window — during the break, real keys are required.
`/v1/sessions?year=2026` returns **131 sessions including future ones**, so it doubles as a calendar
source.

| Endpoint | Records (session 11342) | Fields |
|---|---:|---|
| `drivers` | 22 | number, names, team, colour |
| `laps` | 1,423 | lap number, `date_start`, three sector durations |
| `pit` | **44** | `pit_duration`, `stop_duration`, `lane_duration`, lap |
| `stints` | 67 | `lap_start`, `lap_end`, `compound`, **`tyre_age_at_start`** |
| `position` | 536 | discrete position changes |
| `intervals` | 29,593 | `gap_to_leader`, `interval` — dense |
| `weather` | 156 | matches the official feed's 157 |
| `race_control` | 80 | with parsed `flag`, `scope`, `category` |
| **`session_result`** | **22** | `position`, `number_of_laps`, `points`, `dnf`, `dns`, `dsq`, `duration`, `gap_to_leader` |
| **`overtakes`** | **262** | **`overtaking_driver_number`, `overtaken_driver_number`, `date`, `position`** |
| `team_radio` | 36 | recording URLs |
| `car_data` | — | HTTP 422 "asking for too much data" — needs driver + time filters |
| `starting_grid` | — | 404 for this session |

### The two surfaces the official archive does not provide

**`session_result` — final classification with DNF/DNS/DSQ flags and points.** This is the outcome-truth
layer Gate 1 requires. Note DNFs carry `position: None`.

**`overtakes` — 262 pair-labelled events.** This partially restores what the official `OvertakeSeries`
lacks. **Critical caveat: these are OpenF1's *derived* labels, not official ground truth.** Fitting an
overtake kernel to them means fitting to OpenF1's reconstruction logic. Usable as a validation target
with that stated; it is not a licence to call the overtake kernel "trained on labelled data".

---

## 3. Jolpica — SECONDARY, Ergast-compatible results and reference data

`https://api.jolpi.ca/ergast/f1/{year}/{round}/...` · the Ergast successor.

| Endpoint | Total | Content |
|---|---:|---|
| `results` | 22 | position, driver, constructor, laps, points, **`status`** ("Finished" / "Retired") |
| `pitstops` | **45** | per-stop records |
| `laps` | 1,429 | per-lap timings |

**Jolpica classifies DNFs into positions** — PIA (55 laps) P20, PER (48) P21, BOT (13) P22 — i.e.
retirees ranked by laps completed, descending. **This independently confirms the DNF-ranking convention
frozen in the primary decision utility** ("retired cars placed behind all classified finishers, ordered
by laps completed then retirement time"). OpenF1 instead returns `position: None`, so our own ranking
rule is what reconciles them.

2026 grid detail worth noting: 11 teams / 22 drivers, including **Audi** and **Cadillac F1 Team**.

---

## 4. FastF1 — decoder-parity reference

**Not installed.** `import fastf1` fails. Required as a validation-only dependency for layer 1 of the
three-layer validation. It must never be imported by the runtime path — same category as
`benchmarks/python_libs/`.

---

## 5. Triangulation matrix — and a material discrepancy

| Quantity | Official | OpenF1 | Jolpica | Agreement |
|---|---:|---:|---:|---|
| Classified drivers | 22 | 22 | 22 | ✅ |
| Total laps | 70 | — | — | ✅ |
| Lap records | 1,429 | 1,423 | 1,429 | ⚠️ OpenF1 −6 |
| **Pit stops** | **33** | **44** | **45** | ❌ **three different counts** |
| Weather samples | 157 | 156 | — | ⚠️ −1 |
| Race-control messages | 80 | 80 | — | ✅ |
| Overtakes | 516 count-records | 262 pairs | — | different granularity |
| DNFs | — | 3 | 3 ("Retired") | ✅ |

### The pit-stop discrepancy undercuts an earlier claim

The Gate 0 record states that pit-loss components are "measured, not fitted" — that `pit_loss` and the
right-tailed `σ_pit` can be fitted from observation rather than assumed. **That claim needs qualifying.**

The official `PitStop` feed publishes **33** stops. OpenF1 reports **44** and Jolpica **45**. The most
likely explanation is that the official feed publishes only stops with a measured stationary time, while
the others count pit-lane *entries* — but that is a hypothesis, not a finding.

Why it matters: fitting `σ_pit` on the official 33 is only unbiased if the missing ~12 are missing at
random. If the official feed omits precisely the anomalous stops — drive-throughs, retirements in the
pit lane, stops without a tyre change — then the fitted slow-stop tail is truncated exactly where the
model most needs it, and the plan optimizer would systematically under-price a stop.

**Resolution is a Gate 1 prerequisite, not an optimization.** Reconcile all three sets per stop
(car, lap, timestamp), classify every non-matching record, and document the inclusion rule before any
pit-loss parameter is fitted. Until then, the honest statement is: *stationary and pit-lane time are
directly observed for the stops the official feed publishes; the completeness of that set is unverified.*

---

## 6. Layer assignment for the three-layer validation

| Layer | Source | Purpose |
|---|---|---|
| 1 — implementation | FastF1 (to install) | our decoder vs a reference decoder over the same raw bytes |
| 2 — outcome truth | OpenF1 `session_result` + Jolpica `results` | reconstruction vs final classification, points, DNF status |
| 3 — triangulation | OpenF1 series + Jolpica series | anomaly discovery, e.g. the pit-stop discrepancy above |

**Independence caveat, stated plainly:** all three ultimately derive from F1's own timing data. They are
independent *implementations*, not independent *observations*. Agreement therefore rules out
implementation error, not upstream error. The genuinely primary artefact is the FIA official
classification document; formula1.com's results pages return 200 and are a scraping path to it if a
stronger primary source is ever required.

---

## 7. Actions arising

1. **Include `ArchiveStatus`** in ingest and require `Complete` in the session manifest.
2. **Resolve the 33/44/45 pit-stop discrepancy** before fitting any pit-loss parameter (Gate 1 blocker).
3. **Install FastF1** as a validation-only dependency.
4. `OpenF1 /overtakes` is a *derived secondary* label set — usable for validation, never described as
   ground-truth labels.
5. `ChampionshipPrediction` stays out of ingest; may be cited as an external baseline.
6. OpenF1 `car_data` needs driver + time windowing; it is not a bulk path, so the official `CarData.z`
   remains the only viable telemetry source.
7. OpenF1's coverage starts at **2023**, so pre-2023 corpus seasons have only official + Jolpica —
   triangulation depth is season-dependent and the manifest must record which layers were available.
