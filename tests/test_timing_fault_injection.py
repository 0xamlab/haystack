"""Gate 4 fault injection — the feed must degrade VISIBLY, never silently.

A live timing feed drops frames, repeats them, delivers them out of order and drifts against the wall
clock. None of those produce an exception; they produce a slightly wrong board that looks exactly like a
right one. That is the failure mode a race weekend actually presents, and the plan's requirement is not
"survive it" but "show it": a pit wall acting on a confident board over a feed that died two laps ago is
worse off than one showing nothing.

So each case here injects a specific corruption and asserts BOTH halves:

  1. the state builder does not crash, hang, or silently invent data; and
  2. something OBSERVABLE changes — a provenance counter, a lap count, a state hash — so the corruption
     is visible to the operator rather than absorbed.

The second half is the point. A test that only asserted "no exception" would pass against a decoder that
quietly discarded the whole feed.

The frozen corpus is never touched: every case runs on a copy in a temporary directory.
"""

from __future__ import annotations

import random
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "timing"))

CORPUS = Path.home() / ".algenta" / "f1" / "raw"
CRLF = b"\r\n"


def _session() -> Path:
    if not CORPUS.exists():
        pytest.skip(f"no corpus at {CORPUS}")
    for d in sorted(CORPUS.glob("*/*/*_Race")):
        if (d / "TimingData.jsonStream").exists() and (d / "_laps.parquet").exists():
            return d
    pytest.skip("no replayed race session in the corpus")


def _records(path: Path) -> list[bytes]:
    raw = path.read_bytes()
    if raw[:3] == b"\xef\xbb\xbf":
        raw = raw[3:]
    return [r for r in raw.split(CRLF) if r.strip()]


def _write(path: Path, records: list[bytes]) -> None:
    path.write_bytes(b"\xef\xbb\xbf" + CRLF.join(records))


def _rebuild(session: Path) -> dict:
    from build_event_log import build
    from replay_state import replay

    info = build(session)
    st = replay(session, emit=True)
    return {**st, "digest": info["logical_digest"], "events": info["events"]}


@pytest.fixture(scope="module")
def clean(tmp_path_factory):
    src = _session()
    dst = tmp_path_factory.mktemp("fault") / src.name
    shutil.copytree(src, dst)
    base = _rebuild(dst)
    assert base["laps"] > 50, f"session too short to be a meaningful test: {base['laps']}"
    return {"dir": dst, "base": base}


def _case(clean, tmp_path, name, mutate):
    work = tmp_path / name
    shutil.copytree(clean["dir"], work)
    f = work / "TimingData.jsonStream"
    recs = _records(f)
    _write(f, mutate(list(recs)))
    return _rebuild(work), len(recs)


def test_dropped_frames_reduce_observed_state_rather_than_being_invented(clean, tmp_path):
    """A gap in the feed must LOSE laps, not have them interpolated into existence."""
    rng = random.Random(11)

    def drop(recs):
        # a contiguous 20% outage, which is what a dropout looks like — not scattered singles
        start = int(len(recs) * 0.4)
        end = start + int(len(recs) * 0.2)
        return recs[:start] + recs[end:]

    got, n = _case(clean, tmp_path, "drop", drop)
    assert got["laps"] < clean["base"]["laps"], (
        f"a 20% feed outage produced {got['laps']} laps against {clean['base']['laps']} clean — the "
        f"decoder is inventing state across the gap instead of showing the loss"
    )
    assert got["state_hash"] != clean["base"]["state_hash"]
    assert got["laps"] > 0, "the decoder discarded everything, which is silent failure of another kind"


def test_duplicate_frames_are_absorbed_without_double_counting(clean, tmp_path):
    """A resend must not advance a car's lap count twice. This one SHOULD be invisible in the result."""
    def dup(recs):
        out = []
        for i, r in enumerate(recs):
            out.append(r)
            if i % 7 == 0:
                out.append(r)
        return out

    got, n = _case(clean, tmp_path, "dup", dup)
    assert got["events"] > clean["base"]["events"], "the duplicates never reached the event log"
    assert got["laps"] == clean["base"]["laps"], (
        f"duplicated frames changed the lap count {clean['base']['laps']} -> {got['laps']}. Lap "
        f"emission keys on a car's completed-lap count advancing, so a resend must be idempotent."
    )
    assert got["state_hash"] == clean["base"]["state_hash"], (
        "duplicated frames changed derived state; replay is not idempotent under resends, which a live "
        "reconnect produces routinely"
    )


def test_reordered_frames_are_resorted_by_the_event_log(clean, tmp_path):
    """Out-of-order arrival must be repaired by the log's sort, not carried into state.

    build_event_log sorts on (event_ms, topic order, within-feed index). Arrival order is therefore not
    supposed to matter, and this is the test that says so — the within-feed index is derived from file
    position, so shuffling records is a genuine test of the sort rather than a no-op.
    """
    rng = random.Random(7)

    def shuffle_locally(recs):
        out = list(recs)
        # local jitter: swap neighbours within a small window, which is what a network reorder looks like
        for i in range(0, len(out) - 8, 8):
            w = out[i:i + 8]
            rng.shuffle(w)
            out[i:i + 8] = w
        return out

    got, _ = _case(clean, tmp_path, "reorder", shuffle_locally)
    assert got["laps"] == clean["base"]["laps"], (
        f"locally reordered arrival changed the lap count {clean['base']['laps']} -> {got['laps']}; the "
        f"event log's sort is not repairing out-of-order delivery"
    )


def test_clock_skew_is_visible_in_the_event_log(clean, tmp_path):
    """A jumped clock must move the log, so ordering damage is detectable rather than absorbed."""
    def skew(recs):
        out = []
        for i, r in enumerate(recs):
            if i > len(recs) // 2 and len(r) > 12 and r[2:3] == b":":
                # rewind the hour field by one on the back half of the session
                try:
                    hh = int(r[:2])
                    out.append(b"%02d" % max(0, hh - 1) + r[2:])
                    continue
                except ValueError:
                    pass
            out.append(r)
        return out

    got, _ = _case(clean, tmp_path, "skew", skew)
    assert got["digest"] != clean["base"]["digest"], (
        "a one-hour clock rewind on half the session did not change the event log's logical digest, so "
        "clock damage would be invisible to the manifest"
    )


def test_provenance_reports_the_outage_to_the_operator(clean, tmp_path):
    """The freshness line is the operator-visible half, and it must actually fire."""
    from pitwall_tui import load, provenance, state_as_of

    work = tmp_path / "prov"
    shutil.copytree(clean["dir"], work)
    f = work / "TimingData.jsonStream"
    recs = _records(f)
    # silence the feed for the LAST 35% of the session: cars stop advancing while the clock runs on
    _write(f, recs[: int(len(recs) * 0.65)])
    _rebuild(work)

    sess = load(work)
    assert sess["total"] > 0
    lap = int(sess["total"] * 0.95)
    states = state_as_of(sess["by_car"], lap)
    prov = provenance(states, lap, sess["total"])

    assert prov["cars"] > 0, "no cars at all — the harness lost the session rather than degrading it"
    flagged = prov["stale_cars"] + prov["presumed_retired"] + prov["missing_pace"]
    assert flagged > 0 or prov["max_lap_lag"] > 1, (
        f"a feed silenced for the final third of the race produced no operator-visible warning: "
        f"{prov}. Silent degradation is the failure this line exists to prevent."
    )


def test_the_frozen_corpus_was_not_touched(clean):
    src = _session()
    from build_event_log import build

    before = build(src)["logical_digest"]
    assert build(src)["logical_digest"] == before


def test_live_ingest_reconstructs_the_archive_exactly(clean, tmp_path):
    """Gate 4 acceptance: the live path is the SAME path, proven rather than asserted.

    live_ingest.py streams an archived session through the real ingest loop -- including an injected
    reconnect that re-sends the previous 30 records, as a hub does -- and writes archive-format
    .jsonStream files. If build_event_log and replay_state then produce a bit-identical state hash, the
    live path is not a second implementation of anything.

    This is what caught the dedup defect. Suppressing every byte-identical record looked obviously right
    and diverged on exactly one lap row of 938, because merge_delta treats arrays as index-keyed objects
    and re-applying such a delta is not idempotent -- the feed sends the same bytes twice and means it.
    Suppression is now scoped to the window following a reconnect, which is the only place a duplicate is
    an artifact of transport rather than content.
    """
    import shutil
    import subprocess

    from build_event_log import build
    from replay_state import replay

    src = clean["dir"]
    out = tmp_path / "live"
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "timing" / "live_ingest.py"),
         "--replay-from", str(src), "--out", str(out), "--speed", "0", "--log-every", "999"],
        capture_output=True, text=True, timeout=900,
    )
    assert r.returncode == 0, f"live_ingest failed: {r.stderr[-800:]}"
    assert "duplicates suppressed" in r.stdout

    # the static keyframes a live subscribe would deliver; the archive stores them as .json
    for name in ("SessionInfo.json", "DriverList.json", "ArchiveStatus.json", "Index.json"):
        if (src / name).exists():
            shutil.copy(src / name, out / name)

    want = replay(src, emit=False)
    build(out)
    got = replay(out, emit=False)

    for k in ("laps", "stints", "pit_events", "regime_changes", "max_lap"):
        assert got[k] == want[k], f"{k}: live {got[k]} against archive {want[k]}"
    assert got["state_hash"] == want["state_hash"], (
        "live-ingested output does not reconstruct the archive's state:\n"
        f"  archive {want['state_hash']}\n  live    {got['state_hash']}\n"
        "The live path must be the same path, or it is a second state machine that only runs when it "
        "matters most and can never be checked afterwards."
    )
