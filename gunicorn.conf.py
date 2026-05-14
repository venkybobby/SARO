"""
Gunicorn configuration for SARO FastAPI on Railway.

Worker model: UvicornWorker — each worker is a full async uvicorn event loop.
SARO uses synchronous SQLAlchemy sessions (psycopg2); UvicornWorker is still
the correct choice because FastAPI itself requires an async-capable server.

Sizing: (2 * CPU) + 1 is the standard formula. Railway Starter gives 1 vCPU,
so 3 workers is the right default. Increase via GUNICORN_WORKERS env var if
on a larger plan.
"""
import os

# ── Workers ───────────────────────────────────────────────────────────────────
worker_class = "uvicorn.workers.UvicornWorker"
workers = int(os.environ.get("GUNICORN_WORKERS", 3))

# ── Binding (Railway injects $PORT) ───────────────────────────────────────────
# CMD overrides this; kept here for completeness / local gunicorn runs
bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"

# ── Timeouts ─────────────────────────────────────────────────────────────────
timeout = 120          # kill worker if silent for 2 min (covers slow scan runs)
graceful_timeout = 30  # time to finish in-flight requests on SIGTERM
keepalive = 5          # HTTP keep-alive seconds

# ── Logging ───────────────────────────────────────────────────────────────────
accesslog = "-"        # stdout → Railway log stream
errorlog = "-"         # stderr → Railway log stream
loglevel = os.environ.get("LOG_LEVEL", "info")
access_log_format = (
    '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)sµs'
)

# ── Process naming ────────────────────────────────────────────────────────────
proc_name = "saro-api"

# ── Security ─────────────────────────────────────────────────────────────────
limit_request_line = 8190       # max URI length
limit_request_fields = 100      # max HTTP headers
limit_request_field_size = 8190 # max header value length

# ── Railway-specific: no need for pidfile or daemon mode ─────────────────────
daemon = False
pidfile = None
