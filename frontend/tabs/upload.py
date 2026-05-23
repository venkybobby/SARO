"""
Upload Tab — SARO Streamlit frontend.

Accepts two batch formats:
  1. Standard SARO format  — {samples: [{text, group?, label?}, …]}
     → POST /api/v1/scan
  2. saro_data framework format — {model_type, intended_use, model_outputs: [{output, …}]}
     → POST /api/v1/scan/data

Validation enforces:
  - Minimum 50 samples (EU AI Act Art. 10, NIST MAP 2.3)
  - Required fields per format
  - Shows confidence estimate based on sample count
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Literal

import requests
import streamlit as st

logger = logging.getLogger(__name__)

_API_BASE = os.environ.get("SARO_API_URL", "http://localhost:8000")
_MIN_SAMPLES = 50

# Batch format detection
BatchFormat = Literal["standard", "saro_data", "unknown"]


def _detect_format(data: dict) -> BatchFormat:
    """
    Detect whether a batch dict uses the standard or saro_data format.

    standard  : has 'samples' list → POST /api/v1/scan
    saro_data : has 'model_outputs' + 'model_type' → POST /api/v1/scan/data
    """
    if "model_outputs" in data and "model_type" in data:
        return "saro_data"
    if "samples" in data:
        return "standard"
    return "unknown"


def _post_scan(payload: dict, token: str, fmt: BatchFormat = "standard") -> dict:
    endpoint = "/api/v1/scan/data" if fmt == "saro_data" else "/api/v1/scan"
    resp = requests.post(
        f"{_API_BASE}{endpoint}",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()


def _confidence_label(n: int) -> tuple[str, str]:
    """Return (label, colour) for sample-count-based confidence estimate."""
    if n >= 500:
        return "Very High", "green"
    if n >= 200:
        return "High", "green"
    if n >= 100:
        return "Moderate", "orange"
    if n >= 50:
        return "Low (minimum threshold met)", "orange"
    return "Insufficient", "red"


def _validate_batch(data: Any) -> tuple[bool, str, dict | None, BatchFormat]:
    """
    Validate a raw dict as a SARO batch (either format).

    Returns (is_valid, error_message, normalised_dict, detected_format).
    """
    if not isinstance(data, dict):
        return False, "Batch must be a JSON object.", None, "unknown"

    fmt = _detect_format(data)

    if fmt == "unknown":
        return (
            False,
            "Unrecognised batch format. Expected either:\n"
            "- Standard: `{\"samples\": [{\"text\": …}, …]}`\n"
            "- saro_data: `{\"model_type\": …, \"intended_use\": …, \"model_outputs\": [{\"output\": …}, …]}`",
            None,
            "unknown",
        )

    # ── Standard format validation ────────────────────────────────────────────
    if fmt == "standard":
        samples = data.get("samples", [])
        if not isinstance(samples, list) or len(samples) == 0:
            return False, "Batch must contain a non-empty 'samples' list.", None, fmt
        if len(samples) < _MIN_SAMPLES:
            return (
                False,
                f"Only {len(samples)} samples found. "
                f"A minimum of **{_MIN_SAMPLES} samples** is required for fairness metrics "
                "(EU AI Act Art. 10, NIST MAP 2.3).",
                None,
                fmt,
            )
        bad = [i for i, s in enumerate(samples)
               if not isinstance(s.get("text"), str) or not s["text"].strip()]
        if bad:
            return False, f"Samples at indices {bad[:5]} have missing/blank 'text' fields.", None, fmt

    # ── saro_data format validation ───────────────────────────────────────────
    else:
        model_outputs = data.get("model_outputs", [])
        if not isinstance(model_outputs, list) or len(model_outputs) == 0:
            return False, "Batch must contain a non-empty 'model_outputs' list.", None, fmt
        if len(model_outputs) < _MIN_SAMPLES:
            return (
                False,
                f"Only {len(model_outputs)} model outputs found. "
                f"A minimum of **{_MIN_SAMPLES} samples** is required "
                "(EU AI Act Art. 10, NIST MAP 2.3).",
                None,
                fmt,
            )
        bad = [i for i, s in enumerate(model_outputs)
               if not isinstance(s.get("output"), str) or not s["output"].strip()]
        if bad:
            return False, f"model_outputs at indices {bad[:5]} have missing/blank 'output' fields.", None, fmt
        if not data.get("intended_use"):
            return False, "saro_data batch missing required 'intended_use' field.", None, fmt

    return True, "", data, fmt


def render(token: str) -> None:
    """Render the Upload tab. `token` is the caller's JWT."""
    st.header("Submit Batch for Audit")
    st.caption(
        "Minimum **50 samples** required per EU AI Act Art. 10 and NIST MAP 2.3. "
        "More samples → higher confidence."
    )

    # ── Input method ─────────────────────────────────────────────────────────
    input_method = st.radio(
        "Input method",
        ["Upload JSON file", "Paste JSON"],
        horizontal=True,
        key="upload_input_method",
    )

    raw_text: str | None = None

    if input_method == "Upload JSON file":
        uploaded = st.file_uploader(
            "Upload SARO batch JSON",
            type=["json"],
            help="Expected format: {samples: [{sample_id?, text, group?, label?, metadata?}, ...]}",
            key="upload_file_uploader",
        )
        if uploaded:
            raw_text = uploaded.read().decode("utf-8")
    else:
        raw_text = st.text_area(
            "Paste batch JSON",
            height=250,
            placeholder='{"dataset_name": "my_dataset", "samples": [{"text": "..."}, ...]}',
            key="upload_paste_json",
        )

    if not raw_text:
        st.info("Upload or paste a batch JSON to continue.")
        return

    # ── Parse & validate ──────────────────────────────────────────────────────
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as e:
        st.error(f"Invalid JSON: {e}")
        return

    is_valid, err_msg, batch, fmt = _validate_batch(data)

    if not is_valid:
        st.error(err_msg)
        return

    # ── Resolve format-specific fields ───────────────────────────────────────
    if fmt == "saro_data":
        _items = batch["model_outputs"]  # type: ignore[index]
        _text_field = "output"
        _id_field = "output"          # saro_data has no sample_id
        _group_field_candidates = ("gender", "ethnicity")
    else:
        _items = batch["samples"]  # type: ignore[index]
        _text_field = "text"
        _id_field = "sample_id"
        _group_field_candidates = ("group",)

    n = len(_items)
    conf_label, conf_colour = _confidence_label(n)

    # ── Batch preview ─────────────────────────────────────────────────────────
    with st.expander("Batch preview", expanded=True):
        # Format badge
        if fmt == "saro_data":
            st.markdown(
                "**Format:** :blue[saro_data]  "
                "_(routed to `POST /api/v1/scan/data`)_"
            )
        else:
            st.markdown(
                "**Format:** :gray[standard]  "
                "_(routed to `POST /api/v1/scan`)_"
            )

        col1, col2, col3 = st.columns(3)
        col1.metric("Sample Count", n)
        if fmt == "saro_data":
            col2.metric("Model Type", batch.get("model_type") or "—")  # type: ignore[union-attr]
            col3.metric("Intended Use", (batch.get("intended_use") or "—")[:30])  # type: ignore[union-attr]
        else:
            col2.metric("Dataset", batch.get("dataset_name") or "—")  # type: ignore[union-attr]
            col3.metric("Batch ID", batch.get("batch_id") or "auto")  # type: ignore[union-attr]

        st.markdown(
            f"**Confidence estimate:** :{conf_colour}[{conf_label}]  "
            f"_(based on sample count; ≥200 = High, ≥50 = minimum)_"
        )

        # Show groups if present (field names differ per format)
        if fmt == "saro_data":
            groups = list(
                {s.get("gender") or s.get("ethnicity") for s in _items
                 if s.get("gender") or s.get("ethnicity")}
            )
        else:
            groups = list({s.get("group") for s in _items if s.get("group")})

        if groups:
            st.info(f"Demographic groups detected: `{', '.join(sorted(groups))}` — fairness analysis enabled.")
        else:
            st.warning(
                "No demographic group labels found in samples. "
                "Gate 2 (Fairness) will warn but not block the audit. "
                + (
                    "Add 'gender' or 'ethnicity' fields to each model_output for full statistical parity analysis."
                    if fmt == "saro_data"
                    else "Add a 'group' field to each sample for full statistical parity analysis."
                )
            )

        # Preview table — normalised to common column names
        preview_rows = []
        for i, s in enumerate(_items[:10]):
            raw_text = s.get(_text_field, "")
            preview_rows.append(
                {
                    "sample_id": s.get(_id_field, str(i)) if fmt != "saro_data" else f"output_{i}",
                    "text": (raw_text[:120] + "…") if len(raw_text) > 120 else raw_text,
                    "group": (
                        s.get("gender") or s.get("ethnicity") or ""
                        if fmt == "saro_data"
                        else s.get("group", "")
                    ),
                    "label": (
                        ("risky" if s.get("ground_truth") == 1 else "safe")
                        if fmt == "saro_data" and s.get("ground_truth") is not None
                        else s.get("label", "")
                    ),
                }
            )
        st.dataframe(preview_rows, use_container_width=True)
        if n > 10:
            st.caption(f"Showing first 10 of {n} samples.")

    # ── Configuration override ────────────────────────────────────────────────
    with st.expander("Audit configuration (optional)"):
        incident_top_k = st.slider(
            "Similar incidents to retrieve (top-K)", min_value=1, max_value=20, value=5,
            key="upload_top_k",
        )
        frameworks = st.multiselect(
            "Compliance frameworks",
            options=["EU AI Act", "NIST AI RMF", "AIGP", "ISO 42001"],
            default=["EU AI Act", "NIST AI RMF", "AIGP", "ISO 42001"],
            key="upload_frameworks",
        )
        # config is attached to the batch — field name is the same for both formats
        batch["config"] = {  # type: ignore[index]
            "min_samples": _MIN_SAMPLES,
            "incident_top_k": incident_top_k,
            "frameworks": frameworks,
        }

    # ── Submit ────────────────────────────────────────────────────────────────
    if st.button("Run Audit", type="primary", use_container_width=True, key="upload_run_audit"):
        with st.spinner("Running 4-gate SARO audit…"):
            try:
                report = _post_scan(batch, token, fmt)
                st.session_state["last_report"] = report
                st.success(
                    f"Audit **{report['audit_id']}** completed — "
                    f"status: `{report['status']}`"
                )
                _render_inline_report(report)
            except requests.HTTPError as exc:
                if exc.response is not None and exc.response.status_code == 401:
                    # Token expired mid-session — clear state and force re-login.
                    st.session_state["token"] = None
                    st.session_state["user"] = None
                    st.session_state["_session_expired"] = True
                    st.error(
                        "⏱ **Session expired.** Your login token has expired — "
                        "please sign in again to continue."
                    )
                    st.rerun()
                else:
                    try:
                        detail = exc.response.json().get("detail", str(exc))
                    except Exception:
                        detail = str(exc)
                    st.error(f"API error: {detail}")
            except requests.ConnectionError:
                st.error(
                    f"Cannot connect to SARO API at `{_API_BASE}`. "
                    "Is the backend running?"
                )


def _render_inline_report(report: dict) -> None:
    """Render a compact inline version of the full audit report."""
    import plotly.graph_objects as go

    st.divider()
    st.subheader("Audit Report")

    # ── Top-line metrics ──────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("MIT Coverage", f"{report['mit_coverage']['score']:.1%}")
    c2.metric(
        "Fixed Delta",
        f"{report['fixed_delta']['delta']:+.2f}",
        delta=f"{report['fixed_delta']['delta']:+.2f}",
        delta_color="normal",
    )
    c3.metric("Overall Risk", f"{report['bayesian_scores']['overall']:.1%}")
    c4.metric("Confidence", f"{report['confidence_score']:.1%}")

    # ── Gate results ──────────────────────────────────────────────────────────
    st.subheader("Gate Results")
    gate_icons = {"pass": "✅", "warn": "⚠️", "fail": "❌"}
    for g in report["gates"]:
        icon = gate_icons.get(g["status"], "•")
        with st.expander(f"{icon} Gate {g['gate_id']}: {g['name']} — score {g['score']:.3f}"):
            st.json(g["details"])

    # ── Bayesian domain scores ────────────────────────────────────────────────
    st.subheader("Bayesian Risk Scores by MIT Domain")
    domains = report["bayesian_scores"]["by_domain"]
    fig = go.Figure(
        go.Bar(
            x=[d["domain"] for d in domains],
            y=[d["risk_probability"] for d in domains],
            error_y={
                "type": "data",
                "symmetric": False,
                "array": [d["ci_upper"] - d["risk_probability"] for d in domains],
                "arrayminus": [d["risk_probability"] - d["ci_lower"] for d in domains],
            },
            marker_color=[
                "#d62728" if d["risk_probability"] > 0.4 else
                "#ff7f0e" if d["risk_probability"] > 0.2 else
                "#2ca02c"
                for d in domains
            ],
        )
    )
    fig.update_layout(
        xaxis_title="MIT Risk Domain",
        yaxis_title="Risk Probability (posterior mean)",
        yaxis_range=[0, 1],
        height=350,
        margin={"t": 10},
    )
    st.plotly_chart(fig, use_container_width=True)
