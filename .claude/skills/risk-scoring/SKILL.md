---
name: risk-scoring
description: Triggered when editing scoring logic, TRACE timeline, DIR formula, or drift detection in engine.py. Enforces SARO scoring invariants and SHAP patterns.
---

# Risk Scoring Skill

## Trigger Conditions
Activate for any change to `engine.py`, `routers/scan.py`, `routers/traces.py`, or any file containing `risk_score`, `trace_event`, `dir_score`, or `ks_test`.

## Scoring Invariants (never violate)

```python
# Score is always int, 0–100 inclusive, never negative
assert isinstance(risk_score, int)
assert 0 <= risk_score <= 100

# DIR formula: Dimension-weighted Incident Rate
# dir_score = sum(weight_i * indicator_i) / sum(weight_i)  * 100
# Must use float accumulation, cast to int only at return boundary

# KS-test p-value threshold for drift flag
KS_DRIFT_THRESHOLD = 0.05   # p < 0.05 → drift detected
KS_ALERT_THRESHOLD = 0.01   # p < 0.01 → critical drift, auto-incident
```

## SHAP Patterns

- Use `shap.TreeExplainer` or `shap.LinearExplainer` — never `KernelExplainer` in hot path (too slow).
- SHAP values are for **explanation only** — they must not feed back into the score calculation.
- Always normalise SHAP values to [−1, 1] before including in TRACE output.
- Attach `shap_summary` dict to TRACE event with keys: `top_features` (list of 5), `base_value`, `model_output`.

## TRACE Timeline

Every scan must emit TRACE events in this order:

```
1. SCAN_INITIATED   — request received, prompt hash
2. RULES_APPLIED    — list of rule IDs evaluated
3. SCORE_COMPUTED   — raw DIR score, normalised score
4. SHAP_EXPLAINED   — top 5 features + SHAP values
5. DRIFT_CHECKED    — KS statistic, p-value, drift flag
6. REMEDIATION_GEN  — remediation text attached
7. SCAN_COMPLETE    — final risk_score, latency_ms
```

TRACE events are append-only. Never mutate or delete a TRACE event after creation.

## Output Schema

```python
class ScanResult(BaseModel):
    scan_id: str          # UUID4
    risk_score: int       # 0–100
    trace: list[TraceEvent]
    remediation: str
    drift_detected: bool
    confidence: float     # 0.0–1.0
    latency_ms: int
```

## Performance Constraints

- Full scan pipeline must complete in ≤ 3000 ms (p99).
- SHAP computation must be async or offloaded — never blocks the event loop.
- Cache rule pack weights in Redis with TTL = 300s.
