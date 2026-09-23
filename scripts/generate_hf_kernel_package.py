#!/usr/bin/env python3
"""Generate a Hugging Face kernel repository from built Algenta family libraries.

Input: one or more `--native <backend>=<dir>` staged closures produced by
scripts/build_hf_kernel_family.py (each holds libalgenta_<family>.{dylib,so} + the Mojo runtime
closure + manifest.json). Output: `<out>/build/<variant>/...` for every Hub build variant that
matches the closure's platform and backend, plus README.md (the kernel card) and LICENSE.

Package rules (huggingface.co/docs/kernels/kernel-requirements): stdlib-only Python with relative
imports; `build/<variant>/__init__.py` exports the public API; a directory named after the repo
(dashes -> underscores) exports the same symbols; `metadata.json` carries name, id, version,
license, backend and a sha256/base64 digest of every file except itself and its signature.

The generated Python mirrors the module tree (`kernel.forecasting.interval` is a real subpackage
and module), every wrapper carries the function's own documentation and default values (read from
the Mojo sources), and the shipped `_native/manifest.json` holds only what the loader needs.

Usage:
  scripts/generate_hf_kernel_package.py --family algenta-stats --native cpu=build_out/algenta-stats/_native \
      --out hub/algenta-stats [--torch-versions 2.5 ... 2.14] [--kernel-version 1]
"""
from __future__ import annotations

import argparse
import base64
import ctypes
import hashlib
import json
import keyword
import pprint
import re
import platform
import shutil
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "scripts" / "hf_kernels" / "templates"
ENGINE = ROOT / "mojo" / "engine"
DEFAULT_TORCH_VERSIONS = ["2.5", "2.6", "2.7", "2.8", "2.9", "2.10", "2.11", "2.12", "2.13", "2.14"]
PY_TYPES = {"Int": "int", "Float64": "float", "Float32": "float", "Bool": "bool", "String": "str", "UInt8": "int", "UInt16": "int", "UInt32": "int", "UInt64": "int", "None": "None"}
PUBLIC_MANIFEST_KEYS = ("schema", "family", "backend", "abi_version", "library", "cuda_targets", "cuda_libraries", "platform", "minos", "load_order", "files", "runtime_tag", "mojo_version", "source_commit", "resident_stage_tier")
# Resident decode staging tier of a GPU build (build_hf_kernel_family.py --stage-tier;
# mojo/engine/residentk/contract.mojo RESIDENT_MAX_D_MODEL): a model is accepted when
# max(d_model, h_q*d_head, d_ff) <= tier. A GPU manifest written before the field existed is a
# default build, which stages 3072.
GPU_BACKENDS = ("metal", "cuda")
DEFAULT_STAGE_TIER = 3072
STAGE_TIER_MODELS = {
    3072: "Qwen3-0.6B",
    6144: "Qwen3-0.6B and Qwen3-1.7B",
    8192: "Qwen3-0.6B, Qwen3-1.7B and Llama-3.2-1B/3B",
}
# CUDA builds of each PyTorch release (the loader matches the variant to torch.version.cuda exactly).
CUDA_VERSIONS_BY_TORCH = {"2.5": ["118", "121", "124"], "2.6": ["118", "124", "126"], "2.7": ["118", "126", "128"], "2.8": ["126", "128", "129"], "2.9": ["126", "128", "130"]}
CUDA_VERSIONS_DEFAULT = ["126", "128", "129", "130", "132"]
STATUS_CODE_SCAN = 4096
_LITERAL = re.compile(r"^(-?\d+(\.\d+)?([eE][-+]?\d+)?|True|False|\"[^\"]*\")$")


def py_type(t: str) -> str:
    if t.startswith("List["):
        return f"list[{py_type(t[5:-1])}]"
    return PY_TYPES.get(t, "dict")


def variant_names(platform: str, backend: str, torch_versions: list[str]) -> list[str]:
    arch, os_ = platform.split("-", 1)
    out = []
    for tv in torch_versions:
        tag = "torch" + tv.replace(".", "")
        if os_ == "darwin":
            out.append(f"{tag}-{backend}-{arch}-{os_}")
        elif backend == "cuda":
            for cu in CUDA_VERSIONS_BY_TORCH.get(tv, CUDA_VERSIONS_DEFAULT):
                out.append(f"{tag}-cxx11-cu{cu}-{arch}-{os_}")
        else:
            out.append(f"{tag}-cxx11-{backend}-{arch}-{os_}")
    return out


def stage_tier_of(manifest: dict) -> int | None:
    """The staging tier a GPU closure was compiled for; None for a CPU closure (no resident decode)."""
    if manifest.get("backend") not in GPU_BACKENDS:
        return None
    tier = manifest.get("resident_stage_tier")
    return int(tier) if isinstance(tier, int) and not isinstance(tier, bool) else DEFAULT_STAGE_TIER


def backend_metadata(backend: str, manifest: dict) -> dict:
    """metadata.json's `backend` object: the `kernels` schema (type; CUDA archs) plus, for a GPU
    build, `resident_stage_tier`. The `kernels` loader (0.17.1) ignores keys it does not define, so
    the tier rides beside the variant's backend facts rather than only in the card text."""
    if backend == "cuda":
        info = {"type": "cuda", "archs": [f"{t[3]}.{t[4:]}" for t in manifest.get("cuda_targets", [])]}
    else:
        info = {"type": backend}
    tier = stage_tier_of(manifest)
    if tier is not None:
        info["resident_stage_tier"] = tier
    return info


def stage_tier_sentence(stage_tiers: dict[str, int]) -> str:
    """One card sentence per GPU tier present: which model sizes the GPU builds stage decode for."""
    by_tier: dict[int, list[str]] = {}
    for backend, tier in sorted(stage_tiers.items()):
        by_tier.setdefault(tier, []).append(backend)
    sentences = []
    for tier, backends in sorted(by_tier.items()):
        if len(by_tier) == 1:
            who = "The GPU builds stage"
        else:
            names = " and ".join(b.capitalize() if b == "metal" else b.upper() for b in backends)
            who = f"The {names} builds stage" if len(backends) > 1 else f"The {names} build stages"
        examples = STAGE_TIER_MODELS.get(tier)
        sentences.append(
            f"{who} decode for models with `max(d_model, h_q*d_head, d_ff) <= {tier}`"
            + (f", for example {examples}" if examples else "")
            + '; a larger model is refused with `KernelError("resident_dimension_too_large")`.'
        )
    return " ".join(sentences)


def digest_dir(variant_dir: Path) -> dict:
    files = {}
    for p in sorted(variant_dir.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(variant_dir).as_posix()
        if rel in ("metadata.json", "metadata.json.sigstore") or "__pycache__" in rel or rel.endswith(".pyc"):
            continue
        files[rel] = base64.b64encode(hashlib.sha256(p.read_bytes()).digest()).decode()
    return {"algorithm": "sha256", "files": files}


def ident(name: str) -> str:
    s = re.sub(r"\W", "_", name)
    return s + "_" if keyword.iskeyword(s) else s


# --- Mojo sources: documentation and default values ---------------------------------------------

def module_source(module: str) -> str:
    p = ENGINE / (module.replace(".", "/") + ".mojo")
    if not p.exists():
        p = ENGINE / module.replace(".", "/") / "__init__.mojo"
    return p.read_text() if p.exists() else ""


def _split_top_level(text: str) -> list[str]:
    out, depth, cur = [], 0, ""
    for ch in text:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur)
    return [x.strip() for x in out]


def function_source(src: str, fname: str) -> tuple[str, str]:
    """(parameter text, docstring) of `def fname(...)` in a Mojo module, or ("", "")."""
    m = re.search(r"^def\s+" + re.escape(fname) + r"\s*(\[[^\]]*\])?\s*\(", src, re.M)
    if not m:
        return "", ""
    i = m.end()
    depth, j = 1, i
    while j < len(src) and depth:
        depth += src[j] in "([{"
        depth -= src[j] in ")]}"
        j += 1
    params = src[i:j - 1]
    colon = src.find(":\n", j)
    doc = ""
    if colon != -1:
        d = re.match(r'\s*"""(.*?)"""', src[colon + 2:], re.S)
        if d:
            doc = d.group(1)
    return params, doc


def defaults_from_source(src: str, params_text: str) -> dict[str, object]:
    """Literal default values by parameter name; constants defined in the same file resolve one level."""
    out: dict[str, object] = {}
    for ptxt in _split_top_level(params_text):
        m = re.match(r"^(?:mut\s+|read\s+|owned\s+|var\s+|ref\s+)?([A-Za-z_]\w*)\s*:\s*(.+?)(?:\s*=\s*(.+))?$", ptxt, re.S)
        if not m or not m.group(3):
            continue
        text = m.group(3).strip()
        if not _LITERAL.match(text):
            const = re.search(r"^(?:comptime|alias)\s+" + re.escape(text) + r"\s*(?::\s*\w+\s*)?=\s*(.+?)\s*$", src, re.M)
            if not const or not _LITERAL.match(const.group(1).strip()):
                continue
            text = const.group(1).strip()
        if text in ("True", "False"):
            out[m.group(1)] = text == "True"
        elif text.startswith('"'):
            out[m.group(1)] = text[1:-1]
        elif re.match(r"^-?\d+$", text):
            out[m.group(1)] = int(text)
        else:
            out[m.group(1)] = float(text)
    return out


def _clean(text: str) -> str:
    text = re.sub(r"@capability.*?@endcapability", "", text, flags=re.S)
    return re.sub(r"\s+", " ", text).strip()


def summarize_doc(doc: str) -> tuple[str, dict[str, str], str]:
    """(summary paragraph, {arg: description}, returns description) from a Mojo docstring."""
    body = doc.strip()
    head = re.split(r"\n\s*\n|\n\s*(?:Args|Returns|Raises|Note|Notes|Example|Examples):", body, 1)[0]
    summary = _clean(head)
    args: dict[str, str] = {}
    a = re.search(r"\n\s*Args:\n(.*?)(?:\n\s*\n|\n\s*(?:Returns|Raises|Note|Notes|Example|Examples):|\Z)", body, re.S)
    if a:
        current = None
        for line in a.group(1).splitlines():
            m = re.match(r"^\s{4,}([A-Za-z_]\w*)\s*(?:\([^)]*\))?:\s*(.*)$", line)
            if m:
                current = m.group(1)
                args[current] = m.group(2).strip()
            elif current and line.strip():
                args[current] += " " + line.strip()
    r = re.search(r"\n\s*Returns:\n(.*?)(?:\n\s*\n|\n\s*(?:Args|Raises|Note|Notes|Example|Examples):|\Z)", body, re.S)
    returns = _clean(r.group(1)) if r else ""
    return summary, {k: _clean(v) for k, v in args.items()}, returns


def module_description(module: str, overrides: dict[str, str]) -> str:
    if module in overrides:
        return overrides[module]
    src = module_source(module)
    m = re.match(r'\s*"""(.*?)"""', src, re.S)
    if not m:
        return ""
    t = m.group(1).strip().split("\n\n")[0].replace("\n", " ")
    t = re.sub(r"^[\w./]+\.mojo\s*[—–-]+\s*", "", t)
    t = re.sub(r"^[\w.]+\s+[—–-]+\s+", "", t)
    t = re.sub(r"\s*Zero Python( imports)?( in hot loops)?\.?", "", t)
    t = re.sub(r"\s*(Phase \d+:|Replaces:).*$", "", t)
    s = re.split(r"(?<=[.!?])\s+", t.strip())[0].rstrip(".")
    return s[:1].upper() + s[1:]


# --- contract ------------------------------------------------------------------------------------

def build_contract(modules: list[str], excluded: set[str], descriptions: dict[str, str]) -> dict:
    contract = json.loads((ROOT / "packages" / "algenta" / "algenta" / "runtime_library_contract.json").read_text())
    out: dict = {"modules": {}, "status_names": {}}
    decoders_by_package: dict[str, list[str]] = {}
    for m in contract["modules"]:
        if m["name"] not in modules:
            continue
        src = module_source(m["name"])
        functions = {}
        for f in m["functions"]:
            if f"{m['name']}.{f['name']}" in excluded or f"{m['name']}.*" in excluded:
                continue
            params_text, doc = function_source(src, f["name"])
            defaults = defaults_from_source(src, params_text) if params_text else {}
            summary, arg_docs, returns_doc = summarize_doc(doc) if doc else ("", {}, "")
            params = []
            for p in f["params"]:
                spec = {"name": p["name"], "type": p["type"], "has_default": p["has_default"], "is_mut": p["is_mut"]}
                if p["has_default"] and p["name"] in defaults:
                    spec["default"] = defaults[p["name"]]
                if p["name"] in arg_docs:
                    spec["doc"] = arg_docs[p["name"]]
                params.append(spec)
            functions[f["name"]] = {"name": f["name"], "params": params, "return_type": f["return_type"], "count_relations": f.get("count_relations") or [], "doc": summary, "returns_doc": returns_doc}
            if f["name"].endswith("_status_name") and f["params"] and f["params"][0]["type"] == "Int" and f["return_type"] == "String":
                decoders_by_package.setdefault(m["name"].split(".")[0], []).append(f"{m['name']}.{f['name']}")
        structs = {s["name"]: {"name": s["name"], "fields": [{"name": fl["name"], "type": fl["type"]} for fl in s.get("fields", [])]} for s in m.get("structs", [])}
        out["modules"][m["name"]] = {"name": m["name"], "description": module_description(m["name"], descriptions), "functions": functions, "structs": structs}
    # Each engine package publishes one status vocabulary (`<pkg>.contract.<x>_status_name`); a
    # module's result structs carry codes from its own package's vocabulary.
    for name, spec in out["modules"].items():
        pkg = name.split(".")[0]
        decoders = decoders_by_package.get(pkg, [])
        preferred = [d for d in decoders if d.startswith(f"{pkg}.contract.")] or ([decoders[0]] if len(decoders) == 1 else [])
        has_status = any(any(fl["name"] == "status" and fl["type"] == "Int" for fl in s["fields"]) for s in spec["structs"].values())
        if preferred and has_status:
            spec["status_decoder"] = preferred[0]
    return out


class _NativeProbe:
    """Runs functions through a built library at generation time (card example, status vocabularies)."""

    def __init__(self, native: Path):
        manifest = json.loads((native / "manifest.json").read_text())
        self._closure = [ctypes.CDLL(str(native / name)) for name in manifest.get("load_order", [])]
        lib = ctypes.CDLL(str(native / manifest["library"]))
        lib.algenta_runtime_init.argtypes = [ctypes.c_void_p]
        lib.algenta_runtime_init.restype = ctypes.c_void_p
        lib.algenta_runtime_execute.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        lib.algenta_runtime_execute.restype = ctypes.c_void_p
        lib.algenta_runtime_free.argtypes = [ctypes.c_void_p]
        lib.algenta_runtime_shutdown.argtypes = [ctypes.c_void_p]
        self._lib = lib
        self._handle = lib.algenta_runtime_init(b"{}")

    def call(self, module: str, function: str, args: list):
        ptr = self._lib.algenta_runtime_execute(self._handle, json.dumps({"type": "library_execute", "module": module, "function": function, "args": args}).encode())
        if not ptr:  # ABI 4.4: NULL only when the response could not be allocated
            raise SystemExit(f"native runtime returned no response for {module}.{function}")
        try:
            return json.loads(ctypes.string_at(ptr).decode())
        finally:
            self._lib.algenta_runtime_free(ptr)

    def close(self) -> None:
        self._lib.algenta_runtime_shutdown(self._handle)


def status_tables(probe: _NativeProbe, contract: dict) -> dict[str, dict[int, str]]:
    tables: dict[str, dict[int, str]] = {}
    for spec in contract["modules"].values():
        decoder = spec.get("status_decoder")
        if not decoder or decoder in tables:
            continue
        module, function = decoder.rsplit(".", 1)
        names: dict[int, str] = {}
        for code in range(STATUS_CODE_SCAN):
            reply = probe.call(module, function, [code])
            name = reply.get("result")
            if isinstance(name, str) and name and "out_of_range" not in name and not name.startswith("unknown"):
                names[code] = name
        tables[decoder] = names
    return tables


def format_example_result(result, note: str | None) -> str:
    def rnd(v):
        if isinstance(v, float):
            return round(v, 4)
        if isinstance(v, list):
            return [rnd(x) for x in v]
        return v
    text = json.dumps(rnd(result))
    return f"# -> {text}" + (f"  {note}" if note else "")


# --- Python package ------------------------------------------------------------------------------

def _relation_text(rel: dict) -> str:
    product = " * ".join(rel["factors"]) + (f" + {rel['plus']}" if rel.get("plus") else "")
    lists = ", ".join(rel["bounds"])
    if rel.get("scope") == "length":
        return f"len({lists}) >= {product}" if len(rel["bounds"]) == 1 else f"len(each of {lists}) >= {product}"
    return f"each element of {lists} has at least {product} entries"


def render_module(module: str, spec: dict, depth: int) -> str:
    dots = "." * (depth + 1)
    lines = [f'"""{module} — {spec["description"] or "Algenta compute kernels"}. Compiled Mojo, called in-process."""', "from __future__ import annotations", "",
             f"from {dots}_transport import KERNEL_DEFAULT as _DEFAULT, call as _call", "", ""]
    names = []
    for fname, f in sorted(spec["functions"].items()):
        params = f["params"]
        sig, doc_args = [], []
        for p in params:
            hint = py_type(p["type"])
            if p["has_default"]:
                sig.append(f"{ident(p['name'])}: {hint} = {p['default']!r}" if "default" in p else f"{ident(p['name'])}: {hint} = _DEFAULT")
            else:
                sig.append(f"{ident(p['name'])}: {hint}")
            extra = []
            if p.get("doc"):
                extra.append(p["doc"])
            struct = spec["structs"].get(p["type"]) or spec["structs"].get(p["type"][5:-1] if p["type"].startswith("List[") else "")
            if struct:
                extra.append(("each a dict with keys " if p["type"].startswith("List[") else "dict with keys ") + ", ".join(fl["name"] for fl in struct["fields"]))
            if p["is_mut"]:
                extra.append("updated in place")
            doc_args.append(f"    {p['name']} ({hint})" + (": " + " ".join(extra) if extra else ""))
        ret = py_type(f["return_type"])
        ret_struct = spec["structs"].get(f["return_type"])
        returns = []
        if ret_struct:
            returns.append("dict with keys " + ", ".join(fl["name"] for fl in ret_struct["fields"]))
        if f.get("returns_doc"):
            returns.append(f["returns_doc"])
        doc = [f["doc"] or f"{module}.{fname}."]
        if doc_args:
            doc += ["", "Args:"] + doc_args
        if returns:
            doc += ["", "Returns:", "    " + " ".join(returns)]
        if f["count_relations"]:
            doc += ["", "Requires: " + "; ".join(_relation_text(r) for r in f["count_relations"]) + "."]
        mutable = [p["name"] for p in params if p["is_mut"]]
        if mutable:
            doc += ["", "Updates " + ", ".join(f"`{n}`" for n in mutable) + " in place; pass a list" + (" or dict" if any(spec["structs"].get(p["type"]) for p in params if p["is_mut"]) else "") + "."]
        arg_names = [ident(p["name"]) for p in params]
        body = [f"    args = [{', '.join(arg_names)}]"]
        if any(p["has_default"] and "default" not in p for p in params):
            body += ["    while args and args[-1] is _DEFAULT:", "        args.pop()"]
        if mutable:
            body.append(f"    return _call({module!r}, {fname!r}, args, in_place={{{', '.join(f'{n!r}: {ident(n)}' for n in mutable)}}})")
        else:
            body.append(f"    return _call({module!r}, {fname!r}, args)")
        docstring = "\n".join(doc).replace("\\", "\\\\").replace('"""', "'''")
        lines += [f"def {ident(fname)}({', '.join(sig)}) -> {ret}:", f'    """{docstring}', '    """', *body, "", ""]
        names.append(ident(fname))
    lines += [f"__all__ = {names!r}", ""]
    return "\n".join(lines)


def render_namespace(path: str, children: list[str], family_pkg: str) -> str:
    names = sorted(ident(c) for c in children)
    return "\n".join([f'"""{family_pkg}.{path} — {", ".join(names)}."""', *(f"from . import {n}" for n in names), "", f"__all__ = {names!r}", ""])


def render_init(family_pkg: str, modules: list[str], has_session: bool, excluded: set[str]) -> str:
    tops = sorted({m.split(".")[0] for m in modules})
    lines = [f'"""{family_pkg} — Algenta compute kernels, loaded in-process. See README.md."""', "from __future__ import annotations", "",
             "from ._native import KernelError, NativeUnavailable", "from ._contract import CONTRACT", "from . import _transport",
             "from . import " + ", ".join(ident(t) for t in tops)]
    if has_session:
        lines.append("from .session import DecodeSession, decode")
    lines += ["", "",
              "def execute(module: str, function: str, args: list | dict | None = None):",
              '    """Call any function of this kernel by name.',
              "",
              "    `module` is the dotted module name (`\"forecasting.interval\"`), `args` a list in signature order,",
              "    a dict of parameter names, or None for a function without parameters. Arguments are validated",
              "    against `CONTRACT` before the call; an invalid call raises `KernelError` with a stable `code`.",
              "    Returns the result. A function that updates one of its arguments returns",
              '    `{"result": ..., "mutated_args": {name: new_value}}` here; the module wrappers apply the update in place instead.',
              '    """',
              "    return _transport.call(module, function, args)",
              "", ""]
    exported = ["KernelError", "NativeUnavailable", "CONTRACT", "execute", "modules", "excluded_functions"] + (["DecodeSession", "decode"] if has_session else []) + [ident(t) for t in tops]
    lines += [f"modules = {sorted(modules)!r}", f"excluded_functions = {sorted(excluded)!r}", "", f"__all__ = {sorted(set(exported))!r}", ""]
    return "\n".join(lines)


def write_package_tree(pdir: Path, modules: list[str], contract: dict, family_pkg: str) -> None:
    """One file per module, mirroring the dotted names as real subpackages."""
    children: dict[str, set[str]] = {}
    for m in modules:
        parts = m.split(".")
        for i in range(1, len(parts)):
            children.setdefault(".".join(parts[:i]), set()).add(parts[i])
    for m in modules:
        parts = m.split(".")
        target = pdir.joinpath(*[ident(p) for p in parts[:-1]], ident(parts[-1]) + ".py")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(render_module(m, contract["modules"][m], len(parts) - 1))
    for path, kids in children.items():
        (pdir.joinpath(*[ident(p) for p in path.split(".")]) / "__init__.py").write_text(render_namespace(path, sorted(kids), family_pkg))


# --- card ----------------------------------------------------------------------------------------

def render_card(family: str, summary: str, modules: list[str], contract: dict, variants: dict[str, list[str]], excluded: set[str], backends: list[str], has_session: bool, example_line: str | None, has_status: bool, exclusion_reasons: dict[str, str], stage_tiers: dict[str, int] | None = None) -> str:
    fn_count = sum(len(m["functions"]) for m in contract["modules"].values())
    rows = "\n".join(f"| `{m}` | {len(contract['modules'][m]['functions'])} | {contract['modules'][m]['description']} |" for m in sorted(modules))
    torch_versions = sorted({re.match(r"torch(\d)(\d+)", v).groups() for names in variants.values() for v in names}, key=lambda t: (int(t[0]), int(t[1])))
    torch_range = f"PyTorch {torch_versions[0][0]}.{torch_versions[0][1]} to {torch_versions[-1][0]}.{torch_versions[-1][1]}" if torch_versions else "PyTorch"
    all_variants = [v for names in variants.values() for v in names]
    darwin = any(v.endswith("-aarch64-darwin") for v in all_variants)
    linux_arches = sorted({v.rsplit("-", 2)[1] for v in all_variants if v.endswith("-linux")})
    req_lines = []
    if darwin:
        req_lines.append("- Apple silicon: macOS 15 or later for the CPU build" + (", macOS 26 or later for Metal." if "metal" in variants else "."))
    if linux_arches:
        arch_words = " and ".join({"x86_64": "x86-64", "aarch64": "arm64"}.get(x, x) for x in linux_arches)
        req_lines.append(f"- Linux {arch_words}, glibc 2.35 or later.")
    if "cuda" in variants:
        req_lines.append("- NVIDIA: driver 580 or later; the build carries kernels for T4 (sm_75), A100 (sm_80), L4 (sm_89) and H100/H200 (sm_90) and picks the one matching your GPU.")
    req_lines.append(f"- `kernels` 0.17 or later and {torch_range}. PyTorch has to be installed: the loader picks the build for your PyTorch version. The kernel itself never imports it.")
    req_lines = [textwrap.fill(line, width=100, subsequent_indent="  ") for line in req_lines]
    metal = "metal" in backends
    cuda = "cuda" in backends
    backend_arg = "" if (metal or cuda) else '    backend="cpu",\n'
    backend_note = (("On macOS 26 the loader picks the Metal build. On macOS 15, add `backend=\"cpu\"`." if metal else "")
                    + (" On a Linux host with an NVIDIA GPU and a CUDA build of PyTorch the loader picks the CUDA build." if cuda else "")
                    if (metal or cuda) else "`backend=\"cpu\"` selects the CPU build. On a Mac the loader otherwise looks for a Metal build, which this family does not ship.")
    example = example_line or 'kernel.execute("<module>", "<function>", [...])'
    first_dotted = next((m for m in sorted(modules) if "." in m), None)
    escape_hatch_target = first_dotted or sorted(modules)[0]
    escape_fn = sorted(contract["modules"][escape_hatch_target]["functions"])[0]
    status_sentence = (" Engine kernels report shape and finiteness problems as a `status`; the wrapper raises `KernelError` named after it." if has_status else "")
    session_block = ""
    if has_session:
        session_block = """
## Resident decode

The Metal and CUDA builds run greedy Qwen3-family decode on the GPU. One session is open at a time;
each step blocks until its token is computed and returns the token id.

```python
with kernel.DecodeSession("/path/to/converted-checkpoint", prompt_token_ids, max_new_tokens=32) as session:
    tokens = list(session)
```

`prompt_token_ids` come from the checkpoint's own tokenizer. The checkpoint directory is the
converted form (`manifest.json` + `weights.blob`) written by `prepare_model_checkpoint()` in the
`algenta` package. `kernel.decode(...)` runs a whole session in one call; `session.step()` returns
the full record for one token. Decode needs a GPU build; on the CPU build `DecodeSession` raises
`KernelError("gpu_build_required")`.
"""
        if stage_tiers:
            staged = textwrap.fill(stage_tier_sentence(stage_tiers), width=100,
                                   break_on_hyphens=False, break_long_words=False)
            session_block += "\n" + staged + "\n"
    excluded_block = ""
    if excluded:
        # One bullet per excluded function, wrapped at 100 columns with a hanging indent so the card
        # stays readable in a terminal (the package test enforces <= 110 characters per prose line).
        excluded_block = "\n## Not included\n\n" + "\n".join(
            textwrap.fill(f"`{e}` \u2014 {exclusion_reasons.get(e, 'served by the Algenta runtime, not this in-process build')}.",
                          width=100, initial_indent="- ", subsequent_indent="  ", break_on_hyphens=False, break_long_words=False)
            for e in sorted(excluded)) + "\n"
    backend_word = " · ".join(b.upper() if b == "cpu" else b.capitalize() for b in backends)
    wrap = lambda text: textwrap.fill(" ".join(text.split()), width=100)  # noqa: E731
    intro = wrap(f"{backend_note} `trust_remote_code` names the repositories you allow; Hugging Face's trusted publishers load without it.")
    contract_paragraph = wrap("Plain Python in, plain Python out. Lists, tuples, buffers and tensors are accepted wherever the contract expects a list; structured results are dictionaries. Some functions take a list and the number of elements to use from it, which may not exceed the list's length; multi-dimensional data is passed flattened, row-major, with its dimensions. Functions that update an argument do so in place, as `help()` says. Every call is checked against the published contract before it reaches native code. An invalid call raises `KernelError` with a stable `code`, never a crash." + status_sentence)
    escape_paragraph = f'Any function can also be called by name, with `args` as a list or a dict of parameter names:\n\n```python\nkernel.execute("{escape_hatch_target}", "{escape_fn}", [...])\n```'
    help_target = next((m for m in sorted(modules) if "." not in m), sorted(modules)[0].split(".")[0])
    missing = [w for w, present in (("Linux x86-64", "x86_64" in linux_arches), ("Linux arm64", "aarch64" in linux_arches), ("macOS", darwin)) if not present]
    platform_note = ("Windows is not supported." if not missing else ", ".join(missing) + (" builds follow" if len(missing) > 1 else " builds follow") + " from the same source. Windows is not supported.")
    headline = wrap(f"{summary}. Compiled Mojo, loaded in-process.")
    # the licence version comes from LICENSE itself, so an approved bump propagates on the next publish
    _version_line = re.search(r"^Version (\d+\.\d+)", (ROOT / "LICENSE").read_text(encoding="utf-8-sig"), re.M)
    if not _version_line:
        raise SystemExit("LICENSE has no 'Version X.Y' line: the card's license_name cannot be derived; refusing to generate")
    license_version = _version_line.group(1)
    return f"""---
library_name: kernels
license: other
license_name: algenta-community-license-{license_version}
license_link: LICENSE
tags:
- algenta
- mojo
{chr(10).join(f"- {b}" for b in backends)}
---

# {family}

{headline}

**{len(modules)} modules · {fn_count} functions · {backend_word}**

## Get started

```bash
pip install kernels torch
```

```python
from kernels import get_kernel

kernel = get_kernel(
    "thyn-ai/{family}",
    version=1,
{backend_arg}    trust_remote_code=["thyn-ai/{family}"],
)
{example}
```

{intro}

{contract_paragraph}

{escape_paragraph}
{session_block}
## What's inside

| Module | Functions | What it does |
|---|---:|---|
{rows}

`kernel.CONTRACT` holds every signature, including the length rules for list arguments;
`help(kernel.{ident(help_target)})` documents each function.
{excluded_block}
## Requirements

{chr(10).join(req_lines)}

{platform_note}

## Notes

Calls into one kernel instance run one at a time; use processes for parallelism. Runtime state
does not survive `fork()`; start worker processes with `spawn`.

## License

Algenta Community License {license_version} (`LICENSE`). Free for personal, research and open-source use, and
for internal use at organizations with fewer than 50 employees and under $5M in annual revenue.
Beyond that, a commercial license is required: https://algenta.ai/pricing.

Enforced in the compiled library, not just in this text: **one concurrent native worker per
device** (ABI §9). A second process, family or thread waits its turn rather than running in
parallel. That is the Community licence's worker floor made real; parallel execution comes with a
commercial license.

## Support

Generally Available on the platforms listed under Requirements. Within `v1`, functions are only added;
removals or signature changes ship as `v2`. Platforms, accelerators and PyTorch releases not listed are not
supported. Documentation: https://docs.algenta.ai (the kernels guide:
https://docs.algenta.ai/guides/kernels-on-hugging-face). Community: https://discord.gg/w8NDsph9an or this
repository's Community tab. Commercial licences and support: https://algenta.ai/pricing.
"""


# --- main ----------------------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--family", required=True)
    ap.add_argument("--native", action="append", required=True, help="<backend>=<staged _native dir>")
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--filters", type=Path, default=ROOT / "scripts" / "hf_kernel_filters.json")
    ap.add_argument("--torch-versions", nargs="*", default=DEFAULT_TORCH_VERSIONS)
    ap.add_argument("--kernel-version", type=int, default=1)
    a = ap.parse_args()

    filters = json.loads(a.filters.read_text())["filters"]
    if a.family not in filters:
        raise SystemExit(f"unknown family {a.family}")
    fam = filters[a.family]
    modules = fam["modules"]
    excluded = set(fam.get("excluded_functions", []))
    pkg = a.family.replace("-", "_")
    natives: list[tuple[str, Path]] = []  # (backend, staged closure); several platforms per backend are normal
    for spec in a.native:
        backend, _, path = spec.partition("=")
        natives.append((backend, Path(path)))
    backends_present = sorted({b for b, _ in natives})
    contract = build_contract(modules, excluded, fam.get("module_descriptions", {}))
    missing = [m for m in modules if not contract["modules"][m]["description"]]
    if missing:
        raise SystemExit(f"modules without a card description: {missing}")
    has_session = "qwen3_decode_open" in fam.get("request_types", [])

    host = f"{'aarch64' if platform.machine() in ('arm64', 'aarch64') else 'x86_64'}-{'darwin' if sys.platform == 'darwin' else 'linux'}"
    loadable = [(b, n) for b, n in natives if json.loads((n / "manifest.json").read_text()).get("platform") == host]
    probe_native = next((n for b, n in loadable if b == "cpu"), None) or (loadable[0][1] if loadable else None)
    if probe_native is None:
        raise SystemExit(f"no staged closure for this host ({host}); the generator runs the card example and reads the status vocabularies through a loadable build")
    probe = _NativeProbe(probe_native)
    try:
        contract["status_names"] = status_tables(probe, contract)
        example_line = None
        if fam.get("card_example"):
            module, function, args = fam["card_example"]
            reply = probe.call(module, function, args)
            if "result" in reply and not (isinstance(reply["result"], dict) and reply["result"].get("__algenta_struct")):
                example_line = f"kernel.{module}.{function}({', '.join(json.dumps(x) for x in args)})  {format_example_result(reply['result'], fam.get('card_example_note'))}"
            else:
                raise SystemExit(f"card example did not produce a plain result: {reply}")
    finally:
        probe.close()
    has_status = any("status_decoder" in m for m in contract["modules"].values())

    out = a.out
    if (out / "build").exists():
        shutil.rmtree(out / "build")
    variants_written: dict[str, list[str]] = {}
    stage_tiers: dict[str, int] = {}
    for backend, native in natives:
        manifest = json.loads((native / "manifest.json").read_text())
        if manifest["backend"] != backend:
            raise SystemExit(f"{native} was built for backend {manifest['backend']}, not {backend}")
        tier = stage_tier_of(manifest)
        if tier is not None:
            if stage_tiers.get(backend, tier) != tier:
                raise SystemExit(
                    f"{backend} closures disagree on resident_stage_tier ({stage_tiers[backend]} vs "
                    f"{tier} in {native}); one tier per backend per release"
                )
            stage_tiers[backend] = tier
        public_manifest = {k: manifest[k] for k in PUBLIC_MANIFEST_KEYS if k in manifest}
        if public_manifest.get("resident_stage_tier") is None:
            public_manifest.pop("resident_stage_tier", None)  # CPU closure: no resident decode
        names = variant_names(manifest["platform"], backend, a.torch_versions)
        variants_written.setdefault(backend, []).extend(names)
        for vname in names:
            vdir = out / "build" / vname
            pdir = vdir / pkg
            pdir.mkdir(parents=True)
            (pdir / "_native").mkdir()
            for f in sorted(native.iterdir()):
                if f.is_file() and f.name != "manifest.json":
                    shutil.copy2(f, pdir / "_native" / f.name)
            (pdir / "_native" / "manifest.json").write_text(json.dumps(public_manifest, indent=2) + "\n")
            (pdir / "_native.py").write_text((TEMPLATES / "_native.py").read_text().replace("__LIBRARY_NAME__", manifest["library"]).replace("__FAMILY__", a.family).replace("__BACKEND__", backend))
            (pdir / "_transport.py").write_text((TEMPLATES / "_transport.py").read_text())
            (pdir / "_contract.py").write_text('"""Published contract for this kernel (generated): every module, function, parameter, default,\nstruct, length rule and engine status vocabulary."""\nCONTRACT = ' + pprint.pformat(contract, width=110, sort_dicts=True) + "\n")
            write_package_tree(pdir, modules, contract, pkg)
            if has_session:
                (pdir / "session.py").write_text((TEMPLATES / "session.py").read_text())
            (pdir / "__init__.py").write_text(render_init(pkg, modules, has_session, excluded))
            (vdir / "__init__.py").write_text(f'"""{a.family} ({vname})."""\nfrom .{pkg} import *  # noqa: F401,F403\nfrom .{pkg} import __all__  # noqa: F401\n')
            metadata = {
                "name": a.family,
                "id": f"_{pkg}_{backend}_{manifest['source_commit'][:7]}",
                "version": a.kernel_version,
                "license": "other",
                "python-depends": [],
                "kernel-depends": [],
                "backend": backend_metadata(backend, manifest),
            }
            metadata["digest"] = digest_dir(vdir)
            (vdir / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    (out / "README.md").write_text(render_card(a.family, fam["summary"], modules, contract, variants_written, excluded, backends_present, has_session, example_line, has_status, fam.get("exclusion_reasons", {}), stage_tiers))
    shutil.copy2(ROOT / "LICENSE", out / "LICENSE")
    (out / ".gitattributes").write_text("*.dylib filter=lfs diff=lfs merge=lfs -text\n*.so filter=lfs diff=lfs merge=lfs -text\n")
    total = sum(p.stat().st_size for p in (out / "build").rglob("*") if p.is_file())
    print(f"{a.family}: {len(modules)} modules, {sum(len(m['functions']) for m in contract['modules'].values())} functions; variants {sum(len(v) for v in variants_written.values())} ({', '.join(f'{b}:{len(v)}' for b, v in variants_written.items())}); build/ = {total/1e6:.1f} MB -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
