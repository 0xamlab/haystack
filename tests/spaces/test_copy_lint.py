"""apps/spaces/tools/copy_lint.py — canon and Apple copy rules on fixture Spaces."""

from __future__ import annotations

from pathlib import Path

import copy_lint as cl
import pytest

CLEAN_README = """---
title: Algenta
emoji: ⚡
short_description: 6,000+ compiled Mojo kernels. Race them against Python.
---

# Algenta

Compiler-driven, self-hosted AI infrastructure. Commercial plans at https://algenta.ai/pricing.
"""

CLEAN_APP = '''"""app"""
import gradio as gr
from algenta_spaces.shell import render_header

TAGLINE = "Race compiled kernels against the Python libraries they replace"
HEADER = render_header(title="Algenta", tagline=TAGLINE)

with gr.Blocks() as demo:
    gr.Markdown("Every number here is measured in this container.")
    gr.HTML(value="<p>Results carry their hardware and time.</p>")
    gr.Textbox(label="Query")
    gr.Number(label="Trials", value=1)
'''

CLEAN_SHELL = """PRICING_URL = "https://algenta.ai/pricing"
DISCORD_URL = "https://discord.gg/w8NDsph9an"
"""


def _space(
    tmp_path: Path,
    *,
    readme: str = CLEAN_README,
    app: str = CLEAN_APP,
    shell: str | None = CLEAN_SHELL,
) -> Path:
    d = tmp_path / "space"
    d.mkdir(parents=True)
    (d / "README.md").write_text(readme, encoding="utf-8")
    (d / "app.py").write_text(app, encoding="utf-8")
    if shell is not None:
        (d / "shell.py").write_text(shell, encoding="utf-8")
    (d / "tests").mkdir()
    (d / "tests" / "test_x.py").write_text('BAD = "decision engine mock TODO!"\n', encoding="utf-8")
    (d / "scripts").mkdir()
    (d / "scripts" / "gen.py").write_text('MSG = "coming soon!"\n', encoding="utf-8")
    return d


def test_clean_space_has_no_findings(tmp_path: Path) -> None:
    assert cl.lint_space(_space(tmp_path)) == []


def test_readme_rules(tmp_path: Path) -> None:
    readme = """---
title: Algenta ⚡ live
emoji: 🏁
short_description: The governed decision engine, at machine speed — live
---

# ⚡ Algenta — the governed decision engine!

A mock preview, coming soon. Lorem ipsum. Beta placeholder TODO. Mail sales@algenta.ai.
The stat card shows parity ✓ and never SIMULATED numbers.
"""
    findings = cl.lint_space(_space(tmp_path, readme=readme))
    by_line = {}
    for f in findings:
        if f.file.name == "README.md":
            by_line.setdefault(f.line, set()).add((f.code, f.message))
    assert by_line[2] == {("emoji", "emoji '⚡' in app copy")}
    assert 3 not in by_line, "emoji: is the one place an emoji may live"
    assert by_line[4] == {("banned", "decision engine")}
    assert by_line[7] == {
        ("emoji", "emoji '⚡' in app copy"),
        ("banned", "decision engine"),
        ("exclaim", "exclamation mark"),
    }
    assert {m for _, m in by_line[9]} == {
        "mock",
        "preview",
        "coming soon",
        "lorem",
        "beta",
        "placeholder",
        "todo",
        "email address",
    }
    assert by_line[10] == {("banned", "simulated")}, "the check mark is typographic, not an emoji"


def test_python_string_sources_and_word_budgets(tmp_path: Path) -> None:
    app = """import gradio as gr
from shell import render_header

HERO = "The governed decision engine, at machine speed"
NOTE = f"measured on {1} vCPU (cgroup-effective), harness v0.2"
HEADER = render_header(
    title="Algenta Speed Arena for compiled Mojo kernels",
    tagline="Real-time benchmark duels between native Mojo kernels and the incumbent Python libraries they quietly replace",
    badges=["live"],
)
OTHER = render_header("A B C D E F G", "short")

with gr.Blocks() as demo:
    gr.Markdown("Simulated engine: bit-faithful to R7. Nothing canned!")
    gr.HTML(value="<b>clean-room rewrite</b>")
    gr.Textbox(label="mock query")
    gr.Code(value="x != y", label="result")
    gr.Markdown(some_variable)
"""
    findings = cl.lint_space(_space(tmp_path, app=app))
    app_findings = [(f.line, f.code, f.message) for f in findings if f.file.name == "app.py"]
    assert (4, "banned", "decision engine") in app_findings
    assert (5, "jargon", "cgroup") in app_findings
    assert (5, "jargon", "harness version") in app_findings
    assert (7, "headline", "title has 7 words, budget 6") in app_findings
    assert (8, "subline", "tagline has 15 words, budget 14") in app_findings
    assert (11, "headline", "title has 7 words, budget 6") in app_findings
    assert (14, "banned", "simulated") in app_findings
    assert (14, "jargon", "bit-faithful") in app_findings
    assert (14, "jargon", "rule ids R4/R7/R9") in app_findings
    assert (14, "exclaim", "exclamation mark") in app_findings
    assert (15, "jargon", "clean-room") in app_findings
    assert (16, "banned", "mock") in app_findings
    assert not any(line == 17 for line, _, _ in app_findings), (
        "`!=` inside a code value is not an exclamation"
    )
    assert not any(f.file.parent.name in {"tests", "scripts"} for f in findings)


def test_multiline_strings_report_the_inner_line(tmp_path: Path) -> None:
    app = 'import gradio as gr\nBODY = """first line\nsecond has a placeholder\nthird ok\n"""\n'
    findings = cl.lint_space(_space(tmp_path, app=app))
    assert [(f.line, f.code) for f in findings if f.file.name == "app.py"] == [(3, "banned")]


def test_required_links_in_the_shell(tmp_path: Path) -> None:
    findings = cl.lint_space(_space(tmp_path, shell='PRICING = "https://algenta.ai/pricing"\n'))
    assert [(f.code, f.message) for f in findings] == [
        ("link-missing", "footer lacks https://discord.gg/w8NDsph9an")
    ]
    findings = cl.lint_space(_space(tmp_path / "b", shell=None))
    assert [f.code for f in findings] == ["shell-missing"]
    assert cl.lint_space(_space(tmp_path / "c", shell=None), require_links=False) == []


def test_shared_shell_is_found_next_to_the_space(tmp_path: Path) -> None:
    apps = tmp_path / "apps"
    apps.mkdir()
    space = _space(apps, shell=None)
    shared = apps / "_shared" / "algenta_spaces"
    shared.mkdir(parents=True)
    (shared / "shell.py").write_text(CLEAN_SHELL, encoding="utf-8")
    assert cl.find_shell(space) == shared / "shell.py"
    assert cl.lint_space(space) == []


def test_syntax_errors_are_findings(tmp_path: Path) -> None:
    findings = cl.lint_space(_space(tmp_path, app="def broken(:\n"))
    assert [f.code for f in findings] == ["syntax"]


def test_helpers() -> None:
    assert cl.word_count("Live duels — Mojo drop-ins vs the Python libs they replace") == 10
    assert cl.emoji_in("parity ✓ and ⚡ and 🛡️") == ["⚡", "🛡"]
    assert cl.split_frontmatter("no frontmatter\n") == ([], 1)
    assert cl.split_frontmatter("---\na: 1\n---\nbody\n") == ([(2, "a: 1")], 4)
    assert cl.split_frontmatter("---\nunterminated\n") == ([], 1)
    assert cl.is_retired(Path("/x/apps/spaces/_retired/llm-modules"))
    assert not cl.is_retired(Path("/x/apps/spaces/algenta"))
    assert cl.is_redirect(Path("/x/apps/spaces/_redirects/llm-modules"))
    assert not cl.is_redirect(Path("/x/apps/spaces/algenta"))
    assert cl.blank_code("a `!x` b\n```\nmock!\n```\nc") == "a      b\n   \n     \n   \nc"
    assert cl.summarize(
        [
            cl.Finding(Path("a"), 1, "banned", "x"),
            cl.Finding(Path("a"), 2, "banned", "y"),
            cl.Finding(Path("a"), 3, "emoji", "z"),
        ]
    ) == {"banned": 2, "emoji": 1}
    assert cl.Finding(Path("/r/a.py"), 3, "banned", "x").format(Path("/r")) == "a.py:3: [banned] x"
    assert (
        cl.Finding(Path("/r/a.py"), 3, "banned", "x").format(Path("/other"))
        == "/r/a.py:3: [banned] x"
    )


def test_cli_exit_codes_and_summary(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    clean = _space(tmp_path / "clean")
    assert cl.main([str(clean)]) == 0
    assert "0 finding(s) (clean)" in capsys.readouterr().out
    dirty = _space(tmp_path / "dirty", app='X = "mock"\n', shell=None)
    assert cl.main([str(dirty)]) == 1
    out = capsys.readouterr().out
    assert "[banned] mock" in out and "banned=1, shell-missing=1" in out
    assert cl.main([str(dirty), "--retired"]) == 1
    assert "banned=1)" in capsys.readouterr().out
    with pytest.raises(FileNotFoundError):
        cl.lint_space(tmp_path / "missing")


def test_current_apps_report_the_known_canon_violations(apps_spaces_dir: Path) -> None:
    """M2 rewrote the flagship: no banned phrase, no jargon, no emoji in its copy."""
    findings = cl.lint_space(apps_spaces_dir / "algenta")
    codes = {f.code for f in findings}
    assert "decision engine" not in {f.message for f in findings}, findings
    assert not codes & {"banned", "jargon", "emoji", "headline", "subline", "link-missing"}, (
        findings
    )


def test_the_flagship_is_clean_through_the_cli(
    apps_spaces_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """What the QA table claims (`copy_lint.py apps/spaces/algenta` → 0 findings) is asserted
    here through the CLI itself, so an exclamation mark inside the audit JavaScript
    (`verify_checks.py`, round 2's `!t`) fails the unit suite and not only the release gate."""
    assert cl.main([str(apps_spaces_dir / "algenta")]) == 0
    out = capsys.readouterr().out
    assert out.strip().endswith("apps/spaces/algenta: 0 finding(s) (clean)") or (
        "0 finding(s) (clean)" in out
    )
    exclaims = [f for f in cl.lint_space(apps_spaces_dir / "algenta") if f.code == "exclaim"]
    assert exclaims == [], [f.format(apps_spaces_dir.parents[1]) for f in exclaims]


STUB_README = """---
title: Algenta
emoji: 🤖
sdk: static
short_description: Moved to thyn-ai/algenta
---

This lab moved into the Algenta flagship at https://huggingface.co/spaces/thyn-ai/algenta.
"""

STUB_INDEX = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <link rel="canonical" href="https://huggingface.co/spaces/thyn-ai/algenta">
  <title>Algenta · moved</title>
</head>
<body>
  <main>
    <h1>Now part of Algenta</h1>
    <p class="alg-subline">This lab moved into the Algenta flagship. Taking you there now.</p>
    <a href="https://huggingface.co/spaces/thyn-ai/algenta" target="_top">Open the new home</a>
    <footer>
      <p>Commercial plans at <a href="https://algenta.ai/pricing">algenta.ai/pricing</a> ·
      community on <a href="https://discord.gg/w8NDsph9an">Discord</a></p>
    </footer>
  </main>
</body>
</html>
"""


def _stub(tmp_path: Path, *, readme: str = STUB_README, index: str | None = STUB_INDEX) -> Path:
    d = tmp_path / "apps" / "spaces" / "_redirects" / "old-lab"
    d.mkdir(parents=True)
    (d / "README.md").write_text(readme, encoding="utf-8")
    if index is not None:
        (d / "index.html").write_text(index, encoding="utf-8")
    (d / "style.css").write_text("h1 { margin: 0 !important; }\n", encoding="utf-8")
    return d


def test_redirect_stub_needs_the_footer_links_in_index_html_not_a_shell(tmp_path: Path) -> None:
    assert cl.lint_space(_stub(tmp_path)) == [], "a clean stub: no shell-missing, no findings"
    no_discord = STUB_INDEX.replace(
        '<a href="https://discord.gg/w8NDsph9an">Discord</a>', "Discord"
    )
    findings = cl.lint_space(_stub(tmp_path / "b", index=no_discord))
    assert [(f.file.name, f.code, f.message) for f in findings] == [
        ("index.html", "link-missing", "footer lacks https://discord.gg/w8NDsph9an")
    ]
    findings = cl.lint_space(_stub(tmp_path / "c", index=None))
    assert [(f.file.name, f.code) for f in findings] == [("index.html", "page-missing")]
    assert cl.lint_space(_stub(tmp_path / "d", index=None), require_links=False) == []


def test_html_text_nodes_are_copy(tmp_path: Path) -> None:
    index = """<!doctype html>
<html lang="en">
<head>
  <title>Algenta · moved</title>
  <style>
    .x { color: red !important; }
  </style>
</head>
<body>
  <h1>Now part of the <em>Algenta</em> flagship demo</h1>
  <p class="alg-subline">This lab moved into the Algenta flagship and it is taking you
     there in three seconds.</p>
  <p>The governed decision engine was a mock.</p>
  <h2>Where each tab went ⚡</h2>
  <table><tr><td>Nothing canned!</td></tr></table>
  <p>Powered by cgroups and bit-faithful R7 checks.</p>
  <p>Read <code>x != y</code> here.</p>
  <footer><a href="https://algenta.ai/pricing">plans</a> <a href="https://discord.gg/w8NDsph9an">Discord</a></footer>
</body>
</html>
"""
    findings = cl.lint_space(_stub(tmp_path, index=index))
    got = sorted((f.line, f.code, f.message) for f in findings if f.file.name == "index.html")
    assert got == [
        (10, "headline", "h1 has 7 words, budget 6"),
        (11, "subline", "subline has 16 words, budget 14"),
        (13, "banned", "decision engine"),
        (13, "banned", "mock"),
        (14, "emoji", "emoji '⚡' in app copy"),
        (15, "exclaim", "exclamation mark"),
        (16, "jargon", "bit-faithful"),
        (16, "jargon", "cgroup"),
        (16, "jargon", "rule ids R4/R7/R9"),
    ], "style bodies are not copy; `!=` inside <code> is not an exclamation"
    page = cl.parse_html(tmp_path / "apps/spaces/_redirects/old-lab/index.html")
    assert page.headlines == [(10, "Now part of the Algenta flagship demo")]
    assert page.hrefs == ["https://algenta.ai/pricing", "https://discord.gg/w8NDsph9an"]


def test_markdown_code_is_not_copy(tmp_path: Path) -> None:
    readme = """# algenta_spaces

| module | what it gives |
|---|---|
| `css` | `rule` (class repeated four times, never `!important`) |

```python
MSG = "mock placeholder TODO!"
```

~~~
coming soon!
~~~

Real copy with a shout! And a ``double `tick` span!`` too.
"""
    findings = cl.lint_space(_space(tmp_path, readme=readme))
    assert [(f.line, f.code, f.message) for f in findings if f.file.name == "README.md"] == [
        (15, "exclaim", "exclamation mark")
    ]


def test_shared_package_is_clean_today_and_no_redirect_stub_remains(apps_spaces_dir: Path) -> None:
    """The copy gate that is green today: the shared package. The three redirect stubs left the
    fleet on 2026-09-23 (deleted from the Hub); the stub rules stay covered by `_stub` above."""
    assert cl.lint_space(apps_spaces_dir / "_shared") == []
    assert not (apps_spaces_dir / "_redirects").exists(), "a redirect stub came back"
    assert cl.main([str(apps_spaces_dir / "_shared")]) == 0
