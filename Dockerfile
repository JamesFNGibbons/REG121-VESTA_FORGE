# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app \
    REG121_REPO_ROOT=/app

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY tools/requirements.txt /app/tools/requirements.txt
RUN pip install --no-cache-dir -r /app/tools/requirements.txt

COPY tools /app/tools

RUN python -c "from tools.embeddings import warm_splade_model; warm_splade_model()"

CMD ["python", "-m", "tools.ingest_components", "validate"]
