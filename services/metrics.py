"""In-process metrics registry + Prometheus text exposition (STORY-368).

Dependency-free on purpose. ``prometheus_client`` is **not** a declared SARO
dependency — ``middleware/rate_limiter.py`` imports it optionally with a
fallback — and putting the scrape path at the mercy of an optional import, for a
text format that is a few dozen lines, is a bad trade.

**INV-3 by construction: no tenant labels.** Nothing here accepts a tenant
identifier. A metrics endpoint carrying ``tenant_id`` labels would disclose the
customer list and per-customer volumes to anyone who can scrape it — tenant
isolation lost through the side door rather than through the API. Per-tenant
volume belongs to metering (STORY-374), behind normal authorization.

Counters are process-local and reset on restart. That is fine for rate and
error-ratio alerting (the questions we actually ask) and is stated in
``docs/ops/alerts.md`` so nobody reads a counter as a lifetime total.
"""

from __future__ import annotations

import threading
from typing import Iterable

# Latency buckets in seconds. Chosen around the SLO conversation (STORY-369):
# 100ms/250ms are "feels instant", 1s/2.5s bracket a normal evaluation, and 10s
# catches the pathological tail without inventing precision we cannot act on.
DEFAULT_BUCKETS: tuple[float, ...] = (0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)

_LOCK = threading.Lock()


def _fmt(value: float) -> str:
    """Render a float the way Prometheus expects (no scientific notation)."""
    if value == int(value):
        return str(int(value))
    return repr(round(value, 6))


def _labels_to_str(labels: dict[str, str]) -> str:
    if not labels:
        return ""
    inner = ",".join(f'{k}="{_escape(v)}"' for k, v in sorted(labels.items()))
    return "{" + inner + "}"


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


class Counter:
    """Monotonic counter. Process-local; resets on restart."""

    def __init__(self, name: str, help_text: str) -> None:
        self.name = name
        self.help_text = help_text
        self._values: dict[tuple[tuple[str, str], ...], float] = {}

    def inc(self, amount: float = 1.0, **labels: str) -> None:
        key = tuple(sorted(labels.items()))
        with _LOCK:
            self._values[key] = self._values.get(key, 0.0) + amount

    def value(self, **labels: str) -> float:
        return self._values.get(tuple(sorted(labels.items())), 0.0)

    def render(self) -> list[str]:
        out = [f"# HELP {self.name} {self.help_text}", f"# TYPE {self.name} counter"]
        if not self._values:
            out.append(f"{self.name} 0")
            return out
        for key, val in sorted(self._values.items()):
            out.append(f"{self.name}{_labels_to_str(dict(key))} {_fmt(val)}")
        return out


class Gauge:
    """Point-in-time value, either set directly or supplied by a callback."""

    def __init__(self, name: str, help_text: str) -> None:
        self.name = name
        self.help_text = help_text
        self._value: float = 0.0

    def set(self, value: float) -> None:
        with _LOCK:
            self._value = float(value)

    @property
    def current(self) -> float:
        return self._value

    def render(self) -> list[str]:
        return [
            f"# HELP {self.name} {self.help_text}",
            f"# TYPE {self.name} gauge",
            f"{self.name} {_fmt(self._value)}",
        ]


class Histogram:
    """Cumulative-bucket histogram — enough for p50/p95 estimation in alerting."""

    def __init__(self, name: str, help_text: str, buckets: Iterable[float] = DEFAULT_BUCKETS) -> None:
        self.name = name
        self.help_text = help_text
        self.buckets = tuple(sorted(buckets))
        self._counts: dict[float, float] = {b: 0.0 for b in self.buckets}
        self._inf = 0.0
        self._sum = 0.0

    def observe(self, seconds: float) -> None:
        with _LOCK:
            for bucket in self.buckets:
                if seconds <= bucket:
                    self._counts[bucket] += 1
            self._inf += 1
            self._sum += seconds

    @property
    def count(self) -> float:
        return self._inf

    def render(self) -> list[str]:
        out = [f"# HELP {self.name} {self.help_text}", f"# TYPE {self.name} histogram"]
        for bucket in self.buckets:
            out.append(f'{self.name}_bucket{{le="{_fmt(bucket)}"}} {_fmt(self._counts[bucket])}')
        out.append(f'{self.name}_bucket{{le="+Inf"}} {_fmt(self._inf)}')
        out.append(f"{self.name}_sum {_fmt(self._sum)}")
        out.append(f"{self.name}_count {_fmt(self._inf)}")
        return out


# ── The registry ────────────────────────────────────────────────────────────

REQUESTS = Counter(
    "saro_http_requests_total",
    "HTTP requests handled, labelled by method and status class (no tenant labels).",
)
REQUEST_DURATION = Histogram(
    "saro_http_request_duration_seconds", "HTTP request duration in seconds."
)
DB_REACHABLE = Gauge("saro_db_reachable", "1 when the database answered its health probe, else 0.")
INGESTION_LAG = Gauge(
    "saro_ingestion_lag_seconds",
    "Age of the newest observation watermark. -1 when unknown (no checkpoints yet).",
)
BUILD_INFO = Gauge("saro_build_info", "Always 1; the app version travels in the exposition header.")
CANARY_FAILURES = Counter(
    "saro_canary_failures_total", "Synthetic canary evaluations that failed."
)

_ALL: tuple = (REQUESTS, REQUEST_DURATION, DB_REACHABLE, INGESTION_LAG, BUILD_INFO, CANARY_FAILURES)


def observe_request(method: str, status_code: int, duration_seconds: float) -> None:
    """Record one handled request.

    Only the method and the status CLASS are labelled — never the path. Raw
    paths carry ids (``/api/v1/traces/{uuid}``) and would both explode
    cardinality and put customer-identifying values into a scrape.
    """
    REQUESTS.inc(method=method.upper(), status=f"{status_code // 100}xx")
    REQUEST_DURATION.observe(duration_seconds)


def render_exposition(version: str = "unknown") -> str:
    """Render the full registry in Prometheus text-exposition format."""
    BUILD_INFO.set(1)
    lines: list[str] = [
        "# SARO metrics — global aggregates only, no tenant identifiers (INV-3).",
        f"# saro_version {version}",
    ]
    for metric in _ALL:
        lines.extend(metric.render())
    return "\n".join(lines) + "\n"


def reset_for_tests() -> None:
    """Clear all state. Test-only — production metrics are never reset."""
    with _LOCK:
        for metric in _ALL:
            if isinstance(metric, Counter):
                metric._values.clear()
            elif isinstance(metric, Gauge):
                metric._value = 0.0
            elif isinstance(metric, Histogram):
                metric._counts = {b: 0.0 for b in metric.buckets}
                metric._inf = 0.0
                metric._sum = 0.0
