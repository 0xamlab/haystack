"""probe_generate_vs_manual.py — localize the generate()-vs-plain-forward logit disagreement
at chat_1 step 6 (2026-08-23). Compares the lm_head-input hidden vector generate() computes
at the disputed step against a manual cached forward over the identical prefix."""

import json
import torch
from pathlib import Path
from transformers import AutoModelForCausalLM, AutoTokenizer

prompts = json.loads(Path("/tmp/w7b/ckpt/prompts.json").read_text())
ids = prompts["chat_prompts"][1]["ids"]
mp = Path.home() / "models/Qwen2.5-7B-Instruct"
tok = AutoTokenizer.from_pretrained(mp)
model = AutoModelForCausalLM.from_pretrained(mp, dtype=torch.float32).to("cpu").eval()
gen6 = [49896, 320, 91201, 7779, 24572, 8]

captured = []
def hook(m, inp, out):
    captured.append(inp[0].detach().clone())

h = model.lm_head.register_forward_hook(hook)
with torch.no_grad():
    out = model.generate(
        torch.tensor([ids], dtype=torch.long), max_new_tokens=8, do_sample=False,
        pad_token_id=tok.eos_token_id,
    )
h.remove()
print("n lm_head calls during generate:", len(captured))
# captured[0] = prefill (token 0); captured[6] = the step producing the 7th token (step 6)
h_gen = captured[6][0].double()

with torch.no_grad():
    o = model(torch.tensor([ids]), use_cache=True, output_hidden_states=True)
    pkv = o.past_key_values
    for t in gen6:
        o = model(torch.tensor([[t]]), past_key_values=pkv, use_cache=True,
                  output_hidden_states=True)
        pkv = o.past_key_values
    h_man = o.hidden_states[-1][0].double()

d = (h_gen - h_man).abs()
print("hidden max abs diff:", float(d.max()))
print("hidden rel diff:", float(d.max() / h_man.abs().max()))
print("gen abs-sum:", float(h_gen.abs().sum()), "manual abs-sum:", float(h_man.abs().sum()))
idx = int(d.argmax())
print("worst idx:", idx, "gen:", float(h_gen[idx]), "man:", float(h_man[idx]))
# logit consequence
lm = model.lm_head.weight.detach().double()
lg_gen = lm @ h_gen
lg_man = lm @ h_man
print("logit 323 gen/manual:", float(lg_gen[323]), float(lg_man[323]))
print("logit 374 gen/manual:", float(lg_gen[374]), float(lg_man[374]))
print("argmax gen:", int(lg_gen.argmax()), "argmax man:", int(lg_man.argmax()))
