"""candidate_c_blob_driver.mojo -- forces codegen of BOTH of CANDIDATE C's real GPU kernels
(`_attn_splitk_partial_kernel`, `_attn_splitk_merge_kernel`, `splitk_fa.mojo`) for blob extraction
via `mojo build --emit object`, following `mma_forge/mm8_driver.mojo`'s exact multi-kernel-in-one-
object-file pattern (that file forces THREE kernels; this one forces TWO) -- the SAME pattern
`candidate_a_blob_driver.mojo` already proved carries a single 12-argument attention kernel across
the cross-toolchain blob-extraction-and-link mechanism. No GPU dispatch needs to actually succeed for
this step; `ctx.enqueue_function[kernel]` inside `main()` is what forces the compiler to lower each
kernel to AIR/metallib. Both land in the object file's `__TEXT,__const`, back-to-back, as either two
separate `MTLB` blobs or one combined one -- `mm8_driver.mojo`'s own three-kernel precedent already
proves `extract_blob.py`'s scan loop (and `algenta_open_session`'s own identical scan) handles
back-to-back blobs either way, so this driver does not need to care which.

This is a Phase 2C VALIDATION exercise (Attention Compiler Plan v1.0) -- the ONE explicit unresolved
follow-up risk flagged by the prior (Candidate-A-alone) validation: production wiring needs MULTIPLE
blobs (Candidate A + Candidate C's two kernels + the existing mm8 GEMM blob + residentk's own
natively-compiled kernels) linked into ONE binary simultaneously, and this driver produces Candidate
C's own half of that. Standalone, throwaway driver -- not wired into any production build, not
imported by anything under `mojo/engine/`.

Shape chosen to force codegen: the SAME "tiny aligned" shape `splitk_fa_driver.mojo`'s own
`test_correctness`/`test_partial_isolation` already use first -- n_tok_q=8, n_tok_k=64, h_q=2,
h_kv=1, d=128 (fixed, this candidate's own specialization), n_splits=2, offset=0, native
key_block_size=32 (n_blocks=2, 64/32 exact, zero remainder). Buffer sizes and grid shapes mirror
`splitk_fa_driver.mojo`'s own `test_correctness` exactly (see that file for the derivation); nothing
here needs to be numerically meaningful, only shape-valid, since no dispatch actually runs.

    cd mma_forge
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo build --emit object -I . -I ../attention_forge \
        -o /tmp/candidate_c_forge.o ../attention_forge/candidate_c_blob_driver.mojo
    python3 tools/extract_blob.py /tmp/candidate_c_forge.o \
      ../attention_forge/generated/candidate_c_blob.c --symbol algenta_candidate_c_blob
"""
from max.gpu.host import DeviceContext
from splitk_fa import _attn_splitk_partial_kernel, _attn_splitk_merge_kernel


def main() raises:
    var ctx = DeviceContext()

    var n_tok_q: Int64 = 8
    var n_tok_k: Int64 = 64
    var h_q: Int64 = 2
    var h_kv: Int64 = 1
    var d: Int64 = 128
    var n_splits: Int64 = 2
    var key_block_size: Int64 = 32
    var n_blocks: Int64 = (n_tok_k + key_block_size - 1) // key_block_size  # = 2

    var q_buf = ctx.enqueue_create_buffer[DType.float16](Int(n_tok_q * h_q * d))
    var k_buf = ctx.enqueue_create_buffer[DType.float16](Int(h_kv * n_blocks * d * key_block_size))
    var v_buf = ctx.enqueue_create_buffer[DType.float16](Int(h_kv * n_blocks * key_block_size * d))
    var m_scratch = ctx.enqueue_create_buffer[DType.float32](Int(n_tok_q * h_q * n_splits))
    var l_scratch = ctx.enqueue_create_buffer[DType.float32](Int(n_tok_q * h_q * n_splits))
    var o_scratch = ctx.enqueue_create_buffer[DType.float32](Int(n_tok_q * h_q * n_splits * d))
    var out_buf = ctx.enqueue_create_buffer[DType.float32](Int(n_tok_q * h_q * d))
    var lse_buf = ctx.enqueue_create_buffer[DType.float32](Int(h_q * n_tok_q))

    var scale64: Float64 = 1.0 / Float64(128) ** 0.5
    var scale: Float32 = Float32(scale64)

    var n_q_blocks = (n_tok_q + 7) // 8
    var n_pairs = h_q // 2
    var grid_partial = n_q_blocks * n_pairs * n_splits  # = 1 * 1 * 2 = 2
    ctx.enqueue_function[_attn_splitk_partial_kernel](
        m_scratch.unsafe_ptr(), l_scratch.unsafe_ptr(), o_scratch.unsafe_ptr(),
        q_buf.unsafe_ptr(), k_buf.unsafe_ptr(), v_buf.unsafe_ptr(),
        n_tok_q, n_tok_k, h_q, h_kv,
        scale, Int64(0), n_splits, n_blocks,
        grid_dim=Int(grid_partial), block_dim=256,
    )

    var grid_merge = n_tok_q * h_q  # = 16
    ctx.enqueue_function[_attn_splitk_merge_kernel](
        out_buf.unsafe_ptr(), lse_buf.unsafe_ptr(),
        m_scratch.unsafe_ptr(), l_scratch.unsafe_ptr(), o_scratch.unsafe_ptr(),
        n_tok_q, h_q, n_splits,
        grid_dim=Int(grid_merge), block_dim=128,
    )
    print("CANDIDATE C BLOB DRIVER: codegen forced (partial + merge)")
