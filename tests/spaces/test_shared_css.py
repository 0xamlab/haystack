"""algenta_spaces.css — the rule builder, the Gradio chrome sheet and the CodeMirror sheet."""

from __future__ import annotations

import re

from _rules import _assert_four_class_selectors, _assert_stylesheet_discipline, _contrast
from algenta_spaces import css, design

ROOT = f".{css.PAGE_CLASS}" * 4


def _line(sheet: str, prefix: str) -> str:
    matches = [ln for ln in sheet.splitlines() if ln.strip().startswith(prefix)]
    assert matches, prefix
    return matches[0]


def test_chrome_and_code_sheets_obey_the_discipline():
    assert css.PAGE_CLASS == "alg-page"
    for sheet in (css.CHROME_CSS, css.CODE_CSS):
        _assert_stylesheet_discipline(sheet)
        _assert_four_class_selectors(sheet)
        assert ".svelte-" not in sheet and "!important" not in sheet
        # no Gradio class name is selected: only elements, roles, aria and data attributes
        for selector in re.findall(r"^\s*(\S.*?) \{", sheet, re.M):
            classes = set(re.findall(r"\.([A-Za-z][\w-]*)", selector))
            assert classes <= {css.PAGE_CLASS, css.DISCLOSURE_CLASS, css.SNIPPET_EDITOR_CLASS} | {
                c for c in classes if c.startswith("cm-")
            }, selector
    assert css.page_rule("color: red;", suffix="button") == f"{ROOT} button {{ color: red; }}"
    assert css.DISCLOSURE_CLASS == "alg-disclosure"
    assert css.SNIPPET_EDITOR_CLASS == "alg-snippet-editor"
    assert css.PHONE_MAX_WIDTH == design.PHONE_MAX_WIDTH == 767


def _media_block(sheet: str, header: str) -> str:
    start = sheet.index(f"{header} {{\n")
    return sheet[start : sheet.index("\n}", start)]


def test_open_dropdown_rows_are_44px_rounded_and_themed():
    sheet = css.CHROME_CSS
    panel = _line(sheet, f"{ROOT} div:has(> {css.LISTBOX}) {{")
    assert "background: var(--alg-surface)" in panel
    assert "border: 1px solid var(--alg-hairline)" in panel
    assert "border-radius: var(--alg-radius-input)" in panel and "padding: 4px" in panel
    option = _line(sheet, f"{ROOT} {css.OPTION} {{")
    assert "min-height: var(--alg-target)" in option
    assert "border-radius: var(--alg-radius-input)" in option
    assert (
        "font-size: var(--alg-body-size)" in option
        and "line-height: var(--alg-body-line)" in option
    )
    assert "font-family: var(--alg-font)" in option and "color: var(--alg-text)" in option
    assert "max-width: 100%" in option, "Gradio's inline width never overflows the padded panel"
    assert f"{ROOT} {css.OPTION}:hover {{ background: var(--alg-surface-hover); }}" in sheet
    assert (
        f'{ROOT} {css.OPTION}[aria-selected="true"] {{ background: var(--alg-surface-2); }}'
        in sheet
    )
    check = _line(sheet, f"{ROOT} {css.OPTION} > span {{")
    assert "var(--alg-accent-text" in check


def test_accordion_is_a_44px_row_with_a_turning_chevron_and_no_stock_glyph():
    sheet = css.CHROME_CSS
    disclosure = f".{css.DISCLOSURE_CLASS}" * 4
    assert (
        f"{disclosure} {{ padding: 0; border: 0; background: transparent; box-shadow: none; }}"
        in sheet
    ), "the block is bare; the button carries the frame"
    header = _line(sheet, f"{disclosure} > button {{")
    # the header button is the 44 px target and carries the hairline itself (round 9)
    assert "min-height: var(--alg-target)" in header and " padding: 0 16px; margin: 0;" in header
    assert "border: 1px solid var(--alg-hairline)" in header and "box-sizing: border-box" in header
    assert "justify-content: space-between" in header
    assert f"{disclosure} > button > span + span {{ display: none; }}" in sheet  # the stock ▼
    chevron = _line(sheet, f"{disclosure} > button::after {{")
    assert "width: 20px; height: 20px" in chevron
    assert "background: currentColor" in chevron and "mask: url(" in chevron
    assert "<path d='M7.5 4.5l5.5 5.5-5.5 5.5'/>" in chevron
    assert (
        "transform: rotate(0deg)" in chevron
        and "transition: transform var(--alg-motion)" in chevron
    )
    assert "color: var(--alg-text-2)" in chevron
    assert f"{disclosure} > {css.OPEN_HEADER}::after {{ transform: rotate(90deg); }}" in sheet
    assert f"{disclosure} > button:hover::after {{ color: var(--alg-text); }}" in sheet
    content = _line(sheet, f"{disclosure} > {css.ACCORDION_CONTENT} {{")
    assert "padding: 0 16px 16px" in content and "border-top: 0" in content  # the frame continues
    reduced = _media_block(sheet, "@media (prefers-reduced-motion: reduce)")
    assert f"{disclosure} > button::after {{ transition: none; }}" in reduced
    assert 150 <= design.MOTION_MS <= 200


def test_phone_tab_strip_scrolls_every_tab_into_reach():
    sheet = css.CHROME_CSS
    phone = _media_block(sheet, f"@media (width <= {css.PHONE_MAX_WIDTH}px)")
    wrapper = next(ln for ln in phone.splitlines() if f"div:has(> {css.TABLIST}) {{" in ln)
    assert "overflow-x: auto" in wrapper and "scrollbar-width: none" in wrapper
    assert "scroll-snap-type: x proximity" in wrapper and "height: auto" in wrapper
    assert "margin: 0 -4px; padding: 4px 4px 8px" in wrapper, "room for the 2 px focus ring"
    assert f"{ROOT} div:has(> {css.TABLIST})::-webkit-scrollbar {{ display: none; }}" in phone
    strip = next(ln for ln in phone.splitlines() if f" {css.TABLIST} {{" in ln)
    assert "width: max-content; min-width: 100%" in strip, (
        "Gradio keeps every tab when the strip's clientWidth holds their measured sum"
    )
    tab = next(ln for ln in phone.splitlines() if f" {css.TAB} {{" in ln)
    assert "scroll-snap-align: start" in tab and "white-space: nowrap" in tab
    assert f"{ROOT} span:has(> {css.MORE_TABS}) {{ display: none; }}" in phone
    # the 44 px tab and strip minimums hold at every width
    assert "min-height: var(--alg-target)" in _line(sheet, f"{ROOT} {css.TAB} {{")


def test_code_sheet_hides_the_stock_label_the_gutter_and_the_empty_snippet_editor():
    """Round 3: every gr.Code kept Gradio's `</>` block label ('Snippet', 'Kernel snippet',
    'Engine JSON') and a 27 px line-number gutter. The tabs pass `show_label=False` and
    `show_line_numbers=False`; the sheet is the fallback that holds for a block that forgot."""
    sheet = css.CODE_CSS
    assert css.CODE_BLOCK_LABEL == (
        'div:has(> div > div > .cm-editor) > label[data-testid="block-label"]'
    ), "reached from the block that holds the editor, never from a Gradio class"
    assert f"{ROOT} {css.CODE_BLOCK_LABEL} {{ display: none; }}" in sheet
    # `.cm-gutters` is the one gutter element whose display the base theme does not force
    assert css.GUTTERS == ".cm-gutters"
    assert f"{ROOT} {css.GUTTERS} {{ display: none; }}" in sheet
    assert ".cm-foldGutter" not in sheet and "border-right" not in sheet, (
        "no gutter is styled: the whole container is gone"
    )
    assert f"{ROOT} .cm-line {{ padding: 0 12px; }}" in sheet, "the content keeps its inset"
    editor = f".{css.SNIPPET_EDITOR_CLASS}" * 4
    assert f"{editor}:has({css.EMPTY_EDITOR}) {{ display: none; }}" in sheet
    assert css.EMPTY_EDITOR == ".cm-content > .cm-line:only-child > br:only-child"
    # the editor itself keeps the design: surface-2, radius 8, 13/20 mono
    assert "border-radius: var(--alg-radius-input)" in _line(sheet, f"{ROOT} .cm-editor {{")
    assert design.RADII["input"] == "8px" and design.TYPE_SCALE["mono"] == (13, 20, "0", 400)


def test_phone_tab_strip_fades_the_edge_that_hides_more_tabs():
    """Round 3 at 375 px: `maskImage: none` — a clipped strip looked like it ended at 'LLM ke'.
    The head script writes the edge state; the sheet fades only the edge with more behind it."""
    sheet = css.CHROME_CSS
    phone = _media_block(sheet, f"@media (width <= {css.PHONE_MAX_WIDTH}px)")
    wrap = f"{ROOT} div:has(> {css.TABLIST})"
    assert css.STRIP_EDGE_ATTR == "data-alg-scroll"
    assert css.STRIP_EDGE_VALUES == ("start", "middle", "end", "none")
    assert css.STRIP_FADE == "var(--alg-space-32)", "the fade is a spacing token"
    start = _line(phone, f'{wrap}[{css.STRIP_EDGE_ATTR}="start"] {{')
    assert "linear-gradient(to right, black calc(100% - var(--alg-space-32)), transparent)" in start
    end = _line(phone, f'{wrap}[{css.STRIP_EDGE_ATTR}="end"] {{')
    assert "linear-gradient(to right, transparent, black var(--alg-space-32))" in end
    middle = _line(phone, f'{wrap}[{css.STRIP_EDGE_ATTR}="middle"] {{')
    assert (
        "linear-gradient(to right, transparent, black var(--alg-space-32),"
        " black calc(100% - var(--alg-space-32)), transparent)"
    ) in middle
    for line in (start, end, middle):
        assert "-webkit-mask-image:" in line and " mask-image:" in line
        assert "#" not in line, "a mask is alpha: black and transparent, no colour"
    assert f'[{css.STRIP_EDGE_ATTR}="none"]' not in sheet, "a strip that fits is untouched"
    # the fade never reaches the desktop strip
    outside = sheet.split(f"@media (width <= {css.PHONE_MAX_WIDTH}px)")[0]
    assert "mask-image" not in outside


def test_layout_sheet_stretches_the_results_column_to_the_controls():
    """Round 3: 469 px of void under the LLM controls after a run, 474 px under the Governed
    receipt — Gradio's row is `align-items: flex-start`. The classes for the tab owners."""
    sheet = css.LAYOUT_CSS
    _assert_stylesheet_discipline(sheet)
    _assert_four_class_selectors(sheet)
    assert (css.COLS_CLASS, css.CONTROLS_CLASS, css.RESULTS_CLASS, css.FILL_CLASS) == (
        "alg-cols",
        "alg-col-controls",
        "alg-col-results",
        "alg-fill",
    )
    cols = f".{css.COLS_CLASS}" * 4
    assert f"{cols} {{ align-items: stretch; }}" in sheet
    results = f".{css.RESULTS_CLASS}" * 4
    assert f"{results} {{ display: flex; flex-direction: column; align-self: stretch; }}" in sheet
    fill = f".{css.FILL_CLASS}" * 4
    grow = "display: flex; flex-direction: column; flex: 1 1 auto;"
    # block > container > prose, then the payload's top-level element
    for suffix in ("", " > div", " > div > div"):
        assert f"{fill}{suffix} {{ {grow} }}" in sheet, suffix
    assert f"{fill} > * {{ flex: 1 1 auto; }}" in sheet
    assert "min-height" not in sheet and "height:" not in sheet, (
        "the column's height is the row's; nothing is pinned"
    )
    assert ".row" not in sheet and ".column" not in sheet and ".block" not in sheet
    assert css.LAYOUT_CSS.rstrip("\n") in design.BASE_CSS, "fleet_css ships it"


def test_layout_contract_never_stretches_the_controls_or_a_state_card():
    """The final review (1440 × 900, Governed): opening Engine responses grew the row to
    5,051 px and every controls block with it — Run 49 → 459 px, a slider block 122 → 532 px —
    and at rest the EMPTY card was 894 px around 198 px of content. The contract: the results
    column may grow to the controls' height and never below; the controls keep their natural
    height; an empty, quiet or loading card never grows past its content."""
    sheet = css.LAYOUT_CSS
    cols = f".{css.COLS_CLASS}" * 4
    controls = f".{css.CONTROLS_CLASS}" * 4
    results = f".{css.RESULTS_CLASS}" * 4
    fill = f".{css.FILL_CLASS}" * 4
    # controls: the class, and any row child that is not the results column (a column that
    # forgot the class is still safe) — Gradio's `.column { align-self: stretch }` is (0,1,0)
    assert f"{controls} {{ align-self: flex-start; }}" in sheet
    assert f"{cols} > :not(.{css.RESULTS_CLASS}) {{ align-self: flex-start; }}" in sheet
    assert "align-self: stretch" in next(
        ln for ln in sheet.splitlines() if ln.startswith(results + " {")
    )
    # the fill block alone takes the column's slack; a disclosure or note beside it does not
    assert f"{results} > * {{ flex: 0 0 auto; }}" in sheet
    assert f"{results} > .{css.FILL_CLASS} {{ flex: 1 1 auto; }}" in sheet
    # a state is not a result: it is as tall as its content, the slack is the page's
    assert css.UNFILLED_CARD_CLASSES == ("alg-card-empty", "alg-card-quiet", "alg-card-loading")
    assert (
        f"{fill} > :is(.alg-card-empty, .alg-card-quiet, .alg-card-loading) {{ flex: 0 0 auto; }}"
        in sheet
    )
    grow_rule = sheet.index(f"{fill} > * {{ flex: 1 1 auto; }}")
    assert sheet.index(f"{fill} > :is(") > grow_rule, "the exception follows the rule it narrows"
    # nothing selects a Gradio class, and no rule reaches into a control
    assert "button" not in sheet and ".form" not in sheet and "equal-height" not in sheet
    # the capped code block's names, spelled once here for the tabs
    assert (css.CODE_CAPPED_CLASS, css.CODE_SCROLL_CLASS) == ("alg-code-capped", "alg-code-scroll")
    assert css.CODE_LINES_VAR == "--alg-code-lines" and css.CODE_LINES_DEFAULT == 24


def test_chrome_sheet_sizes_every_control_to_the_target():
    sheet = css.CHROME_CSS
    for suffix in (
        "button",
        'button[role="tab"]',
        '[role="tablist"]',
        'button[aria-label="More tabs"]',
        "textarea",
        'input[type="text"]',
        'input[type="range"]',
        'label:has(> input[type="radio"])',
        'label:has(> input[type="checkbox"])',
        f'input[type="number"]:not({css.SLIDER_VALUE_INPUT})',
        f"div:has(> div > div > {css.COMBOBOX})",
    ):
        assert "min-height: var(--alg-target)" in _line(sheet, f"{ROOT} {suffix} {{"), suffix
    # the combobox: the bordered wrapper is the target; the box inside it and the input are
    # two pixels shorter so the 1 px borders land inside 44 px (round 6: a 46 px dropdown)
    for suffix in (f"div:has(> div > {css.COMBOBOX})", css.COMBOBOX):
        assert css._INNER_TARGET in _line(sheet, f"{ROOT} {suffix} {{"), suffix
    assert css._INNER_TARGET == "min-height: calc(var(--alg-target) - 2px);"
    # every control shares one 20 px line and no vertical padding: 44 px on the grid
    for suffix in ("button", 'button[role="tab"]', 'label:has(> input[type="radio"])'):
        assert "line-height: 20px" in _line(sheet, f"{ROOT} {suffix} {{"), suffix
    assert "padding-top: 0; padding-bottom: 0" in _line(sheet, f"{ROOT} button {{")
    # the slider: a 44 px value box that is never clipped, no reset button
    box = _line(sheet, f"{ROOT} div:has(> {css.SLIDER_VALUE_INPUT}) {{")
    assert "overflow: visible" in box and "height: auto" in box
    assert "min-height: var(--alg-target)" in box
    value = _line(sheet, f"{ROOT} {css.SLIDER_VALUE_INPUT} {{")
    assert "min-height: var(--alg-target)" in value
    assert "font-family: var(--alg-font-mono)" in value and "tabular-nums" in value
    assert "text-align: right" in value
    assert f"{ROOT} {css.SLIDER_RESET_BUTTON} {{ display: none; }}" in sheet
    # checkbox and radio boxes are 20 px
    assert "width: 20px; height: 20px" in _line(
        sheet, f'{ROOT} :is(input[type="checkbox"], input[type="radio"]) {{'
    )


def test_chrome_sheet_hides_stock_progress_and_icon_panels():
    sheet = css.CHROME_CSS
    assert f"{ROOT} {css.STATUS_TRACKER} {{ display: none; }}" in sheet
    panels = _line(sheet, f'{ROOT} :is(div:has(> button[aria-label="Copy"])')
    for label in css.STOCK_ICON_LABELS:
        assert f'div:has(> button[aria-label="{label}"])' in panels
    assert panels.endswith("{ display: none; }")


def test_disabled_and_focus_states_are_designed_not_faded():
    sheet = css.CHROME_CSS
    disabled = _line(sheet, f"{ROOT} button:disabled {{")
    assert "opacity: 1" in disabled and "filter: none" in disabled
    assert "background: var(--alg-surface-2)" in disabled
    assert "color: var(--alg-text-2)" in disabled
    assert "border-color: var(--alg-hairline)" in disabled
    focus = _line(sheet, f'{ROOT} :is(button, a, summary, [role="tab"]):focus-visible {{')
    assert "outline: 2px solid var(--alg-accent-to)" in focus and "outline-offset: 2px" in focus
    boxes = _line(
        sheet,
        f'{ROOT} :is(input[type="checkbox"], input[type="radio"], input[type="range"]):focus-visible {{',
    )
    assert "outline: 2px solid var(--alg-accent-to)" in boxes
    button = _line(sheet, f"{ROOT} button {{")
    assert "transition: background-color var(--alg-motion)" in button
    assert "outline-color" not in button  # rings appear instantly
    assert "prefers-reduced-motion: reduce" in sheet


def test_code_sheet_maps_every_role_in_both_modes_to_aa_colours():
    sheet = css.CODE_CSS
    assert f"{ROOT} .cm-content span {{ color: inherit; }}" in sheet
    light_all: set[str] = set()
    dark_all: set[str] = set()
    for role, (light, dark) in css.CODE_TOKEN_CLASSES.items():
        line = next(
            ln
            for ln in sheet.splitlines()
            if ".cm-content :is(" in ln and f"span.{light[0]}," in ln
        )
        assert line.endswith(f"{{ {css.CODE_ROLE_STYLE[role]} }}"), role
        for cls in light + dark:
            assert f"span.{cls}" in line, (role, cls)
        light_all |= set(light)
        dark_all |= set(dark)
    # the classes the live snippet used on 2026-09-22 (gradio 6.28.0) are all mapped
    assert {"ͼ1q", "ͼ1s", "ͼ21", "ͼ23", "ͼ28", "ͼ1w", "ͼ2c", "ͼ1t", "ͼ1z"} <= light_all
    assert {"ͼp", "ͼr", "ͼ10", "ͼ12", "ͼ17", "ͼv", "ͼ1b", "ͼs", "ͼy"} <= dark_all
    assert not light_all & dark_all
    # every coloured class of basicLight (35 minus strikethrough) and basicDark (36 minus it)
    assert len(light_all) == 34 and len(dark_all) == 35
    used = set(re.findall(r"var\(--alg-([\w-]+)\)", " ".join(css.CODE_ROLE_STYLE.values())))
    assert used == {"accent-text", "ok", "text", "text-2", "err"}
    for mode in (0, 1):
        tokens = {n: v[mode] for n, v in {**design.COLOR_TOKENS, **design.EXTENSION_TOKENS}.items()}
        for name in used:
            for surface in ("surface", "surface-2"):
                assert _contrast(tokens[name], tokens[surface]) >= 4.5, (mode, name, surface)
    editor = _line(sheet, f"{ROOT} .cm-editor {{")
    assert "background: var(--alg-surface-2)" in editor
    content = _line(sheet, f"{ROOT} .cm-content {{")
    assert "font-family: var(--alg-font-mono)" in content
    assert (
        "font-size: var(--alg-mono-size)" in content
        and "line-height: var(--alg-mono-line)" in content
    )
    assert "outline: 2px solid var(--alg-accent-to)" in _line(
        sheet, f"{ROOT} .cm-editor.cm-focused {{"
    )
