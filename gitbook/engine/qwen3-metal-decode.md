---
icon: microchip
description: Greedy decode on Apple Silicon through the int8 Metal GPU kernel path — call surface, checkpoint preparation, refusals, verification. Currently tested on Qwen3 models.
---

# Metal LLM decode

`metaldispatch.qwen3_decode` runs Qwen3-0.6B-Base end to end on Apple Silicon through the compiled
int8-weight Metal kernel path (`_MBQwen3I8AllSimd7`): prompt in, generated token ids out, one call.
The kernels are compiled for this one architecture and hardware family. Measured throughput:
[Decode throughput](../benchmarks/decode-throughput.md).

The model-agnostic entry point on the same kernel family — any supported Qwen3-family shape, seeded
sampling, text in/text out — is `algenta.inference.decode`; see
[Model-agnostic LLM inference](../guides/run-qwen3-family-inference.md). `decode` is itself a Python
wrapper: it calls straight into `metaldispatch.qwen3_prefill_decode`'s
`qwen3_prefill_decode_flat_af_nomirror_msl_anyqwen3` (or its sampled/batched siblings), one of the
four modules this page documents.

## The modules

| Module | What it does |
| --- | --- |
| `metaldispatch.contract` | the status vocabulary this whole family shares (own range 620-639), plus the per-token GPU dispatch-count budget every session asserts its own dispatch count against before trusting a result |
| `metaldispatch.qwen3_decode` | the single-shot greedy decode arm documented above: one call, the prompt already baked into the checkpoint, weights re-uploaded every call, no batching |
| `metaldispatch.qwen3_prefill_decode` | the same decode arm with the prompt ingested through a batched `prefill_batch()` call instead of one `step()` per prompt token, plus the model-agnostic, sampled, and multi-sequence-batched variants built on top of it |
| `metaldispatch.session_prefill_policy` | resolves one attention-path + GEMM-tier + KV-cache-contract + decode-routing plan from a caller's request and this binary's own linked kernels — host-side logic only, no `library_execute` wire surface |

## GPU support matrix

The full matrix — every backend, verification status, and requirements — is
[GPU support](gpu-support.md). Summary for this page's entry point:

| Backend | Build status | Launch status | Requirements |
| --- | --- | --- | --- |
| Metal (Apple Silicon) | Run-verified, ships in the macOS runtime | Run-verified end to end on real hardware | An M-series Mac |
| CUDA (NVIDIA) | Portable kernel layer run-verified; native LLM session hardware-verified; CI compiles and links the lane on a builder with no GPU | Portable kernels run bit-exact on T4, L4 and A100; a separate CUDA-native resident session is measured on A100, L4, H100 and H200 — this Metal entry point is not that session | Linux runtime built with `-D ALGENTA_GPU -D ALGENTA_CUDA`, an NVIDIA driver >= 580 |
| ROCm (AMD) | Compile gate in progress | Not verified | — |

The CUDA lane runs the portable GPU kernels; the Metal batched-dispatch machinery documented on
this page is gated separately (`ALGENTA_METAL`). The CUDA lane includes a native resident session
(v2 prefill GEMMs + CUDA-graph decode) measured on A100, L4, H100 and H200; the SDK entry point on
this page is Metal-only. Install, requirements and entry points for the NVIDIA lane:
[CUDA backend](cuda-backend.md). Measured NVIDIA numbers:
[NVIDIA kernel benchmarks](../benchmarks/nvidia-kernel-benchmarks.md) (portable kernels) and
[NVIDIA LLM throughput](../benchmarks/nvidia-llm-throughput.md) (LLM session).

## Functions

| Function | What it does |
| --- | --- |
| `qwen3_i8_allsimd7_decode_flat(checkpoint_dir, max_new_tokens)` | Greedy-decodes the prompt already folded into the converted checkpoint's `manifest.json` through the GPU session (prefill, then per-token decode to the budget or end-of-text). Returns token ids, prefill/decode tok/s, and the per-token dispatch count. |
| `prepare_qwen3_checkpoint(checkpoint_dir, prompt_token_ids)` (SDK) | Converts a Hugging Face snapshot (`config.json` + `model.safetensors`) into the flat `manifest.json` + `weights.blob` pair the kernel reads, with the prompt folded in. |
| `qwen3_i8_allsimd7_decode(runtime, ...)` (SDK) | Python wrapper: converts when needed, calls the flat function through the bundled runtime, and maps engine statuses to named exceptions. |

```python
from algenta import MojoRuntime, qwen3_i8_allsimd7_decode

runtime = MojoRuntime(mode="local")
result = qwen3_i8_allsimd7_decode(
    runtime,
    checkpoint_dir="/path/to/Qwen3-0.6B-Base",   # your own downloaded HF snapshot
    prompt_token_ids=[785, 6722, 315, 9625, 374], # "The capital of France is"
    max_new_tokens=16,
)
result.token_ids                # prompt ids followed by generated ids
result.decode_tokens_per_sec
```

## Usage notes

* Checkpoint: download the snapshot yourself (`huggingface_hub.snapshot_download` with
  `repo_id="Qwen/Qwen3-0.6B-Base"`); nothing here fetches from the network. Pass
  `converted_checkpoint_dir` after a one-time `prepare_qwen3_checkpoint()` to skip re-converting
  on repeated calls.
* Tokens: this path takes token ids. Tokenize with `algenta.load_tokenizer(checkpoint_dir)`
  (built in, no dependencies) or `transformers.AutoTokenizer` against the same directory.
* One-shot shape: one call opens the session, uploads weights, prefills, and decodes. There is no
  open/step/close surface; the weights load on every call.
* Refusals: a checkpoint of any other shape raises `UnsupportedCheckpointArchitectureError` naming
  every mismatched field before any GPU work; a worker built without `-D ALGENTA_GPU` returns
  `metaldispatch_shader_toolchain_absent`; a host without a Metal accelerator returns
  `metaldispatch_no_device`; missing files return `checkpoint_not_found`. A successful return
  always contains generated token ids.

## Verification

* `prepare_qwen3_checkpoint` is checked byte-for-byte against the benchmark's own converter on a
  real checkpoint (`tests/test_qwen3_decode_checkpoint_conversion.py`).
* The GPU end-to-end path asserts the reference first token (374) and the reference continuation
  on the 256-token benchmark prompt (`tests/test_inference_gpu_e2e.py`).
* Every decode step asserts its dispatch count against the generated budget; a mismatch raises an
  error.

## Status codes and the dispatch budget (`metaldispatch.contract`)

`metaldispatch` owns status codes 620-639 — the same per-package ledger convention
`residentk.contract` established, so a code from this family is never confused with one from
`residentk` or any other kernel package. It exports exactly two functions, and imports no `std.gpu`
and links no shim object: a caller on any host, GPU or not, can ask "what does this status mean" and
"how many dispatches would one token cost" with no device and no shader compiler involved.

```python
runtime.execute("metaldispatch.contract", "metaldispatch_dispatch_budget", [28])["result"]
# 171 — Qwen3-0.6B-Base's 28 layers, at 6 dispatches per layer plus 3 fixed (n_layers*6 + 3);
# delegates to residentk.contract's own residentk_dispatch_budget rather than restating the formula

runtime.execute("metaldispatch.contract", "metaldispatch_status_name", [629])["result"]
# "metaldispatch_dispatch_count_mismatch" — the session built a different number of dispatch
# descriptors than metaldispatch_dispatch_budget(n_layers) says one token costs
```

`metaldispatch_dispatch_budget` is what `qwen3_i8_allsimd7_decode_flat` (this page's own entry point)
checks every decode step against, and what its `dispatches_per_token` result field reports back.
`metaldispatch_status_name` covers every code this family returns, including two `qwen3_decode`-only
additions layered onto the shared 620-639 range: `MB_ERR_CHECKPOINT_UNREADABLE` (631,
`metaldispatch_checkpoint_unreadable`) and `MB_ERR_UNSUPPORTED_ARCHITECTURE` (632,
`metaldispatch_unsupported_architecture`) — the two refusals this page's own Usage notes describe.
An unrecognized code returns `metaldispatch_code_out_of_range` rather than raising.

## The batched prefill+decode arm (`metaldispatch.qwen3_prefill_decode`)

Same scope statement as `qwen3_decode` above (Qwen3-family, greedy or seeded-sampled decode, Apple
Silicon Metal, refused by named status rather than silently downgraded) — with one structural
change: the prompt is ingested through `_MBQwen3I8AllSimd7Prefill.prefill_batch()` instead of a
`for t in range(n_prompt): s.step(...)` loop. One `prefill_batch()` call processes up to
`PREFILL_MAX_TILE` (2048) prompt rows in a single command buffer; a longer prompt runs in multiple
chunked calls, each writing the next slice of the KV cache at its own position offset — correctness
rests on the same argument the single-token path already relies on: every call depends only on the
KV cache and per-layer weights, which persist across calls on the same session instance, never on
the previous call's activation buffers.

`qwen3_i8_allsimd7_prefill_decode_flat(checkpoint_dir, max_new_tokens)` is the one function in this
module actually wired into the runtime dispatch catalog; it resolves its plan explicitly to
`PF_ATTN_OFF`/`PF_GEMM_ORIGINAL` (see the policy module below) and its `Qwen3PrefillDecodeResult`
carries every field `Qwen3DecodeResult` does, plus `prefill_chunks` — how many `prefill_batch()`
calls the run needed (1 for any prompt that fits in one tile). Around it sit explicit, named,
rollback-able kernel-tier choices, never a hidden default flip:

| Function | What it does |
| --- | --- |
| `qwen3_i8_allsimd7_prefill_decode_flat(checkpoint_dir, max_new_tokens)` | The wired entry point: batched prefill, `PF_ATTN_OFF`/`PF_GEMM_ORIGINAL`, prompt baked into the checkpoint's manifest. |
| `qwen3_i8_allsimd7_prefill_decode_flat_af(checkpoint_dir, max_new_tokens, use_native_grouped_fa_attn)` | Opt-in to the with-mirror grouped-FlashAttention prefill tier (populates both KV representations; decode still routes through the legacy path). |
| `qwen3_i8_allsimd7_prefill_decode_flat_af_vecload4(checkpoint_dir, max_new_tokens, use_native_grouped_fa_attn, use_vecload4_all_roles, warmup_prefills)` | With-mirror attention + the vecload4 GEMM tier for all four prefill GEMM roles. |
| `qwen3_i8_allsimd7_prefill_decode_flat_af_msl(checkpoint_dir, max_new_tokens, use_native_grouped_fa_attn, use_msl_parity_all_roles)` | With-mirror attention + the MSL-parity GEMM tier. |
| `qwen3_i8_allsimd7_prefill_decode_flat_af_nomirror(checkpoint_dir, max_new_tokens, use_native_grouped_fa_attn_no_mirror, use_qkv_proj_bm64)` | The mirror-free grouped-FA tier — only the packed-F16 KV representation is populated — plus the BM64 GEMM tier. |
| `qwen3_i8_allsimd7_prefill_decode_flat_af_nomirror_vecload4(checkpoint_dir, max_new_tokens, use_native_grouped_fa_attn_no_mirror, use_qkv_proj_bm64, use_vecload4_all_roles)` | Mirror-free attention + vecload4 GEMM — the fastest prefill-only shape measured, but decode collapses without a split-K decode kernel linked. |
| `qwen3_i8_allsimd7_prefill_decode_flat_af_nomirror_msl(checkpoint_dir, max_new_tokens, use_native_grouped_fa_attn_no_mirror, use_msl_parity_all_roles, warmup_prefills)` | Mirror-free attention + MSL-parity GEMM. |
| `qwen3_prefill_decode_flat_af_nomirror_msl_anyqwen3(checkpoint_dir, max_new_tokens, use_native_grouped_fa_attn_no_mirror, use_msl_parity_all_roles, wire_prompt_ids, warmup_prefills)` | The model-agnostic arm — any structurally-valid Qwen3-family checkpoint, not only Qwen3-0.6B-Base, prompt sent over the wire instead of baked into the manifest. **This is what `algenta.inference.decode` calls by default.** |
| `qwen3_prefill_decode_flat_af_nomirror_msl_anyqwen3_sampled(checkpoint_dir, max_new_tokens, temperature, top_k, top_p, min_p, repeat_penalty, presence_penalty, frequency_penalty, seed, wire_prompt_ids)` | Same arm, sampled instead of greedy; `temperature <= 0` delegates back to the greedy twin, and `top_k = 1` must reproduce the greedy token sequence exactly. |
| `qwen3_batched_prefill_decode_anyqwen3(checkpoint_dir, max_new_tokens, use_msl_parity_all_roles, wire_prompt_ids, prompt_lens)` | Up to `BATCH_DECODE_MAX_SEQS` (32) sequences share one weight sweep per decode step; forces the mirror-free plan, the only one paired with the batched decode caches. |

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")
envelope = runtime.execute(
    "metaldispatch.qwen3_prefill_decode",
    "qwen3_prefill_decode_flat_af_nomirror_msl_anyqwen3",
    [
        "/path/to/converted-checkpoint", 16,   # checkpoint_dir, max_new_tokens
        True, True,                            # use_native_grouped_fa_attn_no_mirror, use_msl_parity_all_roles
        [785, 6722, 315, 9625, 374],            # wire_prompt_ids — "The capital of France is"
        0,                                      # warmup_prefills
    ],
)
result = envelope["result"]
result["token_ids"]              # prompt ids followed by generated ids
result["prefill_chunks"]         # 1 — this 5-token prompt fits in one prefill_batch() call
```

This is byte-for-byte the wire call `algenta.inference.decode(runtime, checkpoint_dir=..., prompt_token_ids=..., max_new_tokens=16)`
makes under its own defaults (`use_native_grouped_fa_attn_no_mirror=True`,
`use_msl_parity_all_roles=True`).

The GPU-verified golden vector for this family (`test_metaldispatch_session_prefill.mojo`, a
2-layer/32-dim toy shape, not the 0.6B production shape) pins the prefill dispatch count exactly:
prefilling 4 rows through the `PF_ATTN_OFF` plan issues `1 + n_layers * 8 + 2` GPU dispatches —
19 for its 2-layer model — and the batched result's token id and logit agree with a frozen
Float64 CPU reference (the same oracle composition `qwen3_decode`'s own verification uses) to
within the int8 quantization bound; `step()` calls made on the same session after `prefill_batch()`
continue correctly from `pos = pos_base + m_rows`, checked against the same CPU reference at every
subsequent position. The same file also drives two defensive-check gates directly: forcing
`session.plan` past the public API into the unresolved sentinel (the only way that value can ever
reach the field, since neither the constructor nor `resolve_plan` ever produce one), and into a
self-contradictory plan — a real attention value paired with a KV-contract/decode-routing pair it
can never actually derive — and confirms `prefill_batch()` raises for both instead of silently
dispatching, then that a subsequent explicit `resolve_plan()` call recovers normal dispatch on the
same instance.

## Resolving one session execution plan (`metaldispatch.session_prefill_policy`)

This module holds no GPU code and has no `library_execute` surface — it is pure host-side policy
logic that `metaldispatch.session_prefill` calls directly to decide, once per session, which
compiled kernel each of four roles (attention, GEMM, KV-cache representation, decode routing)
should use.

It exists to fix a real, twice-reproduced class of bug: an earlier design represented the prefill
dispatch choice as several independent `Bool` flags (`use_native_grouped_fa_attn`,
`use_native_grouped_fa_attn_no_mirror`, `use_qkv_proj_bm64`, `use_vecload4_all_roles`) that could
hold a mutually contradictory combination at the same time, with no way to tell "the caller asked
for this" apart from "this is just sitting at whatever the constructor's own default happens to be
today." Flipping one flag's default once broke two unrelated test suites for exactly that reason.
The first fix collapsed `attention`/`gemm` into one resolved value each — closed, mutually
exclusive sets, so a single `Int` field cannot hold two contradictory requests at once. A later
pass found a further, orthogonal gap: `attention` alone does not just pick a prefill kernel, it also
obligates which persistent KV-cache representation every *decode* call on that same session must
read afterward — and nothing in the type caught a mismatch between the two. `kv_contract` and
`decode` were added to `ResolvedSessionExecutionPlan` to close it, and neither is ever a caller
request: both are *derived*, deterministically, from `attention` alone — there is no constructor
argument on `UnresolvedPrefillConfig` that lets a caller set either one directly, so a mismatched
pairing (a mirror-free attention path resolved next to the natural-F32, mirror-only decode routing)
cannot be constructed through the public API at all.

`resolve_prefill_execution_plan` is the one place the graceful-degrade rule lives: an explicit
request for a path whose kernels are linked into this binary is always honored; a request whose
kernels are absent degrades to the documented fallback — never a hard error, never silently
overridden by a different path's own default. `ResolvedSessionExecutionPlan.is_resolved()` re-derives
`kv_contract`/`decode` from `attention` and compares, so even a direct field mutation that lands on
individually-valid-but-mismatched constants (Mojo 1.0.0b2 has no cross-module private-field
enforcement) is caught before a dispatch call trusts it.

Two resolutions, hand-verified in `test_metaldispatch_session_prefill_policy.mojo`:

```mojo
resolve_prefill_execution_plan(
    UnresolvedPrefillConfig(PF_ATTN_GROUPED_FA_NO_MIRROR, PF_GEMM_ORIGINAL),
    True, False, False, False, False,   # af_grouped_fa_available=True, everything else absent
)
# -> attention=PF_ATTN_GROUPED_FA_NO_MIRROR, kv_contract=KV_CONTRACT_PACKED_F16_NATIVE,
#    decode=DECODE_PATH_NATIVE_PACKED_KV — the request is honored, and the derived fields agree

resolve_prefill_execution_plan(
    UnresolvedPrefillConfig(PF_ATTN_GROUPED_FA_NO_MIRROR, PF_GEMM_ORIGINAL),
    False, False, False, False, False,  # the same request, but no optional kernels linked at all
)
# -> attention=PF_ATTN_OFF, kv_contract=KV_CONTRACT_NATURAL_F32,
#    decode=DECODE_PATH_LEGACY_NATURAL_KV — graceful degrade to the always-available path
```

The second call is the round-5 guarantee stated as a check rather than only as prose: `kv_contract`
and `decode` always match what the *resolved* (possibly degraded) `attention` actually is, never
what the caller's original, un-degraded request would have implied. The same suite also confirms a
closest-capability-first refinement (`feat/llama-native-deep`, 2026-08-13): a `PF_ATTN_GROUPED_FA_
NO_MIRROR` request that cannot resolve because its own kernels are absent lands on
`PF_ATTN_PARAMETRIC_NATIVE_DECODE` instead of falling straight to `PF_ATTN_OFF`, whenever that
plan's own kernels are available — the two share the same native-packed-KV decode routing, so it is
a closer match to the caller's intent than the plain off-path. This is the same
`parametric_native_decode` plan the [model support matrix](model-support-matrix.md) lists as the
served path for d64 Llama-family models like TinyLlama-1.1B and SmolLM2-360M-Instruct.

## Related

* [Decode throughput](../benchmarks/decode-throughput.md) — measured single-stream decode.
* [Batched decode throughput](../benchmarks/batched-decode-throughput.md) — multi-request
  workloads.
* [Model-agnostic LLM inference](../guides/run-qwen3-family-inference.md) — the model-agnostic
  guide.
* [Runtime libraries](runtime-libraries.md) — the same call over `POST /v1/libraries/execute`,
  `module=metaldispatch.qwen3_decode`.
