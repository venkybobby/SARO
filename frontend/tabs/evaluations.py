"""
Evaluation History Tab — saro-data-framework run history.

Shows the history of automated evaluation runs (GET /api/v1/evaluations)
with per-run detail, per-dataset results, and validation rule outcomes.

The weekly cron at .github/workflows/eval-weekly.yml posts run results
to POST /api/v1/evaluations/ingest after each run.
"""
from __future__ import annotations

from typing import Any

import requests
import streamlit as st

_STATUS_CONFIG: dict[str, tuple[str, str]] = {
    "completed": ("✅", "#16a34a"),
    "partial":   ("⚠️", "#ca8a04"),
    "failed":    ("❌", "#dc2626"),
    "running":   ("🔄", "#3b82f6"),
}


def _api(token: str, method: str, path: str, **kwargs: Any) -> requests.Response:
    base = st.session_state.get("api_base", "http://localhost:8000").rstrip("/")
    return getattr(requests, method)(
        f"{base}{path}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
        **kwargs,
    )


def _safe_get(token: str, path: str) -> Any:
    try:
        resp = _api(token, "get", path)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        st.error(f"API error ({path}): {exc}")
        return None


def _safe_post(token: str, path: str, **kwargs: Any) -> Any:
    try:
        resp = _api(token, "post", path, **kwargs)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        st.error(f"API error ({path}): {exc}")
        return None


def _status_badge(status: str) -> str:
    icon, color = _STATUS_CONFIG.get(status, ("❓", "#6b7280"))
    return (
        f'<span style="background:{color}22;color:{color};border:1px solid {color};'
        f'padding:1px 8px;border-radius:10px;font-size:0.75rem;font-weight:700">'
        f'{icon} {status.upper()}</span>'
    )


def _render_dataset_results(results: list[dict]) -> None:
    """Render per-dataset pass/fail/skip table."""
    if not results:
        st.caption("No per-dataset results available.")
        return

    h1, h2, h3, h4 = st.columns([2.5, 1, 1, 3])
    h1.markdown("**Dataset**")
    h2.markdown("**Result**")
    h3.markdown("**Samples**")
    h4.markdown("**Detail**")
    st.divider()

    for r in results:
        name = r.get("dataset_name", "—")
        skipped = r.get("skipped", False)
        passed = r.get("all_passed", False)
        samples = r.get("sample_count", 0)
        upload_err = r.get("upload_error", "")
        convert_err = r.get("convert_error", "")

        if skipped:
            icon, color = "⏭️", "#64748b"
            status_text = "SKIP"
        elif passed:
            icon, color = "✅", "#16a34a"
            status_text = "PASS"
        else:
            icon, color = "❌", "#dc2626"
            status_text = "FAIL"

        c1, c2, c3, c4 = st.columns([2.5, 1, 1, 3])
        c1.markdown(f"`{name}`")
        c2.markdown(
            f'<span style="color:{color};font-weight:700;font-size:0.8rem">'
            f'{icon} {status_text}</span>',
            unsafe_allow_html=True,
        )
        c3.markdown(str(samples) if samples > 0 else "—")
        detail = upload_err or convert_err or ""
        if detail:
            c4.caption(detail[:120])

        # Validation rule breakdown
        validation = r.get("validation") or {}
        if validation and not skipped:
            checks = validation.get("checks", [])
            failed_checks = [c for c in checks if not c.get("passed")]
            if failed_checks:
                with c4.expander(f"⚠️ {len(failed_checks)} rule(s) failed"):
                    for chk in failed_checks:
                        st.markdown(
                            f"- **{chk.get('rule_id', '?')}** {chk.get('description', '')}: "
                            f"{chk.get('detail', '')}"
                        )


def _render_latest_run(run: dict) -> None:
    """Render the most recent completed run as a headline card."""
    icon, color = _STATUS_CONFIG.get(run.get("status", ""), ("❓", "#6b7280"))
    elapsed = run.get("elapsed_seconds")
    elapsed_str = f"{elapsed:.0f}s" if elapsed else "—"
    ts = (run.get("completed_at") or run.get("started_at") or "")[:19].replace("T", " ")

    st.markdown(
        f'<div style="border:1px solid {color};border-radius:8px;padding:16px;'
        f'background:{color}11;margin-bottom:12px">'
        f'<div style="display:flex;align-items:center;gap:12px">'
        f'<span style="font-size:1.6rem">{icon}</span>'
        f'<div>'
        f'<div style="font-weight:700;color:{color}">'
        f'{run.get("datasets_passed", 0)}/{run.get("datasets_attempted", 0)} datasets passed'
        f'</div>'
        f'<div style="font-size:0.8rem;color:#94a3b8">'
        f'{run.get("total_samples_uploaded", 0):,} samples uploaded · '
        f'{elapsed_str} · {ts} UTC · '
        f'triggered by {run.get("triggered_by", "?")}'
        f'</div>'
        f'</div></div></div>',
        unsafe_allow_html=True,
    )


def render(token: str) -> None:
    st.header("🧪 Evaluation History")
    st.caption(
        "Automated evaluation runs from the saro-data-framework weekly pipeline. "
        "Each run converts 5 HuggingFace datasets (TruthfulQA, PII, Toxicity, CrowS-Pairs, "
        "Hallucination), uploads batches to /api/v1/scan, and validates 12 quality rules."
    )

    # ── Trigger manual run ────────────────────────────────────────────────────
    with st.expander("▶️ Trigger a new evaluation run", expanded=False):
        st.caption(
            "Runs the full saro-data-framework pipeline against the live API in the background. "
            "Results appear in the table below when the run completes (~2–3 min)."
        )
        dataset_options = [
            "real_toxicity_prompts", "guardrails_hallucination",
            "pii_masking", "crows_pairs", "truthfulqa",
        ]
        selected_datasets = st.multiselect(
            "Datasets to include (leave empty = all)",
            options=dataset_options,
            key="eval_datasets_select",
        )
        max_samples = st.slider("Max samples per dataset", min_value=50, max_value=500, value=200, step=50)

        if st.button("▶️ Start Evaluation Run", type="primary", key="eval_trigger_btn"):
            payload: dict[str, Any] = {"max_samples": max_samples}
            if selected_datasets:
                payload["datasets"] = selected_datasets
            result = _safe_post(token, "/api/v1/evaluations/trigger", json=payload)
            if result:
                st.success(f"Evaluation run started — ID: `{result.get('id', '?')}`")
                st.rerun()

    st.divider()

    # ── Latest run headline ───────────────────────────────────────────────────
    latest = _safe_get(token, "/api/v1/evaluations/latest")
    if latest:
        st.markdown("### Latest Completed Run")
        _render_latest_run(latest)

        # Per-dataset detail from the run summary JSON
        summary = latest.get("run_summary_json")
        if isinstance(summary, str):
            import json
            try:
                summary = json.loads(summary)
            except Exception:
                summary = None
        if isinstance(summary, dict):
            results = summary.get("results", [])
            if results:
                _render_dataset_results(results)

        st.divider()

    # ── Run history table ─────────────────────────────────────────────────────
    st.markdown("### Run History")

    col_filter, col_refresh = st.columns([3, 1])
    with col_filter:
        status_filter = st.selectbox(
            "Filter by status",
            options=["All", "completed", "partial", "failed", "running"],
            key="eval_status_filter",
        )
    with col_refresh:
        if st.button("🔄 Refresh", key="eval_refresh"):
            st.rerun()

    path = "/api/v1/evaluations?limit=20"
    if status_filter != "All":
        path += f"&status={status_filter}"
    runs = _safe_get(token, path)

    if not runs:
        st.info("No evaluation runs found. Trigger a run above or wait for the weekly cron (Mondays 02:00 UTC).")
        return

    h1, h2, h3, h4, h5 = st.columns([1.2, 1.5, 1.2, 1.2, 1.5])
    h1.markdown("**Status**")
    h2.markdown("**Started**")
    h3.markdown("**Passed**")
    h4.markdown("**Samples**")
    h5.markdown("**Elapsed**")
    st.divider()

    for i, run in enumerate(runs):
        status = run.get("status", "—")
        icon, color = _STATUS_CONFIG.get(status, ("❓", "#6b7280"))
        started = (run.get("started_at") or "")[:16].replace("T", " ")
        passed = run.get("datasets_passed", 0)
        attempted = run.get("datasets_attempted", 0)
        skipped = run.get("datasets_skipped", 0)
        samples = run.get("total_samples_uploaded", 0)
        elapsed = run.get("elapsed_seconds")
        elapsed_str = f"{elapsed:.0f}s" if elapsed else "—"

        c1, c2, c3, c4, c5 = st.columns([1.2, 1.5, 1.2, 1.2, 1.5])
        c1.markdown(
            f'<span style="color:{color};font-weight:700;font-size:0.8rem">{icon} {status}</span>',
            unsafe_allow_html=True,
        )
        c2.markdown(f'<span style="font-size:0.8rem">{started}</span>', unsafe_allow_html=True)
        c3.markdown(f"{passed}/{attempted}" + (f" (+{skipped} skip)" if skipped else ""))
        c4.markdown(f"{samples:,}" if samples else "—")
        c5.markdown(elapsed_str)

        # Expandable detail for this run
        run_id = run.get("id", "")
        with st.expander(f"Detail — run `{str(run_id)[:8]}…`", expanded=False):
            detail = _safe_get(token, f"/api/v1/evaluations/{run_id}")
            if detail:
                summary = detail.get("run_summary_json")
                if isinstance(summary, str):
                    import json
                    try:
                        summary = json.loads(summary)
                    except Exception:
                        summary = None
                if isinstance(summary, dict):
                    _render_dataset_results(summary.get("results", []))
                else:
                    st.json(detail)
            else:
                st.caption("Could not load detail.")
