# Algenta LLM Modules — Live
#
# python:3.14-slim is REQUIRED: `algenta-runtime-native` publishes wheels for
# CPython 3.14 only (>=3.14,<3.15), linux x86_64 + macOS arm64. HF Docker Spaces
# run x86_64, so the manylinux_2_35_x86_64 runtime wheel resolves here.
FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1 \
    GRADIO_SERVER_NAME=0.0.0.0 \
    GRADIO_SERVER_PORT=7860

RUN useradd --create-home --shell /bin/bash space
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chown -R space:space /app
USER space
ENV HOME=/home/space

EXPOSE 7860
CMD ["python", "app.py"]
