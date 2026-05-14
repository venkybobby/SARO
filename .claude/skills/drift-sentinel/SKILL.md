---
name: drift-sentinel
description: Triggered when editing drift detection logic, KS-test implementation, circuit breaker configuration, or alert routing. Enforces SARO's 2σ auto-incident rule and circuit breaker thresholds.
---

# Drift Sentinel Skill

## Trigger Conditions
Activate for changes to `engine.py` sections containing `ks_test`, `drift`, `circuit_breaker`, `alert`, or `incident`, and any files referencing `KS_DRIFT_THRESHOLD` or `CIRCUIT_BREAKER_`.

## KS-Test Implementation

```python
from scipy.stats import ks_2samp
import numpy as np

def check_distribution_drift(
    reference: list[float],
    current: list[float],
    *,
    min_samples: int = 50,
) -> DriftResult:
    if len(reference) < min_samples or len(current) < min_samples:
        return DriftResult(drift_detected=False, reason="insufficient_samples")

    stat, p_value = ks_2samp(reference, current)

    return DriftResult(
        drift_detected=p_value < KS_DRIFT_THRESHOLD,   # 0.05
        critical_drift=p_value < KS_ALERT_THRESHOLD,   # 0.01
        ks_statistic=float(stat),
        p_value=float(p_value),
        sample_sizes=(len(reference), len(current)),
    )
```

## Drift Thresholds

| Condition | Threshold | Action |
|---|---|---|
| No drift | p ≥ 0.05 | Log only, no alert |
| Drift detected | p < 0.05 | `drift_detected=True` in TRACE, Sentry warning |
| Critical drift | p < 0.01 | Auto-incident, circuit breaker evaluation |
| 2σ rule trigger | score deviation > 2 std dev | Auto-incident, page on-call |

The **2σ rule**: if a client's rolling 7-day mean risk score deviates more than 2 standard deviations from their 90-day baseline, trigger an auto-incident regardless of KS p-value.

```python
def check_sigma_rule(baseline_mean, baseline_std, rolling_mean) -> bool:
    if baseline_std == 0:
        return False
    z_score = abs(rolling_mean - baseline_mean) / baseline_std
    return z_score > 2.0  # 2σ threshold — do not change without team review
```

## Circuit Breaker

```python
CIRCUIT_BREAKER_FAILURE_THRESHOLD = 5    # consecutive failures before open
CIRCUIT_BREAKER_RECOVERY_TIMEOUT_S = 60  # seconds before half-open probe
CIRCUIT_BREAKER_SUCCESS_THRESHOLD = 2    # successes to close from half-open

# States: CLOSED → OPEN → HALF_OPEN → CLOSED
# When OPEN: reject scans with 503 + Retry-After header
# When HALF_OPEN: allow 1 probe scan; success closes, failure re-opens
```

## Alert Routing

```python
# Severity levels
ALERT_WARNING  = "warning"   # drift_detected, no incident
ALERT_CRITICAL = "critical"  # critical_drift or 2σ trigger

# Routing (configure via env vars)
# ALERT_WARNING  → Sentry warning + structured log
# ALERT_CRITICAL → Sentry critical + PagerDuty (PAGERDUTY_SERVICE_KEY env var)
#                  + auto-create incident in audit_logs.incidents table

def route_alert(result: DriftResult, client_id: str) -> None:
    if result.critical_drift or result.sigma_breach:
        sentry_sdk.capture_message(
            f"[CRITICAL] Drift breach client={client_id} p={result.p_value:.4f}",
            level="critical"
        )
        create_auto_incident(client_id, result)  # writes to audit_logs
    elif result.drift_detected:
        logger.warning("drift_detected", client_id=client_id, p_value=result.p_value)
```

## Invariants

- `ks_statistic` and `p_value` must always be included in the TRACE `DRIFT_CHECKED` event.
- Auto-incidents are append-only entries in `audit_logs.incidents` — never auto-close them.
- Circuit breaker state is stored in Redis with key `cb:scan:<client_id>` — TTL must be set.
- Drift detection must process the last 30 days of scans as the reference window by default.
