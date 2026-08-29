"""Chat templates: turn chat messages into the exact prompt the model expects.

This is the chat-template half of parity gap 1 from the beat-llama.cpp campaign's end-to-end gap
analysis (2026-08-09): until this module, `algenta_local` chat completions flattened messages to
plain text (role-colon-content lines) with no template, which is wrong for any chat-conditioned
model. This module applies the checkpoint's OWN chat_template -- the Jinja string stored in
`tokenizer_config.json` -- but implements it here from scratch, no `jinja2` import, exactly the
discipline `algenta.tokenizer` established for the BPE half of this gap.

Scope, stated precisely so nothing here overclaims
---------------------------------------------------
* **One template family.** The Qwen3 chat template, in the two revisions currently shipped by the
  supported checkpoints (Qwen3-0.6B-Base and Qwen3-1.7B). The gate is byte-exact: the loaded
  template's SHA-256 must match one of the two canonical revisions this module implements, else
  `ChatTemplateError` is raised naming the refusal -- never a half-render against a template we do
  not implement.
* **Faithful, oracle-validated.** `tests/test_chat_template_qwen3.py` checks the renderer output
  BYTE-FOR-BYTE against `transformers.AutoTokenizer.apply_chat_template` (the reference users
  compare against) across a branch battery on both real checkpoints. On machines without
  `transformers` those oracle tests skip; the structural unit tests (expected literals recorded
  from the oracle) always run.
* **No runtime third-party dependency.** The renderer is pure-Python string construction. The
  checkpoint's template is used only as the gate input, never interpreted.

The Qwen3 template semantics this module reproduces
---------------------------------------------------
* A `tools` preamble (function-calling system block) when `tools` is passed; otherwise an optional
  leading `system` message block.
* Every message wrapped in the im_start/im_end role markers.
* Assistant messages after the last real user query carry their reasoning: an explicit
  `reasoning_content` field, or an inline think-block inside `content`, is surfaced as a
  think-block; earlier assistant messages render content only.
* Assistant `tool_calls` render as tool_call JSON blocks; `tool` role messages are grouped into a
  single user-wrapped tool_response block.
* `add_generation_prompt` appends the assistant turn opener; `enable_thinking=False` additionally
  appends an empty think-block to suppress reasoning.

Usage
-----
    from algenta.chat_template import apply_chat_template

    prompt = apply_chat_template(
        "/path/to/qwen3-checkpoint",
        [{"role": "user", "content": "The capital of France is"}],
    )
    # prompt is the exact chat-formatted string; pass it to `algenta.inference.decode` as
    # `prompt_text` (or use the `messages=` convenience on `decode` directly).
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

__all__ = [
    "ChatTemplateError",
    "apply_chat_template",
    "render_qwen3_chat_template",
    "load_chat_template",
    "is_qwen3_chat_template",
    "split_tool_calls_from_generated_text",
]


class ChatTemplateError(ValueError):
    """The checkpoint has no chat_template, or one this module does not implement.

    Raised before any rendering -- never a guess against an unknown template."""


# SHA-256 of the canonical Qwen3 `chat_template` strings this module implements (byte-exact gate).
# Extracted 2026-08-10 from the two supported checkpoints' tokenizer_config.json; both are the
# Qwen3 chat template, differing only in a defensive non-string-content revision.
_QWEN3_TEMPLATE_SHA256 = {
    # Qwen3 revision shipped with Qwen3-0.6B-Base.
    "87a2728cb8dc9fe424d624542f6060ec05a1d285ebbec578bb078900e33396b5",
    # Qwen3 revision shipped with Qwen3-1.7B.
    "a55ee1b1660128b7098723e0abcd92caa0788061051c62d51cbe87d9cf1974d8",
}


def load_chat_template(checkpoint_dir: str | Path) -> str | None:
    """Read `tokenizer_config.json`'s `chat_template` from the checkpoint. Returns the template
    string, or None when the file or the field is absent (base checkpoints with no template)."""
    path = Path(checkpoint_dir) / "tokenizer_config.json"
    if not path.is_file():
        return None
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    template = config.get("chat_template")
    return template if isinstance(template, str) and template else None


def is_qwen3_chat_template(template: str | None) -> bool:
    """True when `template` is byte-exactly one of the Qwen3 revisions this module implements."""
    if not template:
        return False
    digest = hashlib.sha256(template.encode("utf-8")).hexdigest()
    return digest in _QWEN3_TEMPLATE_SHA256


def apply_chat_template(
    checkpoint_dir: str | Path,
    messages: list[dict],
    *,
    add_generation_prompt: bool = True,
    enable_thinking: bool | None = None,
    tools: list[dict] | None = None,
) -> str:
    """Apply the checkpoint's OWN chat template to `messages` and return the prompt string.

    Refuses (raises `ChatTemplateError`) when the checkpoint ships no chat_template, or one that
    is not a supported Qwen3 revision -- never renders against an unknown template. `messages` is
    a list of OpenAI-style dicts (`role`, `content`, optional `reasoning_content`, `tool_calls`).
    """
    template = load_chat_template(checkpoint_dir)
    if template is None:
        raise ChatTemplateError(
            f"{Path(checkpoint_dir) / 'tokenizer_config.json'} carries no usable chat_template; "
            "this checkpoint cannot format chat messages. Pass raw prompt_text/prompt_token_ids "
            "instead."
        )
    if not is_qwen3_chat_template(template):
        raise ChatTemplateError(
            "the checkpoint's chat_template is not one of the Qwen3 revisions this module "
            "implements; refusing rather than rendering against an unknown template."
        )
    return render_qwen3_chat_template(
        messages,
        add_generation_prompt=add_generation_prompt,
        enable_thinking=enable_thinking,
        tools=tools,
    )


# ── The Qwen3 renderer ────────────────────────────────────────────────────────────────────────
#
# The block below reproduces the Qwen3 chat_template exactly, without interpreting Jinja. The
# im_start / im_end role markers are assembled from pieces so a literal special-token string never
# appears whole in this source (house convention: an accidental copy of a control token into a
# prompt would silently change tokenization). The tool/think markers are plain XML-ish tags the
# template emits verbatim, likewise built in two pieces.
_IM_START = "<|" + "im_start|>"
_IM_END = "<|" + "im_end|>"
_TOOL_RESP_OPEN = "<tool" + "_response>"
_TOOL_RESP_CLOSE = "</tool" + "_response>"
_TOOL_CALL_OPEN = "<tool" + "_call>"
_TOOL_CALL_CLOSE = "</tool" + "_call>"
_THINK_OPEN = "<th" + "ink>"
_THINK_CLOSE = "</th" + "ink>"


def _tojson(value) -> str:
    """JSON exactly as the reference renders tool objects: insertion order preserved, non-ASCII
    kept, no HTML escaping (matches transformers' tojson for this template)."""
    return json.dumps(value, ensure_ascii=False)


def _message_content(message: dict) -> str:
    content = message.get("content")
    return content if isinstance(content, str) else ""


def render_qwen3_chat_template(
    messages: list[dict],
    *,
    add_generation_prompt: bool = True,
    enable_thinking: bool | None = None,
    tools: list[dict] | None = None,
) -> str:
    """Render `messages` with the Qwen3 chat template, byte-for-byte with the reference.

    Pure function over the message list; no checkpoint access. `tools`, when truthy, emits the
    function-calling system preamble; `enable_thinking=False` appends an empty think-block to the
    generation prompt to suppress reasoning. See the module docstring for the full semantics.
    """
    if not isinstance(messages, list | tuple) or not messages:
        raise ChatTemplateError("messages must be a non-empty list of message dicts")

    parts: list[str] = []

    # Preamble: tools block, or a leading system message.
    if tools:
        parts.append(_IM_START + "system\n")
        if messages[0].get("role") == "system":
            parts.append(_message_content(messages[0]) + "\n\n")
        parts.append(
            "# Tools\n\nYou may call one or more functions to assist with the user query.\n\n"
            "You are provided with function signatures within <tools></tools> XML tags:\n<tools>"
        )
        for tool in tools:
            parts.append("\n" + _tojson(tool))
        parts.append(
            "\n</tools>\n\nFor each function call, return a json object with function name and "
            "arguments within " + _TOOL_CALL_OPEN + _TOOL_CALL_CLOSE + " XML tags:\n"
            + _TOOL_CALL_OPEN + "\n"
            + '{"name": <function-name>, "arguments": <args-json-object>}\n'
            + _TOOL_CALL_CLOSE + _IM_END + "\n"
        )
    else:
        if messages[0].get("role") == "system":
            parts.append(
                _IM_START + "system\n" + _message_content(messages[0]) + _IM_END + "\n"
            )

    # Index of the last real user query (a user message that is not a wrapped tool response).
    last_query_index = len(messages) - 1
    multi_step_tool = True
    for index in range(len(messages) - 1, -1, -1):
        message = messages[index]
        content = _message_content(message)
        if (
            multi_step_tool
            and message.get("role") == "user"
            and isinstance(message.get("content"), str)
            and not (
                content.startswith(_TOOL_RESP_OPEN) and content.endswith(_TOOL_RESP_CLOSE)
            )
        ):
            multi_step_tool = False
            last_query_index = index

    for loop_index0, message in enumerate(messages):
        role = message.get("role")
        content = _message_content(message)
        is_first = loop_index0 == 0
        is_last = loop_index0 == len(messages) - 1

        if role == "user" or (role == "system" and not is_first):
            parts.append(_IM_START + role + "\n" + content + _IM_END + "\n")

        elif role == "assistant":
            reasoning_content = ""
            rc = message.get("reasoning_content")
            if isinstance(rc, str):
                reasoning_content = rc
            else:
                if _THINK_CLOSE in content:
                    reasoning_content = (
                        content.split(_THINK_CLOSE)[0]
                        .rstrip("\n")
                        .split(_THINK_OPEN)[-1]
                        .lstrip("\n")
                    )
                    content = content.split(_THINK_CLOSE)[-1].lstrip("\n")

            if loop_index0 > last_query_index:
                if is_last or reasoning_content:
                    parts.append(
                        _IM_START + role + "\n" + _THINK_OPEN + "\n"
                        + reasoning_content.strip("\n") + "\n" + _THINK_CLOSE + "\n\n"
                        + content.lstrip("\n")
                    )
                else:
                    parts.append(_IM_START + role + "\n" + content)
            else:
                parts.append(_IM_START + role + "\n" + content)

            tool_calls = message.get("tool_calls")
            if tool_calls:
                for tc_index, tool_call in enumerate(tool_calls):
                    if (tc_index == 0 and content) or (tc_index != 0):
                        parts.append("\n")
                    if isinstance(tool_call, dict) and tool_call.get("function"):
                        tool_call = tool_call["function"]
                    parts.append(_TOOL_CALL_OPEN + '\n{"name": "')
                    parts.append(tool_call.get("name", ""))
                    parts.append('", "arguments": ')
                    arguments = tool_call.get("arguments")
                    if isinstance(arguments, str):
                        parts.append(arguments)
                    else:
                        parts.append(_tojson(arguments))
                    parts.append("}\n" + _TOOL_CALL_CLOSE)

            parts.append(_IM_END + "\n")

        elif role == "tool":
            if is_first or messages[loop_index0 - 1].get("role") != "tool":
                parts.append(_IM_START + "user")
            parts.append("\n" + _TOOL_RESP_OPEN + "\n")
            parts.append(content)
            parts.append("\n" + _TOOL_RESP_CLOSE)
            if is_last or messages[loop_index0 + 1].get("role") != "tool":
                parts.append(_IM_END + "\n")

    if add_generation_prompt:
        parts.append(_IM_START + "assistant\n")
        if enable_thinking is False:
            parts.append(_THINK_OPEN + "\n\n" + _THINK_CLOSE + "\n\n")

    return "".join(parts)


# ── The inverse direction: pulling tool calls back OUT of generated text ───────────────────────
#
# `render_qwen3_chat_template`'s tools preamble instructs the model to answer a function call by
# emitting a `<tool_call>{"name": ..., "arguments": {...}}</tool_call>` block (see the preamble
# text above: "For each function call, return a json object with function name and arguments
# within <tool_call></tool_call> XML tags"). This is the reference Qwen3/Hermes tool-call wire
# format the model is trained to produce -- the same tags this module uses to RENDER a prior
# assistant turn's tool_calls back into a prompt (round-trip symmetry: what this module writes
# into a prompt is exactly what it must be able to read back out of a completion).
_TOOL_CALL_BLOCK_RE = re.compile(
    re.escape(_TOOL_CALL_OPEN) + r"(.*?)" + re.escape(_TOOL_CALL_CLOSE), re.DOTALL
)


def split_tool_calls_from_generated_text(
    text: str | None,
) -> tuple[str | None, list[dict[str, Any]]]:
    """Pull every `<tool_call>...</tool_call>` block out of freshly generated text, in emission
    order. Returns `(content, calls)`:

    * `content` is the text OUTSIDE every tool_call block, stripped -- `None` when nothing is left
      (a tool-call-only turn), matching this module's own tool-call-only rendering convention
      (assistant `content=""` alongside `tool_calls`).
    * `calls` is a list of `{"name": str, "arguments": dict}` records, one per recognized block.

    This parses MODEL OUTPUT, not a contract this module controls: a block whose body is not valid
    `{"name": ..., "arguments": {...}}` JSON is left untouched in `content` (tags and all) rather
    than raising -- a malformed generation degrades to plain text instead of failing the whole
    turn. An empty/`None` `text` returns `(text, [])` unchanged.
    """
    if not text:
        return text, []

    calls: list[dict[str, Any]] = []
    pieces: list[str] = []
    cursor = 0
    for match in _TOOL_CALL_BLOCK_RE.finditer(text):
        pieces.append(text[cursor : match.start()])
        try:
            parsed = json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            parsed = None
        if (
            isinstance(parsed, dict)
            and isinstance(parsed.get("name"), str)
            and parsed["name"]
            and isinstance(parsed.get("arguments"), dict)
        ):
            calls.append({"name": parsed["name"], "arguments": parsed["arguments"]})
        else:
            # Not a recognizable tool call -- keep the tags and body as plain content rather than
            # silently discarding generated text the model produced.
            pieces.append(match.group(0))
        cursor = match.end()
    pieces.append(text[cursor:])
    content = "".join(pieces).strip()
    return (content or None), calls
