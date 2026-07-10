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
import json
import re
import sys
import tomllib
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
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

LIVE_MARKDOWN_SAMPLES = (
    "/overview.md",
    "/getting-started/quickstart.md",
    "/help/ai-access.md",
    "/sdks/mcp-registry.md",
)

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


def _rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _line_for_offset(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _markdown_pages(source: Path) -> list[Path]:
    return sorted(path for path in source.rglob("*.md") if path.is_file())


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


def _logical_shell_commands(body: str) -> list[str]:
    commands: list[str] = []
    current: list[str] = []
    for raw in body.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("$ "):
            line = line[2:].strip()
        current.append(line[:-1].strip() if line.endswith("\\") else line)
        if not line.endswith("\\"):
            command = " ".join(part for part in current if part).strip()
            if command:
                commands.append(command)
            current = []
    if current:
        command = " ".join(part for part in current if part).strip()
        if command:
            commands.append(command)
    return commands


def _classify_shell_command(command: str) -> str:
    lowered = command.lower()
    if any(token in lowered for token in (" rm ", " rm -", " delete ", " revoke ", "destroy")):
        return "destructive_mutation"
    if re.search(r"\bcurl\b", lowered) and re.search(r"\b(-x|--request)\s+(post|put|patch|delete)\b", lowered):
        return "external_or_mutating"
    if any(token in lowered for token in ("docker compose up", "pip install", "pipx install", "npm install", "pnpm install", "npx ")):
        return "environment_mutating"
    if lowered.startswith("export ") or lowered.startswith("echo ") or lowered.startswith("cat "):
        return "safe_static"
    if lowered.startswith(("curl ", "python3 ", "python ", "de ", "algenta ", "codex ", "claude ", "npx ")):
        return "requires_environment"
    return "static_only"


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
                    message="Docs contain a provider-specific secret prefix placeholder; use a neutral environment-variable placeholder instead.",
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


def _audit_page(source: Path, path: Path, all_pages: set[Path]) -> tuple[list[Issue], dict[str, Any]]:
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
            issues.append(Issue("ERROR", "missing_description", "Page is missing frontmatter description.", rel_path))
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
    for link in links:
        internal_issue = _validate_internal_link(source, link, all_pages)
        if internal_issue:
            issues.append(internal_issue)
    for fence in fences:
        issues.extend(_validate_machine_snippet(fence))

    command_counts: dict[str, int] = {
        "safe_static": 0,
        "requires_environment": 0,
        "environment_mutating": 0,
        "external_or_mutating": 0,
        "destructive_mutation": 0,
        "static_only": 0,
    }
    shell_commands = 0
    for fence in fences:
        if fence.language in SHELL_LANGS:
            for command in _logical_shell_commands(fence.body):
                shell_commands += 1
                command_counts[_classify_shell_command(command)] += 1

    product_claims = {
        term: len(re.findall(rf"(?<![A-Za-z0-9_-]){re.escape(term)}(?![A-Za-z0-9_-])", text, re.IGNORECASE))
        for term in sorted(PRODUCT_TERMS)
    }
    return issues, {
        "path": rel_path,
        "links": len(links),
        "internal_links": sum(1 for link in links if link.kind == "internal"),
        "external_links": sum(1 for link in links if link.kind == "external"),
        "code_fences": len(fences),
        "shell_commands": shell_commands,
        "command_counts": command_counts,
        "product_claims": product_claims,
    }


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
    missing_eval_ids = sorted(eval_id for eval_id in REQUIRED_AGENT_EVAL_IDS if f"id: {eval_id}" not in eval_text)
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
        "google_ai_ready": not any(issue.code.startswith("google_") or issue.code.startswith("gemini_") for issue in issues),
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
            return sum(1 for key in value.keys if isinstance(key, ast.Constant) and isinstance(key.value, str))
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
        return issues, {"mcp_registry_tool_count": None, "hardcoded_mcp_tool_count_claims": hardcoded_mcp_tool_count_claims}

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


def _fetch(url: str, *, max_bytes: int = 2_000_000, timeout: float = 30.0) -> tuple[int, bytes, str]:
    req = urllib.request.Request(url, headers={"User-Agent": "algenta-docs-audit/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - caller controls URL.
            data = resp.read(max_bytes + 1)
            return int(resp.status), data, resp.headers.get("content-type", "")
    except urllib.error.HTTPError as exc:
        return int(exc.code), exc.read(max_bytes + 1), exc.headers.get("content-type", "")


def _audit_live(live_url: str, public_page_count: int) -> tuple[list[Issue], dict[str, Any]]:
    base = live_url.rstrip("/")
    issues: list[Issue] = []
    result: dict[str, Any] = {
        "base_url": base,
        "sitemap_urls": 0,
        "robots_status": None,
        "llms_txt_status": None,
        "llms_full_status": None,
        "markdown_samples_checked": 0,
        "docs_mcp_status": None,
    }

    sitemap_status, sitemap_body, _ = _fetch(f"{base}/sitemap-pages.xml")
    if sitemap_status != 200:
        issues.append(Issue("ERROR", "live_sitemap_unavailable", "Live sitemap-pages.xml is unavailable.", details={"status": sitemap_status}))
    else:
        try:
            root = ET.fromstring(sitemap_body)
            urls = [elem.text or "" for elem in root.findall(".//{http://www.sitemaps.org/schemas/sitemap/0.9}loc")]
            result["sitemap_urls"] = len(urls)
            if len(urls) < public_page_count:
                issues.append(
                    Issue(
                        "ERROR",
                        "live_sitemap_missing_pages",
                        "Live sitemap has fewer URLs than public source pages.",
                        details={"sitemap_urls": len(urls), "public_source_pages": public_page_count},
                    )
                )
        except ET.ParseError as exc:
            issues.append(Issue("ERROR", "live_sitemap_invalid_xml", f"Live sitemap XML is invalid: {exc}"))

    robots_status, robots_body, _ = _fetch(f"{base}/robots.txt", max_bytes=100_000)
    result["robots_status"] = robots_status
    robots_text = robots_body.decode("utf-8", "replace")
    if robots_status != 200:
        issues.append(Issue("ERROR", "robots_unavailable", "robots.txt is unavailable.", details={"status": robots_status}))
    if re.search(r"(?im)^disallow:\s*/\s*$", robots_text):
        issues.append(Issue("ERROR", "robots_blocks_site", "robots.txt blocks the entire docs site."))

    llms_status, llms_body, _ = _fetch(f"{base}/llms.txt")
    result["llms_txt_status"] = llms_status
    llms_text = llms_body.decode("utf-8", "replace")
    if llms_status != 200 or "Algenta" not in llms_text or "https://docs.algenta.ai" not in llms_text:
        issues.append(Issue("ERROR", "llms_txt_invalid", "llms.txt is missing or does not identify Algenta docs."))
    issues.extend(_find_secret_issues(Path("llms.txt"), "live:llms.txt", llms_text))

    llms_full_status, llms_full_body, _ = _fetch(f"{base}/llms-full.txt", max_bytes=3_000_000)
    result["llms_full_status"] = llms_full_status
    llms_full_text = llms_full_body.decode("utf-8", "replace")
    if llms_full_status != 200 or "Using these docs with AI" not in llms_full_text:
        issues.append(Issue("ERROR", "llms_full_invalid", "llms-full.txt is missing the AI access page content."))
    issues.extend(_find_secret_issues(Path("llms-full.txt"), "live:llms-full.txt", llms_full_text))

    for route in LIVE_MARKDOWN_SAMPLES:
        status, body, content_type = _fetch(f"{base}{route}", max_bytes=500_000)
        text = body.decode("utf-8", "replace")
        result["markdown_samples_checked"] += 1
        if status != 200 or "# " not in text or "text" not in content_type:
            issues.append(
                Issue(
                    "ERROR",
                    "live_markdown_sample_invalid",
                    "Representative live Markdown page is unavailable or malformed.",
                    details={"route": route, "status": status, "content_type": content_type},
                )
            )
        issues.extend(_find_secret_issues(Path(route.lstrip("/")), f"live:{route}", text))

    mcp_status, mcp_body, _ = _fetch(f"{base}/~gitbook/mcp", max_bytes=100_000)
    result["docs_mcp_status"] = mcp_status
    if mcp_status not in {200, 405} or b"jsonrpc" not in mcp_body[:2000]:
        issues.append(
            Issue(
                "ERROR",
                "docs_mcp_unavailable",
                "GitBook docs MCP endpoint did not respond like an MCP endpoint.",
                details={"status": mcp_status},
            )
        )
    return issues, result


def run_audit(source: Path, live_url: str | None, skip_live: bool) -> dict[str, Any]:
    source = source.resolve()
    pages = _markdown_pages(source)
    all_pages = {page.resolve() for page in pages}
    issues: list[Issue] = []
    page_reports: list[dict[str, Any]] = []
    totals: dict[str, Any] = {
        "pages": len(pages),
        "public_pages": len([page for page in pages if page.name != "SUMMARY.md"]),
        "links": 0,
        "internal_links": 0,
        "external_links": 0,
        "code_fences": 0,
        "shell_commands": 0,
        "safe_static_commands": 0,
        "requires_environment_commands": 0,
        "environment_mutating_commands": 0,
        "external_or_mutating_commands": 0,
        "destructive_mutation_commands": 0,
        "static_only_commands": 0,
        "product_claims": {term: 0 for term in sorted(PRODUCT_TERMS)},
    }

    for page in pages:
        page_issues, page_report = _audit_page(source, page, all_pages)
        issues.extend(page_issues)
        page_reports.append(page_report)
        totals["links"] += page_report["links"]
        totals["internal_links"] += page_report["internal_links"]
        totals["external_links"] += page_report["external_links"]
        totals["code_fences"] += page_report["code_fences"]
        totals["shell_commands"] += page_report["shell_commands"]
        for key, value in page_report["command_counts"].items():
            totals[f"{key}_commands"] += value
        for product, value in page_report["product_claims"].items():
            totals["product_claims"][product] += value

    agent_issues, agent_report = _audit_agent_readability(source, pages)
    issues.extend(agent_issues)
    source_claim_issues, source_claim_report = _audit_source_claims(source, pages)
    issues.extend(source_claim_issues)
    live_report: dict[str, Any] = {"skipped": bool(skip_live)}
    if live_url and not skip_live:
        live_issues, live_report = _audit_live(live_url, int(totals["public_pages"]))
        issues.extend(live_issues)

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
    return {
        "status": "pass" if failures == 0 else "fail",
        "source": str(source),
        "live_url": live_url or "",
        "totals": totals,
        "snippets": {
            "code_fences": totals["code_fences"],
            "shell_commands": totals["shell_commands"],
            "runnable_safe_commands": totals["safe_static_commands"],
            "static_or_guarded_commands": static_only,
        },
        "agent_readability": agent_report,
        "source_claims": source_claim_report,
        "live": live_report,
        "issues": issue_rows,
        "summary": {
            "failures": failures,
            "warnings": warnings,
            "pages_checked": totals["pages"],
            "links_checked": totals["links"],
            "snippets_checked": totals["code_fences"],
            "commands_classified": totals["shell_commands"],
            "blockers": failures,
            "fixes": 0,
            "skips": static_only + (1 if skip_live else 0),
        },
        "pages": page_reports,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=str(DEFAULT_SOURCE), help="GitBook source directory.")
    parser.add_argument("--live", default="", help="Published GitBook base URL, e.g. https://docs.algenta.ai.")
    parser.add_argument("--skip-live", action="store_true", help="Disable network checks.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when any ERROR is found.")
    parser.add_argument("--json-report", default="", help="Write the full JSON report to this path.")
    args = parser.parse_args()

    report = run_audit(Path(args.source), args.live.strip() or None, args.skip_live)
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
        f"failures={summary['failures']} "
        f"skips={summary['skips']}"
    )
    for issue in report["issues"][:50]:
        location = f" {issue.get('path', '')}:{issue.get('line', '')}".rstrip(":")
        print(f"  [{issue['severity']}] {issue['code']}{location} - {issue['message']}")
    if len(report["issues"]) > 50:
        print(f"  ... {len(report['issues']) - 50} more issue(s); see JSON report")

    return 1 if args.strict and report["summary"]["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
