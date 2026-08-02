"""Precision-isolating sibling of `compare.py`: same driver dump, compared against
`run_reference_fp64.py`'s TRUE float64 reference instead of the float32-default one.

Why this script exists: `compare.py` (vs the float32-default reference) shows small but real
absolute differences that grow through the layer stack, concentrated at token 0 (a documented
"attention sink" position) and a few high-magnitude ("massive activation") channels. Comparing
against a reference computed ENTIRELY in float64 tightens layers 0-1 to ~1e-6/1e-7 (machine-
precision noise) but a bounded, roughly CONSTANT ~9e-4 absolute discrepancy still appears starting
at layer 2, at the same token-0 channels, and does not grow further through the remaining 25 layers.

Root cause, confirmed two ways:
  1. An independent from-scratch numpy (float64, standard operation order) recompute of layer 2, fed
     the reference's OWN hidden_2, reproduces the SAME ~8.6e-4 discrepancy against the reference's
     hidden_3 -- so this is not specific to the Mojo kernels; ANY correctly-written float64
     implementation compared against PyTorch's own kernels shows it.
  2. Reading `transformers/models/qwen3/modeling_qwen3.py`'s `Qwen3RotaryEmbedding.forward` directly:
     it wraps its cos/sin table computation in `with maybe_autocast(..., enabled=False):` and calls
     `.float()` on `inv_freq`/`position_ids` BEFORE the outer product and BEFORE `cos()`/`sin()` --
     forcing that one computation through float32 REGARDLESS of the model's overall dtype -- then
     casts the result back with `.to(dtype=x.dtype)`. `attnk.rope.rope_table` computes the same
     table entirely in Float64. So for this one sub-computation, the Mojo kernel is MORE precise
     than even the "float64" reference, and the gap is the reference's own forced-float32 RoPE
     table, amplified through 26 further layers by the token-0 attention-sink/massive-activation
     channels -- not a Mojo defect.

Tolerance: `abs_tol + eps(f64) * |reference|` per element, `abs_tol = 1e-6` -- deliberately tight,
so the per-layer FAIL rows below are expected and informative (they show exactly where and by how
much), not a red flag on their own. What matters is that the gap stays bounded (~9e-4 absolute at
magnitudes in the hundreds, i.e. ~1e-6 relative) rather than growing layer over layer, and that the
final logits and argmax survive it (see the bottom of the output).
"""
import numpy as np

REF = "/tmp/qwen3smoke/reference_dump_fp64.npz"
DUMP_DIR = "/tmp/qwen3smoke/mojo_dump"
N_LAYERS = 28
ABS_TOL = 1e-6
EPS_F64 = 2.220446049250313e-16


def load_mojo(name: str, shape) -> np.ndarray:
    raw = np.fromfile(f"{DUMP_DIR}/{name}.bin", dtype="<f8")
    return raw.reshape(shape)


def compare(label: str, mojo: np.ndarray, ref: np.ndarray) -> tuple[bool, float, float]:
    assert mojo.shape == ref.shape, (label, mojo.shape, ref.shape)
    diff = np.abs(mojo - ref)
    tol = ABS_TOL + EPS_F64 * np.abs(ref)
    ok = bool(np.all(diff <= tol))
    worst_idx = np.unravel_index(np.argmax(diff - tol), diff.shape)
    worst_diff = float(diff[worst_idx])
    worst_tol = float(tol[worst_idx])
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {label:32s} max|delta|={diff.max():.3e}  "
          f"worst (delta={worst_diff:.3e} vs tol={worst_tol:.3e} at {worst_idx})")
    return ok, float(diff.max()), worst_tol


def main() -> None:
    ref = np.load(REF)
    n_tok, hidden_size = ref["hidden_0"].shape
    vocab_size = ref["logits"].shape[1]

    all_ok = True
    worst_overall = ("", 0.0)

    m0 = load_mojo("hidden_0", (n_tok, hidden_size))
    ok, worst, _ = compare("embedding (hidden_0)", m0, ref["hidden_0"])
    all_ok &= ok
    if worst > worst_overall[1]:
        worst_overall = ("embedding", worst)

    # hidden_1 .. hidden_{N_LAYERS-1} are raw layer outputs on BOTH sides (transformers appends each
    # hidden state before running the next layer, so index i for i in [1, N_LAYERS) is a genuine
    # raw-vs-raw comparison). hidden_{N_LAYERS} is special -- see the note before the final_norm
    # comparison below -- so it is deliberately excluded from this loop.
    for i in range(1, N_LAYERS):
        m = load_mojo(f"hidden_{i}", (n_tok, hidden_size))
        ok, worst, _ = compare(f"layer {i - 1:2d} output (hidden_{i})", m, ref[f"hidden_{i}"])
        all_ok &= ok
        if worst > worst_overall[1]:
            worst_overall = (f"layer {i - 1}", worst)

    # IMPORTANT: transformers' `output_hidden_states` convention appends each hidden state BEFORE
    # running the corresponding layer, and appends the FINAL entry AFTER applying the model's final
    # norm (`Qwen3Model.forward`: `hidden_states = self.norm(hidden_states)` runs after the layer
    # loop, and that post-norm value is what lands in `hidden_states[-1]`, not the raw last-layer
    # output). So `ref["hidden_28"]` is ALREADY norm(raw layer-27 output) -- it is the correct thing
    # to compare `final_norm.bin` (this driver's own rmsnorm_fwd_flat output) against directly, with
    # no second norm applied on either side. A raw-vs-raw comparison at this index looks like a
    # catastrophic divergence (hundreds, not fractions); norm(raw) vs hidden_{N_LAYERS} does not.
    # The "bug" was in an earlier draft of this comparison script's own indexing convention, not in
    # the forward pass -- see compare.py's module docstring for the full trace.
    m_fn = load_mojo("final_norm", (n_tok, hidden_size))
    ok, worst, _ = compare("final_norm (== ref hidden_28, post-final-norm)", m_fn, ref["hidden_28"])
    all_ok &= ok
    if worst > worst_overall[1]:
        worst_overall = ("final_norm", worst)

    m_logits = load_mojo("logits", (n_tok, vocab_size))
    ok, worst, _ = compare("logits", m_logits, ref["logits"])
    all_ok &= ok
    if worst > worst_overall[1]:
        worst_overall = ("logits", worst)

    # Argmax-per-position agreement -- the thing that actually determines greedy-decoded text.
    mojo_argmax = m_logits.argmax(axis=-1)
    ref_argmax = ref["logits"].argmax(axis=-1)
    argmax_agree = bool(np.all(mojo_argmax == ref_argmax))
    print(f"\nargmax(logits) per position: mojo={mojo_argmax.tolist()} ref={ref_argmax.tolist()} "
          f"agree={argmax_agree}")

    print(f"\nworst stage overall: {worst_overall[0]} (max|delta|={worst_overall[1]:.3e})")
    print("ALL STAGES AGREE WITHIN TOLERANCE" if all_ok else "DIVERGENCE DETECTED -- see FAIL rows above")


if __name__ == "__main__":
    main()
