# Algenta Governed Agent — Real LLM
#
# python:3.14-slim is REQUIRED: `algenta-runtime-native` publishes wheels for
# CPython 3.14 only (>=3.14,<3.15), linux x86_64 + macOS arm64. HF docker Spaces
# run x86_64, so the manylinux_2_35_x86_64 runtime and mojo-kernel wheels
# resolve here.
#
# Live inference is streamed from HF Inference Providers (the HF_TOKEN secret,
# billed to the thyn-ai org), so NO model weights are baked into the image and
# nothing is compiled in-image — every dependency installs from wheels.
# Governance, kernels and receipts run locally in this container.
FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1 \
    GRADIO_SERVER_NAME=0.0.0.0 \
    GRADIO_SERVER_PORT=7860 \
    PIP_NO_CACHE_DIR=1

RUN useradd --create-home --shell /bin/bash space
WORKDIR /app

COPY requirements.txt .
# libgomp1 stays: the signed Mojo runtime's native .so links OpenMP.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && pip install --no-cache-dir -r requirements.txt \
    && rm -rf /var/lib/apt/lists/*

COPY . .

RUN chown -R space:space /app
USER space
ENV HOME=/home/space

EXPOSE 7860
CMD ["python", "app.py"]
