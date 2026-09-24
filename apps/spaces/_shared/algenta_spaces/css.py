"""The one way the fleet writes CSS for its own gr.HTML markup, plus the Gradio chrome sheet.

`rule()` repeats the class four times so the selector reaches specificity
(0,4,0) and beats Gradio's scoped resets (`.gradio-container-<version> .prose h1`
is (0,3,1)) on every frontend without `!important` or version-coupled selectors —
the discipline the canonical shell established. Nothing here selects a Gradio
class: where a rule has to reach a Gradio control it hangs off the page root
(`PAGE_CLASS`, the `gr.Column(elem_classes=[PAGE_CLASS])` every Space wraps its
content in) and finds the control by element, role, aria or data attribute.

`CHROME_CSS` — the Gradio controls, sized and coloured by the design system
----------------------------------------------------------------------------
Shipped by `design.BASE_CSS`, so `fleet_css()` carries it. It owns:

* the 44 px minimum on every button (run, chip, tab, accordion header, "More
  tabs"), on standalone number inputs, text areas, the dropdown row, the radio
  and checkbox label rows and the range input; the tab strip grows with its
  buttons instead of clipping them at 32 px;
* the designed disabled button (muted surface, muted text, hairline; no opacity
  or grayscale) and a 2 px accent focus ring, 2 px out, on buttons, links, tabs
  and summaries; inputs keep the theme's 2 px accent box-shadow ring;
* the slider header: a 44 px value box in the mono face with tabular numerals,
  right-aligned, never clipped, and the stock reset button hidden;
* the stock icon panels hidden (Copy / Download on Code and Textbox, Copy table
  data / Fullscreen on Dataframe): the tabs pass `buttons=[]` and
  `show_copy_button=False` and offer a 44 px Copy chip instead;
* the stock progress chrome hidden globally — `[data-testid="status-tracker"]`
  is the element that carries the spinner, the "processing | 0.1s" text, the
  eta bar and the pulsing `generating` border. The designed alternative is
  `cards.loading(title, detail)` and `cards.chip("loading")`, which a handler
  returns first (a generator's first yield) and replaces with the result;
* 20 px checkbox and radio boxes, and the option-label pills at 44 px through
  the theme's padding variables;
* the open dropdown: the listbox panel (`ul[role="listbox"]` and the panel
  around it) on `surface` with a hairline, 8 px radius and 4 px padding, every
  option (`li[role="option"]`) a 44 px row in the body face with an 8 px radius,
  `surface-hover` on hover and `surface-2` when selected — Gradio's stock rows
  measured 35.6 px, 14 px, no radius, no border;
* the accordion (`alg-disclosure`, the class every `gr.Accordion` carries): no
  block padding of its own, so the header is one 44 px row inset 16 px; the
  stock `▼` glyph hidden and a 20 px outline chevron drawn on the header's
  `::after` (a masked SVG in `currentColor`), pointing right when collapsed and
  turning down over `--alg-motion` when `aria-expanded="true"` — the attribute
  `shell.DISCLOSURE_SCRIPT` mirrors from the content's visibility, since Gradio
  sets none; the content gets 16 px below;
* the phone tab strip (below `PHONE_MAX_WIDTH`): Gradio renders only the tabs
  whose measured widths fit the tablist's `clientWidth` and folds the rest into
  a "More tabs" menu, so the tablist is sized `max-content` (its clientWidth is
  then the whole strip and Gradio keeps every tab) inside a wrapper that scrolls
  horizontally with no scrollbar chrome, snap points on every tab and 4 px of
  room for the focus ring; the overflow button is hidden because nothing
  overflows. `shell.TABSTRIP_SCRIPT` scrolls the selected tab into view and
  writes `STRIP_EDGE_ATTR` (`data-alg-scroll` = `start` / `middle` / `end` /
  `none`) on the wrapper from its scroll position; this sheet reads it and fades
  the edge that hides more tabs over `STRIP_FADE` (32 px, a spacing token) with a
  mask — the strip says there is more where there is more, and never fades the
  first tab at the start or the last at the end.

What an app's own CSS must drop once it loads this sheet (the flagship's
`APP_CSS` still carries them and wins ties by loading last): its
`input[type="number"]`, `textarea`, `input[type="range"]` and
`label:has(> input[type="radio" | "checkbox"])` minimum-height rules, the
`label[data-testid="block-label"]` colours (the theme pins them now), the
`button[role="tab"]` and `button[aria-label="More tabs"]` sizing and the
`alg-run` / `alg-chip-btn` / `alg-disclosure > button` minimums. (Gradio 6.28's
`gr.Slider` takes no `show_reset_button` argument — passing one raises — so the
sheet hides the reset button by its aria-label, `SLIDER_RESET_BUTTON`.)

The one Gradio class this module selects is its own `alg-disclosure`; every
other rule reaches a control by element, role, aria or data attribute.

`CODE_CSS` — gr.Code (CodeMirror 6) in the design system
--------------------------------------------------------
Gradio 6.28 ships two highlight styles (basicLight and basicDark) whose token
classes are `StyleModule`-generated (`.ͼ1q`, `.ͼp`, …); the names are fixed by
the bundle, so `CODE_TOKEN_CLASSES` maps each semantic role to its light and dark
classes, read from the live DOM on 2026-09-22 (only the two strikethrough classes,
which carry no colour of their own, are left to the catch-all). Every token colour is a design
token at 4.5:1 or better on `surface` and `surface-2`: keywords in `accent-text`,
strings in `ok`, comments in `text-2` (italic), punctuation and operators in
`text-2`, names and literals in `text`. A catch-all sets every token span to the
body colour first, so a class the map does not know renders legibly rather
than in CodeMirror's default. The editor sits on `surface-2` in the mono face at
13/20, radius 8, with a 2 px accent focus ring.

No stock chrome on a code block. Gradio draws a block label with a `</>` icon
above every `gr.Code` (`label[data-testid="block-label"]`, "Snippet", "Kernel
snippet", "Engine JSON" — round 3) and CodeMirror a line-number gutter beside
every document ("1–26" beside a snippet nobody edits by line). The tabs pass
`show_label=False` and `show_line_numbers=False` and put the words in their own
caption (`cards.snippet_block` for HTML payloads, an `alg-editor-note` or the
disclosure title for a `gr.Code`); this sheet is the fallback that holds for a
block that forgot: the code block's own label (`CODE_BLOCK_LABEL`, reached from
the block that holds a `.cm-editor`) is hidden, and the gutter container
(`GUTTERS`, `.cm-gutters` — the only CodeMirror gutter element whose `display`
is not forced by the base theme) is hidden with it, fold markers included. The
content keeps its 12 px inset (`.cm-line`).

Editors never render empty. A `gr.Code` that shows a snippet or a result
(read-only, filled by a handler) passes `elem_classes=[SNIPPET_EDITOR_CLASS]`
(`alg-snippet-editor`): while its document is CodeMirror's empty line
(`.cm-line` holding a lone `<br>`) the block is `display: none`, and the first
value the handler sends makes the selector stop matching, so the editor appears
with its content — no gutter "1" and no Copy chip over nothing. An editor the
visitor types into (the Playground's JSON fields) never carries the class: it
is empty by design until they type. For a snippet in a `gr.HTML` payload,
`cards.snippet_block(code, language)` refuses empty code outright.

`LAYOUT_CSS` — the two-column contract for a tab's controls and results
-----------------------------------------------------------------------
Gradio's `gr.Row` is `align-items: flex-start` (its `unequal-height` class), so
a results column ends where its card ends and the run leaves a void under the
shorter column — 469 px under the LLM controls after a run, 474 px under the
Governed receipt (round 3, `extra/voids.json`). The first fix stretched both
columns to the row, and the final review measured the other failure: with the
Governed "Engine responses" open, a 4,386 px JSON grew the row to 5,051 px and
every block of the CONTROLS column with it (Gradio's `.column > .form > *` and
its buttons grow into slack) — the Run button 49 → 459 px, a slider block
122 → 532 px — and at rest the EMPTY card was 894 px tall around 198 px of
content (`review-shots/skeptic-apple/gov-open`, `layout/gov-*-rest`). Four
classes, on the 8-pt grid, that a tab owner puts on its own layout components,
and the contract they hold:

* `COLS_CLASS` (`alg-cols`) on the `gr.Row` (never `equal_height=True`, which
  is the same `align-items: stretch` without the rest of this contract):
  `align-items: stretch`, so the row is as tall as its tallest column and the
  results column may grow to it.
* `CONTROLS_CLASS` (`alg-col-controls`) on the controls `gr.Column`: `align-self:
  flex-start` — the controls keep their natural height whatever the results
  column does, so no slack ever reaches a button or a form. The rule also holds
  for any child of the row that is not the results column, so a controls column
  that forgot the class is still safe; the class is the documented spelling.
* `RESULTS_CLASS` (`alg-col-results`) on the results `gr.Column`: a flex column
  that stretches to the row — never shorter than the controls, as tall as its
  own content when that is taller.
* `FILL_CLASS` (`alg-fill`) on the results `gr.HTML` (`elem_classes=["alg-fill"]`
  lands on the block and on its prose wrapper alike): the block, its container
  and the payload's top-level element (`.alg-card`, `.alg-stat`, …) grow to the
  column's remaining height, so a result card is as tall as the controls beside
  it and its content stays at the top. An empty, quiet or loading card
  (`alg-card-empty`, `alg-card-quiet`, `alg-card-loading` — states, not
  results) never grows past its own content: the column's remaining height
  stays the page, not a dashed void. Every other block in the results column
  (a disclosure, a note) keeps its own height (`flex: 0 0 auto`), so the fill
  block alone takes the slack.

Below `PHONE_MAX_WIDTH` the columns stack as Gradio wraps them; the rules are
inert there. `tests/spaces/test_shared_css.py` pins the sheet and the demo page
under `fix5-shots/shared-bench-cards/` measured it on a real Gradio page at
1440 and 375 px.

`CODE_CAPPED_CLASS` (`alg-code-capped`) is the class `cards.code_block` puts on a
long snippet's `<figure>`: its `<pre>` (`alg-code-scroll`, `tabindex="0"`,
`role="region"`) shows `--alg-code-lines` lines (24 by default) and scrolls
inside, with the fleet's 2 px focus ring drawn inside its edge (the figure clips
its corners), so the scrollable region is in the tab order — the rule axe checks
as `scrollable-region-focusable`. The rules live in `cards.CARD_CSS` beside the
snippet rules; the class is named here so a tab can select it.
"""

from __future__ import annotations

from collections.abc import Mapping

REPEAT = 4
PAGE_CLASS = "alg-page"
#: The class every `gr.Accordion` in the fleet carries (`elem_classes=["alg-disclosure"]`).
DISCLOSURE_CLASS = "alg-disclosure"
#: A read-only `gr.Code` filled by a handler: hidden while its document is empty.
SNIPPET_EDITOR_CLASS = "alg-snippet-editor"
#: Below this width the tab strip scrolls and the display type steps down (design.py reads it).
PHONE_MAX_WIDTH = 767
#: The shell script marks the option panel Gradio adds for a combobox reached by Tab with this
#: attribute; the sheet keeps it from ever painting (an inline style would be rewritten by the
#: panel's own 200 ms fly transition).
ARRIVAL_ATTR = "data-alg-arrival"

# Selectors the chrome sheet needs, spelled once. None of them is a Gradio class.
SLIDER_VALUE_INPUT = 'input[type="number"][aria-label^="number input for"]'
SLIDER_RESET_BUTTON = 'button[aria-label="Reset to default value"]'
STATUS_TRACKER = '[data-testid="status-tracker"]'
COMBOBOX = 'input[role="combobox"]'
LISTBOX = 'ul[role="listbox"]'
OPTION = 'li[role="option"]'
TABLIST = '[role="tablist"]'
TAB = 'button[role="tab"]'
MORE_TABS = 'button[aria-label="More tabs"]'
ACCORDION_CONTENT = '[data-testid="accordion-content"]'
#: The header of an open accordion, once `shell.DISCLOSURE_SCRIPT` has mirrored the state.
OPEN_HEADER = 'button[aria-expanded="true"]'
#: CodeMirror's empty document: one line holding a lone `<br>`.
EMPTY_EDITOR = ".cm-content > .cm-line:only-child > br:only-child"
#: CodeMirror's gutter container: line numbers and fold markers alike. Its `display` is the one
#: the base theme does not force, so it is the element hidden.
GUTTERS = ".cm-gutters"
#: Gradio's block label (the `</>` icon and the words) on the block that holds a code editor:
#: `div.block > label[data-testid="block-label"] + div.wrap > div.codemirror-wrapper > .cm-editor`.
CODE_BLOCK_LABEL = 'div:has(> div > div > .cm-editor) > label[data-testid="block-label"]'
STOCK_ICON_LABELS: tuple[str, ...] = ("Copy", "Copy table data", "Download", "Fullscreen")
#: WebKit's native number-box stepper pseudo-elements; the sheet hides both (and Firefox's via
#: `-moz-appearance: textfield`), so a number box is a plain 44 px field.
NUMBER_SPINNERS: tuple[str, str] = ("-webkit-inner-spin-button", "-webkit-outer-spin-button")
#: Written by `shell.TABSTRIP_SCRIPT` on the strip's scrolling wrapper: `start`, `middle`, `end`
#: or `none` (the strip fits). The phone sheet fades the edge that hides more tabs.
STRIP_EDGE_ATTR = "data-alg-scroll"
STRIP_EDGE_VALUES: tuple[str, ...] = ("start", "middle", "end", "none")
#: The fade's length, a spacing token.
STRIP_FADE = "var(--alg-space-32)"
#: The two-column contract (see the module docstring): the row, the controls column, the
#: results column, the fill block.
COLS_CLASS = "alg-cols"
CONTROLS_CLASS = "alg-col-controls"
RESULTS_CLASS = "alg-col-results"
FILL_CLASS = "alg-fill"
#: The cards that are states, not results: they never grow into a column's slack.
UNFILLED_CARD_CLASSES: tuple[str, ...] = ("alg-card-empty", "alg-card-quiet", "alg-card-loading")
#: A long snippet capped to a scrolling, focusable region (`cards.code_block`, `cards.CARD_CSS`).
CODE_CAPPED_CLASS = "alg-code-capped"
CODE_SCROLL_CLASS = "alg-code-scroll"
#: The custom property that sets how many lines the capped block shows before it scrolls.
CODE_LINES_VAR = "--alg-code-lines"
CODE_LINES_DEFAULT = 24

#: A 20 px outline chevron pointing right (SF-style: 1.5 px stroke, round caps), used as a
#: mask over `currentColor` so it takes the text colour of every state.
CHEVRON_MASK = (
    "url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 20 20'"
    " fill='none' stroke='black' stroke-width='1.5' stroke-linecap='round'"
    " stroke-linejoin='round'><path d='M7.5 4.5l5.5 5.5-5.5 5.5'/></svg>\")"
)


def rule(class_name: str, declarations: str, *, suffix: str = "") -> str:
    """`.c.c.c.c<suffix> { declarations }` for one of our classes."""
    if not class_name or " " in class_name or class_name.startswith("."):
        raise ValueError(f"class_name is a bare class name: {class_name!r}")
    body = " ".join(declarations.split())
    if "!important" in body:
        raise ValueError("the fleet never uses !important")
    selector = "".join(f".{class_name}" for _ in range(REPEAT)) + suffix
    return f"{selector} {{ {body} }}"


def block(at_rule: str, *rules: str) -> str:
    """Wrap rules in an at-rule such as `@media (width <= 560px)` or `@supports (...)`."""
    inner = "\n".join(f"  {r}" for r in rules)
    return f"{at_rule} {{\n{inner}\n}}"


def stylesheet(*rules: str) -> str:
    return "\n".join(rules) + "\n"


def page_rule(declarations: str, *, suffix: str) -> str:
    """A rule on the page root reaching a Gradio control by element or attribute."""
    return rule(PAGE_CLASS, declarations, suffix=f" {suffix}")


_TARGET = "min-height: var(--alg-target);"
_RING = "outline: 2px solid var(--alg-accent-to); outline-offset: 2px;"
_BODY_TYPE = (
    "font-family: var(--alg-font); font-size: var(--alg-body-size);"
    " line-height: var(--alg-body-line);"
)
#: The type inside a 44 px control (button, tab, option pill): body size on a 20 px line, so a
#: one-line label plus no vertical padding lands exactly on the target height — on the 8-pt
#: grid (round 6: buttons rendered 48.5 px, tabs and accordion heads 46, pills 48.5, boxes 48).
_CONTROL_TYPE = "font-family: var(--alg-font); font-size: var(--alg-body-size); line-height: 20px;"
_CONTROL_BOX = f"{_TARGET} padding-top: 0; padding-bottom: 0; box-sizing: border-box;"
#: A box inside a 1 px-bordered 44 px wrapper: the wrapper is the target, the box fills it.
_INNER_TARGET = "min-height: calc(var(--alg-target) - 2px);"
_MONO_TYPE = (
    "font-family: var(--alg-font-mono); font-size: var(--alg-mono-size);"
    " line-height: var(--alg-mono-line); font-variant-numeric: tabular-nums;"
)
_STANDALONE_NUMBER = f'input[type="number"]:not({SLIDER_VALUE_INPUT})'
_SLIDER_BOX = f"div:has(> {SLIDER_VALUE_INPUT})"
_SLIDER_HEAD = f"div:has(> div > {SLIDER_VALUE_INPUT})"
_ICON_PANELS = ", ".join(f'div:has(> button[aria-label="{label}"])' for label in STOCK_ICON_LABELS)
_STRIP_WRAP = f"div:has(> {TABLIST})"
# the edge fades: the mask is alpha, so `black` and `transparent` are the only "colours"
_FADE_END = f"linear-gradient(to right, black calc(100% - {STRIP_FADE}), transparent)"
_FADE_START = f"linear-gradient(to right, transparent, black {STRIP_FADE})"
_FADE_BOTH = (
    f"linear-gradient(to right, transparent, black {STRIP_FADE},"
    f" black calc(100% - {STRIP_FADE}), transparent)"
)


def _mask(image: str) -> str:
    return f"-webkit-mask-image: {image}; mask-image: {image};"


def _strip_edge_rule(value: str, image: str) -> str:
    return page_rule(_mask(image), suffix=f'{_STRIP_WRAP}[{STRIP_EDGE_ATTR}="{value}"]')


CHROME_CSS = stylesheet(
    # buttons: every state
    page_rule(
        f"{_CONTROL_BOX} {_CONTROL_TYPE} cursor: pointer;"
        " transition: background-color var(--alg-motion), border-color var(--alg-motion),"
        " color var(--alg-motion);",
        suffix="button",
    ),
    page_rule(
        "opacity: 1; filter: none; cursor: not-allowed; background: var(--alg-surface-2);"
        " color: var(--alg-text-2); border-color: var(--alg-hairline); box-shadow: none;",
        suffix="button:disabled",
    ),
    page_rule(_RING, suffix=':is(button, a, summary, [role="tab"]):focus-visible'),
    page_rule(
        _RING,
        suffix=':is(input[type="checkbox"], input[type="radio"], input[type="range"])'
        ":focus-visible",
    ),
    page_rule("outline: none;", suffix=':is(input[type="number"], textarea, select):focus-visible'),
    # tabs: the strip grows with its 44 px buttons; colours come from the theme variables
    page_rule(f"height: auto; {_TARGET}", suffix='[role="tablist"]'),
    page_rule(
        f"{_TARGET} padding: 12px 16px; {_CONTROL_TYPE} font-weight: 500;",
        suffix='button[role="tab"]',
    ),
    page_rule(f"{_TARGET} min-width: var(--alg-target);", suffix='button[aria-label="More tabs"]'),
    # a combobox list opened by Tab-arrival never paints (the shell marks it before the flush)
    page_rule("display: none;", suffix=f"[{ARRIVAL_ATTR}]"),
    # text inputs
    page_rule(
        f"{_CONTROL_BOX} height: var(--alg-target); {_CONTROL_TYPE}"
        " font-variant-numeric: tabular-nums;",
        suffix=_STANDALONE_NUMBER,
    ),
    # number boxes carry no native spinner: the arrows are 12 px targets that step a typed
    # value by one and read as chrome the design did not draw (round 11); every engine's form
    page_rule("appearance: textfield; -moz-appearance: textfield;", suffix='input[type="number"]'),
    page_rule(
        "-webkit-appearance: none; display: none; margin: 0;",
        suffix=f'input[type="number"]::{NUMBER_SPINNERS[0]}',
    ),
    page_rule(
        "-webkit-appearance: none; display: none; margin: 0;",
        suffix=f'input[type="number"]::{NUMBER_SPINNERS[1]}',
    ),
    # a single-row textarea (the permalink box, the Governed action) lands on 44 px: one 20 px
    # line inside 12 px pads; a taller box grows by whole lines (round 7: 46 px)
    page_rule(
        f"{_TARGET} {_CONTROL_TYPE} padding-top: 12px; padding-bottom: 12px;"
        " box-sizing: border-box;",
        suffix="textarea",
    ),
    page_rule(f"{_TARGET} {_BODY_TYPE}", suffix='input[type="text"]'),
    # the combobox: its bordered wrapper is the 44 px target; the box inside it and the input
    # are two pixels shorter, so the borders land inside the target instead of around it
    # (round 6: a 46 px dropdown beside 44 px pills stepped the Races row by 2 px)
    page_rule(f"{_TARGET} box-sizing: border-box;", suffix=f"div:has(> div > div > {COMBOBOX})"),
    page_rule(
        f"{_INNER_TARGET} align-items: center; box-sizing: border-box; padding: 0 16px;",
        suffix=f"div:has(> div > {COMBOBOX})",
    ),
    page_rule(
        f"{_INNER_TARGET} {_CONTROL_TYPE} margin: 0; box-sizing: border-box;", suffix=COMBOBOX
    ),
    # radio and checkbox rows and boxes
    page_rule(
        f"{_CONTROL_BOX} {_CONTROL_TYPE} align-items: center;",
        suffix='label:has(> input[type="radio"])',
    ),
    page_rule(
        f"{_CONTROL_BOX} {_CONTROL_TYPE} align-items: center;",
        suffix='label:has(> input[type="checkbox"])',
    ),
    page_rule(
        "width: 20px; height: 20px; flex: 0 0 20px; margin: 0;",
        suffix=':is(input[type="checkbox"], input[type="radio"])',
    ),
    page_rule("border-radius: var(--alg-radius-pill);", suffix='input[type="radio"]'),
    # sliders: a 44 px value box, no reset button
    page_rule(_TARGET, suffix='input[type="range"]'),
    page_rule("display: none;", suffix=SLIDER_RESET_BUTTON),
    page_rule(
        f"height: auto; {_TARGET} overflow: visible; align-items: stretch;"
        " border: 1px solid var(--alg-hairline); border-radius: var(--alg-radius-input);"
        " background: var(--alg-surface-2);"
        " box-sizing: border-box;",  # the bordered box is the target; the input inside is 44 - 2
        suffix=_SLIDER_BOX,
    ),
    page_rule("align-items: center; gap: 8px 16px; margin: 0 0 8px;", suffix=_SLIDER_HEAD),
    page_rule(
        # the bordered box around it is the 44 px target (round 10: the box measured 46)
        f"{_INNER_TARGET} height: auto; padding: 0 12px;"
        f" {_MONO_TYPE} text-align: right; min-width: 72px; border: 0;"
        " border-radius: var(--alg-radius-input); background: transparent;"
        " color: var(--alg-text);",
        suffix=SLIDER_VALUE_INPUT,
    ),
    page_rule(
        "box-shadow: 0 0 0 2px var(--alg-accent-to); border-radius: var(--alg-radius-input);",
        suffix=f"{SLIDER_VALUE_INPUT}:focus",
    ),
    # stock chrome that the design system replaces
    page_rule("display: none;", suffix=STATUS_TRACKER),
    page_rule("display: none;", suffix=f":is({_ICON_PANELS})"),
    # the open dropdown: panel, rows, hover, selected, the check mark
    page_rule(
        "background: var(--alg-surface); color: var(--alg-text);"
        " border: 1px solid var(--alg-hairline); border-radius: var(--alg-radius-input);"
        " box-shadow: var(--alg-shadow); padding: 4px; box-sizing: border-box;",
        suffix=f"div:has(> {LISTBOX})",
    ),
    page_rule("margin: 0; padding: 0;", suffix=LISTBOX),
    page_rule(
        f"{_TARGET} max-width: 100%; box-sizing: border-box; display: flex; align-items: center;"
        f" gap: 8px; padding: 12px; {_BODY_TYPE} color: var(--alg-text);"
        " border-radius: var(--alg-radius-input); background: transparent; cursor: pointer;"
        " transition: background-color var(--alg-motion);",
        suffix=OPTION,
    ),
    page_rule("background: var(--alg-surface-hover);", suffix=f"{OPTION}:hover"),
    page_rule("background: var(--alg-surface-2);", suffix=f'{OPTION}[aria-selected="true"]'),
    page_rule(
        "flex: 0 0 16px; padding: 0; color: var(--alg-accent-text, var(--alg-button-from));",
        suffix=f"{OPTION} > span",
    ),
    # accordions: the header button IS the 44 px target and carries the hairline itself (round
    # 9: a bordered block around a 44 px button measured 46, a 42 px button inside a 44 px
    # block failed the focusable-target gate). The block is transparent and unpadded; the
    # button draws the frame (surface, hairline, card radius) with its 20 px line centred and
    # inset 16 px, the chevron turns, and the open content continues the frame below it.
    rule(DISCLOSURE_CLASS, "padding: 0; border: 0; background: transparent; box-shadow: none;"),
    rule(
        DISCLOSURE_CLASS,
        f"{_TARGET} display: flex; align-items: center; justify-content: space-between;"
        f" gap: 16px; padding: 0 16px; margin: 0; {_CONTROL_TYPE} font-weight: 500;"
        " color: var(--alg-text); background: var(--alg-surface); box-sizing: border-box;"
        " border: 1px solid var(--alg-hairline); border-radius: var(--alg-radius-card);",
        suffix=" > button",
    ),
    rule(
        DISCLOSURE_CLASS,
        "border-radius: var(--alg-radius-card) var(--alg-radius-card) 0 0;",
        suffix=f" > {OPEN_HEADER}",
    ),
    rule(DISCLOSURE_CLASS, "display: none;", suffix=" > button > span + span"),
    rule(
        DISCLOSURE_CLASS,
        'content: ""; flex: 0 0 20px; width: 20px; height: 20px; color: var(--alg-text-2);'
        f" background: currentColor; -webkit-mask: {CHEVRON_MASK} center / 20px 20px no-repeat;"
        f" mask: {CHEVRON_MASK} center / 20px 20px no-repeat; transform: rotate(0deg);"
        " transition: transform var(--alg-motion);",
        suffix=" > button::after",
    ),
    rule(DISCLOSURE_CLASS, "color: var(--alg-text);", suffix=" > button:hover::after"),
    rule(DISCLOSURE_CLASS, "transform: rotate(90deg);", suffix=f" > {OPEN_HEADER}::after"),
    rule(
        DISCLOSURE_CLASS,
        "padding: 0 16px 16px; background: var(--alg-surface);"
        " border: 1px solid var(--alg-hairline); border-top: 0;"
        " border-radius: 0 0 var(--alg-radius-card) var(--alg-radius-card);",
        suffix=f" > {ACCORDION_CONTENT}",
    ),
    # the phone tab strip: every tab in one scrolling row (see the module docstring)
    block(
        f"@media (width <= {PHONE_MAX_WIDTH}px)",
        page_rule(
            "height: auto; margin: 0 -4px; padding: 4px 4px 8px; overflow-x: auto;"
            " overflow-y: hidden; scrollbar-width: none; scroll-snap-type: x proximity;"
            " scroll-padding: 0 4px; -webkit-overflow-scrolling: touch;",
            suffix=f"div:has(> {TABLIST})",
        ),
        page_rule("display: none;", suffix=f"div:has(> {TABLIST})::-webkit-scrollbar"),
        page_rule(
            "width: max-content; min-width: 100%; flex: 0 0 auto; overflow: visible;"
            " padding: 0 16px 0 0; box-sizing: border-box;",
            suffix=TABLIST,
        ),
        page_rule("flex: 0 0 auto; scroll-snap-align: start; white-space: nowrap;", suffix=TAB),
        page_rule("display: none;", suffix=f"span:has(> {MORE_TABS})"),
        # the edge that hides more tabs fades (shell.TABSTRIP_SCRIPT writes the attribute)
        _strip_edge_rule("start", _FADE_END),
        _strip_edge_rule("end", _FADE_START),
        _strip_edge_rule("middle", _FADE_BOTH),
    ),
    # Reduced motion: no transition and no animation anywhere on the page. The universal rule
    # is (0,4,0); the chrome rules above that set a transition carry an element or attribute
    # in their selector — `button` is (0,4,1) — so each of those is repeated here, where it
    # wins (round 11 measured the 180 ms button fades still running under the preference).
    block(
        "@media (prefers-reduced-motion: reduce)",
        page_rule("transition: none; animation: none;", suffix="*"),
        page_rule("transition: none;", suffix="button"),
        page_rule("transition: none;", suffix=OPTION),
        rule(DISCLOSURE_CLASS, "transition: none;", suffix=" > button::after"),
    ),
)
#: The selectors whose rest-state rule sets a transition; `REDUCED_MOTION_CSS` must name each.
TRANSITION_SELECTORS: tuple[str, ...] = ("button", OPTION, f".{DISCLOSURE_CLASS} > button::after")

# semantic role -> (light classes, dark classes) — gradio 6.28.0's basicLight / basicDark
CODE_TOKEN_CLASSES: Mapping[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "keyword": (("ͼ1q",), ("ͼp",)),
    "string": (("ͼ28", "ͼ2a", "ͼ27", "ͼ26"), ("ͼ17", "ͼ19", "ͼ16", "ͼ15")),
    "literal": (("ͼ1z", "ͼ2l", "ͼ1v"), ("ͼy", "ͼ1l", "ͼu")),
    "comment": (("ͼ2c",), ("ͼ1b",)),
    "name": (
        ("ͼ1r", "ͼ1s", "ͼ1t", "ͼ1u", "ͼ1w", "ͼ20", "ͼ22", "ͼ24", "ͼ25"),
        ("ͼq", "ͼr", "ͼs", "ͼt", "ͼv", "ͼz", "ͼ11", "ͼ13", "ͼ14"),
    ),
    "punctuation": (
        ("ͼ21", "ͼ1x", "ͼ23", "ͼ2b", "ͼ1y", "ͼ2n", "ͼ2m"),
        ("ͼ10", "ͼw", "ͼ12", "ͼ1a", "ͼx", "ͼ1n", "ͼ1m"),
    ),
    "link": (("ͼ29",), ("ͼ18",)),
    "emphasis": (
        ("ͼ2d", "ͼ2e", "ͼ2g", "ͼ2h", "ͼ2i", "ͼ2j", "ͼ2k"),
        ("ͼ1c", "ͼ1d", "ͼ1e", "ͼ1g", "ͼ1h", "ͼ1i", "ͼ1j", "ͼ1k"),
    ),
    "invalid": (("ͼ2o",), ("ͼ1o",)),
}

# semantic role -> declarations; every colour is a token that clears 4.5:1 on the surfaces
CODE_ROLE_STYLE: Mapping[str, str] = {
    "keyword": "color: var(--alg-accent-text);",
    "string": "color: var(--alg-ok);",
    "literal": "color: var(--alg-text); font-variant-numeric: tabular-nums;",
    "comment": "color: var(--alg-text-2); font-style: italic;",
    "name": "color: var(--alg-text);",
    "punctuation": "color: var(--alg-text-2);",
    "link": "color: var(--alg-accent-text); text-decoration: underline;",
    "emphasis": "color: var(--alg-text);",
    "invalid": "color: var(--alg-err); border-bottom: 0;",
}


def _token_rule(role: str) -> str:
    light, dark = CODE_TOKEN_CLASSES[role]
    spans = ", ".join(f"span.{cls}" for cls in light + dark)
    return page_rule(CODE_ROLE_STYLE[role], suffix=f".cm-content :is({spans})")


CODE_CSS = stylesheet(
    page_rule(
        "background: var(--alg-surface-2); color: var(--alg-text);"
        " border: 1px solid var(--alg-hairline); border-radius: var(--alg-radius-input);",
        suffix=".cm-editor",
    ),
    page_rule(_RING, suffix=".cm-editor.cm-focused"),
    page_rule(f"{_MONO_TYPE} color: var(--alg-text);", suffix=".cm-scroller"),
    page_rule(
        f"{_MONO_TYPE} color: var(--alg-text); padding: 12px 0; caret-color: var(--alg-text);",
        suffix=".cm-content",
    ),
    page_rule("padding: 0 12px;", suffix=".cm-line"),
    page_rule("color: inherit;", suffix=".cm-content span"),
    *(_token_rule(role) for role in CODE_TOKEN_CLASSES),
    # no stock chrome: the `</>` block label above the editor and the gutter beside it (line
    # numbers and fold markers) — the tabs' own captions carry the words (module docstring)
    page_rule("display: none;", suffix=CODE_BLOCK_LABEL),
    page_rule("display: none;", suffix=GUTTERS),
    page_rule("background: transparent;", suffix=".cm-activeLine"),
    page_rule("border-left-color: var(--alg-text);", suffix=".cm-cursor"),
    page_rule(
        "background: color-mix(in srgb, var(--alg-accent-to) 24%, transparent);",
        suffix=":is(.cm-selectionBackground, .cm-content ::selection)",
    ),
    # a snippet editor never shows an empty document
    rule(SNIPPET_EDITOR_CLASS, "display: none;", suffix=f":has({EMPTY_EDITOR})"),
)

_FILL = "display: flex; flex-direction: column; flex: 1 1 auto;"
_UNFILLED = ", ".join(f".{cls}" for cls in UNFILLED_CARD_CLASSES)

# The two-column contract (module docstring): the row stretches, the controls column keeps its
# natural height, the results column is a flex column that stretches, and the fill block's
# chain — block > container > prose > payload — grows; a state card does not.
LAYOUT_CSS = stylesheet(
    rule(COLS_CLASS, "align-items: stretch;"),
    # controls never stretch: the class, and every row child that is not the results column
    rule(CONTROLS_CLASS, "align-self: flex-start;"),
    rule(COLS_CLASS, "align-self: flex-start;", suffix=f" > :not(.{RESULTS_CLASS})"),
    rule(RESULTS_CLASS, "display: flex; flex-direction: column; align-self: stretch;"),
    # the fill block alone takes the column's slack; a disclosure or note beside it does not
    rule(RESULTS_CLASS, "flex: 0 0 auto;", suffix=" > *"),
    rule(RESULTS_CLASS, "flex: 1 1 auto;", suffix=f" > .{FILL_CLASS}"),
    rule(FILL_CLASS, _FILL),
    rule(FILL_CLASS, _FILL, suffix=" > div"),
    rule(FILL_CLASS, _FILL, suffix=" > div > div"),
    rule(FILL_CLASS, "flex: 1 1 auto;", suffix=" > *"),
    # a state is not a result: an empty, quiet or loading card is as tall as its content
    rule(FILL_CLASS, "flex: 0 0 auto;", suffix=f" > :is({_UNFILLED})"),
)
