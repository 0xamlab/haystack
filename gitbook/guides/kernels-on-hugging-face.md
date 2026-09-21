---
description: Load Algenta compute kernels on Apple silicon straight from the Hugging Face Kernel Hub with the kernels library.
icon: cubes
---

# Kernels on Hugging Face

Algenta publishes its compute kernels to the Hugging Face Kernel Hub under the `thyn-ai`
organization. Each repository is one kernel family: a compiled Mojo library, loaded in-process by
the `kernels` library, with a published contract and documentation for every function.

## Install

```bash
pip install kernels torch
```

```python
from kernels import get_kernel

stats = get_kernel(
    "thyn-ai/algenta-stats",
    version=1,
    backend="cpu",
    trust_remote_code=["thyn-ai/algenta-stats"],
)
stats.ab_testing.z_test_proportions(50, 1000, 65, 1000)  # -> [-1.4408, 0.1496]  z statistic, p-value
```

Plain Python in, plain Python out. Lists, tuples, buffers and tensors are accepted wherever the
contract expects a list; structured results are dictionaries. Every call is checked against the
published contract before it reaches native code. An invalid call raises `KernelError` with a stable
`code`, never a crash. `help(stats.ab_testing)` documents every function, with its defaults.

## Families

| Repository | What's inside | Backends |
|---|---|---|
| `thyn-ai/algenta-stats` | Statistics, probability, hypothesis testing, regression and sampling | CPU |
| `thyn-ai/algenta-llm` | LLM, attention, RoPE, embedding and KV-cache kernels, resident decode sessions | CPU · Metal |

More families follow the same layout. Each card lists its modules with a line on each, and
`kernel.CONTRACT` holds every signature.

## Resident decode on Apple silicon

The Metal build of `algenta-llm` runs greedy Qwen3-family decode on the GPU. One session is open
at a time; each step blocks until its token is computed and returns the token id.

```python
llm = get_kernel("thyn-ai/algenta-llm", version=1, trust_remote_code=["thyn-ai/algenta-llm"])
with llm.DecodeSession("/path/to/converted-checkpoint", prompt_token_ids, max_new_tokens=32) as session:
    tokens = list(session)
```

`prompt_token_ids` come from the checkpoint's own tokenizer. The checkpoint directory is the
converted form written by `prepare_model_checkpoint()`, described in
[Model-agnostic LLM inference](run-qwen3-family-inference.md). `llm.decode(...)` runs a whole
session in one call; `session.step()` returns the full record for one token. Decode needs the
Metal build; on the CPU build `DecodeSession` raises `KernelError("metal_required")`.

## Requirements

- Apple silicon: macOS 15 or later for CPU builds, macOS 26 or later for Metal.
- `kernels` 0.17 or later and PyTorch 2.5 to 2.14. PyTorch has to be installed: the loader picks
  the build for your PyTorch version. The kernels themselves never import it.
- `trust_remote_code` names the repositories you allow. `kernels` loads Hugging Face's trusted
  publishers by default; any other publisher needs its exact repository ID here.
- On a Mac the loader picks the Metal build when the family ships one and the system is macOS 26
  or later. Pass `backend="cpu"` for CPU-only families, and for every family on macOS 15.

Linux x86-64 and arm64 builds ship from the Algenta release pipeline. Windows is not supported.

## Terms

Every kernel repository carries the Algenta Community License 1.0: free for personal, research and
open-source use, and for internal use at organizations with fewer than 50 employees and under $5M
in annual revenue. Beyond that, a commercial license is required: licensing@algenta.ai.

## Next

{% content-ref url="run-qwen3-family-inference.md" %}
[run-qwen3-family-inference.md](run-qwen3-family-inference.md)
{% endcontent-ref %}

{% content-ref url="../engine/runtime-library-catalog.md" %}
[runtime-library-catalog.md](../engine/runtime-library-catalog.md)
{% endcontent-ref %}
