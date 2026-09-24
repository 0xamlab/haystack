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
# Gradio 6.28's index page: the same config with `<` and `>` written as \u003c / \u003e.
GRADIO_INDEX = (
    'window.gradio_config = {"components": [{"value": "\\u003cspan class=\\"alg-shell-stamp\\"'
    "\\u003ebuild " + SHARED + '\\u003c/span\\u003e"}]};'
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


STATIC_README = "---\ntitle: Moved\nsdk: static\npinned: false\n---\n"
# The static redirect path is tested on an inline stub: the three real stubs left the fleet on
# 2026-09-23 (deleted from the Hub). verify_remote registers its static checks per Space name,
# so a test that reaches check_redirect calls register_static_checks(monkeypatch) first.
STATIC_NAME = "old-lab"
STATIC_STUB = Space(
    name=STATIC_NAME,
    repo_id=f"thyn-ai/algenta-{STATIC_NAME}",
    sdk="static",
    source=f"_redirects/{STATIC_NAME}",
    verify="verify_remote:check_redirect",
    redirect_to="https://huggingface.co/spaces/thyn-ai/algenta",
)
STUB_INDEX = (
    '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
    f'<link rel="canonical" href="{STATIC_STUB.redirect_to}">\n'
    '<link rel="stylesheet" href="style.css">\n<title>Algenta · moved</title>\n</head>\n'
    "<body>\n<main>\n<h1>Now part of Algenta</h1>\n"
    "<p>This lab moved into the Algenta flagship. This page redirects only on click.</p>\n"
    f'<a class="alg-button" href="{STATIC_STUB.redirect_to}" target="_top">Open Algenta</a>\n'
    "</main>\n</body>\n</html>\n"
)
STUB_CSS = ".alg-button { display: inline-flex; min-height: 44px; border-radius: 999px; }\n"
# What the .hf.space host of a retired Space serves today: a Gradio front end (the markers
# come from the live page; Gradio 6 loads its config over fetch, so no window.gradio_config).
GRADIO_PAGE = (
    "<!doctype html><html><head><title>Gradio</title></head><body>"
    '<script>window.__gradio_mode__ = "app";</script>'
    '<div class="gradio-container gradio-container-6-28-0"></div></body></html>'
)
# A live Space off the shared shell (`shared_shell = false`, gradio SDK), as the deep-dives were
# before they left the fleet on 2026-09-23 (deleted from the Hub): the stamp check must skip
# loudly and extra endpoints are only named. The real manifest is the flagship alone, on the
# shell, since that day; `verify_remote:check_algenta` is the live-Space check set.
OFF_SHELL_NAME = "arena"
OFF_SHELL = Space(
    name=OFF_SHELL_NAME,
    repo_id=f"thyn-ai/algenta-{OFF_SHELL_NAME}",
    sdk="gradio",
    source=OFF_SHELL_NAME,
    verify="verify_remote:check_algenta",
    python="3.12",
    hardware="cpu-upgrade",
    sleep_time=-1,
    secrets=("HF_TOKEN",),
    api_names=("run_duel_ui",),
    shared_shell=False,
)


def register_static_checks(monkeypatch: pytest.MonkeyPatch, name: str = STATIC_NAME) -> None:
    """Give the inline stub the three static checks for one test: verify_remote registers them
    under the retired stubs' names and check_redirect looks them up by ctx.space.name."""
    checks = [(fn.__name__, fn) for fn in (vr.redirect_page, vr.stylesheet, vr.hub_sdk)]
    monkeypatch.setitem(vr.CHECKS, name, checks)


def _stub_routes(
    space: Space, *, html: str | None = None, css: str | None = None, readme: str = STATIC_README
) -> dict[str, tuple[int, str]]:
    """Routes for a published stub: page and stylesheet on the static host, README on the Hub."""
    return {
        "/": (200, STUB_INDEX if html is None else html),
        "/style.css": (200, STUB_CSS if css is None else css),
        vr.HUB_RAW_README.format(repo_id=space.repo_id): (200, readme),
    }


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


def test_extra_endpoints_fail_on_the_shell_and_are_named_off_it(mf) -> None:
    """The flagship's tabs declare every endpoint, so `/gradio_api/info` must equal the manifest
    row (a `/lambda` from a callable value is a leak); a Space off the shell may expose more."""
    space = _on_shell(mf.space("algenta"))
    http = FakeHttp(
        {
            "/gradio_api/info": (200, _info(*space.api_names, "lambda", "initial_state")),
            "/": (200, GRADIO_CONFIG),
        }
    )
    report = vr.verify_space(space, fetch=http, expected_shared_sha=SHARED)
    assert report.failures == ["expected_endpoints"]
    detail = {r.name: r.detail for r in report.results}["expected_endpoints"]
    assert (
        detail == f"unexpected /initial_state, /lambda; the manifest lists {len(space.api_names)}"
    )
    arena = OFF_SHELL
    http = FakeHttp({"/gradio_api/info": (200, _info(*arena.api_names, "lambda")), "/": (200, "")})
    report = vr.verify_space(arena, fetch=http, expected_shared_sha=SHARED)
    assert report.failures == []
    detail = {r.name: r.detail for r in report.results}["expected_endpoints"]
    assert detail == "1 expected endpoints present; live also has /lambda"


def test_missing_endpoint_and_wrong_stamp_fail() -> None:
    space = _on_shell(OFF_SHELL)
    http = FakeHttp({"/gradio_api/info": (200, _info("something_else")), "/": (200, FOOTER_HTML)})
    report = vr.verify_space(space, fetch=http, expected_shared_sha="b" * 64)
    assert not report.ok
    assert report.failures == ["expected_endpoints", "footer_stamp"]
    by_name = {r.name: r.detail for r in report.results}
    assert "missing /run_duel_ui" in by_name["expected_endpoints"]
    assert by_name["footer_stamp"].startswith(f"stamp {SHARED} != staged bbbbbbbbbbbb")


def test_info_errors_are_reported_not_raised(mf) -> None:
    space = mf.space("algenta")  # on the shared shell since M2-B: the stamp check runs
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


def test_redirect_check_reads_primary_link_and_canonical(monkeypatch: pytest.MonkeyPatch) -> None:
    register_static_checks(monkeypatch)
    space, html = STATIC_STUB, STUB_INDEX
    http = FakeHttp(_stub_routes(space))
    report = vr.verify_space(space, fetch=http)
    assert report.ok, report.lines()
    assert [r.name for r in report.results] == ["redirect_page", "stylesheet", "hub_sdk"]
    assert report.skipped == [], "no footer stamp for a static Space"
    assert report.results[0].detail == f"-> {space.redirect_to}"
    assert report.results[2].detail == "sdk: static"
    assert http.calls == [
        f"{space.space_url}/",
        f"{space.space_url}/style.css",
        f"https://huggingface.co/spaces/{space.repo_id}/raw/main/README.md",
    ]
    assert report.lines()[-1] == f"{STATIC_NAME}: all checks passed"

    def page(variant: str) -> str:
        return (
            vr.verify_space(space, fetch=FakeHttp(_stub_routes(space, html=variant)))
            .results[0]
            .detail
        )

    button = f'class="alg-button" href="{space.redirect_to}"'
    assert html.count(button) == 1
    wrong = html.replace(
        button, 'class="alg-button" href="https://huggingface.co/spaces/thyn-ai/elsewhere"'
    )
    report = vr.verify_space(space, fetch=FakeHttp(_stub_routes(space, html=wrong)))
    assert report.failures == ["redirect_page"]
    assert "primary link points at" in report.results[0].detail
    assert page("<html/>") == "no primary link on the page"
    assert page("<html><head><title>Other app</title></head></html>") == (
        "no primary link on the page (title 'Other app'); not the static stub"
    )
    timed = html.replace(
        "<head>", f'<head><meta http-equiv="refresh" content="3;url={space.redirect_to}">', 1
    )
    assert "meta refresh" in page(timed)
    assert (
        vr.verify_space(space, fetch=FakeHttp({**_stub_routes(space), "/": (404, "")}))
        .results[0]
        .detail
        == "/ answered 404"
    )
    assert "canonical" in page(html.replace('rel="canonical"', 'rel="alternate"'))


def test_pre_publish_state_is_named_precisely(monkeypatch: pytest.MonkeyPatch) -> None:
    """The live Space still runs its old app: every static check must say so, not just fail."""
    register_static_checks(monkeypatch)
    space = STATIC_STUB
    live_readme = "---\ntitle: Algenta for LLM Agents\nsdk: gradio\nsdk_version: 6.28.0\n---\n"
    # a Gradio front end answers every path with its index page, style.css included
    http = FakeHttp(_stub_routes(space, html=GRADIO_PAGE, css=GRADIO_PAGE, readme=live_readme))
    report = vr.verify_space(space, fetch=http)
    assert not report.ok
    assert report.failures == ["redirect_page", "stylesheet", "hub_sdk"]
    details = {r.name: r.detail for r in report.results}
    assert details["redirect_page"] == (
        "no primary link on the page: a Gradio app is still served, not the static stub"
    )
    assert details["stylesheet"] == (
        "/style.css is not the stub stylesheet (no .alg-button rule); an app shell answered instead"
    )
    assert details["hub_sdk"] == (
        "Hub README declares sdk: gradio; the static stub is not published yet "
        "(manifest says sdk: static)"
    )
    assert report.lines()[-1] == f"{STATIC_NAME}: FAILED: redirect_page, stylesheet, hub_sdk"
    # the same stub over a Space the Hub still runs as a docker app
    report = vr.verify_space(
        space, fetch=FakeHttp(_stub_routes(space, readme="---\nsdk: docker\n---\n"))
    )
    assert report.failures == ["hub_sdk"]
    assert report.results[2].detail.startswith("Hub README declares sdk: docker;")


def test_stylesheet_and_hub_sdk_edge_cases(monkeypatch: pytest.MonkeyPatch) -> None:
    register_static_checks(monkeypatch)
    space = STATIC_STUB
    raw = vr.HUB_RAW_README.format(repo_id=space.repo_id)

    def detail(name: str, **routes: tuple[int, str]) -> str:
        report = vr.verify_space(space, fetch=FakeHttp({**_stub_routes(space), **routes}))
        return {r.name: r.detail for r in report.results}[name]

    assert detail("stylesheet", **{"/style.css": (404, "")}) == "/style.css answered 404"
    assert detail("stylesheet", **{"/style.css": (200, "body { color: red }")}) == (
        "/style.css is not the stub stylesheet (no .alg-button rule); wrong content"
    )
    assert detail("hub_sdk", **{raw: (404, "Not Found")}) == f"{raw} answered 404"
    assert detail("hub_sdk", **{raw: (200, "---\ntitle: no sdk\n---\n")}) == (
        "live README has no `sdk:` in its frontmatter"
    )
    assert detail("hub_sdk", **{raw: (200, "# no frontmatter at all\n")}) == (
        "live README has no `sdk:` in its frontmatter"
    )
    assert vr.describe_non_stub("") == "no primary link on the page"
    assert vr.describe_non_stub("<title></title>") == "no primary link on the page"
    assert vr.describe_non_stub('<gradio-app src="x"></gradio-app>').startswith(
        "no primary link on the page: a Gradio app"
    )


def test_cli_reports_an_unpublished_stub_and_exits_one(
    mf, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    register_static_checks(monkeypatch)
    space = STATIC_STUB
    with_stub = replace(mf, spaces={**mf.spaces, STATIC_NAME: space})
    live_readme = "---\nsdk: gradio\n---\n"
    http = FakeHttp(_stub_routes(space, html=GRADIO_PAGE, css=GRADIO_PAGE, readme=live_readme))
    monkeypatch.setattr(vr, "urllib_fetch", http)
    rc = vr.main(["--space", STATIC_NAME], manifest=with_stub)
    out = capsys.readouterr().out
    assert rc == 1
    assert "[FAIL] redirect_page no primary link on the page: a Gradio app is still served" in out
    assert (
        "[FAIL] hub_sdk Hub README declares sdk: gradio; the static stub is not published yet"
        in out
    )
    assert f"{STATIC_NAME}: FAILED: redirect_page, stylesheet, hub_sdk" in out
    assert "footer_stamp" not in out
    monkeypatch.setattr(vr, "urllib_fetch", FakeHttp(_stub_routes(space)))
    assert vr.main(["--space", STATIC_NAME], manifest=with_stub) == 0
    assert f"{STATIC_NAME}: all checks passed" in capsys.readouterr().out


def test_footer_stamp_parsing_handles_plain_and_json_escaped_html() -> None:
    assert vr.footer_stamp_of(FOOTER_HTML) == SHARED
    assert vr.footer_stamp_of(GRADIO_CONFIG) == SHARED
    assert vr.footer_stamp_of(GRADIO_INDEX) == SHARED, "the index page escapes the brackets"
    assert vr.footer_stamp_of('<span class="alg-shell-stamp">build dev</span>') is None
    assert vr.footer_stamp_of("") is None
    # a stamp of another element, or a stamp that is not hex, is not read
    assert vr.footer_stamp_of('<span class="alg-shell-other">build ' + SHARED + "</span>") is None
    assert vr.footer_stamp_of('alg-shell-stamp\\"\\u003ebuild zz\\u003c') is None


SHORT = SHARED[:12]
#: The shared shell's stamp: twelve hex characters, the full sha in the span's `title`.
FOOTER_SHORT = (
    f'<footer><span title="build {SHARED}" class="alg-shell-stamp">build {SHORT}</span></footer>'
)
FOOTER_SHORT_TITLE_AFTER = (
    f'<footer><span class="alg-shell-stamp" title="build {SHARED}">build {SHORT}</span></footer>'
)
GRADIO_INDEX_SHORT = (
    'window.gradio_config = {"components": [{"value": "\\u003cspan title=\\"build '
    + SHARED
    + '\\" class=\\"alg-shell-stamp\\"\\u003ebuild '
    + SHORT
    + '\\u003c/span\\u003e"}]};'
)


def test_footer_stamp_accepts_the_shared_shells_twelve_hex_stamp(mf) -> None:
    """`shell.render_footer` prints `build <12 hex>` with the full sha in `title` (a 64-hex
    stamp wrapped to three lines at 375 px); the check reads it in every spelling, compares it
    as a prefix of the staged sha, and still refuses another sha."""
    for page in (FOOTER_SHORT, FOOTER_SHORT_TITLE_AFTER, GRADIO_INDEX_SHORT):
        assert vr.footer_stamp_of(page) == SHORT, page
    space = _on_shell(mf.space("algenta"))
    for page in (FOOTER_SHORT, GRADIO_INDEX_SHORT):
        http = FakeHttp({"/gradio_api/info": (200, _info(*space.api_names)), "/": (200, page)})
        report = vr.verify_space(space, fetch=http, expected_shared_sha=SHARED)
        assert report.ok, report.lines()
        assert report.results[2].detail == f"shared {SHORT}"
    http = FakeHttp({"/gradio_api/info": (200, _info(*space.api_names)), "/": (200, FOOTER_SHORT)})
    wrong = vr.verify_space(space, fetch=http, expected_shared_sha="b" * 64)
    assert wrong.failures == ["footer_stamp"]
    assert wrong.results[2].detail == f"stamp {SHORT} != staged bbbbbbbbbbbb"
    # the stamp is read from the `alg-shell-stamp` span alone, whatever attributes follow
    assert (
        vr.footer_stamp_of(f'<span class="alg-shell-stamp" data-x="1">build {SHORT}</span>')
        == SHORT
    )
    assert vr.footer_stamp_of(f'<span class="alg-shell-other">build {SHORT}</span>') is None
    # `.shared_sha` staged with the full sha still matches its own 64-hex stamp
    assert vr.footer_stamp_of(FOOTER_HTML) == SHARED


def test_footer_stamp_check_reads_the_gradio_6_index_page(mf) -> None:
    """`GET /` on the flagship serves the escaped config; the stamp check must pass on it."""
    space = _on_shell(mf.space("algenta"))
    http = FakeHttp({"/gradio_api/info": (200, _info(*space.api_names)), "/": (200, GRADIO_INDEX)})
    report = vr.verify_space(space, fetch=http, expected_shared_sha=SHARED)
    assert report.ok, report.lines()
    assert report.results[2].detail == f"shared {SHARED[:12]}"
    wrong = vr.verify_space(space, fetch=http, expected_shared_sha="b" * 64)
    assert wrong.failures == ["footer_stamp"]
    assert wrong.results[2].detail == f"stamp {SHARED} != staged bbbbbbbbbbbb"


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
    for name in ("for-llm-agents", "governed-tool-calls", "llm-modules"):
        assert [n for n, _ in vr.CHECKS[name]] == ["redirect_page", "stylesheet", "hub_sdk"], name


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


def test_footer_stamp_is_skipped_loudly_for_a_space_off_the_shared_shell(mf) -> None:
    """Every live Space of the fleet renders the shared footer today (the flagship since M2-B;
    the deep-dives left on 2026-09-23), so the skip path runs on the inline off-shell Space:
    the stamp check must not pass silently, and the flag alone decides skip versus check."""
    assert [s.name for s in mf.live] == ["algenta"] and mf.space("algenta").shared_shell is True
    space = OFF_SHELL
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
    assert lines[-1] == f"{OFF_SHELL_NAME}: all checks passed; skipped: footer_stamp"
    # once on the shell the same Space and the same fake page fail the check instead
    space = _on_shell(OFF_SHELL)
    http = FakeHttp({"/gradio_api/info": (200, _info(*space.api_names)), "/": (200, "<html/>")})
    report = vr.verify_space(space, fetch=http, expected_shared_sha=SHARED)
    assert report.failures == ["footer_stamp"] and report.skipped == []
    assert report.results[2].detail == "page has no build stamp in the footer"
    assert report.lines()[-1] == f"{OFF_SHELL_NAME}: FAILED: footer_stamp"
    # and a skip never hides a failure elsewhere in the verdict
    report = vr.verify_space(
        OFF_SHELL,
        fetch=FakeHttp({"/gradio_api/info": (200, _info("other")), "/": (200, "<html/>")}),
        expected_shared_sha=SHARED,
    )
    assert not report.ok
    assert report.lines()[-1] == (
        f"{OFF_SHELL_NAME}: FAILED: expected_endpoints; skipped: footer_stamp"
    )


def test_cli_skips_the_stamp_for_a_space_off_the_shell(
    mf, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    space = OFF_SHELL
    with_arena = replace(mf, spaces={**mf.spaces, OFF_SHELL_NAME: space})
    http = FakeHttp({"/gradio_api/info": (200, _info(*space.api_names)), "/": (200, "<html/>")})
    monkeypatch.setattr(vr, "urllib_fetch", http)
    rc = vr.main(["--space", OFF_SHELL_NAME, "--shared-sha", SHARED], manifest=with_arena)
    out = capsys.readouterr().out
    assert rc == 0
    assert "[SKIP] footer_stamp skipped: app not yet on the shared shell" in out
    assert f"{OFF_SHELL_NAME}: all checks passed; skipped: footer_stamp" in out


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
