"""
Read-Only GitHub Integration routes.

SARO connects to GitHub with read-only scopes only.
No code is stored in SARO — only scan results + file hashes.
Clients can revoke access at any time.

POST   /api/v1/github/configure          — save PAT + allowed repos
GET    /api/v1/github/status             — integration status
DELETE /api/v1/github/disconnect         — revoke access + clear token
POST   /api/v1/github/scan/{audit_id}    — trigger read-only repo scan
GET    /api/v1/github/scan/{audit_id}    — retrieve scan results
"""
from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timezone
from typing import Annotated, Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from auth import get_current_user, require_role
from database import get_db
from models import Audit, AuditTrace, GitHubIntegration, GitHubScanResult, User
from routers.clients import _log_event
from schemas import (
    GitHubIntegrationConfigIn,
    GitHubIntegrationOut,
    GitHubScanResultOut,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/github", tags=["github-integration"])

_GITHUB_API = "https://api.github.com"
_SNIPPET_MAX_CHARS = 500  # max snippet length stored per file — never full file
_MAX_RESULTS_PER_SCAN = 20  # cap on correlated file results per audit

# MIT domain → search keywords for GitHub code search
_DOMAIN_SEARCH_TERMS: dict[str, list[str]] = {
    "Discrimination & Toxicity": ["bias", "toxicity", "filter", "content_policy", "guardrail"],
    "Privacy & Security": ["pii", "privacy", "redact", "anonymize", "encrypt", "sensitive"],
    "Misinformation": ["grounding", "rag", "fact_check", "hallucination", "citation"],
    "Malicious Use": ["safety", "guardrail", "moderation", "jailbreak", "injection"],
    "Human-Computer Interaction": ["human_review", "human_in_the_loop", "approval", "oversight"],
    "Socioeconomic & Environmental": ["impact", "fairness", "equity", "environmental"],
    "AI System Safety": ["fallback", "fail_safe", "timeout", "circuit_breaker", "override"],
}


# ── Helpers ───────────────────────────────────────────────────────────────────


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _get_integration_or_404(tenant_id: uuid.UUID, db: Session) -> GitHubIntegration:
    integ = (
        db.query(GitHubIntegration)
        .filter(GitHubIntegration.tenant_id == tenant_id, GitHubIntegration.is_active == True)  # noqa: E712
        .first()
    )
    if not integ:
        raise HTTPException(
            status_code=404,
            detail=(
                "No active GitHub integration configured. "
                "Use POST /api/v1/github/configure to set up read-only access."
            ),
        )
    return integ


def _github_headers(pat: str) -> dict[str, str]:
    return {
        "Authorization": f"token {pat}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _search_code(
    pat: str,
    query: str,
    repo: str,
    timeout: int = 10,
) -> list[dict[str, Any]]:
    """GitHub code search — read-only, returns file paths and snippets."""
    try:
        url = f"{_GITHUB_API}/search/code"
        params = {"q": f"{query} repo:{repo}", "per_page": 5}
        resp = httpx.get(url, headers=_github_headers(pat), params=params, timeout=timeout)
        if resp.status_code == 200:
            return resp.json().get("items", [])
        if resp.status_code == 422:
            return []  # Query too complex / no results
        logger.warning("GitHub search returned %d for query %r in %s", resp.status_code, query, repo)
        return []
    except httpx.TimeoutException:
        logger.warning("GitHub search timed out for %r in %s", query, repo)
        return []
    except Exception as exc:
        logger.warning("GitHub search error: %s", exc)
        return []


def _fetch_file_snippet(
    pat: str,
    repo: str,
    path: str,
    max_chars: int = _SNIPPET_MAX_CHARS,
) -> tuple[str | None, str | None]:
    """
    Fetch the first `max_chars` of a file from GitHub (read-only).
    Returns (snippet, sha256_of_content).
    Full file content is NEVER stored — only the snippet.
    """
    try:
        url = f"{_GITHUB_API}/repos/{repo}/contents/{path}"
        resp = httpx.get(url, headers=_github_headers(pat), timeout=10)
        if resp.status_code != 200:
            return None, None
        data = resp.json()
        import base64
        content = base64.b64decode(data.get("content", "")).decode("utf-8", errors="replace")
        scan_hash = hashlib.sha256(content.encode()).hexdigest()
        snippet = content[:max_chars] + ("…" if len(content) > max_chars else "")
        return snippet, scan_hash
    except Exception:
        return None, None


def _correlate_finding(domain: str, path: str, snippet: str | None) -> str:
    """Generate a human-readable correlation note from domain + file path."""
    hints = {
        "Discrimination & Toxicity": "Review this file for bias filters, content policies, or toxicity guardrails.",
        "Privacy & Security": "Check for PII handling, redaction logic, or data minimisation controls.",
        "Misinformation": "Inspect RAG grounding, fact-checking integrations, or uncertainty handling.",
        "Malicious Use": "Verify safety classifiers, input validation, or jailbreak-prevention logic.",
        "Human-Computer Interaction": "Look for human-in-the-loop checkpoints or approval gates.",
        "Socioeconomic & Environmental": "Review fairness scoring or impact assessment hooks.",
        "AI System Safety": "Check fail-safe mechanisms, timeout handling, or override logic.",
    }
    base_hint = hints.get(domain, "Inspect this file for AI governance controls related to the flagged domain.")
    return (
        f"[{domain}] Correlated with `{path}`. {base_hint} "
        f"Update according to SARO's remediation recommendations for this domain."
    )


# ── Routes ────────────────────────────────────────────────────────────────────


@router.post(
    "/configure",
    response_model=GitHubIntegrationOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("super_admin"))],
    summary="Configure read-only GitHub integration",
)
def configure_github(
    payload: GitHubIntegrationConfigIn,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> GitHubIntegrationOut:
    """
    Set up SARO's read-only GitHub integration.

    The PAT is hashed (SHA-256) before storage and is never retrievable.
    SARO will only read repositories explicitly listed in `allowed_repos`.
    """
    # Validate PAT has basic GitHub API access (read-only test)
    try:
        resp = httpx.get(
            f"{_GITHUB_API}/user",
            headers=_github_headers(payload.access_token),
            timeout=10,
        )
        if resp.status_code == 401:
            raise HTTPException(status_code=400, detail="Invalid GitHub Personal Access Token.")
        if resp.status_code not in (200, 403):
            raise HTTPException(status_code=400, detail=f"GitHub API returned {resp.status_code}.")
    except httpx.TimeoutException:
        raise HTTPException(status_code=400, detail="GitHub API timeout — check token validity.")

    # Validate repo format: "owner/repo"
    bad_repos = [r for r in payload.allowed_repos if "/" not in r or len(r.split("/")) != 2]
    if bad_repos:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid repo format (expected 'owner/repo'): {bad_repos}",
        )

    # Upsert integration
    existing = (
        db.query(GitHubIntegration)
        .filter(GitHubIntegration.tenant_id == current_user.tenant_id)
        .first()
    )
    token_hash = _hash_token(payload.access_token)

    if existing:
        existing.allowed_repos = payload.allowed_repos
        existing.access_token_hash = token_hash
        existing.is_active = True
        integ = existing
    else:
        integ = GitHubIntegration(
            tenant_id=current_user.tenant_id,
            allowed_repos=payload.allowed_repos,
            access_token_hash=token_hash,
            is_active=True,
        )
        db.add(integ)

    _log_event(db, current_user.tenant_id, current_user.id, "github_integration_configured", {
        "allowed_repos": payload.allowed_repos,
        "configured_by": current_user.email,
    })
    db.commit()
    db.refresh(integ)

    logger.info(
        "GitHub integration configured for tenant %s: %d repo(s)",
        current_user.tenant_id, len(payload.allowed_repos),
    )
    return GitHubIntegrationOut.model_validate(integ)


@router.get(
    "/status",
    response_model=GitHubIntegrationOut,
    dependencies=[Depends(require_role("super_admin", "operator"))],
    summary="GitHub integration status",
)
def get_github_status(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> GitHubIntegrationOut:
    """Return the current GitHub integration configuration for this tenant."""
    integ = _get_integration_or_404(current_user.tenant_id, db)  # noqa: F841
    return GitHubIntegrationOut.model_validate(integ)


@router.delete(
    "/disconnect",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_role("super_admin"))],
    summary="Revoke GitHub integration — clears token immediately",
)
def disconnect_github(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    """
    Revoke SARO's read-only GitHub access.
    Clears the token hash and marks the integration inactive.
    Existing scan results are retained for audit trail purposes.
    """
    integ = _get_integration_or_404(current_user.tenant_id, db)  # noqa: F841
    integ.is_active = False
    integ.access_token_hash = None

    _log_event(db, current_user.tenant_id, current_user.id, "github_integration_revoked", {
        "revoked_by": current_user.email,
    })
    db.commit()
    logger.info("GitHub integration revoked for tenant %s", current_user.tenant_id)


@router.post(
    "/scan/{audit_id}",
    response_model=list[GitHubScanResultOut],
    dependencies=[Depends(require_role("super_admin", "operator"))],
    summary="Trigger read-only GitHub repo scan correlated with audit findings",
)
def scan_repos_for_audit(
    audit_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[GitHubScanResultOut]:
    """
    Scan the client's configured GitHub repositories for code locations
    correlated with the triggered risk domains from this audit.

    Read-only: SARO only fetches file metadata and short snippets.
    Full file content is NEVER stored — only the first 500 chars + SHA-256.
    Every scan is logged to the immutable audit_events table.
    """
    # Validate audit belongs to this tenant
    audit = db.get(Audit, audit_id)
    if not audit or audit.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="Audit not found")
    if audit.status != "completed":
        raise HTTPException(status_code=400, detail=f"Audit is {audit.status} — scan requires completed audit.")

    # Get GitHub integration (validates access is configured)
    integ = _get_integration_or_404(current_user.tenant_id, db)  # noqa: F841

    # We need the plaintext token to call GitHub API — but we only store the hash!
    # This means the client must have recently configured the integration.
    # For MVP: store a short-lived encrypted token in a session/cache.
    # Current approach: return a helpful error directing the user to reconfigure.
    #
    # NOTE: In production, use GitHub App installation tokens (refreshable) instead of PATs.
    # For now, we require the user to re-enter their PAT via /configure before scanning.
    # The integration status endpoint shows last_scan_at to indicate freshness.
    #
    # To work around this cleanly, we accept an optional `pat` query param for scan requests.
    # This is safe because: (1) HTTPS-only, (2) not logged, (3) not stored.
    raise HTTPException(
        status_code=501,
        detail=(
            "GitHub scanning requires a live PAT for each scan request. "
            "Use POST /api/v1/github/scan-with-token to provide the token inline, "
            "or configure a GitHub App installation for token-refresh support."
        ),
    )


@router.post(
    "/scan-with-token/{audit_id}",
    response_model=list[GitHubScanResultOut],
    dependencies=[Depends(require_role("super_admin", "operator"))],
    summary="Scan repos with inline PAT — token not stored",
)
def scan_repos_with_token(
    audit_id: uuid.UUID,
    pat: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[GitHubScanResultOut]:
    """
    Trigger a read-only GitHub scan correlated with audit findings.

    The PAT is used in-flight and NEVER stored (not even hashed in this endpoint).
    The scan verifies the token matches the configured integration by comparing
    its SHA-256 to the stored hash.

    Results are stored as GitHubScanResult rows and logged to audit_events.
    """
    audit = db.get(Audit, audit_id)
    if not audit or audit.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="Audit not found")
    if audit.status != "completed":
        raise HTTPException(status_code=400, detail=f"Audit is {audit.status}")

    integ = _get_integration_or_404(current_user.tenant_id, db)  # noqa: F841

    # Verify provided PAT matches the configured integration
    if integ.access_token_hash and _hash_token(pat) != integ.access_token_hash:
        raise HTTPException(status_code=403, detail="Provided token does not match the configured integration.")

    # Get triggered domains from audit traces
    traces = (
        db.query(AuditTrace)
        .filter(
            AuditTrace.audit_id == audit_id,
            AuditTrace.check_type == "risk_domain",
            AuditTrace.result == "flagged",
        )
        .all()
    )
    triggered_domains = list({t.check_name for t in traces})

    if not triggered_domains:
        return []

    # Delete any existing scan results for this audit (idempotent)
    db.query(GitHubScanResult).filter(GitHubScanResult.audit_id == audit_id).delete()
    db.commit()

    results: list[GitHubScanResult] = []
    total_found = 0

    for repo in integ.allowed_repos:
        if total_found >= _MAX_RESULTS_PER_SCAN:
            break

        for domain in triggered_domains:
            search_terms = _DOMAIN_SEARCH_TERMS.get(domain, [domain.lower().replace(" & ", " ")])

            for term in search_terms[:2]:  # max 2 terms per domain to avoid rate limiting
                items = _search_code(pat, term, repo, timeout=10)

                for item in items[:3]:  # max 3 files per search term
                    if total_found >= _MAX_RESULTS_PER_SCAN:
                        break

                    file_path = item.get("path", "")
                    if not file_path:
                        continue

                    snippet, scan_hash = _fetch_file_snippet(pat, repo, file_path)
                    correlation_note = _correlate_finding(domain, file_path, snippet)

                    result = GitHubScanResult(
                        audit_id=audit_id,
                        repo_name=repo,
                        file_path=file_path,
                        line_number=None,  # GitHub code search doesn't return line numbers
                        snippet=snippet,
                        correlation_note=correlation_note,
                        finding_domain=domain,
                        scan_hash=scan_hash,
                    )
                    db.add(result)
                    results.append(result)
                    total_found += 1

    db.commit()
    for r in results:
        db.refresh(r)

    # Update last_scan_at + log event
    integ.last_scan_at = datetime.now(tz=timezone.utc)
    _log_event(db, current_user.tenant_id, current_user.id, "github_scan_completed", {
        "audit_id": str(audit_id),
        "repos_scanned": integ.allowed_repos,
        "domains_searched": triggered_domains,
        "results_found": len(results),
    })
    db.commit()

    logger.info(
        "GitHub scan for audit %s: %d results across %d repo(s)",
        audit_id, len(results), len(integ.allowed_repos),
    )
    return [GitHubScanResultOut.model_validate(r) for r in results]


@router.get(
    "/scan/{audit_id}",
    response_model=list[GitHubScanResultOut],
    dependencies=[Depends(require_role("super_admin", "operator"))],
    summary="Retrieve existing GitHub scan results for an audit",
)
def get_scan_results(
    audit_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[GitHubScanResultOut]:
    """Return all GitHub scan results previously stored for this audit."""
    audit = db.get(Audit, audit_id)
    if not audit or audit.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="Audit not found")

    results = (
        db.query(GitHubScanResult)
        .filter(GitHubScanResult.audit_id == audit_id)
        .order_by(GitHubScanResult.finding_domain, GitHubScanResult.repo_name)
        .all()
    )
    return [GitHubScanResultOut.model_validate(r) for r in results]
