"""Post-deploy smoke checks against a live Space.

Each Space in ``spaces.toml`` names a ``verify`` entry (``verify_remote:check_<space>``).
That entry runs the checks registered for the Space through one injectable HTTP fetcher,
so the same code runs against the live URL from ``deploy.py`` and against fakes in tests.

M0 registers the checks that exist for today's apps:

* ``info_reachable``      GET /gradio_api/info answers 200 with JSON inside the turn budget
* ``expected_endpoints``  every ``api_names`` entry from the manifest is a named endpoint; on
                          a Space on the shared shell the live set must equal the manifest's
                          (its tabs declare every endpoint), elsewhere extras are only named
* ``footer_stamp``        the footer's build stamp equals the staged .shared_sha; runs only
                          when the manifest says ``shared_shell = true`` for the Space and is
                          otherwise SKIPPED with an explicit ``[SKIP]`` line, never passed
                          silently (every live Space is ``false`` until M2 puts it on the shell)
* ``redirect_page``       a retired Space's ``/`` on the ``.hf.space`` host (a static Space
                          serves its index.html there) answers 200, its primary button and
                          ``<link rel="canonical">`` point at ``redirect_to`` and the page
                          carries no timed ``<meta http-equiv="refresh">`` (axe: critical);
                          a Gradio page still being served is named as such
* ``stylesheet``          ``/style.css`` answers 200 with the stub's own rules, not an app
                          shell's HTML fallback
* ``hub_sdk``             the live README on the Hub (``/raw/main/README.md``) declares
                          ``sdk: static``; until the stub is published it says gradio/docker
                          and the check fails with that value
The footer stamp check is never registered for a static Space (no Python, no shared shell).

The check/budget pattern is lifted from governed-agent/scripts/verify_remote.py
(``check(name, cond, detail)``, ``TURN_BUDGET_S = 30``) and
_retired/for-llm-agents/scripts/verify_remote.py; endpoint-level assertions on real inputs
follow in the milestones that ship those endpoints.

Footer contract (``algenta_spaces.shell.render_footer``): ``<span class="alg-shell-stamp">build
<sha></span>`` where ``<sha>`` is the ``.shared_sha`` written by ``stage.py`` next to the vendored
package, or its first twelve characters (``shell.SHORT_STAMP_CHARS``; the full sha rides in the
span's ``title``) — the check compares the stamp as a prefix of the staged sha, so both pass.
Gradio serialises the HTML into ``window.gradio_config``: the attribute quote arrives
JSON-escaped (``\\"``) and, on the index page of Gradio 6.28, the angle brackets arrive as
``\\u003e`` / ``\\u003c`` (``/config`` keeps them literal). ``SHA_STAMP_RE`` reads all three
spellings of the same stamp.
"""

from __future__ import annotations

import json
import logging
import re
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from manifest import Manifest, Space, load_manifest
from stage import frontmatter_sdk

log = logging.getLogger(__name__)

Fetcher = Callable[[str, float], tuple[int, str]]
TURN_BUDGET_S = 30.0
INFO_PATH = "/gradio_api/info"
#: `<span class="alg-shell-stamp">build <sha></span>` in the literal, the `\"`-escaped and the
#: `\u003e`-escaped spellings; attributes may follow the class (`title="build <full sha>"` on
#: the shared shell's 12-hex stamp) and the sha may be 7 to 64 hex characters — the check
#: compares it as a prefix of the staged `.shared_sha`.
SHA_STAMP_RE = re.compile(
    r'alg-shell-stamp\\?"[^<>]{0,240}?(?:>|\\u003e)\s*build ([0-9a-f]{7,64})\s*(?:<|\\u003c)'
)
META_REFRESH_RE = re.compile(r'<meta\s+http-equiv=["\']refresh["\']', re.IGNORECASE)
PRIMARY_LINK_RE = re.compile(
    r'<a\s+class=["\']alg-button["\']\s+href=["\']([^"\']+)["\']', re.IGNORECASE
)
CANONICAL_RE = re.compile(r'<link\s+rel=["\']canonical["\']\s+href=["\']([^"\']+)["\']', re.I)
TITLE_RE = re.compile(r"<title>\s*([^<]*?)\s*</title>", re.IGNORECASE | re.DOTALL)
# Markers of a Gradio front end, whichever SDK (gradio or docker) serves it.
GRADIO_RE = re.compile(r"gradio[-_]container|__gradio_mode__|<gradio-app|gradio_config", re.I)
STYLESHEET_PATH = "/style.css"
STYLESHEET_MARKER = ".alg-button"
HUB_RAW_README = "https://huggingface.co/spaces/{repo_id}/raw/main/README.md"
USER_AGENT = "algenta-spaces-verify/1.0"


class VerifyError(AssertionError):
    """One check did not hold."""


class VerifySkipped(Exception):  # noqa: N818 - a skip signal, not an error
    """One check cannot run yet; the reason is reported on its own line."""


def urllib_fetch(url: str, timeout: float) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})  # noqa: S310
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - https only
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")


@dataclass
class VerifyContext:
    space: Space
    fetch: Fetcher
    base_url: str
    expected_shared_sha: str | None = None
    budget_s: float = TURN_BUDGET_S
    clock: Callable[[], float] = time.perf_counter
    _info: dict | None = field(default=None, repr=False)

    def get(self, path: str) -> tuple[int, str]:
        return self.fetch(self.base_url.rstrip("/") + path, self.budget_s)

    def info(self) -> dict:
        if self._info is None:
            status, body = self.get(INFO_PATH)
            if status != 200:
                raise VerifyError(f"{INFO_PATH} answered {status}")
            try:
                parsed = json.loads(body)
            except json.JSONDecodeError as exc:
                raise VerifyError(f"{INFO_PATH} is not JSON: {exc}") from exc
            if not isinstance(parsed, dict) or "named_endpoints" not in parsed:
                raise VerifyError(f"{INFO_PATH} lacks named_endpoints")
            self._info = parsed
        return self._info


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str
    elapsed_s: float
    skipped: bool = False

    @property
    def tag(self) -> str:
        if self.skipped:
            return "SKIP"
        return "OK" if self.ok else "FAIL"


@dataclass(frozen=True)
class VerifyReport:
    space: str
    results: tuple[CheckResult, ...]

    @property
    def ok(self) -> bool:
        return all(r.ok for r in self.results)

    @property
    def failures(self) -> list[str]:
        return [r.name for r in self.results if not r.ok]

    @property
    def skipped(self) -> list[str]:
        return [r.name for r in self.results if r.skipped]

    def lines(self) -> list[str]:
        out = [f"  [{r.tag}] {r.name} {r.detail}".rstrip() for r in self.results]
        verdict = "all checks passed" if self.ok else f"FAILED: {', '.join(self.failures)}"
        if self.skipped:
            verdict += f"; skipped: {', '.join(self.skipped)}"
        out.append(f"{self.space}: {verdict}")
        return out


Check = Callable[[VerifyContext], str]
CHECKS: dict[str, list[tuple[str, Check]]] = {}


def register(*space_names: str) -> Callable[[Check], Check]:
    def wrap(fn: Check) -> Check:
        for name in space_names:
            CHECKS.setdefault(name, []).append((fn.__name__, fn))
        return fn

    return wrap


@register("algenta", "speed-arena", "governed-agent")
def info_reachable(ctx: VerifyContext) -> str:
    info = ctx.info()
    return f"{len(info['named_endpoints'])} named endpoints"


@register("algenta", "speed-arena", "governed-agent")
def expected_endpoints(ctx: VerifyContext) -> str:
    """Every manifest ``api_names`` entry is live. On a Space on the shared shell the two sets
    are equal — its tabs declare every endpoint, so a name the manifest does not list is a
    leak (a ``/lambda`` from a callable value, a forgotten ``api_name=False``); off the shell
    the live set may hold more and the extras are only named."""
    named = set(ctx.info()["named_endpoints"])
    expected = {f"/{n}" for n in ctx.space.api_names}
    missing = sorted(expected - named)
    extra = sorted(named - expected)
    if missing:
        raise VerifyError(f"missing {', '.join(missing)}; live: {', '.join(sorted(named))}")
    if extra and ctx.space.shared_shell:
        raise VerifyError(f"unexpected {', '.join(extra)}; the manifest lists {len(expected)}")
    tail = f"; live also has {', '.join(extra)}" if extra else ""
    return f"{len(expected)} expected endpoints present{tail}"


def footer_stamp_of(html: str) -> str | None:
    m = SHA_STAMP_RE.search(html)
    return m.group(1) if m else None


@register("algenta", "speed-arena", "governed-agent")
def footer_stamp(ctx: VerifyContext) -> str:
    if not ctx.space.shared_shell:
        raise VerifySkipped("app not yet on the shared shell")
    if not ctx.expected_shared_sha:
        raise VerifyError("no staged .shared_sha to compare against")
    status, html = ctx.get("/")
    if status != 200:
        raise VerifyError(f"/ answered {status}")
    stamp = footer_stamp_of(html)
    if stamp is None:
        raise VerifyError("page has no build stamp in the footer")
    if not ctx.expected_shared_sha.startswith(stamp):
        raise VerifyError(f"stamp {stamp} != staged {ctx.expected_shared_sha[:12]}")
    return f"shared {stamp[:12]}"


@register("for-llm-agents", "governed-tool-calls", "llm-modules")
def redirect_page(ctx: VerifyContext) -> str:
    status, html = ctx.get("/")
    if status != 200:
        raise VerifyError(f"/ answered {status}")
    if META_REFRESH_RE.search(html):
        raise VerifyError("page carries a meta refresh; the stub redirects only on click")
    m = PRIMARY_LINK_RE.search(html)
    if not m:
        raise VerifyError(describe_non_stub(html))
    target = m.group(1).strip()
    if target != ctx.space.redirect_to:
        raise VerifyError(f"primary link points at {target}, manifest says {ctx.space.redirect_to}")
    canonical = CANONICAL_RE.search(html)
    if not canonical or canonical.group(1).strip() != ctx.space.redirect_to:
        raise VerifyError("canonical link missing or not the redirect target")
    return f"-> {target}"


def describe_non_stub(html: str) -> str:
    """Why a page that lacks the stub's primary link is not the static stub."""
    if GRADIO_RE.search(html):
        return "no primary link on the page: a Gradio app is still served, not the static stub"
    title = TITLE_RE.search(html)
    if title and title.group(1):
        return f"no primary link on the page (title {title.group(1)!r}); not the static stub"
    return "no primary link on the page"


@register("for-llm-agents", "governed-tool-calls", "llm-modules")
def stylesheet(ctx: VerifyContext) -> str:
    status, css = ctx.get(STYLESHEET_PATH)
    if status != 200:
        raise VerifyError(f"{STYLESHEET_PATH} answered {status}")
    if STYLESHEET_MARKER not in css:
        raise VerifyError(
            f"{STYLESHEET_PATH} is not the stub stylesheet (no {STYLESHEET_MARKER} rule); "
            + ("an app shell answered instead" if GRADIO_RE.search(css) else "wrong content")
        )
    return f"{len(css)} bytes"


@register("for-llm-agents", "governed-tool-calls", "llm-modules")
def hub_sdk(ctx: VerifyContext) -> str:
    """The Hub runs the SDK its README frontmatter names; a stub must say ``sdk: static``."""
    url = HUB_RAW_README.format(repo_id=ctx.space.repo_id)
    status, readme = ctx.fetch(url, ctx.budget_s)
    if status != 200:
        raise VerifyError(f"{url} answered {status}")
    declared = frontmatter_sdk(readme)
    if declared is None:
        raise VerifyError("live README has no `sdk:` in its frontmatter")
    if declared != ctx.space.sdk:
        raise VerifyError(
            f"Hub README declares sdk: {declared}; the static stub is not published yet "
            f"(manifest says sdk: {ctx.space.sdk})"
        )
    return f"sdk: {declared}"


def run_checks(ctx: VerifyContext, checks: list[tuple[str, Check]]) -> VerifyReport:
    results: list[CheckResult] = []
    for name, fn in checks:
        t0 = ctx.clock()
        skipped = False
        try:
            detail = fn(ctx)
            ok = True
        except VerifySkipped as exc:
            detail, ok, skipped = f"skipped: {exc}", True, True
        except VerifyError as exc:
            detail, ok = str(exc), False
        except (OSError, ValueError, KeyError, TypeError) as exc:
            detail, ok = f"{type(exc).__name__}: {exc}", False
        elapsed = ctx.clock() - t0
        if ok and not skipped and elapsed > ctx.budget_s:
            ok, detail = False, f"took {elapsed:.1f}s, budget {ctx.budget_s:.0f}s"
        results.append(CheckResult(name, ok, detail, elapsed, skipped=skipped))
    return VerifyReport(space=ctx.space.name, results=tuple(results))


def _entry(space_name: str) -> Callable[[VerifyContext], VerifyReport]:
    def entry(ctx: VerifyContext) -> VerifyReport:
        checks = CHECKS.get(space_name, [])
        if not checks:
            raise VerifyError(f"no checks registered for {space_name}")
        return run_checks(ctx, checks)

    entry.__name__ = f"check_{space_name.replace('-', '_')}"
    return entry


check_algenta = _entry("algenta")
check_speed_arena = _entry("speed-arena")
check_governed_agent = _entry("governed-agent")


def check_redirect(ctx: VerifyContext) -> VerifyReport:
    return run_checks(ctx, CHECKS[ctx.space.name])


ENTRIES: dict[str, Callable[[VerifyContext], VerifyReport]] = {
    "check_algenta": check_algenta,
    "check_speed_arena": check_speed_arena,
    "check_governed_agent": check_governed_agent,
    "check_redirect": check_redirect,
}


def resolve_entry(space: Space) -> Callable[[VerifyContext], VerifyReport]:
    if space.verify_module != Path(__file__).stem:
        raise VerifyError(f"{space.name}: verify module {space.verify_module!r} is not this tool")
    try:
        return ENTRIES[space.verify_function]
    except KeyError:
        raise VerifyError(f"{space.name}: no verify entry {space.verify_function!r}") from None


def verify_space(
    space: Space,
    *,
    fetch: Fetcher = urllib_fetch,
    base_url: str | None = None,
    expected_shared_sha: str | None = None,
    budget_s: float = TURN_BUDGET_S,
    clock: Callable[[], float] = time.perf_counter,
) -> VerifyReport:
    ctx = VerifyContext(
        space=space,
        fetch=fetch,
        base_url=base_url or space.space_url,
        expected_shared_sha=expected_shared_sha,
        budget_s=budget_s,
        clock=clock,
    )
    return resolve_entry(space)(ctx)


def main(argv: list[str] | None = None, *, manifest: Manifest | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="smoke-check a live Space")
    ap.add_argument("--space", required=True)
    ap.add_argument("--url", default=None, help="override the Space URL")
    ap.add_argument("--staged", type=Path, default=None, help="staged dir holding .shared_sha")
    ap.add_argument("--shared-sha", default=None, help="expected shared sha (overrides --staged)")
    a = ap.parse_args(argv)
    manifest = manifest or load_manifest()
    space = manifest.space(a.space)
    expected = a.shared_sha
    if expected is None and a.staged is not None:
        stamp = a.staged / ".shared_sha"
        expected = stamp.read_text(encoding="utf-8").strip() if stamp.is_file() else None
    report = verify_space(space, fetch=urllib_fetch, base_url=a.url, expected_shared_sha=expected)
    for line in report.lines():
        print(line)
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
