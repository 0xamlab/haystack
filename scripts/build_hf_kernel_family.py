#!/usr/bin/env python3
"""Build one Algenta HF-kernel family: a self-contained in-process shared library.

Pipeline (all additive, the frozen engine is only read):
  1. filtered dispatch  -> scripts/generate_runtime_library_dispatch.py --modules ...
  2. count-relation guard -> scripts/hf_kernels/generate_abi_guard.py --modules ...
  3. stage mojo/hfkernel/abi.mojo beside them (sibling resolution, as the shard builder does)
  4. scripts/shadow_max_pkg_name_collisions.sh on the pixi lib dir (same reason as the worker build)
  5. `mojo build -I mojo/engine <stage>/abi.mojo --emit shared-lib` with an explicit deployment
     target (CPU floor: macOS 15.0) and, on Linux x86-64, --mcpu x86-64-v3
  6. stage the library + its non-system dylib closure into <out>/_native with @loader_path/$ORIGIN
     rpaths (reusing scripts/stage_runtime_worker_package.py), delete any absolute LC_RPATH, strip
  7. verify: exports == the five ABI symbols, every dependency resolves inside <out>/_native
  8. write <out>/_native/manifest.json (family, modules, toolchain, platform, sha256 per file, source commit)

Usage:
  scripts/build_hf_kernel_family.py --family algenta-stats --out build_out/algenta-stats
  scripts/build_hf_kernel_family.py --modules stats ab_testing --name stats-spike --out /tmp/x
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from stage_runtime_worker_package import (  # noqa: E402
    StageError,
    _is_relative_to,
    linked_dependencies,
    relink_artifacts,
)

ABI_EXPORTS = {
    "algenta_runtime_version",
    "algenta_runtime_init",
    "algenta_runtime_execute",
    "algenta_runtime_free",
    "algenta_runtime_shutdown",
}
CPU_MACOS_DEPLOYMENT_TARGET = "15.0"
METAL_MACOS_DEPLOYMENT_TARGET = "26.0"


def _run(cmd: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None) -> str:
    proc = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout[-4000:] + proc.stderr[-4000:])
        raise SystemExit(f"command failed ({proc.returncode}): {' '.join(cmd)}")
    return proc.stdout


def _platform() -> tuple[str, str]:
    system = platform.system().lower()
    machine = platform.machine()
    arch = {"arm64": "aarch64", "AMD64": "x86_64"}.get(machine, machine)
    if system == "darwin":
        return "darwin", f"{arch}-darwin"
    if system == "linux":
        return "linux", f"{arch}-linux"
    raise SystemExit(f"unsupported host platform: {system} {machine}")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _exports(lib: Path, system: str) -> set[str]:
    if system == "darwin":
        out = _run(["nm", "-gU", str(lib)])
        return {line.split()[-1].lstrip("_") for line in out.splitlines() if " T " in line}
    out = _run(["nm", "-D", "--defined-only", str(lib)])
    return {line.split()[-1] for line in out.splitlines() if " T " in line}


def _collect_closure(lib: Path, lib_root: Path, out_dir: Path, system: str) -> list[Path]:
    """Copy `lib` and every linked non-system dependency from `lib_root` into `out_dir`.

    Same policy as stage_runtime_worker_package.collect_runtime_closure (dependencies outside
    `lib_root` are refused), but tolerant of a dylib's own install-name line, which `otool -L`
    prints for libraries and never for the worker executable that helper was written for.
    """
    dest = out_dir / lib.name
    shutil.copy2(lib, dest)
    dest.chmod(0o755)
    artifacts = [dest]
    seen = {lib.resolve()}
    queue = [lib.resolve()]
    while queue:
        current = queue.pop()
        for dep in linked_dependencies(current, system, search_roots=(current.parent, lib_root, out_dir)):
            resolved = dep.resolve()
            if resolved in seen or _is_relative_to(resolved, out_dir):
                continue
            if not _is_relative_to(resolved, lib_root):
                raise StageError(f"runtime dependency {resolved} is outside the library root {lib_root}")
            seen.add(resolved)
            # Copy under the name the loader will ask for (`dep.name`, e.g. libc++.1.dylib), not the
            # symlink target's real name (libc++.1.0.dylib); a Hub repo cannot carry symlinks.
            copy = out_dir / dep.name
            shutil.copy2(resolved, copy)
            copy.chmod(0o755)
            artifacts.append(copy)
            queue.append(resolved)
    return artifacts



def _tagged_name(name: str, tag: str) -> str:
    """Insert the toolchain tag before the shared-library suffix, keeping versioned Linux suffix chains:
    libX.dylib -> libX.<tag>.dylib; libX.so.1.0.0 -> libX.<tag>.so.1.0.0 (not libX.so.1.0.<tag>.0)."""
    for ext in (".dylib", ".so"):
        i = name.find(ext)
        if i != -1:
            return f"{name[:i]}.{tag}{name[i:]}"
    if "." not in name:
        return f"{name}.{tag}"
    stem, _, ext = name.rpartition(".")
    return f"{stem}.{tag}.{ext}"

def _absolute_rpaths(lib: Path) -> list[str]:
    out = _run(["otool", "-l", str(lib)])
    paths, grab = [], False
    for line in out.splitlines():
        if "LC_RPATH" in line:
            grab = True
        elif grab and "path " in line:
            paths.append(line.split("path ", 1)[1].split(" (offset")[0].strip())
            grab = False
    return [p for p in paths if p.startswith("/")]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--family", help="filter name from scripts/hf_kernel_filters.json")
    src.add_argument("--modules", nargs="+", help="ad-hoc module list (spikes)")
    ap.add_argument("--name", help="artifact name when --modules is used (default: joined)")
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--filters", type=Path, default=ROOT / "scripts" / "hf_kernel_filters.json")
    ap.add_argument("--backend", choices=["cpu", "metal", "cuda"], default="cpu")
    ap.add_argument("--stub-guard", action="store_true", help="TEST ONLY: build without the count-relation guard")
    ap.add_argument("--exclude", nargs="*", default=None, help="module.function or module.* refused in-process (ad hoc; families read excluded_functions from the filter table)")
    ap.add_argument("--request-types", nargs="*", default=None, help="ad-hoc declared routes (families read request_types from the filter table)")
    ap.add_argument("--keep-stage", action="store_true")
    a = ap.parse_args()

    if a.family:
        filters = json.loads(a.filters.read_text())["filters"]
        if a.family not in filters:
            raise SystemExit(f"unknown family {a.family}; known: {sorted(filters)}")
        modules = filters[a.family]["modules"]
        name = a.family
        request_types = filters[a.family].get("request_types", ["library_execute"])
        excluded = filters[a.family].get("excluded_functions", [])
    else:
        modules = a.modules
        name = a.name or "-".join(a.modules)[:60]
        request_types = a.request_types or ["library_execute"]
        excluded = a.exclude or []
    if a.backend == "cuda":
        raise SystemExit("--backend cuda is Stage 6 work (cross-compile on Linux); not implemented in this revision")

    system, plat = _platform()
    pixi_env = (ROOT / "mojo_env" / ".pixi" / "envs" / "default").resolve()
    lib_root = pixi_env / "lib"
    if not lib_root.is_dir():
        raise SystemExit(f"pixi env missing: {lib_root} (run `cd mojo_env && pixi install`)")
    ext = ".dylib" if system == "darwin" else ".so"
    lib_name = f"libalgenta_{name.replace('-', '_')}{ext}"

    stage = Path(tempfile.mkdtemp(prefix=f".hfk-{name}-", dir=str(a.out.parent if a.out.parent.exists() else "/tmp")))
    try:
        _run([sys.executable, str(ROOT / "scripts" / "generate_runtime_library_dispatch.py"),
              "--output", str(stage / "runtime_library_dispatch_generated.mojo"), "--modules", *modules])
        guard_cmd = [sys.executable, str(ROOT / "scripts" / "hf_kernels" / "generate_abi_guard.py"),
                     "--modules", *modules, "--output", str(stage / "hf_abi_guard_generated.mojo")]
        if a.stub_guard:
            guard_cmd.append("--stub")
        if excluded:
            guard_cmd += ["--exclude", *excluded]
        guard_report = _run(guard_cmd).strip()
        router_report = _run([sys.executable, str(ROOT / "scripts" / "hf_kernels" / "generate_abi_router.py"),
                              "--request-types", *request_types, "--output", str(stage / "hf_abi_router_generated.mojo")]).strip()
        shutil.copy2(ROOT / "mojo" / "hfkernel" / "abi.mojo", stage / "abi.mojo")
        _run(["bash", str(ROOT / "scripts" / "shadow_max_pkg_name_collisions.sh"), str(lib_root)])

        env = os.environ.copy()
        deployment_target = METAL_MACOS_DEPLOYMENT_TARGET if a.backend == "metal" else CPU_MACOS_DEPLOYMENT_TARGET
        env["MACOSX_DEPLOYMENT_TARGET"] = deployment_target
        mojo_version = _run(["pixi", "run", "mojo", "--version"], cwd=ROOT / "mojo_env").strip().splitlines()[0]
        if a.backend == "cpu":
            build = ["pixi", "run", "mojo", "build", "-I", str(ROOT / "mojo" / "engine"), str(stage / "abi.mojo"),
                     "--emit", "shared-lib", "-o", str(stage / lib_name)]
            if system == "linux" and plat.startswith("x86_64"):
                build[5:5] = ["--mcpu", "x86-64-v3"]
            _run(build, cwd=ROOT / "mojo_env", env=env)
        else:  # metal: the worker recipe (build_mojo_binary.sh) — object emit, ObjC shim, clang link
            if system != "darwin":
                raise SystemExit("--backend metal needs a macOS arm64 host")
            xcode = next(iter(sorted(Path("/Applications").glob("Xcode*.app"))), None)
            if xcode is None:
                raise SystemExit("Xcode (with the Metal toolchain) is required for --backend metal")
            env["DEVELOPER_DIR"] = str(xcode / "Contents" / "Developer")
            sdk = _run(["xcrun", "--show-sdk-path"], env=env).strip()
            clang = _run(["xcrun", "--find", "clang"], env=env).strip()
            shim_src = ROOT / "benchmarks" / "llm_smoke" / "metal_batch_dispatch" / "batch_shim.m"
            _run([clang, "-c", "-fobjc-arc", "-O2", "-isysroot", sdk, str(shim_src), "-o", str(stage / "metal_batch_shim.o")], env=env)
            # Prefill/GEMM/attention pipelines live in prebuilt Metal blobs (mma_forge + attention_forge
            # generated C), the same set scripts/build_metal_beat_workers.sh links into the shipped
            # Metal worker; the i8kv pair is excluded there for determinism and is excluded here too.
            exclude_blobs = {"kv_i8_quant_blob.c", "native_kv_decode_attn_splitk_i8kv_blob.c"}
            blob_dir = stage / "blobs"
            blob_dir.mkdir()
            blob_objects: list[Path] = []
            for src in sorted([*(ROOT / "mma_forge" / "generated").glob("*.c"), *(ROOT / "attention_forge" / "generated").glob("*.c")]):
                if src.name in exclude_blobs:
                    continue
                obj = blob_dir / (src.stem + ".o")
                _run([clang, "-c", "-O2", "-isysroot", sdk, str(src), "-o", str(obj)], env=env)
                blob_objects.append(obj)
            target = os.environ.get("MOJO_BUILD_METAL_TARGET", "apple-m1")
            _run(["pixi", "run", "mojo", "build", "-I", str(ROOT / "mojo" / "engine"), str(stage / "abi.mojo"), "--emit", "object",
                  "-D", "ALGENTA_GPU", "-D", "ALGENTA_METAL", "--target-accelerator", target, "-o", str(stage / "abi.o")],
                 cwd=ROOT / "mojo_env", env=env)
            rt_libs = [f"-l{n}" for n in ("KGENCompilerRTShared", "AsyncRTRuntimeGlobals", "MSupportGlobals", "AsyncRTMojoBindings")
                       if list(lib_root.glob(f"lib{n}.*"))]
            # Only the five ABI symbols are public: the ObjC shim's C entry points resolve inside the
            # dylib at link time and must not widen the export set (ABI.md §1).
            exported = [f"-Wl,-exported_symbol,_{sym}" for sym in sorted(ABI_EXPORTS)]
            _run([clang, "-dynamiclib", str(stage / "abi.o"), str(stage / "metal_batch_shim.o"), *map(str, blob_objects), "-o", str(stage / lib_name),
                  "-isysroot", sdk, "-L", str(lib_root), *rt_libs, "-lc++",
                  "-framework", "Metal", "-framework", "Foundation", "-framework", "IOKit",
                  *exported, "-Wl,-rpath," + str(lib_root), "-install_name", f"@loader_path/{lib_name}"], env=env)

        # Artifact-level inclusion evidence for the GPU engine kernels (plan v3: inventoried ->
        # included in artifact). Read from the UNSTRIPPED library: the private kernel symbols are
        # stripped from the shipped file. Substring match on the inventoried kernel names.
        kernels_included: list[str] = []
        embedded_pipelines = 0
        blob_names = [b.stem for b in blob_objects] if a.backend == "metal" else []
        floor_path = ROOT / "scripts" / "engine_kernel_floor.json"
        if a.backend != "cpu" and floor_path.is_file():
            floor = json.loads(floor_path.read_text())["kernels"]
            # Mojo GPU kernels appear in the binary as mangled markers of the form
            # `<module with . -> _>__<kernel name>` (e.g. residentk_kernels__argmax_reduce_kernel).
            raw_bytes = (stage / lib_name).read_bytes()
            blob = subprocess.run(["strings", "-", str(stage / lib_name)], capture_output=True).stdout.decode("utf-8", "ignore")
            # The compiler truncates the kernel name to its first 11 characters inside the marker
            # (`residentk_kernels__argmax_redu6A6A6A6A_<hash>`), so siblings sharing a prefix
            # cannot be told apart here: this is prefix-level inclusion evidence, reported as such.
            markers = sorted({(k["module"].replace(".", "_") + "__" + k["name"][:11], k["module"] + "." + k["name"]) for k in floor if k["backend"] == a.backend})
            kernels_included = [full for marker, full in markers if marker in blob]
            embedded_pipelines = raw_bytes.count(b"MTLB")
        native = a.out / "_native"
        if native.exists():
            shutil.rmtree(native)
        native.mkdir(parents=True)
        artifacts = _collect_closure(stage / lib_name, lib_root, native, system)
        relink_artifacts(tuple(artifacts), lib_root, native, system)
        own = native / lib_name
        # Dependency-first load order for the Python loader: the Hub cache materialises every file as a
        # symlink into blobs/, and dyld resolves @loader_path from the blob's REAL directory, where the
        # siblings are not. The loader therefore dlopens each runtime dylib by real path first; dyld then
        # satisfies the main library's `@rpath/<name>` needs from the already-loaded image whose install
        # name is exactly `@rpath/<name>` (measured: fails with @loader_path ids, works with @rpath ids).
        # Runtime dylibs are renamed with the toolchain tag (libKGENCompilerRTShared.dylib ->
        # libKGENCompilerRTShared.mojo1_0_0.dylib) so that, with @rpath install names, families built
        # from the SAME pinned toolchain share one loaded runtime copy in a process while families
        # built from different toolchains can never satisfy each other's dependencies by accident.
        tag = "mojo" + re.sub(r"[^0-9A-Za-z]+", "_", mojo_version.split()[1]) if len(mojo_version.split()) > 1 else "mojo"
        renamed: dict[str, str] = {}
        for art in list(artifacts):
            if art.name != lib_name:
                new_name = _tagged_name(art.name, tag)
                art.rename(art.parent / new_name)
                renamed[art.name] = new_name
        artifacts = [a.parent / renamed.get(a.name, a.name) for a in artifacts]
        if system == "darwin":
            for art in artifacts:
                for old_name, new_name in renamed.items():
                    for prefix in ("@loader_path/", "@rpath/"):
                        _run(["install_name_tool", "-change", f"{prefix}{old_name}", f"@rpath/{new_name}", str(art)])
        elif system == "linux":
            # The ELF analogue: the renamed runtime objects get their new name as SONAME, every artifact's
            # DT_NEEDED entries follow the rename, and RUNPATH is $ORIGIN so the closure resolves in place.
            if shutil.which("patchelf") is None:
                raise SystemExit("patchelf is required to retag the Linux runtime closure (apt-get install patchelf)")
            for art in artifacts:
                if art.name in renamed.values():
                    _run(["patchelf", "--set-soname", art.name, str(art)])
                for old_name, new_name in renamed.items():
                    _run(["patchelf", "--replace-needed", old_name, new_name, str(art)])
                _run(["patchelf", "--set-rpath", "$ORIGIN", str(art)])
        closure_names = {art.name for art in artifacts}
        deps_of: dict[str, set[str]] = {}
        for art in artifacts:
            deps_of[art.name] = {d.name for d in linked_dependencies(art, system, search_roots=(native,)) if d.name in closure_names and d.name != art.name}
        load_order: list[str] = []
        remaining = {n for n in closure_names if n != lib_name}
        while remaining:
            ready = sorted(n for n in remaining if not (deps_of.get(n, set()) & remaining))
            if not ready:
                ready = sorted(remaining)  # cycle: fall back to name order
            load_order += ready
            remaining -= set(ready)
        if system == "darwin":
            for art in artifacts:
                for rp in _absolute_rpaths(art):
                    _run(["install_name_tool", "-delete_rpath", rp, str(art)])
                if art.name != lib_name:
                    _run(["install_name_tool", "-id", f"@rpath/{art.name}", str(art)])
                for dep in closure_names:
                    if dep != art.name:
                        _run(["install_name_tool", "-change", f"@loader_path/{dep}", f"@rpath/{dep}", str(art)])
            # Strip only our own library; the Modular runtime dylibs ship as-is.
            _run(["strip", "-x", str(own)])
            # install_name_tool/strip invalidate the plain ad-hoc signatures of the copied Modular
            # dylibs (only linker-signed files re-sign themselves); on Apple silicon dyld then
            # kills the loading process (exit 137). Re-sign every artifact ad hoc, then verify.
            for art in artifacts:
                _run(["codesign", "--force", "--sign", "-", str(art)])
            for art in artifacts:
                _run(["codesign", "--verify", "--verbose=1", str(art)])
        else:
            _run(["strip", "--strip-unneeded", str(own)])

        lib_path = native / lib_name
        exports = _exports(lib_path, system)
        if exports != ABI_EXPORTS:
            raise SystemExit(f"export set mismatch: {sorted(exports)}")
        if system == "darwin":
            leftovers = [rp for art in artifacts for rp in _absolute_rpaths(art)]
            if leftovers:
                raise SystemExit(f"absolute LC_RPATH left in staged artifacts: {leftovers}")
            deps_out = _run(["otool", "-L", str(lib_path)])
            external = [l.strip().split(" (")[0] for l in deps_out.splitlines()[1:]
                        if l.strip().startswith("/") and not l.strip().startswith(("/usr/lib/", "/System/"))]
            if external:
                raise SystemExit(f"non-system absolute dependencies remain: {external}")
        minos = None
        if system == "darwin":
            for line in _run(["otool", "-l", str(lib_path)]).splitlines():
                if "minos" in line:
                    minos = line.split()[-1]
                    break
        commit = _run(["git", "rev-parse", "HEAD"], cwd=ROOT).strip()
        dirty = bool(_run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT).strip())
        files = sorted(p for p in native.iterdir() if p.is_file() and p.name != "manifest.json")
        manifest = {
            "schema": 1,
            "family": name,
            "backend": a.backend,
            "abi_version": 1,
            "modules": list(modules),
            "request_types": request_types,
            "excluded_functions": list(excluded),
            "library": lib_name,
            "load_order": load_order,
            "runtime_tag": tag,
            "renamed_runtime_files": renamed,
            "platform": plat,
            "macos_deployment_target": deployment_target if system == "darwin" else None,
            "router": router_report,
            "engine_kernels_included": kernels_included,
            "engine_kernels_included_count": len(kernels_included),
            "engine_kernels_inclusion_method": "11-char mangled name prefix in binary strings (prefix-level evidence)",
            "embedded_metal_libraries": embedded_pipelines,
            "linked_metal_blobs": blob_names,
            "minos": minos,
            "mojo_version": mojo_version,
            "guard": guard_report,
            "stub_guard": a.stub_guard,
            "source_commit": commit,
            "source_dirty": dirty,
            "exports": sorted(exports),
            "files": {p.name: {"sha256": _sha256(p), "bytes": p.stat().st_size} for p in files},
        }
        (native / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        total = sum(v["bytes"] for v in manifest["files"].values())
        print(f"built {name}: {len(modules)} modules -> {lib_path} ({plat}, minos {minos}); closure {len(files)} files, {total/1e6:.1f} MB; {guard_report}")
        return 0
    finally:
        if a.keep_stage:
            print(f"stage kept at {stage}")
        else:
            shutil.rmtree(stage, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
