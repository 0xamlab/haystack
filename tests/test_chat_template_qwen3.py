"""`algenta.chat_template` is parity gap 1's chat-template increment: the checkpoint's OWN
`chat_template` (the Qwen3 Jinja template) applied from scratch -- no `jinja2` import -- so chat
messages become the exact prompt the model expects. Like `algenta.tokenizer`, "from scratch" only
means something if it is checked against the reference, so this file has two halves:

* STRUCTURAL tests (always run): the renderer's branch behavior on hand-recorded expected outputs,
  the SHA-256 template gate, the loader, and the refusal contract -- none need a checkpoint or any
  third-party package.
* ORACLE tests (skip unless the machine has a real Qwen3 snapshot AND `transformers`): the
  renderer must be BYTE-IDENTICAL to `transformers.AutoTokenizer.apply_chat_template` across a
  branch battery on both checkpoints, and the end-to-end token ids must match too. Same
  skip-unless-present convention `test_tokenizer_qwen3.py` established: the checkpoint is the
  README-documented manual download, never fetched by a test.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_ALGENTA = ROOT / "packages" / "algenta"
if str(_ALGENTA) not in sys.path:
    sys.path.insert(0, str(_ALGENTA))

from algenta.chat_template import (  # noqa: E402
    ChatTemplateError,
    apply_chat_template,
    is_qwen3_chat_template,
    load_chat_template,
    render_qwen3_chat_template,
)

# Special-token markers, built by concatenation so a literal control token never sits in this
# source (same convention as test_tokenizer_qwen3.py).
_IM_S = "<|" + "im_start|>"
_IM_E = "<|" + "im_end|>"
_TOOL_CALL_O = "<tool" + "_call>"
_TOOL_CALL_C = "</tool" + "_call>"
_TOOL_RESP_O = "<tool" + "_response>"
_TOOL_RESP_C = "</tool" + "_response>"
_THINK_O = "<th" + "ink>"
_THINK_C = "</th" + "ink>"


# ── structural: always run ─────────────────────────────────────────────────────────────────────


def test_empty_messages_refused() -> None:
    with pytest.raises(ChatTemplateError):
        render_qwen3_chat_template([])
    with pytest.raises(ChatTemplateError):
        render_qwen3_chat_template("not a list")  # type: ignore[arg-type]


def test_simple_user_with_generation_prompt() -> None:
    out = render_qwen3_chat_template([{"role": "user", "content": "The capital of France is"}])
    assert out == (
        _IM_S + "user\nThe capital of France is" + _IM_E + "\n" + _IM_S + "assistant\n"
    )


def test_simple_user_without_generation_prompt() -> None:
    out = render_qwen3_chat_template(
        [{"role": "user", "content": "The capital of France is"}],
        add_generation_prompt=False,
    )
    assert out == _IM_S + "user\nThe capital of France is" + _IM_E + "\n"


def test_system_user_multi_turn() -> None:
    out = render_qwen3_chat_template(
        [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "What is 2+2?"},
            {"role": "assistant", "content": "4"},
            {"role": "user", "content": "And 3+3?"},
        ]
    )
    assert out == (
        _IM_S + "system\nYou are helpful." + _IM_E + "\n"
        + _IM_S + "user\nWhat is 2+2?" + _IM_E + "\n"
        + _IM_S + "assistant\n4" + _IM_E + "\n"
        + _IM_S + "user\nAnd 3+3?" + _IM_E + "\n"
        + _IM_S + "assistant\n"
    )


def test_enable_thinking_false_appends_empty_think_block() -> None:
    out = render_qwen3_chat_template(
        [{"role": "user", "content": "hi"}], enable_thinking=False
    )
    assert out == (
        _IM_S + "user\nhi" + _IM_E + "\n"
        + _IM_S + "assistant\n" + _THINK_O + "\n\n" + _THINK_C + "\n\n"
    )


def test_enable_thinking_true_or_default_no_think_block() -> None:
    default = render_qwen3_chat_template([{"role": "user", "content": "hi"}])
    true = render_qwen3_chat_template(
        [{"role": "user", "content": "hi"}], enable_thinking=True
    )
    assert default == true == _IM_S + "user\nhi" + _IM_E + "\n" + _IM_S + "assistant\n"


def test_tool_call_with_dict_arguments_uses_tojson() -> None:
    out = render_qwen3_chat_template(
        [
            {"role": "user", "content": "weather?"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"function": {"name": "get_weather", "arguments": {"city": "Paris"}}}
                ],
            },
        ],
        add_generation_prompt=False,
    )
    # Insertion order preserved, no HTML escaping -- the reference's tojson for this template.
    assert (
        _TOOL_CALL_O + '\n{"name": "get_weather", "arguments": {"city": "Paris"}}\n' + _TOOL_CALL_C
    ) in out


def test_tool_call_with_string_arguments_verbatim() -> None:
    out = render_qwen3_chat_template(
        [
            {"role": "user", "content": "q"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"function": {"name": "f", "arguments": '{"raw": true}'}}
                ],
            },
        ],
        add_generation_prompt=False,
    )
    assert _TOOL_CALL_O + '\n{"name": "f", "arguments": {"raw": true}}\n' + _TOOL_CALL_C in out


def test_tool_role_messages_grouped_into_single_response_block() -> None:
    out = render_qwen3_chat_template(
        [
            {"role": "user", "content": "two lookups"},
            {"role": "tool", "content": "result-a"},
            {"role": "tool", "content": "result-b"},
        ],
        add_generation_prompt=False,
    )
    # One user-wrapped block containing both responses, no repeated im_start between them.
    assert out == (
        _IM_S + "user\ntwo lookups" + _IM_E + "\n"
        + _IM_S + "user" + "\n" + _TOOL_RESP_O + "\nresult-a\n" + _TOOL_RESP_C
        + "\n" + _TOOL_RESP_O + "\nresult-b\n" + _TOOL_RESP_C + _IM_E + "\n"
    )


def test_reasoning_content_surfaced_for_assistant_after_last_query() -> None:
    out = render_qwen3_chat_template(
        [
            {"role": "user", "content": "q"},
            {"role": "assistant", "content": "ans", "reasoning_content": "thought here"},
        ],
        add_generation_prompt=False,
    )
    assert (
        _IM_S + "assistant\n" + _THINK_O + "\nthought here\n" + _THINK_C + "\n\nans"
    ) in out


def test_inline_think_split_for_assistant_after_last_query() -> None:
    out = render_qwen3_chat_template(
        [
            {"role": "user", "content": "q"},
            {"role": "assistant", "content": _THINK_O + "T" + _THINK_C + "A"},
        ],
        add_generation_prompt=False,
    )
    assert (
        _IM_S + "assistant\n" + _THINK_O + "\nT\n" + _THINK_C + "\n\nA"
    ) in out


def test_tools_preamble_emits_function_schemas() -> None:
    tools = [
        {
            "type": "function",
            "function": {"name": "get_weather", "description": "Get weather"},
        }
    ]
    out = render_qwen3_chat_template(
        [{"role": "user", "content": "weather in Paris?"}], tools=tools
    )
    assert out.startswith(_IM_S + "system\n# Tools\n\n")
    assert "<tools>" in out and "</tools>" in out
    # The schema is serialized with insertion order preserved.
    assert '"type": "function", "function": {"name": "get_weather"' in out
    assert out.endswith(_IM_S + "assistant\n")


def test_gate_refuses_none_empty_and_foreign_templates() -> None:
    assert is_qwen3_chat_template(None) is False
    assert is_qwen3_chat_template("") is False
    assert is_qwen3_chat_template("{% for m in messages %}{{ m }}{% endfor %}") is False


def test_load_chat_template_reads_and_defaults(tmp_path: Path) -> None:
    assert load_chat_template(tmp_path) is None  # no tokenizer_config.json
    (tmp_path / "tokenizer_config.json").write_text(
        json.dumps({"chat_template": "SOME-TEMPLATE"}), encoding="utf-8"
    )
    assert load_chat_template(tmp_path) == "SOME-TEMPLATE"
    # A missing/empty field yields None.
    (tmp_path / "tokenizer_config.json").write_text(json.dumps({}), encoding="utf-8")
    assert load_chat_template(tmp_path) is None


def test_apply_chat_template_refuses_missing_and_unsupported(tmp_path: Path) -> None:
    # No template at all.
    with pytest.raises(ChatTemplateError) as excinfo:
        apply_chat_template(tmp_path, [{"role": "user", "content": "hi"}])
    assert "no usable chat_template" in str(excinfo.value)
    # A template that is not a supported Qwen3 revision.
    (tmp_path / "tokenizer_config.json").write_text(
        json.dumps({"chat_template": "{% for m in messages %}{{ m.content }}{% endfor %}"}),
        encoding="utf-8",
    )
    with pytest.raises(ChatTemplateError) as excinfo:
        apply_chat_template(tmp_path, [{"role": "user", "content": "hi"}])
    assert "not one of the Qwen3 revisions" in str(excinfo.value)


def test_decode_messages_input_guards() -> None:
    """`decode()`'s new `messages` input: exactly-one-of validation and the unsupported-template
    refusal both fire client-side, before any runtime work."""
    from algenta.inference import InferenceError, decode

    with pytest.raises(InferenceError) as excinfo:
        decode(object(), checkpoint_dir="/nonexistent", messages=[])
    assert excinfo.value.code == "invalid_arguments"

    with pytest.raises(InferenceError) as excinfo:
        decode(
            object(),
            checkpoint_dir="/nonexistent",
            prompt_text="x",
            messages=[{"role": "user", "content": "hi"}],
        )
    assert excinfo.value.code == "invalid_arguments"

    # A checkpoint with no template refuses messages (never a guess).
    with pytest.raises(InferenceError) as excinfo:
        decode(
            object(),
            checkpoint_dir="/nonexistent-checkpoint-dir",
            messages=[{"role": "user", "content": "hi"}],
        )
    assert excinfo.value.code == "unsupported_chat_template"


# ── oracle: real checkpoints + transformers, skip-unless-present ───────────────────────────────


def _checkpoint_dirs() -> list[Path]:
    dirs = []
    for env_name, default in (
        ("ALGENTA_QWEN3_TEST_CHECKPOINT", Path("/private/tmp/qwen3-0.6b-base")),
        ("ALGENTA_QWEN3_TEST_CHECKPOINT_17B", Path("/private/tmp/qwen3-1.7b")),
    ):
        override = os.environ.get(env_name)
        candidate = Path(override) if override else default
        if (candidate / "tokenizer_config.json").is_file():
            dirs.append(candidate)
    return dirs


def _transformers():
    return pytest.importorskip("transformers", reason="the oracle cross-check needs transformers")


# Branch battery exercised against the reference.
_BATTERY = {
    "simple_user": [{"role": "user", "content": "The capital of France is"}],
    "system_user": [
        {"role": "system", "content": "Be brief."},
        {"role": "user", "content": "Hello."},
    ],
    "multi_turn": [
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "What is 2+2?"},
        {"role": "assistant", "content": "4"},
        {"role": "user", "content": "And 3+3?"},
    ],
    "no_system_user_first": [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
        {"role": "user", "content": "bye"},
    ],
    "assistant_reasoning_field": [
        {"role": "user", "content": "think hard"},
        {
            "role": "assistant",
            "content": "The answer is 42.",
            "reasoning_content": "I reasoned step by step.",
        },
        {"role": "user", "content": "thanks"},
    ],
    "assistant_inline_think": [
        {"role": "user", "content": "q"},
        {"role": "assistant", "content": _THINK_O + "inner thought" + _THINK_C + "\n\nFinal answer."},
        {"role": "user", "content": "next"},
    ],
    "tool_round_trip": [
        {"role": "user", "content": "What is the weather?"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"function": {"name": "get_weather", "arguments": {"city": "Paris"}}}
            ],
        },
        {"role": "tool", "content": '{"temp": 20}'},
        {"role": "assistant", "content": "It is 20 degrees."},
    ],
    "consecutive_tool": [
        {"role": "user", "content": "two lookups"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"function": {"name": "a", "arguments": {}}},
                {"function": {"name": "b", "arguments": {"x": 1}}},
            ],
        },
        {"role": "tool", "content": "result-a"},
        {"role": "tool", "content": "result-b"},
        {"role": "assistant", "content": "done"},
    ],
    "tool_response_user_msg": [
        {"role": "user", "content": "q"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"function": {"name": "f", "arguments": {}}}],
        },
        {"role": "user", "content": _TOOL_RESP_O + "ok" + _TOOL_RESP_C},
        {"role": "assistant", "content": "final"},
    ],
    "reasoning_after_last_query": [
        {"role": "user", "content": "q"},
        {"role": "assistant", "content": "ans", "reasoning_content": "thought here"},
    ],
    "tool_call_str_arguments": [
        {"role": "user", "content": "q"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"function": {"name": "f", "arguments": '{"raw": true}'}}],
        },
        {"role": "tool", "content": "r"},
    ],
}

_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get weather",
            "parameters": {
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_time",
            "description": "Get time",
            "parameters": {"type": "object", "properties": {"tz": {"type": "string"}}},
        },
    },
]


@pytest.mark.skipif(
    not _checkpoint_dirs(),
    reason="no Qwen3 snapshot with tokenizer_config.json on this machine (manual download)",
)
def test_render_byte_identical_to_transformers_oracle() -> None:
    """The honesty gate: for every battery case (x add_generation_prompt x enable_thinking) and a
    tools case, the from-scratch renderer must match transformers.apply_chat_template EXACTLY."""
    AutoTokenizer = _transformers().AutoTokenizer
    for model_dir in _checkpoint_dirs():
        ref = AutoTokenizer.from_pretrained(str(model_dir), trust_remote_code=True)
        for case, msgs in _BATTERY.items():
            for agp in (True, False):
                for et in (None, False):
                    mine = render_qwen3_chat_template(
                        msgs, add_generation_prompt=agp, enable_thinking=et
                    )
                    kwargs = {"tokenize": False, "add_generation_prompt": agp}
                    if et is not None:
                        kwargs["enable_thinking"] = et
                    theirs = ref.apply_chat_template(msgs, **kwargs)
                    assert mine == theirs, (
                        f"{model_dir.name}: render mismatch on {case} agp={agp} et={et}"
                    )
        # tools preamble
        for agp in (True, False):
            mine = render_qwen3_chat_template(
                [{"role": "user", "content": "weather in Paris?"}],
                add_generation_prompt=agp,
                tools=_TOOLS,
            )
            theirs = ref.apply_chat_template(
                [{"role": "user", "content": "weather in Paris?"}],
                tokenize=False,
                add_generation_prompt=agp,
                tools=_TOOLS,
            )
            assert mine == theirs, f"{model_dir.name}: tools render mismatch agp={agp}"


@pytest.mark.skipif(
    not _checkpoint_dirs(),
    reason="no Qwen3 snapshot with tokenizer_config.json on this machine (manual download)",
)
def test_gate_accepts_real_qwen3_templates_and_apply_round_trips() -> None:
    for model_dir in _checkpoint_dirs():
        template = load_chat_template(model_dir)
        assert is_qwen3_chat_template(template), f"{model_dir.name} template not recognized"
        # apply_chat_template against the real checkpoint matches the bare renderer.
        msgs = [{"role": "user", "content": "The capital of France is"}]
        assert apply_chat_template(model_dir, msgs) == render_qwen3_chat_template(msgs)


@pytest.mark.skipif(
    not _checkpoint_dirs(),
    reason="no Qwen3 snapshot with tokenizer_config.json on this machine (manual download)",
)
def test_end_to_end_token_ids_match_transformers() -> None:
    """The full serving path: apply_chat_template -> algenta.tokenizer.encode must equal
    transformers.apply_chat_template(tokenize=True), so the GPU kernels see identical ids."""
    from algenta.tokenizer import load_tokenizer

    AutoTokenizer = _transformers().AutoTokenizer

    def _hf_ids(tok, msgs, agp):
        out = tok.apply_chat_template(
            msgs, tokenize=True, add_generation_prompt=agp, return_dict=False
        )
        if isinstance(out, dict):
            return list(out["input_ids"])
        if hasattr(out, "ids"):
            return list(out.ids)
        if isinstance(out, list) and out and hasattr(out[0], "ids"):
            return list(out[0].ids)
        return list(out)

    for model_dir in _checkpoint_dirs():
        mine_tok = load_tokenizer(model_dir)
        ref_tok = AutoTokenizer.from_pretrained(str(model_dir), trust_remote_code=True)
        for case in ("simple_user", "multi_turn", "tool_round_trip"):
            msgs = _BATTERY[case]
            for agp in (True, False):
                text = apply_chat_template(model_dir, msgs, add_generation_prompt=agp)
                assert mine_tok.encode(text) == _hf_ids(ref_tok, msgs, agp), (
                    f"{model_dir.name}: token-id mismatch on {case} agp={agp}"
                )
