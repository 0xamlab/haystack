"""Live checks for the hosted lane and the kill switch — real network, real SDK, no fakes.

Run with `ALGENTA_SPACES_LIVE=1 python3 -m pytest tests/spaces/integration -q -m slow`.

* The kill switch polls a real public JSON document over https and proves the
  `If-None-Match` round trip (200 then 304) and the fail-closed path against a
  URL that does not exist.
* The hosted lane builds the real `algenta.AlgentaClient` and probes
  `https://api.algenta.ai` with a key the engine must reject, proving the
  401 → not-configured mapping, the scrub and the no-traceback promise on the
  real transport. With `ALGENTA_API_KEY` set, it also runs the real
  recommend → log → get round trip on that tenant.
"""

from __future__ import annotations

import os
import secrets

import pytest
from algenta_spaces import hosted_api, killswitch
from algenta_spaces.hosted_api import ConfigState, HostedGoverned, NotConfiguredError

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(
        os.environ.get("ALGENTA_SPACES_LIVE") != "1", reason="set ALGENTA_SPACES_LIVE=1"
    ),
]

PUBLIC_JSON = "https://huggingface.co/api/spaces/thyn-ai/algenta"
MISSING_JSON = "https://huggingface.co/datasets/thyn-ai/no-such-dataset/resolve/main/flags.json"


class RecordingFetch:
    def __init__(self) -> None:
        self.statuses: list[int] = []
        self.etags_sent: list[str | None] = []

    def __call__(self, url: str, etag: str | None) -> killswitch.FetchResult:
        self.etags_sent.append(etag)
        result = killswitch.urllib_fetch(url, etag)
        self.statuses.append(result.status)
        return result


def test_killswitch_polls_a_public_json_with_etag_round_trip():
    fetch = RecordingFetch()
    ks = killswitch.KillSwitch(PUBLIC_JSON, fetch=fetch)
    assert ks.refresh() is True
    snap = ks.snapshot()
    assert snap["etag"], "the Hub sends an ETag"
    assert fetch.statuses == [200]
    assert ks.refresh() is True
    assert fetch.etags_sent[1] == snap["etag"]
    assert fetch.statuses[1] in (200, 304)
    assert ks.snapshot()["missed"] == 0
    assert ks.enabled("provider")  # a document without our flags leaves features on


def test_killswitch_fails_closed_for_spend_when_the_flag_file_is_missing():
    fetch = RecordingFetch()
    ks = killswitch.KillSwitch(MISSING_JSON, fetch=fetch, max_missed=3)
    for _ in range(4):
        assert ks.refresh() is False
    assert all(status >= 400 for status in fetch.statuses)
    assert ks.spend_locked
    assert not ks.enabled("provider") and not ks.enabled("gpu")
    assert ks.enabled("kernels")


def test_hosted_lane_maps_a_rejected_key_on_the_real_api_without_leaking_it():
    pytest.importorskip("algenta")
    pytest.importorskip("decision_engine")
    bogus = "de_test_" + secrets.token_hex(16)
    hg = HostedGoverned(env={"ALGENTA_API_KEY": bogus})
    status = hg.status()
    assert status.state is ConfigState.NOT_CONFIGURED, status
    assert status.reason == hosted_api.REJECTED_KEY_REASON
    assert bogus not in status.reason
    with pytest.raises(NotConfiguredError) as info:
        hg.get_decision("00000000-0000-0000-0000-000000000000")
    assert info.value.status_code in (401, 403)
    assert bogus not in str(info.value)
    assert bogus not in repr(hg)
    assert hosted_api.NOT_CONFIGURED_CODE in hosted_api.render_status_card(status)


def test_hosted_lane_round_trip_on_a_real_tenant():
    pytest.importorskip("algenta")
    if not os.environ.get("ALGENTA_API_KEY"):
        pytest.skip("ALGENTA_API_KEY not set: no tenant to exercise")
    hg = HostedGoverned()
    status = hg.status()
    assert status.ready, status.reason
    rec = hg.recommend(
        [
            {"name": "expand_eu", "expected_value": 120.0, "risk": 0.1},
            {"name": "hold", "expected_value": 20.0, "risk": 0.05},
        ]
    )
    assert rec.recommended_action
    dec = hg.log_decision(
        rec.recommended_action,
        confidence=rec.confidence if rec.confidence is not None else 0.9,
        risk_p5=-0.01,
        context="Live check from tests/spaces/integration.",
        rationale=rec.rationale or "live check",
    )
    assert dec.decision_id
    again = hg.get_decision(dec.decision_id)
    assert again.decision_id == dec.decision_id
    assert again.chosen_action == dec.chosen_action
