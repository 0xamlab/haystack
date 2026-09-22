"""algenta_spaces.killswitch — fail open for reads, fail closed for spend, with a fake fetch."""

from __future__ import annotations

import json
import threading

import pytest
from algenta_spaces import killswitch
from algenta_spaces.killswitch import FetchResult, KillSwitch

URL = "https://huggingface.co/datasets/thyn-ai/spaces-flags/resolve/main/flags.json"


def body(flags: dict[str, object], *, nested: bool = False) -> bytes:
    return json.dumps({"flags": flags} if nested else flags).encode()


class FakeFetch:
    """Answers from a script; each entry is a `FetchResult` or an exception to raise."""

    def __init__(self, *script: FetchResult | BaseException) -> None:
        self.script = list(script)
        self.calls: list[tuple[str, str | None]] = []
        self.event = threading.Event()

    def __call__(self, url: str, etag: str | None) -> FetchResult:
        self.calls.append((url, etag))
        self.event.set()
        item = self.script.pop(0) if len(self.script) > 1 else self.script[0]
        if isinstance(item, BaseException):
            raise item
        return item


def test_refresh_parses_flags_and_sends_the_etag_back():
    fetch = FakeFetch(
        FetchResult(200, body({"provider": True, "gpu": False, "kernels": True}), 'W/"v1"'),
        FetchResult(304, None, 'W/"v1"'),
    )
    ks = KillSwitch(URL, fetch=fetch, clock=lambda: 1_790_000_000.0)
    assert ks.refresh() is True
    assert ks.flags() == {"provider": True, "gpu": False, "kernels": True}
    assert ks.enabled("provider") and ks.enabled("kernels") and not ks.enabled("gpu")
    assert ks.refresh() is True  # 304 keeps the flags
    assert fetch.calls == [(URL, None), (URL, 'W/"v1"')]
    assert ks.flags()["gpu"] is False
    snap = ks.snapshot()
    assert (snap["polls"], snap["missed"], snap["degraded"], snap["spend_locked"]) == (
        2,
        0,
        False,
        False,
    )
    assert snap["etag"] == 'W/"v1"'
    assert snap["last_ok_utc"].endswith("UTC")
    assert snap["spend_features"] == ["gpu", "provider"]
    assert snap["running"] is False


def test_parse_flags_accepts_flat_or_nested_and_ignores_non_booleans():
    assert killswitch.parse_flags(body({"a": True, "b": 1, "c": "yes"})) == {"a": True}
    assert killswitch.parse_flags(body({"a": False}, nested=True)) == {"a": False}
    with pytest.raises(ValueError):
        killswitch.parse_flags(b"[true]")
    with pytest.raises(ValueError):
        killswitch.parse_flags(b"not json")


def test_reads_fail_open_and_spend_fails_closed_after_max_missed_polls():
    fetch = FakeFetch(
        FetchResult(200, body({"provider": True, "gpu": True, "leaderboard": False}), None),
        OSError("network down"),
    )
    ks = KillSwitch(URL, fetch=fetch, max_missed=3)
    assert ks.refresh()
    for missed in range(1, 4):  # three misses: last known values stand
        assert ks.refresh() is False
        assert ks.degraded and not ks.spend_locked
        assert ks.snapshot()["missed"] == missed
        assert ks.enabled("provider") and ks.enabled("gpu")
        assert ks.enabled("kernels")  # unknown read feature: on
        assert not ks.enabled("leaderboard")  # last known read value: kept
    assert ks.refresh() is False  # the fourth miss closes the spend lanes
    assert ks.spend_locked
    assert not ks.enabled("provider") and not ks.enabled("gpu")
    assert ks.enabled("kernels") and not ks.enabled("leaderboard")
    assert ks.snapshot()["last_error"] == "OSError: network down"


def test_spend_features_recover_when_a_poll_succeeds_again():
    fetch = FakeFetch(
        ValueError("HTTP 404"),
        ValueError("HTTP 404"),
        ValueError("HTTP 404"),
        ValueError("HTTP 404"),
        FetchResult(200, body({"provider": True, "gpu": False}), None),
    )
    ks = KillSwitch(URL, fetch=fetch)
    for _ in range(4):
        ks.refresh()
    assert ks.spend_locked and not ks.enabled("provider")
    assert ks.refresh()
    assert not ks.spend_locked
    assert ks.enabled("provider")
    assert not ks.enabled("gpu")  # the file itself says no


def test_never_fetched_switch_keeps_spend_off_and_reads_open():
    """Cold start: until one poll has succeeded, spend features are OFF (fail-closed) while every
    other feature stays ON; a first successful fetch opens spend features per the flag file."""
    fetch = FakeFetch(
        FetchResult(503, None, None),
        FetchResult(503, None, None),
        FetchResult(200, body({"provider": True, "gpu": True}), 'W/"v1"'),
    )
    ks = KillSwitch(URL, fetch=fetch, max_missed=3)
    assert ks.enabled("kernels") is True  # reads fail open
    assert ks.enabled("provider") is False and ks.enabled("gpu") is False  # never fetched
    assert ks.refresh() is False and ks.refresh() is False
    assert ks.enabled("provider") is False  # still never fetched, 2 misses < max_missed
    assert ks.refresh() is True
    assert ks.enabled("provider") is True and ks.enabled("gpu") is True
    assert ks.snapshot()["spend_locked"] is False


def test_a_non_json_body_or_missing_body_counts_as_a_miss():
    fetch = FakeFetch(FetchResult(200, b"<html>", None), FetchResult(200, None, None))
    ks = KillSwitch(URL, fetch=fetch)
    assert ks.refresh() is False
    assert ks.refresh() is False
    assert ks.snapshot()["missed"] == 2


def test_start_polls_once_synchronously_then_in_the_background_and_stop_joins():
    fetch = FakeFetch(
        FetchResult(200, body({"provider": True}), 'W/"a"'), FetchResult(304, None, None)
    )
    ks = KillSwitch(URL, fetch=fetch, poll_s=0.01)
    ks.start()
    assert ks.snapshot()["polls"] == 1  # the first poll happened before start() returned
    assert ks.running
    fetch.event.clear()
    assert fetch.event.wait(2.0)  # the thread polled again
    ks.start()  # idempotent
    ks.stop()
    assert not ks.running
    polls = ks.snapshot()["polls"]
    assert polls >= 2
    assert fetch.calls[1][1] == 'W/"a"'  # the background poll carried the etag
    ks.stop()  # stopping twice is harmless
    assert ks.snapshot()["polls"] == polls


def test_constructor_validation():
    with pytest.raises(ValueError):
        KillSwitch(URL, poll_s=0)
    with pytest.raises(ValueError):
        KillSwitch(URL, max_missed=-1)


def test_urllib_fetch_refuses_plain_http_without_touching_the_network():
    with pytest.raises(ValueError, match="https"):
        killswitch.urllib_fetch("http://example.org/flags.json", None)
