"""Playground — any of the published functions: family → module → function → a typed form.

The form is generated from the kernel's own contract (``playground.form_spec``): whole numbers
and floats get a number box, booleans a checkbox, strings a text box, lists and structs a JSON
box whose help names the element type. Every number box takes what the visitor types, decimals
included — no ``precision`` rounds a value in the browser or on the way back from the server —
and Run validates with the kernel wrapper's exact acceptance rules (``playground.parse_inputs``):
a whole-number parameter given ``2.5`` is refused with "n_a must be a whole number." under the
field, never rounded and never a traceback. The call then runs through the one native lane and
the tab shows the result card (its subtitle is the function's own description; a parity chip only
when a reference library is installed for that function and it agrees on the very arguments
that ran), the request and response as JSON, the reproducible snippet in three dialects with the
visitor's arguments, and a permalink.

Gradio components are static, so the form is ``MAX_FIELDS`` slots (enough for every published
function; the widest takes 24 arguments), each a column holding one component per control kind
and its message. The default function's form is built at construction, so the first paint is a
complete form; a slot a function does not need is a hidden column that takes no space; the slots
sit on one form surface. Changing the family, module or function resets everything a run left
behind: the result card returns to the empty state, the status row clears, and the Request and
Reproduce editors show the request, the snippets and the permalink for the newly selected
function with its default arguments — an editor is never shown empty. A function without a known
argument set hides those editors behind one line that says they appear after Run; the response
editor appears only once a response exists.

The dropdown cascade listens to the visitor's ``input`` only (never ``change``, which a restore
or the cascade itself fires), so the page can restore ``?tab=play&fn=module.function&args={...}``
through the shell's permalink protocol without the cascade undoing the restored choice. Gradio's
Dropdown dispatches ``input`` on every blur as well — closing the listbox by clicking away or
tabbing off, with nothing chosen, fires it with the value unchanged (Escape does not; ``select``
fires for a pointer pick only, never for Enter) — so a value guard sits in front of the cascade:
``gr.State`` holds the trio last applied, and a family, module or function that equals it is a
no-op that leaves every typed value alone. A typed filter that matches nothing (``allow_custom_
value`` on the module and function boxes, which the API needs) is snapped back to the applied
choice instead of clearing the form.

Refused input leaves no result card behind, and one convention says so twice: the field message
appears under the offending field (``role="alert"``) and the same sentence is echoed in the status
row beside Run (``common.render_status_echo``, ``role="status"``) — Run sits far below a long
form, and after the page scrolls to it the field message can be above the viewport. The card
returns to its empty state, and the Request-and-response disclosure shows that no call was made:
the request editor hides (never the previous run's request beside arguments that did not run),
the response stays hidden and the note reads ``REQUEST_REFUSED_NOTE``. The Reproduce editors keep
the last call they showed — the refusal for a whole number at or above 2^53 points the visitor
at the snippet there, to edit by hand.

Every dropdown allows a custom value, so an API or MCP client can name any family, module or
function and the handlers, not Gradio, answer: a selection this container does not serve
(``selection_refusal`` — a family that is not loaded here, a module the family does not ship, a
function the module does not publish) snaps the box back to the applied choice, echoes one
sentence in the status row and puts the quiet coded card (``unknown_family``, ``unknown_module``,
``unknown_function``, or the family's own load error code) in the card slot — never Gradio's
stock "not in the list of choices" error. A typed filter that still matches part of a choice
and is blurred (``is_filter``) is a dismissal, not a request: the box snaps back and nothing
else moves. Run with such a selection (the API path) answers the same card. The permalink report
(``permalink_applied`` in the handles, with the catalogue) names the function this container
serves and, of the link's arguments, only the values the form's fields can show as the kernel
would take them.

Every read-only code block — the request, the response, the three snippets — is
``common.code_editor``: our caption above an editor without Gradio's block label or line-number
gutter, the caption shown and hidden with its editor.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from algenta_spaces import bench, cards, examples, hubkernel, playground
from algenta_spaces.runtime import utc_stamp

import permalink as permalink_mod
import races
from tabs import TAB_PLAY, Deps, TabSpec, common

log = logging.getLogger(__name__)

MAX_FIELDS = 24
FEATURE = "kernels"
API_NAMES = ("play_modules", "play_functions", "play_form", "play_run")
DEFAULT_FAMILY = "stats"
DEFAULT_MODULE = "ab_testing"
DEFAULT_FUNCTION = "z_test_proportions"

LABEL_FAMILY = "Family"
LABEL_MODULE = "Module"
LABEL_FUNCTION = "Function"
LABEL_RUN = "Run"
LABEL_REQUEST = "Request and response"
LABEL_REQUEST_JSON = "request"
LABEL_RESPONSE_JSON = "response"
LABEL_SNIPPETS = "Reproduce"
LABEL_KERNELS = "kernels"
LABEL_SDK = "SDK"
LABEL_MCP = "MCP"
LABEL_PERMALINK = "Permalink"
OPTIONAL_NOTE = "optional · the kernel's default applies when empty"
NO_ARGUMENTS = "takes no arguments"
EMPTY_TITLE = "No result yet"
EMPTY_TEXT = "Choose a function, fill the form and press Run."
REQUEST_NOTE = "The request and the response appear here after Run."
#: The Request-and-response note after a refusal: nothing ran, so nothing is shown as a request.
REQUEST_REFUSED_NOTE = (
    "No call was made — the form refused the input. "
    "The request and the response appear here after a run."
)
REPRODUCE_NOTE = "The snippets and the permalink appear here with your arguments after Run."
#: The codes of a selection this container does not serve (`selection_refusal`).
CODE_UNKNOWN_FAMILY = "unknown_family"
CODE_UNKNOWN_MODULE = "unknown_module"
CODE_UNKNOWN_FUNCTION = "unknown_function"
#: The longest typed name a refusal repeats back.
NAME_ECHO_CHARS = 60
#: The components a function change resets besides the form, in output order: the request and
#: response editors and their note, the three snippets, the permalink and its note, provenance.
EDITOR_OUTPUTS: tuple[str, ...] = (
    "request_json",
    "response_json",
    "request_note",
    "kernels",
    "sdk",
    "mcp",
    "permalink",
    "reproduce_note",
    "provenance",
)

_SNIPPET_MODES = (playground.MODE_KERNELS, playground.MODE_SDK, playground.MODE_MCP)
_SNIPPET_LANGUAGES = {
    playground.MODE_KERNELS: "python",
    playground.MODE_SDK: "python",
    playground.MODE_MCP: "json",
}
_SNIPPET_LABELS = {
    playground.MODE_KERNELS: LABEL_KERNELS,
    playground.MODE_SDK: LABEL_SDK,
    playground.MODE_MCP: LABEL_MCP,
}
KINDS_IN_SLOT: tuple[str, ...] = (
    playground.KIND_INT,
    playground.KIND_FLOAT,
    playground.KIND_BOOL,
    playground.KIND_STR,
    playground.KIND_JSON,
)
#: The component each control kind lives in: int and float share the number box.
SLOT_COMPONENTS: tuple[str, ...] = ("number", "bool", "str", "json")
#: What a slot's form update carries, in order: its column, the four controls, its message.
SLOT_OUTPUTS: tuple[str, ...] = ("column", *SLOT_COMPONENTS, "message")
_COMPONENT_OF = {
    playground.KIND_INT: "number",
    playground.KIND_FLOAT: "number",
    playground.KIND_BOOL: "bool",
    playground.KIND_STR: "str",
    playground.KIND_JSON: "json",
}


# ---------------------------------------------------------------------------
# Catalogue navigation
# ---------------------------------------------------------------------------


class Catalogue:
    """The loaded families' contracts as the dropdowns see them, described once per family."""

    def __init__(self, deps: Deps):
        self._deps = deps
        self._described: dict[str, dict[str, Any]] = {}

    @property
    def families(self) -> list[str]:
        return sorted(name for name, loaded in self._deps.kernels.items() if not loaded.is_umbrella)

    def kernel(self, family: str) -> hubkernel.LoadedKernel | None:
        return self._deps.kernel(family)

    def describe(self, family: str) -> dict[str, Any]:
        if family not in self._described:
            loaded = self.kernel(family)
            if loaded is None:
                raise hubkernel.HubKernelUnavailable(
                    "unknown_family", f"{family} is not loaded here"
                )
            self._described[family] = hubkernel.describe(loaded)
        return self._described[family]

    def modules(self, family: str) -> list[str]:
        try:
            return sorted(self.describe(family)["modules"])
        except hubkernel.HubKernelError:
            return []

    def functions(self, family: str, module: str) -> list[str]:
        try:
            module_spec = self.describe(family)["modules"].get(module)
        except hubkernel.HubKernelError:
            return []
        return sorted(module_spec["functions"]) if module_spec else []

    def default_selection(self) -> tuple[str, str, str]:
        """stats · ab_testing · z_test_proportions when loaded, else the first of everything."""
        families = self.families
        if not families:
            return "", "", ""
        family = DEFAULT_FAMILY if DEFAULT_FAMILY in families else families[0]
        modules = self.modules(family)
        module = DEFAULT_MODULE if DEFAULT_MODULE in modules else (modules[0] if modules else "")
        functions = self.functions(family, module)
        function = (
            DEFAULT_FUNCTION
            if DEFAULT_FUNCTION in functions
            else (functions[0] if functions else "")
        )
        return family, module, function

    def locate(self, module: str, function: str) -> str | None:
        """The first family (in dropdown order) publishing ``module.function``, or None."""
        for family in self.families:
            if function in self.functions(family, module):
                return family
        return None

    def form(self, family: str, module: str, function: str) -> playground.Form | None:
        """The typed form, or None when the trio does not name a callable function here."""
        kernel = self.kernel(family) if family else None
        if kernel is None or not module or not function:
            return None
        try:
            return playground.form_spec(kernel, module, function)
        except playground.PlaygroundError:
            return None

    def total_functions(self) -> int:
        return sum(int(self.describe(f)["function_count"]) for f in self.families)


def hero_defaults(family: str, module: str, function: str) -> Mapping[str, Any] | None:
    """The plan's default arguments when ``module.function`` is a hero entry."""
    for hero in playground.heroes_for(family) if family in playground.FAMILIES else ():
        if hero.module == module and hero.function == function:
            return hero.args
    return None


#: The verified prefilled arguments, one file per family (`apps/spaces/tools/build_examples.py`).
EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "examples"


def plan_defaults(
    form: playground.Form | None, family: str, module: str, function: str
) -> dict[str, Any]:
    """What every field opens with: the hero's arguments, else the verified example for the
    function, else a synthesised set — never an empty box (round 9, owner rule)."""
    hero = hero_defaults(family, module, function)
    if hero:
        return dict(hero)
    if form is None:
        return {}
    return examples.for_form(form, family, EXAMPLES_DIR)


def split_qualname(fn: str | None) -> tuple[str, str]:
    """``text.fuzzy.levenshtein_distance`` -> ``("text.fuzzy", "levenshtein_distance")``."""
    if not fn or "." not in fn:
        return "", ""
    module, _, function = fn.rpartition(".")
    return module, function


# ---------------------------------------------------------------------------
# Form plan: which slot shows which control
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SlotPlan:
    """One slot after a function change: the component to show, its label, help and value."""

    index: int
    visible: bool
    component: str = "number"
    label: str = ""
    info: str = ""
    value: Any = None


def slot_plans(form: playground.Form | None, defaults: Mapping[str, Any] | None) -> list[SlotPlan]:
    plans: list[SlotPlan] = []
    fields = list(form.fields) if form is not None else []
    for index in range(MAX_FIELDS):
        if index >= len(fields):
            plans.append(SlotPlan(index, False))
            continue
        spec = fields[index]
        value = None if defaults is None else defaults.get(spec.name)
        if spec.kind == playground.KIND_JSON and value is not None and not isinstance(value, str):
            value = json.dumps(value, ensure_ascii=False)
        if spec.kind == playground.KIND_BOOL:
            value = bool(value) if value is not None else False
        info = spec.help if spec.required else f"{spec.help} · {OPTIONAL_NOTE}"
        plans.append(
            SlotPlan(
                index=index,
                visible=True,
                component=_COMPONENT_OF[spec.kind],
                label=spec.name,
                info=info,
                value=value,
            )
        )
    return plans


def function_doc(form: playground.Form) -> str:
    parts = [form.doc] if form.doc else []
    if form.return_type:
        parts.append(f"returns {playground.type_words(form.return_type, form.structs)}")
    if not form.fields:
        parts.append(NO_ARGUMENTS)
    return common.render_note(" · ".join(parts)) if parts else ""


def control_kwargs(plan: SlotPlan, name: str) -> dict[str, Any]:
    """The constructor or update keywords for the `name` control of one slot."""
    if not (plan.visible and plan.component == name):
        return {"visible": False}
    kwargs: dict[str, Any] = {
        "visible": True,
        "label": plan.label,
        "info": plan.info,
        "value": plan.value,
    }
    if name == "json":
        kwargs.pop("info")
        kwargs["label"] = f"{plan.label} — {plan.info}"
    return kwargs


def collect_raw(form: playground.Form, slot_values: Sequence[Sequence[Any]]) -> dict[str, Any]:
    """The form's raw mapping from the slots: each field reads the component of its own kind."""
    raw: dict[str, Any] = {}
    for index, spec in enumerate(form.fields):
        if index >= len(slot_values):
            break
        values = dict(zip(SLOT_COMPONENTS, slot_values[index], strict=True))
        raw[spec.name] = values[_COMPONENT_OF[spec.kind]]
    return raw


def field_message(name: str, reason: str) -> str:
    """`n_a is required.` — the field named, one sentence."""
    return f"{name} {reason}."


def _not_one_of(name: object, count: int, what: str) -> str:
    """`nope is not one of the 12 functions of ab_testing.` — the typed name (cut to
    `NAME_ECHO_CHARS`, whitespace folded) against what the list holds; with nothing to choose
    from, `… is not available here: no functions of ab_testing.`"""
    shown = " ".join(str(name or "").split())[:NAME_ECHO_CHARS] or "An empty name"
    if count == 0:
        return f"{shown} is not available here: no {what}."
    return f"{shown} is not one of the {count} {what}."


def is_filter(text: object, choices: Sequence[str]) -> bool:
    """True for a typed value that still matches part of a choice — an unfinished filter that a
    blur left in the box (Gradio filters its list by substring), a dismissal rather than a
    request for something that does not exist."""
    typed = " ".join(str(text or "").split()).lower()
    return bool(typed) and any(typed in str(choice).lower() for choice in choices)


def selection_refusal(
    deps: Deps,
    catalogue: Catalogue,
    family: str,
    module: str | None = None,
    function: str | None = None,
) -> tuple[str, str] | None:
    """``(code, one sentence)`` when the selection names something this container does not
    serve, else None. Judged in dropdown order, so the sentence names the first thing that is
    wrong: a family that is not loaded here (`unknown_family`, or the family's own load error
    code when it is published and did not load — the boot card carries the same code), a module
    the family does not ship (`unknown_module`), a function the module does not publish
    (`unknown_function`). `module` and `function` are judged only when given, so a family
    change is judged on the family alone."""
    families = catalogue.families
    if family not in families:
        error = deps.kernel_errors.get(family) or deps.kernel_errors.get(f"algenta-{family}")
        if error is not None:
            reason = " ".join(str(error.message).split()).rstrip(".")
            if reason and not (len(reason) > 1 and reason[1].isupper()):
                reason = reason[0].lower() + reason[1:]  # a clause, unless it opens an initialism
            return error.code, f"{family} did not load in this container: {reason}."
        return CODE_UNKNOWN_FAMILY, _not_one_of(
            family, len(families), "families loaded in this container"
        )
    if module is None:
        return None
    modules = catalogue.modules(family)
    if module not in modules:
        return CODE_UNKNOWN_MODULE, _not_one_of(module, len(modules), f"modules of {family}")
    if function is None:
        return None
    functions = catalogue.functions(family, module)
    if function not in functions:
        return CODE_UNKNOWN_FUNCTION, _not_one_of(
            function, len(functions), f"functions of {module}"
        )
    return None


def refusal_card(deps: Deps, code: str, sentence: str) -> str:
    """The quiet card for a selection this container does not serve: the empty state's title,
    the code chip and the sentence. Nothing ran, so nothing is red."""
    return cards.render_unavailable_card(
        title=EMPTY_TITLE, error_code=code, hint=sentence, hardware=common.hardware_line(deps)
    )


def subtitle_for(catalogue: Catalogue, family: str, module: str, form: playground.Form) -> str:
    """The card's human subtitle: the function's own description from the contract, else the
    module's, else how many arguments it takes — never a build variant or a revision."""
    if form.doc:
        return form.doc
    try:
        described = catalogue.describe(family)["modules"].get(module) or {}
    except hubkernel.HubKernelError:
        described = {}
    description = str(described.get("description") or "").strip()
    if description:
        return description
    count = len(form.fields)
    return NO_ARGUMENTS if count == 0 else f"{count} {'argument' if count == 1 else 'arguments'}"


def build_note(deps: Deps, kernel: hubkernel.LoadedKernel | None) -> str:
    """The Reproduce disclosure's provenance chips: family and revision, build variant, versions."""
    if kernel is None:
        return ""
    chips = [common.chip(kernel.label()), common.chip(f"build {kernel.variant}")]
    versions = deps.facts.get("versions") if isinstance(deps.facts, Mapping) else None
    if isinstance(versions, Mapping):
        for name in ("kernels", "torch"):
            version = versions.get(name)
            if version:
                chips.append(common.chip(f"{name} {version}"))
    return f'<div class="alg-chips">{"".join(chips)}</div>'


@dataclass(frozen=True)
class EditorState:
    """What the Request and Reproduce editors show for a function before any run.

    With a known argument set (the plan's defaults, or a permalink's) the request, the three
    snippets and the permalink carry that call; without one they are hidden behind the notes.
    The response is never shown before a response exists.
    """

    request_json: str | None = None
    snippets: Mapping[str, str] = field(default_factory=dict)
    permalink: str | None = None

    @property
    def known(self) -> bool:
        return self.request_json is not None


def editor_state(
    catalogue: Catalogue,
    family: str,
    module: str,
    function: str,
    args: Mapping[str, Any] | None,
    *,
    base: str = "",
) -> EditorState:
    """The default call for ``module.function`` when its arguments validate, else nothing."""
    form = catalogue.form(family, module, function)
    if form is None:
        return EditorState()
    defaults = dict(hero_defaults(family, module, function) or {})
    if args:
        defaults.update(args)
    if not defaults and form.fields:
        return EditorState()
    try:
        values = playground.parse_inputs(form, defaults)
    except playground.PlaygroundError:
        return EditorState()
    named = playground.named_args(form, values)
    title = f"{module}.{function}"
    try:
        snippets = {
            mode: playground.snippet(family, module, function, dict(named), mode=mode)
            for mode in _SNIPPET_MODES
        }
    except (playground.PlaygroundError, TypeError, ValueError):
        return EditorState()
    request = {"module": module, "function": function, "args": values}
    return EditorState(
        request_json=common.pretty_json(request, limit=common.RESULT_CHARS * 4),
        snippets=snippets,
        permalink=common.permalink(TAB_PLAY, fn=title, args=dict(named), base=base),
    )


# ---------------------------------------------------------------------------
# Running one call
# ---------------------------------------------------------------------------


@dataclass
class Outcome:
    """What one Run produces; every field maps onto one output component.

    `echo` is the one sentence the status row repeats beside Run for a refusal that has no
    field of its own (a selection this container does not serve); a field refusal's echo is
    its field message, built where the outputs are."""

    chip: str = ""
    card: str | None = None
    request_json: str | None = None
    response_json: str | None = None
    snippets: dict[str, str] = field(default_factory=dict)
    permalink: str | None = None
    field_errors: dict[str, str] = field(default_factory=dict)
    echo: str = ""

    @property
    def refused(self) -> bool:
        """True when the form refused the input: a message under a field, no result card."""
        return bool(self.field_errors)


def parity_chip(module: str, function: str, args: Sequence[Any], result: Any) -> tuple[str, str]:
    """``(label, tone)`` from the installed reference for this function; empty without one."""
    found = races.reference_for(module, function)
    if found is None:
        return "", ""
    reference, pin = found
    try:
        theirs = reference.call(args)
        ok, label = reference.gate(result, theirs)
    except Exception as exc:  # a reference that cannot run here is reported, not hidden
        log.warning("reference %s failed: %s", pin, exc)
        return f"reference {pin} did not run", "warn"
    return (f"{label} · {pin}", "ok") if ok else (f"differs from {pin}", "err")


def run_call(
    deps: Deps,
    catalogue: Catalogue,
    family: str,
    module: str,
    function: str,
    raw: Mapping[str, Any],
    request: Any = None,
    *,
    base: str = "",
) -> Iterator[Outcome]:
    """Validate, queue on the lane, execute, render — yielding the lane chip first. An unset
    selection (no family loaded in this container, so the dropdowns carry nothing) is the
    quiet `kernel_not_loaded` card under the empty-state title — never a raise, which Gradio
    would paint as a toast; a selection this container does not serve (the API path: the
    browser's boxes cannot hold one) is the quiet coded card with its sentence echoed
    (`selection_refusal`)."""
    if not (family and module and function):
        yield Outcome(card=common.no_kernel_card(EMPTY_TITLE, family or "", deps))
        return
    refusal = selection_refusal(deps, catalogue, family, module, function)
    if refusal is not None:
        code, sentence = refusal
        yield Outcome(card=refusal_card(deps, code, sentence), echo=sentence)
        return
    title = f"{module}.{function}"
    hardware = common.hardware_line(deps)
    kernel = catalogue.kernel(family)
    if kernel is None:
        yield Outcome(card=common.no_kernel_card(title, family, deps))
        return
    try:
        form = playground.form_spec(kernel, module, function)
        values = playground.parse_inputs(form, raw)
    except playground.ValidationError as exc:
        yield Outcome(field_errors={exc.field: exc.reason})
        return
    except playground.PlaygroundError as exc:
        # the catalogue lists it but the contract refuses it: nothing ran, so the quiet card
        sentence = f"{title} cannot be called here: {' '.join(str(exc).split()).rstrip('.')}."
        yield Outcome(card=refusal_card(deps, CODE_UNKNOWN_FUNCTION, sentence), echo=sentence)
        return
    if not deps.feature_on(FEATURE):
        yield Outcome(card=common.switched_off_card(title, hardware))
        return
    decision = common.check_limit(deps, request)
    if decision is not None and not decision.allowed:
        yield Outcome(card=common.limited_card(title, decision, hardware))
        return
    named = playground.named_args(form, values)
    snippets = {
        mode: playground.snippet(family, module, function, dict(named), mode=mode)
        for mode in _SNIPPET_MODES
    }
    link = common.permalink(TAB_PLAY, fn=title, args=dict(named), base=base)
    ticket = None
    try:
        ticket = deps.lane.submit(
            hubkernel.execute,
            kernel,
            module,
            function,
            values,
            budget_s=common.CALL_BUDGET_S,
            label=title,
        )
        yield Outcome(chip=common.lane_chip(ticket))
        call = ticket.result()
    except Exception as exc:  # lane refusals and kernel errors are cards with a code
        log.warning("%s failed: %s", title, exc)
        yield Outcome(chip="", card=common.error_card(title, exc, hardware), snippets=snippets)
        return
    label, tone = parity_chip(module, function, values, call.result)
    card = common.render_call_card(
        title=title,
        subtitle=subtitle_for(catalogue, family, module, form),
        latency_ms=call.elapsed_ms,
        result=call.result,
        hardware=hardware,
        ts_utc=utc_stamp(),
        parity=label if tone == "ok" else "",
        kernel_label=kernel.label(),
        extra_chips=((label, tone),) if tone in ("warn", "err") else (),
        load_1m=bench.load_1m(),
    )
    request_doc = {"module": module, "function": function, "args": values}
    yield Outcome(
        chip=common.done_chip(ticket) if ticket is not None else "",
        card=card,
        request_json=common.pretty_json(request_doc, limit=common.RESULT_CHARS * 4),
        response_json=common.pretty_json(
            {"result": call.result, "elapsed_ms": round(call.elapsed_ms, 3)},
            limit=common.RESULT_CHARS * 4,
        ),
        snippets=snippets,
        permalink=link,
    )


# ---------------------------------------------------------------------------
# Permalink protocol (see app.py and docs/spaces/FLAGSHIP.md)
# ---------------------------------------------------------------------------


def permalink_outputs(handles: Mapping[str, Any]) -> list[Any]:
    """One hidden box the shell writes on page load; its change event restores the form."""
    box = handles.get("restore")
    return [box] if box is not None else []


def permalink_restore(fn: str | None, args: Mapping[str, Any] | None) -> list[Any]:
    return [common.permalink_payload(fn, args)]


def applied_args(form: playground.Form, args: Mapping[str, Any] | None) -> dict[str, Any]:
    """Of `args`, the values the form's fields can show, as the kernel would take them: each key
    must name a field and its value must pass the field's own coercion and type check on its
    own (a string for a number box, a decimal for a whole number, an unknown key, a value the
    number box cannot carry exactly, all drop). What survives is what a restore writes into the
    controls and what the permalink report promises — nothing more."""
    out: dict[str, Any] = {}
    if not args:
        return out
    for spec in form.fields:
        if spec.name not in args:
            continue
        try:
            value = playground.coerce(spec, args[spec.name])
            playground.normalize_value(value, spec.type_name, form.structs, spec.name)
        except playground.ValidationError:
            continue
        # the coerced value, not the normalised one: `10` for a float field stays `10` in the
        # box and in the link, as the visitor wrote it; text JSON becomes the object it names
        out[spec.name] = value
    return out


def applied_call(
    catalogue: Catalogue, fn: str | None, args: Mapping[str, Any] | None
) -> tuple[str, dict[str, Any] | None] | None:
    """The permalink report: `(fn, applied args or None)` when a loaded family serves `fn`, else
    None — a link to a function this container does not run restores nothing beyond the tab."""
    module, function = split_qualname(fn)
    if not module:
        return None
    family = catalogue.locate(module, function)
    form = catalogue.form(family, module, function) if family else None
    if form is None:
        return None
    applied = applied_args(form, args)
    return fn, applied or None


def restore_target(
    catalogue: Catalogue, text: Any
) -> tuple[str, str, str, Mapping[str, Any] | None] | None:
    """``(family, module, function, applied args)`` named by a restore payload, or None when the
    function is unknown here; the arguments are filtered by `applied_args`, so the controls show
    exactly what the report promised."""
    fn, args = common.permalink_request(text)
    module, function = split_qualname(fn)
    if not module:
        return None
    family = catalogue.locate(module, function)
    if family is None:
        return None
    form = catalogue.form(family, module, function)
    applied = applied_args(form, args) if form is not None else {}
    return family, module, function, applied or None


# ---------------------------------------------------------------------------
# The tab
# ---------------------------------------------------------------------------


def build(deps: Deps) -> TabSpec:
    catalogue = Catalogue(deps)
    family0, module0, function0 = catalogue.default_selection()
    form0 = catalogue.form(family0, module0, function0)
    plans0 = slot_plans(form0, plan_defaults(form0, family0, module0, function0))
    base = permalink_mod.public_base(deps.env)

    editors0 = editor_state(catalogue, family0, module0, function0, None, base=base)

    def render(gr: Any) -> dict[str, Any]:
        hooks = _event_hooks()
        quiet = {"show_progress": "hidden"}
        # The value guard: the trio the form was last built for. A dropdown `input` that names
        # the same value (Gradio fires one on every blur) changes nothing and keeps typed values.
        selection = gr.State((family0, module0, function0))
        with gr.Row(elem_classes=["alg-form-row"]):
            # Every box allows a custom value: Gradio would otherwise answer an API or MCP
            # client's foreign family with its stock error before any handler ran; the handlers
            # judge the selection (`selection_refusal`) and answer with a coded card instead.
            family = gr.Dropdown(
                catalogue.families,
                value=family0 or None,
                label=LABEL_FAMILY,
                interactive=True,
                allow_custom_value=True,
            )
            # The module and function lists follow the family; without allow_custom_value the
            # server validates an API or MCP call's value against the default family's list.
            module = gr.Dropdown(
                catalogue.modules(family0) if family0 else [],
                value=module0 or None,
                label=LABEL_MODULE,
                interactive=True,
                allow_custom_value=True,
            )
            function = gr.Dropdown(
                catalogue.functions(family0, module0) if module0 else [],
                value=function0 or None,
                label=LABEL_FUNCTION,
                interactive=True,
                allow_custom_value=True,
            )
        doc_html = function_doc(form0) if form0 is not None else ""
        doc = gr.HTML(doc_html, elem_classes=["alg-fn-doc"], visible=bool(doc_html))
        slots: list[dict[str, Any]] = []
        with gr.Column(
            elem_classes=["alg-form"], visible=any(p.visible for p in plans0)
        ) as surface:
            for plan in plans0:
                with gr.Column(elem_classes=["alg-field"], visible=plan.visible) as column:
                    slot = {
                        "column": column,
                        # `precision=None`: the box keeps what the visitor types; a whole-number
                        # parameter given a decimal is refused on Run, never rounded here.
                        "number": gr.Number(
                            interactive=True, precision=None, **control_kwargs(plan, "number")
                        ),
                        "bool": gr.Checkbox(interactive=True, **control_kwargs(plan, "bool")),
                        "str": gr.Textbox(interactive=True, lines=1, **control_kwargs(plan, "str")),
                        "json": gr.Code(
                            language="json",
                            interactive=True,
                            lines=3,
                            wrap_lines=True,
                            buttons=[],
                            **control_kwargs(plan, "json"),
                        ),
                        # Try's convention (round 7): an always-present slot holding one reserved
                        # caption line, so a refusal fills the line and moves nothing below it
                        "message": gr.HTML(
                            "",
                            elem_classes=["alg-status-row", "alg-field-slot", "alg-field-messages"],
                        ),
                    }
                slots.append(slot)
        run = gr.Button(LABEL_RUN, variant="primary", elem_classes=["alg-run"])
        status = gr.HTML(common.render_status(), elem_classes=["alg-status-row"])
        card = gr.HTML(common.render_empty(EMPTY_TITLE, EMPTY_TEXT), elem_classes=["alg-play-card"])
        copies: list[tuple[Any, Any]] = []

        def copy_chip(source: Any, *, visible: bool = True) -> Any:
            """A 44 px Copy chip under `source`, in a row shown exactly when the editor is."""
            with gr.Row(elem_classes=["alg-copy-row"], visible=visible) as row:
                button = gr.Button(
                    common.LABEL_COPY, variant="secondary", elem_classes=["alg-chip-btn"], scale=0
                )
            copies.append((button, source))
            return row

        known0 = editors0.known
        with gr.Accordion(LABEL_REQUEST, open=False, elem_classes=["alg-disclosure"]):
            request_note = gr.HTML(
                common.render_note(REQUEST_NOTE),
                elem_classes=["alg-editor-note"],
                visible=not known0,
            )
            request_caption, request_json = common.code_editor(
                gr,
                value=editors0.request_json or "",
                language="json",
                caption=LABEL_REQUEST_JSON,
                lines=6,
                visible=known0,
            )
            request_copy = copy_chip(request_json, visible=known0)
            response_caption, response_json = common.code_editor(
                gr, value="", language="json", caption=LABEL_RESPONSE_JSON, lines=6, visible=False
            )
            response_copy = copy_chip(response_json, visible=False)
        with gr.Accordion(LABEL_SNIPPETS, open=False, elem_classes=["alg-disclosure"]):
            provenance = gr.HTML(
                build_note(deps, catalogue.kernel(family0) if family0 else None),
                elem_classes=["alg-provenance"],
            )
            reproduce_note = gr.HTML(
                common.render_note(REPRODUCE_NOTE),
                elem_classes=["alg-editor-note"],
                visible=not known0,
            )
            snippet_boxes: dict[str, Any] = {}
            snippet_copies: dict[str, Any] = {}
            snippet_captions: dict[str, Any] = {}
            for mode in _SNIPPET_MODES:
                snippet_captions[mode], snippet_boxes[mode] = common.code_editor(
                    gr,
                    value=editors0.snippets.get(mode, ""),
                    language=_SNIPPET_LANGUAGES[mode],
                    caption=_SNIPPET_LABELS[mode],
                    lines=10,
                    visible=known0,
                )
                snippet_copies[mode] = copy_chip(snippet_boxes[mode], visible=known0)
            permalink = gr.Textbox(
                editors0.permalink or "",
                label=LABEL_PERMALINK,
                buttons=[],
                interactive=False,
                visible=known0,
            )
            permalink_copy = copy_chip(permalink, visible=known0)
        restore = gr.Textbox("", visible=False, elem_classes=["alg-restore"])
        editor_components = {
            "request_json": request_json,
            "response_json": response_json,
            "request_note": request_note,
            "kernels": snippet_boxes[playground.MODE_KERNELS],
            "sdk": snippet_boxes[playground.MODE_SDK],
            "mcp": snippet_boxes[playground.MODE_MCP],
            "permalink": permalink,
            "reproduce_note": reproduce_note,
            "provenance": provenance,
        }
        #: The Copy chip rows, shown exactly when their editor is.
        copy_of = {
            "request_json": request_copy,
            "response_json": response_copy,
            "kernels": snippet_copies[playground.MODE_KERNELS],
            "sdk": snippet_copies[playground.MODE_SDK],
            "mcp": snippet_copies[playground.MODE_MCP],
            "permalink": permalink_copy,
        }
        #: The code captions, shown exactly when their editor is (the permalink is a text box).
        caption_of = {
            "request_json": request_caption,
            "response_json": response_caption,
            "kernels": snippet_captions[playground.MODE_KERNELS],
            "sdk": snippet_captions[playground.MODE_SDK],
            "mcp": snippet_captions[playground.MODE_MCP],
        }

        slot_components = [[slot[name] for name in SLOT_COMPONENTS] for slot in slots]
        flat_slot_inputs = [c for group in slot_components for c in group]
        form_outputs = [doc, surface]
        for slot in slots:
            form_outputs.extend(slot[name] for name in SLOT_OUTPUTS)
        editor_outputs = [editor_components[name] for name in EDITOR_OUTPUTS]
        editor_copies = [copy_of[name] for name in EDITOR_OUTPUTS if name in copy_of]
        editor_captions = [caption_of[name] for name in EDITOR_OUTPUTS if name in caption_of]
        #: What a family, module or function change writes: the form, then what a run left.
        change_outputs = [
            *form_outputs,
            status,
            card,
            *editor_outputs,
            *editor_copies,
            *editor_captions,
        ]
        #: Where the status row and the card sit in `change_outputs` (a refusal writes them).
        status_index = len(form_outputs)
        card_index = status_index + 1

        def editor_updates(
            fam: str, mod: str, fn: str, args: Mapping[str, Any] | None = None
        ) -> list[Any]:
            """One update per `EDITOR_OUTPUTS` entry, then one per Copy chip, then one per code
            caption, for a function before any run: its default call in every editor, or the
            notes when none is known."""
            state = editor_state(catalogue, fam, mod, fn, args, base=base)
            shown = state.known
            by_name: dict[str, Any] = {
                "request_json": gr.update(value=state.request_json or "", visible=shown),
                "response_json": gr.update(value="", visible=False),
                "request_note": gr.update(
                    value=common.render_note(REQUEST_NOTE), visible=not shown
                ),
                "permalink": gr.update(value=state.permalink or "", visible=shown),
                "reproduce_note": gr.update(visible=not shown),
                "provenance": gr.update(
                    value=build_note(deps, catalogue.kernel(fam) if fam else None)
                ),
            }
            for mode in _SNIPPET_MODES:
                by_name[mode] = gr.update(value=state.snippets.get(mode, ""), visible=shown)
            updates = [by_name[name] for name in EDITOR_OUTPUTS]
            for following in (copy_of, caption_of):
                for name in EDITOR_OUTPUTS:
                    if name in following:
                        updates.append(gr.update(visible=by_name[name]["visible"]))
            return updates

        def form_updates(
            fam: str, mod: str, fn: str, args: Mapping[str, Any] | None = None
        ) -> list[Any]:
            """Every output of a change, in `change_outputs` order: the doc, the surface and
            each slot's parts, then the status row and the result card reset, then the editors."""
            form = catalogue.form(fam, mod, fn)
            defaults = plan_defaults(form, fam, mod, fn)
            if args:
                defaults.update(args)
            plans = slot_plans(form, defaults or None)
            text = function_doc(form) if form is not None else ""
            updates: list[Any] = [
                gr.update(value=text, visible=bool(text)),
                gr.update(visible=any(p.visible for p in plans)),
            ]
            for plan in plans:
                updates.append(gr.update(visible=plan.visible))
                for name in SLOT_COMPONENTS:
                    updates.append(gr.update(**control_kwargs(plan, name)))
                # the message slot is cleared, never hidden: it keeps its reserved line (round 7)
                updates.append(gr.update(value=""))
            updates.append(gr.update(value=common.render_status()))
            updates.append(gr.update(value=common.render_empty(EMPTY_TITLE, EMPTY_TEXT)))
            updates.extend(editor_updates(fam, mod, fn, args))
            return updates

        def no_change(applied: tuple[str, str, str], *boxes: Any) -> list[Any]:
            """Every output untouched (the given dropdown updates first), the state as it was."""
            return [*boxes, *(gr.update() for _ in change_outputs), applied]

        def refuse(
            applied: tuple[str, str, str], boxes: Sequence[Any], code: str, sentence: str
        ) -> list[Any]:
            """A selection this container does not serve: the boxes snapped back to the applied
            trio, the sentence echoed in the status row, the quiet coded card in the card slot,
            everything else untouched, the state as it was."""
            updates: list[Any] = [gr.update() for _ in change_outputs]
            # beside Run the status row says the run did not happen; the sentence itself lives
            # under the offending field, once (round 6)
            updates[status_index] = gr.update(
                value=common.render_status(echo=common.STATUS_NOT_RUN)
            )
            updates[card_index] = gr.update(value=refusal_card(deps, code, sentence))
            return [*boxes, *updates, applied]

        def as_trio(applied: Any) -> tuple[str, str, str]:
            trio = tuple(str(part or "") for part in (applied or ()))
            return trio if len(trio) == 3 else (family0, module0, function0)  # type: ignore[return-value]

        def snap(value: str) -> Any:
            """The box back on the applied choice (None when nothing is loaded)."""
            return gr.update(value=value or None)

        def on_family(fam: str, applied: Any) -> list[Any]:
            """The family box fired: a no-op when it names the applied family (a blur, a re-pick)
            or an unfinished filter (snapped back, nothing else moves); the refusal when it names
            a family this container does not serve; the cascade for another loaded one."""
            fam = str(fam or "")
            was = as_trio(applied)
            if fam == was[0]:
                return no_change(was, gr.update(), gr.update(), gr.update())
            refusal = selection_refusal(deps, catalogue, fam)
            if refusal is not None:
                if is_filter(fam, catalogue.families):
                    return no_change(was, snap(was[0]), gr.update(), gr.update())
                return refuse(was, [snap(was[0]), gr.update(), gr.update()], *refusal)
            modules = catalogue.modules(fam)
            mod = modules[0] if modules else ""
            functions = catalogue.functions(fam, mod) if mod else []
            fn = functions[0] if functions else ""
            return [
                gr.update(),
                gr.update(choices=modules, value=mod or None),
                gr.update(choices=functions, value=fn or None),
                *form_updates(fam, mod, fn),
                (fam, mod, fn),
            ]

        def on_module(fam: str, mod: str, applied: Any) -> list[Any]:
            """The module box fired: a no-op for the applied module or an unfinished filter; the
            refusal for a family or module this container does not serve; a real change
            cascades."""
            fam, mod = str(fam or ""), str(mod or "")
            was = as_trio(applied)
            if (fam, mod) == was[:2]:
                return no_change(was, gr.update())
            refusal = selection_refusal(deps, catalogue, fam, mod)
            if refusal is not None:
                if fam == was[0] and is_filter(mod, catalogue.modules(fam)):
                    return no_change(was, snap(was[1]))
                return refuse(was, [snap(was[1])], *refusal)
            functions = catalogue.functions(fam, mod)
            fn = functions[0] if functions else ""
            return [
                gr.update(choices=functions, value=fn or None),
                *form_updates(fam, mod, fn),
                (fam, mod, fn),
            ]

        def on_function(fam: str, mod: str, fn: str, applied: Any) -> list[Any]:
            """The function box fired: a no-op for the applied function (typed values stay) or
            an unfinished filter; the refusal for a family, module or function this container
            does not serve; a real change cascades."""
            fam, mod, fn = str(fam or ""), str(mod or ""), str(fn or "")
            was = as_trio(applied)
            if (fam, mod, fn) == was:
                return no_change(was, gr.update())
            refusal = selection_refusal(deps, catalogue, fam, mod, fn)
            if refusal is not None:
                if (fam, mod) == was[:2] and is_filter(fn, catalogue.functions(fam, mod)):
                    return no_change(was, snap(was[2]))
                return refuse(was, [snap(was[2])], *refusal)
            return [gr.update(), *form_updates(fam, mod, fn), (fam, mod, fn)]

        def on_restore(text: Any, applied: Any) -> list[Any]:
            target = restore_target(catalogue, text)
            if target is None:
                return [gr.update() for _ in range(3 + len(change_outputs))] + [as_trio(applied)]
            fam, mod, fn, args = target
            return [
                gr.update(value=fam),
                gr.update(choices=catalogue.modules(fam), value=mod),
                gr.update(choices=catalogue.functions(fam, mod), value=fn),
                *form_updates(fam, mod, fn, args),
                (fam, mod, fn),
            ]

        def on_run(
            fam: str, mod: str, fn: str, *slot_values: Any, request: gr.Request | None = None
        ):
            grouped = [
                list(slot_values[i : i + len(SLOT_COMPONENTS)])
                for i in range(0, len(slot_values), len(SLOT_COMPONENTS))
            ]
            form = catalogue.form(fam, mod, fn)
            raw = collect_raw(form, grouped) if form is not None else {}
            names = form.names if form is not None else ()
            for outcome in run_call(deps, catalogue, fam, mod, fn, raw, request, base=base):
                echo = outcome.echo
                if outcome.refused:
                    # the first refused field's own sentence, said once more beside Run
                    echo = field_message(*next(iter(outcome.field_errors.items())))
                # a refusal's sentence lives in its card; the status row acknowledges it (round 6)
                acknowledged = common.STATUS_NOT_RUN if echo else ""
                out: list[Any] = [common.render_status(outcome.chip, echo=acknowledged)]
                if outcome.refused:
                    # nothing ran: the empty state, never a card beside arguments it did not use
                    out.append(common.render_empty(EMPTY_TITLE, EMPTY_TEXT))
                else:
                    out.append(gr.update() if outcome.card is None else outcome.card)
                texts: dict[str, str | None] = {
                    "request_json": outcome.request_json,
                    "response_json": outcome.response_json,
                    "permalink": outcome.permalink,
                    **{mode: outcome.snippets.get(mode) for mode in _SNIPPET_MODES},
                }
                # Per editor: None leaves it as it is, True shows its text, False empties and
                # hides it — the Copy chip and the caption under and above it follow the same.
                shown: dict[str, bool | None] = {
                    name: (None if text is None else True) for name, text in texts.items()
                }
                if outcome.refused:
                    # no call was made: the request editor never keeps an earlier run's request
                    # beside arguments that did not run, and there is no response to show
                    shown["request_json"] = shown["response_json"] = False
                for name in EDITOR_OUTPUTS:
                    if name == "request_note":
                        if outcome.refused:
                            out.append(
                                gr.update(
                                    value=common.render_note(REQUEST_REFUSED_NOTE), visible=True
                                )
                            )
                        elif outcome.request_json is not None:
                            out.append(gr.update(visible=False))
                        else:
                            out.append(gr.update())
                    elif name == "reproduce_note":
                        out.append(gr.update(visible=False) if outcome.snippets else gr.update())
                    elif name == "provenance":
                        out.append(gr.update())
                    elif shown[name] is None:
                        out.append(gr.update())
                    elif shown[name]:
                        out.append(gr.update(value=texts[name], visible=True))
                    else:
                        out.append(gr.update(value="", visible=False))
                for index in range(MAX_FIELDS):
                    name = names[index] if index < len(names) else ""
                    reason = outcome.field_errors.get(name, "")
                    text = field_message(name, reason) if reason else ""
                    out.append(gr.update(value=common.render_field_message(text)))
                out.extend(common.LABEL_COPY for _ in copies)
                for following in (copy_of, caption_of):
                    for name in EDITOR_OUTPUTS:
                        if name in following:
                            state = shown[name]
                            out.append(gr.update() if state is None else gr.update(visible=state))
                yield tuple(out)

        # `.input`, never `.change`: a restore or the cascade's own writes fire `change`. The
        # guard state rides as the last input and the last output of every cascade event.
        family.input(
            on_family,
            [family, selection],
            [family, module, function, *change_outputs, selection],
            api_name=API_NAMES[0],
            **quiet,
        )
        module.input(
            on_module,
            [family, module, selection],
            [function, *change_outputs, selection],
            api_name=API_NAMES[1],
            **quiet,
        )
        function.input(
            on_function,
            [family, module, function, selection],
            [function, *change_outputs, selection],
            api_name=API_NAMES[2],
            **quiet,
        )
        restore.change(
            on_restore,
            [restore, selection],
            [family, module, function, *change_outputs, selection],
            api_name=False,
            **quiet,
        )
        run_outputs = [status, card, *editor_outputs, *(slot["message"] for slot in slots)]
        run_outputs += [button for button, _ in copies]
        run_outputs += editor_copies
        run_outputs += editor_captions
        run.click(
            on_run,
            [family, module, function, *flat_slot_inputs],
            run_outputs,
            api_name=API_NAMES[3],
            **hooks,
            **quiet,
        )
        for button, source in copies:
            button.click(None, [source], [button], js=common.COPY_JS, api_name=False, **quiet)
        return {
            "family": family,
            "module": module,
            "function": function,
            "doc": doc,
            "surface": surface,
            "slots": slots,
            "run": run,
            "status": status,
            "card": card,
            "request_json": request_json,
            "response_json": response_json,
            "request_note": request_note,
            "reproduce_note": reproduce_note,
            "provenance": provenance,
            "snippets": snippet_boxes,
            "permalink": permalink,
            "restore": restore,
            "selection": selection,
            "copies": [button for button, _ in copies],
            "captions": caption_of,
            "editor_outputs": editor_outputs,
            "editor_captions": editor_captions,
            "change_outputs": change_outputs,
            "on_family": on_family,
            "on_module": on_module,
            "on_function": on_function,
            "on_restore": on_restore,
            "on_run": on_run,
            # The shell's report hook, with the catalogue: what a link to this tab restores.
            "permalink_applied": lambda fn, args: applied_call(catalogue, fn, args),
        }

    return TabSpec(TAB_PLAY, "Playground", render, API_NAMES)


def _event_hooks() -> dict[str, Any]:
    from algenta_spaces.lane import gradio_hooks

    return gradio_hooks()["event"]


def slot_kinds() -> tuple[str, ...]:
    """The control kinds a slot can show, for tests and the shell's smoke inputs."""
    return KINDS_IN_SLOT


__all__ = [
    "API_NAMES",
    "CODE_UNKNOWN_FAMILY",
    "CODE_UNKNOWN_FUNCTION",
    "CODE_UNKNOWN_MODULE",
    "EDITOR_OUTPUTS",
    "MAX_FIELDS",
    "REQUEST_REFUSED_NOTE",
    "SLOT_COMPONENTS",
    "SLOT_OUTPUTS",
    "Catalogue",
    "EditorState",
    "Outcome",
    "SlotPlan",
    "applied_args",
    "applied_call",
    "build",
    "build_note",
    "collect_raw",
    "control_kwargs",
    "editor_state",
    "field_message",
    "function_doc",
    "hero_defaults",
    "is_filter",
    "parity_chip",
    "permalink_outputs",
    "permalink_restore",
    "refusal_card",
    "restore_target",
    "run_call",
    "selection_refusal",
    "slot_kinds",
    "slot_plans",
    "split_qualname",
    "subtitle_for",
]
