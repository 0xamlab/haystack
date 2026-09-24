"""algenta_spaces.shell — header, footer, nav, copy rules, stylesheet discipline."""

from __future__ import annotations

import re

import pytest
from _rules import (
    _assert_clean_copy,
    _assert_four_class_selectors,
    _assert_stylesheet_discipline,
)
from algenta_spaces import design, shell

REQUIRED_LINKS = {
    "https://huggingface.co/spaces/thyn-ai/algenta",
    "https://huggingface.co/thyn-ai",
    "https://github.com/thyn-ai/mojo-kernels",
    "https://docs.algenta.ai",
    "https://algenta.ai/pricing",
    "https://discord.gg/w8NDsph9an",
}


def test_nav_is_exactly_the_eight_fleet_links():
    assert [label for label, _ in shell.NAV] == [
        "Flagship",
        "Kernels Hub",
        "GitHub",
        "Docs",
        "Pricing",
        "Discord",
    ]
    assert {url for _, url in shell.NAV} == REQUIRED_LINKS


def test_header_renders_every_link_the_eyebrow_and_the_duplicate_link():
    html = shell.render_header(
        "Compiled kernels, live",
        "Race them against Python",
        [("measured here", "ok"), "Hub kernels"],
        active="Flagship",
        space_id="thyn-ai/algenta",
    )
    # the header links the other two Spaces; the resources (Hub, GitHub, Docs, Pricing, Discord)
    # are the footer's — the two kinds of link do not share a line (owner, 2026-09-23)
    for _, url in shell.SPACES_NAV:
        if url != "https://huggingface.co/spaces/thyn-ai/algenta":
            assert f'href="{url}"' in html
    for _, url in shell.RESOURCE_LINKS:
        assert f'href="{url}"' not in html
    footer = shell.render_footer(active="Flagship", stamp="dev", commit="dev")
    for url in REQUIRED_LINKS - {"https://huggingface.co/spaces/thyn-ai/algenta"}:
        assert f'href="{url}"' in footer
    # the active Space is text, not a link
    assert 'href="https://huggingface.co/spaces/thyn-ai/algenta"' not in html
    assert '<span class="alg-shell-nav-active" aria-current="page">Flagship</span>' in html
    assert shell.EYEBROW in html
    assert "compiler-driven, self-hosted AI infrastructure" in html
    assert 'href="https://huggingface.co/spaces/thyn-ai/algenta?duplicate=true"' in html
    assert "Duplicate this Space" in html
    assert "alg-shell-badge-ok" in html
    _assert_clean_copy(html)


def test_header_without_space_id_omits_duplicate_link(monkeypatch):
    monkeypatch.delenv("SPACE_ID", raising=False)
    html = shell.render_header("Flagship", "Mojo drop-ins against the Python libraries")
    assert "duplicate=true" not in html
    monkeypatch.setenv("SPACE_ID", "thyn-ai/algenta-speed-arena")
    html = shell.render_header("Flagship", "Mojo drop-ins against the Python libraries")
    assert "thyn-ai/algenta-speed-arena?duplicate=true" in html


def test_header_escapes_user_text():
    html = shell.render_header("<b>Kernels</b>", 'Race "them" & win', ["<i>x</i>"])
    assert "<b>" not in html
    assert "&lt;b&gt;Kernels&lt;/b&gt;" in html
    assert "&quot;them&quot; &amp; win" in html
    assert "&lt;i&gt;x&lt;/i&gt;" in html


@pytest.mark.parametrize(
    ("title", "tagline"),
    [
        ("One two three four five six seven", "fine"),
        ("Fine", " ".join(["word"] * 15)),
        ("Fast kernels!", "fine"),
        ("Fine", "the decision engine is here"),
        ("Fine", "measured inside the cgroup"),
        ("Fine", "R7 configs printed"),
        ("Fine", "\U0001f680 launch"),
        ("", "fine"),
    ],
)
def test_header_rejects_copy_that_breaks_the_rules(title, tagline):
    with pytest.raises(ValueError):
        shell.render_header(title, tagline)


def test_header_rejects_unknown_active_and_badge_variant():
    with pytest.raises(ValueError):
        shell.render_header("Fine", "fine", active="LLM Agents lab")
    with pytest.raises(ValueError):
        shell.render_header("Fine", "fine", [("x", "danger")])


def test_footer_has_canon_licence_links_and_stamp(tmp_path):
    html = shell.render_footer(stamp="abc1234def")
    assert shell.CANON in html
    assert shell.LICENCE_LINE in html
    assert "Algenta Community License 1.1" in html
    assert "algenta.ai/pricing" in html
    # the resources live in the footer; the flagship (the one Space) is the header's own link
    for url in REQUIRED_LINKS - {shell.FLAGSHIP_URL}:
        assert f'href="{url}"' in html
    assert f'href="{shell.FLAGSHIP_URL}"' in shell.render_header("Algenta", "Compiled Mojo kernels")
    assert "build abc1234def" in html
    assert "@" not in html  # never an email
    _assert_clean_copy(html)


def test_footer_stamp_reads_shared_sha_file_or_dev(tmp_path):
    missing = tmp_path / ".shared_sha"
    assert shell.shared_sha(missing) == "dev"
    missing.write_text("not a sha\n")
    assert shell.shared_sha(missing) == "dev"
    missing.write_text("0123ABCDEF0123456789abcdef0123456789abcd\n")
    assert shell.shared_sha(missing) == "0123abcdef0123456789abcdef0123456789abcd"
    # the default location is next to the package; no stamp there in the repo
    assert shell.shared_sha() == "dev"


def test_footer_active_label_is_text_and_unknown_raises():
    html = shell.render_footer(active="Docs", stamp="dev")
    assert 'href="https://docs.algenta.ai"' not in html
    assert "alg-shell-footer-active" in html
    with pytest.raises(ValueError):
        shell.render_footer(active="SDK", stamp="dev")


def test_duplicate_url_validates_space_id():
    assert (
        shell.duplicate_url("thyn-ai/algenta")
        == "https://huggingface.co/spaces/thyn-ai/algenta?duplicate=true"
    )
    for bad in ("algenta", "thyn-ai/", "/algenta", "a b/c", "thyn-ai/algenta/x"):
        with pytest.raises(ValueError):
            shell.duplicate_url(bad)


def test_check_copy_and_detectors():
    assert shell.check_copy("Compiled kernels, live", max_words=6) == "Compiled kernels, live"
    assert shell.banned_phrase("a Decision Engine") == "Decision Engine"
    assert shell.banned_phrase("bit-faithful") == "bit-faithful"
    assert shell.banned_phrase("write to sales@algenta.ai") == "@algenta.ai"
    assert shell.banned_phrase("R4X is a part number") is None
    assert shell.banned_phrase("exact match") is None
    assert shell.has_emoji("ok ✅")
    assert not shell.has_emoji("ratio 3.2× · P95 — fine")


def test_shell_css_discipline():
    css = shell.SHELL_CSS
    _assert_stylesheet_discipline(css)
    _assert_four_class_selectors(css)
    assert "var(--alg-" in css
    assert "#" not in css.replace("#", "", 0)  # colours come from tokens only


# --------------------------------------------------------------- interactive targets

INTERACTIVE = (
    "alg-shell-nav-link",
    "alg-shell-nav-active",
    "alg-shell-nav-dup",
    "alg-shell-footer-link",
    "alg-shell-footer-active",
)
_RULE_RE = re.compile(r"^((?:\.[\w-]+)+)((?::[\w-]+)*) \{ (.*) \}$")
_TOKEN_RE = re.compile(r"--(alg-[\w-]+): ([^;]+);")
_VAR_RE = re.compile(r"var\(--(alg-[\w-]+)\)")


def _rules(css: str) -> dict[tuple[str, str], dict[str, str]]:
    """{(class, pseudo): {property: value}} for every single-line rule in a stylesheet."""
    out: dict[tuple[str, str], dict[str, str]] = {}
    for line in css.splitlines():
        m = _RULE_RE.match(line.strip())
        if not m:
            continue
        cls = m.group(1).split(".")[1]
        decls = out.setdefault((cls, m.group(2)), {})
        for decl in m.group(3).split(";"):
            if decl.strip():
                prop, _, value = decl.partition(":")
                decls[prop.strip()] = value.strip()
    return out


def _px(value: str, tokens: dict[str, str]) -> float:
    """A CSS length in px, resolving `var(--alg-*)` through the token set."""
    value = _VAR_RE.sub(lambda m: tokens[m.group(1)], value).strip()
    assert value.endswith("px"), value
    return float(value[:-2])


def _vertical_padding(shorthand: str, tokens: dict[str, str]) -> float:
    parts = shorthand.split()
    assert 1 <= len(parts) <= 4, shorthand
    top = _px(parts[0], tokens)
    bottom = _px(parts[2], tokens) if len(parts) >= 3 else top
    return top + bottom


def test_every_interactive_target_is_at_least_44px_tall():
    tokens = dict(_TOKEN_RE.findall(design.TOKENS_CSS))
    rules = _rules(shell.SHELL_CSS)
    for cls in INTERACTIVE:
        decls = rules[(cls, "")]
        if "min-height" in decls:
            height = _px(decls["min-height"], tokens)
        else:
            assert "line-height" in decls, f"{cls} declares neither line-height nor min-height"
            height = _px(decls["line-height"], tokens) + _vertical_padding(
                decls.get("padding", "0"), tokens
            )
        assert height >= design.TARGET_PX, f"{cls} is {height}px tall"


def test_focus_rings_follow_the_element_radius():
    css = shell.SHELL_CSS
    assert not re.search(r"border-radius:\s*4px", css), "no 4px radius anywhere"
    rules = _rules(css)
    for cls in ("alg-shell-nav-link", "alg-shell-footer-link"):
        focus = rules[(cls, ":focus-visible")]
        assert focus["outline"] == "2px solid var(--alg-accent-to)"
        assert focus["border-radius"] == "var(--alg-radius-input)"
    pill, pill_focus = (
        rules[("alg-shell-nav-dup", "")],
        rules[("alg-shell-nav-dup", ":focus-visible")],
    )
    assert pill["border-radius"] == "var(--alg-radius-pill)"
    assert pill_focus["outline"] == "2px solid var(--alg-accent-to)"
    assert pill_focus["border-radius"] == pill["border-radius"], (
        "the pill keeps its radius on focus"
    )


# ------------------------------------------------------- M2-B design system: nav as a list


def test_nav_and_footer_are_lists_whose_separators_cannot_wrap_alone():
    header = shell.render_header("Fine", "fine", active="Flagship", space_id="thyn-ai/algenta")
    nav = header[header.index("<nav") :]
    assert '<ul class="alg-shell-nav-list">' in nav
    # the header's nav is the three Spaces; the resources live in the footer (owner, 2026-09-23:
    # the two kinds of link do not belong together in one line)
    assert nav.count('<li class="alg-shell-nav-item">') == len(shell.SPACES_NAV) == 1
    for label, url in shell.RESOURCE_LINKS:
        assert label not in nav and url not in nav, label
    assert shell.NAV == shell.SPACES_NAV + shell.RESOURCE_LINKS
    assert "alg-shell-sep" not in nav and shell.SEPARATOR not in nav
    footer = shell.render_footer(stamp="dev")
    # one Space: the footer shows the resources alone, no one-item Spaces group (round 9)
    assert footer.count('<li class="alg-shell-footer-item">') == len(shell.RESOURCE_LINKS)
    assert 'aria-label="Spaces"' not in footer
    # the footer keeps every link, in two groups: the Spaces, then the resources
    # one Space: a single Resources list (the Spaces group returns with a second Space)
    assert footer.count('<ul class="alg-shell-footer-list') == 1
    assert '<ul class="alg-shell-footer-list" aria-label="Resources">' in footer
    assert footer.index("Kernels Hub") < footer.index("Discord")
    # the list itself carries no separator glyph (the commit · build stamp after it does,
    # when a checkout has a commit — CI has one, a bare local run does not)
    assert shell.SEPARATOR not in footer[footer.index("<ul") : footer.index("</ul>")]
    css = shell.SHELL_CSS
    for item in ("alg-shell-nav-item", "alg-shell-footer-item"):
        sel = f".{item}" * 4
        line = next(ln for ln in css.splitlines() if ln.startswith(f"{sel} + .{item}::before {{"))
        assert f'content: "{shell.SEPARATOR}"' in line and "var(--alg-text-2)" in line
    rules = _rules(css)
    for cls in (
        "alg-shell-nav-link",
        "alg-shell-footer-link",
        "alg-shell-nav-active",
        "alg-shell-footer-active",
    ):
        decls = rules[(cls, "")]
        assert decls["min-inline-size"] == "var(--alg-target)", cls
        assert decls["display"] == "inline-flex" and decls["white-space"] == "nowrap", cls
    # the glyph sits in the column gap (no layout of its own) and the item that opens a wrapped
    # row, marked by the head script, draws none
    for item in ("alg-shell-nav-item", "alg-shell-footer-item"):
        sel = f".{item}" * 4
        line = next(ln for ln in css.splitlines() if ln.startswith(f"{sel} + .{item}::before {{"))
        assert "position: absolute" in line and f"width: {shell.SEPARATOR_GAP_PX}px" in line
        assert f"{sel}[{shell.ROW_START_ATTR}]::before {{ content: none; }}" in css
        assert rules[(item, "")]["position"] == "relative"
    assert rules[("alg-shell-nav-list", "")]["gap"] == f"0 {shell.SEPARATOR_GAP_PX}px"
    script = shell.NAV_ROWS_SCRIPT
    assert shell.ROW_START_ATTR in script and "ResizeObserver" in script
    assert ".alg-shell-nav-list" in script and ".alg-shell-footer-list" in script
    assert "!" not in script.replace("!==", ""), "no exclamation mark (copy lint)"
    assert shell.NAV_ROWS_HEAD.startswith(f"<script>{script}</script>")
    assert f"@media (width <= {shell.PHONE_MAX_WIDTH}px)" in css and shell.PHONE_MAX_WIDTH == 767
    _assert_clean_copy(header)


# ---------------------------------------------- head scripts: disclosure state, tab strip


def test_head_fragment_carries_the_five_scripts_without_an_exclamation_mark():
    assert shell.HEAD_SCRIPTS == (
        shell.NAV_ROWS_SCRIPT,
        shell.DISCLOSURE_SCRIPT,
        shell.TABSTRIP_SCRIPT,
        shell.CHIP_WRAP_SCRIPT,
        shell.DROPDOWN_CLOSE_SCRIPT,
    )
    assert shell.NAV_ROWS_HEAD == "".join(f"<script>{s}</script>" for s in shell.HEAD_SCRIPTS)
    assert shell.SHELL_HEAD == shell.NAV_ROWS_HEAD
    for script in shell.HEAD_SCRIPTS:
        assert "!" not in script.replace("!==", ""), "no exclamation mark (copy lint)"
        assert script.startswith("(function () {") and script.endswith(" })();")
        assert "DOMContentLoaded" in script
    disclosure = shell.DISCLOSURE_SCRIPT
    assert "'.alg-disclosure > button'" in disclosure
    assert '[data-testid="accordion-content"]' in disclosure
    assert (
        "aria-expanded" in disclosure
        and "getComputedStyle(content).display !== 'none'" in disclosure
    )
    assert "attributeFilter: ['style']" in disclosure, "re-run when Gradio toggles the content"
    strip = shell.TABSTRIP_SCRIPT
    assert '[role="tab"][aria-selected="true"]' in strip and "scrollLeft" in strip
    assert "wrap.scrollWidth > wrap.clientWidth + 1" in strip, "a strip that fits is untouched"
    assert "attributeFilter: ['aria-selected']" in strip and "'resize'" in strip
    assert "addEventListener('focusin'" in strip, "a tab that takes focus is revealed too"
    wrap = shell.CHIP_WRAP_SCRIPT
    assert f"var ATTR = '{shell.CHIP_WRAP_ATTR}';" in wrap
    assert f"var CHIPS = '{shell.WRAP_SELECTOR}';" in wrap
    assert shell.WRAP_SELECTOR == ".alg-chip, .alg-shell-badge", "pills wrap like chips"
    assert "range.getClientRects()" in wrap and "Math.round(rect.top)" in wrap, (
        "wrapping is read from the chip's line boxes, never guessed from a height"
    )
    assert "chip.offsetParent === null" in wrap, "chips hidden with their tab are skipped"
    assert "requestAnimationFrame" in wrap, "one pass per frame"
    assert "attributeFilter: ['style', 'class', 'aria-selected']" in wrap, (
        "the attribute it sets is not observed, so a pass never schedules another"
    )
    assert "document.fonts.ready" in wrap and "'resize'" in wrap
    # round 8: the departed box's OPEN list is marked on the Tab keydown itself and whenever a
    # box turns expanded while unfocused (Gradio re-expands it with a filtered one-row list)
    script = shell.DROPDOWN_CLOSE_SCRIPT
    assert "var markPanelOf = function (box)" in script
    assert "box.closest('.wrap')" in script and "wrap.querySelector(LIST_PANEL)" in script
    assert "markPanelOf(event.target)" in script and "markPanelOf(box); schedule();" in script


def test_footer_stamp_is_twelve_hex_on_one_line_with_the_full_sha_as_title():
    """Round 2: the full 64-hex `.shared_sha` measured 546 × 20 px on the desktop and three
    lines at 375 px. Twelve characters name a build; the whole value rides in `title`, and
    the span keeps the verifiers' contract (`alg-shell-stamp">build <hex><`)."""
    import re

    import verify_remote as vr

    full = "bc8e7c68957ebaf278e6bff976d3577c9545abbf18a60ed1dc13c02f461b0c57"
    html = shell.render_footer(stamp=full)
    assert f'<span title="build {full}" class="alg-shell-stamp">build bc8e7c68957e</span>' in html
    assert shell.short_stamp(full) == "bc8e7c68957e" and shell.SHORT_STAMP_CHARS == 12
    assert shell.short_stamp("dev") == "dev"
    assert shell.render_footer(stamp="dev").count("build dev") == 1
    assert 'title="build dev"' not in shell.render_footer(stamp="dev"), "no title without a sha"
    # the verifiers read the stamp as a prefix of the staged sha: the plain page, Gradio's
    # escaped `window.gradio_config` spelling, and the /config route all still match
    assert vr.footer_stamp_of(html) == "bc8e7c68957e" and full.startswith(vr.footer_stamp_of(html))
    escaped = html.replace('"', '\\"').replace(">", "\\u003e").replace("<", "\\u003c")
    assert vr.footer_stamp_of(escaped) == "bc8e7c68957e"
    check_re = re.compile(
        r'alg-shell-stamp\\?"(?:>|\\u003e)build ([0-9a-f]{7,64}|dev)(?:<|\\u003c)'
    )  # verify_checks.STAMP_RE, spelled here so the shell test does not import the app
    assert check_re.search(html).group(1) == "bc8e7c68957e"
    assert check_re.search(shell.render_footer(stamp="dev")).group(1) == "dev"
    stamp = _rules(shell.SHELL_CSS)[("alg-shell-stamp", "")]
    assert stamp["white-space"] == "nowrap" and "overflow-wrap" not in stamp
    _assert_clean_copy(html)


def test_footer_names_the_deploy_commit_beside_the_shared_stamp(tmp_path):
    """Round 5: both reviewers read `build 0dfc70f1ed86` as the git build and could not correlate
    the page with a release. The deploy's commit precedes the shared-package stamp — nine
    characters, this repository's own abbreviation (round 10: seven read short beside the
    twelve of the build), the full sha in `title` — and is left out when no sha is known
    (`dev`); the
    verifiers' stamp contract (`alg-shell-stamp">build <hex><`) is untouched."""
    import verify_remote as vr

    full = "bc8e7c68957ebaf278e6bff976d3577c9545abbf18a60ed1dc13c02f461b0c57"
    commit = "f1feb7170a3c9d6e2b4f8a1c7d5e9b3f2a6c8d4e"
    html = shell.render_footer(stamp=full, commit=commit)
    # round 6: the pair is one flex item with a middle dot, so a wrap moves both together
    assert (
        f'<span class="{shell.STAMPS_CLASS}">'
        f'<span title="commit {commit}" class="alg-shell-commit">commit f1feb7170</span>'
        '<span class="alg-shell-stamp-sep" aria-hidden="true"> · </span>'
        f'<span title="build {full}" class="alg-shell-stamp">build bc8e7c68957e</span></span>'
    ) in html
    assert (
        shell.COMMIT_CHARS == 9 and ">commit f1feb7170<" in html and ">commit f1feb71<" not in html
    )
    assert vr.footer_stamp_of(html) == "bc8e7c68957e", "the stamp contract still reads the build"
    assert html.count('class="alg-shell-stamp"') == 1
    assert "alg-shell-commit" not in shell.render_footer(stamp=full, commit="dev")
    assert "alg-shell-commit" not in shell.render_footer(stamp=full, commit="")
    # the default reads the staged `.git_sha` next to the package, or `dev`
    (tmp_path / ".git_sha").write_text(commit + "\n")
    assert shell.git_sha(tmp_path / ".git_sha") == commit
    assert shell.git_sha(tmp_path / "missing") == "dev"
    rules = _rules(shell.SHELL_CSS)
    assert rules[("alg-shell-commit", "")]["white-space"] == "nowrap"
    pair = rules[(shell.STAMPS_CLASS, "")]
    assert pair["display"] == "inline-flex" and pair["white-space"] == "nowrap"
    assert pair["margin-left"] == "auto", "the pair keeps the right edge when it wraps"
    assert shell.STAMPS_CLASS not in shell.render_footer(stamp=full, commit="dev")
    _assert_clean_copy(html)


# ------------------------------------------------ head scripts: the strip and the dropdown


def test_tab_strip_script_marks_the_edges_and_lets_one_tap_select_a_clipped_tab():
    """Round 3 at 375 px: a tap on the half-visible tab at the right edge scrolled the strip
    (scrollLeft 4 -> 184) and selected nothing, and the strip had no edge affordance
    (`maskImage: none`). The script writes the edge state the sheet fades on, holds its own
    focus reveal for the length of a pointer gesture, and arms a tap so the selection lands."""
    from algenta_spaces import css

    strip = shell.TABSTRIP_SCRIPT
    assert (
        f"var EDGE = '{css.STRIP_EDGE_ATTR}';" in strip and css.STRIP_EDGE_ATTR == "data-alg-scroll"
    )
    for value in css.STRIP_EDGE_VALUES:
        assert f"'{value}'" in strip, value
    # the state is read from the first and last visible tab against the wrapper's box: the snap
    # points park scrollLeft at the 4 px padding and the tablist's end padding keeps it short
    # of its maximum, so a scrollLeft threshold read `middle` at rest
    assert "scrollLeft <= 1" not in strip and "max - 1" not in strip
    assert "shown[0].getBoundingClientRect().left < box.left - 1" in strip
    assert "shown[shown.length - 1].getBoundingClientRect().right > box.right + 1" in strip
    assert "if (tabs[i].getBoundingClientRect().width > 0) { shown.push(tabs[i]); }" in strip, (
        "the tabs Gradio folds into its hidden overflow menu do not count"
    )
    assert "wrap.setAttribute(EDGE, value)" in strip
    assert (
        "wrap.addEventListener('scroll', function () { markEdge(wrap); }, {passive: true});"
        in strip
    ), "scroll does not bubble: a listener on each wrapper as it appears"
    assert "if (wired.indexOf(wrap) !== -1) { return; }" in strip, "wired once"
    # a pointer gesture: the reveal stands down, a tap arms the tab, a swipe never selects
    assert f"var SLOP = {shell.TAP_SLOP_PX};" in strip and shell.TAP_SLOP_PX == 8
    assert f"var GESTURE_MS = {shell.GESTURE_MS};" in strip and 500 <= shell.GESTURE_MS <= 1000
    assert (
        "addEventListener('pointerdown'" in strip
        and "gestureUntil = Date.now() + GESTURE_MS" in strip
    )
    assert "Date.now() >= gestureUntil) { reveal(tab); }" in strip, "keyboard focus still reveals"
    assert (
        "addEventListener('pointerup'" in strip
        and "if (moved === false) { arm(gesture.tab); }" in strip
    )
    assert "addEventListener('pointercancel'" in strip
    assert "if (tabOf(event.target) === tab) { return; }" in strip, "a click that lands is Gradio's"
    assert "event.stopImmediatePropagation(); event.preventDefault();" in strip
    assert "if (tab.getAttribute('aria-selected') !== 'true') { tab.click(); }" in strip, (
        "an already selected tab is never clicked twice"
    )
    assert "event.isTrusted === false) { return; }" in strip, "the script's own click passes"
    assert "!" not in strip.replace("!==", ""), "no exclamation mark (copy lint)"


def test_dropdown_close_script_closes_what_gradio_leaves_open_without_touching_the_value():
    """Round 3: Tab out of an open dropdown left `aria-expanded="true"` and the listbox on the
    page 20/20 (five dropdowns, Tab and Shift+Tab, light and dark) with focus gone, and Escape
    from there reached nothing. The script dispatches the Escape keydown Gradio's own handler
    closes on — the one path that changes no value — to every open list that has no focus."""
    from algenta_spaces import css

    script = shell.DROPDOWN_CLOSE_SCRIPT
    assert f"var BOX = '{css.COMBOBOX}';" in script and css.COMBOBOX == 'input[role="combobox"]'
    assert "var OPEN = BOX + '[aria-expanded=\"true\"]';" in script
    assert "new KeyboardEvent('keydown'" in script and "key: 'Escape'" in script
    assert "bubbles: true, cancelable: true" in script
    assert "if (boxes[i] !== document.activeElement) { escape(boxes[i]); }" in script, (
        "a list open under the focused input is Gradio's to close"
    )
    assert "addEventListener('focusout'" in script, "focus leaving a combobox"
    assert "attributeFilter: ['aria-expanded']});" in script, "the reopen after Tab"
    # Codna review on #1150: style changes are read on the placed panel alone — its own observer,
    # never the page-wide one — and a panel is placed again at most eight times per opening
    assert "attributeFilter: ['aria-expanded', 'style']" not in script
    assert "var panelWatch = new MutationObserver(keepPlaced);" in script
    assert "panelWatch.observe(panel, {attributes: true, attributeFilter: ['style']});" in script
    assert "placements < 8" in script and "panelWatch.disconnect();" in script
    assert "event.key === 'Escape' && event.isTrusted" in script, "Escape from anywhere"
    # Tab out of the input landed on the listbox itself (a keyboard-focusable scroller) and fell
    # to <body> when the list closed: every listbox is taken out of the tab order as it appears
    assert f"var LIST = '{css.LISTBOX}';" in script and css.LISTBOX == 'ul[role="listbox"]'
    assert "lists[i].setAttribute('tabindex', '-1')" in script
    assert (
        "if (record.type === 'childList')" in script and "if (added) { unfocusable(); }" in script
    )
    assert "childList: true, subtree: true, attributes: true" in script
    assert "window.setTimeout(function () { queued = false; closeUnfocused(); }, 0);" in script
    for forbidden in (".value", "dispatch('change'", "dispatch('input'", "click()"):
        assert forbidden not in script, f"the script never writes a value: {forbidden}"
    assert "!" not in script.replace("!==", ""), "no exclamation mark (copy lint)"
    assert script.startswith("(function () {") and script.endswith(" })();")


# --------------------------------------------- header pills: the whole text, human words


def test_badge_carries_its_whole_text_and_wraps_into_a_tag_instead_of_truncating():
    """Round 3 at 375 px: `0 of 19 kernel families · this con…` — the count the pill exists to
    state, cut by an ellipsis. A pill is one line when it fits; when it needs two lines the head
    script marks it (`CHIP_WRAP_ATTR`, from its line boxes) and the sheet draws a 12 px tag,
    left-aligned, 50 px tall for two lines — never an ellipsis, never a `title` to hover for."""
    html = shell.render_header(
        "Fine", "fine", ['Hub kernels · "Linux" & macOS', ("19 families warm in 2.0 s", "ok")]
    )
    assert (
        '<span class="alg-shell-badge">Hub kernels · &quot;Linux&quot; &amp; macOS</span>'
    ) in html
    assert (
        '<span class="alg-shell-badge alg-shell-badge-ok">19 families warm in 2.0 s</span>' in html
    )
    assert "title=" not in html[html.index("alg-shell-badges") :].split("<nav", 1)[0], (
        "nothing is truncated, so nothing hides behind a title"
    )
    rules = _rules(shell.SHELL_CSS)
    badge = rules[("alg-shell-badge", "")]
    assert "white-space" not in badge and "text-overflow" not in badge and "overflow" not in badge
    assert badge["overflow-wrap"] == "anywhere" and badge["max-width"] == "100%"
    assert badge["display"] == "inline-block" and badge["border-radius"] == "var(--alg-radius-pill)"
    assert badge["padding"] == "4px 12px"
    line = next(
        ln
        for ln in shell.SHELL_CSS.splitlines()
        if ln.startswith(".alg-shell-badge" * 4 + f"[{shell.CHIP_WRAP_ATTR}] {{")
    )
    assert "border-radius: var(--alg-radius-card)" in line and "text-align: left" in line
    assert "padding: 8px 12px" in line, "two 16 px lines + 16 px + the hairlines = 50 px"
    row = rules[("alg-shell-badges", "")]
    assert row["align-items"] == "center" and row["flex-wrap"] == "wrap"
    assert shell.CHIP_WRAP_ATTR == "data-alg-wrap"


def test_machine_token_names_what_is_not_copy():
    assert (
        shell.machine_token("Hub kernels · torch-universal, torch25-cpu-aarch64-darwin")
        == "torch-universal"
    )
    assert shell.machine_token("built for torch29-cxx11-cpu-x86_64-linux") == (
        "torch29-cxx11-cpu-x86_64-linux"
    )
    assert shell.machine_token("the Space secret ALGENTA_API_KEY turns it on") == "ALGENTA_API_KEY"
    assert shell.machine_token("ab_testing.z_test_proportions · successes_a 50") == "ab_testing"
    assert shell.machine_token("algenta-stats@ac35ffe") == "@ac35ffe"
    for human in (
        "19 families warm in 2.0 s",
        "Hub kernels · Linux x86-64 and macOS arm64",
        "CPU upgrade · 8 vCPU",
        "Mojo kernels running on this machine. Race them against Python.",
        "measured 2026-09-22 14:02 UTC",
    ):
        assert shell.machine_token(human) is None, human


def test_headline_count_is_its_own_gradient_display_line():
    """Round 11 (owner): "6,040 is huge — must be visible right away", "AI-ish gradient". A
    headline that opens with a number renders the number as a display line in the accent
    gradient above the words; a headline without one is plain text; the copy check sees the
    whole sentence either way."""
    html = shell.render_header(
        "6,040 compiled Mojo kernels", "Mojo kernels running on this machine."
    )
    assert (
        f'<span class="alg-shell-count alg-accent-text" style="{shell.COUNT_STYLE}">6,040</span>'
        in html
    )
    assert "var(--alg-accent-from)" in shell.COUNT_STYLE and "#" not in shell.COUNT_STYLE
    assert '<span class="alg-shell-title-text">compiled Mojo kernels</span>' in html
    plain = shell.render_header("Compiled Mojo kernels", "Mojo kernels running on this machine.")
    assert "alg-shell-count" not in plain and ">Compiled Mojo kernels</h1>" in plain
    count_rule = _rules(shell.SHELL_CSS)[("alg-shell-count", "")]
    assert count_rule["font-size"] == "var(--alg-count-size)" and count_rule["display"] == "block"
    assert "tabular-nums" in count_rule["font-variant-numeric"]
    assert design.TYPE_SCALE["count"] == (64, 64, "-0.03em", 600)
    assert "background-clip: text" in shell.COUNT_STYLE
    assert f"--alg-accent-gradient: {design.ACCENT_GRADIENT};" in design.build_tokens_css()
    assert design.ACCENT_GRADIENT == "linear-gradient(90deg, #7C5CFA, #3B82F6)"
