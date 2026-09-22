"""Copy lint for a Space directory: canon, Apple copy rules, no hedging words.

User-visible strings are collected from

* ``README.md`` — the Hub card: frontmatter values (``emoji:`` may hold an emoji, nothing
  else may) and the Markdown body, with fenced code blocks and inline code spans blanked
  first (code is not copy: a ```` `!important` ```` in a table cell is not an exclamation);
* Python modules — module-level string constants, the literal passed to ``gr.Markdown`` /
  ``gr.HTML`` (positional or ``value=``), every ``label=`` literal, and the ``title`` /
  ``tagline`` passed to ``render_header``;
* ``*.html`` pages — every text node (``html.parser``; ``<style>`` and ``<script>`` bodies
  excluded), the ``<h1>`` as the headline and ``p.alg-subline`` as the subline.

Rules (each finding carries a code): ``banned`` phrases (case-insensitive), ``jargon`` in
primary strings, ``emoji`` outside README frontmatter, ``exclaim`` (no exclamation marks),
``headline`` (<= 6 words) and ``subline`` (<= 14 words), ``link-missing`` when the footer
lacks the pricing or Discord link. The footer lives in the shell module for a live Space
and in ``index.html`` for a redirect stub under ``_redirects/`` (no shell there); retired
sources under ``_retired/`` skip the link rule. Exit status is non-zero when anything is
found; output is ``file:line: [code] msg``.

Findings are reported, never fixed: the copy itself is owned by the app milestones.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path

PRICING_URL = "https://algenta.ai/pricing"
DISCORD_URL = "https://discord.gg/w8NDsph9an"
REQUIRED_LINKS = (PRICING_URL, DISCORD_URL)
HEADLINE_MAX_WORDS = 6
SUBLINE_MAX_WORDS = 14

BANNED: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(pat, re.IGNORECASE), label)
    for pat, label in (
        (r"decision[ -]engine", "decision engine"),
        (r"@algenta\.ai", "email address"),
        (r"\bsimulated\b", "simulated"),
        (r"\bmocks?\b", "mock"),
        (r"coming soon", "coming soon"),
        (r"\btodo\b", "todo"),
        (r"\bplaceholders?\b", "placeholder"),
        (r"\blorem\b", "lorem"),
        (r"\bbeta\b", "beta"),
        (r"\bpreview\b", "preview"),
    )
)
JARGON: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(pat, re.IGNORECASE), label)
    for pat, label in (
        (r"\bcgroups?\b", "cgroup"),
        (r"\bR[479]\b", "rule ids R4/R7/R9"),
        (r"\bwire shapes?\b", "wire shapes"),
        (r"\bharness v\d", "harness version"),
        (r"\bclean-room\b", "clean-room"),
        (r"\bpost-open-source\b", "post-open-source"),
        (r"\bdefensibility\b", "defensibility"),
        (r"\bbit-faithful\b", "bit-faithful"),
    )
)
EMOJI_RE = re.compile(
    "["
    + chr(0x1F000)
    + "-"
    + chr(0x1FAFF)  # pictographs, emoticons, symbols
    + chr(0x2600)
    + "-"
    + chr(0x27BF)  # misc symbols and dingbats
    + chr(0x2B00)
    + "-"
    + chr(0x2BFF)  # misc symbols and arrows
    + "]"
)
TYPOGRAPHIC_MARKS = frozenset("✓✔✗✘")  # check and ballot marks are not emoji
EXCLAIM_RE = re.compile(r"(?<![<!])!(?![=\-\[!])")
_WORD_PUNCT = frozenset({"—", "–", "-", "·", "•", "|", "/", ":", "&"})
_SKIP_DIRS = frozenset({"tests", "scripts", "vendor", "__pycache__"})
_FENCE_RE = re.compile(r"^(`{3,}|~{3,})[^\n]*\n.*?^\1[ \t]*$", re.MULTILINE | re.DOTALL)
_CODE_SPAN_RE = re.compile(r"(`+)[^`\n](?:[^`\n]|`(?!\1))*?\1")
_HTML_SILENT_TAGS = frozenset({"style", "script"})
_HTML_VOID_TAGS = frozenset(
    {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source"}
)


@dataclass(frozen=True)
class Finding:
    file: Path
    line: int
    code: str
    message: str

    def format(self, root: Path | None = None) -> str:
        shown = self.file
        if root is not None:
            try:
                shown = self.file.relative_to(root)
            except ValueError:
                shown = self.file
        return f"{shown}:{self.line}: [{self.code}] {self.message}"


def word_count(text: str) -> int:
    return sum(1 for tok in text.split() if tok not in _WORD_PUNCT)


def emoji_in(text: str) -> list[str]:
    return [ch for ch in EMOJI_RE.findall(text) if ch not in TYPOGRAPHIC_MARKS]


def _line_of(text: str, index: int, first_line: int) -> int:
    return first_line + text.count("\n", 0, index)


def scan_text(
    text: str, file: Path, first_line: int, *, primary: bool, allow_emoji: bool = False
) -> list[Finding]:
    """All findings for one user-visible string that starts on ``first_line``."""
    out: list[Finding] = []
    for pattern, label in BANNED:
        for m in pattern.finditer(text):
            out.append(Finding(file, _line_of(text, m.start(), first_line), "banned", label))
    if primary:
        for pattern, label in JARGON:
            for m in pattern.finditer(text):
                out.append(Finding(file, _line_of(text, m.start(), first_line), "jargon", label))
    if not allow_emoji:
        for m in EMOJI_RE.finditer(text):
            if m.group(0) not in TYPOGRAPHIC_MARKS:
                line = _line_of(text, m.start(), first_line)
                out.append(Finding(file, line, "emoji", f"emoji {m.group(0)!r} in app copy"))
    for m in EXCLAIM_RE.finditer(text):
        out.append(
            Finding(file, _line_of(text, m.start(), first_line), "exclaim", "exclamation mark")
        )
    return out


def split_frontmatter(text: str) -> tuple[list[tuple[int, str]], int]:
    """(frontmatter lines as (lineno, text), first body line number). No frontmatter -> ([], 1)."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return [], 1
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return [(n + 1, lines[n]) for n in range(1, i)], i + 2
    return [], 1


def _blank(match: re.Match[str]) -> str:
    return re.sub(r"[^\n]", " ", match.group(0))


def blank_code(markdown: str) -> str:
    """Markdown with fenced blocks and inline code spans replaced by spaces, lines kept."""
    return _CODE_SPAN_RE.sub(_blank, _FENCE_RE.sub(_blank, markdown))


def lint_readme(path: Path) -> list[Finding]:
    text = path.read_text(encoding="utf-8")
    out: list[Finding] = []
    front, body_start = split_frontmatter(text)
    for lineno, line in front:
        allow = line.lstrip().startswith("emoji:")
        out.extend(scan_text(line, path, lineno, primary=False, allow_emoji=allow))
    body = "\n".join(text.splitlines()[body_start - 1 :])
    out.extend(scan_text(blank_code(body), path, body_start, primary=False))
    return out


@dataclass
class HtmlCopy(HTMLParser):
    """Text nodes with their line numbers, the headline, the sublines and every href."""

    texts: list[tuple[int, str]] = field(default_factory=list)
    headlines: list[tuple[int, str]] = field(default_factory=list)
    sublines: list[tuple[int, str]] = field(default_factory=list)
    hrefs: list[str] = field(default_factory=list)
    _open: list[str] = field(default_factory=list)
    _h1: list[tuple[int, str]] = field(default_factory=list)
    _sub: list[tuple[int, str]] = field(default_factory=list)

    def __post_init__(self) -> None:
        super().__init__(convert_charrefs=True)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "a" and attributes.get("href"):
            self.hrefs.append(attributes["href"] or "")
        if tag in _HTML_VOID_TAGS:
            return
        classes = (attributes.get("class") or "").split()
        self._open.append("p.alg-subline" if tag == "p" and "alg-subline" in classes else tag)

    def handle_endtag(self, tag: str) -> None:
        while self._open:
            top = self._open.pop()
            if top.split(".")[0] == tag:
                if tag == "h1":
                    self.headlines.append(_join(self._h1))
                    self._h1 = []
                elif top == "p.alg-subline":
                    self.sublines.append(_join(self._sub))
                    self._sub = []
                break

    def handle_data(self, data: str) -> None:
        if not data.strip() or any(t in _HTML_SILENT_TAGS for t in self._open):
            return
        lineno = self.getpos()[0]
        self.texts.append((lineno, data))
        if "h1" in self._open:
            self._h1.append((lineno, data))
        if "p.alg-subline" in self._open:
            self._sub.append((lineno, data))


def _join(parts: list[tuple[int, str]]) -> tuple[int, str]:
    lineno = parts[0][0] if parts else 1
    return lineno, " ".join(" ".join(text for _, text in parts).split())


def parse_html(path: Path) -> HtmlCopy:
    page = HtmlCopy()
    page.feed(path.read_text(encoding="utf-8"))
    page.close()
    return page


def lint_html(path: Path) -> list[Finding]:
    page = parse_html(path)
    out: list[Finding] = []
    for lineno, text in page.texts:
        out.extend(scan_text(text, path, lineno, primary=True))
    for parts, budget, code, what in (
        (page.headlines, HEADLINE_MAX_WORDS, "headline", "h1"),
        (page.sublines, SUBLINE_MAX_WORDS, "subline", "subline"),
    ):
        for lineno, text in parts:
            n = word_count(text)
            if n > budget:
                out.append(Finding(path, lineno, code, f"{what} has {n} words, budget {budget}"))
    return out


def _literal(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        parts = [
            v.value for v in node.values if isinstance(v, ast.Constant) and isinstance(v.value, str)
        ]
        return "".join(parts) if parts else None
    return None


def _is_gr_call(call: ast.Call, names: frozenset[str]) -> bool:
    func = call.func
    if isinstance(func, ast.Attribute) and func.attr in names:
        return isinstance(func.value, ast.Name) and func.value.id == "gr"
    return False


def _is_render_header(call: ast.Call) -> bool:
    func = call.func
    if isinstance(func, ast.Name):
        return func.id == "render_header"
    return isinstance(func, ast.Attribute) and func.attr == "render_header"


def _header_arg(call: ast.Call, name: str, position: int) -> ast.AST | None:
    for kw in call.keywords:
        if kw.arg == name:
            return kw.value
    return call.args[position] if len(call.args) > position else None


def lint_python(path: Path) -> list[Finding]:
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        return [Finding(path, exc.lineno or 1, "syntax", f"cannot parse: {exc.msg}")]
    out: list[Finding] = []

    for node in tree.body:
        value = None
        if isinstance(node, ast.Assign | ast.AnnAssign):
            value = node.value
        text = _literal(value)
        if text is not None and value is not None:
            out.extend(scan_text(text, path, value.lineno, primary=True))

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if _is_gr_call(node, frozenset({"Markdown", "HTML"})):
            target = node.args[0] if node.args else None
            for kw in node.keywords:
                if kw.arg == "value":
                    target = kw.value
            text = _literal(target)
            if text is not None and target is not None:
                out.extend(scan_text(text, path, target.lineno, primary=True))
        for kw in node.keywords:
            if kw.arg == "label":
                text = _literal(kw.value)
                if text is not None:
                    out.extend(scan_text(text, path, kw.value.lineno, primary=True))
        if _is_render_header(node):
            for name, position, budget, code in (
                ("title", 0, HEADLINE_MAX_WORDS, "headline"),
                ("tagline", 1, SUBLINE_MAX_WORDS, "subline"),
            ):
                arg = _header_arg(node, name, position)
                text = _literal(arg)
                if text is None or arg is None:
                    continue
                out.extend(scan_text(text, path, arg.lineno, primary=True))
                n = word_count(text)
                if n > budget:
                    out.append(
                        Finding(path, arg.lineno, code, f"{name} has {n} words, budget {budget}")
                    )
    return out


def _dedupe(findings: list[Finding]) -> list[Finding]:
    seen: set[Finding] = set()
    out: list[Finding] = []
    for f in findings:
        if f not in seen:
            seen.add(f)
            out.append(f)
    return sorted(out, key=lambda f: (str(f.file), f.line, f.code, f.message))


def _files(space_dir: Path, pattern: str) -> list[Path]:
    files = []
    for p in sorted(space_dir.rglob(pattern)):
        rel = p.relative_to(space_dir)
        if any(part in _SKIP_DIRS for part in rel.parts[:-1]):
            continue
        files.append(p)
    return files


def python_files(space_dir: Path) -> list[Path]:
    return _files(space_dir, "*.py")


def html_files(space_dir: Path) -> list[Path]:
    return _files(space_dir, "*.html")


def find_shell(space_dir: Path) -> Path | None:
    local = space_dir / "shell.py"
    if local.is_file():
        return local
    shared = space_dir.parent / "_shared" / "algenta_spaces" / "shell.py"
    return shared if shared.is_file() else None


def lint_links(space_dir: Path) -> list[Finding]:
    shell = find_shell(space_dir)
    if shell is None:
        return [
            Finding(
                space_dir / "shell.py", 1, "shell-missing", "no shell module renders the footer"
            )
        ]
    source = shell.read_text(encoding="utf-8")
    return [
        Finding(shell, 1, "link-missing", f"footer lacks {url}")
        for url in REQUIRED_LINKS
        if url not in source
    ]


def lint_page_links(space_dir: Path) -> list[Finding]:
    """A redirect stub has no shell: its ``index.html`` must carry the footer links."""
    index = space_dir / "index.html"
    if not index.is_file():
        return [Finding(index, 1, "page-missing", "no index.html renders the page")]
    hrefs = set(parse_html(index).hrefs)
    return [
        Finding(index, 1, "link-missing", f"footer lacks {url}")
        for url in REQUIRED_LINKS
        if url not in hrefs
    ]


def lint_space(space_dir: Path, *, require_links: bool = True) -> list[Finding]:
    space_dir = Path(space_dir)
    if not space_dir.is_dir():
        raise FileNotFoundError(space_dir)
    findings: list[Finding] = []
    readme = space_dir / "README.md"
    if readme.is_file():
        findings.extend(lint_readme(readme))
    for py in python_files(space_dir):
        findings.extend(lint_python(py))
    for page in html_files(space_dir):
        findings.extend(lint_html(page))
    if require_links:
        findings.extend(
            lint_page_links(space_dir) if is_redirect(space_dir) else lint_links(space_dir)
        )
    return _dedupe(findings)


def is_retired(space_dir: Path) -> bool:
    return "_retired" in Path(space_dir).resolve().parts


def is_redirect(space_dir: Path) -> bool:
    return "_redirects" in Path(space_dir).resolve().parts


def summarize(findings: list[Finding]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for f in findings:
        counts[f.code] = counts.get(f.code, 0) + 1
    return dict(sorted(counts.items()))


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="lint user-visible copy in Space directories")
    ap.add_argument("dirs", nargs="+", type=Path)
    ap.add_argument("--retired", action="store_true", help="skip the required-links rule")
    a = ap.parse_args(argv)
    total = 0
    for d in a.dirs:
        findings = lint_space(d, require_links=not (a.retired or is_retired(d)))
        for f in findings:
            print(f.format(Path.cwd()))
        counts = ", ".join(f"{k}={v}" for k, v in summarize(findings).items()) or "clean"
        print(f"{d}: {len(findings)} finding(s) ({counts})")
        total += len(findings)
    return 1 if total else 0


if __name__ == "__main__":
    raise SystemExit(main())
