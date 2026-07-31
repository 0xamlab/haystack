"""Invariant 4 — as-of replay must not see corrections that arrived after the decision time.

WHY THIS TEST OUTRANKS EVERY OTHER ONE HERE

A static archive contains corrections that did not exist at the original decision time: revised lap
times, later compound corrections, retrospective stint tables, final classifications. If a snapshot
reconstructed at lap 28 can see any of them, the backtest is contaminated by look-ahead and every
accuracy number already published is meaningless — while looking excellent, because look-ahead makes a
model appear MORE accurate, not less. There is no summary statistic that reveals it. The plan therefore
requires exactly this: inject a future correction into the archive and prove an earlier snapshot's hash
does not change.

WHAT MAKES THIS TEST NON-VACUOUS

Three assertions, and the second and third are what give the first any weight:

  1. a correction timestamped AFTER the watermark must not move the as-of hash;
  2. the SAME correction timestamped BEFORE the watermark MUST move it — otherwise the test would pass
     just as happily against a state machine that ignored the feed entirely, or a hash blind to the
     field being corrected;
  3. the correction must move the FULL-log hash — proving the injected record is well-formed enough to
     reach the state machine at all. A malformed record that gets silently dropped would satisfy (1)
     and could be mistaken for a passing test.

The frozen corpus is never mutated. Every case runs against a copy in a temporary directory, and the
test asserts the original archive's digest is unchanged afterwards.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "timing"))

CORPUS = Path.home() / ".algenta" / "f1" / "raw"
CRLF = "\r\n"


def _session() -> Path:
    """A completed race with a built event log. Skips rather than fails if the corpus is absent."""
    if not CORPUS.exists():
        pytest.skip(f"no corpus at {CORPUS}")
    for d in sorted(CORPUS.glob("*/*/*_Race")):
        if (d / "TimingData.jsonStream").exists() and (d / "_event_log.parquet").exists():
            return d
    pytest.skip("no replayed race session found in the corpus")


def _ms_to_ts(ms: int) -> str:
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, msec = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{msec:03d}"


def _inject(session: Path, at_ms: int, car: str, lap_time: str) -> None:
    """Append a TimingData correction at a chosen feed timestamp.

    The payload rewrites LastLapTime and bumps NumberOfLaps, which is what the state machine keys lap
    emission on — so the record is guaranteed to reach state rather than being a decorative append.
    Records are appended rather than inserted because build_event_log sorts by
    (event_ms, topic order, within-feed index); a later-timestamped record therefore sorts into place.
    """
    payload = (
        '{"Lines":{"' + car + '":{"NumberOfLaps":97,'
        '"LastLapTime":{"Value":"' + lap_time + '"},'
        '"Position":"1"}}}'
    )
    f = session / "TimingData.jsonStream"
    with f.open("ab") as fh:
        fh.write((CRLF + _ms_to_ts(at_ms) + payload).encode("utf-8"))


def _rebuild(session: Path, cutoff_ms: int | None) -> str:
    from build_event_log import build
    from replay_state import replay

    build(session)
    return replay(session, cutoff_ms=cutoff_ms, emit=False)["state_hash"]


@pytest.fixture(scope="module")
def fixture(tmp_path_factory):
    """A copy of one race session, plus a watermark at 60% of its span and a car that is present."""
    import pyarrow.parquet as pq

    src = _session()
    log = pq.read_table(src / "_event_log.parquet").to_pydict()
    span = max(log["event_ms"])
    cutoff = int(span * 0.60)

    dst = tmp_path_factory.mktemp("leak") / src.name
    shutil.copytree(src, dst)
    from build_event_log import build
    from replay_state import replay

    build(dst)
    full = replay(dst, emit=False)
    assert full["laps"] > 50, f"session has too few laps to be a meaningful test: {full['laps']}"
    return {"dir": dst, "cutoff": cutoff, "span": span, "src": src,
            "as_of": replay(dst, cutoff_ms=cutoff, emit=False)["state_hash"],
            "full": full["state_hash"]}


def test_a_future_correction_cannot_change_an_earlier_snapshot(fixture, tmp_path):
    """The load-bearing assertion: a correction that arrived later is invisible to the earlier snapshot."""
    work = tmp_path / "future"
    shutil.copytree(fixture["dir"], work)
    # comfortably after the watermark, and inside the log's span so it is not sorted off the end
    _inject(work, int(fixture["cutoff"] + 0.2 * fixture["span"]), "44", "1:11.111")

    after_as_of = _rebuild(work, fixture["cutoff"])
    after_full = _rebuild(work, None)

    assert after_as_of == fixture["as_of"], (
        "LOOK-AHEAD: a correction timestamped after the watermark changed the as-of snapshot.\n"
        f"  before {fixture['as_of']}\n  after  {after_as_of}\n"
        "Every backtest number is contaminated until this holds."
    )
    # non-vacuity: the injection must be effective, or the assertion above proves nothing
    assert after_full != fixture["full"], (
        "the injected correction did not change the FULL-log state either, so it never reached the "
        "state machine and the leakage assertion is vacuous"
    )


def test_a_past_correction_does_change_that_snapshot(fixture, tmp_path):
    """The control. Without this the test would pass against a state machine that ignored the feed."""
    work = tmp_path / "past"
    shutil.copytree(fixture["dir"], work)
    _inject(work, int(fixture["cutoff"] * 0.5), "44", "1:11.111")

    after_as_of = _rebuild(work, fixture["cutoff"])
    assert after_as_of != fixture["as_of"], (
        "a correction timestamped BEFORE the watermark did not change the as-of snapshot. The "
        "watermark is not the thing being tested — either the state machine ignores TimingData or the "
        "hash is blind to the corrected field, and the leakage test above is meaningless."
    )


@pytest.mark.parametrize("frac", [0.25, 0.5, 0.75])
def test_the_watermark_is_monotone_in_information(fixture, tmp_path, frac):
    """A snapshot at T must be reproducible from a log that has grown past T.

    This is the property a backtest actually relies on: the archive we replay today is the FINAL
    archive, so every earlier snapshot in it must equal what would have been reconstructed live.
    """
    work = tmp_path / f"mono-{frac}"
    shutil.copytree(fixture["dir"], work)
    cut = int(fixture["span"] * frac)
    before = _rebuild(work, cut)
    # append several corrections strictly after this cutoff
    for k, car in enumerate(("1", "16", "63")):
        _inject(work, int(cut + (k + 1) * 0.05 * fixture["span"]), car, "1:09.999")
    after = _rebuild(work, cut)
    assert after == before, (
        f"snapshot at {frac:.0%} of the session moved when LATER records were appended:\n"
        f"  {before} -> {after}"
    )


@pytest.mark.parametrize("frac", [0.2, 0.4, 0.6])
def test_an_as_of_snapshot_cannot_contain_the_finish(fixture, frac):
    """The hole the append-a-later-record test could not see.

    For an archived COMPLETED session the keyframe of an evolving topic is the POST-SESSION snapshot --
    TimingData.json for Bahrain 2019 carries NumberOfLaps=57 and Position=1 for the winner. Keyframes are
    placed at event_ms = 0, before everything, so feeding them to the state machine put the FINAL
    CLASSIFICATION into every as-of snapshot at every lap.

    Nothing failed. The monotonicity and future-correction tests above all PASSED against it, because
    appending a later record genuinely did not change the snapshot -- the snapshot was already final. The
    symptom was an in-race "current running order" baseline scoring a Brier of exactly 0.00000 and a BSS
    of +1.000 over 117 held-out snapshots. Only an impossible number gave it away.

    So this asserts the property directly: a snapshot taken partway through a race must not know how many
    laps the race lasted.
    """
    import pyarrow.parquet as pq
    from replay_state import replay

    session = fixture["dir"]
    complete0 = replay(session, cutoff_ms=None, emit=False)
    total = complete0["max_lap"]
    # A fraction of RACE DISTANCE, not of the archive span: the archive begins well before lights out,
    # so 20% of the span lands before the race has started and no lap exists to test.
    target = max(2, int(total * frac))
    rows = pq.read_table(session / "_event_log.parquet").to_pydict()
    cut = None
    for i in range(len(rows["event_ms"])):
        if rows["is_keyframe"][i] or rows["topic"][i] != "TimingData":
            continue
        if f'"NumberOfLaps":{target}' in rows["payload"][i]:
            cut = rows["event_ms"][i]
            break
    if cut is None:
        cut = int(fixture["span"] * (0.35 + 0.5 * frac))

    at_cut = replay(session, cutoff_ms=cut, emit=False)
    complete = replay(session, cutoff_ms=None, emit=False)

    assert at_cut["max_lap"] > 0, (
        f"no laps at all at the {frac:.0%} race-distance watermark (target lap {target}) -- the cut "
        f"landed before the race started, so the test cannot say anything"
    )
    assert at_cut["max_lap"] < complete["max_lap"], (
        f"an as-of snapshot at {frac:.0%} of race distance reached lap {at_cut['max_lap']} of "
        f"{complete['max_lap']} -- it knows the race distance, so it has seen the finish. "
        f"Evolving-topic keyframes are leaking post-session state into the as-of path."
    )
    assert at_cut["skipped_keyframes"] > 0, (
        "no keyframes were skipped, so the exclusion is not active and this test would pass only by "
        "luck on a session whose keyframe happened to be empty"
    )


def test_the_frozen_corpus_was_not_mutated(fixture):
    """A test that edits the archive it is validating would invalidate the corpus it was proving."""
    from build_event_log import build

    digest = build(fixture["src"])["logical_digest"]
    from replay_state import replay

    replay(fixture["src"], emit=False)
    assert build(fixture["src"])["logical_digest"] == digest
    assert not (fixture["src"] / "TimingData.jsonStream").read_bytes().endswith(b'"Position":"1"}}}')
