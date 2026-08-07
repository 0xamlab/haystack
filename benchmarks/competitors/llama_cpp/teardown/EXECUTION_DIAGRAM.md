# EXECUTION DIAGRAM — llama.cpp Metal Flash Attention (Stage-1 Teardown, Attention Compiler Plan v1.0)

**Pinned upstream:** llama.cpp commit `000547513f1530346ecd163db8b3e13962949961` (Homebrew build 10210).
**Vendored sources (all paths relative to `benchmarks/competitors/llama_cpp/upstream_src/`):**

| file | role |
|---|---|
| `ggml-metal.metal` (11280 lines) | all kernels |
| `ggml-metal-ops.cpp` (4915 lines) | encode-time dispatch: kargs fill, buffer bindings, grids, smem |
| `ggml-metal-device.cpp` (2175 lines) | pipeline construction: host_name selection, function constants |
| `ggml-metal-impl.h` (1225 lines) | kargs structs, FC base offsets, block-size constants |

**Instantiation under analysis:** `kernel_flash_attn_ext_f16_dk128_dv128` (matrix path), specialized with `nsg=4`, F16 KV cache — the kernel Qwen3-0.6B prefill runs. All quoted line numbers verified against the vendored source.

**Region map (`ggml-metal.metal`):**
- `kernel_flash_attn_ext_pad` (KV/mask tail pad pre-pass): 6242–6305 (FCs 6237–6239)
- `kernel_flash_attn_ext_blk` (mask block classifier pre-pass): 6314–6367 (FCs 6307–6308)
- matrix-kernel function constants: 6369–6383
- `kernel_flash_attn_ext_impl` (matrix kernel body): **6415–7023**
- `kernel_flash_attn_ext` (nsg dispatch wrapper): 7025–7078
- `FA_TYPES` + f16 dk128 instantiation: 7083–7089, **7136**
- vec-kernel FCs: 7246–7259; `kernel_flash_attn_ext_vec`: 7280–7710; f16 dk128 vec instantiation (NE=1): 7767
- `kernel_flash_attn_ext_vec_reduce`: 7849–7889 (FCs 7846–7847)

**Global tuning constants** (`ggml-metal-impl.h:109–113`):

```c
#define OP_FLASH_ATTN_EXT_NQPSG 8        // matrix: queries per threadgroup (Q)
#define OP_FLASH_ATTN_EXT_NCPSG 64       // matrix: cache items per tile (C)
#define OP_FLASH_ATTN_EXT_VEC_NQPSG 1    // vec
#define OP_FLASH_ATTN_EXT_VEC_NCPSG 32   // vec
```

**FC base offsets** (`ggml-metal-impl.h:91–95`): `FC_FLASH_ATTN_EXT_PAD=100`, `FC_FLASH_ATTN_EXT_BLK=200`, `FC_FLASH_ATTN_EXT=300`, `FC_FLASH_ATTN_EXT_VEC=400`, `FC_FLASH_ATTN_EXT_VEC_REDUCE=500`.

ggml naming used throughout (`GGML_TENSOR_LOCALS`, ops.cpp:2710–2719): `neXY`/`nbXY` = dim/stride Y of `src[X]`; src0=Q, src1=K, src2=V, src3=mask, src4=sinks; `nb*` are **bytes**. `GGML_PAD(x,n) = (((x)+(n)-1) & ~((n)-1))`.

---

## 1. Overview: dispatch flow for a Qwen3-0.6B 256-token causal prefill

Workload: h_q=16, h_kv=8 (GQA factor 2), DK=DV=128, Q=F32, K/V=F16, causal F16 mask, no sinks/ALiBi/softcap. m = ne01 = 256 query rows; assume n_kv = ne11 = 256 with `n_kv % 64 == 0` (llama.cpp pads its cache; if not, the pad kernel runs first — §5.2).

**Path selection** (ops.cpp:2578–2586): `use_vec = (ne01 < 20) && (ne00 % 32 == 0)` → 256 ≥ 20 → **matrix path**.

Encode sequence inside `ggml_metal_op_flash_attn_ext` (ops.cpp:2702–3130):

| # | dispatch | condition | grid (threadgroups) | threads/tg | this workload |
|---|---|---|---|---|---|
| 0 | `kernel_flash_attn_ext_pad` | `ne11 % 64 != 0` (ops.cpp:2787) | `(64, max(ne12,ne32), max(ne13,ne33))` (2822) | (32,1,1) | **skipped** (256%64==0) |
| 1 | `kernel_flash_attn_ext_blk` | `has_mask` (2827) | `(nblk0, nblk1, ne32*ne33)` = `(ceil(256/64), ceil(256/8), 1)` = **(4, 32, 1)** (2848–2851) | (32,1,1) | runs; writes 128 int8 classifications |
| 2 | `ggml_metal_op_concurrency_reset(ctx)` | `need_sync` (2856–2858) | — | — | encoder barrier between pre-pass and main kernel |
| 3 | `kernel_flash_attn_ext_f16_dk128_dv128` (nsg=4) | always | `((ne01+7)/8, ne02, ne03)` = **(32, 16, 1)** (2941) | **(32, 4, 1) = 128** | 512 threadgroups; 10240 B threadgroup memory |

For this causal 256×256 case the blk pre-pass classifies the 4×32 = 128 mask tiles as: **48 tiles → 0** (fully −INF, skipped by the main kernel), **48 tiles → 2** (all-zero, mask add skipped), **32 tiles → 1** (diagonal, mask applied). Derivation: tile (i0,i1) is class 0 iff `64·i0 > 8·i1+7`, class 2 iff `64·i0+63 ≤ 8·i1`.

Each main-kernel threadgroup owns one block of 8 query rows (`iq1 = tgpig[0]*8`) for one head (`iq2 = tgpig[1]`) and walks the KV cache in C=64 tiles (4 tiles for n_kv=256), consuming `blk[ic0]` per tile. Decode (m<20) would instead take the **vec path** (§5.3): `kernel_flash_attn_ext_vec_f16_dk128_dv128` with nwg=32 workgroups + `kernel_flash_attn_ext_vec_reduce`, separated by a concurrency reset (ops.cpp:3106).

**Scratch buffer chain** — pad/blk/tmp live in the **same Metal buffer as dst, appended after `ggml_nbytes(op)`** (ops.cpp:2765–2774):

```cpp
ggml_metal_buffer_id bid_pad = bid_dst;   bid_pad.offs += ggml_nbytes(op);
ggml_metal_buffer_id bid_blk = bid_pad;   bid_blk.offs += ggml_metal_op_flash_attn_ext_extra_pad(op);
ggml_metal_buffer_id bid_tmp = bid_blk;   bid_tmp.offs += ggml_metal_op_flash_attn_ext_extra_blk(op);
```

All three extras are reserved **unconditionally** ("always reserve … to avoid graph reallocations": `if (false)` at 2608, commented-out early return at 2658–2660, `if (true)` at 2689), even when the corresponding kernel never runs:

- `extra_pad` (ops.cpp:2621–2628) = `64*(nb11*ne12*ne13 + nb21*ne22*ne23 + (has_mask ? 2*ne31*ne32*ne33 : 0))` bytes (the `2` = sizeof f16; mask term **conditional on has_mask**).
- `extra_blk` (2662–2668, **0 if no mask**, 2650–2652) = `GGML_PAD(1*ceil(ne01/nqptg)*ceil(ne30/ncpsg)*ne32*ne33, 32)` with (nqptg,ncpsg) = (8,64) matrix / (1,32) vec, selected by `use_vec` (2662–2663).
- `extra_tmp` (2689–2696) = `4*(min(ne01,32)*ne02*ne03*32*(ne20+2))` bytes (F32; consumed only by the vec nwg>1 path but reserved for every FA op).

Concrete allocation for this prefill (dst = 128·16·256·4 = 2,097,152 B): extra_pad = 64·(2048 + 2048 + 2·256) = 294,912 B; extra_blk = GGML_PAD(4·32,32) = 128 B; extra_tmp = 4·(32·16·1·32·130) = 8,519,680 B.

---

## 2. The matrix kernel: `kernel_flash_attn_ext_impl` execution diagram

### 2.1 Template, types, compile-time constants

Template signature (6386–6414): 17 type parameters (shmem/fragment types for Q, K, V, QK, softmax, O), device-memory K/V types + dequant fns (`kd4x4_t, nl_k, deq_k, vd4x4_t, nl_v, deq_v`), then `DK, DV, Q, C, NSG`. The outer wrapper `kernel_flash_attn_ext` (7053) fixes `Q = OP_FLASH_ATTN_EXT_NQPSG = 8`, `C = OP_FLASH_ATTN_EXT_NCPSG = 64` (7051–7052) and selects NSG at pipeline-specialization time (7069–7075):

```metal
7069      switch (FC_flash_attn_ext_nsg) {
7071        //case 1: ... //case 2: ...   // disabled to reduce library load time
7073          case 4: kernel_flash_attn_ext_impl<FWD_TMPL, 4>(FWD_ARGS); break;
7074          case 8: kernel_flash_attn_ext_impl<FWD_TMPL, 8>(FWD_ARGS); break;
```

Host: `int32_t nsg = ne00 >= 512 ? 8 : 4;` (ops.cpp:2887) → **NSG = 4** for DK=128. Only nsg ∈ {4,8} link.

Kernel arguments (6415–6428): `constant ggml_metal_kargs_flash_attn_ext & args`, device pointers `q, k, v, mask, sinks, pad, blk, dst`, `threadgroup half * shmem_f16`, `tgpig/tiisg/sgitg`. Decode: `iq3 = tgpig[2]; iq2 = tgpig[1]; iq1 = tgpig[0]*Q` (6429–6431). `NS10`/`NS20` macro-alias the stride FCs (6433–6434).

F16 instantiation (7083–7089, 7136):

```metal
7083  #define FA_TYPES \
7084      half,   half4,     simdgroup_half8x8,  \      // q_t, q4_t, q8x8_t
7085      half,   half4x4,   simdgroup_half8x8,  \      // k_t, k4x4_t, k8x8_t
7086      half,   half4x4,   simdgroup_half8x8,  \      // v_t, v4x4_t, v8x8_t
7087      float,             simdgroup_float8x8, \      // qk_t, qk8x8_t
7088      float,  float2,    simdgroup_float8x8, \      // s_t, s2_t, s8x8_t
7089      float,  float4,    simdgroup_float8x8         // o_t, o4_t, o8x8_t
7136  template [[host_name("kernel_flash_attn_ext_f16_dk128_dv128")]]  kernel flash_attn_ext_t
          kernel_flash_attn_ext<FA_TYPES, half4x4, 1, dequantize_f16, half4x4, 1, dequantize_f16, 128, 128>;
```

| operand | fragment | scalar in shmem | note |
|---|---|---|---|
| Q (`mq`) | `simdgroup_half8x8` | half (converted from device f32 at load) | precision loss at Q load |
| K (`mk`) | `simdgroup_half8x8` | — (read direct from device f16) | transposed load |
| QK acc (`mqk`) | `simdgroup_float8x8` | float in `ss` | float from the first MAC |
| P (`vs`) | `simdgroup_float8x8` | float in `ss` (in place over scores) | |
| V (`mv`) | `simdgroup_half8x8` | — (direct from device f16) | |
| O acc (`lo`) | `simdgroup_float8x8` | float in `so` | |

Both MMAs are **mixed-precision half8x8 × half8x8 → float8x8** (P×V is float8x8 × half8x8 → float8x8). Because `kd4x4_t == k4x4_t == half4x4` and `vd4x4_t == v4x4_t == half4x4`, the `is_same<>` compile-time branches at 6657 and 6829 select the **direct-from-device paths**; `dequantize_f16` and the `sk`/`sv` staging branches (6714–6774 quantized-K, 6905–6970 quantized-V) are dead code for this instantiation.

Derived constants for DK=DV=128, Q=8, C=64, NSG=4 (6443–6462):

```metal
6445      constexpr short DK4  = DK/4;          // 32
6446      constexpr short DK8  = DK/8;          // 16
6452      constexpr short PV   = PAD2(DV, 64);  // 128 (no padding needed)
6453      constexpr short PV4  = PV/4;          // 32
6454      constexpr short PV8  = PV/8;          // 16
6457      constexpr short NW  = N_SIMDWIDTH;    // 32
6458      constexpr short NQ  = Q/NSG;          // 2  (query rows per SIMD group)
6459      constexpr short SH  = 2*C;            // 128 floats of per-row scratch (s_t == float)
6461      constexpr short TS = 2*SH;            // 256 halves per scratch row
6462      constexpr short T  = DK + 2*PV;       // 384 halves per query (sq+so)
```

### 2.2 Threadgroup geometry and SIMD-group ownership

Host dispatch (ops.cpp:2941): grid `((ne01+7)/8, ne02, ne03)`, **128 threads = 4 SIMD groups of 32** per threadgroup. One threadgroup = one (8-query block, head, batch) triple.

**Q-row ↔ SIMD-group mapping is interleaved, not blocked.** Everywhere rows are iterated as (e.g. 6484):

```metal
6484        const short j = jj*NSG + sgitg;      // jj ∈ {0,1}
```

so SIMD group `s` owns query rows **{s, s+4}**. Per-stage ownership:

| stage | SG `s` reads | SG `s` computes/writes |
|---|---|---|
| Q load (6506–6519) | device Q rows {s, s+4} | `sq` rows {s, s+4} |
| mask load (6613–6624) | device mask rows {s, s+4} | `sm2` slots of rows {s, s+4} |
| QK^T (6657–6713) | **all 8 rows** of `sq`; K positions `[ic+8s,ic+8s+8) ∪ [ic+8s+32,ic+8s+40)` | score **column blocks {s, s+4}** of `ss` (all 8 rows) |
| softmax (6779–6822) | full 64-col rows {s, s+4} of `ss` | P rows {s, s+4} in place; rescales `so` rows {s, s+4}; register M/S |
| PV (6826–6904) | **full 8×64 P tile**; V dims `{8s..} ∪ {8(s+4)..} ∪ {8(s+8)..} ∪ {8(s+12)..}` | O **column blocks {s, s+4, s+8, s+12}** of `so` (all 8 rows) |
| epilogue (6976–7019) | `so` rows {s, s+4} | dst rows {s, s+4} |

QK produces columns per-SG but softmax consumes rows per-SG; PV produces column-slices of `so` but writeback consumes rows — this row/column ownership flip is exactly what the three in-loop barriers order (§2.7). **There is no cross-SIMD-group reduction anywhere**: each row's M/S state lives in one SG's registers, and one row's 64 scores fit in one SG (2 per lane), so `simd_max`/`simd_sum` are the only reductions in the kernel.

### 2.3 Threadgroup memory map

One blob, carved at 6464–6478:

```metal
6464    threadgroup q_t  * sq  = (threadgroup q_t  *) (shmem_f16 + 0*T);           // query data
6466    threadgroup o_t  * so  = (threadgroup o_t  *) (shmem_f16 + 0*T + Q*DK);    // O accumulator (float)
6468    threadgroup s_t  * ss  = (threadgroup s_t  *) (shmem_f16 + Q*T);           // scores/P + mask + diag scratch
6471    threadgroup k_t  * sk  = (threadgroup k_t  *) (shmem_f16 + sgitg*(4*16*KV) + Q*T + Q*TS); // K staging (quantized only)
6474    threadgroup v_t  * sv  = (threadgroup v_t  *) (... same address as sk ...);               // V staging (quantized only)
6478    threadgroup half2 * sm2 = (threadgroup half2 *) (shmem_f16 + Q*T + 2*C);   // mask, packed inside ss rows
```

Concrete map for DK=DV=128, Q=8, C=64, NSG=4 (offsets in **halves** from `shmem_f16`):

| region | offset (halves) | bytes | contents / lifetime |
|---|---|---|---|
| `sq` | `[0, 1024)` | 2048 | Q tile, half, 8×128, ld=DK; written once, read every tile |
| `so` | `[1024, 3072)` | 4096 | O accumulator, **float**, 8×128 (ld=PV); persists across tiles; rescaled in softmax, accumulated in PV, read at writeback |
| `ss` | `[3072, 5120)` | 4096 | per-row scratch, **float**, 8 rows × SH=128 floats (row stride TS=256 halves) |
| `sk`/`sv` | `[5120 + sgitg·512, …)` | 1024/SG | quantized-KV staging only — **neither touched nor allocated for f16** |

**Internal layout of each `ss` row** (256 halves):
- floats `[0,64)` (halves `[0,128)`): raw QK^T scores → overwritten **in place** by P at 6809.
- halves `[128,192)` (floats `[64,96)`): the 64 mask halves, via `sm2`. `sm2` base = `ss` base + 2*C halves; index `sm2[j*SH + tiisg]` (half2 units; `j*SH` half2 = `j*TS` halves row stride) puts mask element `i` of row `j` at halves `Q*T + j*TS + 2*C + i` (corrected below; not `2*i` — verified against source in the appendix). Host comment (ops.cpp:2862–2863): "2*(2*ncpsg) — ncpsg soft_max values + ncpsg mask values".
- halves `[192,256)` (floats `[96,128)`): **unused padding** — 128 B/row, 1024 B total allocated and zero-initialized but never read.

**Aliasing/reuse:** (a) scores and P share the same floats within a tile; (b) the mask lives *inside* the `ss` allocation after each row's scores; (c) `sk` and `sv` are the same bytes (quantized path only); (d) `so` is the single running accumulator — never re-derived.

**Host allocation** (ops.cpp:2860, 2869, 2939):

```c
2860    const int is_q = ggml_is_quantized(op->src[1]->type) ? 1 : 0;
2869    #define FATTN_SMEM(nsg) (GGML_PAD((nqptg*(ne00 + 2*GGML_PAD(ne20, 64) + 2*(2*ncpsg)) + is_q*(16*32*(nsg)))*(sizeof(float)/2), 16))
```

F16 (is_q=0), DK=DV=128: `8*(128 + 256 + 256)*2 = ` **10240 bytes**, nsg-independent, set at threadgroup-memory index 0 (2939). The `sk/sv` staging (`16*32*nsg*2` B) is added only for quantized KV. There is no smem-cap assert on the matrix path (only vec, ops.cpp:3079).

### 2.4 Stage A — Q load, accumulator init, per-thread state

Q is read from device **f32**, converted to **half**, parked in `sq` for the whole kernel (6506–6519):

```metal
6510        device const float4 * q4 = (device const float4 *) ((device const char *) q + j*args.nb01);
6512        for (short i = tiisg; i < DK4; i += NW) {
6513            if (iq1 + j < args.ne01) { sq4[j*DK4 + i] = (q4_t) q4[i]; }
6515            else                     { sq4[j*DK4 + i] = 0; }
```

DK4 = 32 = NW → each lane converts exactly one float4→half4 per row (2 total). Ragged last query block zero-fills. **No scale applied at load** — `args.scale` is folded in at 6786. Q was pre-offset `q += iq1*nb01 + iq2*nb02 + iq3*nb03` (6497); K/V pre-offset for GQA (6499–6503, §4.4); `blk` pre-offset to this row of tiles (6489–6494); per-query device mask pointers set (6481–6487):

```metal
6486        pm2[jj] = (device const half2 *) ((device const char *) mask + (iq1 + j)*args.nb31 + (iq2%args.ne32)*args.nb32 + (iq3%args.ne33)*args.nb33);
```

Init: `so4[j*PV4 + i] = 0` over DV4 and `ss[j*SH + i] = 0.0f` over **all** SH (6521–6532 — the full-row zero covers the mask slots so the maskless mask-add reads 0), then the one-time barrier at **6534**. Per-thread state: `float S[NQ] = {0}` (6536), `float M[NQ] = {-FLT_MAX/2}` (6539) — NQ=2 registers each, replicated-uniform across the 32 lanes, **never in shmem**. ALiBi slope at 6544–6551 (dead here, `has_bias=false`).

### 2.5 Stage B — the K-tile loop

```metal
6555        for (int ic0 = 0; ; ++ic0) {
6556            int ic = ic0*C;
6557            if (ic >= args.ne11) { break; }
```

One iteration = one C=64 KV tile; `ic0` also indexes `blk`.

**B0 — kvpad redirect (6562–6597), compiled out when `has_kvpad=false`.** When `FC_flash_attn_ext_has_kvpad && ic + C > args.ne11`: `k`,`v`,`mask` are redirected into the pad buffer (`v = k + nb11*C*ne_12_2*ne_12_3; mask = v + nb21*C*...`, 6563–6565), K/V advanced by pad-plane head strides `(ikv2 + ikv3*ne_12_2)*nb11*C` (6570–6571), `pm2` recomputed against the pad-mask layout (6589–6592), and `ic = 0` (6596). With no user mask, phantom columns get `-MAXHALF` sentinels written into `sm2` in-place (6579–6583). Because `has_kvpad` is only set when `ne11 % 64 != 0` (ops.cpp:2787), the steady-state loop has **zero bounds checks**.

**B1 — blk classification consume (6599–6629).** `blk` values come from the pre-pass (§5.1; semantics at 6310–6313: `0` = all −INF, `1` = mixed, `2` = all zero):

```metal
6599            char blk_cur = 1;
6602            if (FC_flash_attn_ext_has_mask) {
6603                blk_cur = blk[ic0];
6605                if (blk_cur == 0) {
6606                    FOR_UNROLL (short jj = 0; jj < NQ; ++jj) { pm2[jj] += NW; }
6610                    continue;                    // skips QK, softmax, PV, and all 3 barriers
6611                }
6613                if (blk_cur == 1) {
6614                    FOR_UNROLL (short jj = 0; jj < NQ; ++jj) {
6615                        const short j = jj*NSG + sgitg;
6617                        if (FC_flash_attn_ext_bc_mask) {
6618                            sm2[j*SH + tiisg] = (iq1 + j) < args.ne31 ? pm2[jj][tiisg] : half2(-MAXHALF, -MAXHALF);
6619                        } else {
6620                            sm2[j*SH + tiisg] = pm2[jj][tiisg];
6621                        }
6623                        pm2[jj] += NW;
6624                    }
6625                } else if (blk_cur == 2) {
6626                    FOR_UNROLL (short jj = 0; jj < NQ; ++jj) { pm2[jj] += NW; }
6628                }
```

- **blk==0**: advance `pm2` by NW half2 (=64 mask values) and `continue` — no threadgroup memory is written, so skipping the barriers is safe.
- **blk==1**: each SG copies the 64 mask halves for its 2 rows into `sm2` (one half2 per lane per row); added in softmax.
- **blk==2**: skip the load; the mask add at 6793 is also skipped (`blk_cur != 2`).
- **No mask at all** (`has_mask=false`): block 6602 compiled out, `blk_cur` stays 1, and the softmax *does* execute the mask add — reading `sm2` slots that the init at 6529–6531 zeroed (adds 0), except where the kvpad path wrote `-MAXHALF` sentinels. This is why the zero-init covers all of SH.
- The obsolete in-kernel −INF detector is `#if 0`-ed at 6631–6652 ("old -INF block optimization - obsoleted by pre-computing non-masked blocks").

**B2 — QK^T MMA (6655–6713).** F16 K → direct-from-device branch (6657). Per-SG pointers (6659–6668):

```metal
6659                device      const k_t * pk = (device const k_t *) (k + ic*args.nb11);
6660                threadgroup const q_t * pq = sq;
6661                threadgroup       s_t * ps = ss;
6663                pk += sgitg*(8*NS10);
6664                ps += sgitg*(8*1);
6666                static_assert((C/8) % NSG == 0, "");
6668                constexpr short NC = (C/8)/NSG;      // = 2 column blocks per SG
```

After each block: `pk += 8*(NSG*NS10); ps += 8*NSG;` (6711–6712) → SG `s` owns score column blocks {s, s+4}. DK=128 → `DK % 16 == 0` → the double-buffered branch (6687–6707):

```metal
6688                    k8x8_t mk[2];
6689                    q8x8_t mq[2];
6691                    // note: too much unroll can tank the performance for large heads
6692                    #pragma unroll (MIN(DK8/2, 4*NSG))
6693                    for (short i = 0; i < DK8/2; ++i) {          // 8 iterations, fully unrolled
6694                        simdgroup_barrier(mem_flags::mem_none);
6696                        simdgroup_load(mq[0], pq + 0*8 + 16*i, DK);
6697                        simdgroup_load(mq[1], pq + 1*8 + 16*i, DK);
6699                        simdgroup_load(mk[0], pk + 0*8 + 16*i, NS10, 0, true);   // transposed, from device
6700                        simdgroup_load(mk[1], pk + 1*8 + 16*i, NS10, 0, true);
6702                        simdgroup_barrier(mem_flags::mem_none);
6704                        simdgroup_multiply_accumulate(mqk, mq[0], mk[0], mqk);
6705                        simdgroup_multiply_accumulate(mqk, mq[1], mk[1], mqk);
6706                    }
6709                simdgroup_store(mqk, ps, SH, 0, false);
```

Mechanics: `mq` = 8 queries × 8 head dims (half, from `sq`, ld=DK); `mk` = `simdgroup_load(..., NS10, 0, true)` — **transposed load direct from device**, turning 8 cache rows × 8 dims into 8 dims × 8 positions; `mqk += mq·mk` = 8 queries × 8 positions, accumulated float over 16 rank-8 updates. **Raw scores are float from the first MAC** and land in `ss` via `simdgroup_store(..., SH, ...)`. The `mem_none` simdgroup barriers are intra-SG scheduling fences with no memory semantics. The quantized-K branch (6714–6774) is dead here.

**B3 — scale / softcap / mask (6785–6799)**, top of the softmax block, per owned row, 2 columns per lane as `float2`:

```metal
6786                float2 s2 = ss2[j*SH/2 + tiisg]*args.scale;
6788                if (FC_flash_attn_ext_has_scap) { s2 = args.logit_softcap*precise::tanh(s2); }
6793                if (blk_cur != 2) {
6794                    if (FC_flash_attn_ext_has_bias) { s2 += s2_t(sm2[j*SH + tiisg])*slope; }
6796                    else                            { s2 += s2_t(sm2[j*SH + tiisg]); }
6799                }
```

Exact order: (1) × `args.scale`; (2) softcap `softcap·tanh(·)` (host pre-divided scale by softcap at ops.cpp:2742–2744, so composition = `softcap·tanh(scale·qk/softcap)`); (3) mask add (half→float promote), × ALiBi slope if `has_bias`. There is **no causal special-case** — causality arrives only through the mask tensor. blk==2 skips the add; blk==0 never gets here.

**B4 — online softmax (6779–6822).** Per query row (M/S in registers):

```metal
6801                M[jj] = simd_max(max(M[jj], max(s2[0], s2[1])));
6803                const float  ms  = exp(m  - M[jj]);
6804                const float2 vs2 = exp(s2 - M[jj]);
6806                S[jj] = S[jj]*ms + simd_sum(vs2[0] + vs2[1]);
6809                ss2[j*SH/2 + tiisg] = vs2;                    // P written IN PLACE over the scores
6811                if (DV4 % NW == 0) {
6812                    FOR_UNROLL (short ii = 0; ii < DV4/NW; ++ii) {   // DV4/NW = 1
6815                        so4[j*PV4 + ii*NW + tiisg] *= ms;            // one float4 per lane
```

One 32-lane `simd_max` covers all 64 columns (2/lane); `ms` rescales both the running sum and the O accumulator row; P is staged to `ss` as float for PV to consume as fragments.

**B5 — PV MMA (6826–6904).** F16 V (6829) and DV=128 > 64 → the `else` scheduling branch (6868–6893). O fragments hoisted once per tile (6830–6844):

```metal
6832                    constexpr short NO = PV8/NSG;     // = 4 fragments per SG
6834                    o8x8_t lo[NO];
6837                        auto sot = so + 8*sgitg;
6839                        FOR_UNROLL (short ii = 0; ii < NO; ++ii) { simdgroup_load(lo[ii], sot, PV, 0, false); sot += 8*NSG; }
```

SG `s` owns O column blocks {s, s+4, s+8, s+12} → output dims `[8s,8s+8) ∪ [8s+32,8s+40) ∪ [8s+64,8s+72) ∪ [8s+96,8s+104)`, all 8 rows. V direct from device: `pv = v + ic*nb21; pv += 8*sgitg;` ld = NS20 (6847–6849). Inner schedule:

```metal
6869                        constexpr short NC = (C/8)/2;                    // = 4
6871                        FOR_UNROLL (short cc = 0; cc < NC; ++cc) {
6872                            s8x8_t vs[2];
6874                            simdgroup_load(vs[0], ss + 16*cc + 0, SH, 0, false);   // P: 8 queries x 8 positions
6875                            simdgroup_load(vs[1], ss + 16*cc + 8, SH, 0, false);
6877                            FOR_UNROLL (short ii = 0; ii < NO/2; ++ii) {
6878                                v8x8_t mv[4];
6880                                simdgroup_load(mv[0], pv + 0*NSG + 16*ii*NSG + 0*8*NS20, NS20, 0, false);
6881                                simdgroup_load(mv[1], pv + 8*NSG + 16*ii*NSG + 0*8*NS20, NS20, 0, false);
6882                                simdgroup_load(mv[2], pv + 0*NSG + 16*ii*NSG + 1*8*NS20, NS20, 0, false);
6883                                simdgroup_load(mv[3], pv + 8*NSG + 16*ii*NSG + 1*8*NS20, NS20, 0, false);
6885                                simdgroup_multiply_accumulate(lo[2*ii + 0], vs[0], mv[0], lo[2*ii + 0]);
6886                                simdgroup_multiply_accumulate(lo[2*ii + 1], vs[0], mv[1], lo[2*ii + 1]);
6887                                simdgroup_multiply_accumulate(lo[2*ii + 0], vs[1], mv[2], lo[2*ii + 0]);
6888                                simdgroup_multiply_accumulate(lo[2*ii + 1], vs[1], mv[3], lo[2*ii + 1]);
6889                            }
6891                            pv  += 2*8*NS20;
6892                        }
```

Shapes: `vs[k]` = P (8q × 8c, float, non-transposed from `ss`); `mv[k]` = V (8c × 8d, half, device); `lo += vs·mv` (8q × 8d, float). Each outer `cc` consumes 16 cache positions; each `ii` covers 2 of the SG's 4 output blocks. Fragments stored back once per tile (6896–6903, mirror of the hoist). Every SG loads the **full** P tile — P is the only redundantly-loaded operand (4×). Quantized-V branch (6905–6970) dead.

### 2.6 Epilogue — sinks, normalization, writeback

**Sink correction (6976–6994)** — post-loop, *not* per-tile; compiled out here (`has_sinks=false`). One extra online-softmax step folding `sinks[iq2]` into M/S (lane 0 carries the sink; other lanes contribute `-FLT_MAX/2`, so `simd_sum(vs)` = `exp(s−M)`), rescaling `so` by `ms`. It inflates only the denominator, contributing nothing to the numerator.

**Normalization + store (6997–7019):**

```metal
7004            device float4 * dst4 = (device float4 *) dst + ((uint64_t)iq3*args.ne2*args.ne1 + iq2 + (uint64_t)(iq1 + j)*args.ne1)*DV4;
7006            const float scale = S[jj] == 0.0 ? 0.0f : 1.0f/S[jj];
7012            dst4[i] = (float4) so4[j*PV4 + i]*scale;
```

Single reciprocal per row at store time, with an all-masked guard (`S==0 → 0`). Ragged rows break out at 7000–7002. **No cross-SG combination step exists** — column contributions were merged in `so` under the tile-end barrier; each SG writes only rows {s, s+4}; no barrier is needed between loop and writeback. Output layout: dst f32, row index = `token*ne1 + head` (heads contiguous within a token — the standard ggml FA output permutation), dst assumed dense. DV4 = NW → one float4 per lane per row.

### 2.7 Barrier inventory

Exactly **four** `threadgroup_barrier(mem_flags::mem_threadgroup)` sites in the live path (a fifth, 6648, is inside the `#if 0` block):

| line | position | hazard guarded |
|---|---|---|
| **6534** | after init, before loop | Init→first use. Each SG wrote only rows {s,s+4} of `sq`/`so`/`ss`, but QK^T reads all 8 rows of `sq`, and the maskless mask-add reads zero-initialized `sm2` slots. RAW across SGs. |
| **6777** | after QK^T stores, before softmax | SG `s` stored score **columns** {s,s+4} of `ss`; softmax on row `j` reads all 64 columns written by all 4 SGs. RAW on `ss`. (Also orders the blk==1 `sm2` stores, though those are same-SG.) |
| **6824** | after softmax, before PV | Softmax wrote P rows {s,s+4} and rescaled `so` rows {s,s+4}; PV has every SG read the **full** P tile and full-height `lo` column slices of `so`. RAW on `ss` and `so`. |
| **6973** | end of tile body | (a) PV stored column slices of all rows of `so`; next tile's softmax rescale / final writeback reads full rows — RAW. (b) Next tile's QK stores and mask stores overwrite `ss` that this tile's PV was reading — WAR. |

Plus `simdgroup_barrier(mem_flags::mem_none)` at **6694/6702** — per-SG instruction scheduling fences, no memory semantics (the analogous 6678/6683 and the `mem_threadgroup` simdgroup barriers at 6926/6950 are in dead branches).

**Skipped tiles (blk==0) execute zero barriers** — the `continue` at 6610 fires before all of them; safe because a skipped iteration writes nothing to threadgroup memory. All 4 SGs read the same `blk[ic0]`, so the branch is threadgroup-uniform.

### 2.8 Per-K-tile cost counts (DK=DV=128, Q=8, C=64, NSG=4, F16 KV)

**Barriers:**
- computed tile (blk ∈ {1,2} or maskless): **3** `threadgroup_barrier(mem_threadgroup)` (6777, 6824, 6973) + **32** `simdgroup_barrier(mem_none)` per SG (2 per inner iteration × 8 iterations × NC=2 column blocks);
- skipped tile (blk==0): **0**;
- plus 1 one-time init barrier (6534).

**MMAs (`simdgroup_multiply_accumulate`, 8×8×8) per SG per tile:**
- QK^T: NC × DK8 = 2 × 16 = **32** (half×half→float)
- PV: 4 × 2 × 4 = **32** (float×half→float)
- → 64/SG/tile = **256/threadgroup/tile** (128 QK + 128 PV) — both exactly `8·64·128/8³`, i.e. the theoretical minimum, zero duplicated MMA work across SGs.

**`simdgroup_load`/`store` per SG per tile:** QK: 32 `mq` (tg) + 32 `mk` (device, transposed) + 2 `mqk` stores; PV: 4 `lo` (tg) + 8 `vs` (tg) + 32 `mv` (device) + 4 `lo` stores.

**Threadgroup memory (10240 B total):** `sq` 2048 + `so` 4096 + `ss` 4096 (of which scores/P 2048 + mask 1024 + **1024 unused padding**, 128 B/row).

**Device traffic per threadgroup per steady-state tile:** K 64×128×2 = 16 KiB, V 16 KiB, mask (blk==1 only) 8×64×2 = 1 KiB, `blk[ic0]` 1 byte; Q read once per threadgroup (8×128×4 = 4 KiB f32); dst written once (8×128×4 = 4 KiB).

**Registers of note per thread:** `M[2]`, `S[2]` floats (never in shmem); per SG: 4 `lo` float8x8 during PV, 2+2 half8x8 (`mq`/`mk`) + 1 float8x8 (`mqk`) during QK.

---

## 3. The kargs ABI

### 3.1 `ggml_metal_kargs_flash_attn_ext` (impl.h:365–398) — byte-exact layout

C/MSL natural alignment (uint64_t 8-aligned in both → host and shader agree). **sizeof = 192**, passed via `setBytes` at buffer index 0 (ops.cpp:2929). Three 4-byte internal holes (offsets 12, 84, 124) + 4-byte tail — replicate them (zero-fill).

| # | field | type | offset | filled from (ops.cpp:2891–2924) | Qwen3 matrix path value |
|---|---|---|---|---|---|
| 1 | ne01 | i32 | 0 | ne01 | m (e.g. 256) |
| 2 | ne02 | i32 | 4 | ne02 | 16 (Q heads) |
| 3 | ne03 | i32 | 8 | ne03 | 1 |
| — | *hole* | — | 12 | — | 0 |
| 4 | nb01 | u64 | 16 | nb01 | Q row stride B (contig: 512) |
| 5 | nb02 | u64 | 24 | nb02 | Q head stride B |
| 6 | nb03 | u64 | 32 | nb03 | Q batch stride B |
| 7 | ne11 | i32 | 40 | ne11 | n_kv |
| 8 | ne_12_2 | i32 | 44 | **ne12** (K's dim2) | 8 (KV heads) |
| 9 | ne_12_3 | i32 | 48 | **ne13** | 1 |
| 10 | ns10 | i32 | 52 | `int32_t(nb11/nb10)` | 128 (K row stride, elements) |
| 11 | nb11 | u64 | 56 | nb11 | 256 (K row stride B) |
| 12 | nb12 | u64 | 64 | nb12 | K head stride B |
| 13 | nb13 | u64 | 72 | nb13 | K batch stride B |
| 14 | ns20 | i32 | 80 | `int32_t(nb21/nb20)` | 128 |
| — | *hole* | — | 84 | — | 0 |
| 15 | nb21 | u64 | 88 | nb21 | 256 |
| 16 | nb22 | u64 | 96 | nb22 | V head stride B |
| 17 | nb23 | u64 | 104 | nb23 | V batch stride B |
| 18 | ne31 | i32 | 112 | ne31 | mask rows (≥ ne01, ideally %8==0) |
| 19 | ne32 | i32 | 116 | ne32 | 1 (broadcast over heads) |
| 20 | ne33 | i32 | 120 | ne33 | 1 |
| — | *hole* | — | 124 | — | 0 |
| 21 | nb31 | u64 | 128 | nb31 | mask row stride B (2·ne30) |
| 22 | nb32 | u64 | 136 | nb32 | mask dim2 stride B |
| 23 | nb33 | u64 | 144 | nb33 | mask dim3 stride B |
| 24 | ne1 | i32 | 152 | dst ne[1] | 16 (n_head) |
| 25 | ne2 | i32 | 156 | dst ne[2] | n_tokens |
| 26 | ne3 | i32 | 160 | dst ne[3] | 1 |
| 27 | scale | f32 | 164 | op_params[0] (÷softcap if scap) | 1/√128 |
| 28 | max_bias | f32 | 168 | op_params[1] | 0.0 |
| 29 | m0 | f32 | 172 | `2^(−max_bias/n_head_log2)` | 1.0 |
| 30 | m1 | f32 | 176 | `2^(−max_bias/2/n_head_log2)` | 1.0 |
| 31 | n_head_log2 | i32 | 180 | `1u << floor(log2(n_head))` | 16 |
| 32 | logit_softcap | f32 | 184 | op_params[2] | 0.0 |
| — | *tail pad* | — | 188 | — | 0 |

`ggml_metal_kargs_flash_attn_ext_vec` (impl.h:400–433) is **field-for-field identical** (same 192 bytes), just a distinct type. When maskless, ne31…nb33 come from null-src3 tensor locals — garbage-but-unused (kernel gated on `has_mask`); a harness fills them with 0.

Auxiliary structs: pad kargs (impl.h:336–352) = `{i32 ne11, ne_12_2, ne_12_3; [hole@12] u64 nb11,nb12,nb13,nb21,nb22,nb23; i32 ne31,ne32,ne33; [hole@76] u64 nb31,nb32,nb33}` → **sizeof 104**. blk kargs (354–363) = `{i32 ne01, ne30, ne31, ne32, ne33; [hole@20] u64 nb31, nb32, nb33}` → **sizeof 48**. vec_reduce kargs (435–437) = `{i32 nrows}`.

### 3.2 Buffer bindings (matrix main kernel, ops.cpp:2928–2939)

| index | binding |
|---|---|
| 0 (bytes) | kargs, 192 B |
| 1 | Q (`bid_src0`, F32) |
| 2 | K (`bid_src1`, F16) |
| 3 | V (`bid_src2`, F16) |
| 4 | mask (`bid_src3`, F16; **= Q's buffer as placeholder if no mask**, ops.cpp:2762) |
| 5 | sinks (`bid_src4`, F32; = Q's buffer if none, 2763) |
| 6 | pad scratch (`bid_pad`) |
| 7 | blk scratch (`bid_blk`) |
| 8 | dst (F32) |
| tg-mem 0 | 10240 B |

Aux bindings: pad kernel — 0=kargs(104B), 1=K, 2=V, 3=mask, 4=`bid_pad` (2813–2817). blk kernel — 0=kargs(48B), 1=mask, 2=`bid_blk` (2844–2846). Vec kernel — 0=kargs, 1..5 as matrix, 6=`bid_pad`, 7=`bid_dst` (nwg==1) or `bid_tmp` (nwg>1) — **no blk buffer** (3085–3086, 3099–3100). vec_reduce — 0=kargs(4B), 1=`bid_tmp`, 2=`bid_dst` (3119–3121).

### 3.3 Function constants + pipeline naming (device.cpp:1410–1473)

```c
1427    const int32_t ns10 = op->src[1]->nb[1]/op->src[1]->nb[0];
1428    const int32_t ns20 = op->src[2]->nb[1]/op->src[2]->nb[0];
1431    const bool bc_mask = op->src[3] && (op->src[3]->ne[1] % 8 != 0);
1433    snprintf(base, 256, "kernel_%s_%s_dk%d_dv%d", "flash_attn_ext", ggml_type_name(op->src[1]->type), dk, dv);
1439    snprintf(name, 256, "%s_mask=%d_sinks=%d_bias=%d_scap=%d_kvpad=%d_bcm=%d_ns10=%d_ns20=%d_nsg=%d", ...);
```

`base` is the metallib `host_name` to specialize; `name` is only the cache key. Qwen3 F16 contiguous KV: **base = `kernel_flash_attn_ext_f16_dk128_dv128`**, name = `..._mask=1_sinks=0_bias=0_scap=0_kvpad=0_bcm=0_ns10=128_ns20=128_nsg=4`.

FCs at pipeline creation (device.cpp:1455–1465; shader decls metal:6369–6383), base 300:

| FC index | shader name | type | Qwen3 causal value |
|---|---|---|---|
| 300 | `FC_flash_attn_ext_has_mask` | bool | **true** |
| 301 | `FC_flash_attn_ext_has_sinks` | bool | false |
| 302 | `FC_flash_attn_ext_has_bias` | bool | false |
| 303 | `FC_flash_attn_ext_has_scap` | bool | false |
| 304 | `FC_flash_attn_ext_has_kvpad` | bool | false (true iff n_kv%64≠0) |
| 310 | `FC_flash_attn_ext_bc_mask` | bool | false (mask ne[1]%8==0) |
| 320 | `FC_flash_attn_ext_ns10` | i32 | **128** |
| 321 | `FC_flash_attn_ext_ns20` | i32 | **128** |
| 322 | `FC_flash_attn_ext_nsg` | i32 | **4** |

Note `ns10`/`ns20` are baked as FCs **and** passed in kargs — a harness buffer stride must match the pipeline's specialization or a new pipeline is required. Companion pipelines: pad — FCs `has_mask` @ **100**, `ncpsg` @ **125** (device.cpp:1347, 1357); blk — `nqptg` @ **224**, `ncpsg` @ **225** (1399–1400); vec — 5 bools @ 400+0..4, ns10/ns20/nsg/nwg @ 420–423 (1517–1526; name uses `sink=` not `sinks=`, no `bcm`); vec_reduce — `DV` @ **500**, `NWG` @ **501** (1553–1554).

---

## 4. Host-side policy

### 4.1 Vec-vs-matrix (ops.cpp:2578–2586)

```c
return (ne01 < 20) && (ne00 % 32 == 0);
```

Qwen3 d_head=128 → decode (m ≤ 19) = vec path; prefill (m ≥ 20) = matrix path.

### 4.2 All runtime decisions

| decision | line | code | Qwen3 |
|---|---|---|---|
| softcap fold | 2742–2744 | `if (logit_softcap != 0.0f) scale /= logit_softcap;` | no-op |
| has_mask/sinks/bias/scap | 2746–2749 | src3/src4 null-checks; `max_bias != 0`; `softcap != 0` | T/F/F/F |
| ALiBi params | 2751–2755 | `n_head_log2 = 1u << floor(log2(n_head))`; m0/m1 powers | 16, 1.0, 1.0 |
| query cap | 2757 | `GGML_ASSERT(ne01 < 65536)` | ok |
| has_kvpad | 2787 (matrix) / 2955 (vec) | `ne11 % ncpsg != 0` | false when n_kv%64==0 |
| nsg (matrix) | 2887 | `ne00 >= 512 ? 8 : 4` (adaptive logic 2871–2886 commented out) | **4** |
| is_q | 2860 | `ggml_is_quantized(K type)` | 0 |
| bc_mask | device.cpp:1431 | `mask && mask->ne[1] % 8 != 0` | false |
| nwg/nsg (vec) | 3015–3027 | `nwg=32; nsg=1; while (2*nwg*nsg*ncpsg < ne11 && nsg < 4) nsg *= 2;` | nsg=1 ≤2048 kv, 2 ≤4096, else 4 |
| nhptg (vec) | 2947 | 1 head per threadgroup | 1 |

Input contract (ops.cpp:2721–2732): `ne00 % 4 == 0`; Q is F32; K type == V type; `ne11 == ne21`; `ne12 == ne22`; mask (if present) is F16 with `ne[1] >= ne01`; vec additionally `ne10 >= ne20` (3000).

### 4.3 Threadgroup memory formulas

Matrix (2869): `GGML_PAD((8·(DK + 2·GGML_PAD(DV,64) + 4·64) + is_q·512·nsg)·2, 16)` → **10240 B** for f16 DK=DV=128 (nsg-independent). Vec (3009): `GGML_PAD((GGML_PAD(DK,128) + 4·32 + 2·GGML_PAD(DV,128))·nsg·2, 16)` → **1024 B** at nsg=1.

### 4.4 GQA mapping

No explicit broadcast field. Kernel derives it (metal:6499–6503):

```metal
6499        const short ikv2 = iq2/(args.ne02/args.ne_12_2);   // 16/8 = broadcast factor 2
6500        const short ikv3 = iq3/(args.ne03/args.ne_12_3);
6502        k += ikv2*args.nb12 + ikv3*args.nb13;
6503        v += ikv2*args.nb22 + ikv3*args.nb23;
```

Grid dim y = ne02, so one threadgroup column per **query** head; integer division maps it to a KV head (requires `ne02 % ne_12_2 == 0`). Mask broadcasts separately by modulo: `(iq2%ne32)*nb32 + (iq3%ne33)*nb33` (6486) — a [n_kv, n_q, 1, 1] mask serves all 16 heads. Same formula in the kvpad branch with pad-plane stride `nb11*C` (6567–6571).

### 4.5 KV-cache layout expectations (f16)

Rows (one head-vector per position) may be strided (`nb11`/`nb21` free); element stride within a row must be dense (ns10 = nb11/nb10 only meaningful then). Head/batch strides free-form via nb12/nb13/nb22/nb23. No length-padding requirement on the buffer itself — a ragged tail is handled by the pad pre-pass + `kvpad=1` pipeline. dst is assumed dense (kargs carry no dst strides).

---

## 5. Auxiliary kernels

### 5.1 `kernel_flash_attn_ext_blk` (metal:6314–6367) — mask tile classifier

Matrix path only, mask present only. One threadgroup = one simdgroup = one 64×8 mask tile. Decode: `i3 = tgpig[2]/ne32; i2 = tgpig[2]%ne32; i1 = tgpig[1]` (query block); `i0 = tgpig[0]` (KV block) (6326–6329).

**Classification:** boundary short-circuit `char res = i0*C + C > args.ne30 ? 1 : 0;` (6331 — an overhanging tile is force-classified 1 without scanning; its overhang is sourced from the pad buffer's −MAXHALF columns). Otherwise full scan (6336–6359): each lane reads `Q·C/NW = 16` halves striding NW, tracks min/max, then `simd_min`/`simd_max`; decision: `mmax <= -MAXHALF` → 0; `mmin==0 && mmax==0` → 2; else → 1. Output: one int8 per tile at `dst[((i3*ne32 + i2)*nblk1 + i1)*nblk0 + i0]`, `i0` fastest (6361–6366), by lane 0.

Cost for causal 256²: 128 threadgroups × 32 threads; the entire 128 KB mask is read once to produce 128 bytes; census 48× class-0 / 48× class-2 / 32× class-1 — a fact that is a pure function of (i0, i1).

### 5.2 `kernel_flash_attn_ext_pad` (metal:6242–6305) — K/V/mask tail padding

Runs on both paths iff `ne11 % ncpsg != 0`. Grid `(ncpsg, max(ne12,ne32), max(ne13,ne33))` × 32 threads (ops.cpp:2822/2990). It materializes a bounds-safe replacement chunk because the main kernels do full-width unbounds-checked loads over whole C-sized tiles:

```metal
6253    device char * k_pad    = dst;
6254    device char * v_pad    = k_pad + args.nb11*C*args.ne_12_2*args.ne_12_3;
6255    device char * mask_pad = v_pad + args.nb21*C*args.ne_12_2*args.ne_12_3;
6257    const int32_t icp = args.ne11 % C;      // real rows in the last partial chunk
6258    const int32_t ic0 = args.ne11 - icp;    // its start
```

K/V rows `i1 < icp` copied byte-wise (6280–6285), rows `i1 >= icp` zero-filled (6271–6278 — safe, "we rely on masking out the scores"). Mask (6289–6304): for every query row `ib`, a contiguous C-column chunk at `mask_pad + C*ib + C*ne31*i2 + C*ne31*ne32*i3`; real columns copied, phantom columns `-MAXHALF`. Consumers swap base pointers for the final iteration (matrix 6561–6596, vec 7402–7426). `has_kvpad` is baked into the main pipeline (FC 304/404) — padded and unpadded runs are distinct binaries.

### 5.3 Vec path: `kernel_flash_attn_ext_vec` (7280–7710) + `kernel_flash_attn_ext_vec_reduce` (7849–7889)

Decode kernel: Q=1, C=32; per-head-size `NE` ("head elements per thread") from the instantiations: dk32→4, dk64→2, dk96→4, **dk128→1** (line 7767), dk192→2, dk256→1. For DK=128: NE=1, NL=NW/NE=32. Kargs identical to matrix (§3.1); FCs add `nwg` (7259); buffer list has **no blk** (7280–7292).

Geometry: grid `((ne01+0)/1, ne02, ne03*nwg)` × (32, nsg, 1) threads (ops.cpp:3090/3103); nwg=32 always (3022). KV strided round-robin over all NWG·NSG simdgroups (7396): `for (int ic0 = iwg*NSG + sgitg; ; ic0 += NWG*NSG)`. Shmem (7327–7331): `sq4` (PK=PAD2(DK,128) halves, shared), per-SG `ss` (SH=4·C) with mask scratch `sm` at +2·C, per-SG full f32 output vector `so4`.

Per 32-key chunk: mask row loaded one half per lane, then the **inline** replacement for the blk pre-pass (7428–7435):

```metal
7428            if (FC_flash_attn_ext_vec_has_mask) { sm[tiisg] = pm[ic + tiisg]; }
7432            // skip -INF blocks
7433            if (simd_max(sm[tiisg]) <= -MAXHALF) { continue; }
```

Q·K^T is **dot-product based**: for NE=1, all 32 lanes cooperate on one key (`mqk[cc] += dot((float4) pk4[...], (float4) pq4[...])`, 7451), completed by `simd_sum` (7468); NE>1 uses a `simd_shuffle_down` chain (7476–7492). Scale+mask fused via `fma(mqk[tx], args.scale, (qk_t) sm[...])` on the fast path (7496–7499). Online softmax per chunk (7519–7540) with `so4 *= ms`. O accumulation via per-lane float4 products (7558–7561) + shuffle-down tree when NE>1 (7578–7613). K/V f16 read directly from device. Sink fold gated `sgitg == 0 && iwg == 0` (7623). Intra-SG chunk barriers are `simdgroup_barrier(mem_threadgroup)` (7517, 7542).

**Two-level reduction:** Level 1 — intra-threadgroup log2 tree over shared memory merging (S, M, O) triples (7652–7680): `so4[i] = so4[i]*ms0 + so4[i + r*PV4]*ms1`. Level 2 — each workgroup writes unnormalized partial O interleaved by workgroup (`dst4[rid*DV4*NWG + NWG*i + iwg]`) plus its (S, M) pair after the O block (7683–7704), into `bid_tmp`; then after a concurrency reset (3106), `kernel_flash_attn_ext_vec_reduce` runs with grid `(nrows,1,1)` × `32*nwg` threads (3123): lane = workgroup (`iwg = tiisg`), simdgroup strides DV; merges `M/S` via `simd_max`/`simd_sum` and reduces the interleaved partials (7859–7885), with the same `S==0` guard (7872). When nwg==1 the kernel normalizes and writes dst directly (7690).

| | matrix | vec |
|---|---|---|
| trigger | `ne01 ≥ 20` or `DK%32≠0` | `ne01 < 20 && DK%32==0` |
| tile | 8×64 | 1×32 |
| compute | simdgroup 8×8 MMA | `dot()` + shuffle trees |
| mask skip | precomputed blk (0/1/2) | inline `simd_max ≤ −MAXHALF → continue` |
| KV parallelism | 1 threadgroup walks full KV | split over 32 workgroups × NSG SGs + 2nd pass |
| output | direct to dst | via tmp (interleaved partials + S/M) unless nwg==1 |

---

## 6. Negative specification for Qwen3 (ablation ledger input)

Workload facts: pure causal mask, no ALiBi/softcap/sinks, DK=DV=128, GQA 16→8, F16 KV, occupancy known at dispatch. Every row below is generality llama.cpp pays for because the mask is an opaque runtime tensor / shapes are runtime values; a causality-specialized, shape-fixed kernel deletes it. Class **[FC]** = already compiled out by function constants in llama.cpp's own binary (no perf win available, only code-size/complexity win); all other rows are live costs.

| # | item | where (lines) | live cost in llama.cpp | replacement in specialized kernel |
|---|---|---|---|---|
| N1 | blk pre-pass dispatch | metal 6314–6367; ops 2827–2854 | 128 threadgroups per FA op (256² case); full 128 KB mask read → 128 B output | closed-form: tile class 0 iff `C·i0 > Q·i1 + (Q−1) + n_past`, class 2 iff `C·i0 + C−1 ≤ Q·i1 + n_past` — two integer compares in-kernel |
| N2 | pre-pass↔main encoder barrier | ops 2856–2858 | serialization of every FA op against its pre-pass | none needed |
| N3 | mask tensor itself | graph-level | materialization + storage + the reads in N1/N6 | no mask tensor exists |
| N4 | `extra_blk` reservation | ops 2662–2668 | `ceil(m/8)·ceil(n_kv/64)` bytes per FA node (reserved even on vec path, 2658–2660) | none |
| N5 | per-tile `blk[ic0]` device load + 3-way branch | metal 6603–6629 | 1 byte + branch per tile per threadgroup | loop bound: `ic_max(iq1) = (n_past + Q·(iq1/Q) + Q−1)/C + 1`; never *visits* future tiles (beats llama.cpp's own ceiling: blk==0 tiles still cost an iteration + load + `pm2` advance) |
| N6 | mask load to shmem for diagonal tiles | metal 6613–6624 | 1 KiB device traffic + shmem writes per blk==1 tile | analytic column predicate `ic + col ≤ q` on diagonal tiles only |
| N7 | mask add in softmax | metal 6793–6799 | 1 half2 read + float2 add per lane per row per non-class-2 tile | `−INF` select on the diagonal tile's boundary columns; nothing elsewhere |
| N8 | mask shmem region + zero-init + padding | metal 6478, 6529–6531; ops 2869 | 1 KiB mask slots + 1 KiB dead padding of the 10240 B smem; init stores | `ss` shrinks toward 2048 B (scores only) |
| N9 | `pm2` pointer setup/advance | metal 6481–6487, 6607/6623/6627 | 2 device pointers per thread + advance every tile incl. skipped | none |
| N10 | pad pre-pass + kvpad redirect | metal 6242–6305, 6562–6597; ops 2789–2825 | (only when n_kv%64≠0) copy dispatch + `-MAXHALF` writes for all ne31 rows + barrier + pointer-swap branch | fix n_kv to a 64-multiple at allocation, or one `col < ne11` compare in the last iteration |
| N11 | `extra_pad` reservation | ops 2621–2628 | `64·(nb11·ne12·ne13 + nb21·ne22·ne23 + 2·ne31·ne32·ne33)` B per FA node, always | none |
| N12 | `extra_tmp` reservation on matrix ops | ops 2689–2696 (`if (true)`) | ~8.5 MB per prefill node that never uses it | size once, decode only |
| N13 | `bc_mask` variant | metal 6617–6618; device 1431 | dead branch when mask%8==0 | fixed shapes: gone |
| N14 | runtime NSG switch + ns10/ns20 FCs + kargs stride duplication | metal 7069–7075, 6433–6434; device 1463–1465 | pipeline plumbing; FC-fed `ld` registers | compile-time constants (NSG=4, ld=128) |
| N15 | GQA integer division | metal 6499–6500 | 2 divisions per threadgroup | `ikv2 = iq2 >> 1` folded at compile time |
| N16 | mask modulo broadcast | metal 6486 | 2 modulos per row pointer | fixed (ne32=ne33=1) |
| N17 | ragged-Q guards | metal 6513–6517, 7000–7002 | per-load compare + writeback break | m%8==0 fixed: gone |
| N18 | `S==0` guards | metal 7006 (matrix), 7690/7872 (vec) | select per row | causal ⇒ every row attends to ≥1 key: gone |
| N19 | quantized-KV branches + `is_q` staging | metal 6714–6774, 6905–6970 (6673-6686 is a SEPARATE dead branch, `DK % 16 != 0`, not quantization-related — corrected below) | dead code (compile-time `is_same`), template weight | not instantiated |
| N20 | ALiBi / softcap / sinks | metal 6544–6551, 6788–6790, 6976–6994 | **[FC]** compiled out | not written |
| N21 | vec: per-chunk mask load + `simd_max` skip check + `fma` mask add | metal 7428–7435, 7499 | ~n_kv half-reads + one cross-lane reduction per 32-key chunk per (head × pass) that never fire in pure decode | plain `mqk*scale`; no `sm` region (vec smem 4·C → 2·C) |
| N22 | vec: kvpad redirect | metal 7402–7426 | branch per chunk | per N10 |
| N23 | vec: split-KV (nwg=32) + 2-pass reduce | metal 7652–7704, 7849–7889; ops 3091–3124 | **NOT deletable** — required to occupy the GPU at m=1; keep the shape, trim only N18-style guards and exact tmp sizing | keep |

**Net:** two of the three auxiliary kernels (`_blk`, `_pad`), their buffer reservations, and their encoder barriers are pure negative-specification for a known-causal workload — llama.cpp pays a mask materialization, a full mask scan, a K/V/mask copy, and two encoder barriers per attention op to discover at runtime structure (triangularity, tail length) that is a dispatch-time integer predicate. The matrix kernel's per-tile MMA schedule itself (§2.8) is already minimal — the replica's headroom is in the deleted machinery and loop bounds, not the MMA count.

## 7. Open questions / uncertainties

1. **Mask tensor shape at the graph boundary.** `ne30/ne31` (mask KV width and row count, incl. `GGML_KQ_MASK_PAD` row padding) are produced by llama.cpp graph code **not vendored here** — only the constraints are verified (`ne31 ≥ ne01`, ops.cpp:2731; `bc_mask` iff `ne31 % 8 != 0`, device.cpp:1431). Verify actual values by tracing a live run before freezing harness constants (the §1 census assumed ne30 = 256, ne31 = 256).
2. **`ggml_metal_op_concurrency_reset` semantics** (ggml-metal-common.cpp, not read for this teardown): whether it splits encoders or inserts a memory barrier. The harness must provide equivalent ordering (two encoders or `MTLBarrierScopeBuffers`) at ops.cpp:2856, 3106.
3. **`simdgroup_barrier(mem_flags::mem_none)` effect** (6694/6702): a scheduling fence with no memory semantics; its actual perf effect on M-series is unverified. The `#pragma unroll (MIN(DK8/2, 4*NSG))` with the "too much unroll can tank the performance" note (6691) is empirically tuned — the Mojo replica must benchmark its own unroll factor rather than assume 8 is optimal.
4. **Numerics for bit-comparison:** `exp` at 6803–6804 is Metal fast-math exp; only the softcap path uses `precise::tanh` (6789). Q undergoes f32→f16 at load (6514); scores/P/O stay f32. A Mojo replica will not be bit-identical; the comparison harness needs a tolerance derived from these precision points (cf. the Mojo transcendental floor in memory).
5. **`FOR_UNROLL` definition** was not independently verified (assumed `#pragma unroll` wrapper); no behavioral impact on this analysis.
6. **Vec smem formula quirk** (ops.cpp:3009): multiplies the whole sum — including the *shared* `sq` region — by nsg, over-allocating `(nsg−1)·PK·2` bytes. Replicate the formula, not a derivation, if reproducing the vec path.
7. **Contract edges not exercised by Qwen3:** behavior when `ne02 % ne_12_2 != 0` (GQA division silently truncates — no assert); `dst` is assumed dense (no dst strides in kargs); `ne01 < 65536` (2757) vs the `uint64_t` casts in the dst index (7004). A harness must respect all three.
8. **Homebrew build 10210 ↔ commit correspondence** is taken as pinned by the vendoring step; the replica's baseline numbers must come from a binary built at exactly `000547513`, since the FA kernels are under active upstream churn.

---

## Appendix: adversarial verification pass

Independently re-checked against the vendored source (not the maps) by a separate agent, after
the synthesis pass above had already self-corrected two arithmetic slips (noted in its own
preamble: *"two arithmetic slips in Map 1 corrected: the `ss` padding is 8×128 B not 8×64 B, and the QK inner loop issues 32 not 16 `simdgroup_barrier`s per SG per tile; Map 3's `extra_pad` formula corrected to make the mask term conditional on `has_mask`"*).

All verification passes are complete. Every file, line number, struct offset, and derived constant has been checked against the vendored source.

## VERDICT

### CONFIRMED (verified against source)

**Section 1 (dispatch flow):** `use_vec` predicate (ops.cpp:2585); pad condition `ne11 % ncpsg != 0` (2787); pad grid `(ncpsg, max(ne12,ne32), max(ne13,ne33))` (2822); blk grid `(nblk0, nblk1, ne32*ne33)` (2848–2851) = (4,32,1) for 256²; concurrency reset gated on `need_sync` (2856–2858); main grid `((ne01+7)/8, ne02, ne03)` × (32,4,1) (2941); scratch chain `bid_pad/bid_blk/bid_tmp` appended after `ggml_nbytes(op)` (2765–2774); unconditional reservations — `if (false)` at 2608, commented-out vec early-return 2658–2660, `if (true)` at 2689; all three extra formulas (2624–2627, 2662–2668, 2690–2696) including the has_mask-conditional F16 term and `GGML_PAD(...,32)`; concrete numbers recomputed: extra_pad = 64·(2048+2048+512) = 294,912 B, extra_blk = 128 B, extra_tmp = 8,519,680 B, dst = 2,097,152 B. Blk census independently re-derived: 48 class-0 / 48 class-2 / 32 class-1, and the two integer predicates are correct.

**Section 2 (kernel):** All quoted line numbers in §2 land exactly (template 6386–6414, body 6415–7023, constants 6443–6462, carve 6464–6478, pm2 6481–6487, blk offset 6489–6494, GQA 6499–6503, Q load 6506–6519, init 6521–6532, loop 6555–6557, kvpad 6562–6597, blk consume 6599–6629, `#if 0` 6631–6652, QK 6657–6713, softmax 6779–6822, PV 6826–6904, sinks 6976–6994, writeback 6997–7019, wrapper switch 7069–7075, FA_TYPES 7083–7089, instantiation 7136). Derived constants recomputed: DK4=32, DK8=16, PV=128, NQ=2, SH=128 floats, TS=256 halves, T=384 halves.

**Threadgroup memory map (recomputed from source constants):** `sq` halves [0,1024) = 2048 B; `so` [1024,3072) = 4096 B (float, ld=PV); `ss` [3072,5120) = 4096 B (row = 64 floats scores + 64 halves mask at [128,192) + 64 halves unused [192,256), 1024 B total dead padding); `sk/sv` at 5120 + sgitg·512 halves, quantized-only. Host formula (2869) recomputed = exactly **10240 B**, nsg-independent for is_q=0; no smem-cap assert on the matrix path (assert only at 3079, vec). Struct-compile check confirms every region boundary.

**Barrier inventory (grep of 6242–7078):** live-path `threadgroup_barrier(mem_threadgroup)` sites are exactly **6534, 6777, 6824, 6973 — the document lists all four; nothing missing on the live path**. `simdgroup_barrier(mem_none)` 6694/6702 live; 6678/6683 dead (DK%16 branch). Per-tile counts verified: 3 tg-barriers per computed tile, 0 per skipped tile (continue at 6610 precedes all three), 32 mem_none barriers/SG/tile (2 × 8 unrolled × NC=2). Skipped-tile safety argument (no tg-memory writes before `continue`) confirmed against 6605–6610.

**kargs ABI:** compiled a byte-identical C replica of impl.h:365–398 — **sizeof = 192**, offsets match the table field-for-field: ne01@0…ne03@8, hole@12, nb01@16…nb03@32, ne11@40, ne_12_2@44, ne_12_3@48, ns10@52, nb11@56…nb13@72, ns20@80, hole@84, nb21@88…nb23@104, ne31@112…ne33@120, hole@124, nb31@128…nb33@144, ne1@152…ne3@160, scale@164…m1@176, n_head_log2@180, logit_softcap@184, tail pad→192. Vec struct (400–433) field-for-field identical. Pad kargs sizeof 104 (holes @12, @76), blk kargs sizeof 48 (hole @20), vec_reduce `{i32 nrows}` — all as documented. Buffer bindings 0–8 + tg-mem (2928–2939), pad bindings (2813–2817), blk bindings (2844–2846), vec bindings incl. no-blk (3070–3074, 3085–3086, 3099–3100), vec_reduce (3119–3123) all match. FC indices: matrix 300–304/310/320–322 (device.cpp:1455–1465, metal:6369–6383), pad 100/125 (1347/1357), blk 224/225 (1399–1400), vec 400–404/420–423 (1517–1526, name uses `sink=`, no `bcm`), vec_reduce 500/501 (1553–1554). base/name split and the exact name format string (1433, 1439) confirmed.

**SIMD-group ownership (re-derived from loops):** `j = jj*NSG + sgitg` → rows {s, s+4} interleaved, used at 6484/6508/6523/6615/6781/6978/6999. QK: `pk += sgitg*8*NS10`, `ps += sgitg*8`, advance `8*NSG` (6663–6664, 6711–6712) → score column blocks {s, s+4}, K positions [ic+8s,ic+8s+8)∪[ic+8s+32,ic+8s+40) — matches. PV: NO=4, `sot = so + 8*sgitg` stride `8*NSG` (6837–6842) → O column blocks {s,s+4,s+8,s+12}; mv offsets (6880–6883) re-derived to dims [8s,8s+8)∪[8s+32,+8)∪[8s+64,+8)∪[8s+96,+8), 16 cache positions per `cc` (`pv += 2*8*NS20`); every SG loads the full 8×64 P tile (vs at `ss + 16*cc {+0,+8}`, 4× redundant) — matches. MMA counts verified: 32 QK + 32 PV per SG per tile = 256/threadgroup, the row/column ownership flip and "no cross-SG reduction" claims hold.

**Sections 4–5:** every host-policy line cite checked (2721–2757, 2742–2744, 2860, 2887 + commented 2871–2886, 3000, 3009, 3015–3027, 2947, device 1427–1431); vec smem = 1024 B at nsg=1 recomputed; pad kernel (6242–6305) and blk kernel (6314–6367) mechanics, output indexing `i0`-fastest (6365), boundary short-circuit (6331), lane-read count 16 (Q=8 × C/NW=2); vec kernel: NE table from instantiations (f16 dk128 → NE=1 at exactly line **7767**), round-robin loop (7396), inline skip quote (7428–7435) exact, fma fast path (7496–7499), tree reduce (7652–7680, merge at 7675 exact), interleaved partial write (7694), S/M after O block (7688/7700–7701), reduce kernel (7849–7889, guard at 7872), `iwg = tiisg` (7861).

### ERRORS

1. **§2.3, sm2 element formula — off by 2×.** The doc states mask element `i` of row `j` lands "at halves `Q*T + j*TS + 2*C + 2*i`". Correct is `Q*T + j*TS + 2*C + i`. `sm2` is `threadgroup half2 *`; `sm2[j*SH + tiisg]` (metal:6618/6620) is the half2 at half-offset `j*TS + 2*tiisg` from the sm2 base, and it receives `pm2[jj][tiisg]` = device mask elements `2*tiisg` and `2*tiisg+1` — so element `i` sits at half-offset `i`, contiguous. The doc's own region map ("64 mask halves at [128,192), [192,256) unused") is consistent only with `+i`; `+2*i` would spread the mask over [128,256) and contradict the padding claim two lines later. The totals/region boundaries elsewhere in the doc are unaffected; only this formula needs the fix.

2. **§6 N19 — 6673–6686 mislabeled as a quantized-KV branch.** metal:6673–6686 is the `if (DK % 16 != 0)` single-buffered branch *inside the direct-from-device f16 path*; it is dead for DK=128 because of the `DK % 16` compile-time check, not because of `is_same`/quantization (the doc's own §2.5 B2 states this correctly). Only 6714–6774 (quantized K) and 6905–6970 (quantized V) belong under "quantized-KV branches + is_q staging". The row's conclusion (dead code, not instantiated) still holds for all three ranges.

### GAPS (things in the source the document missed)

1. **§2.7 undercounts dead barriers: the `#if 0` block (6631–6652) contains TWO `threadgroup_barrier(mem_threadgroup)` sites — 6634 and 6648 — not just 6648.** Total tg-barrier sites in the impl body = 6 (4 live + 2 dead). No replica impact (dead code), but "a fifth, 6648" should read "a fifth and sixth, 6634 and 6648".
2. **§2.7 dead simdgroup_barrier list omits 6735 and 6756** (`simdgroup_barrier(mem_threadgroup)` in the quantized-K staging branch, dead for f16). The doc lists only 6678/6683 and 6926/6950.
3. **Open question §7.2 is answerable from the vendored tree.** `ggml_metal_op_concurrency_reset` (ops.cpp:147–157) issues `ggml_metal_encoder_memory_barrier` = `[encoder memoryBarrierWithScope:MTLBarrierScopeBuffers]` **within the same encoder** (ggml-metal-device.m:512–514) and resets the mem-ranges concurrency tracker — no encoder split. Relatedly, the doc's vendored-sources table omits three files that are present: `ggml-metal-common.cpp` (457 lines), `ggml-metal-common.h`, and `ggml-metal-device.m` (1951 lines).
4. **Open question §7.5 is now resolved:** `#define FOR_UNROLL(x) _Pragma("clang loop unroll(full)") for (x)` (ggml-metal.metal:26) — full unroll, the doc's assumption was correct.
5. **§7.6 nuance:** the vec-path "(nsg−1)·PK·2 over-allocation" is not merely a host-formula quirk — the kernel's own address map hard-codes it (`ss` at `NSG*PK`, `so4` at `NSG*PK + NSG*SH`, metal:7328–7331), so a replica must reproduce the *offsets*, not just the total size. The doc's "replicate the formula" advice is right but understates that the layout is load-bearing inside the kernel.
6. **§6 N4 (very minor):** the cost expression `ceil(m/8)·ceil(n_kv/64)` is the matrix-path size; for a vec-classified node `extra_blk` is sized with (nqptg,ncpsg) = (1,32) and against `ne30` not `ne11` (ops.cpp:2662–2666). §1's bullet states this correctly; N4's summary is the matrix special case.

**Bottom line:** the document is accurate at the level that matters for a replica — the live barrier inventory is complete (4/4), the kargs ABI is byte-exact (192 B, all holes placed correctly), the shmem map totals are right (10240 B, region boundaries confirmed), and the SG ownership/MMA schedule re-derivations all match. Two localized errors (the `+2*i` sm2 formula in §2.3; the N19 6673–6686 label) and six gaps, all in dead code, uncertainty bookkeeping, or omitted vendored files.
