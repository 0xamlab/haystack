---
icon: gauge-high
description: Install Algenta, get a supported checkpoint, and run greedy decode on your own Apple Silicon GPU — requirements, limitations, and a complete working example. Currently tested on Qwen3 models.
---

# Run local LLM decode

By the end of this guide you will have installed Algenta, downloaded the one checkpoint this capability supports, tokenized a prompt, and run a real greedy decode through a compiled int8 Metal GPU kernel path — reading back the generated token ids on your own Apple Silicon machine. Everything runs inside the runtime that ships with the `algenta` package; there is nothing separate to start or manage.

This is a narrow, real capability, not a general LLM-serving surface. Read [Requirements](#requirements) and [Limitations](#limitations) before you start — this page is only about **Qwen3-0.6B-Base**, on **Apple Silicon with Metal**.

## Requirements

* **Apple Silicon (M-series) Mac with Metal.** There is no CPU fallback and no support for other GPU vendors. Metal is the only GPU backend that is RUN-verified today — NVIDIA CUDA compiles in CI but has never been launched on real hardware (it needs an NVIDIA driver ≥ 580 and a validation machine that does not exist yet), and AMD ROCm is not built. See the [GPU support matrix](../engine/qwen3-metal-decode.md#gpu-support-matrix).
* **Python 3.14** — `pip install algenta` requires it.
* **The exact checkpoint this kernel path was compiled for**: [`Qwen/Qwen3-0.6B-Base`](https://huggingface.co/Qwen/Qwen3-0.6B-Base) (Apache-2.0, ungated — no Hugging Face account or token needed). No other Qwen3 size and no other model family.
* **`numpy`**, to convert the checkpoint's published BF16 weights. Install it with the `benchmark` extra: `pip install "algenta[benchmark]"`.
* **A tokenizer for the checkpoint.** This capability takes token ids in and token ids out, not raw text — the example below uses `transformers`' `AutoTokenizer` against the same checkpoint directory.

## Limitations

* **One model, one exact shape.** Qwen3-0.6B-Base's exact architecture only (`hidden_size=1024`, 28 layers, 16 query heads, 8 key/value heads, `head_dim=128`, `vocab_size=151936`, tied embeddings). A checkpoint of any other shape is refused by name before any conversion or GPU work starts. Other Qwen3 sizes (for example Qwen3-1.7B) run through the model-agnostic path instead — see [Model-agnostic LLM inference](run-qwen3-family-inference.md).
* **One hardware family, run-verified.** Apple Silicon with Metal, and nothing else — the only GPU lane that has actually run. A host with no Metal accelerator gets a named refusal, never a slower silent substitute. (CUDA is compile-verified only and ROCm is not built — [GPU support matrix](../engine/qwen3-metal-decode.md#gpu-support-matrix).)
* **Greedy decode only.** Every generated token is the argmax at that step. There is no sampling, no temperature, no top-p/top-k, and no beam search.
* **One call, start to finish.** There is no session you open once and step token-by-token across separate calls — a single call prefills the prompt and decodes to `max_new_tokens` or an end-of-text token in one round trip.
* **Every call converts the checkpoint first.** The checkpoint's BF16 weights are converted into the kernel's own flat format on every call by default, which takes real time before decoding starts.
* **Not a chat template; token ids in.** This pinned path takes token ids, not raw text. Tokenize with the checkpoint's own tokenizer — either `algenta.load_tokenizer()` (built into the SDK, no dependencies) or `transformers`' `AutoTokenizer`; the example below shows the latter.

## Install Algenta

{% stepper %}
{% step %}
### Install the package

The `algenta` package installs the matching compiled native runtime automatically — there is no separate Mojo/Metal toolchain to install.

```bash
python3.14 -m venv .venv
source .venv/bin/activate
pip install "algenta[benchmark]"
```
{% endstep %}

{% step %}
### Verify the runtime is healthy

```bash
algenta runtime doctor
```

Expect a report that ends in `READY`, with the bundled native runtime verified and no fallback. If this does not say `READY`, resolve that first — nothing in the rest of this guide will run without it.
{% endstep %}
{% endstepper %}

## Get the checkpoint

This capability does not download anything for you — get your own copy of `Qwen/Qwen3-0.6B-Base` onto disk first, the same way you would for any other checkpoint:

```bash
pip install huggingface_hub
python3 -c "
from huggingface_hub import snapshot_download
snapshot_download(
    repo_id='Qwen/Qwen3-0.6B-Base',
    local_dir='./qwen3-0.6b-base',
    allow_patterns=['*.json', '*.safetensors', 'tokenizer*', 'vocab*', 'merges*'],
)
"
```

## Run a decode

{% stepper %}
{% step %}
### Tokenize your prompt

`qwen3_i8_allsimd7_decode()` takes a list of integer token ids, not a string. Tokenize with the checkpoint's own tokenizer:

```python title="tokenize_prompt.py"
from transformers import AutoTokenizer

tokenizer = AutoTokenizer.from_pretrained("./qwen3-0.6b-base")
prompt_token_ids = tokenizer("The capital of France is", return_tensors=None)["input_ids"]
```
{% endstep %}

{% step %}
### Call the decode function

`qwen3_i8_allsimd7_decode()` needs a `MojoRuntime` (so it can reach the bundled runtime), the checkpoint directory, your prompt token ids, and how many tokens to generate. It converts the checkpoint automatically the first time you call it.

```python title="run_decode.py"
from algenta import MojoRuntime, qwen3_i8_allsimd7_decode

runtime = MojoRuntime(mode="local")

result = qwen3_i8_allsimd7_decode(
    runtime,
    checkpoint_dir="./qwen3-0.6b-base",
    prompt_token_ids=prompt_token_ids,
    max_new_tokens=16,
)
```
{% endstep %}

{% step %}
### Read the result

`result` is a `Qwen3DecodeResult`: `token_ids` is your prompt followed by every generated token, in order.

```python title="read_result.py"
print(result.token_ids)
print(result.decode_tokens_per_sec)

generated_only = result.token_ids[result.n_prompt :]
print(tokenizer.decode(generated_only))
```
{% endstep %}
{% endstepper %}

{% hint style="success" %}
**Expected result** — `result.token_ids` is a non-empty list of integers starting with your prompt's own token ids, followed by up to `max_new_tokens` generated ids (fewer if the model produced an end-of-text token first). Decoding `generated_only` with the tokenizer reads as ordinary continuation text, and `result.decode_tokens_per_sec` is a positive number. If the call did not raise, generation happened — an empty result is never a silent, valid response.
{% endhint %}

## Troubleshooting

`qwen3_i8_allsimd7_decode()` never returns a plausible-looking wrong answer for a mismatch it can detect — it raises instead, by name:

| What you did | What you get |
| --- | --- |
| Pointed `checkpoint_dir` at a checkpoint that is not Qwen3-0.6B-Base's exact shape | `UnsupportedCheckpointArchitectureError`, naming every mismatched field, before any conversion or GPU work starts. |
| Pointed `checkpoint_dir` at a path with no `config.json` / `model.safetensors` | `Qwen3DecodeError` with code `checkpoint_not_found`. |
| Ran on a host, or a runtime build, without working Metal GPU support | `Qwen3DecodeError` with code `metaldispatch_shader_toolchain_absent`. |

Every one of these is a `Qwen3DecodeError` (or its subclass `UnsupportedCheckpointArchitectureError`), and every instance carries a stable `.code` string:

```python title="handle_errors.py"
from algenta import Qwen3DecodeError

try:
    result = qwen3_i8_allsimd7_decode(
        runtime,
        checkpoint_dir="./qwen3-0.6b-base",
        prompt_token_ids=prompt_token_ids,
        max_new_tokens=16,
    )
except Qwen3DecodeError as error:
    print(error.code, str(error))
```

## Next steps

{% content-ref url="run-qwen3-family-inference.md" %}
[Model-agnostic LLM inference](run-qwen3-family-inference.md)
{% endcontent-ref %}

{% content-ref url="../engine/qwen3-metal-decode.md" %}
[Metal LLM decode](../engine/qwen3-metal-decode.md)
{% endcontent-ref %}

{% content-ref url="../benchmarks/decode-throughput.md" %}
[decode-throughput.md](../benchmarks/decode-throughput.md)
{% endcontent-ref %}

{% content-ref url="../install.md" %}
[install.md](../install.md)
{% endcontent-ref %}
