# ── Stage 1: dependency builder ──────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir --prefix=/install \
    -r requirements.txt \
    gunicorn==22.0.0

# ── Stage 2: production image ─────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Runtime system deps only (libpq for psycopg2)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application source
COPY . /app

# Install saro-data-framework from the local subdirectory now that /app exists.
# This is done in Stage 2 (not Stage 1 builder) because the local path
# ./saro-data-framework cannot be resolved in Stage 1's restricted context.
RUN pip install --no-cache-dir /app/saro-data-framework

ENV PYTHONPATH=/app \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Railway injects $PORT; default to 8000 for local runs
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
  CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

# Gunicorn + UvicornWorker: async-safe, production-grade
CMD ["sh", "-c", "gunicorn main:app \
  --config gunicorn.conf.py \
  --bind 0.0.0.0:${PORT:-8000}"]
