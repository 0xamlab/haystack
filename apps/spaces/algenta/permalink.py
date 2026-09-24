"""Permalinks — `?tab=<id>&fn=<module.function>&args=<json>`, parsed on load, written back.

A link names at most three things: the tab (one of the shell's tab ids), the function the
visitor was looking at (a dotted `module.function` name) and its arguments (one JSON
object, at most `MAX_ARGS_CHARS` characters). Anything that does not parse is dropped
field by field — a bad `args` keeps a good `tab` — so a link never promises a state the
page cannot restore. Nothing here runs in the browser: the shell reads the query string
from `gr.Request` in `Blocks.load` and renders the current link into a text box with a copy
button, so a visitor copies a URL the server built.

The public base comes from the Space's environment first (`ALGENTA_PUBLIC_BASE_URL`, then
`SPACE_HOST`, which the Hub sets in every Space container), then from the request's
forwarding headers; without either the link is relative (`?tab=play`), which still works
from the page it is shown on. Stdlib only.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit

PARAM_TAB = "tab"
PARAM_FN = "fn"
PARAM_ARGS = "args"
PARAMS: tuple[str, ...] = (PARAM_TAB, PARAM_FN, PARAM_ARGS)
MAX_ARGS_CHARS = 4_096
PUBLIC_BASE_ENV = "ALGENTA_PUBLIC_BASE_URL"
SPACE_HOST_ENV = "SPACE_HOST"

_FN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+$")
_HOST_RE = re.compile(r"^[A-Za-z0-9.-]+(?::\d{1,5})?$")


@dataclass(frozen=True)
class Permalink:
    """One restorable page state; every field optional, every field already validated."""

    tab: str | None = None
    fn: str | None = None
    args: Mapping[str, Any] | None = None

    @property
    def empty(self) -> bool:
        return self.tab is None and self.fn is None and self.args is None

    @property
    def empty_call(self) -> bool:
        """True when the link names no function and no arguments (a tab alone)."""
        return self.fn is None and self.args is None

    def query(self) -> str:
        """`?tab=play&fn=text.fuzzy.levenshtein_distance&args={...}`, or an empty string."""
        items: dict[str, str] = {}
        if self.tab:
            items[PARAM_TAB] = self.tab
        if self.fn:
            items[PARAM_FN] = self.fn
        if self.args:
            items[PARAM_ARGS] = json.dumps(self.args, separators=(",", ":"), ensure_ascii=False)
        return "?" + urlencode(items) if items else ""

    def url(self, base: str = "") -> str:
        """The absolute link when `base` is given, else the query alone."""
        return (base.rstrip("/") + "/" if base else "") + self.query()


def parse_fn(text: str | None) -> str | None:
    """A dotted `module.function` name, or None."""
    if not text:
        return None
    value = text.strip()
    return value if _FN_RE.match(value) and len(value) <= 200 else None


def parse_args(text: str | None, *, max_chars: int = MAX_ARGS_CHARS) -> dict[str, Any] | None:
    """One JSON object of at most `max_chars` characters, or None."""
    if not text or len(text) > max_chars:
        return None
    try:
        data = json.loads(text)
    except ValueError:
        return None
    if not isinstance(data, dict) or not data:
        return None
    return {str(key): value for key, value in data.items()}


def parse(params: Mapping[str, Any] | None, *, tabs: Sequence[str]) -> Permalink:
    """The validated permalink in `params`; unknown tabs, bad names and bad JSON are dropped."""
    if not params:
        return Permalink()
    tab = _first(params.get(PARAM_TAB))
    fn = parse_fn(_first(params.get(PARAM_FN)))
    args = parse_args(_first(params.get(PARAM_ARGS)))
    return Permalink(tab if tab in tabs else None, fn, args)


def parse_query(url: str, *, tabs: Sequence[str] | None = None) -> Permalink:
    """The permalink inside a URL or a bare `?tab=…` query the page has shown; `tabs` limits the
    tab as `parse` does, and without it any non-empty tab value is kept."""
    params: dict[str, Any] = dict(parse_qs(urlsplit(str(url or "")).query))
    if tabs is None:
        tab = _first(params.get(PARAM_TAB)) or None
        fn = parse_fn(_first(params.get(PARAM_FN)))
        return Permalink(tab, fn, parse_args(_first(params.get(PARAM_ARGS))))
    return parse(params, tabs=tabs)


def restorable(link: Permalink, *, known_functions: Collection[str] | None = None) -> Permalink:
    """What a tab without its own `permalink_applied` can be taken to restore of `link`.

    The tab always; the function only when this container serves it (`known_functions`, the
    loaded contracts' `module.function` names — with none given every well-formed name passes);
    the arguments only beside a function that passed, or alone when the link names no function
    (the Try tab restores its four numbers without one). A link never shows a call the page
    did not restore.
    """
    fn = link.fn
    if fn is not None and known_functions is not None and fn not in known_functions:
        fn = None
    args = link.args if (fn is not None or link.fn is None) else None
    return Permalink(link.tab, fn, dict(args) if args else None)


def _first(value: Any) -> str | None:
    """Query values may arrive as a string or a list of strings; the first one counts."""
    if value is None:
        return None
    if isinstance(value, list | tuple):
        return str(value[0]) if value else None
    return str(value)


def query_params_of(request: Any) -> dict[str, str]:
    """The query mapping of a `gr.Request` (or anything with `query_params`), never raising."""
    if request is None:
        return {}
    params = getattr(request, "query_params", None)
    if params is None:
        inner = getattr(request, "request", None)
        params = getattr(inner, "query_params", None)
    if params is None:
        return {}
    try:
        return {str(key): str(value) for key, value in dict(params).items()}
    except (TypeError, ValueError):
        return {}


def from_request(request: Any, *, tabs: Sequence[str]) -> Permalink:
    return parse(query_params_of(request), tabs=tabs)


def public_base(env: Mapping[str, str] | None = None, request: Any = None) -> str:
    """`https://<host>` from the environment, else the request's forwarding headers, else ""."""
    env = os.environ if env is None else env
    explicit = env.get(PUBLIC_BASE_ENV, "").strip().rstrip("/")
    if explicit.startswith(("https://", "http://")):
        return explicit
    host = env.get(SPACE_HOST_ENV, "").strip()
    if host and _HOST_RE.match(host):
        return f"https://{host}"
    return _base_from_request(request)


def _base_from_request(request: Any) -> str:
    headers = _headers_of(request)
    host = headers.get("x-forwarded-host", "").split(",", 1)[0].strip() or headers.get("host", "")
    proto = headers.get("x-forwarded-proto", "").split(",", 1)[0].strip()
    if host and _HOST_RE.match(host):
        scheme = proto if proto in ("http", "https") else "https"
        return f"{scheme}://{host}"
    url = getattr(request, "url", None) or getattr(getattr(request, "request", None), "url", None)
    if url:
        parts = urlsplit(str(url))
        if parts.scheme in ("http", "https") and parts.netloc:
            return f"{parts.scheme}://{parts.netloc}"
    return ""


def _headers_of(request: Any) -> dict[str, str]:
    if request is None:
        return {}
    headers = getattr(request, "headers", None)
    if headers is None:
        headers = getattr(getattr(request, "request", None), "headers", None)
    if headers is None:
        return {}
    try:
        return {str(key).lower(): str(value) for key, value in dict(headers).items()}
    except (TypeError, ValueError):
        return {}


def build(
    tab: str,
    *,
    fn: str | None = None,
    args: Mapping[str, Any] | None = None,
    base: str = "",
    tabs: Sequence[str] | None = None,
) -> str:
    """The link for `tab` (+ optional function and arguments); refuses a tab outside `tabs`."""
    if tabs is not None and tab not in tabs:
        raise ValueError(f"unknown tab {tab!r}; expected one of {tuple(tabs)}")
    return Permalink(tab, parse_fn(fn), dict(args) if args else None).url(base)
