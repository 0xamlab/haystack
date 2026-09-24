#!/usr/bin/env bash
# Launch the flagship Space locally, the way QA, the golden capture and the verifier need it.
#
#   apps/spaces/algenta/scripts/spaces-flagship-run.sh [--port 7860] [--venv DIR] [--hf-home DIR]
#                                                      [--wait] [--no-install] [-- extra app args]
#
# * one shared venv (default: <scratchpad>/venv-flagship, override with --venv or
#   ALGENTA_FLAGSHIP_VENV); created with uv on CPython 3.12 and given the pinned set below
#   when `gradio` is missing from it — an existing venv is reused untouched
# * HF_HOME on a writable directory (default: <checkout>/../hf-home, override with --hf-home
#   or HF_HOME); ~/.cache/huggingface is a broken symlink on this machine
# * the shared package is imported from apps/spaces/_shared (in the container it is vendored
#   next to app.py by tools/stage.py), so the footer stamp reads `dev` locally
# * --wait blocks until /health reports ready (up to ALGENTA_FLAGSHIP_BOOT_S, default 600 s)
#   and then keeps the server in the foreground; without it the app is exec'd directly
#
# Prints the URL it serves on. Ctrl-C stops the app.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
app_dir="$(cd "${here}/.." && pwd)"
spaces_dir="$(cd "${app_dir}/.." && pwd)"
checkout="$(cd "${spaces_dir}/../.." && pwd)"

port="${GRADIO_SERVER_PORT:-7860}"
venv_dir="${ALGENTA_FLAGSHIP_VENV:-}"
hf_home="${HF_HOME:-}"
wait_ready=0
install=1
extra_args=()

while [ $# -gt 0 ]; do
  case "$1" in
    --port) port="$2"; shift 2 ;;
    --venv) venv_dir="$2"; shift 2 ;;
    --hf-home) hf_home="$2"; shift 2 ;;
    --wait) wait_ready=1; shift ;;
    --no-install) install=0; shift ;;
    --) shift; extra_args=("$@"); break ;;
    -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

if [ -z "${venv_dir}" ]; then
  scratch="$(dirname "${checkout}")"
  venv_dir="${scratch}/venv-flagship"
fi
if [ -z "${hf_home}" ]; then
  hf_home="$(dirname "${checkout}")/hf-home"
fi
mkdir -p "${hf_home}"

py="${venv_dir}/bin/python"
if [ ! -x "${py}" ]; then
  echo "creating ${venv_dir} (CPython 3.12)"
  uv venv --python 3.12 "${venv_dir}"
fi
if [ "${install}" -eq 1 ] && ! "${py}" -c "import gradio, gradio_client, torch, kernels, PIL, playwright" 2>/dev/null; then
  echo "installing the flagship's local toolchain into ${venv_dir}"
  uv pip install --python "${py}" \
    "gradio==6.28.0" gradio_client torch==2.5.1 "kernels>=0.17.1,<0.18" \
    "huggingface_hub>=1.26,<2" statsmodels scipy networkx nltk sympy numpy \
    pytest pytest-asyncio playwright pillow axe-playwright-python
  "${py}" -m playwright install chromium
fi

export HF_HOME="${hf_home}"
export GRADIO_SERVER_NAME="${GRADIO_SERVER_NAME:-127.0.0.1}"
export GRADIO_SERVER_PORT="${port}"
export GRADIO_ANALYTICS_ENABLED="False"
export PYTHONPATH="${spaces_dir}/_shared${PYTHONPATH:+:${PYTHONPATH}}"
export PYTHONUNBUFFERED=1

url="http://${GRADIO_SERVER_NAME}:${port}"
echo "flagship: ${url}  (HF_HOME=${HF_HOME}, venv=${venv_dir})"

cd "${app_dir}"
if [ "${wait_ready}" -eq 0 ]; then
  exec "${py}" app.py "${extra_args[@]+"${extra_args[@]}"}"
fi

"${py}" app.py "${extra_args[@]+"${extra_args[@]}"}" &
app_pid=$!
trap 'kill "${app_pid}" 2>/dev/null || true' EXIT INT TERM

boot_budget="${ALGENTA_FLAGSHIP_BOOT_S:-600}"
deadline=$((SECONDS + boot_budget))
until "${py}" - "${url}" <<'PY'
import json, sys, urllib.request
try:
    with urllib.request.urlopen(sys.argv[1] + "/health", timeout=5) as resp:
        snap = json.loads(resp.read())
except Exception:
    sys.exit(1)
sys.exit(0 if snap.get("ready") is True else 1)
PY
do
  if ! kill -0 "${app_pid}" 2>/dev/null; then
    echo "app exited before /health reported ready" >&2
    exit 1
  fi
  if [ "${SECONDS}" -ge "${deadline}" ]; then
    echo "app did not report ready within ${boot_budget} s" >&2
    exit 1
  fi
  sleep 2
done
echo "flagship ready: ${url}/health"
wait "${app_pid}"
