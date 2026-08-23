# AMD LAUNCH READINESS — MI300X launch plan, wavefront audit, ROCm matrix, AMD-WORKAROUNDS audit

Status (2026-08-23): the AMD lane's COMPILE gate is PASSED (`amd_rocm_compile_gate.mojo`,
12 portable kernels, gfx942/gfx950/gfx90a on Mojo 1.0.0 / MAX 26.5.0). Launching is blocked on
hardware + quota. This document is the launch-stage map: what is portable today, what BREAKS
on a 64-lane CDNA wavefront and how, which ROCm the target needs, every AMD-specific
workaround/gate/known-limitation already in this tree (each re-verified against the current
Modular docs), and the ordered checklist from quota to the first verified AMD launch.

Honesty line unchanged: compile-verified, launch-UNVERIFIED. Nothing in this document is a
claim that algenta RUNS on AMD.

---

## 1. WAVEFRONT GEOMETRY AUDIT — the 12 gated kernels vs 64-lane CDNA

The portable kernels were written against the NVIDIA warp: `residentk.kernels` fixes
`_TG = 256`, `_LANES = 32`, `_SUBS = 8` and the reduction vocabulary is
`std.gpu.primitives.warp.sum` plus explicit shared-memory barrier trees. CDNA executes
64-thread wavefronts. The current Modular docs state the rule and the mechanism:

- `warp.sum(value)` "Computes the sum of `value` across all threads in the warp. The result
  is broadcast to all lanes." — the reduction width is the HARDWARE warp/wavefront width,
  not a parameter (max.modular.com/gpu/block-and-warp/).
- `std.gpu.WARP_SIZE` is resolved AT COMPILE TIME per target accelerator: 32 on NVIDIA,
  32 on AMD RDNA, **64 on AMD CDNA**, 0 with no GPU (mojolang.org/docs/std/gpu/globals/).
- "The most common mistake is assuming a warp size of 32. Use the `gpu.WARP_SIZE` constant
  to ensure your code works correctly on all vendors' hardware." (max.modular.com, same page).
- `syncwarp()` is a no-op on AMD (wavefronts are hardware lockstep).

`residentk.kernels` IMPORTS `WARP_SIZE` but never uses it for geometry — `_LANES` is the
literal `32`. Every construct below was enumerated by reading the five gated files line by
line (`kernels.mojo`, `kernels_packed3.mojo`, `kernels_decode_attn_flash.mojo`,
`kernels_prefill_attn_flash.mojo`, `kernels_prefill_f32_v2.mojo`).

### Verdict table (12 gated kernels)

| kernel | file:line | reduction / geometry | wave64 verdict |
|---|---|---|---|
| `_gemv_accum_kernel` | kernels.mojo:889 | shared-mem barrier tree, `red[tid]`, strides `_LANES//2` inside 32-thread groups; no warp primitives | ✅ PORTABLE (perf re-tune only) |
| `_packed3_gemv_kernel` | kernels_packed3.mojo:207 | `_warp_sum` + `grp[sub]` combine; `lane=tid%32`, `sub=tid//32`, `if lane==0` | ❌ BREAKS — silent 2x |
| `_packed3_gemv_kernel_v2` | kernels_packed3.mojo:309 | same | ❌ BREAKS — silent 2x |
| `_packed3_gemv_kernel_v3` | kernels_packed3.mojo:400 | same | ❌ BREAKS — silent 2x |
| `_norm_gemv_kernel_p3` | kernels_packed3.mojo:492 | barrier trees only (full-block `_TG//2` ss-tree + per-group `_LANES//2` tree) | ✅ PORTABLE |
| `_norm_gemv_kernel_p3_v2` | kernels_packed3.mojo:613 | same | ✅ PORTABLE |
| `_norm_gemv_kernel_p3_v3` | kernels_packed3.mojo:727 | same | ✅ PORTABLE |
| `_splitk_partial_batched_flash_kernel` | kernels_decode_attn_flash.mojo:94 | `warp_id()` unit map (8 warps/block = `256//32`), `e0=lane*4` over d_head=128, `_warp_sum` scores | ❌ BREAKS — silent corruption |
| `_pf_attn_flash_kernel` | kernels_prefill_attn_flash.mojo:100 | `warp_id()*4` row map (8 warps/block), `_PF_FLASH_NTHREADS=8*32`, `e0=lane*4`, `_warp_sum` scores | ❌ BREAKS — silent corruption |
| `_pf_gemm_assign_kernel_v2` | kernels_prefill_f32_v2.mojo:127 | pure tid arithmetic + shared + `barrier()`; zero warp primitives | ✅ PORTABLE |
| `_pf_gemm_accum_kernel_v2` | kernels_prefill_f32_v2.mojo:351 | same | ✅ PORTABLE |
| `_pf_gemm_swiglu_kernel_v2` | kernels_prefill_f32_v2.mojo:567 | same | ✅ PORTABLE |

7 portable, 5 wavefront-locked. All five failures are SILENT (no fault, wrong numbers).

### Exact failure mechanics at wave64

**packed3 GEMV v1/v2/v3 (silent 2x).** One output row per block, 256 threads stream it in
12-element chunks (the chunk loop is tid-strided and wavefront-agnostic), then:
`total = _warp_sum(acc); if lane == 0: grp[sub] = total; barrier(); out = Σ grp[0..7]`.
With 64-lane wavefronts, physical wave 0 covers tids 0..63 = LOGICAL groups sub=0 AND sub=1;
`_warp_sum` returns the sum of BOTH groups broadcast to all 64 lanes; `lane == tid % 32 == 0`
is true at tid 0 AND tid 32, writing that combined total into grp[0] and grp[1]. Every wave
duplicates its two groups' combined sum into two grp slots, so `out = 2 × Σ(all partials)`:
every row of `y` comes out exactly TWICE the correct value. Not a crash, not a fault — a
uniform 2x scale error.

**decode flash attention (silent corruption, three independent breaks).**
1. `_DECODE_FLASH_WARPS_PER_BLOCK = 256 // 32 = 8` and `u = block_idx.x*8 + warp_id()`: on
   wave64, 256 threads are FOUR waves (`warp_id()` 0..3), so each block computes units
   {8b+0..3} and units {8b+4..7} are NEVER assigned to any thread — their partials are never
   written and the unchanged merge kernel consumes stale/garbage buffers.
2. `lane = lane_id()` runs 0..63 and `e0 = lane*4`: lanes 32..63 load Q/K/V elements
   [128..255] of a d_head=128 row — OUT-OF-BOUNDS reads into neighbouring rows/slots. The
   kernel's own contract states `d_head == 128 = WARP_SIZE x 4`.
3. `_warp_sum` reduces 64 lanes, not the assumed 32, folding the OOB terms into every score.

**prefill flash attention (silent corruption, same class).**
`_PF_FLASH_NTHREADS = 8*32`, `_PF_FLASH_WARPS_PER_BLOCK = 8`, row ownership
`m_base = (g//h_q)*32 + warp_id()*4 + 0..3`: wave64 blocks have 4 waves → only 16 of the 32
rows per block are computed (the host grid `ceil(m/32)*h_q` assumes 32) — half the prompt's
attention rows never computed. `e0 = lane*4` OOB-reads exactly as the decode kernel, and each
per-key score's `_warp_sum` spans 64 lanes.

### What 64 changes (fix sketch, hardware-verification-gated)

- `std.gpu.WARP_SIZE` resolves to 64 on gfx942 AT COMPILE TIME — replacing the literal
  `_LANES = 32` with a target-derived constant re-derives `_SUBS = _TG // _LANES` (256/64 = 4
  groups) and every `lane/sub` map automatically. For the packed3 GEMV arm that alone fixes
  the reduction: one wavefront = one logical group, `grp[0..3]` combine — CORRECT. Same for
  the barrier-tree kernels (they already work; the group count just halves, rows/block 8→4).
- The two flash-attention kernels need a genuine restructure, not a constant swap: with
  d_head=128 and 64 lanes the natural ownership is 2 elements per lane (or one half-wave per
  row), plus matching HOST-side grid constants (the session launches with the 8-warps-per-block
  arithmetic baked into its grid math). That work is deliberately deferred to the launch stage:
  it is untestable without MI300X and correctness there is gated by the serve driver's
  token-identity oracle, not by compilation.
- Performance re-tunes expected even where correctness holds: `_VEC/_VEC_H` byte-width choices
  were tuned for Metal/NVIDIA vector types; CDNA wants its own check (the `_VEC_H = 8` lesson
  in kernels.mojo's docstring generalizes — check the backend's actual vector types). Bank-pad
  constants (`_G2_APAD`, `_G2_BPAD`) assume 32 banks; CDNA LDS also has 32 banks, so the pads
  carry, but re-profile on hardware.

---

## 2. ROCM VERSION MATRIX

| target | gfx | ROCm floor (Modular's stated) | source / re-verification |
|---|---|---|---|
| MI300X | gfx942 | >= 6.3.3 | Modular MAX claim as recorded in the ledger ("THE AMD ROCM COMPILE GATE" §5). The CURRENT docs site (max.modular.com, checked 2026-08-23) no longer publishes an explicit numeric floor — re-verify on first boot: `cat /opt/rocm/.info/version` |
| MI355X | gfx950 | ROCm 7 | same provenance, same re-verification rule |
| MI250X | gfx90a | rides along (gate compiles it; not a launch target) | — |

What the pinned toolchain and MAX 26.5 ship (docs verified 2026-08-23):
- `mojo build --print-supported-accelerators` (Mojo 1.0.0 / MAX 26.5.0): full ROCm/HIP table —
  gfx90a/gfx942/mi300x/gfx950/mi355x/RDNA2-4; LLVM `amdgpu` backend ships inside the
  toolchain like NVPTX (no ROCm toolkit needed to COMPILE).
- MAX container (`max-full`, docs.modular.com → max.modular.com/container/): Ubuntu 22.04,
  Python 3.12, PyTorch (GPU) 2.6.0, CUDA 12.8, ROCm (no version number published), plus
  `max-amd` / `max-amd-base` flavors carrying "all ROCm ... dependencies". The page explicitly
  recommends **AMD MI300X via Azure `ND_MI300X_v5-series`** cloud instances.
- MAX v26.5 release notes (max.modular.com/releases/v26.5/, Aug 11 2026): heavy AMD investment
  (MI300-series VMM allocator, MI355X kernel/collective work, MI250X targeting fix,
  float32 GEMV vectorized/split-K paths on AMD). Two entries are direct launch-stage evidence:
  Modular DISABLED their own v2 attention prefill kernel on AMD "due to a race producing NaNs"
  and fixed "NaNs from fused SwiGLU kernel on AMD GPUs" — vendor-first-party kernels hit
  AMD-only correctness races in this exact release. Our launch verification bar must be
  numerical, not "it compiled".
- Also from v26.5 notes, constraints our code ALREADY satisfies: kernel params must be
  fixed-width DevicePassable (`Int`/`UInt` no longer conform — every residentk kernel takes
  Int64 scalars and widens at entry), and `GPUInfo.vendor` is removed in favor of
  `GPUInfo.api` ("hip" for AMD) — host-side only, no kernel impact.

Azure leg: `Standard_ND96isr_MI300X_v5` / `Standard_ND96is_MI300X_v5` (8x MI300X) is offered
in exactly ONE region as of this audit's catalog scan — **francecentral** (see §4 quota note).
The Azure ND MI300X v5 marketplace image ships ROCm; boot check in §5 step 3.

---

## 3. AMD-WORKAROUNDS AUDIT — every AMD/ROCm-specific gate, workaround and known limitation in this tree, re-verified against MAX 26.5 docs

| # | workaround / gate / limitation | where | still accurate vs MAX 26.5 docs? | MI300X launch: what changes |
|---|---|---|---|---|
| W1 | `-D ALGENTA_ROCM` backend selector (two-tier define: `ALGENTA_GPU` portable + backend flag) | amd_rocm_compile_gate.mojo, CI script, ledger | ✅ current — the portable layer has NO `ALGENTA_ROCM` branches inside kernels; the selector only scopes the gate build, and the docs' portability model (target-resolved codegen, `warp.*` fallbacks) confirms that is the right shape | stays; an AMD SESSION (`session_rocm*`) will need the flag to grow real branches when the session layer is ported (out of this lane's scope) |
| W2 | compile gate driver (12 kernels enqueue-forced through codegen) | benchmarks/llm_smoke/amd_rocm_compile_gate.mojo | ✅ current; THIS PR extends it with a PART 0.5 wavefront advisory that prints the target-resolved `WARP_SIZE` and names the 5 wave64-locked kernels, so a gfx build can never again pass without the geometry caveat on record | unchanged at launch — it becomes the FIRST binary executed on MI300X (§5 step 4) |
| W3 | `.github/workflows/amd-rocm-gate.yml` — `workflow_dispatch` only, in no job's `needs`, disabled by design | .github/workflows/ | ✅ correct for a no-hardware lane | flip to scheduled/on-push ONLY after a launch-verified runner exists |
| W4 | fleet amd64 container compile leg (pixi + mojo build per gfx target, embedded-target assertion) | .github/scripts/amd_rocm_compile_gate.sh | ✅ mirrors build-linux-cuda's container pattern | unchanged |
| W5 | `_LANES = 32` / 32-lane `warp.sum` trees assumed across the portable layer | residentk/kernels.mojo:229 + consumers | ❌ the audit's finding — 5 of 12 gated kernels SILENTLY break at wave64; the current docs call this exact assumption "the most common mistake" and prescribe `gpu.WARP_SIZE` | target-derived `_LANES` fixes 3 kernels (packed3 GEMV arm); the 2 attention kernels need lane-ownership restructure + host grid constants (§1) |
| W6 | macOS host run refuses HIP: "Failed to open HIP library: hip is not supported on this operating system" (MAX `device_context.mojo:3825`) | recorded in ledger §3 | ✅ expected host-runtime behaviour — the MAX host path routes the AMD target through HIP; compiling needs no ROCm, launching needs Linux + ROCm libhip | becomes moot on the Linux launch VM (first success = PART 1 enqueues executing) |
| W7 | honesty line "compile-verified, launch-UNVERIFIED" in ledger, gate docstrings, workflow comments | repo-wide | ✅ required until §5 steps 4-6 pass | upgrade to launch-verified ONLY after the numerical gates pass on hardware |
| W8 | Int64-only kernel parameter discipline (fixed-width DevicePassable) | every residentk kernel entry | ✅ v26.5 notes make this HARD (`Int`/`UInt` no longer DevicePassable) — already compliant | nothing |
| W9 | no `syncwarp`/`warp.match_*`/masked-shuffle usage in the portable layer | audited all 5 files | ✅ good by luck AND design — docs: `syncwarp()` is a no-op on AMD, masks are 64-bit there; the kernels' barrier-tree reductions are vendor-neutral | nothing |
| W10 | lever #0 `load[width=4, alignment=16]` vector-load path | residentk/loadvec.mojo | ✅ carries to AMD — the gate's `.amdgcn` sidecars show single `global_load_dwordx4` in all 12 kernels | profile on HBM3; MI300X streams 128-bit loads natively |
| W11 | CUDA-only session layer NOT ported (`session_cuda*.mojo`) | scope rule, ledger | ✅ still the correct scope — the gate proves kernels, not serving | launch stage decision: HIP-graph equivalent for resident sessions; Mojo DeviceContext graph-capture support on ROCm must be probed ON hardware |
| W12 | CUDA 12.6 nvcc recipes (build_tc_drivers / build_cuda_drivers, llama.cpp GGML_CUDA) | setup_vm.sh, .github/scripts | n/a for AMD — NVIDIA opponents only | an AMD VM runs a separate setup path (§5 step 4 note): ROCm-native hippBLAS/rocBLAS opponents (vLLM-ROCm, llama.cpp GGML_HIP) are DIFFERENT opponents than the NVIDIA lane's |

---

## 4. AZURE QUOTA + REGION DISCOVERY (the MI300X launch gate, discovered 2026-08-23 via az CLI)

Subscription "thyn ai" (fed0aaeb-1166-4483-a437-1ef62d224f04). All five portal quota
requests landed in EASTUS and ALL auto-failed (`provisioningState: Failed`, "ContactSupport"),
escalating to four OPEN support tickets (EASTUS, 2 each: NDsr H100 v5, ND128isr GB300 v6,
NDsr H200 v5, NDsr MI300X v5). The catalog scan (`az vm list-skus --all`, ~40 regions)
explains three of the four failures: **eastus does not OFFER the H200 v5, GB300 v6 or MI300X
v5 series at all** — quota cannot be granted for a SKU the region does not carry; the requests
for those series must be re-filed against regions that do:

| series | SKU | regions offering it (catalog scan, 2026-08-23) |
|---|---|---|
| NDsr MI300X v5 | Standard_ND96isr_MI300X_v5 (+ ND96is variant) | **francecentral ONLY** |
| ND128isr GB300 v6 | Standard_ND128isr_GB300_v6 | swedencentral, westus2, westus3, uksouth, northeurope, eastus2, germanywestcentral, brazilsouth |
| NDsr H200 v5 | Standard_ND96isr_H200_v5 | australiaeast, westus3, uksouth, japaneast, eastus2, francecentral, switzerlandnorth, uaenorth, italynorth, polandcentral, spaincentral |
| NDsr H100 v5 | Standard_ND96isr_H100_v5 | eastus, southcentralus, australiaeast, swedencentral, canadacentral, westus2, westus3, uksouth, westeurope, northeurope, japaneast, koreacentral |
| NCCads H100 v5 | Standard_NC40ads_H100_v5 / NC80adis | eastus (+ others; the tickets actually filed are for the NDsr family) |

Current granted quota: **zero everywhere** (every GPU family `limit = 0` in all regions).
`benchmarks/llm_smoke/nvidia_race/azure_provision.sh` (sibling PR) implements the
quota-aware, region-aware spot provisioning; it skips 0-of-0 families and never exceeds a
granted limit. Note the owner's "2 locations" portal selection was almost certainly
eastus + francecentral — only eastus registered requests.

---

## 5. MI300X LAUNCH CHECKLIST (ordered)

1. **Quota**: re-file the MI300X v5 quota request for **francecentral**
   (`standardNDISv5MI300XFamily`, x2; the eastus ticket cannot grant it — SKU absent from
   the eastus catalog). Re-file H200 v5 / GB300 v6 against §4 regions if those lanes are
   wanted. Track ticket SLAs; the four open eastus tickets expire 2026-08-24.
2. **Provision**: `azure_provision.sh` once quota > 0 — spot (Deallocate eviction), 512GB
   premium SSD, Ubuntu 22.04 (24.04 override if the ROCm apt route demands it), names
   `algenta-az-mi300x-{1,2}`.
3. **Boot checks** (on the VM): `cat /opt/rocm/.info/version` (floor 6.3.3 — §2),
   `rocm-smi` (8x MI300X visible), `rocminfo | grep -m1 gfx942`.
4. **First launch**: build the gate ON the VM (`mojo build -D ALGENTA_GPU -D ALGENTA_ROCM
   --target-accelerator gfx942 -I mojo/engine benchmarks/llm_smoke/amd_rocm_compile_gate.mojo`)
   and RUN it — PART 0 host checks, PART 0.5 advisory, then PART 1's 12 enqueues executing on
   device. PART 1 passing would be the first-ever AMD launch of this kernel layer; its
   enqueues use GATE shapes (k=n=1024 etc.), so it smoke-tests geometry without claiming
   model correctness.
5. **Wavefront fix wave** (each step numerically gated against the f32 reference oracles in
   the probe drivers before the next step starts):
   a. target-derived `_LANES` (WARP_SIZE) through `residentk.kernels` + consumers — fixes
      the packed3 GEMV arm's 2x error; re-run packed3_gemv_probe oracles on gfx942.
   b. `_norm_gemv_kernel_p3*` group-count halving (8→4 rows/block) — host dispatch constants.
   c. decode + prefill flash attention lane-ownership restructure (2 elems/lane at
      d_head=128) + host grid constants — validated by the serve driver selftest oracle.
6. **Session decision**: probe Mojo DeviceContext HIP-graph capture on the VM; scope the
   AMD session lane (W11) based on the answer.
7. **Publish**: only after 4-5 are green does the honesty line upgrade to launch-verified,
   and only wins get raced publicly (campaign rule).
