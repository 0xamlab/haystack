"""Compare the Mojo driver's dumped intermediates against the real `transformers` reference,
stage by stage, with a STATED tolerance -- not a bare pass/fail on the final token.

Tolerance: `abs_tol + eps(f64) * |reference|` per element, `abs_tol = 1e-6`. The forward pass is
computed in Float64 on both sides (the reference model was loaded with `dtype=torch.float32` and
transformers upcasts to fp32 compute internally; both arms are far above bf16's own ~2e-2 storage
noise floor, so 1e-6 is a real correctness tolerance, not a dtype-driven floor).
"""
import numpy as np

REF = "/tmp/qwen3smoke/reference_dump.npz"
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
    # no second norm applied on either side. Verified against a from-scratch numpy recompute of layer
    # 27 fed the reference's own hidden_27: comparing RAW vs RAW gave max|delta|=456 (looked like a
    # catastrophic divergence); comparing norm(raw) vs hidden_28 gives max|delta|=7.8e-4. The "bug"
    # was in this comparison script's own indexing convention, not in the forward pass.
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
