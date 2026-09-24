"""Prefilled arguments for every Playground function.

Owner rule (round 9): everywhere a visitor can act, every field opens with a value — never an
empty box. The contract names types and length rules but no example values (16,139 of the
16,335 parameters have no default), so this module synthesises one argument set per function:

* a value chosen from the parameter's NAME and type — a probability is 0.5, a significance level
  0.05, a latitude 51.5074 (London) and a second one 48.8566 (Paris), a seed 42, a count 5, an
  index 0, a text the fox sentence, a list five numbers, a matrix 3 × 3; a struct fills field by
  field with the same rules (an `Interval` opens as lo 0.0, hi 1.0, empty false);
* every count relation satisfied exactly — a count equals the length of the list it bounds,
  rows × cols equals the elements, an index is 0 — checked with the Playground's own guard.

`apps/spaces/tools/build_examples.py` runs this synthesis for every function of every family and
EXECUTES each argument set through the family's compiled kernel; the result lands in
`apps/spaces/algenta/examples/<family>.json` with `verified` true when the kernel answered a
result. The Playground reads that file first (`for_form`) and synthesises only for a function the
file does not know. Nothing here is typed by hand per function: the values come from the rules
below, the verification from the kernel.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from functools import lru_cache
from pathlib import Path
from typing import Any

from . import playground

#: One flat list of numbers, the default length of every list the visitor sees.
LIST_LEN = 5
#: Square matrices open at 3 × 3.
SIDE = 3
#: The count a bare count parameter opens with when it bounds nothing.
COUNT = 5
#: Latitude/longitude pairs: London, then Paris (the haversine hero uses the same points).
POINTS = ((51.5074, -0.1278), (48.8566, 2.3522), (40.7128, -74.0060))
TEXT = "The quick brown fox jumps over the lazy dog"
WORDS = ("alpha", "beta", "gamma", "delta", "epsilon")
FLOATS = [1.0, 2.0, 3.0, 4.0, 5.0]
INTS = [3, 1, 4, 1, 5]
FLOAT_DEFAULT = 1.5
INT_DEFAULT = 5
EXAMPLES_FILE_SUFFIX = ".json"

_TRAILING_DIGITS = re.compile(r"(\d+)$")
_FINANCE = re.compile(r"finance|option|greek|bond|portfolio|black|vol|price|asset|trading", re.I)

# --- exact names --------------------------------------------------------------------------------
INT_BY_NAME: dict[str, int] = {
    "seed": 42,
    "random_seed": 42,
    "rng_seed": 42,
    "backend": 0,
    "device": 0,
    "device_id": 0,
    "bits": 8,
    "width": 8,
    "bit_width": 8,
    "nbits": 8,
    "port": 8080,
    "year": 2026,
    "month": 9,
    "day": 24,
    "hour": 12,
    "minute": 30,
    "second": 0,
    "weekday": 2,
    "quarter": 3,
    "dow": 2,
    "timestamp": 1_758_700_000,
    "ts": 1_758_700_000,
    "epoch": 1_758_700_000,
    "unix": 1_758_700_000,
    "epoch_seconds": 1_758_700_000,
    "millis": 1_758_700_000_000,
    "precision": 2,
    "digits": 2,
    "decimals": 2,
    "places": 2,
    "ndigits": 2,
    "depth": 3,
    "max_depth": 3,
    "levels": 3,
    "order": 2,
    "degree": 2,
    "lag": 1,
    "lags": 2,
    "window": 3,
    "window_size": 3,
    "span": 3,
    "period": 3,
    "periods": 3,
    "horizon": 3,
    "max_iter": 100,
    "max_iters": 100,
    "iterations": 100,
    "iters": 100,
    "epochs": 10,
    "steps": 10,
    "n_steps": 10,
    "max_steps": 10,
    "trials": 1000,
    "n_trials": 1000,
    "samples": 100,
    "n_samples": 100,
    "num_samples": 100,
    "simulations": 100,
    "successes": 50,
    "hits": 50,
    "wins": 50,
    "failures": 5,
    "losses": 5,
    "n_success": 50,
    "k": 3,
    "top_k": 3,
    "topk": 3,
    "neighbors": 3,
    "n_neighbors": 3,
    "clusters": 3,
    "n_clusters": 3,
    "components": 2,
    "n_components": 2,
    "base": 10,
    "radix": 10,
    "modulus": 97,
    "mod": 97,
    "p": 97,
    "q": 89,
    "exponent": 3,
    "power": 2,
    "shift": 1,
    "rotate": 1,
    "offset": 0,
    "start": 0,
    "stop": 5,
    "end": 5,
    "step": 1,
    "stride": 1,
    "capacity": 16,
    "limit": 10,
    "max_len": 10,
    "max_length": 10,
    "min_len": 1,
    "min_length": 1,
    "threshold": 3,
    "min_count": 1,
    "min_support": 2,
    "budget": 100,
    "retries": 3,
    "max_retries": 3,
    "servers": 2,
    "channels": 3,
    "batch": 4,
    "batch_size": 4,
    "heads": 2,
    "n_heads": 2,
    "vocab": 100,
    "vocab_size": 100,
    "head_dim": 16,
    "hidden": 16,
    "dim": 16,
    "d_model": 16,
    "seq": 4,
    "seq_len": 4,
    "tokens": 4,
    "n_tokens": 4,
    "layers": 2,
    "n_layers": 2,
    "rank": 2,
    "axis": 0,
    "dimension": 2,
    "ndim": 2,
    "channel": 0,
    "level": 1,
    "flags": 1,
    "code": 200,
    "status": 200,
    "status_code": 200,
    "http_status": 200,
    "version": 1,
    "id": 1,
    "key": 7,
    "value": 3,
    "x": 3,
    "y": 4,
    "z": 5,
    "a": 6,
    "b": 4,
    "c": 2,
    "m": 3,
    "n": 100,
    "n_a": 1000,
    "n_b": 1000,
    "trials_a": 1000,
    "trials_b": 1000,
    "successes_a": 50,
    "successes_b": 65,
    "conversions": 50,
    "clicks": 50,
    "impressions": 1000,
    "visitors": 1000,
    "population": 1000,
    "lo": 0,
    "low": 0,
    "min": 0,
    "minimum": 0,
    "hi": 10,
    "high": 10,
    "max": 10,
    "maximum": 10,
    "left": 0,
    "right": 5,
    "top": 0,
    "bottom": 5,
    "row": 0,
    "col": 0,
    "column": 0,
    "i": 0,
    "j": 0,
    "idx": 0,
    "index": 0,
    "pos": 0,
    "position": 0,
    "at": 0,
    "cursor": 0,
    "u": 0,
    "v": 1,
    "source": 0,
    "src": 0,
    "target": 1,
    "dst": 1,
    "node": 0,
    "from_node": 0,
    "to_node": 1,
    "root": 0,
    "vertex": 0,
    "vertices": 5,
    "nodes": 5,
    "edges": 5,
    "num_nodes": 5,
    "n_nodes": 5,
    "num_edges": 5,
    "n_edges": 5,
    "num_vertices": 5,
    "rows": SIDE,
    "cols": SIDE,
    "columns": SIDE,
    "height": SIDE,
    "size": COUNT,
    "count": COUNT,
    "length": COUNT,
    "len": COUNT,
    "num": COUNT,
    "number": COUNT,
    "total": COUNT,
    "n_items": COUNT,
}
FLOAT_BY_NAME: dict[str, float] = {
    "alpha": 0.05,
    "significance": 0.05,
    "sig": 0.05,
    "level": 0.95,
    "confidence": 0.95,
    "conf": 0.95,
    "confidence_level": 0.95,
    "ci": 0.95,
    "power": 0.8,
    "beta": 0.2,
    "p": 0.5,
    "prob": 0.5,
    "probability": 0.5,
    "p0": 0.5,
    "p1": 0.6,
    "p2": 0.55,
    "p_value": 0.03,
    "pvalue": 0.03,
    "p_val": 0.03,
    "pval": 0.03,
    "p_a": 0.5,
    "p_b": 0.55,
    "baseline": 0.5,
    "uplift": 0.05,
    "mde": 0.05,
    "effect": 0.2,
    "effect_size": 0.2,
    "t_stat": 2.1,
    "statistic": 2.1,
    "chi2": 3.84,
    "df": 10.0,
    "dof": 10.0,
    "z_score": 1.96,
    "theta": 0.5,
    "q": 0.5,
    "quantile": 0.5,
    "percentile": 50.0,
    "pct": 50.0,
    "rate": 0.05,
    "r": 0.05,
    "interest": 0.05,
    "discount": 0.05,
    "discount_rate": 0.05,
    "growth": 0.03,
    "inflation": 0.02,
    "yield": 0.04,
    "coupon": 0.05,
    "apr": 0.05,
    "learning_rate": 0.01,
    "lr": 0.01,
    "eta": 0.01,
    "step_size": 0.01,
    "momentum": 0.9,
    "decay": 0.9,
    "gamma": 0.9,
    "lambda": 0.5,
    "lambda_": 0.5,
    "lam": 0.5,
    "reg": 0.1,
    "l1": 0.1,
    "l2": 0.1,
    "ridge": 0.1,
    "dropout": 0.1,
    "temperature": 0.7,
    "temp": 0.7,
    "top_p": 0.9,
    "nucleus": 0.9,
    "penalty": 1.1,
    "repetition_penalty": 1.1,
    "threshold": 0.5,
    "cutoff": 0.5,
    "tol": 1e-6,
    "tolerance": 1e-6,
    "eps": 1e-6,
    "epsilon": 1e-6,
    "atol": 1e-8,
    "rtol": 1e-5,
    "delta": 0.1,
    "h": 0.01,
    "dt": 0.01,
    "sigma": 1.0,
    "std": 1.0,
    "stddev": 1.0,
    "sd": 1.0,
    "scale": 1.0,
    "variance": 1.0,
    "var": 1.0,
    "mu": 0.0,
    "mean": 0.0,
    "loc": 0.0,
    "median": 0.0,
    "mode": 0.0,
    "center": 0.0,
    "x": 1.5,
    "y": 2.5,
    "z": 3.5,
    "a": 1.0,
    "b": 2.0,
    "c": 3.0,
    "d": 4.0,
    "t": 1.0,
    "u": 0.3,
    "v": 0.7,
    "w": 1.0,
    "weight": 1.0,
    "mass": 1.0,
    "value": 2.5,
    "amount": 100.0,
    "principal": 1000.0,
    "pv": 1000.0,
    "fv": 1100.0,
    "payment": 100.0,
    "pmt": 100.0,
    "cost": 100.0,
    "revenue": 150.0,
    "profit": 50.0,
    "budget": 100.0,
    "salary": 50000.0,
    "price": 100.0,
    "spot": 100.0,
    "s": 100.0,
    "s0": 100.0,
    "strike": 105.0,
    "k": 105.0,
    "volatility": 0.2,
    "vol": 0.2,
    "iv": 0.2,
    "maturity": 1.0,
    "tau": 1.0,
    "years": 1.0,
    "time": 1.0,
    "duration": 1.0,
    "dividend": 0.0,
    "div": 0.0,
    "q_div": 0.0,
    "lat": POINTS[0][0],
    "latitude": POINTS[0][0],
    "lat1": POINTS[0][0],
    "latitude1": POINTS[0][0],
    "lon": POINTS[0][1],
    "lng": POINTS[0][1],
    "longitude": POINTS[0][1],
    "lon1": POINTS[0][1],
    "lat2": POINTS[1][0],
    "latitude2": POINTS[1][0],
    "lon2": POINTS[1][1],
    "lng2": POINTS[1][1],
    "longitude2": POINTS[1][1],
    "radius": 6371.0,
    "earth_radius": 6371.0,
    "distance": 10.0,
    "angle": 45.0,
    "degrees": 45.0,
    "radians": 0.7853981633974483,
    "bearing": 90.0,
    "lo": 0.0,
    "low": 0.0,
    "min": 0.0,
    "minimum": 0.0,
    "lower": 0.0,
    "start": 0.0,
    "begin": 0.0,
    "hi": 1.0,
    "high": 1.0,
    "max": 1.0,
    "maximum": 1.0,
    "upper": 1.0,
    "end": 1.0,
    "stop": 1.0,
    "width": 4.0,
    "height": 3.0,
    "length": 5.0,
    "area": 12.0,
    "volume": 60.0,
    "depth": 2.0,
    "speed": 60.0,
    "velocity": 60.0,
    "acceleration": 9.81,
    "gravity": 9.81,
    "g": 9.81,
    "force": 10.0,
    "energy": 100.0,
    "frequency": 50.0,
    "freq": 50.0,
    "hz": 50.0,
    "sample_rate": 100.0,
    "fs": 100.0,
    "phase": 0.0,
    "amplitude": 1.0,
    "amp": 1.0,
    "period": 1.0,
    "omega": 6.283185307179586,
    "celsius": 20.0,
    "fahrenheit": 68.0,
    "kelvin": 293.15,
    "temperature_c": 20.0,
    "score": 0.8,
    "similarity": 0.8,
    "ratio": 0.5,
    "fraction": 0.5,
    "share": 0.5,
    "pct_change": 0.1,
    "risk": 0.2,
    "risk_p5": 0.2,
    "utility": 0.5,
    "reward": 1.0,
    "cost_per_call": 0.01,
    "load": 0.5,
    "arrival_rate": 0.8,
    "service_rate": 1.0,
    "utilization": 0.8,
    "rho": 0.8,
    "bandwidth": 1.0,
    "smoothing": 0.5,
    "smooth": 0.5,
    "span": 3.0,
    "factor": 2.0,
    "multiplier": 2.0,
    "exponent": 2.0,
    "base": 10.0,
    "target": 1.0,
    "goal": 1.0,
    "estimate": 1.0,
    "observed": 1.2,
    "expected": 1.0,
    "actual": 1.2,
    "predicted": 1.1,
    "residual": 0.1,
    "error": 0.1,
    "noise": 0.1,
    "n": 5.0,
    "count": 5.0,
    "size": 5.0,
    "total": 10.0,
    "sum": 15.0,
    "capital": 1000.0,
}
STR_BY_NAME: dict[str, str] = {
    "text": TEXT,
    "s": TEXT,
    "string": TEXT,
    "str": TEXT,
    "sentence": TEXT,
    "doc": TEXT,
    "document": TEXT,
    "content": TEXT,
    "body": TEXT,
    "message": TEXT,
    "msg": TEXT,
    "input": TEXT,
    "line": TEXT,
    "paragraph": TEXT,
    "query": "quick fox",
    "q": "quick fox",
    "needle": "fox",
    "haystack": TEXT,
    "reference": TEXT,
    "hypothesis": "The quick brown fox jumped over the dog",
    "candidate": "The quick brown fox jumped over the dog",
    "prompt": "Explain compiled kernels in one sentence.",
    "response": "Compiled kernels run your Python call as native code.",
    "answer": "42",
    "word": "kernel",
    "token": "kernel",
    "term": "kernel",
    "prefix": "ker",
    "suffix": "nel",
    "a": "kitten",
    "b": "sitting",
    "s1": "kitten",
    "s2": "sitting",
    "left": "kitten",
    "right": "sitting",
    "x": "kitten",
    "y": "sitting",
    "first": "kitten",
    "second": "sitting",
    "source": "kitten",
    "target": "sitting",
    "old": "kitten",
    "new": "sitting",
    "expected": "kitten",
    "actual": "sitting",
    "pattern": "[a-z]+",
    "regex": "[a-z]+",
    "glob": "*.csv",
    "wildcard": "*.csv",
    "path": "reports/q3.csv",
    "file": "reports/q3.csv",
    "filename": "q3.csv",
    "filepath": "reports/q3.csv",
    "dir": "reports",
    "directory": "reports",
    "folder": "reports",
    "ext": "csv",
    "extension": "csv",
    "url": "https://algenta.ai/pricing",
    "uri": "https://algenta.ai/pricing",
    "href": "https://algenta.ai/pricing",
    "link": "https://algenta.ai/pricing",
    "domain": "algenta.ai",
    "host": "algenta.ai",
    "hostname": "algenta.ai",
    "ip": "192.168.1.10",
    "ipv4": "192.168.1.10",
    "address": "192.168.1.10",
    "cidr": "192.168.1.0/24",
    "mac": "00:1A:2B:3C:4D:5E",
    "email": "team@example.com",
    "user": "alice",
    "username": "alice",
    "name": "alpha",
    "key": "alpha",
    "label": "alpha",
    "field": "alpha",
    "column": "alpha",
    "tag": "alpha",
    "id": "a1b2c3",
    "uuid": "123e4567-e89b-12d3-a456-426614174000",
    "slug": "compiled-kernels",
    "json": '{"a": 1, "b": [1, 2, 3]}',
    "json_text": '{"a": 1, "b": [1, 2, 3]}',
    "payload": '{"a": 1}',
    "csv": "a,b,c\n1,2,3\n4,5,6",
    "csv_text": "a,b,c\n1,2,3\n4,5,6",
    "tsv": "a\tb\n1\t2",
    "yaml": "a: 1\nb: 2",
    "toml": 'a = 1\nb = "x"',
    "xml": "<root><a>1</a></root>",
    "html": "<p>Hello <b>world</b></p>",
    "date": "2026-09-24",
    "day": "2026-09-24",
    "start_date": "2026-01-01",
    "end_date": "2026-09-24",
    "datetime": "2026-09-24T12:30:00Z",
    "timestamp": "2026-09-24T12:30:00Z",
    "iso": "2026-09-24T12:30:00Z",
    "time": "12:30:00",
    "tz": "UTC",
    "timezone": "UTC",
    "zone": "UTC",
    "locale": "en_US",
    "lang": "en",
    "language": "en",
    "country": "GB",
    "currency": "USD",
    "code": "USD",
    "symbol": "ALG",
    "ticker": "ALG",
    "hex": "deadbeef",
    "hexstr": "deadbeef",
    "b64": "aGVsbG8gd29ybGQ=",
    "base64": "aGVsbG8gd29ybGQ=",
    "encoded": "aGVsbG8gd29ybGQ=",
    "digest": "5d41402abc4b2a76b9719d911017c592",
    "hash": "5d41402abc4b2a76b9719d911017c592",
    "sep": ",",
    "separator": ",",
    "delimiter": ",",
    "delim": ",",
    "joiner": ", ",
    "quote": '"',
    "fmt": "%Y-%m-%d",
    "format": "%Y-%m-%d",
    "template": "Hello, {name}!",
    "mask": "###-##-####",
    "cron": "0 9 * * 1-5",
    "expr": "1 + 2 * 3",
    "expression": "1 + 2 * 3",
    "formula": "a + b * c",
    "sql": "SELECT a, b FROM t WHERE a > 1",
    "method": "GET",
    "verb": "GET",
    "scheme": "https",
    "protocol": "https",
    "version": "1.0.0",
    "semver": "1.0.0",
    "op": "add",
    "operation": "add",
    "mode": "fast",
    "kind": "linear",
    "type": "linear",
    "kernel": "linear",
    "metric": "euclidean",
    "distance": "euclidean",
    "norm": "l2",
    "strategy": "greedy",
    "policy": "greedy",
    "algorithm": "auto",
    "action": "approve",
    "tool": "search",
    "role": "user",
    "system": "You are a helpful assistant.",
    "unit": "km",
    "units": "km",
    "from_unit": "km",
    "to_unit": "mi",
    "color": "#3B82F6",
    "hex_color": "#3B82F6",
    "password": "correct horse battery staple",
    "secret": "correct horse battery staple",
    "salt": "algenta",
    "seed": "algenta",
    "nonce": "algenta",
    "iv": "0123456789abcdef",
    "plaintext": TEXT,
    "ciphertext": "aGVsbG8gd29ybGQ=",
    "tokens": "the quick brown fox",
    "words": "the quick brown fox",
    "alphabet": "abcdefghijklmnopqrstuvwxyz",
    "chars": "abc",
    "charset": "utf-8",
    "encoding": "utf-8",
    "codec": "utf-8",
    "dtype": "float64",
    "empty": "",
    "default": "n/a",
    "fallback": "n/a",
    "placeholder": "n/a",
}
FALSE_BOOLS = frozenset(
    {
        "strict",
        "reverse",
        "reversed",
        "descending",
        "desc",
        "verbose",
        "debug",
        "dry_run",
        "dryrun",
        "inplace",
        "in_place",
        "empty",
        "force",
        "override",
        "skip",
        "ignore",
        "raw",
        "unsafe",
        "quiet",
        "disabled",
        "disable",
        "negate",
        "invert",
        "inverse",
        "reject",
        "deny",
        "block",
        "locked",
        "closed",
        "hidden",
        "readonly",
        "read_only",
        "frozen",
        "paused",
        "cancelled",
        "failed",
        "error",
        "is_error",
        "has_error",
        "missing",
        "null",
        "none",
    }
)
LIST_FLOAT_BY_NAME: dict[str, list[float]] = {
    "weights": [0.2, 0.2, 0.2, 0.2, 0.2],
    "w": [0.2, 0.2, 0.2, 0.2, 0.2],
    "probs": [0.1, 0.2, 0.3, 0.25, 0.15],
    "probabilities": [0.1, 0.2, 0.3, 0.25, 0.15],
    "p": [0.1, 0.2, 0.3, 0.25, 0.15],
    "dist": [0.1, 0.2, 0.3, 0.25, 0.15],
    "returns": [0.01, -0.02, 0.015, 0.03, -0.01],
    "rets": [0.01, -0.02, 0.015, 0.03, -0.01],
    "prices": [100.0, 101.5, 99.8, 102.3, 103.1],
    "closes": [100.0, 101.5, 99.8, 102.3, 103.1],
    "highs": [101.0, 102.5, 100.8, 103.3, 104.1],
    "lows": [99.0, 100.5, 98.8, 101.3, 102.1],
    "opens": [99.5, 101.0, 99.9, 102.0, 102.8],
    "volumes": [1000.0, 1200.0, 900.0, 1500.0, 1100.0],
    "x": [1.0, 2.0, 3.0, 4.0, 5.0],
    "xs": [1.0, 2.0, 3.0, 4.0, 5.0],
    "y": [2.0, 4.1, 6.2, 7.9, 10.1],
    "ys": [2.0, 4.1, 6.2, 7.9, 10.1],
    "y_true": [1.0, 0.0, 1.0, 1.0, 0.0],
    "y_pred": [0.9, 0.2, 0.8, 0.6, 0.3],
    "targets": [1.0, 0.0, 1.0, 1.0, 0.0],
    "predictions": [0.9, 0.2, 0.8, 0.6, 0.3],
    "scores": [0.9, 0.2, 0.8, 0.6, 0.3],
    "labels": [1.0, 0.0, 1.0, 1.0, 0.0],
    "logits": [2.0, -1.0, 0.5, 1.5, -0.5],
    "a": [1.0, 2.0, 3.0, 4.0, 5.0],
    "b": [2.0, 3.0, 4.0, 5.0, 6.0],
    "u": [1.0, 0.0, 0.0],
    "v": [0.0, 1.0, 0.0],
    "lats": [POINTS[0][0], POINTS[1][0], POINTS[2][0]],
    "latitudes": [POINTS[0][0], POINTS[1][0], POINTS[2][0]],
    "lons": [POINTS[0][1], POINTS[1][1], POINTS[2][1]],
    "longitudes": [POINTS[0][1], POINTS[1][1], POINTS[2][1]],
    "times": [0.0, 1.0, 2.0, 3.0, 4.0],
    "timestamps": [0.0, 1.0, 2.0, 3.0, 4.0],
    "t": [0.0, 1.0, 2.0, 3.0, 4.0],
    "signal": [0.0, 1.0, 0.0, -1.0, 0.0],
    "samples": [0.0, 1.0, 0.0, -1.0, 0.0],
    "wave": [0.0, 1.0, 0.0, -1.0, 0.0],
    "cashflows": [-1000.0, 300.0, 400.0, 500.0],
    "cash_flows": [-1000.0, 300.0, 400.0, 500.0],
    "flows": [-1000.0, 300.0, 400.0, 500.0],
    "coefficients": [1.0, -2.0, 1.0],
    "coeffs": [1.0, -2.0, 1.0],
    "poly": [1.0, -2.0, 1.0],
    "kernel": [0.25, 0.5, 0.25],
    "filter": [0.25, 0.5, 0.25],
    "taps": [0.25, 0.5, 0.25],
}

# --- rules --------------------------------------------------------------------------------------


def _base(name: str) -> tuple[str, int | None]:
    """`lat2` -> (`lat`, 2); `n_b` -> (`n_b`, None)."""
    lower = name.lower()
    m = _TRAILING_DIGITS.search(lower)
    if m and len(lower) > len(m.group(1)):
        return lower[: m.start()], int(m.group(1))
    return lower, None


def _lookup(table: Mapping[str, Any], name: str) -> Any | None:
    lower = name.lower()
    if lower in table:
        return table[lower]
    base, _ = _base(lower)
    if base in table:
        return table[base]
    for token in reversed(base.split("_")):  # `n_samples` -> `samples`, `max_iter` -> `iter`
        if token in table:
            return table[token]
    return None


def scalar(name: str, type_name: str, module: str = "") -> Any:
    """One primitive value for `name` of `type_name`, chosen from the tables above."""
    lower = name.lower()
    finance = bool(_FINANCE.search(module))
    if type_name == "Bool":
        base, _ = _base(lower)
        return not any(word in FALSE_BOOLS for word in (lower, base, *base.split("_")))
    if type_name == "String":
        found = _lookup(STR_BY_NAME, lower)
        return found if found is not None else "hello world"
    if type_name in ("Float32", "Float64"):
        if finance and lower in ("sigma", "s", "k", "r", "t", "q"):
            return {"sigma": 0.2, "s": 100.0, "k": 105.0, "r": 0.05, "t": 1.0, "q": 0.0}[lower]
        if lower in FLOAT_BY_NAME:
            return FLOAT_BY_NAME[lower]
        base, idx = _base(lower)
        coords = ("lat", "latitude", "lon", "lng", "longitude")
        if idx is not None and base in coords and idx <= len(POINTS):
            point = POINTS[idx - 1]
            return point[0] if base.startswith("la") else point[1]
        found = _lookup(FLOAT_BY_NAME, lower)
        if found is None:
            return FLOAT_DEFAULT
        if idx is not None and base in ("x", "y", "z", "a", "b", "c"):
            return round(float(found) + 0.5 * (idx - 1), 6)  # x1 1.5, x2 2.0: distinct points
        return found
    if type_name in ("Int", "UInt8", "UInt16", "UInt32", "UInt64"):
        found = _lookup(INT_BY_NAME, lower)
        value = INT_DEFAULT if found is None else int(found)
        if type_name == "UInt8":
            value = min(max(value, 0), 255)
        return max(value, 0) if type_name.startswith("UInt") else value
    return None


def value_for(
    name: str,
    type_name: str,
    structs: Mapping[str, Any] | Sequence[Any],
    module: str = "",
    depth: int = 0,
) -> Any:
    """A value of `type_name` for the parameter (or struct field) `name`."""
    if type_name == "None":
        return None
    inner = playground.list_inner(type_name)
    if inner is not None:
        return list_value(name, inner, structs, module, depth)
    struct = _struct(structs, type_name)
    if struct is not None:
        return {
            f["name"]: value_for(f["name"], f["type"], structs, module, depth + 1)
            for f in struct["fields"]
        }
    return scalar(name, type_name, module)


def list_value(name: str, inner: str, structs: Any, module: str, depth: int) -> list[Any]:
    lower = name.lower()
    if inner in ("Float32", "Float64"):
        found = _lookup(LIST_FLOAT_BY_NAME, lower)
        return list(found) if found is not None else list(FLOATS)
    if inner in ("Int", "UInt8", "UInt16", "UInt32", "UInt64"):
        base, _ = _base(lower)
        if base in ("indices", "index", "idx", "ids", "positions", "offsets"):
            return [0, 1, 2, 3, 4]
        if base in (
            "labels",
            "classes",
            "y",
            "y_true",
            "targets",
            "event",
            "events",
            "treatment",
            "treated",
            "censored",
            "status",
            "flags",
            "mask",
            "hits",
            "outcome",
            "outcomes",
        ):
            return [1, 0, 1, 1, 0]
        if base in ("y_pred", "predictions", "preds"):
            return [1, 0, 0, 1, 0]
        if base in ("sources", "src", "from_nodes", "u", "edges_from", "rows", "row"):
            return [0, 0, 1, 2, 3]
        if base in ("targets_", "dst", "to_nodes", "v", "edges_to", "cols", "col"):
            return [1, 2, 2, 3, 4]
        if base in ("shape", "dims", "sizes"):
            return [SIDE, SIDE]
        if base in ("tokens", "token_ids", "ids", "input_ids"):
            return [101, 2054, 2003, 1996, 102]
        if base in ("bytes", "data", "buffer", "pixels", "image", "img"):
            return [0, 64, 128, 192, 255] if inner == "UInt8" else list(INTS)
        return list(INTS)
    if inner == "String":
        base, _ = _base(lower)
        if base in ("tokens", "words", "terms"):
            return TEXT.lower().split()[:LIST_LEN]
        if base in ("docs", "documents", "corpus", "texts", "sentences", "lines"):
            return [
                TEXT,
                "Compiled kernels run your Python call as native code.",
                "Pack my box with five dozen liquor jugs.",
            ]
        if base in ("keys", "names", "labels", "columns", "fields", "headers"):
            return list(WORDS)
        return list(WORDS)
    if inner == "Bool":
        return [True, False, True, True, False]
    inner_inner = playground.list_inner(inner)
    if inner_inner is not None:  # a matrix: rows of the inner kind
        return [
            list_value(f"{name}_row", inner_inner, structs, module, depth + 1)[:SIDE]
            for _ in range(SIDE)
        ]
    struct = _struct(structs, inner)
    if struct is not None:
        return [value_for(name, inner, structs, module, depth + 1) for _ in range(SIDE)]
    return [scalar(name, inner, module) for _ in range(LIST_LEN)]


def _struct(structs: Any, type_name: str) -> Mapping[str, Any] | None:
    if isinstance(structs, Mapping):
        found = structs.get(type_name)
        return found if isinstance(found, Mapping) else None
    for entry in structs or ():
        if isinstance(entry, Mapping) and entry.get("name") == type_name:
            return entry
    return None


# --- count relations ------------------------------------------------------------------------------


def _product(values: Sequence[int]) -> int:
    out = 1
    for v in values:
        out *= v
    return out


def apply_relations(form: playground.Form, values: dict[str, Any]) -> None:
    """Make every count relation hold exactly: counts equal the lengths they bound, indexes 0."""
    types = {f.name: f.type_name for f in form.fields}
    for rel in form.count_relations:
        factors = [n for n in rel["factors"] if n in values]
        if not factors:
            continue
        is_index = rel.get("role") == "index" or int(rel.get("plus", 0)) > 0
        if is_index:
            for n in factors:
                values[n] = 0
            need = 1 + int(rel.get("plus", 0))
        else:
            per = COUNT if len(factors) == 1 else SIDE
            for n in factors:
                values[n] = per
            need = _product([values[n] for n in factors]) + int(rel.get("plus", 0))
        for list_name in rel["bounds"]:
            if list_name not in values or not isinstance(values[list_name], list):
                continue
            inner = playground.list_inner(types.get(list_name, "")) or "Float64"
            if rel.get("scope") == "length":
                values[list_name] = _resize(values[list_name], need, list_name, inner, form)
                if not is_index and len(factors) == 1:
                    values[factors[0]] = len(values[list_name])
            else:  # element_length: every element list holds `need`
                values[list_name] = [
                    _resize(e, need, list_name, playground.list_inner(inner) or inner, form)
                    if isinstance(e, list)
                    else e
                    for e in values[list_name]
                ]


def _resize(items: list[Any], need: int, name: str, inner: str, form: playground.Form) -> list[Any]:
    if len(items) >= need:
        return items if need == 0 else items[: max(need, min(len(items), LIST_LEN))]
    filler = list_value(name, inner, form.structs, form.module, 1)
    out = list(items)
    while len(out) < need:
        out.append(filler[len(out) % len(filler)] if filler else scalar(name, inner, form.module))
    return out


#: Int parameters that count the elements of a list in the same form even when the contract
#: declares no relation for them ("flat" functions take `n_rows`/`n_cols`/`n` beside a flat list).
COUNT_NAMES = frozenset(
    {
        "n",
        "count",
        "len",
        "length",
        "size",
        "num",
        "number",
        "total",
        "n_items",
        "n_obs",
        "n_samples",
        "n_points",
        "n_values",
        "n_elements",
        "n_units",
        "n_rows",
        "rows",
        "n_cols",
        "cols",
        "columns",
        "n_features",
        "n_vars",
        "n_cons",
        "n_lanes",
        "n_tok",
        "n_tokens",
        "d_model",
        "n_bins",
        "n_pairs",
        "m",
        "k",
        "batch",
        "seq",
        "seq_len",
        "horizon",
        "n_series",
    }
)


def _follow_lists(form: playground.Form, values: dict[str, Any]) -> None:
    """Counts with no declared relation take the length of the flat lists they sit beside: a
    5-element list and `n = 100` is what the kernels refused most often in the first build."""
    related = {n for rel in form.count_relations for n in (*rel["factors"], *rel["bounds"])}
    flat = [f for f in form.fields if f.list_of and playground.list_inner(f.list_of) is None]
    if not flat:
        return
    counts = [
        f
        for f in form.fields
        if f.type_name == "Int"
        and f.name not in related
        and (f.name.lower() in COUNT_NAMES or f.name.lower().startswith(("n_", "num_")))
    ]
    if not counts:
        return
    shape_pairs = (
        ("n_rows", "n_cols"),
        ("rows", "cols"),
        ("rows", "columns"),
        ("m", "n"),
        ("m", "k"),
    )
    names = {f.name.lower() for f in counts}
    for a, b in shape_pairs:
        if a in names and b in names:  # a flat matrix: SIDE x SIDE, every flat list SIDE*SIDE long
            for f in counts:
                if f.name.lower() in (a, b):
                    values[f.name] = SIDE
            for f in flat:
                if isinstance(values.get(f.name), list) and len(values[f.name]) == LIST_LEN:
                    values[f.name] = _resize(
                        values[f.name], SIDE * SIDE, f.name, f.list_of or "Float64", form
                    )
            return
    length = next(
        (len(values[f.name]) for f in flat if isinstance(values.get(f.name), list)), LIST_LEN
    )
    for f in counts:
        if f.name.lower() in (
            "n_bins",
            "k",
            "horizon",
            "batch",
            "seq",
            "seq_len",
            "d_model",
            "n_features",
        ):
            values[f.name] = (
                min(values.get(f.name, SIDE), SIDE)
                if values.get(f.name, 0) > length
                else values[f.name]
            )
            continue
        values[f.name] = length


def synthesize(form: playground.Form) -> dict[str, Any]:
    """The prefilled argument mapping for `form`: every field a value, every relation satisfied."""
    values: dict[str, Any] = {
        f.name: value_for(f.name, f.type_name, form.structs, form.module) for f in form.fields
    }
    _follow_lists(form, values)
    apply_relations(form, values)
    return values


# --- the crash gate's arguments ------------------------------------------------------------------
#: The values `scripts/hf_kernels/family_smoke.py` called every function with (zero crashes or
#: hangs across the portfolio, the 16 exceptions excluded at the ABI): the fallback when a
#: rules-based proposal hangs or is refused.
SMOKE_INT = 2
SMOKE_FLOAT = 0.5
SMOKE_LIST_LEN = 8


def smoke_value(type_name: str, structs: Any, depth: int = 0) -> Any:
    if type_name == "None":
        return None
    if type_name == "Bool":
        return True
    if type_name == "String":
        return "algenta"
    if type_name in ("Int", "UInt8", "UInt16", "UInt32", "UInt64"):
        return SMOKE_INT
    if type_name in ("Float32", "Float64"):
        return SMOKE_FLOAT
    inner = playground.list_inner(type_name)
    if inner is not None:
        n = SMOKE_LIST_LEN if depth == 0 else 4
        return [smoke_value(inner, structs, depth + 1) for _ in range(n)]
    struct = _struct(structs, type_name)
    if struct is None:
        return None
    return {f["name"]: smoke_value(f["type"], structs, depth + 1) for f in struct["fields"]}


def plain_args(form: playground.Form) -> dict[str, Any]:
    """The crash gate's argument shapes for `form`, its count relations satisfied."""
    values = {f.name: smoke_value(f.type_name, form.structs) for f in form.fields}
    apply_relations(form, values)
    return values


# --- the verified file ----------------------------------------------------------------------------


@lru_cache(maxsize=64)
def _load(path: str) -> Mapping[str, Any]:
    p = Path(path)
    if not p.is_file():
        return {}
    data = json.loads(p.read_text(encoding="utf-8"))
    functions = data.get("functions") if isinstance(data, Mapping) else None
    return functions if isinstance(functions, Mapping) else {}


def load_examples(directory: Path | str, family: str) -> Mapping[str, Any]:
    """`module.function` -> {"args": {...}, "verified": bool, "outcome": str} for one family."""
    return _load(str(Path(directory) / f"{family}{EXAMPLES_FILE_SUFFIX}"))


def for_form(form: playground.Form, family: str, directory: Path | str | None) -> dict[str, Any]:
    """The arguments the Playground opens `form` with: the verified file's, else synthesised."""
    if directory is not None:
        entry = load_examples(directory, family).get(f"{form.module}.{form.function}")
        if isinstance(entry, Mapping) and isinstance(entry.get("args"), Mapping):
            names = {f.name for f in form.fields}
            args = {k: v for k, v in entry["args"].items() if k in names}
            if len(args) == len(names):
                return args
    return synthesize(form)
