"""realrace_mlx_lm.py — the mlx-lm arm of the RealRace phase.

Runs the SAME prompt through the SAME Qwen3-0.6B-Base checkpoint (loaded directly from its
HuggingFace safetensors snapshot — mlx-lm converts on the fly, in memory, no GGUF needed) via
`mlx_lm.generate.stream_generate`, greedy (temp=0), for the same generation length the Mojo
`qwen3_generate.mojo` driver uses (`N_NEW_MAX=16`). Prints the generated text and mlx-lm's own
`generation_tps`/`prompt_tps` (real, on-device Metal-GPU numbers — `mx.default_device()` is the GPU
on this machine, genuinely Apple-Silicon-native, matching the MLX-LM plan's own target).

Run (uses the isolated pip env — never bare `python`, never cwd=/tmp):
    /tmp/bb/bin/python -P /path/to/realrace_mlx_lm.py --checkpoint /private/tmp/qwen3-0.6b-base
"""

import argparse
import sys


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", required=True, help="local HF snapshot dir (config.json + model.safetensors)")
    ap.add_argument("--prompt", default="The capital of France is")
    ap.add_argument("--max-tokens", type=int, default=16)
    args = ap.parse_args()

    from mlx_lm import load
    from mlx_lm.generate import stream_generate
    from mlx_lm.sample_utils import make_sampler

    model, tokenizer = load(args.checkpoint)
    sampler = make_sampler(temp=0.0)  # temp=0 -> argmax, the same greedy rule the Mojo driver uses

    text = ""
    last = None
    for response in stream_generate(model, tokenizer, args.prompt, max_tokens=args.max_tokens, sampler=sampler):
        text += response.text
        last = response

    print(f"[mlx-lm] generated text: {text!r}", file=sys.stderr)
    if last is not None:
        print(
            f"[mlx-lm] prompt: {last.prompt_tokens} tok, {last.prompt_tps:.3f} tok/s | "
            f"generation: {last.generation_tokens} tok, {last.generation_tps:.3f} tok/s "
            f"(peak mem {last.peak_memory:.3f} GB)",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
