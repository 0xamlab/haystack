# Algenta — the flagship Space (thyn-ai/algenta).
#
# python:3.14-slim: `algenta` (the hosted-API client behind the Governed tab) and its native
# runtime ship CPython 3.14 wheels only; everything else is pure Python or ships cp314 wheels,
# and requirements.lock pins each one by hash (uv pip compile --generate-hashes, see
# requirements.txt for the exact command). Build from the tree tools/stage.py produces: the
# shared package is vendored there as algenta_spaces/ next to app.py, with its .shared_sha.
#
# The Hub kernel cache is baked into the image as the runtime user and the runtime loads with
# HF_HUB_OFFLINE=1, so boot never downloads. Set the Space variable HF_HUB_OFFLINE=0 to let
# get_kernel reach the Hub instead (a host without the baked cache); the boot card then shows
# the load times it paid.
FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    GRADIO_SERVER_NAME=0.0.0.0 \
    GRADIO_SERVER_PORT=7860 \
    GRADIO_ANALYTICS_ENABLED=False \
    HF_HUB_DISABLE_TELEMETRY=1

# Hub Spaces run the container as uid 1000; the app and the cache belong to that user.
RUN useradd --create-home --uid 1000 --shell /bin/bash user
WORKDIR /app

# Dependencies first, so a copy edit does not reinstall torch. Every line is hash-pinned.
COPY requirements.lock ./
RUN pip install --no-cache-dir --require-hashes -r requirements.lock

COPY --chown=user:user . .
USER user
ENV HOME=/home/user \
    HF_HOME=/home/user/.cache/huggingface

# Bake the kernel cache: the twenty capped repositories at v1, this platform's build variant
# only, with the user-agent shim applied before `kernels` (boot_sequence imports hf_ua_shim
# first), then the Hub tree listings pruned so the offline loader accepts a variant-only cache.
RUN python boot_sequence.py --bake
# Prove the runtime never downloads: every family loads with the Hub unreachable.
RUN HF_HUB_OFFLINE=1 python boot_sequence.py --verify-cache

ENV HF_HUB_OFFLINE=1
EXPOSE 7860
CMD ["python", "app.py"]
