# Gate 0 — Verification record

Engineering record, not published documentation. Every external fact the build depends on is verified
against a primary source here, with the probe that established it, so nothing rests on secondary
summaries.

Branch `feat/timing-pitwall`, worktree `~/Developer/decision-engine-timing`, off `origin/main`
`79de0cf1` (#412).

Probed 2026-07-29.

---

## 1. Calendar — VERIFIED

Source: formula1.com official 2026 calendar.

| | Round | Event | Dates |
|---|---|---|---|
| Last completed | 11 | Hungarian Grand Prix, Budapest | 24–26 Jul 2026 |
| Next race | 12 | Dutch Grand Prix, Zandvoort | **21–23 Aug 2026** |
| **Target** | 13 | **Italian Grand Prix, Monza** | **4–6 Sep 2026** |
| After | 14 | Spanish Grand Prix | 11–13 Sep 2026 |

23 rounds, season ends Abu Dhabi 4–6 Dec 2026.

**Correction to an earlier assumption:** Monza was assumed to be 21–23 Aug. That date is Zandvoort.
Monza is 4–6 Sep — five weeks out, not three and a half.

**Consequence:** Zandvoort becomes the Gate 4 live rehearsal, two weeks before the target. Gate 4's
requirement that the target weekend must not be the first live exercise is now met by a real Grand Prix
rather than a synthetic fault-injection run. Fault injection still happens; it is no longer the only
pre-target evidence.

---

## 2. Live-timing endpoints — VERIFIED

```
POST https://livetiming.formula1.com/signalrcore/negotiate?negotiateVersion=1   → 200
GET  https://livetiming.formula1.com/static/Index.json                          → {"Years":[{"Year":2026,"Path":"2026/"}]}
GET  https://livetiming.formula1.com/static/2024/Index.json                     → 200
GET  https://livetiming.formula1.com/static/2018/Index.json                     → 200
```

**The root index lists only the current year.** Historical years are reachable by direct path but are
not discoverable from the root. Corpus discovery must enumerate years explicitly rather than crawl.

Hierarchy: root → `/{year}/Index.json` (meetings, each with sessions carrying `Key`, `Type`, `Number`,
`Name`, `StartDate`, `EndDate`, `GmtOffset`, `Path`) → `{Path}/Index.json` (`Feeds`, each with
`KeyFramePath` and `StreamPath`).

---

## 3. Feed inventory — VERIFIED: 33 feeds, not 20

Probe session: `2026/2026-07-26_Hungarian_Grand_Prix/2026-07-26_Race/Index.json`.

The FastF1 client subscribes to 20 topics; the archive exposes 33. Full list:

```
ArchiveStatus            AudioStreams             CarData.z
ChampionshipPrediction   ContentStreams           CurrentTyres
DriverList               DriverRaceInfo           DriverTracker
ExtrapolatedClock        Heartbeat                LapCount
LapSeries                OvertakeSeries           PitLaneTimeCollection
PitStop                  PitStopSeries            Position.z
RaceControlMessages      SessionData              SessionInfo
SessionStatus            TeamRadio                TimingAppData
TimingData               TimingDataF1             TimingStats
TlaRcm                   TopThree                 TrackStatus
TyreStintSeries          WeatherData              WeatherDataSeries
```

### Strategy-critical feeds absent from the assumed list

| Feed | Why it matters |
|---|---|
| `CurrentTyres` | compound **and** a `New` boolean per car — fitted-tyre state is directly observed |
| `TyreStintSeries` | stint boundaries and history without reconstruction |
| `PitStop`, `PitStopSeries`, `PitLaneTimeCollection` | pit events with timing; pit-loss components become measurable rather than fitted |
| `OvertakeSeries` | **labelled overtake events** — a direct fitting/validation target for the overtake kernel instead of deriving battles from gap traces |
| `LapSeries` | per-lap series data |
| `TimingDataF1` | a second timing representation alongside `TimingData`; usable for cross-checking |
| `DriverRaceInfo`, `WeatherDataSeries` | supplementary race and weather series |

### Archive selection

**Include:** `SessionInfo` `SessionStatus` `SessionData` `DriverList` `LapCount` `LapSeries`
`TimingData` `TimingDataF1` `TimingAppData` `TimingStats` `CurrentTyres` `TyreStintSeries` `PitStop`
`PitStopSeries` `PitLaneTimeCollection` `OvertakeSeries` `TrackStatus` `RaceControlMessages`
`WeatherData` `WeatherDataSeries` `DriverRaceInfo` `ExtrapolatedClock` `Heartbeat` `CarData.z`
`Position.z`

**Exclude:** `TeamRadio` `AudioStreams` `ContentStreams` — legal and storage surface, no strategy value.
`ChampionshipPrediction` — a third-party model output, not an observation; ingesting it would risk
contaminating our own probabilities. `DriverTracker` `TlaRcm` `TopThree` `ArchiveStatus` — presentation
surfaces, revisit only if a specific need appears.

---

## 4. Stream format — VERIFIED, and different from the assumption

Probe: first 20 001 bytes of `CarData.z.jsonStream`, Hungarian GP race.

| Property | Verified |
|---|---|
| Leading bytes | UTF-8 BOM `EF BB BF` — present, must be stripped |
| Record separator | CRLF (49 CRLF and 49 LF in the sample → all LF are part of CRLF) |
| Record shape | `HH:MM:SS.mmm` immediately followed by the payload. **Not** a `[timestamp, content]` JSON array |
| `.z` payload | a quoted base64 string |
| Compression | base64 → **raw deflate**, `wbits = -zlib.MAX_WBITS`. zlib (`+MAX_WBITS`) and gzip (`31`) framing both fail |

Confirmed record: `00:00:01.864"7ZjNasMwDIDfRee0SPJvfC17g+2ysUMZhQ1GD11vIe9ez6ewelocmoGLLw6YfBhL9iclAzwcz6ePwxeElwGezm8QgJHtBt2G7SNxwD4QbVkbq7V7hg52+1N8ewD6Hnbv++Px8JkmEAJ2wGlUadQQCHUHJj3HMc2XQ2YJZJdAhLMoTAwmYl4YpgRnCI1KhnTxMvMCMCV8KcG5dGqlrAi5HMR0Df08O8XJUcXJ0eXEvCM9JXK5ZFT+z3uQuwiqdyStZrM5wp4lyOVyJG7KFwfOF64RGclQOhqKDDVDrWYocvdiKHbiVpqhbmoojazKDUVK1FqFhnLWGOtaD7WWoWIl7O/GUPb6rjVDrddDeVNuKJYLYnWG4i2iMYq5GWq9HkqsaQ..."`
→ 460 base64 chars → 5 943 bytes JSON.

### Decoded `CarData` shape

```json
{"Entries": [
  {"Utc": "2026-07-26T12:09:11.2456447Z",
   "Cars": {"1": {"Channels": {"0": 0, "2": 0, "3": 0, "4": 104, "5": 104}}, ...}}
]}
```

Multiple entries per frame (5 in the sampled frame). `Utc` carries **7 fractional digits** — beyond
microsecond precision, so a naive `datetime` parse truncates. Store as string or a 100 ns tick.

**Channels are sparse.** The sampled frame carried `0, 2, 3, 4, 5` and no `45`. The decoder must not
assume a fixed channel set per frame.

### OPEN — channel semantics unconfirmed

The conventional map is `0`=RPM, `2`=Speed, `3`=nGear, `4`=Throttle, `5`=Brake, `45`=DRS. A stationary
car at session start decoded as `{'0':0, '2':0, '3':0, '4':104, '5':104}`. Throttle and brake both
reading 104 is inconsistent with a 0–100 throttle and an on/off brake, so either the map is wrong for
this data or these are uncalibrated raw values.

**No feature may depend on channel semantics until this passes the three-layer validation** (decoder vs
FastF1 · reconstruction vs official results · secondary-source triangulation). This is exactly the class
of assumption the validation requirement exists to catch.

### `CurrentTyres` shape

```json
{"Tyres": {"11": {"Compound": "SOFT", "New": true}, "12": {"Compound": "HARD", "New": true}, ...}}
```

Keyed by car number as a string. Compound and new/used are directly observed.

---

## 4b. Full session pulled and decoded — VERIFIED

Probe session: Hungarian GP race, 2026-07-26 (Round 11, the last completed round).
Fetched by `scripts/timing/fetch_session.py`, surveyed by `scripts/timing/survey_session.py`
(validation tooling — the production decode is a Mojo kernel).

**51 artifacts, 28,167,917 bytes (~26.9 MiB)** in `~/.algenta/f1/raw/2026/2026-07-26_Hungarian_Grand_Prix/2026-07-26_Race`,
each with sha256 + byte length + BOM flag in `_ingest_manifest.json`.

Corpus projection: ~27 MiB per race session → ~4 GB for ~155 race sessions, ~10–15 GB including
practice and qualifying. Comfortably local.

### Record counts (full race, 2h37m)

| Feed | Records | | Feed | Records |
|---|---:|---|---|---:|
| `TimingData` | 71,303 | | `TyreStintSeries` | 807 |
| `TimingDataF1` | 40,878 | | `Heartbeat` | 708 |
| `DriverRaceInfo` | 30,428 | | `OvertakeSeries` | 516 |
| `Position.z` | 9,344 | | `DriverList` | 211 |
| `CarData.z` | 9,342 | | `WeatherData` / `…Series` | 157 each |
| `LapSeries` | 1,429 | | `PitLaneTimeCollection` | 90 |
| `TimingStats` | 1,297 | | `RaceControlMessages` | 80 |
| `TimingAppData` | 1,160 | | `LapCount` | 70 |
| `SessionData` | 86 | | `CurrentTyres` | 44 |
| `PitStopSeries` | 34 | | `PitStop` | 33 |
| `TrackStatus` | 12 | | `SessionStatus` | 5 |

Session: *FORMULA 1 AWS HUNGARIAN GRAND PRIX 2026*, Hungaroring, key 11342, 70 laps, **22 drivers**.

### Telemetry — full decode

```
CarData.z  : 9,342 stream lines → 9,342 parsed (zero loss) → 34,884 entries → 767,448 car-samples
             cars-per-entry histogram: {22: 34884} — every entry carries the full field
             span 12:09:11.2456447Z → 14:46:16.9584529Z (9,426 s)
Position.z : 9,344 frames → 786,060 car-position samples
```

**Completeness:** every stream line decoded, and **zero inter-entry gaps above 2 s** across the whole
race. We hold 100% of what the archive publishes. A "sample" is one car × one timestamp × its channels —
the unit of the series, not a subset.

### Sampling is irregular — do not assume a fixed dt

The mean rate (34,884 / 9,426 ≈ 3.70 Hz) understates the nominal rate and hides substantial jitter:

| | interval | implied rate | distance @ 300 km/h |
|---|---|---|---|
| min | 0.155 s | 6.5 Hz | 13 m |
| **p50** | **0.240 s** | **4.17 Hz** | **20 m** |
| p90 | 0.400 s | 2.5 Hz | 33 m |
| p99 | 0.520 s | 1.9 Hz | 43 m |
| max | 1.521 s | 0.7 Hz | 127 m |

Consequences:

1. **No fixed `dt`.** Every derivative (acceleration, braking onset, per-corner energy) must use actual
   timestamps, and its quality varies with the local interval. A resampling step that assumes uniform
   spacing would silently fabricate precision.
2. **This is the quantitative basis for the braking classification.** An F1 braking zone is ~100–150 m.
   At p50 that is 3–5 samples; in the tail a single interval can span the entire zone. Braking-point
   location is therefore *inferred proxy*, not *measured* — a limit set by 20–127 m of spatial
   resolution, not by caution.
3. The cars produce telemetry internally at hundreds of Hz to kHz. The public feed is F1's decimation of
   that signal. We have all of the published signal and none of the underlying one.

### Channel semantics — RESOLVED, after one wrong intermediate conclusion

| ch | Meaning | Range | Distinct | Evidence |
|---|---|---|---|---|
| `0` | **RPM** | 0–13,305 | 9,581 | continuous, plausible 2026 PU ceiling |
| `2` | **Speed (km/h)** | 0–305 | 306 | integer km/h, plausible Hungaroring top speed |
| `3` | **nGear** | 0–8 | 9 | exactly `{0,1,…,8}` — neutral plus 8 gears |
| `4` | **Throttle (%)** | 0–100, plus `104` | 100 | see staleness below |
| `5` | **Brake** | `{0, 100}`, plus `104` | 3 | binary brake, plus `104` |

**Correction.** An earlier revision of this document concluded that `104` was a *session-level*
no-data sentinel confined to pre-session frames. That was wrong. `104` appears in **186,477 of
767,448 car-samples — 24.3%**, spread throughout the race, not clustered at the start.

**`104` marks per-frame staleness.** A contiguous car-1 trace makes the mechanism plain:

```
utc               rpm  spd  gr  ch4  ch5
13:43:25.384     7782   87   2  104  104     <- rpm repeated 8x: no fresh values this frame
13:43:26.064     7782   87   2  104  104
13:43:26.384     8902   87   2   30    0     <- rpm fresh: real throttle 30, brake 0
13:43:29.584    10120  126   3   59  104     <- throttle fresh, brake stale — independently marked
```

So a frame that carries no update for throttle or brake emits `104` for that channel, while
**RPM, speed and gear silently repeat their last value with no marker at all.**

Three consequences, all of which matter more than the original sentinel story:

1. **Masking is channel-specific.** `104` is out of range for throttle (0–100) and brake (`{0,100}`),
   so it is unambiguous there and must be read as *missing*. But `104` is a perfectly legitimate
   **speed** (2,964 occurrences, consistent with ~2,508 expected per distinct value if roughly
   uniform over 0–305) and must **not** be masked. A blanket "mask 104" rule would silently delete
   real speed data.
2. **Missingness is common, not rare** — ~23.9% of brake samples and ~11.7% of throttle samples.
3. **RPM/speed/gear staleness is invisible.** A repeated value cannot be distinguished from a
   genuinely constant one. This is worse than an explicit marker: computing acceleration or braking
   onset across repeated samples yields spurious zeros. The measured p50 interval of 0.240 s is the
   **frame** interval, not the fresh-value interval — the true information rate is lower still.

Point 3 strengthens, quantitatively, why braking-zone location is a class-2 *inferred proxy* deferred
to Gate 5 rather than a measured quantity.

**This does not block the Monza slice.** Every class-1 feature the slice needs — lap and sector times,
gaps, position, compound, tyre age, pit events, track status, lap count — comes from `TimingData`,
`TyreStintSeries`, `PitStop` and `TrackStatus`. `CarData` feeds only the deferred telemetry proxies.

**Channel `45` (DRS) does not exist in 2026 data — count zero.** Consistent with DRS being abolished
under the 2026 regulations. Override/overtake-mode availability appears instead as
`RaceControlMessages` text (`OVERTAKE ENABLED` / `OVERTAKE DISABLED`), i.e. it is a race-control
signal, not a telemetry channel. Any 2026 override modelling reads race control, not `CarData`.

### Pit-loss components are measured, not fitted

`PitStop` is flat and per-stop: `{"RacingNumber","PitStopTime","PitLaneTime","Lap"}`.

```
{"RacingNumber":"18","PitStopTime":"2.1","PitLaneTime":"21.789","Lap":"8"}
{"RacingNumber":"18","PitStopTime":"4.8","PitLaneTime":"24.241","Lap":"37"}
```

33 stops in this race, each with **stationary time** and **total pit-lane time** separately. This is
directly the decomposition the lap-time model needs: `pit_loss` and the right-tailed `σ_pit` slow-stop
distribution can be *fitted from observation* instead of assumed, and the 2.1 s vs 4.8 s spread in one
driver's two stops is exactly the tail the plan warned a symmetric Gaussian would understate.

`PitStopSeries` is the accumulating form: `{"PitTimes":{"<car>":[{"Timestamp","PitStop":{…}}]}}`.

`PitLaneTimeCollection` is a **live transient**: `{"PitTimes":{"<car>":{"RacingNumber","Duration","Lap"}}}`
followed by `{"PitTimes":{"_deleted":["18"]}}`. The `_deleted` sentinel is a delta-semantics
requirement for the state builder — records are added *and retracted*, so naive accumulation is wrong.

### CORRECTION — `OvertakeSeries` is not labelled pairs

An earlier claim in this record and in the plan said `OvertakeSeries` gives "labelled overtake events —
a direct fitting target for the overtake kernel". **That was wrong.** The actual shape is a per-car
*count* series:

```
{"Overtakes":{"81":[{"Timestamp":"2026-07-26T13:03:28.883Z","count":1}]}}
{"Overtakes":{"81":{"1":{"Timestamp":"2026-07-26T13:03:28.899Z","count":1}}}}
```

No overtaker/overtaken pairing. Two different encodings appear in the same stream (list form and
dict-keyed form), and some records carry `count: 21`, whose meaning is unresolved.

Consequence: overtakes stay usable as a **per-car count aggregate** (good for a passes-per-race MAE
check) but pair-level battles must still be reconstructed from position and gap traces. The overtake
kernel therefore does **not** get a free labelled training target, and `OvertakeSeries` reverts from
*directly observed* to a *derived aggregate* in the feature classification.

### Track status — a real VSC in the probe race

```
00:00:00 Yellow → 00:06:07 AllClear → 00:14:56 Yellow → 00:21:37 AllClear
01:49:26 Yellow → 01:49:29 AllClear → 02:05:28 Yellow → 02:05:30 AllClear
02:13:30 Yellow → 02:13:45 VSCDeployed → 02:15:03 VSCEnding → 02:15:14 AllClear
```

Status codes observed: `1` AllClear, `2` Yellow, `6` VSCDeployed, `7` VSCEnding. A full SC code was not
exercised in this race, so the SC path needs a session that contains one before the regime model is
trusted.

### Tyre stints decode cleanly

```
NOR  MEDIUM(17L,new) → HARD(22L,new) → HARD(17L,new) → SOFT(17L)
VER  MEDIUM(14L,new) → HARD(27L,new) → SOFT(32L)
BOR  SOFT(29L,new)   → HARD(40L,new)
```

Compound, stint length and new/used per stint, for all 22 drivers.

### Weather is richer than assumed

`{'AirTemp','Humidity','Pressure','Rainfall','TrackTemp','WindDirection','WindSpeed'}` at ~60 s
cadence, 157 samples. `TrackTemp` (51.3 °C here) is a real input for a future thermal model, and
`Rainfall` is a direct wet/dry regime signal.

---

## 5. Reference paper — PENDING

arXiv:2607.06495. The model spec in the plan was extracted from the PDF; equations, parameter table,
calibration objective and reported accuracy need re-verification against the paper and any published
repository before they are treated as a reproduction baseline for the controlled speed comparison.

## 6. FIA 2026 regulations — PENDING

Needed for Gate 5 only (energy scenario optimizer), not for the Monza slice. MGU-K power, per-lap energy
limit and override-mode thresholds must come from the primary regulation text, not press summaries.

## 7. Sporting rules per target season — PENDING

Mandatory-compound rule and red-flag tyre treatment for each season in the corpus. Required before the
tyre-set feasibility cap can be trusted in the plan optimizer.

## 8. Data-use / retention / trademark terms — PENDING

Blocks publication, not development. Determines whether raw telemetry may be retained, what the
ClickHouse TTL matrix must enforce, and how the artifact may be described.

## 9. Local license, control-plane-offline start — PENDING

Owner-executed. Mint and install, then confirm the runtime starts and stays licensed with the control
plane unreachable and egress restricted to the timing host.

---

## Consequences already folded into the plan

1. Target date corrected; Zandvoort adopted as the Gate 4 live rehearsal.
2. Feed inventory corrected from 20 to 33, with an explicit include/exclude list.
3. Stream format corrected: BOM, CRLF, `HH:MM:SS.mmm` prefix, raw deflate.
4. Corpus discovery must enumerate years; the root index is not a crawl surface.
5. Feature classification updated — compound, new/used, stint history, pit timing and overtakes move
   from *inferred proxy* to *directly observed*.
6. Tyre-inventory contract narrowed: fitted tyres are observed; only **remaining** inventory is
   assumption-driven.
7. Channel semantics recorded as an open validation item rather than an assumption.
