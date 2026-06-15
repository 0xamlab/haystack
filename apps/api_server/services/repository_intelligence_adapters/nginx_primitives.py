from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str]
ResolveSuffixMatch = Callable[..., str | None]

NGINX_SUFFIXES = frozenset({".conf"})
NGINX_INDEX_BASENAMES = frozenset(
    {
        "nginx.conf",
        "fastcgi.conf",
        "fastcgi_params",
        "mime.types",
        "scgi_params",
        "uwsgi_params",
        "koi-utf",
        "koi-win",
        "win-utf",
    }
)
NGINX_PATH_PARTS = frozenset(
    {
        "nginx",
        "conf.d",
        "http-conf.d",
        "sites-available",
        "sites-enabled",
        "snippets",
        "stream-conf.d",
    }
)
_NGINX_DIRECTIVE_NAMES = frozenset(
    {
        "access_log",
        "default_type",
        "error_page",
        "error_log",
        "fastcgi_param",
        "fastcgi_pass",
        "grpc_pass",
        "include",
        "index",
        "keepalive_timeout",
        "listen",
        "proxy_pass",
        "resolver",
        "root",
        "scgi_pass",
        "sendfile",
        "server_name",
        "ssl_certificate",
        "try_files",
        "types_hash_max_size",
        "uwsgi_param",
        "uwsgi_pass",
        "worker_connections",
        "worker_processes",
    }
)
_NGINX_BLOCK_NAMES = frozenset({"events", "geo", "http", "location", "map", "server", "stream", "types", "upstream"})
# nginx directives are separated by ``;``/``{``/``}`` rather than newlines, so an
# ``include`` may sit inline inside a block (e.g. ``http { include mime.types; }``). Anchor
# on a directive boundary (line start or a preceding ``{``/``}``/``;``) instead of only the
# line start, otherwise inline includes are missed.
_INCLUDE_RE = re.compile(r"(?m)(?:^|[{};])\s*include\s+(?P<target>[^;#]+?)\s*;")
_UPSTREAM_RE = re.compile(r"(?m)^\s*upstream\s+(?P<name>[A-Za-z_][\w.-]*)\s*\{")
_MAP_RE = re.compile(r"(?m)^\s*map\s+\$[^\s]+\s+\$(?P<name>[A-Za-z_][\w.-]*)\s*\{")
_COMMENT_RE = re.compile(r"#.*?$", re.MULTILINE)
_PROXY_REF_RE = re.compile(
    r"(?m)\b(?:proxy_pass|fastcgi_pass|uwsgi_pass|scgi_pass|grpc_pass)\s+(?:https?://)?(?P<name>[A-Za-z_][\w.-]*)\b"
)


def strip_comments(text: str) -> str:
    return _COMMENT_RE.sub("", text)


def _line_number(text: str, offset: int) -> int:
    bounded_offset = max(0, min(offset, len(text)))
    return text.count("\n", 0, bounded_offset) + 1


def normalize_identifier(value: str) -> str:
    return str(value or "").strip().strip('"').strip("'")


def has_nginx_path_hints(path: Path | PurePosixPath) -> bool:
    normalized_path = PurePosixPath(path)
    lower_name = normalized_path.name.lower()
    if lower_name in NGINX_INDEX_BASENAMES:
        return True
    # Directory hints like ``snippets/`` or ``conf.d/`` are shared with other ecosystems
    # (e.g. Shopify/Liquid themes also use ``snippets/``). Only treat a file under such a
    # directory as an nginx hint when its own name is nginx-plausible — an nginx suffix
    # (``.conf``), no suffix at all (e.g. ``fastcgi_params``), or a known nginx basename —
    # so a foreign suffix like ``.liquid`` is not claimed.
    nginx_plausible_name = (
        normalized_path.suffix.lower() in NGINX_SUFFIXES
        or normalized_path.suffix == ""
        or lower_name in NGINX_INDEX_BASENAMES
    )
    if not nginx_plausible_name:
        return False
    lowered_parts = {part.lower() for part in normalized_path.parts}
    if lowered_parts & NGINX_PATH_PARTS:
        return True
    return any("nginx" in part.lower() for part in normalized_path.parts)


def _iter_directive_names(text: str) -> tuple[str, ...]:
    directives: list[str] = []
    for raw_line in strip_comments(text).splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("}"):
            continue
        if line.startswith("{"):
            continue
        if line.endswith("{"):
            directive_name = line[:-1].strip().split(None, 1)[0].lower()
        else:
            directive_name = line.split(None, 1)[0].rstrip(";").lower()
        directives.append(directive_name)
    return tuple(directives)


def is_probable_nginx_source(*, path: Path | PurePosixPath, text: str) -> bool:
    if not has_nginx_path_hints(path) or not text:
        return False
    directives = _iter_directive_names(text)
    if not directives:
        return False
    return any(
        directive in _NGINX_DIRECTIVE_NAMES or directive in _NGINX_BLOCK_NAMES
        for directive in directives
    )


def module_name_from_path(file_path: str) -> str:
    normalized_path = PurePosixPath(file_path)
    if normalized_path.name in NGINX_INDEX_BASENAMES:
        return normalized_path.name
    if normalized_path.suffix:
        return normalized_path.stem
    return normalized_path.name


def iter_symbol_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    seen_names: set[tuple[str, str]] = set()
    for symbol_kind, pattern in (("upstream", _UPSTREAM_RE), ("map", _MAP_RE)):
        for match in pattern.finditer(stripped_text):
            symbol_name = normalize_identifier(match.group("name") or "")
            key = (symbol_kind, symbol_name)
            if not symbol_name or key in seen_names:
                continue
            seen_names.add(key)
            entries.append((symbol_name, symbol_kind, _line_number(stripped_text, match.start())))
    return tuple(entries)


def iter_dependency_entries(text: str) -> tuple[tuple[str, int], ...]:
    stripped_text = strip_comments(text)
    return tuple(
        (
            normalize_identifier(match.group("target") or ""),
            _line_number(stripped_text, match.start()),
        )
        for match in _INCLUDE_RE.finditer(stripped_text)
        if normalize_identifier(match.group("target") or "")
    )


def iter_reference_entries(
    text: str,
    *,
    local_symbol_names: set[str],
) -> tuple[tuple[str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, int]] = []
    seen_entries: set[tuple[str, int]] = set()
    for match in _PROXY_REF_RE.finditer(stripped_text):
        symbol_name = normalize_identifier(match.group("name") or "")
        if not symbol_name or symbol_name not in local_symbol_names:
            continue
        entry = (symbol_name, _line_number(stripped_text, match.start()))
        if entry in seen_entries:
            continue
        seen_entries.add(entry)
        entries.append(entry)
    return tuple(entries)


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
    text: str | None = None,
) -> set[str]:
    del root_path, stable_identifier
    normalized_path = PurePosixPath(file_path)
    if not has_nginx_path_hints(normalized_path):
        return set()
    aliases = {
        file_path,
        normalized_path.name,
        module_name_from_path(file_path),
    }
    if normalized_path.suffix:
        aliases.add(str(normalized_path.with_suffix("")))
        aliases.add(normalized_path.stem)
    if text:
        aliases.update(name for name, _kind, _line in iter_symbol_entries(text))
    return {alias for alias in aliases if alias}


def collect_symbols(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
) -> tuple[Any, ...]:
    from apps.api_server.services.repository_intelligence_contracts import _Symbol

    module_name = module_name_from_path(file_path)
    line_count = max(1, text.count("\n") + 1)
    symbols = [
        _Symbol(
            symbol_id=stable_identifier(
                "symbol",
                {"file_path": file_path, "symbol_name": module_name, "kind": "nginx"},
            ),
            symbol_name=module_name,
            symbol_kind="nginx",
            start_line=1,
            end_line=line_count,
            parent_symbol_id=None,
            signature=f"nginx {module_name}",
        )
    ]
    module_symbol_id = symbols[0].symbol_id
    for symbol_name, symbol_kind, line_number in iter_symbol_entries(text):
        symbols.append(
            _Symbol(
                symbol_id=stable_identifier(
                    "symbol",
                    {"file_path": file_path, "symbol_name": symbol_name, "kind": symbol_kind},
                ),
                symbol_name=symbol_name,
                symbol_kind=symbol_kind,
                start_line=line_number,
                end_line=line_number,
                parent_symbol_id=module_symbol_id,
                signature=f"{symbol_kind} {symbol_name}",
            )
        )
    return tuple(symbols)


def source_symbol_name_for_line(
    symbol_entries: tuple[tuple[str, str, int], ...],
    *,
    line_number: int,
) -> str | None:
    best_name: str | None = None
    best_line = -1
    for name, _kind, symbol_line in symbol_entries:
        if symbol_line <= line_number and symbol_line >= best_line:
            best_name = name
            best_line = symbol_line
    return best_name
