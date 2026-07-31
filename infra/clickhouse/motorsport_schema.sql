-- Motorsport corpus schema — f1_current (mutable development corpus).
--
-- Frozen decisions this encodes (see docs/motorsport/FROZEN_SPECS.md):
--
--   PARTITION BY (season, session_key)   one session is the swap unit, because a session is the
--                                        unit a decoder fix invalidates
--   ORDER BY (... event_time, source_sequence)
--                                        source_sequence is a MANDATORY final tie-break: multiple
--                                        records share one event_time, and deterministic replay must
--                                        never depend on unspecified ordering among equal timestamps.
--                                        session_key is NOT led with — it is constant in a partition.
--
-- Frozen-corpus counterpart: f1_frozen_<version>.* holds the same shapes but is immutable after
-- preregistration — no REPLACE PARTITION, mutation, or benchmark-input-altering TTL.
--
-- RETENTION IS DELIBERATELY ABSENT. The plan's retention matrix is driven by a legal finding that is
-- still pending; inventing a period now would be a guess dressed as policy. TTL arrives as
-- ALTER TABLE ... MODIFY TTL once that finding lands, together with the deletion-manifest job that
-- proves removal of the external artifacts ClickHouse TTL cannot touch.
--
-- Telemetry sort key is (event_time, car_number, source_sequence), NOT car_number-first. Decided on
-- evidence rather than preference: measured 1,077,254 B against 1,996,100 B, i.e. 1.85x smaller,
-- because all 22 cars share each frame timestamp so time-first makes consecutive deltas zero. The
-- access pattern settled it -- the as-of state builder reads the WHOLE FIELD at each lap
-- (state_as_of in pitwall_tui.py), which is exactly time-ordered, and Invariant 4 requires processing
-- in (event_time, source_sequence) order anyway. Per-car traces cost 10.5 ms against 3.1 ms, which
-- matters only to the deferred Gate 5 proxies and is far from any bottleneck at 767k rows/session.
--
-- Timestamp codec is Delta, NOT DoubleDelta. Measured on a real session (767,448 rows): Delta costs
-- 1.611 B/row against DoubleDelta's 2.943 -- 1.8x better. DoubleDelta assumes near-constant second
-- differences, i.e. a regular clock; this feed is irregular (p50 0.240 s, p90 0.400 s, max 1.521 s),
-- so DoubleDelta actively hurts. Plain ZSTD(3) also beat DoubleDelta in the event_time-sorted case.
--
-- Timestamps: source Utc carries 7 fractional digits (100 ns ticks). DateTime64(9) represents those
-- exactly; a microsecond type would truncate and lose ordering information.

CREATE DATABASE IF NOT EXISTS f1_current;

-- ── dimensions ───────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS f1_current.driver_dim
(
    season       UInt16,
    session_key  UInt32,
    car_number   UInt16,
    tla          LowCardinality(String),
    full_name    String,
    team_name    LowCardinality(String),
    team_colour  LowCardinality(String)
)
ENGINE = ReplacingMergeTree
PARTITION BY (season, session_key)
ORDER BY (car_number);

-- ── operational spine ────────────────────────────────────────────────────────
-- Multi-table session replacement is coordinated through this manifest. REPLACE PARTITION is atomic
-- per table only, so a session spanning many tables is not exposed as complete until every table has
-- validated and an `active` row lands here for that ingest_generation.

CREATE TABLE IF NOT EXISTS f1_current.corpus_session_manifest
(
    manifest_id             String,          -- SHA256(corpus_version || session_key || ingest_generation)
    corpus_version          LowCardinality(String),
    season                  UInt16,
    session_key             UInt32,
    session_path            String,
    session_type            LowCardinality(String),
    ingest_generation       UInt32,
    status                  Enum8('loading'=1,'validated'=2,'active'=3,'failed'=4,'superseded'=5),
    archive_status          LowCardinality(String),   -- must be 'Complete' before activation
    decoder_version         LowCardinality(String),
    state_builder_version   LowCardinality(String),
    feeds_available         Array(LowCardinality(String)),
    providers_available     Array(LowCardinality(String)),
    raw_artifact_sha256     String,
    parquet_artifact_sha256 String,
    expected_row_count      UInt64,
    actual_row_count        UInt64,
    min_event_time          DateTime64(9, 'UTC'),
    max_event_time          DateTime64(9, 'UTC'),
    canonical_logical_digest String,
    schema_hash             String,
    started_at              DateTime64(3, 'UTC'),
    validated_at            Nullable(DateTime64(3, 'UTC')),
    activated_at            Nullable(DateTime64(3, 'UTC')),
    failure_reason          String
)
ENGINE = ReplacingMergeTree(started_at)
ORDER BY (corpus_version, session_key, ingest_generation);

-- ── bronze index ─────────────────────────────────────────────────────────────
-- Raw bytes stay on disk under the immutable ingest root; ClickHouse indexes them.

CREATE TABLE IF NOT EXISTS f1_current.raw_frame_index
(
    season          UInt16,
    session_key     UInt32,
    topic           LowCardinality(String),
    source_sequence UInt64          CODEC(DoubleDelta, ZSTD(3)),
    feed_timestamp  String,                                     -- raw HH:MM:SS.mmm prefix, verbatim
    event_time      DateTime64(9, 'UTC') CODEC(Delta, ZSTD(3)),
    payload_bytes   UInt32          CODEC(T64, ZSTD(3)),
    payload_sha256  String,
    artifact_path   String
)
ENGINE = MergeTree
PARTITION BY (season, session_key)
ORDER BY (topic, event_time, source_sequence);

-- ── car telemetry — the large table ──────────────────────────────────────────
-- ~767k rows per race session.
--
-- throttle/brake are Nullable because 104 marks per-frame staleness for exactly those two channels
-- (24.3% of samples carry one). 104 is NOT masked in speed — it is a legitimate km/h value there, and
-- a blanket mask would delete real data.
--
-- rpm/speed/gear have NO staleness marker: the feed silently repeats the last value. repeat_run_length
-- is Mojo-derived so downstream can tell a stale value from a genuinely constant one; derivatives
-- computed across repeats would otherwise yield spurious zeros.

CREATE TABLE IF NOT EXISTS f1_current.car_telemetry
(
    season            UInt16,
    session_key       UInt32,
    car_number        UInt16               CODEC(T64, ZSTD(3)),
    event_time        DateTime64(9, 'UTC') CODEC(Delta, ZSTD(3)),
    source_sequence   UInt64               CODEC(DoubleDelta, ZSTD(3)),
    rpm               UInt16               CODEC(Delta, ZSTD(3)),
    speed_kph         UInt16               CODEC(Delta, ZSTD(3)),
    gear              UInt8                CODEC(T64, ZSTD(3)),
    throttle_pct      Nullable(UInt8)      CODEC(T64, ZSTD(3)),
    brake             Nullable(UInt8)      CODEC(T64, ZSTD(3)),
    repeat_run_length UInt8                CODEC(T64, ZSTD(3))
)
ENGINE = MergeTree
PARTITION BY (season, session_key)
ORDER BY (event_time, car_number, source_sequence);

CREATE TABLE IF NOT EXISTS f1_current.position_samples
(
    season          UInt16,
    session_key     UInt32,
    car_number      UInt16               CODEC(T64, ZSTD(3)),
    event_time      DateTime64(9, 'UTC') CODEC(Delta, ZSTD(3)),
    source_sequence UInt64               CODEC(DoubleDelta, ZSTD(3)),
    status          LowCardinality(String),
    x               Int32                CODEC(Delta, ZSTD(3)),
    y               Int32                CODEC(Delta, ZSTD(3)),
    z               Int32                CODEC(Delta, ZSTD(3))
)
ENGINE = MergeTree
PARTITION BY (season, session_key)
ORDER BY (event_time, car_number, source_sequence);

-- ── derived (Mojo-emitted) race records ─────────────────────────────────────

CREATE TABLE IF NOT EXISTS f1_current.laps
(
    season           UInt16,
    session_key      UInt32,
    car_number       UInt16               CODEC(T64, ZSTD(3)),
    lap_number       UInt16               CODEC(T64, ZSTD(3)),
    event_time       DateTime64(9, 'UTC') CODEC(Delta, ZSTD(3)),
    source_sequence  UInt64               CODEC(DoubleDelta, ZSTD(3)),
    lap_time_s       Nullable(Float32)    CODEC(Gorilla, ZSTD(3)),
    sector1_s        Nullable(Float32)    CODEC(Gorilla, ZSTD(3)),
    sector2_s        Nullable(Float32)    CODEC(Gorilla, ZSTD(3)),
    sector3_s        Nullable(Float32)    CODEC(Gorilla, ZSTD(3)),
    compound         LowCardinality(String),
    tyre_age         UInt8                CODEC(T64, ZSTD(3)),
    stint_index      UInt8                CODEC(T64, ZSTD(3)),
    track_regime     UInt8                CODEC(T64, ZSTD(3)),
    is_green_lap     UInt8                CODEC(T64, ZSTD(3)),
    is_in_lap        UInt8                CODEC(T64, ZSTD(3)),
    is_out_lap       UInt8                CODEC(T64, ZSTD(3)),
    position         UInt8                CODEC(T64, ZSTD(3)),
    gap_to_leader_s  Nullable(Float32)    CODEC(Gorilla, ZSTD(3)),
    interval_ahead_s Nullable(Float32)    CODEC(Gorilla, ZSTD(3))
)
ENGINE = MergeTree
PARTITION BY (season, session_key)
ORDER BY (car_number, lap_number, source_sequence);

CREATE TABLE IF NOT EXISTS f1_current.stints
(
    season       UInt16,
    session_key  UInt32,
    car_number   UInt16 CODEC(T64, ZSTD(3)),
    stint_index  UInt8  CODEC(T64, ZSTD(3)),
    compound     LowCardinality(String),
    is_new       UInt8  CODEC(T64, ZSTD(3)),
    lap_start    UInt16 CODEC(T64, ZSTD(3)),
    lap_end      UInt16 CODEC(T64, ZSTD(3)),
    total_laps   UInt16 CODEC(T64, ZSTD(3)),
    tyre_age_at_start UInt8 CODEC(T64, ZSTD(3))
)
ENGINE = MergeTree
PARTITION BY (season, session_key)
ORDER BY (car_number, stint_index);

-- Pit events carry the provider, because official PitStop exists only from 2025 and the three
-- available sources disagree on how many stops occurred (33 / 44 / 45 for the probe race). The
-- inclusion rule must be explicit in the data, not implicit in whichever loader ran.
CREATE TABLE IF NOT EXISTS f1_current.pit_events
(
    season           UInt16,
    session_key      UInt32,
    car_number       UInt16               CODEC(T64, ZSTD(3)),
    lap_number       UInt16               CODEC(T64, ZSTD(3)),
    event_time       DateTime64(9, 'UTC') CODEC(Delta, ZSTD(3)),
    source_sequence  UInt64               CODEC(DoubleDelta, ZSTD(3)),
    provider         LowCardinality(String),   -- official | openf1 | jolpica
    stationary_s     Nullable(Float32)    CODEC(Gorilla, ZSTD(3)),
    pit_lane_s       Nullable(Float32)    CODEC(Gorilla, ZSTD(3)),
    under_neutralisation UInt8            CODEC(T64, ZSTD(3)),
    reconciliation   LowCardinality(String)    -- matched | official_only | provider_only | unresolved
)
ENGINE = MergeTree
PARTITION BY (season, session_key)
ORDER BY (car_number, lap_number, provider, source_sequence);

CREATE TABLE IF NOT EXISTS f1_current.track_status
(
    season          UInt16,
    session_key     UInt32,
    event_time      DateTime64(9, 'UTC') CODEC(Delta, ZSTD(3)),
    source_sequence UInt64               CODEC(DoubleDelta, ZSTD(3)),
    status_code     UInt8                CODEC(T64, ZSTD(3)),   -- 1 AllClear 2 Yellow 4 SC 6 VSC 7 VSCEnding
    message         LowCardinality(String),
    is_unknown_code UInt8                CODEC(T64, ZSTD(3))    -- codes 3/5 unobserved: surface, never map
)
ENGINE = MergeTree
PARTITION BY (season, session_key)
ORDER BY (event_time, source_sequence);

CREATE TABLE IF NOT EXISTS f1_current.race_control
(
    season          UInt16,
    session_key     UInt32,
    event_time      DateTime64(9, 'UTC') CODEC(Delta, ZSTD(3)),
    source_sequence UInt64               CODEC(DoubleDelta, ZSTD(3)),
    lap_number      Nullable(UInt16)     CODEC(T64, ZSTD(3)),
    category        LowCardinality(String),
    flag            LowCardinality(String),
    scope           LowCardinality(String),
    sector          Nullable(UInt8)      CODEC(T64, ZSTD(3)),
    mode            LowCardinality(String),
    car_number      Nullable(UInt16)     CODEC(T64, ZSTD(3)),
    message         String
)
ENGINE = MergeTree
PARTITION BY (season, session_key)
ORDER BY (event_time, source_sequence);

CREATE TABLE IF NOT EXISTS f1_current.weather
(
    season          UInt16,
    session_key     UInt32,
    event_time      DateTime64(9, 'UTC') CODEC(Delta, ZSTD(3)),
    source_sequence UInt64               CODEC(DoubleDelta, ZSTD(3)),
    air_temp_c      Float32 CODEC(Gorilla, ZSTD(3)),
    track_temp_c    Float32 CODEC(Gorilla, ZSTD(3)),
    humidity_pct    Float32 CODEC(Gorilla, ZSTD(3)),
    pressure_mbar   Float32 CODEC(Gorilla, ZSTD(3)),
    wind_speed_ms   Float32 CODEC(Gorilla, ZSTD(3)),
    wind_direction  UInt16  CODEC(T64, ZSTD(3)),
    rainfall        UInt8   CODEC(T64, ZSTD(3))
)
ENGINE = MergeTree
PARTITION BY (season, session_key)
ORDER BY (event_time, source_sequence);

-- Outcome truth. provider recorded because DNF conventions differ: Jolpica ranks retirees into
-- positions by laps completed descending (matching the frozen utility), OpenF1 returns NULL.
CREATE TABLE IF NOT EXISTS f1_current.classification
(
    season         UInt16,
    session_key    UInt32,
    car_number     UInt16 CODEC(T64, ZSTD(3)),
    provider       LowCardinality(String),
    position       Nullable(UInt8) CODEC(T64, ZSTD(3)),
    ranked_position UInt8 CODEC(T64, ZSTD(3)),   -- frozen-utility ranking, DNFs included
    completed_laps UInt16 CODEC(T64, ZSTD(3)),
    points         Float32 CODEC(Gorilla, ZSTD(3)),
    duration_s     Nullable(Float64) CODEC(Gorilla, ZSTD(3)),
    gap_to_leader_s Nullable(Float32) CODEC(Gorilla, ZSTD(3)),
    grid_position  Nullable(UInt8) CODEC(T64, ZSTD(3)),
    status         LowCardinality(String),
    dnf            UInt8 CODEC(T64, ZSTD(3)),
    dns            UInt8 CODEC(T64, ZSTD(3)),
    dsq            UInt8 CODEC(T64, ZSTD(3))
)
ENGINE = MergeTree
PARTITION BY (season, session_key)
ORDER BY (car_number, provider);

-- ── prospective decision evidence (written only by the outbox shipper) ───────
-- Never written by the decision runtime, which holds no route here. Row hashes chain into a per-session
-- Merkle root whose signed head is published externally before the outcome is known — ClickHouse gives
-- queryability, the external digest gives non-repudiation.

CREATE TABLE IF NOT EXISTS f1_current.decision_snapshots
(
    decision_id                String,   -- SHA256 over the coordinates below (see FROZEN_SPECS)
    season                     UInt16,
    session_key                UInt32,
    decision_event_time        DateTime64(9, 'UTC') CODEC(Delta, ZSTD(3)),
    event_time_watermark       DateTime64(9, 'UTC') CODEC(DoubleDelta, ZSTD(3)),
    ingest_sequence_watermark  UInt64 CODEC(DoubleDelta, ZSTD(3)),
    state_hash                 String,
    source_event_log_hash      String,
    config_hash                String,
    source_commit              LowCardinality(String),
    corpus_version             LowCardinality(String),
    rng_version                LowCardinality(String),
    objective_version          LowCardinality(String),
    master_seed_commitment     String,
    focal_car                  UInt16 CODEC(T64, ZSTD(3)),
    target_rival               UInt16 CODEC(T64, ZSTD(3)),
    lap_number                 UInt16 CODEC(T64, ZSTD(3)),
    laps_remaining             UInt16 CODEC(T64, ZSTD(3)),
    replication_count          UInt32 CODEC(T64, ZSTD(3)),
    simulation_latency_ms      Float32 CODEC(Gorilla, ZSTD(3)),
    row_hash                   String,
    chain_hash                 String,
    created_at                 DateTime64(3, 'UTC')
)
ENGINE = MergeTree
PARTITION BY (season, session_key)
ORDER BY (session_key, decision_event_time, decision_id);

CREATE TABLE IF NOT EXISTS f1_current.option_boards
(
    decision_id            String,
    season                 UInt16,
    session_key            UInt32,
    option_label           LowCardinality(String),   -- stay | box_now | box_plus_1 | box_plus_2
    p_ahead                Float32 CODEC(Gorilla, ZSTD(3)),
    delta_vs_stay          Float32 CODEC(Gorilla, ZSTD(3)),
    ci_low_simultaneous    Float32 CODEC(Gorilla, ZSTD(3)),
    ci_high_simultaneous   Float32 CODEC(Gorilla, ZSTD(3)),
    expected_position      Float32 CODEC(Gorilla, ZSTD(3)),
    p_win                  Float32 CODEC(Gorilla, ZSTD(3)),
    p_podium               Float32 CODEC(Gorilla, ZSTD(3)),
    pit_loss_total_s       Float32 CODEC(Gorilla, ZSTD(3)),
    feasible               UInt8   CODEC(T64, ZSTD(3)),
    tyre_inventory_source  LowCardinality(String),   -- observed | manual | inferred | unknown
    is_recommended         UInt8   CODEC(T64, ZSTD(3)),
    verdict                Enum8('recommended'=1,'inconclusive'=2,'rejected'=3)
)
ENGINE = MergeTree
PARTITION BY (season, session_key)
ORDER BY (session_key, decision_id, option_label);
