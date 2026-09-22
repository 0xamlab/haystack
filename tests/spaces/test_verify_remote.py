"""apps/spaces/tools/verify_remote.py — smoke checks against fakes, no network."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
import verify_remote as vr
from manifest import Manifest, Space, load_manifest

SHARED = "a" * 64
FOOTER_HTML = f'<footer><span class="alg-shell-stamp">build {SHARED}</span></footer>'
GRADIO_CONFIG = (
    'window.gradio_config = {"components": [{"value": "<span class=\\"alg-shell-stamp\\">build '
    + SHARED
    + '</span>"}]};'
)


class FakeHttp:
    def __init__(self, routes: dict[str, tuple[int, str]]) -> None:
        self.routes = routes
        self.calls: list[str] = []

    def __call__(self, url: str, timeout: float) -> tuple[int, str]:
        self.calls.append(url)
        path = url.split(".hf.space", 1)[1] if ".hf.space" in url else url
        return self.routes[path]


def _info(*names: str) -> str:
    return json.dumps(
        {"named_endpoints": {f"/{n}": {"parameters": []} for n in names}, "unnamed_endpoints": {}}
    )


@pytest.fixture
def mf():
    return load_manifest()


def _on_shell(space: Space) -> Space:
    """The Space as it will be once M2 renders the shared footer stamp."""
    return replace(space, shared_shell=True)


@pytest.fixture
def mf_shell(mf: Manifest) -> Manifest:
    return replace(
        mf, spaces={name: _on_shell(s) if s.is_live else s for name, s in mf.spaces.items()}
    )


def test_algenta_all_checks_pass(mf) -> None:
    space = _on_shell(mf.space("algenta"))
    http = FakeHttp({"/gradio_api/info": (200, _info(*space.api_names)), "/": (200, GRADIO_CONFIG)})
    report = vr.verify_space(space, fetch=http, expected_shared_sha=SHARED)
    assert report.ok
    assert [r.name for r in report.results] == [
        "info_reachable",
        "expected_endpoints",
        "footer_stamp",
    ]
    assert http.calls == [
        f"{space.space_url}/gradio_api/info",
        f"{space.space_url}/",
    ]  # info is cached
    assert report.lines()[-1] == "algenta: all checks passed"
    assert f"shared {SHARED[:12]}" in report.lines()[2]


def test_missing_endpoint_and_wrong_stamp_fail(mf) -> None:
    space = _on_shell(mf.space("speed-arena"))
    http = FakeHttp({"/gradio_api/info": (200, _info("something_else")), "/": (200, FOOTER_HTML)})
    report = vr.verify_space(space, fetch=http, expected_shared_sha="b" * 64)
    assert not report.ok
    assert report.failures == ["expected_endpoints", "footer_stamp"]
    by_name = {r.name: r.detail for r in report.results}
    assert "missing /run_duel_ui" in by_name["expected_endpoints"]
    assert by_name["footer_stamp"].startswith(f"stamp {SHARED} != staged bbbbbbbbbbbb")


def test_info_errors_are_reported_not_raised(mf) -> None:
    space = _on_shell(mf.space("governed-agent"))
    http = FakeHttp({"/gradio_api/info": (503, "starting"), "/": (200, "<html></html>")})
    report = vr.verify_space(space, fetch=http, expected_shared_sha=SHARED)
    details = {r.name: r.detail for r in report.results}
    assert details["info_reachable"] == "/gradio_api/info answered 503"
    assert details["expected_endpoints"] == "/gradio_api/info answered 503"
    assert details["footer_stamp"] == "page has no build stamp in the footer"
    http = FakeHttp({"/gradio_api/info": (200, "not json"), "/": (200, FOOTER_HTML)})
    report = vr.verify_space(space, fetch=http, expected_shared_sha=None)
    details = {r.name: r.detail for r in report.results}
    assert details["info_reachable"].startswith("/gradio_api/info is not JSON")
    assert details["footer_stamp"] == "no staged .shared_sha to compare against"
    http = FakeHttp({"/gradio_api/info": (200, json.dumps({"x": 1})), "/": (200, FOOTER_HTML)})
    assert (
        vr.verify_space(space, fetch=http, expected_shared_sha=SHARED).results[0].detail
        == "/gradio_api/info lacks named_endpoints"
    )


def test_exceptions_inside_a_check_become_failures(mf) -> None:
    space = _on_shell(mf.space("algenta"))

    def boom(url: str, timeout: float) -> tuple[int, str]:
        raise OSError("connection refused")

    report = vr.verify_space(space, fetch=boom, expected_shared_sha=SHARED)
    assert not report.ok
    assert all(r.detail == "OSError: connection refused" for r in report.results)


def test_turn_budget_enforced_with_injected_clock(mf) -> None:
    space = _on_shell(mf.space("algenta"))
    http = FakeHttp({"/gradio_api/info": (200, _info(*space.api_names)), "/": (200, FOOTER_HTML)})
    ticks = iter([0.0, 31.0, 31.0, 31.5, 31.5, 32.0])
    report = vr.verify_space(
        space, fetch=http, expected_shared_sha=SHARED, clock=lambda: next(ticks)
    )
    assert report.failures == ["info_reachable"]
    assert report.results[0].detail == "took 31.0s, budget 30s"
    assert report.results[1].ok and report.results[2].ok


def test_redirect_check_reads_primary_link_and_canonical(mf, apps_spaces_dir: Path) -> None:
    space = mf.space("for-llm-agents")
    html = (apps_spaces_dir / "_redirects" / "for-llm-agents" / "index.html").read_text(
        encoding="utf-8"
    )
    http = FakeHttp({"/": (200, html)})
    report = vr.verify_space(space, fetch=http)
    assert report.ok, report.lines()
    assert report.results[0].detail == f"-> {space.redirect_to}"

    button = f'class="alg-button" href="{space.redirect_to}"'
    assert html.count(button) == 1
    wrong = html.replace(
        button, 'class="alg-button" href="https://huggingface.co/spaces/thyn-ai/elsewhere"'
    )
    report = vr.verify_space(space, fetch=FakeHttp({"/": (200, wrong)}))
    assert report.failures == ["redirect_page"]
    assert "primary link points at" in report.results[0].detail
    assert (
        vr.verify_space(space, fetch=FakeHttp({"/": (200, "<html/>")})).results[0].detail
        == "no primary link on the page"
    )
    timed = html.replace(
        "<head>", f'<head><meta http-equiv="refresh" content="3;url={space.redirect_to}">', 1
    )
    assert (
        "meta refresh"
        in vr.verify_space(space, fetch=FakeHttp({"/": (200, timed)})).results[0].detail
    )
    assert (
        vr.verify_space(space, fetch=FakeHttp({"/": (404, "")})).results[0].detail
        == "/ answered 404"
    )
    no_canonical = html.replace('rel="canonical"', 'rel="alternate"')
    assert (
        "canonical"
        in vr.verify_space(space, fetch=FakeHttp({"/": (200, no_canonical)})).results[0].detail
    )


def test_footer_stamp_parsing_handles_plain_and_json_escaped_html() -> None:
    assert vr.footer_stamp_of(FOOTER_HTML) == SHARED
    assert vr.footer_stamp_of(GRADIO_CONFIG) == SHARED
    assert vr.footer_stamp_of('<span class="alg-shell-stamp">build dev</span>') is None
    assert vr.footer_stamp_of("") is None


def test_every_manifest_entry_resolves_and_has_checks(mf) -> None:
    for space in mf.spaces.values():
        entry = vr.resolve_entry(space)
        assert callable(entry)
        assert vr.CHECKS[space.name], space.name
    assert {n for n, _ in vr.CHECKS["algenta"]} == {
        "info_reachable",
        "expected_endpoints",
        "footer_stamp",
    }
    assert {n for n, _ in vr.CHECKS["llm-modules"]} == {"redirect_page"}


def test_resolve_entry_rejects_foreign_modules_and_unknown_functions(mf) -> None:
    from dataclasses import replace

    space = mf.space("algenta")
    with pytest.raises(vr.VerifyError, match="is not this tool"):
        vr.resolve_entry(replace(space, verify="other_tool:check_algenta"))
    with pytest.raises(vr.VerifyError, match="no verify entry"):
        vr.resolve_entry(replace(space, verify="verify_remote:check_nothing"))
    with pytest.raises(vr.VerifyError, match="no checks registered"):
        vr._entry("unregistered")(
            vr.VerifyContext(space=space, fetch=FakeHttp({}), base_url="https://x")
        )


def test_footer_stamp_is_skipped_loudly_until_the_app_is_on_the_shared_shell(mf) -> None:
    """Every live Space has shared_shell = false today: the stamp check must not pass silently."""
    for name in ("algenta", "speed-arena", "governed-agent"):
        space = mf.space(name)
        assert space.shared_shell is False
        http = FakeHttp({"/gradio_api/info": (200, _info(*space.api_names)), "/": (200, "<html/>")})
        report = vr.verify_space(space, fetch=http, expected_shared_sha=SHARED)
        assert report.ok and report.failures == []
        assert report.skipped == ["footer_stamp"]
        stamp = report.results[2]
        assert stamp.skipped and stamp.ok and stamp.tag == "SKIP"
        assert stamp.detail == "skipped: app not yet on the shared shell"
        assert http.calls == [f"{space.space_url}/gradio_api/info"], "the page is not fetched"
        lines = report.lines()
        assert "  [SKIP] footer_stamp skipped: app not yet on the shared shell" in lines
        assert lines[-1] == f"{name}: all checks passed; skipped: footer_stamp"
    # once on the shell the same fake page fails the check instead of skipping it
    space = _on_shell(mf.space("algenta"))
    http = FakeHttp({"/gradio_api/info": (200, _info(*space.api_names)), "/": (200, "<html/>")})
    report = vr.verify_space(space, fetch=http, expected_shared_sha=SHARED)
    assert report.failures == ["footer_stamp"] and report.skipped == []
    assert report.results[2].detail == "page has no build stamp in the footer"
    assert report.lines()[-1] == "algenta: FAILED: footer_stamp"
    # and a skip never hides a failure elsewhere in the verdict
    space = mf.space("algenta")
    report = vr.verify_space(
        space,
        fetch=FakeHttp({"/gradio_api/info": (200, _info("other")), "/": (200, "<html/>")}),
        expected_shared_sha=SHARED,
    )
    assert not report.ok
    assert report.lines()[-1] == "algenta: FAILED: expected_endpoints; skipped: footer_stamp"


def test_cli_skips_the_stamp_for_a_space_off_the_shell(
    mf, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    space = mf.space("algenta")
    http = FakeHttp({"/gradio_api/info": (200, _info(*space.api_names)), "/": (200, "<html/>")})
    monkeypatch.setattr(vr, "urllib_fetch", http)
    rc = vr.main(["--space", "algenta", "--shared-sha", SHARED], manifest=mf)
    out = capsys.readouterr().out
    assert rc == 0
    assert "[SKIP] footer_stamp skipped: app not yet on the shared shell" in out
    assert "algenta: all checks passed; skipped: footer_stamp" in out


def test_cli_reads_staged_stamp_and_exit_codes(
    mf_shell, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    mf = mf_shell
    space = mf.space("algenta")
    (tmp_path / ".shared_sha").write_text(SHARED + "\n", encoding="utf-8")
    http = FakeHttp({"/gradio_api/info": (200, _info(*space.api_names)), "/": (200, FOOTER_HTML)})
    monkeypatch.setattr(vr, "urllib_fetch", http)
    rc = vr.main(["--space", "algenta", "--staged", str(tmp_path)], manifest=mf)
    out = capsys.readouterr().out
    assert rc == 0 and "algenta: all checks passed" in out
    rc = vr.main(
        [
            "--space",
            "algenta",
            "--shared-sha",
            "c" * 64,
            "--url",
            "https://thyn-ai-algenta.hf.space",
        ],
        manifest=mf,
    )
    out = capsys.readouterr().out
    assert rc == 1 and "[FAIL] footer_stamp" in out


def test_urllib_fetch_maps_http_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    import io
    import urllib.error
    import urllib.request

    class Resp(io.BytesIO):
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def fake_open(req, timeout):
        assert req.get_header("User-agent") == vr.USER_AGENT
        if req.full_url.endswith("/missing"):
            raise urllib.error.HTTPError(req.full_url, 404, "nf", {}, io.BytesIO(b"gone"))
        return Resp(b'{"ok": true}')

    monkeypatch.setattr(urllib.request, "urlopen", fake_open)
    assert vr.urllib_fetch("https://x.hf.space/gradio_api/info", 5.0) == (200, '{"ok": true}')
    assert vr.urllib_fetch("https://x.hf.space/missing", 5.0) == (404, "gone")
