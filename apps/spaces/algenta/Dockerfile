# Algenta — the flagship Space
#
# python:3.14-slim is REQUIRED for the main app: `algenta-runtime-native`
# publishes wheels for CPython 3.14 only (>=3.14,<3.15). The arena's pinned
# incumbents (ruptures<3.14, numba, ...) cannot share that interpreter, so
# duel cells run in a dedicated CPython 3.12 venv (/opt/arena) via
# arena_runner.py — same harness code as the standalone Speed Arena Space.
FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1 \
    GRADIO_SERVER_NAME=0.0.0.0 \
    GRADIO_SERVER_PORT=7860

RUN useradd --create-home --shell /bin/bash space
WORKDIR /app

# --- arena interpreter: CPython 3.12 (uv-managed, world-readable under /opt) ---
ENV UV_PYTHON_INSTALL_DIR=/opt/uv-python
COPY arena-requirements.txt .
RUN pip install --no-cache-dir uv \
    && uv python install 3.12 \
    && uv venv --python 3.12 /opt/arena \
    && uv pip install --python /opt/arena/bin/python -r arena-requirements.txt

# --- main app deps (CPython 3.14) ---
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chown -R space:space /app /opt/arena
USER space
ENV HOME=/home/space

EXPOSE 7860
CMD ["python", "app.py"]
