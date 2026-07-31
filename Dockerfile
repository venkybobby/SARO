# Production build target — used by fly.toml, .github/workflows/deploy.yml
# (flyctl deploy), and .github/workflows/security-scans.yml. This is the
# canonical backend image. For local docker-compose dev, see Dockerfile.api.
#
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

# Upgrade setuptools in place (proper pip upgrade, not a cross-stage file
# merge — merging a newer setuptools in via COPY left old and new _vendor/
# copies coexisting without actually replacing the active install). The
# base image's stale setuptools bundles vulnerable _vendor/ copies of wheel
# and jaraco.context (CVE-2026-24049, CVE-2026-23949); neither is a real
# requirements.txt dependency, so this is the only place to fix them.
RUN pip install --no-cache-dir --upgrade "setuptools>=80"

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
