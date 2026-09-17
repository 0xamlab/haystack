---
icon: microchip
description: The public inventory of the engine's CUDA and Metal kernels — what ships, per backend, per model family, and the evidence behind each module.
---

# Kernel inventory

The engine's racing kernels — the fused CUDA and Metal kernels a resident decode, prefill, or batched step is made of — are published here as a capability inventory. They are **not** runtime-library functions: their signatures take device pointers, which never cross a JSON frame, so they are declared, not callable. Every kernel that ships is listed; the inventory is generated from the engine sources and ratcheted, so a kernel can never silently disappear from the public surface.

## Surface at a glance

| Backend | Kernels | Model families | Staging tiers (elements) |
| --- | --- | --- | --- |
| CUDA (NVIDIA) | 141 | gemma3, qwen3/llama | 3072, 6144, 8192, 18944 |
| Metal (Apple Silicon) | 57 | qwen3/llama | 3072, 6144 |

Staging is the decode kernels' shared-memory ceiling per build tier — one binary per tier; a checkpoint whose staged vectors exceed every tier of a backend is refused naming the value and the tiers. See the [Model support matrix](model-support-matrix.md) for the fact ranges that decide support.

## CUDA (NVIDIA) kernels

| Kernel | Role | Family profile |
| --- | --- | --- |
| `native_kv_decode_splitk_partial_batched_f32_kernel_bg` | Decode attention (split-K flash-decoding / SDPA) | qwen3/llama |
| `g3_kv_decode_splitk_partial_batched_kernel` | Decode attention (split-K flash-decoding / SDPA) | gemma3 |
| `g3_kv_decode_splitk_partial_batched_kernel_kv16` | Decode attention (split-K flash-decoding / SDPA) | gemma3 |
| `g3_kv_decode_splitk_partial_batched_kernel_kv16_flash` | Decode attention (split-K flash-decoding / SDPA) | gemma3 |
| `sdpa_kernel_g` | Decode attention (split-K flash-decoding / SDPA) | qwen3/llama |
| `sdpa_kernel_simd_g` | Decode attention (split-K flash-decoding / SDPA) | qwen3/llama |
| `splitk_partial_kernel_simd_g` | Decode attention (split-K flash-decoding / SDPA) | qwen3/llama |
| `splitk_partial_batched_flash_kernel` | Decode attention (split-K flash-decoding / SDPA) | qwen3/llama |
| `splitk_partial_batched_flash_kernel_bg` | Decode attention (split-K flash-decoding / SDPA) | qwen3/llama |
| `g3_sdpa_window_kernel` | Decode attention (split-K flash-decoding / SDPA) | gemma3 |
| `g3_splitk_partial_kernel_simd_g` | Decode attention (split-K flash-decoding / SDPA) | gemma3 |
| `p3_dequant_rows_kernel` | Dequantize / unpack | qwen3/llama |
| `pf_embed_rows_kernel_bg` | Embedding gather | qwen3/llama |
| `embed_row_kernel_f16_g` | Embedding gather | qwen3/llama |
| `embed_row_kernel_g` | Embedding gather | qwen3/llama |
| `g3_embed_row_kernel` | Embedding gather | gemma3 |
| `g3_embed_row_kernel_f16` | Embedding gather | gemma3 |
| `g3_embed_row_kernel_f16_g` | Embedding gather | gemma3 |
| `pf_embed_rows_kernel_f16` | Embedding gather | qwen3/llama |
| `pf_embed_rows_kernel` | Embedding gather | qwen3/llama |
| `pf_embed_rows_g3_kernel` | Embedding gather | gemma3 |
| `pf_embed_rows_g3_kernel_f16` | Embedding gather | gemma3 |
| `batched_p3_swiglu_kernel` | FFN activation combine (SwiGLU / GeGLU) | qwen3/llama |
| `pf_geglu_rows_f16_kernel` | FFN activation combine (SwiGLU / GeGLU) | gemma3 |
| `pf_geglu_rows_kernel` | FFN activation combine (SwiGLU / GeGLU) | gemma3 |
| `pf_swiglu_rows_f16_kernel` | FFN activation combine (SwiGLU / GeGLU) | gemma3 |
| `pf_swiglu_rows_kernel` | FFN activation combine (SwiGLU / GeGLU) | qwen3/llama |
| `g3_norm_gemv2_geglu_kernel` | FFN gate/up projection + norm | gemma3 |
| `g3_norm_gemv2_geglu_kernel_f16` | FFN gate/up projection + norm | gemma3 |
| `g3_norm_gemv2_geglu_kernel_f16_u4` | FFN gate/up projection + norm | gemma3 |
| `norm_gemv2_swiglu_kernel_p3` | FFN gate/up projection + norm | qwen3/llama |
| `norm_gemv2_swiglu_kernel_p3_v2` | FFN gate/up projection + norm | qwen3/llama |
| `norm_gemv2_swiglu_kernel_p3_v3` | FFN gate/up projection + norm | qwen3/llama |
| `norm_gemv2_swiglu_kernel_p3_v4` | FFN gate/up projection + norm | qwen3/llama |
| `pf_attn_flash_kernel` | Flash-style attention | qwen3/llama |
| `pf_attn_flash2_kernel` | Flash-style attention | qwen3/llama |
| `graph_advance_batched_kernel` | CUDA graph advance | qwen3/llama |
| `graph_advance_kernel` | CUDA graph advance | qwen3/llama |
| `native_kv_producer_batched_f32_kernel_bg` | KV-cache producer | qwen3/llama |
| `batched_lmhead_argmax_kernel_f32` | LM head + argmax | qwen3/llama |
| `g3_batched_lmhead_argmax_kernel_f16` | LM head + argmax | gemma3 |
| `g3_logits_argmax_kernel` | LM head + argmax | gemma3 |
| `batched_lmhead_argmax_kernel_p3` | LM head + argmax | qwen3/llama |
| `lmhead_argmax_kernel_p3` | LM head + argmax | qwen3/llama |
| `lmhead_argmax_kernel_p3_v2` | LM head + argmax | qwen3/llama |
| `lmhead_argmax_kernel_p3_v3` | LM head + argmax | qwen3/llama |
| `g3_norm_accum_kernel` | Norm / RMSNorm rows | gemma3 |
| `g3_norm_inplace_kernel` | Norm / RMSNorm rows | gemma3 |
| `pf_norm_accum_rows_kernel` | Norm / RMSNorm rows | gemma3 |
| `pf_rmsnorm_rows_f16_kernel` | Norm / RMSNorm rows | gemma3 |
| `pf_fill_scale_kernel` | Utility | gemma3 |
| `pf_row_copy_kernel` | Utility | gemma3 |
| `p3g_log_head_copy_kernel` | Utility | qwen3/llama |
| `pf_attn_window_flash_kernel` | Prefill attention (tiled / windowed) | gemma3 |
| `pf_attn_window_flash_kernel_h` | Prefill attention (tiled / windowed) | gemma3 |
| `pf_attn_window_kernel` | Prefill attention (tiled / windowed) | gemma3 |
| `pf_attn_window_kernel_h` | Prefill attention (tiled / windowed) | gemma3 |
| `pf_gemm_accum_kernel_f16` | Prefill GEMM tile | qwen3/llama |
| `pf_gemm_assign_kernel_f16` | Prefill GEMM tile | qwen3/llama |
| `pf_gemm_swiglu_kernel_f16` | Prefill GEMM tile | qwen3/llama |
| `pf_gemm_accum_kernel` | Prefill GEMM tile | qwen3/llama |
| `pf_gemm_assign_kernel` | Prefill GEMM tile | qwen3/llama |
| `pf_gemm_swiglu_kernel` | Prefill GEMM tile | qwen3/llama |
| `pf_gemm_accum_kernel_v2` | Prefill GEMM tile | qwen3/llama |
| `pf_gemm_assign_kernel_v2` | Prefill GEMM tile | qwen3/llama |
| `pf_gemm_swiglu_kernel_v2` | Prefill GEMM tile | qwen3/llama |
| `pf_gemm_accum_kernel_v2n` | Prefill GEMM tile | qwen3/llama |
| `pf_gemm_accum_kernel_v3` | Prefill GEMM tile | qwen3/llama |
| `pf_gemm_accum_kernel_v3s` | Prefill GEMM tile | qwen3/llama |
| `pf_gemm_assign_kernel_v3` | Prefill GEMM tile | qwen3/llama |
| `pf_gemm_accum_kernel_v2h` | Prefill GEMM tile | gemma3 |
| `pf_gemm_assign_kernel_v2h` | Prefill GEMM tile | gemma3 |
| `pf_gemm_geglu_kernel_v2` | Prefill GEMM tile | gemma3 |
| `pf_gemm_geglu_kernel_v2h` | Prefill GEMM tile | gemma3 |
| `pf_gemm_accum_kernel_v2f16` | Prefill GEMM tile | qwen3/llama |
| `pf_gemm_assign_kernel_v2f16` | Prefill GEMM tile | qwen3/llama |
| `pf_gemm_swiglu_kernel_v2f16` | Prefill GEMM tile | qwen3/llama |
| `g3_gemv_kernel` | Fused norm + projection (QKV / O / FFN GEMV) | gemma3 |
| `g3_gemv_kernel_f16` | Fused norm + projection (QKV / O / FFN GEMV) | gemma3 |
| `norm_gemv_kernel_p3` | Fused norm + projection (QKV / O / FFN GEMV) | qwen3/llama |
| `norm_gemv_kernel_p3_v2` | Fused norm + projection (QKV / O / FFN GEMV) | qwen3/llama |
| `norm_gemv_kernel_p3_v3` | Fused norm + projection (QKV / O / FFN GEMV) | qwen3/llama |
| `packed3_gemv_kernel` | Fused norm + projection (QKV / O / FFN GEMV) | qwen3/llama |
| `packed3_gemv_kernel_v2` | Fused norm + projection (QKV / O / FFN GEMV) | qwen3/llama |
| `packed3_gemv_kernel_v3` | Fused norm + projection (QKV / O / FFN GEMV) | qwen3/llama |
| `batched_p3_gemv_accum_kernel` | Fused norm + projection (QKV / O / FFN GEMV) | qwen3/llama |
| `batched_p3_gemv_accum_kernel_r2` | Fused norm + projection (QKV / O / FFN GEMV) | qwen3/llama |
| `batched_p3_gemv_assign_kernel` | Fused norm + projection (QKV / O / FFN GEMV) | qwen3/llama |
| `batched_p3_gemv_assign_kernel_r2` | Fused norm + projection (QKV / O / FFN GEMV) | qwen3/llama |
| `packed3_gemv_accum_kernel` | Fused norm + projection (QKV / O / FFN GEMV) | qwen3/llama |
| `packed3_gemv_accum_kernel_v2` | Fused norm + projection (QKV / O / FFN GEMV) | qwen3/llama |
| `packed3_gemv_accum_kernel_v3` | Fused norm + projection (QKV / O / FFN GEMV) | qwen3/llama |
| `g3_ropewrt_batched_kernel` | RoPE + KV-cache write | gemma3 |
| `g3_ropewrt_batched_kernel_kv16` | RoPE + KV-cache write | gemma3 |
| `qk_rope_write_kernel_g` | RoPE + KV-cache write | qwen3/llama |
| `pf_biasropewrt_kernel` | RoPE + KV-cache write | gemma3 |
| `pf_biasropewrt_vec_kernel` | RoPE + KV-cache write | gemma3 |
| `pf_ropewrt_kernel_h` | RoPE + KV-cache write | gemma3 |
| `pf_ropewrt_warps_kernel` | RoPE + KV-cache write | gemma3 |
| `pf_ropewrt_warps_vec_kernel` | RoPE + KV-cache write | gemma3 |
| `tc_attn_softmax_mask_async` | Tensor-core shim (cuBLAS HMMA escape hatch) | qwen3/llama |
| `tc_bgemm_f16_async` | Tensor-core shim (cuBLAS HMMA escape hatch) | qwen3/llama |
| `tc_create_stream` | Tensor-core shim (cuBLAS HMMA escape hatch) | qwen3/llama |
| `tc_dequant_packed3_f16_dense` | Tensor-core shim (cuBLAS HMMA escape hatch) | qwen3/llama |
| `tc_fa2_causal_async` | Tensor-core shim (cuBLAS HMMA escape hatch) | qwen3/llama |
| `tc_fa2_causal_o16_async` | Tensor-core shim (cuBLAS HMMA escape hatch) | qwen3/llama |
| `tc_fa2_layout_probe` | Tensor-core shim (cuBLAS HMMA escape hatch) | qwen3/llama |
| `tc_fa_causal_async` | Tensor-core shim (cuBLAS HMMA escape hatch) | qwen3/llama |
| `tc_fa_g3_window2_async` | Tensor-core shim (cuBLAS HMMA escape hatch) | gemma3 |
| `tc_fa_g3_window3_async` | Tensor-core shim (cuBLAS HMMA escape hatch) | gemma3 |
| `tc_fa_g3_window_async` | Tensor-core shim (cuBLAS HMMA escape hatch) | gemma3 |
| `tc_fa_layout_probe` | Tensor-core shim (cuBLAS HMMA escape hatch) | qwen3/llama |
| `tc_gemm_dispatch` | Tensor-core shim (cuBLAS HMMA escape hatch) | qwen3/llama |
| `tc_gemm_dispatch_async` | Tensor-core shim (cuBLAS HMMA escape hatch) | qwen3/llama |
| `tc_gemm_dispatch_auto` | Tensor-core shim (cuBLAS HMMA escape hatch) | qwen3/llama |
| `tc_gemm_f16_16c_pre` | Tensor-core shim (cuBLAS HMMA escape hatch) | qwen3/llama |
| `tc_gemm_f16_16c_pre_async` | Tensor-core shim (cuBLAS HMMA escape hatch) | qwen3/llama |
| `tc_gemm_f16_16c_pre_lt` | Tensor-core shim (cuBLAS HMMA escape hatch) | qwen3/llama |
| `tc_gemm_f16_32c` | Tensor-core shim (cuBLAS HMMA escape hatch) | qwen3/llama |
| `tc_gemm_f16_32c_async` | Tensor-core shim (cuBLAS HMMA escape hatch) | qwen3/llama |
| `tc_gemm_f16_32c_pre` | Tensor-core shim (cuBLAS HMMA escape hatch) | qwen3/llama |
| `tc_gemm_f16_32c_pre_async` | Tensor-core shim (cuBLAS HMMA escape hatch) | qwen3/llama |
| `tc_gemm_f16_32c_pre_lt` | Tensor-core shim (cuBLAS HMMA escape hatch) | qwen3/llama |
| `tc_gemm_f16_acc16` | Tensor-core shim (cuBLAS HMMA escape hatch) | qwen3/llama |
| `tc_gemm_f16_assign` | Tensor-core shim (cuBLAS HMMA escape hatch) | qwen3/llama |
| `tc_gemm_tf32_beta` | Tensor-core shim (cuBLAS HMMA escape hatch) | qwen3/llama |
| `tc_init` | Tensor-core shim (cuBLAS HMMA escape hatch) | qwen3/llama |
| `tc_last_error` | Tensor-core shim (cuBLAS HMMA escape hatch) | qwen3/llama |
| `tc_lt_count` | Tensor-core shim (cuBLAS HMMA escape hatch) | qwen3/llama |
| `tc_lt_explore_begin` | Tensor-core shim (cuBLAS HMMA escape hatch) | qwen3/llama |
| `tc_lt_freeze` | Tensor-core shim (cuBLAS HMMA escape hatch) | qwen3/llama |
| `tc_lt_init` | Tensor-core shim (cuBLAS HMMA escape hatch) | qwen3/llama |
| `tc_lt_insitu_state` | Tensor-core shim (cuBLAS HMMA escape hatch) | qwen3/llama |
| `tc_lt_tune` | Tensor-core shim (cuBLAS HMMA escape hatch) | qwen3/llama |
| `tc_noseam` | Tensor-core shim (cuBLAS HMMA escape hatch) | qwen3/llama |
| `tc_stage_f32_to_f16` | Tensor-core shim (cuBLAS HMMA escape hatch) | qwen3/llama |
| `tc_stage_f32_to_f16_v8` | Tensor-core shim (cuBLAS HMMA escape hatch) | qwen3/llama |
| `tc_swiglu_f16_fastexp` | Tensor-core shim (cuBLAS HMMA escape hatch) | qwen3/llama |
| `tc_use_legacy_stream` | Tensor-core shim (cuBLAS HMMA escape hatch) | qwen3/llama |
| `tc_verify_o16` | Tensor-core shim (cuBLAS HMMA escape hatch) | qwen3/llama |
| `tc_verify_o16_report` | Tensor-core shim (cuBLAS HMMA escape hatch) | qwen3/llama |

## Metal (Apple Silicon) kernels

| Kernel | Role | Family profile |
| --- | --- | --- |
| `batched_splitk_merge_kernel_simd` | Decode attention (split-K flash-decoding / SDPA) | qwen3/llama |
| `sdpa_kernel` | Decode attention (split-K flash-decoding / SDPA) | qwen3/llama |
| `sdpa_kernel_kvf16` | Decode attention (split-K flash-decoding / SDPA) | qwen3/llama |
| `sdpa_kernel_simd` | Decode attention (split-K flash-decoding / SDPA) | qwen3/llama |
| `sdpa_kernel_simd_kvf16` | Decode attention (split-K flash-decoding / SDPA) | qwen3/llama |
| `splitk_merge_kernel_simd` | Decode attention (split-K flash-decoding / SDPA) | qwen3/llama |
| `splitk_partial_kernel_simd` | Decode attention (split-K flash-decoding / SDPA) | qwen3/llama |
| `splitk_partial_kernel_simd_batched4` | Decode attention (split-K flash-decoding / SDPA) | qwen3/llama |
| `splitk_partial_kernel_simd_native` | Decode attention (split-K flash-decoding / SDPA) | qwen3/llama |
| `embed_row_kernel` | Embedding gather | qwen3/llama |
| `embed_row_kernel_f16` | Embedding gather | qwen3/llama |
| `embed_row_kernel_i8` | Embedding gather | qwen3/llama |
| `pf_embed_rows_kernel_i8` | Embedding gather | qwen3/llama |
| `pf_swiglu_kernel_simd_i8` | FFN activation combine (SwiGLU / GeGLU) | qwen3/llama |
| `norm_gemv2_swiglu_kernel` | FFN gate/up projection + norm | qwen3/llama |
| `norm_gemv2_swiglu_kernel_f16` | FFN gate/up projection + norm | qwen3/llama |
| `norm_gemv2_swiglu_kernel_i4` | FFN gate/up projection + norm | qwen3/llama |
| `norm_gemv2_swiglu_kernel_i8` | FFN gate/up projection + norm | qwen3/llama |
| `norm_gemv2_swiglu_kernel_simd_i8` | FFN gate/up projection + norm | qwen3/llama |
| `argmax_reduce_kernel` | LM head + argmax | qwen3/llama |
| `argmax_reduce_kernel_simd` | LM head + argmax | qwen3/llama |
| `batched_argmax_reduce_kernel_simd` | LM head + argmax | qwen3/llama |
| `batched_lmhead_argmax_kernel_simd_i8` | LM head + argmax | qwen3/llama |
| `lmhead_argmax_kernel` | LM head + argmax | qwen3/llama |
| `lmhead_argmax_kernel_f16` | LM head + argmax | qwen3/llama |
| `lmhead_argmax_kernel_i8` | LM head + argmax | qwen3/llama |
| `lmhead_argmax_kernel_simd_i8` | LM head + argmax | qwen3/llama |
| `lmhead_logits_kernel_simd_i8` | LM head + argmax | qwen3/llama |
| `pf_rmsnorm_rows_kernel` | Norm / RMSNorm rows | qwen3/llama |
| `dump7b_copy_row_kernel` | Utility | qwen3/llama |
| `pf_attn8_kernel_simd` | Prefill attention (tiled / windowed) | qwen3/llama |
| `pf_attn_tiled_kernel_simd` | Prefill attention (tiled / windowed) | qwen3/llama |
| `pf_gemm_accum_kernel_i8` | Prefill GEMM tile | qwen3/llama |
| `pf_gemm_assign_kernel_i8` | Prefill GEMM tile | qwen3/llama |
| `pf_gemm_swiglu_kernel_i8` | Prefill GEMM tile | qwen3/llama |
| `pf_gnrw_accum_kernel_i8` | Prefill GEMM tile | qwen3/llama |
| `pf_gnrw_assign_kernel_i8` | Prefill GEMM tile | qwen3/llama |
| `pf_gnrw_swiglu_kernel_i8` | Prefill GEMM tile | qwen3/llama |
| `smalln_accum_kernel_simd_i8` | Prefill GEMM tile | qwen3/llama |
| `smalln_assign_kernel_simd_i8` | Prefill GEMM tile | qwen3/llama |
| `smalln_swiglu_kernel_simd_i8` | Prefill GEMM tile | qwen3/llama |
| `gemv_accum_kernel` | Fused norm + projection (QKV / O / FFN GEMV) | qwen3/llama |
| `gemv_accum_kernel_f16` | Fused norm + projection (QKV / O / FFN GEMV) | qwen3/llama |
| `gemv_accum_kernel_i4` | Fused norm + projection (QKV / O / FFN GEMV) | qwen3/llama |
| `gemv_accum_kernel_i8` | Fused norm + projection (QKV / O / FFN GEMV) | qwen3/llama |
| `gemv_accum_kernel_simd_i8` | Fused norm + projection (QKV / O / FFN GEMV) | qwen3/llama |
| `norm_gemv_kernel` | Fused norm + projection (QKV / O / FFN GEMV) | qwen3/llama |
| `norm_gemv_kernel_f16` | Fused norm + projection (QKV / O / FFN GEMV) | qwen3/llama |
| `norm_gemv_kernel_i4` | Fused norm + projection (QKV / O / FFN GEMV) | qwen3/llama |
| `norm_gemv_kernel_i8` | Fused norm + projection (QKV / O / FFN GEMV) | qwen3/llama |
| `norm_gemv_kernel_simd_i8` | Fused norm + projection (QKV / O / FFN GEMV) | qwen3/llama |
| `pf_gemv_accum_kernel_simd_i8` | Fused norm + projection (QKV / O / FFN GEMV) | qwen3/llama |
| `pf_qkv_proj_kernel_simd_i8` | Fused norm + projection (QKV / O / FFN GEMV) | qwen3/llama |
| `qkv_bias_add_rows_kernel` | Fused norm + projection (QKV / O / FFN GEMV) | qwen3/llama |
| `pf_ropewrt_kernel` | RoPE + KV-cache write | qwen3/llama |
| `qk_rope_write_kernel` | RoPE + KV-cache write | qwen3/llama |
| `qk_rope_write_kernel_kvf16` | RoPE + KV-cache write | qwen3/llama |

## Evidence by module

Each kernel module declares its own evidence in its `@capability-module` block: the golden vectors its correctness runs against and the benchmark it is raced under. The conformance battery gates every release on these paths.

| Module | Backend | Kernels | Golden vectors | Benchmark |
| --- | --- | --- | --- | --- |
| `residentk.kernels` | metal | 57 | `mojo/tests/libs/test_residentk_session.mojo` | `benchmarks/llm_smoke/qwen3_generate_metal.mojo` |
| `residentk.kernels_batched_cuda` | cuda | 1 | `benchmarks/llm_smoke/nvidia_race/qwen3_batched_cuda.mojo` | `benchmarks/llm_smoke/nvidia_race/qwen3_batched_cuda.mojo` |
| `residentk.kernels_batched_cuda_graph` | cuda | 4 | `benchmarks/llm_smoke/nvidia_race/qwen3_batched_graph_cuda.mojo` | `benchmarks/llm_smoke/nvidia_race/qwen3_batched_graph_cuda.mojo` |
| `residentk.kernels_batched_gemma3` | cuda | 7 | `benchmarks/llm_smoke/nvidia_race/gemma3_batched_cuda.mojo` | `benchmarks/llm_smoke/nvidia_race/gemma3_batched_cuda.mojo` |
| `residentk.kernels_cuda_graph` | cuda | 7 | `benchmarks/llm_smoke/qwen3_generate_cuda.mojo` | `benchmarks/llm_smoke/qwen3_bench_cuda.mojo` |
| `residentk.kernels_decode_attn_flash` | cuda | 2 | `benchmarks/llm_smoke/nvidia_race/qwen3_serve_batched_cuda.mojo --selftest` | `benchmarks/llm_smoke/nvidia_race/enterprise_bench.py` |
| `residentk.kernels_gemma3` | cuda | 12 | `benchmarks/llm_smoke/gemma3/ref_gemma3_torch.py` | `benchmarks/llm_smoke/nvidia_race/gemma3_correctness_cuda.mojo` |
| `residentk.kernels_packed3` | cuda | 7 | `benchmarks/llm_smoke/nvidia_race/packed3_gemv_probe.mojo` | `benchmarks/llm_smoke/nvidia_race/packed3_gemv_probe.mojo` |
| `residentk.kernels_packed3_batched` | cuda | 6 | `benchmarks/llm_smoke/nvidia_race/qwen3_serve_batched_cuda.mojo --selftest` | `benchmarks/llm_smoke/nvidia_race/enterprise_bench.py` |
| `residentk.kernels_prefill_attn_flash` | cuda | 1 | `benchmarks/llm_smoke/nvidia_race/qwen3_serve_batched_cuda.mojo --selftest` | `benchmarks/llm_smoke/nvidia_race/ttft_probe.py` |
| `residentk.kernels_prefill_attn_flash2` | cuda | 1 | `benchmarks/llm_smoke/nvidia_race/qwen3_serve_batched_cuda.mojo --selftest` | `benchmarks/llm_smoke/nvidia_race/h100_attn_probe.mojo` |
| `residentk.kernels_prefill_f16` | cuda | 4 | `benchmarks/llm_smoke/qwen3_generate_cuda.mojo` | `benchmarks/llm_smoke/qwen3_bench_cuda.mojo` |
| `residentk.kernels_prefill_f32` | cuda | 4 | `benchmarks/llm_smoke/qwen3_generate_cuda.mojo` | `benchmarks/llm_smoke/qwen3_generate_cuda.mojo` |
| `residentk.kernels_prefill_f32_v2` | cuda | 3 | `benchmarks/llm_smoke/nvidia_race/prefill_gemm_probe.mojo` | `benchmarks/llm_smoke/nvidia_race/prefill_gemm_probe.mojo` |
| `residentk.kernels_prefill_f32_v2n` | cuda | 1 | `benchmarks/llm_smoke/nvidia_race/qwen3_serve_batched_cuda.mojo` | `benchmarks/llm_smoke/nvidia_race/qwen3_serve_batched_cuda.mojo` |
| `residentk.kernels_prefill_f32_v3` | cuda | 3 | `benchmarks/llm_smoke/nvidia_race/h100_gemm_probe.mojo` | `benchmarks/llm_smoke/nvidia_race/h100_gemm_probe.mojo` |
| `residentk.kernels_prefill_gemma3` | cuda | 22 | `benchmarks/llm_smoke/gemma3/ref_transformers_gemma3.py` | `benchmarks/llm_smoke/nvidia_race/gemma3_correctness_cuda.mojo` |
| `residentk.kernels_prefill_v2f16` | cuda | 3 | `benchmarks/llm_smoke/nvidia_race/qwen3_serve_batched_cuda.mojo --selftest` | `benchmarks/llm_smoke/nvidia_race/ttft_probe.py` |
| `residentk.session_cuda_batched_p3_graph` | cuda | 1 | `benchmarks/llm_smoke/nvidia_race/qwen3_serve_batched_cuda.mojo` | `benchmarks/llm_smoke/nvidia_race/enterprise_bench.py` |
| `residentk.session_cuda_p3` | cuda | 10 | `benchmarks/llm_smoke/nvidia_race/qwen3_p3_session_cuda.mojo` | `benchmarks/llm_smoke/nvidia_race/qwen3_p3_session_cuda.mojo` |
| `residentk.tc_shim_bridge` | cuda | 42 | `benchmarks/llm_smoke/nvidia_race/tc_escape_probe.mojo` | `benchmarks/llm_smoke/nvidia_race/tc_escape_probe.mojo` |

## Querying the inventory from the SDK

The same inventory ships in the runtime contract and is queryable from `algenta` — filters compose:

```python
from algenta import engine_kernels, engine_kernel_backends

engine_kernel_backends()                      # ("cuda", "metal")
len(engine_kernels(backend="metal"))         # every Metal kernel that ships
engine_kernels(backend="cuda", family="gemma3")   # the Gemma 3 CUDA lane
engine_kernels(role="tc_shim")               # the tensor-core escape hatch
```

Kernel entries map a stable public name to the private engine symbol, its backend, its model-family profile, and its role class. A kernel leaving the inventory is a contract change, enforced by the SDK audit gates — never a silent regen side effect.
