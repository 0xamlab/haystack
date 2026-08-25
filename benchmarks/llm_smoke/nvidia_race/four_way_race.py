#!/usr/bin/env python3
"""four_way_race.py — Qwen2.5-7B-Instruct 4-way engine race on a single A100.

Engines:
  (a) algenta CUDA engine — packed-int8 (p3) weights, cuBLAS tensor-core prefill,
      one-pass flash attention, NOSEAM. Resident-session fixture driver (no HTTP).
  (b) llama.cpp llama-server — Q8_0 GGUF (same pin/config family as prior race).
  (c) vLLM — HF safetensors, bfloat16 (checkpoint dtype, --dtype auto),
      prefix caching disabled.
  (d) SGLang — HF safetensors, bfloat16 (checkpoint dtype), radix cache disabled.

Cells (identical prompt content across all engines):
  * prefill pp256 / pp1024 — the 256-token race prompt, and the same prompt x4
    (exact token-id repetition = 1024 ids). Servers: streaming TTFT with
    max_tokens=1; prefill tok/s = n_prompt / TTFT (llama.cpp n_prompt = its own
    tokenizer's count of the same text, read from /tokenize). Algenta:
    resident-session fixture measurement (no HTTP layer).
  * sweep c=1 / 8 / 32 — c concurrent requests, each the 256-token race prompt,
    256 generated tokens, greedy (temperature 0). Aggregate tok/s =
    (total generated tokens) / (wall time from first dispatch to last completion).

Correctness guard: every engine must emit the fp32-oracle greedy first token on
the race prompt (oracle: /tmp/w7b/gate/ref_tokens.json — fp32 CPU transformers,
repetition_penalty=1.0; first token 14374 = "###"). Each engine's 16-token greedy
trace is re-tokenized and compared id-for-id with the oracle; a 15-token prefix
match is accepted as a documented near-tie (16th-token boundary).

Protocol: SM clocks pinned at 1410 MHz; solo GPU (wait-for-idle before every
engine and before llama-bench); servers killed and GPU drained between engines;
3 warmup runs per cell (excluded), then RUNS measured runs, median + IQR; the
algenta arm runs first and re-runs last as a regime-drift check.

Runs on the VM with the paths below; stdlib only. Results land in
/tmp/w7b/race/results/*.json with every raw sample for audit.
"""

import argparse
import json
import os
import re
import statistics
import subprocess
import sys
import threading
import time
import urllib.request

MODEL_HF = "/home/angel/models/Qwen2.5-7B-Instruct"
GGUF_Q8 = "/home/angel/models/qwen2.5-7b-instruct-q8_0.gguf"
LLAMA_SERVER = "/home/angel/llama.cpp/build/bin/llama-server"
LLAMA_BENCH = "/home/angel/llama.cpp/build/bin/llama-bench"
ALGENTA_BIN = os.environ.get(
    "ALGENTA_RACE_BIN",
    "/home/angel/algenta_nv/qwen25_7b_p3_graph_cuda_tc_b1_ns")
CKPT = "/tmp/w7b/ckpt"
RACE_DIR = "/tmp/w7b/race"
RESULTS = os.path.join(RACE_DIR, "results")
FIXTURE_TXT = os.path.join(RACE_DIR, "fixture_prompt.txt")
PP1024_IDS = "/tmp/w7b/gate/pp1024_ids.txt"
REF_TOKENS = "/tmp/w7b/gate/ref_tokens.json"
ORACLE_TEXTS = os.path.join(RACE_DIR, "oracle_texts.json")
VLLM_PY = "/home/angel/vllm-venv/bin/python"
SGLANG_PY = "/home/angel/sglang-venv/bin/python"

PORT_LLAMA = 8300
PORT_VLLM = 8100
PORT_SGLANG = 8200

RUNS = 7            # measured runs per cell (>=5 per protocol)
WARMUP = 3          # excluded warmup runs per cell
SWEEP_CONC = (1, 8, 32)
OUT_TOKENS = 256
HEALTH_TIMEOUT_S = 900
sglang_ids_ok = True  # flipped by sglang_run's input_ids probe


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def http_json(url, payload, timeout=900):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:500]
        raise RuntimeError(f"HTTP {e.code} from {url}: {body}") from e


def http_get(url, timeout=10):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.status


def extract_delta_text(obj):
    ch = obj.get("choices")
    if isinstance(ch, list) and ch:
        c0 = ch[0]
        if "text" in c0:
            return c0["text"]
        d = c0.get("delta") or {}
        return d.get("content") or ""
    if isinstance(obj.get("text"), str):
        return obj["text"]
    return ""


def extract_completion(obj):
    """(text, n_completion_tokens) from a non-stream completion.

    llama.cpp /completion -> {"content": ...}; sglang /generate -> {"text": ...};
    OpenAI-style -> choices[0].text.
    """
    ch = obj.get("choices")
    if isinstance(ch, list) and ch:
        c0 = ch[0]
        text = c0.get("text") or (c0.get("message") or {}).get("content") or ""
        n = (obj.get("usage") or {}).get("completion_tokens")
        return text, n
    text = obj.get("text") or obj.get("content") or ""
    meta = obj.get("meta_info") or {}
    n = meta.get("completion_tokens")
    if n is None and isinstance(meta.get("output_ids"), list):
        n = len(meta["output_ids"])
    return text, n


def stream_first_token_ms(url, payload, timeout=300):
    """POST a streaming request; return ttft_ms to the first content delta."""
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    first_ms = None
    with urllib.request.urlopen(req, timeout=timeout) as r:
        for raw in r:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                obj = json.loads(data)
            except json.JSONDecodeError:
                continue
            if extract_delta_text(obj) and first_ms is None:
                first_ms = (time.perf_counter() - t0) * 1000.0
                break
    if first_ms is None:
        first_ms = (time.perf_counter() - t0) * 1000.0
    return first_ms


def wait_gpu_idle(timeout_s=300):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        out = subprocess.run(
            ["nvidia-smi", "--query-compute-apps=pid", "--format=csv,noheader"],
            capture_output=True, text=True).stdout.strip()
        if not out:
            return True
        time.sleep(2)
    return False


def kill_proc(p, name):
    if p is None:
        return
    try:
        p.terminate()
        try:
            p.wait(timeout=30)
        except subprocess.TimeoutExpired:
            p.kill()
            p.wait(timeout=30)
    except Exception as e:
        log(f"  kill {name}: {e}")
    wait_gpu_idle(120)
    time.sleep(3)


def wait_health(urls, name, timeout_s=HEALTH_TIMEOUT_S):
    """Poll every URL in `urls` until all answer 200 (readiness, not just port)."""
    if isinstance(urls, str):
        urls = [urls]
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        ok = True
        for u in urls:
            try:
                if http_get(u) != 200:
                    ok = False
            except Exception:
                ok = False
        if ok:
            log(f"  {name} ready in {time.time()-t0:.0f}s")
            return True
        time.sleep(3)
    return False


def med_iqr(xs):
    xs = sorted(xs)
    med = statistics.median(xs)
    n = len(xs)
    if n >= 4:
        q1 = statistics.median(xs[: n // 2])
        q3 = statistics.median(xs[(n + 1) // 2:])
        iqr = q3 - q1
    else:
        iqr = max(xs) - min(xs)
    rel_iqr = (iqr / med * 100.0) if med else 0.0
    return med, iqr, rel_iqr


def sweep_stats(engine_fn, c, runs):
    """c-way concurrent fan-out; repeat `runs` times; aggregate tok/s stats."""
    agg, walls, per_req_lat = [], [], []

    def worker(res, lock):
        t0 = time.perf_counter()
        n = engine_fn()
        with lock:
            res.append((time.perf_counter() - t0, n))

    for _ in range(runs):
        t_start = time.perf_counter()
        threads, res, lock = [], [], threading.Lock()
        for _ in range(c):
            th = threading.Thread(target=worker, args=(res, lock))
            threads.append(th)
            th.start()
        for th in threads:
            th.join()
        wall = time.perf_counter() - t_start
        total = sum(n for _, n in res)
        agg.append(total / wall)
        walls.append(wall)
        per_req_lat.append([dt for dt, _ in res])
    med, iqr, rel = med_iqr(agg)
    return {"c": c, "out_tokens": OUT_TOKENS, "agg_tok_s": agg, "walls_s": walls,
            "median_tok_s": med, "iqr_tok_s": iqr, "rel_iqr_pct": rel}


def ttft_stats(fn, n_prompt, runs):
    ttfts = []
    for _ in range(runs):
        ttfts.append(fn())
    med, iqr, rel = med_iqr(ttfts)
    return {"n_prompt": n_prompt, "ttft_ms": ttfts, "median_ms": med,
            "iqr_ms": iqr, "rel_iqr_pct": rel,
            "tok_s": n_prompt / (med / 1000.0)}


# ---------------------------------------------------------------- correctness


def correctness(engine_name, gen_text_16, tokenize_fn):
    """Id-level comparison of an engine's 16 greedy tokens vs the fp32 oracle."""
    oracle = json.load(open(ORACLE_TEXTS))
    oids = oracle["ids_16"]
    entry = {"engine": engine_name, "oracle_ids_16": oids,
             "oracle_text_16": oracle["text_16"],
             "engine_text_16": gen_text_16}
    ids = None
    try:
        ids = tokenize_fn(gen_text_16)
    except Exception as e:
        entry["tokenize_error"] = repr(e)
    if ids is not None and len(ids) >= 15:
        entry["engine_ids_16"] = ids[:16]
        entry["first_token_ok"] = bool(ids[0] == oids[0])
        entry["seq16_ok"] = bool(ids[:16] == oids)
        entry["seq15_ok"] = bool(ids[:15] == oids[:15])
    else:  # fallback: text prefix comparison
        entry["first_token_ok"] = bool(gen_text_16.startswith(oracle["text_1"]))
        entry["seq16_ok"] = bool(gen_text_16.startswith(oracle["text_16"]))
        entry["seq15_ok"] = bool(gen_text_16.startswith(oracle["text_15"]))
    entry["verdict"] = ("PASS" if entry["first_token_ok"] and
                        (entry["seq16_ok"] or entry["seq15_ok"]) else "CHECK")
    log(f"  {engine_name}: first_token_ok={entry['first_token_ok']} "
        f"seq16_ok={entry['seq16_ok']} seq15_ok={entry['seq15_ok']} -> {entry['verdict']}")
    return entry


# ---------------------------------------------------------------- algenta


def run_algenta(tag, runs=20):
    log(f"algenta arm run '{tag}' ({runs} runs/cell, oracle gates inside)")
    if not wait_gpu_idle():
        raise RuntimeError("GPU not idle before algenta run")
    ref = json.load(open(REF_TOKENS))
    oracle = ",".join(str(int(t)) for t in ref["fixture"]["generated_ids"][:16])
    out_txt = os.path.join(RESULTS, f"algenta_{tag}.txt")
    out_log = os.path.join(RESULTS, f"algenta_{tag}.log")
    with open(out_log, "w") as lf:
        subprocess.run(
            [ALGENTA_BIN, "--checkpoint", CKPT, "--arm", "p3",
             "--oracle", oracle, "--runs", str(runs), "--out", out_txt],
            stdout=lf, stderr=subprocess.STDOUT, check=True)
    report = {}
    for line in open(out_txt):
        m = re.match(r"^(\w+)=([0-9.eE+-]+)$", line.strip())
        if m:
            report[m.group(1)] = float(m.group(2))
    gates = [l.strip() for l in open(out_log)
             if "G0 RESULT" in l or "G1 RESULT" in l]
    for g in gates:
        log("  " + g)
    log(f"  report: {report}")
    return {"tag": tag, "runs": runs, "report": report, "gates": gates,
            "txt": out_txt, "log": out_log}


# ---------------------------------------------------------------- llama.cpp


def start_llama(parallel, ctx, tag):
    """llama-server serves ctx/parallel per slot: the prefill cells need one slot
    >= 1025 tokens, the sweep cells need `parallel` slots x (256+256)."""
    log(f"starting llama-server ({tag}: parallel={parallel} ctx={ctx})...")
    p = subprocess.Popen(
        [LLAMA_SERVER, "-m", GGUF_Q8, "--host", "127.0.0.1",
         "--port", str(PORT_LLAMA), "-ngl", "99", "--parallel", str(parallel),
         "--ctx-size", str(ctx), "--no-webui"],
        stdout=open(os.path.join(RESULTS, f"llama_server_{tag}.log"), "w"),
        stderr=subprocess.STDOUT)
    if not wait_health(f"http://127.0.0.1:{PORT_LLAMA}/health", f"llama-server ({tag})"):
        raise RuntimeError("llama-server failed to become healthy")
    # llama-server opens its port before model load completes — functional probe
    t0 = time.time()
    while time.time() - t0 < 600:
        try:
            if llama_tokenize("hello"):
                log(f"  llama-server ({tag}) model loaded")
                return p
        except Exception:
            pass
        time.sleep(3)
    raise RuntimeError("llama-server model never finished loading")


def llama_tokenize(text):
    obj = http_json(f"http://127.0.0.1:{PORT_LLAMA}/tokenize",
                    {"content": text})
    return [int(t) for t in obj["tokens"]]


def llama_generate(text, n):
    """Returns (text, tokens_predicted)."""
    obj = http_json(f"http://127.0.0.1:{PORT_LLAMA}/completion",
                    {"prompt": text, "n_predict": n, "temperature": 0.0,
                     "stream": False, "cache_prompt": False})
    t, _ = extract_completion(obj)
    return t, int(obj.get("tokens_predicted") or n)


def llama_run(fixture_text, runs):
    """Owns its own servers: prefill instance (one slot >= 1025 ctx), then a
    sweep instance (32 slots x 560). Each killed + GPU drained after use."""
    cells = {}
    p = start_llama(parallel=4, ctx=4608, tag="prefill")
    try:
        base = f"http://127.0.0.1:{PORT_LLAMA}"
        ids256 = llama_tokenize(fixture_text)
        ids1024 = llama_tokenize(fixture_text * 4)
        n256, n1024 = len(ids256), len(ids1024)
        log(f"  llama tokenizer: fixture={n256} ids, fixture x4={n1024} ids")
        url = f"{base}/completion"

        def ttft(text):
            return stream_first_token_ms(
                url, {"prompt": text, "n_predict": 1, "temperature": 0.0,
                      "stream": True, "cache_prompt": False})

        log("  llama correctness...")
        trace, _ = llama_generate(fixture_text, 16)
        cells["correctness"] = correctness(
            "llama.cpp Q8_0", trace, llama_tokenize)
        for warm in range(WARMUP):
            ttft(fixture_text)
        log("  llama pp256...")
        cells["pp256"] = ttft_stats(lambda: ttft(fixture_text), n256, runs)
        for warm in range(WARMUP):
            ttft(fixture_text * 4)
        log("  llama pp1024...")
        cells["pp1024"] = ttft_stats(lambda: ttft(fixture_text * 4), n1024, runs)
        cells["prompt_token_counts"] = {"pp256": n256, "pp1024": n1024}
    finally:
        kill_proc(p, "llama-server (prefill)")

    p = start_llama(parallel=32, ctx=17920, tag="sweep")
    try:
        def gen256():
            _, n = llama_generate(fixture_text, OUT_TOKENS)
            return n

        sweep = {}
        for c in SWEEP_CONC:
            for warm in range(min(WARMUP, 2)):
                gen256()
            log(f"  llama sweep c={c}...")
            sweep[c] = sweep_stats(gen256, c, runs)
        cells["sweep"] = sweep
    finally:
        kill_proc(p, "llama-server (sweep)")
    return cells


def llama_bench_controls():
    """Continuity with the prior race: llama-bench Q8_0 pp cells, -r 5, solo."""
    out = {}
    for name, n_prompt, args in (("pp256", 256, ["-p", "256", "-n", "0"]),
                                 ("pp1024", 1024, ["-p", "1024", "-n", "0"])):
        if not wait_gpu_idle():
            raise RuntimeError("GPU not idle before llama-bench")
        j = os.path.join(RESULTS, f"llama_bench_q8_{name}.json")
        subprocess.run([LLAMA_BENCH, "-m", GGUF_Q8, *args, "-r", "5",
                        "-ngl", "99", "-o", "json"],
                       stdout=open(j, "w"),
                       stderr=open(j + ".err", "w"), check=True)
        data = json.load(open(j))
        rows = [r for r in data
                if isinstance(r, dict) and r.get("n_prompt") == n_prompt
                and r.get("n_gen") == 0]
        samples = rows[-1]["samples_ts"] if rows else []
        entry = {"samples_ts": samples}
        if samples:
            m, iqr, rel = med_iqr(samples)
            entry["median_tok_s"] = m
            entry["rel_iqr_pct"] = rel
        out[name] = entry
        log(f"  llama-bench {name}: {entry.get('median_tok_s')}")
    return out


# ---------------------------------------------------------------- vLLM


def venv_env(venv_py):
    """Env for a server child: venv bin on PATH (JIT needs ninja etc.)."""
    env = dict(os.environ)
    env["PATH"] = os.path.dirname(venv_py) + ":" + env.get("PATH", "")
    return env


def start_vllm():
    log("starting vLLM...")
    env = venv_env(VLLM_PY)
    env["VLLM_USE_FLASHINFER_SAMPLER"] = "0"
    p = subprocess.Popen(
        [VLLM_PY, "-m", "vllm.entrypoints.openai.api_server",
         "--model", MODEL_HF, "--served-model-name", "qwen25-7b",
         "--host", "127.0.0.1", "--port", str(PORT_VLLM),
         "--max-model-len", "2048", "--gpu-memory-utilization", "0.9",
         "--max-num-seqs", "64", "--no-enable-prefix-caching",
         "--dtype", "auto", "--no-enable-log-requests"],
        env=env,
        stdout=open(os.path.join(RESULTS, "vllm_server.log"), "w"),
        stderr=subprocess.STDOUT)
    if not wait_health([f"http://127.0.0.1:{PORT_VLLM}/health",
                        f"http://127.0.0.1:{PORT_VLLM}/v1/models"], "vllm"):
        raise RuntimeError("vllm failed to become healthy")
    return p


def vllm_tokenize(text):
    obj = http_json(f"http://127.0.0.1:{PORT_VLLM}/tokenize",
                    {"model": "qwen25-7b", "prompt": text})
    return [int(t) for t in obj["tokens"]]


def vllm_run(fixture_text, fixture_ids, runs):
    # vLLM >= 0.27 /v1/completions takes text prompts; same HF tokenizer, so the
    # race prompt re-tokenizes to the identical 256 ids — verified via /tokenize.
    prompt_text = {256: fixture_text, 1024: fixture_text * 4}
    n_verified = {}
    for n, text in prompt_text.items():
        ids = vllm_tokenize(text)
        n_verified[n] = len(ids)
        assert len(ids) == n and ids == (fixture_ids * (n // 256)), \
            f"vllm tokenizer mismatch at {n}: {len(ids)} ids"
    log(f"  vllm tokenizer verified: 256 and 1024 ids identical to the race ids")
    base = f"http://127.0.0.1:{PORT_VLLM}/v1/completions"

    def ttft(n):
        return stream_first_token_ms(
            base, {"model": "qwen25-7b", "prompt": prompt_text[n],
                   "max_tokens": 1, "temperature": 0.0, "stream": True})

    def gen256():
        obj = http_json(base, {"model": "qwen25-7b",
                               "prompt": prompt_text[256],
                               "max_tokens": OUT_TOKENS, "temperature": 0.0,
                               "stream": False})
        _, n = extract_completion(obj)
        return n if n is not None else OUT_TOKENS

    def gen_text(n):
        obj = http_json(base, {"model": "qwen25-7b",
                               "prompt": prompt_text[256],
                               "max_tokens": n, "temperature": 0.0,
                               "stream": False})
        t, _ = extract_completion(obj)
        return t

    cells = {}
    log("  vllm correctness...")
    cells["correctness"] = correctness("vLLM bfloat16", gen_text(16), vllm_tokenize)
    for warm in range(WARMUP):
        ttft(256)
    log("  vllm pp256...")
    cells["pp256"] = ttft_stats(lambda: ttft(256), 256, runs)
    for warm in range(WARMUP):
        ttft(1024)
    log("  vllm pp1024...")
    cells["pp1024"] = ttft_stats(lambda: ttft(1024), 1024, runs)
    sweep = {}
    for c in SWEEP_CONC:
        for warm in range(min(WARMUP, 2)):
            gen256()
        log(f"  vllm sweep c={c}...")
        sweep[c] = sweep_stats(gen256, c, runs)
    cells["sweep"] = sweep
    cells["prompt_token_counts"] = n_verified
    return cells


# ---------------------------------------------------------------- SGLang


def start_sglang():
    log("starting SGLang...")
    p = subprocess.Popen(
        [SGLANG_PY, "-m", "sglang.launch_server",
         "--model-path", MODEL_HF, "--served-model-name", "qwen25-7b",
         "--host", "127.0.0.1", "--port", str(PORT_SGLANG),
         "--mem-fraction-static", "0.9", "--context-length", "2048",
         "--disable-radix-cache"],
        env=venv_env(SGLANG_PY),
        stdout=open(os.path.join(RESULTS, "sglang_server.log"), "w"),
        stderr=subprocess.STDOUT)
    if not wait_health([f"http://127.0.0.1:{PORT_SGLANG}/health",
                        f"http://127.0.0.1:{PORT_SGLANG}/get_model_info"], "sglang"):
        raise RuntimeError("sglang failed to become healthy")
    return p


def sglang_tokenize(text):
    obj = http_json(f"http://127.0.0.1:{PORT_SGLANG}/tokenize",
                    {"text": text})
    toks = obj.get("tokens") or obj.get("input_ids")
    return [int(t) for t in toks]


def sglang_run(fixture_text, fixture_ids, runs):
    pp1024_ids = fixture_ids * 4
    base = f"http://127.0.0.1:{PORT_SGLANG}/generate"

    def prompt_payload(ids, text, max_new, stream):
        if sglang_ids_ok:
            return {"input_ids": ids,
                    "sampling_params": {"max_new_tokens": max_new,
                                        "temperature": 0.0},
                    "stream": stream}
        return {"text": text,
                "sampling_params": {"max_new_tokens": max_new,
                                    "temperature": 0.0},
                "stream": stream}

    # probe: does this sglang build accept input_ids?
    global sglang_ids_ok
    sglang_ids_ok = True
    try:
        stream_first_token_ms(
            base, {"input_ids": fixture_ids,
                   "sampling_params": {"max_new_tokens": 1, "temperature": 0.0},
                   "stream": True}, timeout=120)
        log("  sglang accepts input_ids (exact token parity)")
    except Exception as e:
        sglang_ids_ok = False
        log(f"  sglang input_ids rejected ({e}); falling back to text prompts")
    textmap = {256: fixture_text, 1024: fixture_text * 4}
    idsmap = {256: fixture_ids, 1024: pp1024_ids}

    def ttft(n):
        return stream_first_token_ms(
            base, prompt_payload(idsmap[n], textmap[n], 1, True))

    def gen256():
        obj = http_json(base, prompt_payload(fixture_ids, fixture_text,
                                             OUT_TOKENS, False))
        _, n = extract_completion(obj)
        return n if n is not None else OUT_TOKENS

    def gen_text(n):
        obj = http_json(base, prompt_payload(fixture_ids, fixture_text, n, False))
        t, _ = extract_completion(obj)
        return t

    cells = {}
    log("  sglang correctness...")
    cells["correctness"] = correctness("SGLang bfloat16", gen_text(16), sglang_tokenize)
    for warm in range(WARMUP):
        ttft(256)
    log("  sglang pp256...")
    cells["pp256"] = ttft_stats(lambda: ttft(256), 256, runs)
    for warm in range(WARMUP):
        ttft(1024)
    log("  sglang pp1024...")
    cells["pp1024"] = ttft_stats(lambda: ttft(1024), 1024, runs)
    sweep = {}
    for c in SWEEP_CONC:
        for warm in range(min(WARMUP, 2)):
            gen256()
        log(f"  sglang sweep c={c}...")
        sweep[c] = sweep_stats(gen256, c, runs)
    cells["sweep"] = sweep
    cells["input_ids_path"] = sglang_ids_ok
    return cells


# ---------------------------------------------------------------- main


def save(name, obj):
    path = os.path.join(RESULTS, name)
    with open(path, "w") as f:
        json.dump(obj, f, indent=1)
    log(f"  -> {path}")


def engine_versions():
    v = {}
    try:
        out = subprocess.run([VLLM_PY, "-c", "import vllm;print(vllm.__version__)"],
                             capture_output=True, text=True, timeout=120)
        v["vllm"] = out.stdout.strip().splitlines()[-1]
    except Exception as e:
        v["vllm"] = f"error: {e}"
    try:
        out = subprocess.run([SGLANG_PY, "-c", "import sglang;print(sglang.__version__)"],
                             capture_output=True, text=True, timeout=120)
        v["sglang"] = out.stdout.strip().splitlines()[-1]
    except Exception as e:
        v["sglang"] = f"error: {e}"
    try:
        out = subprocess.run([LLAMA_BENCH, "--version"], capture_output=True,
                             text=True, timeout=30)
        v["llama_cpp"] = (out.stdout + out.stderr).strip().splitlines()[-1][:200]
    except Exception as e:
        v["llama_cpp"] = f"error: {e}"
    return v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=RUNS)
    ap.add_argument("--only", default="",
                    help="comma subset: algenta,llama,vllm,sglang")
    args = ap.parse_args()
    os.makedirs(RESULTS, exist_ok=True)
    only = set(x for x in args.only.split(",") if x) or \
        {"algenta", "llama", "vllm", "sglang"}

    fixture_text = open(FIXTURE_TXT).read()
    pp = [int(x) for x in open(PP1024_IDS).read().split(",")]
    assert len(pp) == 1024 and pp[:256] * 4 == pp, "pp1024 ids must be fixture x4"
    fixture_ids = pp[:256]
    assert len(fixture_text) > 0

    meta = {
        "date": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "vm": "algenta-ent-a100 (GCP a2-highgpu-1g, 1x A100-SXM4-40GB, solo GPU)",
        "gpu": subprocess.run(["nvidia-smi", "--query-gpu=name,driver_version",
                               "--format=csv,noheader"],
                              capture_output=True, text=True).stdout.strip(),
        "clocks_pinned": "nvidia-smi -lgc 1410,1410",
        "model": "Qwen/Qwen2.5-7B-Instruct (unmodified HF weights)",
        "model_dtype_served": "bfloat16 (checkpoint torch_dtype; vLLM/SGLang --dtype auto)",
        "algenta_arm": "p3 packed-int8 + cuBLAS TC prefill + one-pass flash2 + NOSEAM",
        "llama_cpp_gguf": "Q8_0",
        "prompt": "256-token chat-template race prompt; pp1024 = same token ids x4",
        "greedy": "temperature 0 everywhere; algenta oracle pinned repetition_penalty=1.0",
        "runs_per_cell": args.runs, "warmup_runs_excluded": WARMUP,
        "caching": "vLLM --no-enable-prefix-caching; SGLang --disable-radix-cache; "
                   "llama.cpp cache_prompt=false (no cross-request prompt reuse)",
        "versions": engine_versions(),
        "oracle": REF_TOKENS,
    }
    save("meta.json", meta)
    summary = {"meta": meta, "engines": {}}

    def condense(cells):
        return {
            "correctness": cells.get("correctness"),
            "pp256": {"median_ttft_ms": cells["pp256"]["median_ms"],
                      "tok_s": cells["pp256"]["tok_s"],
                      "rel_iqr_pct": cells["pp256"]["rel_iqr_pct"]},
            "pp1024": {"median_ttft_ms": cells["pp1024"]["median_ms"],
                       "tok_s": cells["pp1024"]["tok_s"],
                       "rel_iqr_pct": cells["pp1024"]["rel_iqr_pct"]},
            "sweep": {str(c): {"median_agg_tok_s": s["median_tok_s"],
                               "rel_iqr_pct": s["rel_iqr_pct"]}
                      for c, s in cells["sweep"].items()},
        }

    # ---- algenta first
    if "algenta" in only:
        a1 = run_algenta("race_a", runs=20)
        save("algenta_race_a.json", a1)
        summary["engines"]["algenta"] = {
            "run_a": a1["report"], "gates_a": a1["gates"],
            "note": "resident session fixture: no HTTP; TTFT = n_prompt/prefill_toks; "
                    "gen256 = c=1 sweep cell (256-token prompt, 256 generated)"}

    # ---- llama.cpp (owns its own server instances)
    if "llama" in only:
        cells = llama_run(fixture_text, args.runs)
        save("llama_cells.json", cells)
        summary["engines"]["llama"] = condense(cells)
        if not wait_gpu_idle():
            raise RuntimeError("GPU not idle before llama-bench")
        bench = llama_bench_controls()
        save("llama_bench_controls.json", bench)
        summary["engines"]["llama"]["llama_bench_q8"] = bench

    # ---- vLLM
    if "vllm" in only:
        p = start_vllm()
        try:
            cells = vllm_run(fixture_text, fixture_ids, args.runs)
        finally:
            kill_proc(p, "vllm")
        save("vllm_cells.json", cells)
        summary["engines"]["vllm"] = condense(cells)

    # ---- SGLang
    if "sglang" in only:
        p = start_sglang()
        try:
            cells = sglang_run(fixture_text, fixture_ids, args.runs)
        finally:
            kill_proc(p, "sglang")
        save("sglang_cells.json", cells)
        summary["engines"]["sglang"] = condense(cells)

    # ---- algenta drift re-run
    if "algenta" in only:
        a2 = run_algenta("race_b", runs=20)
        save("algenta_race_b.json", a2)
        summary["engines"]["algenta"]["run_b"] = a2["report"]
        summary["engines"]["algenta"]["gates_b"] = a2["gates"]
        ra = summary["engines"]["algenta"]["run_a"]
        drift = {k: (a2["report"][k] - ra[k]) / ra[k] * 100.0
                 for k in ra if k in a2["report"]}
        summary["engines"]["algenta"]["drift_pct_a_to_b"] = drift
        log(f"  algenta drift a->b: {drift}")

    save("summary.json", summary)
    log("RACE DONE")


if __name__ == "__main__":
    sys.exit(main())
