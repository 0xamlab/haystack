#!/usr/bin/env python3
"""A-Z GitBook docs audit for source, live-site, agent, and search ingestion drift.

The existing docs gates prove structural quality and source-surface coverage. This gate
adds the operational layer:

* inventory every page, Markdown/HTML link, fenced snippet, shell command, and product claim;
* fail on malformed machine-readable snippets, private/local leakage, secret-like values,
  broken internal links, weak Cursor/Codex setup coverage, weak Google/LLM ingestion coverage,
  and live GitBook drift;
* classify customer-affecting commands instead of executing them blindly.

The JSON report is deterministic for the same source tree and live responses: no timestamps,
random ids, or host-local paths are embedded beyond the provided source/live arguments.
"""

from __future__ import annotations

import argparse
import ast
import concurrent.futures
import hashlib
import json
import re
import subprocess
import tempfile
import tomllib
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = ROOT / "gitbook"

SHELL_LANGS = {"bash", "sh", "shell", "console", "zsh"}
JSON_LANGS = {"json", "jsonc"}
PYTHON_LANGS = {"python", "py"}
TOML_LANGS = {"toml"}
YAML_LANGS = {"yaml", "yml"}

PRODUCT_TERMS = {
    "algenta",
    "codna",
    "cohenta",
    "decimas",
    "escrypto",
    "mission",
}

REQUIRED_AGENT_EVAL_IDS = {
    "cursor-mcp-install",
    "codex-mcp-install",
    "google-search-crawlability",
    "gemini-docs-ingestion",
}

SECRET_PATTERNS = (
    re.compile(r"\bde_(?:live|test)_[A-Za-z0-9_=-]{16,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9][A-Za-z0-9_-]{18,}\b"),
    re.compile(r"\bghp_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bghs_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bAIza[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
    re.compile(r"\b[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\b"),
)

DISALLOWED_PLACEHOLDER_SECRET_PREFIX_PATTERNS = (
    re.compile(r"\b(?:ghp|gho|ghs|ghu|ghr)_[A-Za-z0-9_./=-]*\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_./=-]*\b"),
    re.compile(r"\bsk_(?:live|test)_[A-Za-z0-9_./=-]*\b"),
    re.compile(r"\bpk_(?:live|test)_[A-Za-z0-9_./=-]*\b"),
    re.compile(r"\bwhsec_[A-Za-z0-9_./=-]*\b"),
    re.compile(r"\bflyv1[A-Za-z0-9_./=-]*\b"),
)

PRIVATE_LEAK_PATTERNS = (
    re.compile(r"/Users/[A-Za-z0-9._-]+"),
    re.compile(r"/private/tmp\b"),
    re.compile(r"\bdecision-engine/\.env\b"),
    re.compile(r"\bangel@[A-Za-z0-9_.-]+\b", re.IGNORECASE),
    re.compile(r"\bglobet\.io\b", re.IGNORECASE),
    re.compile(r"\b(private repo|internal-only|do not publish)\b", re.IGNORECASE),
    re.compile(r"\binternal plan\b", re.IGNORECASE),
    re.compile(r"\bcodna(?:\.ai)?\b", re.IGNORECASE),
)

RUNTIME_ENCAPSULATION_PATTERNS = (
    re.compile(r"\brun the mojo engine\b", re.IGNORECASE),
    re.compile(r"\b(?:local\s+)?(?:algenta\s+)?runtime daemon\b", re.IGNORECASE),
    re.compile(r"\b(?:mojo|native|bundled|runtime) sidecar\b", re.IGNORECASE),
    re.compile(r"\bsidecar engine\b", re.IGNORECASE),
    re.compile(r"\bde runtime (?:start|stop)\b", re.IGNORECASE),
    re.compile(r"\bstart the runtime worker\b", re.IGNORECASE),
    re.compile(r"\bmake (?:setup-mojo|build-mojo|test-mojo)\b", re.IGNORECASE),
    re.compile(r"\b(?:RUNTIME_FALLBACK_MODE|MOJO_BINARY_PATH|MOJO_ALLOW_SUBPROCESS_FALLBACK)\b"),
    re.compile(r"\b(?:subprocess_fallback|local_dev_daemon)\b"),
    re.compile(r"\bmojo_build/simulate\b"),
    re.compile(r"\bsource[- ]built\b", re.IGNORECASE),
    re.compile(r"\bpixi\b", re.IGNORECASE),
)

DISALLOWED_PUBLIC_PACKAGE_PATTERNS = (
    (
        re.compile(r"@algenta/sdk"),
        "wrong_typescript_sdk_package",
        ("Docs reference @algenta/sdk, but the published TypeScript package name is algenta-sdk."),
    ),
)

SUMMARY_HEADING_ROUTE_SLUGS = {
    "Getting Started": "getting-started",
    "Engine runtime": "engine-runtime",
    "Concepts": "concepts",
    "Guides": "guides",
    "LLM API": "llm-api",
    "SDKs": "sdks",
    "MCP tools": "mcp-tools",
    "Microsoft & Azure": "microsoft-and-azure",
    "Deploy & Operate": "deploy-and-operate",
    "HTTP API": "http-api",
    "Connectors": "connectors",
    "Help": "help",
}

SUMMARY_ROUTE_PREFIX_STRIPS = {
    "run-the-engine": ("engine/", "concepts/"),
    "concepts": ("concepts/",),
    "guides": ("guides/",),
    "llm-api": ("llm/",),
    "sdks": ("sdk/",),
    "mcp-tools": ("mcp-tools/",),
    "deploy-and-operate": ("operate/",),
    "http-api": ("api/",),
    "connectors": ("connectors/",),
    "help": ("help/",),
}

REQUIRED_PYPI_PACKAGES = ("algenta-sdk", "algenta-mcp")
REQUIRED_NPM_PACKAGES = ("algenta-sdk",)
OPTIONAL_RUNTIME_PYPI_PACKAGES = ("algenta", "algenta-runtime-native")

PUBLIC_ALGENTA_RUNTIME_INSTALL_RE = re.compile(
    r"(?im)^\s*(?:\$\s*)?(?:python(?:3(?:\.\d+)?)?\s+-m\s+)?"
    r"pip\s+install\s+(?!-e\b)[\"']?algenta[\"']?(?:\s|$)"
)
PUBLIC_RUNTIME_NATIVE_INSTALL_RE = re.compile(
    r"(?im)^\s*(?:\$\s*)?(?:python(?:3(?:\.\d+)?)?\s+-m\s+)?"
    r"pip\s+install\s+(?!-e\b)[\"']?algenta-runtime-native[\"']?(?:\s|$)"
)
RUNTIME_NOT_LIVE_PHRASES = (
    "public pypi runtime distribution is not live yet",
    "public pypi runtime release is not live yet",
    "public pypi package is not live yet",
    "runtime distribution is not public on pypi yet",
    "not a public pypi install yet",
    "not a public registry install yet",
    "not a public pypi install path today",
)


@dataclass(frozen=True)
class Issue:
    severity: str
    code: str
    message: str
    path: str = ""
    line: int | None = None
    details: dict[str, Any] | None = None

    def to_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
        }
        if self.path:
            out["path"] = self.path
        if self.line is not None:
            out["line"] = self.line
        if self.details:
            out["details"] = self.details
        return out


@dataclass(frozen=True)
class CodeFence:
    path: Path
    rel_path: str
    line: int
    info: str
    language: str
    body: str


@dataclass(frozen=True)
class Link:
    path: Path
    rel_path: str
    line: int
    target: str
    kind: str


@dataclass(frozen=True)
class ShellCommand:
    line: int
    command: str


@dataclass(frozen=True)
class EndpointMention:
    path: str
    line: int
    method: str | None
    scope: str


def _rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _report_path(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _line_for_offset(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _markdown_pages(source: Path) -> list[Path]:
    return sorted(path for path in source.rglob("*.md") if path.is_file())


def _route_tail_for_summary_target(section_slug: str, target: str) -> str:
    tail = target.split("#", 1)[0].removesuffix(".md").strip("/")
    for prefix in SUMMARY_ROUTE_PREFIX_STRIPS.get(section_slug, ()):  # deterministic order
        if tail.startswith(prefix):
            return tail[len(prefix) :]
    path_tail_sections = {
        "microsoft-and-azure",
        "deploy-and-operate",
        "engine-runtime",
    }
    if "/" in tail and section_slug in path_tail_sections:
        return tail.rsplit("/", 1)[-1]
    if "/" in tail and section_slug in {"getting-started", "help"}:
        return tail.rsplit("/", 1)[-1]
    return tail


def _summary_expected_sitemap_urls(source: Path, base_url: str) -> list[str]:
    summary_path = source / "SUMMARY.md"
    if not summary_path.is_file():
        return []
    base = base_url.rstrip("/")
    urls: list[str] = []
    current_heading: str | None = None
    link_re = re.compile(r"^\s*\*\s+\[[^\]]+\]\(([^)]+\.md(?:#[^)]+)?)\)")
    for line in _read(summary_path).splitlines():
        heading_match = re.match(r"^##\s+(.+?)\s*$", line)
        if heading_match:
            current_heading = heading_match.group(1).strip()
            continue
        link_match = link_re.match(line)
        if not link_match:
            continue
        target = link_match.group(1)
        if current_heading is None and target.split("#", 1)[0] == "overview.md":
            route = ""
        else:
            section_slug = SUMMARY_HEADING_ROUTE_SLUGS.get(current_heading or "")
            if not section_slug:
                continue
            tail = _route_tail_for_summary_target(section_slug, target)
            route = f"/{section_slug}/{tail}" if tail else f"/{section_slug}"
        url = f"{base}{route}"
        if url not in urls:
            urls.append(url)
    return urls


def _strip_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end < 0:
        return {}, text
    raw = text[4:end]
    fields: dict[str, str] = {}
    for line in raw.splitlines():
        if ":" in line and not line.startswith(" "):
            key, value = line.split(":", 1)
            fields[key.strip()] = value.strip().strip('"')
    return fields, text[end + 4 :]


def _extract_code_fences(path: Path, rel_path: str, text: str) -> list[CodeFence]:
    fences: list[CodeFence] = []
    lines = text.splitlines()
    in_fence = False
    start_line = 0
    info = ""
    body: list[str] = []
    for idx, line in enumerate(lines, start=1):
        if line.lstrip().startswith("```"):
            marker = line.lstrip()
            if not in_fence:
                in_fence = True
                start_line = idx
                info = marker[3:].strip()
                body = []
            else:
                lang = info.split(None, 1)[0].lower() if info else ""
                fences.append(
                    CodeFence(
                        path=path,
                        rel_path=rel_path,
                        line=start_line,
                        info=info,
                        language=lang,
                        body="\n".join(body),
                    )
                )
                in_fence = False
                info = ""
                body = []
            continue
        if in_fence:
            body.append(line)
    return fences


def _outside_fence_lines(text: str) -> list[str]:
    out: list[str] = []
    in_fence = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence:
            out.append(line)
    return out


def _extract_links(path: Path, rel_path: str, text: str) -> list[Link]:
    links: list[Link] = []
    md_link = re.compile(r"\[[^\]]+\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
    html_link = re.compile(r"<a\s+[^>]*href=\"([^\"]+)\"", re.IGNORECASE)
    for regex in (md_link, html_link):
        for match in regex.finditer(text):
            target = match.group(1).strip()
            if target.startswith("mailto:"):
                kind = "mailto"
            elif target.startswith("#"):
                kind = "anchor"
            elif urllib.parse.urlparse(target).scheme in {"http", "https"}:
                kind = "external"
            else:
                kind = "internal"
            links.append(
                Link(
                    path=path,
                    rel_path=rel_path,
                    line=_line_for_offset(text, match.start()),
                    target=target,
                    kind=kind,
                )
            )
    return links


def _looks_like_shell_output(command: str) -> bool:
    """Reject response payload lines that were placed in a shell fence."""
    first = command.lstrip().splitlines()[0] if command.strip() else ""
    if not first:
        return True
    if first[0] in "{[}]\"'":
        return True
    if re.match(r"^(?:HTTP/\d|[0-9]{3}\s|<[/!?A-Za-z])", first):
        return True
    return bool(re.match(r"^[A-Za-z0-9_.-]+:\s", first))


def _logical_shell_commands(body: str, *, start_line: int = 1) -> list[ShellCommand]:
    """Parse command-sized shell records without splitting quoted JSON payloads."""
    commands: list[ShellCommand] = []
    current: list[str] = []
    command_line = start_line
    quote: str | None = None
    heredoc_delimiter: str | None = None
    block_depth = 0

    def finish() -> None:
        nonlocal current
        command = "\n".join(part for part in current if part).strip()
        if command and not _looks_like_shell_output(command):
            commands.append(ShellCommand(line=command_line, command=command))
        current = []

    for offset, raw in enumerate(body.splitlines()):
        line_number = start_line + offset
        stripped = raw.strip()
        if not current and (not stripped or stripped.startswith("#")):
            continue
        if not current:
            command_line = line_number
            if stripped.startswith("$ "):
                stripped = stripped[2:].strip()

        current.append(stripped)
        if heredoc_delimiter is not None:
            if stripped == heredoc_delimiter:
                heredoc_delimiter = None
                finish()
            continue

        heredoc_match = re.search(r"<<-?\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?", stripped)
        if heredoc_match:
            heredoc_delimiter = heredoc_match.group(1)
            continue

        if len(current) == 1 and re.match(r"^(?:for|while|until|if|case)\b", stripped):
            block_depth += 1
        if re.match(r"^(?:done|fi|esac)\b", stripped):
            block_depth = max(0, block_depth - 1)

        escaped = False
        for char in stripped:
            if escaped:
                escaped = False
                continue
            if char == "\\" and quote != "'":
                escaped = True
                continue
            if char in {"'", '"'}:
                if quote is None:
                    quote = char
                elif quote == char:
                    quote = None

        if quote is not None or stripped.endswith("\\"):
            continue

        if block_depth:
            continue
        finish()

    if current:
        finish()
    return commands


def _is_safe_relative_output_path(value: str) -> bool:
    path = PurePosixPath(value)
    return bool(value) and not path.is_absolute() and ".." not in path.parts


def _is_provably_safe_static_shell_command(command: str) -> bool:
    stripped = command.strip()
    if stripped.startswith("export "):
        if "$" in stripped or "`" in stripped:
            return False
        return bool(
            re.fullmatch(
                r"export\s+[A-Za-z_][A-Za-z0-9_]*="
                r'(?:"[^"\n]*"|\'[^\'\n]*\'|[^\s;&|<>]+)(?:\s+#.*)?',
                stripped,
            )
        )

    if stripped.startswith("echo "):
        match = re.fullmatch(
            r"echo\s+"
            r"(?P<payload>'[^'\n]*'|\"[^\"\n]*\"|[A-Za-z0-9_.,:/@%+=-]+)"
            r"(?:\s+>>?\s+(?P<output>[A-Za-z0-9._/-]+))?",
            stripped,
        )
        if not match or "$" in stripped or "`" in stripped or "\\" in stripped:
            return False
        output = match.group("output")
        return output is None or _is_safe_relative_output_path(output)

    if stripped.startswith("cat "):
        lines = stripped.splitlines()
        if len(lines) < 3 or "`" in stripped:
            return False
        header = re.fullmatch(
            r"cat\s+>\s+([A-Za-z0-9._/-]+)\s+<<'([A-Za-z0-9_]+)'",
            lines[0].strip(),
        )
        return bool(
            header
            and _is_safe_relative_output_path(header.group(1))
            and lines[-1].strip() == header.group(2)
            and sum(line.strip() == header.group(2) for line in lines[1:]) == 1
        )

    return False


def _classify_shell_command(command: str) -> str:
    lowered = command.lower()
    destructive_verb = re.search(
        r"(?:^|[\s;&|()])(?:sudo\s+)?rm(?:\s|$)|\b(?:delete|destroy|drop|revoke|truncate|unlink)\b",
        lowered,
    )
    if destructive_verb:
        return "destructive_mutation"
    curl_mutation = re.search(r"\bcurl\b", lowered) and (
        re.search(
            r"(?:^|\s)(?:-x|--request)\s+(?:post|put|patch|delete)\b", lowered
        )
        or re.search(
            r"(?:^|\s)(?:-d|--data(?:-[a-z-]+)?|--json|--form|--upload-file)(?:\s|=)",
            lowered,
        )
        or re.search(r"(?:^|\s)(?:-F|-T)(?:\s|=)", command)
    )
    cli_mutation = lowered.startswith("de ") and re.search(
        r"\b(?:approve|cancel|connect|create|disconnect|execute|fire|login|logout|pause|refresh|resume|set-key|submit|update)\b",
        lowered,
    )
    if curl_mutation or cli_mutation:
        return "external_or_mutating"
    if any(
        token in lowered
        for token in (
            "docker compose up",
            "pip install",
            "pipx install",
            "npm install",
            "pnpm install",
            "npx ",
        )
    ):
        return "environment_mutating"
    if lowered.startswith(("export ", "echo ", "cat ")):
        if _is_provably_safe_static_shell_command(command):
            return "safe_static"
        if "$" in command or "`" in command:
            return "requires_environment"
        return "static_only"
    if lowered.startswith(
        ("curl ", "python3 ", "python ", "de ", "algenta ", "codex ", "claude ", "npx ")
    ):
        return "requires_environment"
    return "static_only"


def _validate_shell_command(rel_path: str, command: ShellCommand) -> Issue | None:
    result = subprocess.run(  # noqa: S603 - bash -n parses but never executes the docs command.
        ["/bin/bash", "-n", "-c", command.command],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    if result.returncode == 0:
        return None
    return Issue(
        "ERROR",
        "invalid_shell_command",
        "Shell command is not valid Bash syntax.",
        rel_path,
        command.line,
        {"stderr": result.stderr.strip()[:300]},
    )


def _execute_safe_shell_command(
    command: str, rel_path: str, line: int
) -> tuple[Issue | None, dict[str, Any]]:
    if not _is_provably_safe_static_shell_command(command):
        return (
            Issue(
                "ERROR",
                "unsafe_command_execution_refused",
                "Command classified for execution did not satisfy the safe-static contract.",
                rel_path,
                line,
            ),
            {"execution_attempted": False, "executed": False, "execution_status": "refused"},
        )

    with tempfile.TemporaryDirectory(prefix="algenta-docs-command-") as temp_dir:
        root = Path(temp_dir)
        env = {
            "BASH_ENV": "/dev/null",
            "ENV": "/dev/null",
            "HOME": str(root),
            "LANG": "C",
            "LC_ALL": "C",
            "PATH": "/usr/bin:/bin",
            "TMPDIR": str(root),
        }
        try:
            result = subprocess.run(  # noqa: S603 - strict allowlist and isolated environment.
                [
                    "/bin/bash",
                    "--noprofile",
                    "--norc",
                    "-e",
                    "-u",
                    "-o",
                    "pipefail",
                    "-c",
                    f"umask 077\n{command}",
                ],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return (
                Issue(
                    "ERROR",
                    "safe_command_execution_timeout",
                    "Safe-static command exceeded the five-second execution limit.",
                    rel_path,
                    line,
                ),
                {
                    "execution_attempted": True,
                    "executed": False,
                    "execution_status": "timeout",
                },
            )

        created_files = []
        for path in sorted(candidate for candidate in root.rglob("*") if candidate.is_file()):
            data = path.read_bytes()
            created_files.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "bytes": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                }
            )
        execution = {
            "execution_attempted": True,
            "executed": result.returncode == 0,
            "execution_status": "pass" if result.returncode == 0 else "fail",
            "execution_exit_code": result.returncode,
            "stdout_bytes": len(result.stdout.encode("utf-8")),
            "stdout_sha256": hashlib.sha256(result.stdout.encode("utf-8")).hexdigest(),
            "files_created": created_files,
        }
        if result.returncode == 0:
            return None, execution
        return (
            Issue(
                "ERROR",
                "safe_command_execution_failed",
                "Safe-static command failed in its isolated execution environment.",
                rel_path,
                line,
                {"exit_code": result.returncode},
            ),
            execution,
        )


def _is_placeholder_secret(value: str) -> bool:
    lowered = value.lower()
    if any(token in lowered for token in ("your", "example", "placeholder", "xxxxx")):
        return True
    tail = value.split("_", 2)[-1] if "_" in value else value
    if "..." in value or "<" in value or ">" in value:
        return True
    compact = re.sub(r"[^A-Za-z0-9]", "", tail)
    return bool(compact) and set(compact.lower()) <= {"x"}


def _find_secret_issues(path: Path, rel_path: str, text: str) -> list[Issue]:
    issues: list[Issue] = []
    for regex in SECRET_PATTERNS:
        for match in regex.finditer(text):
            token = match.group(0)
            if _is_placeholder_secret(token):
                continue
            issues.append(
                Issue(
                    severity="ERROR",
                    code="secret_like_value",
                    message="Docs contain a concrete-looking secret or bearer token.",
                    path=rel_path,
                    line=_line_for_offset(text, match.start()),
                    details={"prefix": token[:12]},
                )
            )
    for regex in DISALLOWED_PLACEHOLDER_SECRET_PREFIX_PATTERNS:
        for match in regex.finditer(text):
            token = match.group(0)
            issues.append(
                Issue(
                    severity="ERROR",
                    code="secret_like_placeholder_prefix",
                    message=(
                        "Docs contain a provider-specific secret prefix placeholder; "
                        "use a neutral environment-variable placeholder instead."
                    ),
                    path=rel_path,
                    line=_line_for_offset(text, match.start()),
                    details={"prefix": token[:16]},
                )
            )
    for regex in PRIVATE_LEAK_PATTERNS:
        for match in regex.finditer(text):
            issues.append(
                Issue(
                    severity="ERROR",
                    code="private_or_internal_leak",
                    message="Docs contain private local or internal-only information.",
                    path=rel_path,
                    line=_line_for_offset(text, match.start()),
                    details={"match": match.group(0)[:80]},
                )
            )
    return issues


def _find_public_package_issues(path: Path, rel_path: str, text: str) -> list[Issue]:
    issues: list[Issue] = []
    for regex, code, message in DISALLOWED_PUBLIC_PACKAGE_PATTERNS:
        for match in regex.finditer(text):
            issues.append(
                Issue(
                    severity="ERROR",
                    code=code,
                    message=message,
                    path=rel_path,
                    line=_line_for_offset(text, match.start()),
                    details={"reference": match.group(0)},
                )
            )
    return issues


def _find_runtime_encapsulation_issues(rel_path: str, text: str) -> list[Issue]:
    issues: list[Issue] = []
    for regex in RUNTIME_ENCAPSULATION_PATTERNS:
        for match in regex.finditer(text):
            issues.append(
                Issue(
                    severity="ERROR",
                    code="public_runtime_encapsulation_violation",
                    message=(
                        "Public docs expose separate runtime setup or internal runtime controls."
                    ),
                    path=rel_path,
                    line=_line_for_offset(text, match.start()),
                    details={"match": match.group(0)[:80]},
                )
            )
    return issues


def _pricing_contract_name(rel_path: str) -> str | None:
    normalized = rel_path.lower().split("?", 1)[0]
    if normalized.endswith("/rate-limits.md") or normalized == "api/rate-limits.md":
        return "rate_limits"
    if normalized.endswith("/licensing.md") or normalized == "licensing.md":
        return "licensing"
    if normalized.endswith("/billing.md") or normalized == "billing.md":
        return "billing"
    return None


def _find_pricing_contract_issues(rel_path: str, text: str) -> list[Issue]:
    contract = _pricing_contract_name(rel_path)
    if contract is None:
        return []

    required: dict[str, tuple[tuple[str, str], ...]] = {
        "rate_limits": (
            (r"Decisions and executions are unlimited on every edition", "unlimited decisions"),
            (r"no monthly quota", "no monthly quota"),
            (r"no .*edition-specific request meter", "no edition request meter"),
            (r"\|\s*Community\s*\|\s*unlimited\s*\|\s*1\s*\|", "Community worker cap 1"),
        ),
        "licensing": (
            (r"\|\s*Community \(free\)\s*\|\s*1\s*\|", "Community worker cap 1"),
            (r"\|\s*Pro\s*\|\s*5\s*\|", "Pro worker cap 5"),
            (r"\|\s*Team\s*\|\s*20\s*\|", "Team worker cap 20"),
            (r"downgrades to Community", "lapse downgrade to Community"),
            (
                r"1 device, 1 worker, 1 seat, non-commercial",
                "Community lapse capacity",
            ),
        ),
        "billing": (
            (r"unlimited decisions", "unlimited decisions"),
            (r"not sent to Algenta or Stripe", "no outbound execution counts"),
            (r"not an Algenta usage bill", "local audit is not an Algenta usage bill"),
        ),
    }
    stale: dict[str, tuple[tuple[str, str], ...]] = {
        "rate_limits": (
            (r"Requests/minute", "edition requests-per-minute table"),
            (r"Monthly execution governance", "monthly execution governance table"),
            (r"reaches its monthly ceiling", "monthly quota rejection guidance"),
        ),
        "licensing": (
            (r"per-node self-host plan", "removed per-node self-host plan"),
            (r"lapsed subscription genuinely expires", "obsolete lapse behavior"),
        ),
        "billing": (
            (
                r"Metering, quotas, and per-key limits are",
                "obsolete plan-metering explanation",
            ),
        ),
    }

    issues: list[Issue] = []
    for pattern, label in required[contract]:
        if re.search(pattern, text, re.IGNORECASE | re.DOTALL):
            continue
        issues.append(
            Issue(
                severity="ERROR",
                code="pricing_contract_required_text_missing",
                message="Pricing-critical documentation is missing a required current claim.",
                path=rel_path,
                details={"contract": contract, "required": label},
            )
        )
    for pattern, label in stale[contract]:
        match = re.search(pattern, text, re.IGNORECASE)
        if match is None:
            continue
        issues.append(
            Issue(
                severity="ERROR",
                code="pricing_contract_stale_text",
                message="Pricing-critical documentation contains an obsolete claim.",
                path=rel_path,
                line=_line_for_offset(text, match.start()),
                details={"contract": contract, "stale": label},
            )
        )
    return issues


def _validate_machine_snippet(fence: CodeFence) -> list[Issue]:
    issues: list[Issue] = []
    lang = fence.language
    body = fence.body.strip()
    if not body:
        return issues
    if fence.language in JSON_LANGS and not body.startswith(("{", "[")):
        return issues
    if fence.language in JSON_LANGS and "..." in body:
        return issues
    try:
        if lang in JSON_LANGS:
            json.loads(body)
        elif lang in TOML_LANGS:
            tomllib.loads(body)
        elif lang in PYTHON_LANGS:
            ast.parse(body)
    except Exception as exc:  # noqa: BLE001 - report malformed docs snippets with context.
        issues.append(
            Issue(
                severity="ERROR",
                code=f"invalid_{lang}_snippet",
                message=f"Malformed {lang} snippet: {exc}",
                path=fence.rel_path,
                line=fence.line,
            )
        )
    return issues


def _validate_internal_link(source: Path, link: Link, all_pages: set[Path]) -> Issue | None:
    if link.kind != "internal":
        return None
    raw_target = link.target.split("#", 1)[0]
    if not raw_target or not raw_target.endswith(".md"):
        return None
    candidate = (link.path.parent / raw_target).resolve()
    if candidate not in all_pages:
        return Issue(
            severity="ERROR",
            code="broken_internal_link",
            message=f"Internal Markdown link does not resolve: {link.target}",
            path=link.rel_path,
            line=link.line,
            details={"target": link.target, "source_root": str(source)},
        )
    return None


HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options"}
ENDPOINT_MENTION_RE = re.compile(
    r"(?:(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s+)?"
    r"((?:/v1|/auth|/oauth|/mcp)/[A-Za-z0-9_{}./:*-]+)"
)


def _canonical_endpoint_path(path: str) -> str:
    clean = path.rstrip(".,;:`'\")]")
    return re.sub(r"\{[^{}]+\}", "{}", clean)


def _openapi_operations() -> dict[str, set[str]]:
    spec_path = ROOT / "schemas" / "openapi" / "openapi.yaml"
    if not spec_path.is_file():
        return {}
    operations: dict[str, set[str]] = {}
    current_path: str | None = None
    for line in _read(spec_path).splitlines():
        path_match = re.match(r"^  (/[^\s:]+):\s*$", line)
        if path_match:
            current_path = _canonical_endpoint_path(path_match.group(1))
            operations.setdefault(current_path, set())
            continue
        method_match = re.match(r"^    ([a-z]+):\s*$", line)
        if current_path and method_match and method_match.group(1) in HTTP_METHODS:
            operations[current_path].add(method_match.group(1).upper())
    return operations


def _source_route_operations() -> dict[str, set[str]]:
    """Derive FastAPI route contracts without importing application dependencies."""
    operations: dict[str, set[str]] = {}
    source_root = ROOT / "apps" / "api_server"
    for path in sorted(source_root.rglob("*.py")):
        try:
            module = ast.parse(_read(path))
        except SyntaxError:
            continue

        prefixes: dict[str, str] = {}
        for node in ast.walk(module):
            if not isinstance(node, ast.Assign | ast.AnnAssign):
                continue
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if not isinstance(node.value, ast.Call):
                continue
            factory = node.value.func
            factory_name = (
                factory.id
                if isinstance(factory, ast.Name)
                else factory.attr
                if isinstance(factory, ast.Attribute)
                else ""
            )
            if factory_name not in {"APIRouter", "FastAPI"}:
                continue
            prefix = ""
            for keyword in node.value.keywords:
                if (
                    keyword.arg == "prefix"
                    and isinstance(keyword.value, ast.Constant)
                    and isinstance(keyword.value.value, str)
                ):
                    prefix = keyword.value.value
            for target in targets:
                if isinstance(target, ast.Name):
                    prefixes[target.id] = prefix

        for node in ast.walk(module):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            for decorator in node.decorator_list:
                if (
                    not isinstance(decorator, ast.Call)
                    or not isinstance(decorator.func, ast.Attribute)
                    or decorator.func.attr not in HTTP_METHODS
                    or not decorator.args
                    or not isinstance(decorator.args[0], ast.Constant)
                    or not isinstance(decorator.args[0].value, str)
                ):
                    continue
                owner = decorator.func.value
                owner_name = owner.id if isinstance(owner, ast.Name) else ""
                route = prefixes.get(owner_name, "") + decorator.args[0].value
                canonical = _canonical_endpoint_path(route)
                operations.setdefault(canonical, set()).add(decorator.func.attr.upper())
    return operations


def _matching_endpoint_methods(
    path: str, operations: dict[str, set[str]]
) -> tuple[set[str] | None, str]:
    if path in operations:
        return operations[path], "exact"
    for template, methods in operations.items():
        pattern = "^" + re.escape(template).replace(r"\{\}", "[^/]+") + "$"
        if re.match(pattern, path):
            return methods, "template"
    if path.endswith("*"):
        prefix = path[:-1]
        prefix_matches = [
            methods for route, methods in operations.items() if route.startswith(prefix)
        ]
        if prefix_matches:
            return set().union(*prefix_matches), "wildcard_family"
    if path.endswith("/") or "/" in path:
        prefix = path if path.endswith("/") else f"{path}/"
        prefix_matches = [
            methods for route, methods in operations.items() if route.startswith(prefix)
        ]
        if prefix_matches:
            return set().union(*prefix_matches), "route_family"
    return None, "unresolved"


def _extract_endpoint_mentions(text: str) -> list[EndpointMention]:
    mentions: list[EndpointMention] = []
    for match in ENDPOINT_MENTION_RE.finditer(text):
        before = text[max(0, match.start() - 200) : match.start()]
        host_match = re.search(r"https?://([A-Za-z0-9.-]+)(?::\d+)?$", before)
        host = host_match.group(1).lower() if host_match else ""
        scope = (
            "external"
            if host and host not in {"api.algenta.ai", "localhost", "127.0.0.1"}
            else "algenta"
        )
        mentions.append(
            EndpointMention(
                path=_canonical_endpoint_path(match.group(2)),
                line=_line_for_offset(text, match.start()),
                method=match.group(1),
                scope=scope,
            )
        )
    return mentions


def _audit_openapi_public_identity() -> tuple[list[Issue], dict[str, Any]]:
    spec_path = ROOT / "schemas" / "openapi" / "openapi.yaml"
    if not spec_path.is_file():
        issue = Issue(
            "ERROR",
            "openapi_schema_missing",
            "Canonical OpenAPI schema is missing.",
            "schemas/openapi/openapi.yaml",
        )
        return [issue], {
            "algenta_title": False,
            "cross_product_mentions": 0,
            "runtime_encapsulation_mentions": 0,
        }

    text = _read(spec_path)
    matches = list(re.finditer(r"\bcodna(?:\.ai)?\b", text, re.IGNORECASE))
    issues = [
        Issue(
            "ERROR",
            "openapi_cross_product_identity",
            "Public Algenta OpenAPI schema contains Codna identity text.",
            "schemas/openapi/openapi.yaml",
            _line_for_offset(text, match.start()),
        )
        for match in matches
    ]
    runtime_matches = [
        match
        for pattern in RUNTIME_ENCAPSULATION_PATTERNS
        for match in pattern.finditer(text)
    ]
    issues.extend(
        Issue(
            "ERROR",
            "openapi_runtime_encapsulation_leak",
            "Public OpenAPI schema exposes a user-managed runtime lifecycle detail.",
            "schemas/openapi/openapi.yaml",
            _line_for_offset(text, match.start()),
        )
        for match in runtime_matches
    )
    algenta_title = bool(re.search(r"(?m)^  title: Algenta API\s*$", text))
    if not algenta_title:
        issues.append(
            Issue(
                "ERROR",
                "openapi_algenta_title_missing",
                "Public OpenAPI schema title must be Algenta API.",
                "schemas/openapi/openapi.yaml",
            )
        )
    operations = _openapi_operations()
    return issues, {
        "algenta_title": algenta_title,
        "cross_product_mentions": len(matches),
        "runtime_encapsulation_mentions": len(runtime_matches),
        "paths": len(operations),
        "operations": sum(len(methods) for methods in operations.values()),
    }


def _validate_endpoint_mentions(
    rel_path: str,
    mentions: list[EndpointMention],
    openapi_operations: dict[str, set[str]],
) -> list[Issue]:
    issues: list[Issue] = []
    for mention in mentions:
        if mention.scope != "algenta":
            continue
        methods, match_kind = _matching_endpoint_methods(mention.path, openapi_operations)
        if methods is None:
            issues.append(
                Issue(
                    "ERROR",
                    "unknown_documented_endpoint",
                    "Documented endpoint is absent from the canonical OpenAPI schema.",
                    rel_path,
                    mention.line,
                    {"path": mention.path, "method": mention.method, "match": match_kind},
                )
            )
        elif mention.method and mention.method not in methods:
            issues.append(
                Issue(
                    "ERROR",
                    "wrong_documented_endpoint_method",
                    "Documented HTTP method is absent for this OpenAPI path.",
                    rel_path,
                    mention.line,
                    {
                        "path": mention.path,
                        "method": mention.method,
                        "allowed_methods": sorted(methods),
                    },
                )
            )
    return issues


def _audit_page(
    source: Path,
    path: Path,
    all_pages: set[Path],
    openapi_operations: dict[str, set[str]],
) -> tuple[list[Issue], dict[str, Any], dict[str, list[dict[str, Any]]]]:
    text = _read(path)
    rel_path = _rel(path, source)
    frontmatter, body = _strip_frontmatter(text)
    issues: list[Issue] = []
    fences = _extract_code_fences(path, rel_path, text)
    links = _extract_links(path, rel_path, text)
    h1s = [
        match.group(1)
        for line in _outside_fence_lines(body)
        for match in [re.match(r"^#\s+(.+)$", line)]
        if match
    ]

    if rel_path != "SUMMARY.md":
        if not frontmatter.get("description"):
            issues.append(
                Issue(
                    "ERROR",
                    "missing_description",
                    "Page is missing frontmatter description.",
                    rel_path,
                )
            )
        if len(h1s) != 1:
            issues.append(
                Issue(
                    "ERROR",
                    "invalid_h1_count",
                    f"Expected exactly one H1, found {len(h1s)}.",
                    rel_path,
                )
            )

    issues.extend(_find_secret_issues(path, rel_path, text))
    issues.extend(_find_public_package_issues(path, rel_path, text))
    issues.extend(_find_runtime_encapsulation_issues(rel_path, text))
    issues.extend(_find_pricing_contract_issues(rel_path, text))
    for link in links:
        internal_issue = _validate_internal_link(source, link, all_pages)
        if internal_issue:
            issues.append(internal_issue)
    fence_evidence: list[dict[str, Any]] = []
    for fence in fences:
        fence_issues = _validate_machine_snippet(fence)
        issues.extend(fence_issues)
        if fence_issues:
            validation = "failed"
        elif fence.language in JSON_LANGS | PYTHON_LANGS | TOML_LANGS | YAML_LANGS:
            validation = "parsed"
        elif fence.language in SHELL_LANGS:
            validation = "command_inventory"
        else:
            validation = "static_inventory"
        fence_evidence.append(
            {
                "path": rel_path,
                "line": fence.line,
                "language": fence.language,
                "bytes": len(fence.body.encode("utf-8")),
                "sha256": hashlib.sha256(fence.body.encode("utf-8")).hexdigest(),
                "validation": validation,
            }
        )

    command_counts: dict[str, int] = {
        "safe_static": 0,
        "requires_environment": 0,
        "environment_mutating": 0,
        "external_or_mutating": 0,
        "destructive_mutation": 0,
        "static_only": 0,
    }
    command_evidence: list[dict[str, Any]] = []
    for fence in fences:
        if fence.language in SHELL_LANGS:
            for command in _logical_shell_commands(fence.body, start_line=fence.line + 1):
                classification = _classify_shell_command(command.command)
                command_issue = _validate_shell_command(rel_path, command)
                if command_issue:
                    issues.append(command_issue)
                command_counts[classification] += 1
                command_evidence.append(
                    {
                        "path": rel_path,
                        "line": command.line,
                        "classification": classification,
                        "syntax_valid": command_issue is None,
                        "executed": False,
                        "command": command.command,
                    }
                )

    claim_evidence: list[dict[str, Any]] = []
    product_claims: dict[str, int] = {}
    for term in sorted(PRODUCT_TERMS):
        matches = list(
            re.finditer(
                rf"(?<![A-Za-z0-9_-]){re.escape(term)}(?![A-Za-z0-9_-])",
                text,
                re.IGNORECASE,
            )
        )
        product_claims[term] = len(matches)
        claim_evidence.extend(
            {"path": rel_path, "line": _line_for_offset(text, match.start()), "term": term}
            for match in matches
        )

    endpoint_mentions = _extract_endpoint_mentions(text)
    issues.extend(_validate_endpoint_mentions(rel_path, endpoint_mentions, openapi_operations))
    endpoint_evidence: list[dict[str, Any]] = []
    for mention in endpoint_mentions:
        matched_methods, match_kind = _matching_endpoint_methods(mention.path, openapi_operations)
        endpoint_evidence.append(
            {
                "path": rel_path,
                "line": mention.line,
                "method": mention.method,
                "endpoint": mention.path,
                "scope": mention.scope,
                "authority_match": mention.scope != "algenta"
                or matched_methods is not None
                and (mention.method is None or mention.method in matched_methods),
                "match_kind": "external" if mention.scope != "algenta" else match_kind,
            }
        )

    page_report = {
        "path": rel_path,
        "links": len(links),
        "internal_links": sum(1 for link in links if link.kind == "internal"),
        "external_links": sum(1 for link in links if link.kind == "external"),
        "code_fences": len(fences),
        "shell_commands": len(command_evidence),
        "endpoint_mentions": len(endpoint_mentions),
        "command_counts": command_counts,
        "product_claims": product_claims,
    }
    evidence = {
        "links": [
            {"path": rel_path, "line": link.line, "kind": link.kind, "target": link.target}
            for link in links
        ],
        "code_fences": fence_evidence,
        "shell_commands": command_evidence,
        "product_claim_mentions": claim_evidence,
        "endpoint_mentions": endpoint_evidence,
    }
    return issues, page_report, evidence


def _require_text(corpus: str, checks: list[tuple[str, str]]) -> list[Issue]:
    issues: list[Issue] = []
    lower = corpus.lower()
    for code, needle in checks:
        if needle.lower() not in lower:
            issues.append(
                Issue(
                    severity="ERROR",
                    code=code,
                    message=f"Required docs-readability phrase is missing: {needle}",
                )
            )
    return issues


def _audit_agent_readability(source: Path, pages: list[Path]) -> tuple[list[Issue], dict[str, Any]]:
    corpus = "\n".join(_read(path) for path in pages)
    issues: list[Issue] = []
    checks = [
        ("cursor_mcp_config_missing", "~/.cursor/mcp.json"),
        ("cursor_api_key_missing", "ALGENTA_API_KEY"),
        ("cursor_base_url_missing", "ALGENTA_BASE_URL"),
        ("cursor_expected_tool_missing", "get_contract"),
        ("codex_config_missing", "~/.codex/config.toml"),
        ("codex_mcp_table_missing", "[mcp_servers.algenta]"),
        ("codex_agents_missing", "AGENTS.md"),
        ("codex_transport_missing", "stdio"),
        ("google_llms_missing", "llms.txt"),
        ("google_full_context_missing", "llms-full.txt"),
        ("google_markdown_missing", ".md"),
        ("google_mcp_missing", "/~gitbook/mcp"),
        ("google_named_missing", "Google"),
        ("gemini_named_missing", "Gemini"),
        ("notebooklm_named_missing", "NotebookLM"),
    ]
    issues.extend(_require_text(corpus, checks))

    chatbot_eval = ROOT / "scripts" / "docs" / "chatbot_eval.yaml"
    eval_text = _read(chatbot_eval) if chatbot_eval.is_file() else ""
    missing_eval_ids = sorted(
        eval_id for eval_id in REQUIRED_AGENT_EVAL_IDS if f"id: {eval_id}" not in eval_text
    )
    for eval_id in missing_eval_ids:
        issues.append(
            Issue(
                severity="ERROR",
                code="missing_agent_prompt_eval",
                message=f"Chatbot eval set is missing required agent/search prompt: {eval_id}",
                path="scripts/docs/chatbot_eval.yaml",
            )
        )

    return issues, {
        "cursor_ready": not any(issue.code.startswith("cursor_") for issue in issues),
        "codex_ready": not any(issue.code.startswith("codex_") for issue in issues),
        "google_ai_ready": not any(
            issue.code.startswith("google_") or issue.code.startswith("gemini_") for issue in issues
        ),
        "required_prompt_evals": sorted(REQUIRED_AGENT_EVAL_IDS),
        "missing_prompt_evals": missing_eval_ids,
    }


def _source_registry_tool_count() -> int | None:
    registry_path = ROOT / "apps" / "mcp_server" / "registry.py"
    if not registry_path.is_file():
        return None
    try:
        module = ast.parse(_read(registry_path))
    except SyntaxError:
        return None
    for node in module.body:
        target: ast.AST | None = None
        value: ast.AST | None = None
        if isinstance(node, ast.AnnAssign):
            target = node.target
            value = node.value
        elif isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            value = node.value
        if isinstance(target, ast.Name) and target.id == "TOOLS" and isinstance(value, ast.Dict):
            return sum(
                1
                for key in value.keys
                if isinstance(key, ast.Constant) and isinstance(key.value, str)
            )
    return None


def _audit_source_claims(source: Path, pages: list[Path]) -> tuple[list[Issue], dict[str, Any]]:
    issues: list[Issue] = []
    mcp_tool_count = _source_registry_tool_count()
    hardcoded_mcp_tool_count_claims = 0
    if mcp_tool_count is None:
        issues.append(
            Issue(
                "ERROR",
                "mcp_registry_count_unavailable",
                "Could not derive the current MCP tool count from apps/mcp_server/registry.py.",
                "apps/mcp_server/registry.py",
            )
        )
        return issues, {
            "mcp_registry_tool_count": None,
            "hardcoded_mcp_tool_count_claims": hardcoded_mcp_tool_count_claims,
        }

    for page in pages:
        rel_path = _rel(page, source)
        text = _read(page)
        for match in re.finditer(r"\b(\d+)\s+tools?\b", text, re.IGNORECASE):
            window = text[max(0, match.start() - 120) : match.end() + 120]
            if not re.search(r"\b(algenta|mcp|catalog|registry|server)\b", window, re.IGNORECASE):
                continue
            hardcoded_mcp_tool_count_claims += 1
            claimed = int(match.group(1))
            if claimed != mcp_tool_count:
                issues.append(
                    Issue(
                        "ERROR",
                        "stale_mcp_tool_count_claim",
                        "Hardcoded MCP tool-count claim does not match the source registry.",
                        rel_path,
                        _line_for_offset(text, match.start()),
                        {"claimed": claimed, "actual": mcp_tool_count},
                    )
                )

    return issues, {
        "mcp_registry_tool_count": mcp_tool_count,
        "hardcoded_mcp_tool_count_claims": hardcoded_mcp_tool_count_claims,
    }


def _fetch(
    url: str, *, max_bytes: int = 2_000_000, timeout: float = 30.0
) -> tuple[int, bytes, str]:
    req = urllib.request.Request(  # noqa: S310 - live audit accepts http(s) URLs only.
        url,
        headers={"User-Agent": "algenta-docs-audit/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - caller controls URL.
            data = resp.read(max_bytes + 1)
            return int(resp.status), data, resp.headers.get("content-type", "")
    except urllib.error.HTTPError as exc:
        return int(exc.code), exc.read(max_bytes + 1), exc.headers.get("content-type", "")


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001, ARG002
        return None


def _fetch_redirect_target(url: str, *, timeout: float = 20.0) -> tuple[int, str]:
    request = urllib.request.Request(  # noqa: S310 - caller controls audited live URL.
        url,
        headers={"User-Agent": "algenta-docs-audit/1.0"},
    )
    opener = urllib.request.build_opener(_NoRedirectHandler)
    try:
        with opener.open(request, timeout=timeout) as response:  # noqa: S310
            return int(response.status), response.headers.get("location", "")
    except urllib.error.HTTPError as exc:
        return int(exc.code), exc.headers.get("location", "")


def _fetch_json(url: str, *, timeout: float = 20.0) -> tuple[int, dict[str, Any] | None]:
    status, body, _ = _fetch(url, max_bytes=1_000_000, timeout=timeout)
    if status != 200:
        return status, None
    try:
        payload = json.loads(body.decode("utf-8", "replace"))
    except json.JSONDecodeError:
        return status, None
    if not isinstance(payload, dict):
        return status, None
    return status, payload


def _parse_jsonrpc_body(body: bytes, content_type: str) -> dict[str, Any] | None:
    text = body.decode("utf-8", "replace")
    candidates: list[str] = []
    if "text/event-stream" in content_type.lower():
        event_data: list[str] = []
        for line in text.splitlines():
            if line.startswith("data:"):
                event_data.append(line.removeprefix("data:").lstrip())
            elif not line.strip() and event_data:
                candidates.append("\n".join(event_data))
                event_data = []
        if event_data:
            candidates.append("\n".join(event_data))
    else:
        candidates.append(text)

    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    return None


def _post_jsonrpc(
    url: str,
    payload: dict[str, Any],
    *,
    max_bytes: int = 2_000_000,
    timeout: float = 30.0,
) -> tuple[int, dict[str, Any] | None, dict[str, str]]:
    request = urllib.request.Request(  # noqa: S310 - live audit accepts http(s) URLs only.
        url,
        data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
        headers={
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "User-Agent": "algenta-docs-audit/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            body = response.read(max_bytes + 1)
            headers = {key.lower(): value for key, value in response.headers.items()}
            return (
                int(response.status),
                _parse_jsonrpc_body(body, headers.get("content-type", "")),
                headers,
            )
    except urllib.error.HTTPError as exc:
        body = exc.read(max_bytes + 1)
        headers = {key.lower(): value for key, value in exc.headers.items()}
        return int(exc.code), _parse_jsonrpc_body(body, headers.get("content-type", "")), headers


def _jsonrpc_result(payload: dict[str, Any] | None, request_id: int) -> dict[str, Any] | None:
    if (
        not isinstance(payload, dict)
        or payload.get("jsonrpc") != "2.0"
        or payload.get("id") != request_id
        or "error" in payload
        or not isinstance(payload.get("result"), dict)
    ):
        return None
    return payload["result"]


def _mcp_text_content(result: dict[str, Any] | None) -> str:
    content = result.get("content") if isinstance(result, dict) else None
    if not isinstance(content, list):
        return ""
    return "\n".join(
        item["text"]
        for item in content
        if isinstance(item, dict)
        and item.get("type") == "text"
        and isinstance(item.get("text"), str)
    )


def _validate_docs_mcp_tool_url_aliases(
    base: str, tools: Any
) -> tuple[list[Issue], list[dict[str, Any]]]:
    issues: list[Issue] = []
    aliases: list[dict[str, Any]] = []
    expected_origin = urllib.parse.urlsplit(base)
    tool_rows = tools if isinstance(tools, list) else []

    for tool in tool_rows:
        if not isinstance(tool, dict) or not isinstance(tool.get("name"), str):
            continue
        description = tool.get("description", "")
        if not isinstance(description, str):
            continue
        for match in re.finditer(r"https?://[^\s)`]+", description):
            example = match.group(0).rstrip(".,;:!?")
            parsed = urllib.parse.urlsplit(example)
            normalized_path = re.sub(r"/{2,}", "/", parsed.path)
            if normalized_path == parsed.path:
                continue

            canonical = urllib.parse.urlunsplit(parsed._replace(path=normalized_path))
            same_origin = (
                parsed.scheme.lower() == expected_origin.scheme.lower()
                and parsed.netloc.lower() == expected_origin.netloc.lower()
            )
            redirect_status, location = _fetch_redirect_target(example)
            redirect_target = urllib.parse.urljoin(example, location) if location else ""
            canonical_status, _, _ = _fetch(canonical)
            equivalent = (
                same_origin
                and redirect_status in {301, 302, 307, 308}
                and redirect_target == canonical
                and canonical_status == 200
            )
            aliases.append(
                {
                    "tool": tool["name"],
                    "example": example,
                    "canonical": canonical,
                    "redirect_status": redirect_status,
                    "redirect_target": redirect_target,
                    "canonical_status": canonical_status,
                    "equivalent": equivalent,
                }
            )
            if not equivalent:
                issues.append(
                    Issue(
                        "ERROR",
                        "docs_mcp_noncanonical_tool_url",
                        "GitBook docs MCP tool metadata contains an unsafe URL alias.",
                        details={
                            "tool": tool["name"],
                            "example": example,
                            "canonical": canonical,
                            "redirect_status": redirect_status,
                            "redirect_target": redirect_target,
                            "canonical_status": canonical_status,
                        },
                    )
                )
    return issues, aliases


def _validate_docs_mcp_tools(tools: Any) -> tuple[list[Issue], list[str]]:
    issues: list[Issue] = []
    tool_rows = tools if isinstance(tools, list) else []
    by_name = {
        tool["name"]: tool
        for tool in tool_rows
        if isinstance(tool, dict) and isinstance(tool.get("name"), str)
    }
    expected = {"searchDocumentation": "query", "getPage": "url"}
    for name, required_input in expected.items():
        tool = by_name.get(name)
        schema = tool.get("inputSchema") if isinstance(tool, dict) else None
        annotations = tool.get("annotations") if isinstance(tool, dict) else None
        valid = (
            isinstance(schema, dict)
            and schema.get("type") == "object"
            and required_input in schema.get("required", [])
            and isinstance(schema.get("properties", {}).get(required_input), dict)
            and schema["properties"][required_input].get("type") == "string"
            and schema.get("additionalProperties") is False
            and isinstance(annotations, dict)
            and annotations.get("readOnlyHint") is True
            and annotations.get("destructiveHint") is False
        )
        if not valid:
            issues.append(
                Issue(
                    "ERROR",
                    "docs_mcp_tool_contract_invalid",
                    "GitBook docs MCP tool contract is missing or unsafe.",
                    details={"tool": name, "required_input": required_input},
                )
            )
    return issues, sorted(by_name)


def _audit_live_docs_mcp(base: str) -> tuple[list[Issue], dict[str, Any]]:
    endpoint = f"{base}/~gitbook/mcp"
    issues: list[Issue] = []
    report: dict[str, Any] = {
        "initialize_status": None,
        "protocol_version": None,
        "tools_status": None,
        "tools": [],
        "tool_url_aliases": [],
        "search_status": None,
        "page_status": None,
    }
    initialize = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "algenta-docs-audit", "version": "1.0.0"},
        },
    }
    status, payload, _ = _post_jsonrpc(endpoint, initialize)
    result = _jsonrpc_result(payload, 1)
    report["initialize_status"] = status
    report["protocol_version"] = result.get("protocolVersion") if result else None
    if (
        status != 200
        or result is None
        or not isinstance(result.get("capabilities", {}).get("tools"), dict)
    ):
        issues.append(
            Issue(
                "ERROR",
                "docs_mcp_initialize_failed",
                "GitBook docs MCP initialize exchange failed.",
                details={"status": status},
            )
        )

    status, payload, _ = _post_jsonrpc(
        endpoint, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
    )
    tools_result = _jsonrpc_result(payload, 2)
    report["tools_status"] = status
    tools = tools_result.get("tools") if tools_result else None
    tool_issues, tool_names = _validate_docs_mcp_tools(tools)
    tool_url_issues, tool_url_aliases = _validate_docs_mcp_tool_url_aliases(base, tools)
    report["tools"] = tool_names
    report["tool_url_aliases"] = tool_url_aliases
    if status != 200 or tools_result is None:
        issues.append(
            Issue(
                "ERROR",
                "docs_mcp_tools_list_failed",
                "GitBook docs MCP tools/list exchange failed.",
                details={"status": status},
            )
        )
    issues.extend(tool_issues)
    issues.extend(tool_url_issues)

    search_request = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "searchDocumentation",
            "arguments": {"query": "How do I install the Algenta MCP server for Codex?"},
        },
    }
    status, payload, _ = _post_jsonrpc(endpoint, search_request)
    search_text = _mcp_text_content(_jsonrpc_result(payload, 3))
    report["search_status"] = status
    if status != 200 or not all(
        term in search_text for term in ("Algenta", "algenta-mcp", "Codex")
    ):
        issues.append(
            Issue(
                "ERROR",
                "docs_mcp_search_failed",
                "GitBook docs MCP search did not retrieve canonical Algenta Codex setup content.",
                details={"status": status},
            )
        )

    page_request = {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {"name": "getPage", "arguments": {"url": f"{base}/sdks/mcp"}},
    }
    status, payload, _ = _post_jsonrpc(endpoint, page_request)
    page_text = _mcp_text_content(_jsonrpc_result(payload, 4))
    report["page_status"] = status
    if status != 200 or not all(
        term in page_text for term in ("# MCP server", "algenta-mcp", "Cursor")
    ):
        issues.append(
            Issue(
                "ERROR",
                "docs_mcp_page_fetch_failed",
                "GitBook docs MCP getPage did not return the canonical MCP setup page.",
                details={"status": status},
            )
        )

    for label, text in (("searchDocumentation", search_text), ("getPage", page_text)):
        issues.extend(_find_secret_issues(Path(label), f"live:mcp:{label}", text))
        issues.extend(_find_public_package_issues(Path(label), f"live:mcp:{label}", text))
        issues.extend(_find_runtime_encapsulation_issues(f"live:mcp:{label}", text))
    return issues, report


def _audit_package_registries(corpus: str) -> tuple[list[Issue], dict[str, Any]]:
    issues: list[Issue] = []
    report: dict[str, Any] = {
        "skipped": False,
        "pypi": {},
        "npm": {},
        "public_runtime_install_claims": 0,
        "public_runtime_native_install_claims": 0,
    }

    for package in (*REQUIRED_PYPI_PACKAGES, *OPTIONAL_RUNTIME_PYPI_PACKAGES):
        status, payload = _fetch_json(f"https://pypi.org/pypi/{package}/json")
        info = payload.get("info", {}) if payload else {}
        report["pypi"][package] = {
            "status": status,
            "version": info.get("version", "") if isinstance(info, dict) else "",
            "summary": info.get("summary", "") if isinstance(info, dict) else "",
        }
        if package in REQUIRED_PYPI_PACKAGES and status != 200:
            issues.append(
                Issue(
                    "ERROR",
                    "pypi_package_unavailable",
                    "Docs reference a required public PyPI package that is unavailable.",
                    details={"package": package, "status": status},
                )
            )

    for package in REQUIRED_NPM_PACKAGES:
        status, payload = _fetch_json(f"https://registry.npmjs.org/{package}/latest")
        report["npm"][package] = {
            "status": status,
            "version": payload.get("version", "") if payload else "",
            "description": payload.get("description", "") if payload else "",
            "license": payload.get("license", "") if payload else "",
        }
        if status != 200:
            issues.append(
                Issue(
                    "ERROR",
                    "npm_package_unavailable",
                    "Docs reference a required public npm package that is unavailable.",
                    details={"package": package, "status": status},
                )
            )

    runtime_installs = list(PUBLIC_ALGENTA_RUNTIME_INSTALL_RE.finditer(corpus))
    native_installs = list(PUBLIC_RUNTIME_NATIVE_INSTALL_RE.finditer(corpus))
    report["public_runtime_install_claims"] = len(runtime_installs)
    report["public_runtime_native_install_claims"] = len(native_installs)
    if runtime_installs and report["pypi"].get("algenta", {}).get("status") != 200:
        issues.append(
            Issue(
                "ERROR",
                "runtime_package_install_not_live",
                (
                    "Docs contain a public `pip install algenta` command, "
                    "but PyPI does not serve algenta."
                ),
                details={
                    "package": "algenta",
                    "status": report["pypi"].get("algenta", {}).get("status"),
                },
            )
        )
    if native_installs and report["pypi"].get("algenta-runtime-native", {}).get("status") != 200:
        issues.append(
            Issue(
                "ERROR",
                "runtime_native_install_not_live",
                (
                    "Docs contain a public `pip install algenta-runtime-native` command, "
                    "but PyPI does not serve it."
                ),
                details={
                    "package": "algenta-runtime-native",
                    "status": report["pypi"].get("algenta-runtime-native", {}).get("status"),
                },
            )
        )
    lower_corpus = corpus.lower()
    if report["pypi"].get("algenta", {}).get("status") == 200 and any(
        phrase in lower_corpus for phrase in RUNTIME_NOT_LIVE_PHRASES
    ):
        issues.append(
            Issue(
                "ERROR",
                "stale_runtime_registry_caveat",
                "Docs still say the algenta runtime package is not public, but PyPI serves it.",
                details={"package": "algenta", "status": 200},
            )
        )

    return issues, report


def _sitemap_url_to_markdown_route(base_url: str, page_url: str) -> str | None:
    base = urllib.parse.urlparse(base_url.rstrip("/"))
    parsed = urllib.parse.urlparse(page_url)
    if parsed.scheme != base.scheme or parsed.netloc != base.netloc:
        return None
    path = parsed.path or "/"
    if path == "/":
        return "/.md"
    return f"{path.rstrip('/')}.md"


_LLMS_FULL_NEXT_PAGE_RE = re.compile(r"\[Next Page\]\(([^)\s]+)\)")
_LLMS_FULL_PAGE_PATH_RE = re.compile(r"^/llms-full\.txt/\d+$")
_LLMS_FULL_MAX_PAGES = 32
_LLMS_FULL_MAX_PAGE_BYTES = 3_000_000


def _fetch_llms_full_pages(
    base: str,
) -> tuple[list[Issue], list[tuple[str, str]], dict[str, Any]]:
    """Fetch GitBook's bounded llms-full.txt pagination chain."""
    issues: list[Issue] = []
    pages: list[tuple[str, str]] = []
    routes: list[str] = []
    visited: set[str] = set()
    route = "/llms-full.txt"
    root_status: int | None = None
    total_bytes = 0
    complete = False

    for _ in range(_LLMS_FULL_MAX_PAGES):
        if route in visited:
            issues.append(
                Issue(
                    "ERROR",
                    "llms_full_pagination_cycle",
                    "llms-full.txt pagination contains a cycle.",
                    details={"route": route},
                )
            )
            break
        visited.add(route)

        status, body, content_type = _fetch(f"{base}{route}", max_bytes=_LLMS_FULL_MAX_PAGE_BYTES)
        if root_status is None:
            root_status = status
        routes.append(route)
        total_bytes += len(body)
        if len(body) > _LLMS_FULL_MAX_PAGE_BYTES:
            issues.append(
                Issue(
                    "ERROR",
                    "llms_full_page_too_large",
                    "A page in the llms-full.txt pagination chain exceeds the byte limit.",
                    details={"route": route, "max_bytes": _LLMS_FULL_MAX_PAGE_BYTES},
                )
            )
            break
        text = body.decode("utf-8", "replace")
        if (
            status != 200
            or "<!doctype html" in text[:500].lower()
            or (content_type and "text" not in content_type.lower())
        ):
            issues.append(
                Issue(
                    "ERROR",
                    "llms_full_page_unavailable",
                    "A page in the llms-full.txt pagination chain is unavailable or malformed.",
                    details={
                        "route": route,
                        "status": status,
                        "content_type": content_type,
                    },
                )
            )
            break
        pages.append((route, text))

        next_links = set(_LLMS_FULL_NEXT_PAGE_RE.findall(text))
        if not next_links:
            complete = True
            break
        if len(next_links) != 1:
            issues.append(
                Issue(
                    "ERROR",
                    "llms_full_pagination_ambiguous",
                    "llms-full.txt contains multiple distinct next-page links.",
                    details={"route": route, "next_links": sorted(next_links)},
                )
            )
            break

        next_url = urllib.parse.urljoin(f"{base}{route}", next_links.pop())
        parsed_base = urllib.parse.urlparse(base)
        parsed_next = urllib.parse.urlparse(next_url)
        if (
            parsed_next.scheme != parsed_base.scheme
            or parsed_next.netloc != parsed_base.netloc
            or not _LLMS_FULL_PAGE_PATH_RE.fullmatch(parsed_next.path)
            or parsed_next.query
            or parsed_next.fragment
        ):
            issues.append(
                Issue(
                    "ERROR",
                    "llms_full_pagination_invalid",
                    "llms-full.txt contains an invalid next-page URL.",
                    details={"route": route},
                )
            )
            break
        route = parsed_next.path
    else:
        issues.append(
            Issue(
                "ERROR",
                "llms_full_pagination_limit",
                "llms-full.txt exceeded the bounded pagination limit.",
                details={"max_pages": _LLMS_FULL_MAX_PAGES},
            )
        )

    report = {
        "root_status": root_status,
        "pages": len(pages),
        "bytes": total_bytes,
        "routes": routes,
        "complete": complete,
    }
    return issues, pages, report


def _audit_live(
    live_url: str, public_page_count: int, source: Path
) -> tuple[list[Issue], dict[str, Any]]:
    base = live_url.rstrip("/")
    issues: list[Issue] = []
    sitemap_urls: list[str] = []
    result: dict[str, Any] = {
        "base_url": base,
        "sitemap_urls": 0,
        "robots_status": None,
        "llms_txt_status": None,
        "llms_full_status": None,
        "llms_full_pages": 0,
        "llms_full_bytes": 0,
        "llms_full_complete": False,
        "markdown_pages_checked": 0,
        "source_navigation_urls": 0,
        "sitemap_matches_source_navigation": False,
        "docs_mcp": {},
    }

    sitemap_status, sitemap_body, _ = _fetch(f"{base}/sitemap-pages.xml")
    if sitemap_status != 200:
        issues.append(
            Issue(
                "ERROR",
                "live_sitemap_unavailable",
                "Live sitemap-pages.xml is unavailable.",
                details={"status": sitemap_status},
            )
        )
    else:
        try:
            root = ET.fromstring(sitemap_body)  # noqa: S314 - bounded public sitemap fetch.
            urls = [
                elem.text or ""
                for elem in root.findall(".//{http://www.sitemaps.org/schemas/sitemap/0.9}loc")
            ]
            sitemap_urls = [url for url in urls if url]
            result["sitemap_urls"] = len(urls)
            expected_navigation_urls = _summary_expected_sitemap_urls(source, base)
            result["source_navigation_urls"] = len(expected_navigation_urls)
            result["sitemap_matches_source_navigation"] = sitemap_urls == expected_navigation_urls
            if len(urls) < public_page_count:
                issues.append(
                    Issue(
                        "ERROR",
                        "live_sitemap_missing_pages",
                        "Live sitemap has fewer URLs than public source pages.",
                        details={
                            "sitemap_urls": len(urls),
                            "public_source_pages": public_page_count,
                        },
                    )
                )
            if expected_navigation_urls:
                missing = sorted(set(expected_navigation_urls) - set(sitemap_urls))
                extra = sorted(set(sitemap_urls) - set(expected_navigation_urls))
                if missing or extra:
                    issues.append(
                        Issue(
                            "ERROR",
                            "live_sitemap_source_navigation_mismatch",
                            "Live sitemap URLs do not match GitBook SUMMARY.md navigation.",
                            details={"missing": missing[:20], "extra": extra[:20]},
                        )
                    )
                elif sitemap_urls != expected_navigation_urls:
                    first_mismatch = next(
                        (
                            {"expected": expected, "actual": actual, "index": index}
                            for index, (expected, actual) in enumerate(
                                zip(expected_navigation_urls, sitemap_urls, strict=True), start=1
                            )
                            if expected != actual
                        ),
                        None,
                    )
                    issues.append(
                        Issue(
                            "ERROR",
                            "live_sitemap_source_navigation_order_mismatch",
                            "Live sitemap URL order does not match GitBook SUMMARY.md navigation.",
                            details=first_mismatch or {},
                        )
                    )
        except ET.ParseError as exc:
            issues.append(
                Issue("ERROR", "live_sitemap_invalid_xml", f"Live sitemap XML is invalid: {exc}")
            )

    robots_status, robots_body, _ = _fetch(f"{base}/robots.txt", max_bytes=100_000)
    result["robots_status"] = robots_status
    robots_text = robots_body.decode("utf-8", "replace")
    if robots_status != 200:
        issues.append(
            Issue(
                "ERROR",
                "robots_unavailable",
                "robots.txt is unavailable.",
                details={"status": robots_status},
            )
        )
    if re.search(r"(?im)^disallow:\s*/\s*$", robots_text):
        issues.append(
            Issue("ERROR", "robots_blocks_site", "robots.txt blocks the entire docs site.")
        )

    llms_status, llms_body, _ = _fetch(f"{base}/llms.txt")
    result["llms_txt_status"] = llms_status
    llms_text = llms_body.decode("utf-8", "replace")
    if (
        llms_status != 200
        or "Algenta" not in llms_text
        or "https://docs.algenta.ai" not in llms_text
    ):
        issues.append(
            Issue(
                "ERROR",
                "llms_txt_invalid",
                "llms.txt is missing or does not identify Algenta docs.",
            )
        )
    issues.extend(_find_secret_issues(Path("llms.txt"), "live:llms.txt", llms_text))
    issues.extend(_find_public_package_issues(Path("llms.txt"), "live:llms.txt", llms_text))
    issues.extend(_find_runtime_encapsulation_issues("live:llms.txt", llms_text))

    llms_full_issues, llms_full_pages, llms_full_report = _fetch_llms_full_pages(base)
    issues.extend(llms_full_issues)
    result["llms_full_status"] = llms_full_report["root_status"]
    result["llms_full_pages"] = llms_full_report["pages"]
    result["llms_full_bytes"] = llms_full_report["bytes"]
    result["llms_full_complete"] = llms_full_report["complete"]
    llms_full_text = "\n".join(text for _route, text in llms_full_pages)
    if (
        llms_full_report["root_status"] != 200
        or not llms_full_report["complete"]
        or "Using these docs with AI" not in llms_full_text
    ):
        issues.append(
            Issue(
                "ERROR", "llms_full_invalid", "llms-full.txt is missing the AI access page content."
            )
        )
    for route, text in llms_full_pages:
        rel_path = f"live:{route.lstrip('/')}"
        issues.extend(_find_secret_issues(Path(route.lstrip("/")), rel_path, text))
        issues.extend(_find_public_package_issues(Path(route.lstrip("/")), rel_path, text))
        issues.extend(_find_runtime_encapsulation_issues(rel_path, text))

    markdown_routes = [
        route
        for route in (_sitemap_url_to_markdown_route(base, url) for url in sitemap_urls)
        if route
    ]

    def fetch_markdown_route(route: str) -> list[Issue]:
        status, body, content_type = _fetch(f"{base}{route}", max_bytes=500_000)
        text = body.decode("utf-8", "replace")
        route_issues: list[Issue] = []
        if (
            status != 200
            or "markdown" not in content_type.lower()
            or "<!doctype html" in text[:500].lower()
        ):
            route_issues.append(
                Issue(
                    "ERROR",
                    "live_markdown_page_invalid",
                    "Live sitemap page Markdown route is unavailable or malformed.",
                    details={"route": route, "status": status, "content_type": content_type},
                )
            )
        route_issues.extend(_find_secret_issues(Path(route.lstrip("/")), f"live:{route}", text))
        route_issues.extend(
            _find_public_package_issues(Path(route.lstrip("/")), f"live:{route}", text)
        )
        route_issues.extend(_find_runtime_encapsulation_issues(f"live:{route}", text))
        route_issues.extend(_find_pricing_contract_issues(f"live:{route}", text))
        return route_issues

    if markdown_routes:
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=min(8, len(markdown_routes))
        ) as executor:
            for route_issues in executor.map(fetch_markdown_route, markdown_routes):
                result["markdown_pages_checked"] += 1
                issues.extend(route_issues)

    mcp_issues, mcp_report = _audit_live_docs_mcp(base)
    issues.extend(mcp_issues)
    result["docs_mcp"] = mcp_report
    return issues, result


def run_audit(
    source: Path,
    live_url: str | None,
    skip_live: bool,
    execute_safe_commands: bool = False,
) -> dict[str, Any]:
    source = source.resolve()
    pages = _markdown_pages(source)
    all_pages = {page.resolve() for page in pages}
    issues: list[Issue] = []
    page_reports: list[dict[str, Any]] = []
    schema_operations = _openapi_operations()
    source_operations = _source_route_operations()
    route_operations = {path: set(methods) for path, methods in schema_operations.items()}
    for route, methods in source_operations.items():
        route_operations.setdefault(route, set()).update(methods)
    evidence: dict[str, list[dict[str, Any]]] = {
        "links": [],
        "code_fences": [],
        "shell_commands": [],
        "product_claim_mentions": [],
        "endpoint_mentions": [],
    }
    totals: dict[str, Any] = {
        "pages": len(pages),
        "public_pages": len([page for page in pages if page.name != "SUMMARY.md"]),
        "links": 0,
        "internal_links": 0,
        "external_links": 0,
        "code_fences": 0,
        "shell_commands": 0,
        "endpoint_mentions": 0,
        "safe_static_commands": 0,
        "requires_environment_commands": 0,
        "environment_mutating_commands": 0,
        "external_or_mutating_commands": 0,
        "destructive_mutation_commands": 0,
        "static_only_commands": 0,
        "product_claims": dict.fromkeys(sorted(PRODUCT_TERMS), 0),
    }

    for page in pages:
        page_issues, page_report, page_evidence = _audit_page(
            source, page, all_pages, route_operations
        )
        issues.extend(page_issues)
        page_reports.append(page_report)
        for evidence_type, rows in page_evidence.items():
            evidence[evidence_type].extend(rows)
        totals["links"] += page_report["links"]
        totals["internal_links"] += page_report["internal_links"]
        totals["external_links"] += page_report["external_links"]
        totals["code_fences"] += page_report["code_fences"]
        totals["shell_commands"] += page_report["shell_commands"]
        totals["endpoint_mentions"] += page_report["endpoint_mentions"]
        for key, value in page_report["command_counts"].items():
            totals[f"{key}_commands"] += value
        for product, value in page_report["product_claims"].items():
            totals["product_claims"][product] += value

    executed_commands = 0
    if execute_safe_commands:
        for row in evidence["shell_commands"]:
            if row["classification"] != "safe_static" or not row["syntax_valid"]:
                continue
            execution_issue, execution = _execute_safe_shell_command(
                row["command"], row["path"], row["line"]
            )
            row.update(execution)
            if execution_issue:
                issues.append(execution_issue)
            elif execution["executed"]:
                executed_commands += 1

    agent_issues, agent_report = _audit_agent_readability(source, pages)
    issues.extend(agent_issues)
    source_claim_issues, source_claim_report = _audit_source_claims(source, pages)
    issues.extend(source_claim_issues)
    openapi_identity_issues, openapi_identity_report = _audit_openapi_public_identity()
    issues.extend(openapi_identity_issues)
    corpus = "\n".join(_read(path) for path in pages)
    live_report: dict[str, Any] = {"skipped": bool(skip_live)}
    package_registry_report: dict[str, Any] = {"skipped": bool(skip_live or not live_url)}
    if live_url and not skip_live:
        live_issues, live_report = _audit_live(live_url, int(totals["public_pages"]), source)
        issues.extend(live_issues)
        package_registry_issues, package_registry_report = _audit_package_registries(corpus)
        issues.extend(package_registry_issues)

    issue_rows = [issue.to_json() for issue in issues]
    failures = sum(1 for issue in issues if issue.severity == "ERROR")
    warnings = sum(1 for issue in issues if issue.severity == "WARNING")
    static_only = (
        int(totals["static_only_commands"])
        + int(totals["requires_environment_commands"])
        + int(totals["environment_mutating_commands"])
        + int(totals["external_or_mutating_commands"])
        + int(totals["destructive_mutation_commands"])
    )
    skips = static_only + (1 if skip_live else 0)
    claim_mentions = sum(int(value) for value in totals["product_claims"].values())
    source_items_inventoried = sum(len(rows) for rows in evidence.values())
    unique_endpoint_operations = {
        (row["method"], row["endpoint"]) for row in evidence["endpoint_mentions"]
    }
    shell_syntax_validated_commands = sum(
        1 for row in evidence["shell_commands"] if row["syntax_valid"]
    )
    runnable_commands = int(totals["safe_static_commands"])
    command_execution_percent = (
        round(executed_commands * 100 / runnable_commands, 4)
        if runnable_commands
        else (100.0 if execute_safe_commands else 0.0)
    )
    totals.update(
        {
            "claim_mentions": claim_mentions,
            "runnable_commands": runnable_commands,
            "static_or_guarded_commands": static_only,
            "guarded_commands": static_only,
            "executed_commands": executed_commands,
            "unexecuted_runnable_commands": runnable_commands - executed_commands,
            "command_classification_percent": 100.0 if totals["shell_commands"] else 100.0,
            "shell_syntax_validated_commands": shell_syntax_validated_commands,
            "shell_syntax_validation_percent": (
                round(shell_syntax_validated_commands * 100 / totals["shell_commands"], 4)
                if totals["shell_commands"]
                else 100.0
            ),
            "command_execution_percent": command_execution_percent,
            "source_items_inventoried": source_items_inventoried,
            "source_inventory_percent": 100.0,
            "unique_endpoint_operations": len(unique_endpoint_operations),
            "failures": failures,
            "warnings": warnings,
            "fixes": 0,
            "skips": skips,
            "blockers": failures,
        }
    )
    return {
        "status": "pass" if failures == 0 else "fail",
        "source": _report_path(source),
        "live_url": live_url or "",
        "totals": totals,
        "snippets": {
            "code_fences": totals["code_fences"],
            "shell_commands": totals["shell_commands"],
            "runnable_safe_commands": totals["safe_static_commands"],
            "static_or_guarded_commands": static_only,
            "executed_safe_commands": totals["executed_commands"],
        },
        "agent_readability": agent_report,
        "source_claims": source_claim_report,
        "openapi_identity": openapi_identity_report,
        "route_authority": {
            "schema_paths": len(schema_operations),
            "schema_operations": sum(len(methods) for methods in schema_operations.values()),
            "source_paths": len(source_operations),
            "source_operations": sum(len(methods) for methods in source_operations.values()),
            "combined_paths": len(route_operations),
            "combined_operations": sum(len(methods) for methods in route_operations.values()),
        },
        "live": live_report,
        "package_registries": package_registry_report,
        "issues": issue_rows,
        "summary": {
            "failures": failures,
            "warnings": warnings,
            "pages_checked": totals["pages"],
            "links_checked": totals["links"],
            "snippets_checked": totals["code_fences"],
            "commands_classified": totals["shell_commands"],
            "commands_executed": totals["executed_commands"],
            "commands_unexecuted": totals["unexecuted_runnable_commands"],
            "blockers": totals["blockers"],
            "claim_mentions": claim_mentions,
            "endpoint_mentions": totals["endpoint_mentions"],
            "source_items_inventoried": source_items_inventoried,
            "source_inventory_percent": totals["source_inventory_percent"],
            "shell_syntax_validation_percent": totals["shell_syntax_validation_percent"],
            "command_execution_percent": totals["command_execution_percent"],
            "fixes": totals["fixes"],
            "skips": totals["skips"],
        },
        "evidence": evidence,
        "pages": page_reports,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=str(DEFAULT_SOURCE), help="GitBook source directory.")
    parser.add_argument(
        "--live", default="", help="Published GitBook base URL, e.g. https://docs.algenta.ai."
    )
    parser.add_argument("--skip-live", action="store_true", help="Disable network checks.")
    parser.add_argument(
        "--execute-safe-commands",
        action="store_true",
        help="Execute only provably safe literal shell commands in isolated temporary directories.",
    )
    parser.add_argument(
        "--strict", action="store_true", help="Exit non-zero when any ERROR is found."
    )
    parser.add_argument(
        "--json-report", default="", help="Write the full JSON report to this path."
    )
    args = parser.parse_args()

    report = run_audit(
        Path(args.source),
        args.live.strip() or None,
        args.skip_live,
        execute_safe_commands=args.execute_safe_commands,
    )
    if args.json_report:
        out_path = Path(args.json_report)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    summary = report["summary"]
    print(
        "GitBook A-Z audit: "
        f"{report['status']} "
        f"pages={summary['pages_checked']} "
        f"links={summary['links_checked']} "
        f"snippets={summary['snippets_checked']} "
        f"commands={summary['commands_classified']} "
        f"executed={summary['commands_executed']} "
        f"claims={summary['claim_mentions']} "
        f"failures={summary['failures']} "
        f"warnings={summary['warnings']} "
        f"skips={summary['skips']} "
        f"blockers={summary['blockers']}"
    )
    for issue in report["issues"][:50]:
        location = f" {issue.get('path', '')}:{issue.get('line', '')}".rstrip(":")
        print(f"  [{issue['severity']}] {issue['code']}{location} - {issue['message']}")
    if len(report["issues"]) > 50:
        print(f"  ... {len(report['issues']) - 50} more issue(s); see JSON report")

    return 1 if args.strict and report["summary"]["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
