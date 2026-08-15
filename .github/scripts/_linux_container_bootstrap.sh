#!/usr/bin/env bash
# Shared bootstrap for the linux/amd64 container legs of build-runtime.yml: a real CPython 3.14
# (python-build-standalone via uv -- ubuntu:22.04's distro python is 3.10) plus the apt toolchain
# the runtime build links against. Sourced by the per-leg scripts; assumes cwd = /work (the
# mounted GITHUB_WORKSPACE). These containers run on the self-hosted macOS fleet under amd64
# emulation (Docker/Rosetta) -- the build-runtime linux pipeline moved here when GitHub-hosted
# runners became billing-blocked; the container OS is still ubuntu:22.04 (glibc 2.35), so the
# manylinux_2_35_x86_64 contract the wheel ships under is unchanged.
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
# patchelf: the staging script relinks the worker binaries' rpaths into the bundled lib closure.
# clang: `mojo build` emits objects but LINKS the worker executables through the system clang --
# GitHub-hosted ubuntu images ship it, the bare ubuntu:22.04 image does not (shard 1 died with
# "clang not found; cannot link Mojo object into an executable" until this landed).
# file/binutils: artifact type checks + strip. openssl: runtime manifest signing.
apt-get install -y -qq --no-install-recommends \
  ca-certificates curl git xz-utils bzip2 \
  build-essential clang patchelf file binutils openssl >/dev/null

# CPython 3.14 via uv (downloads python-build-standalone; no deadsnakes PPA, no source build).
curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/uv sh >/dev/null
export PATH="/usr/local/uv:$PATH"
uv python install 3.14 >/dev/null
PY="$(uv python find 3.14)"
ln -sf "$PY" /usr/local/bin/python3
ln -sf "$PY" /usr/local/bin/python
ln -sf "$PY" /usr/local/bin/python3.14
python3 --version

# uv doubles as the package installer for this interpreter (standalone builds ship no pip).
# uv-managed interpreters are "externally managed" by default; in this disposable container the
# base interpreter IS the target environment, so opt out explicitly.
export UV_BREAK_SYSTEM_PACKAGES=1
