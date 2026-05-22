"""Jira Cloud OAuth2 integration service (SPEC-F3)."""
from __future__ import annotations

import base64
import hashlib
import logging
import os

logger = logging.getLogger(__name__)


def _get_fernet():
    from cryptography.fernet import Fernet
    secret = os.environ.get("JWT_SECRET_KEY", "saro-default-secret-key-change-in-prod")
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
    return Fernet(key)


def encrypt_token(token: str) -> str:
    return _get_fernet().encrypt(token.encode()).decode()


def decrypt_token(encrypted: str) -> str:
    return _get_fernet().decrypt(encrypted.encode()).decode()


def create_issue(
    access_token: str,
    project_key: str,
    summary: str,
    description: str,
    priority: str = "Medium",
    labels: list[str] | None = None,
) -> dict:
    """Create a Jira Cloud issue. Returns {key, id, url} or raises on failure."""
    import httpx

    url = "https://api.atlassian.com/ex/jira/cloud/rest/api/3/issue"
    payload = {
        "fields": {
            "project": {"key": project_key},
            "summary": summary,
            "description": {
                "type": "doc",
                "version": 1,
                "content": [{"type": "paragraph", "content": [{"type": "text", "text": description}]}],
            },
            "issuetype": {"name": "Task"},
            "priority": {"name": priority},
            "labels": labels or ["saro-audit"],
        }
    }
    resp = httpx.post(
        url,
        json=payload,
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    key = data.get("key", "")
    return {
        "key": key,
        "id": data.get("id"),
        "url": f"https://your-domain.atlassian.net/browse/{key}",
    }


def refresh_token(refresh_token_val: str, client_id: str, client_secret: str) -> dict:
    """Refresh Jira OAuth access token."""
    import httpx

    resp = httpx.post(
        "https://auth.atlassian.com/oauth/token",
        json={
            "grant_type": "refresh_token",
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token_val,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()
