"""FND-057 — get_demo_jwt() sent a form-encoded body to a JSON-only endpoint.

`scripts/seed_demo_tenant.py`'s `get_demo_jwt()` POSTed
`data={"username": ..., "password": ...}` (form-encoded) to
`/api/v1/auth/token`. That route's request model, `LoginIn` (`schemas.py`),
is a plain Pydantic body with no `Form()` dependency — FastAPI parses it as
JSON only. A form-encoded POST never satisfies it, so every demo-tenant
login attempt via this script 422'd; the demo tenant had ingested findings
but no way to obtain a working login. Found while wiring up a demo-tenant
login for e84e6a6c-e774-4e34-83cb-8610631b09dd.

Fix: `get_demo_jwt()` now sends `json={"email": ..., "password": ...}`,
matching `LoginIn.email`/`LoginIn.password`. This test pins the request body
shape so this can't silently regress back to form-encoding.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")


@pytest.mark.regression
def test_get_demo_jwt_sends_json_body_not_form_encoded():
    from scripts.seed_demo_tenant import get_demo_jwt

    resp = MagicMock()
    resp.json.return_value = {"access_token": "tok-fnd057"}

    with patch("scripts.seed_demo_tenant.requests.post", return_value=resp) as mock_post:
        token = get_demo_jwt("https://test.local", "demo@saro-demo.io", "s3cret")

    assert token == "tok-fnd057"

    _, kwargs = mock_post.call_args
    assert kwargs.get("json") == {"email": "demo@saro-demo.io", "password": "s3cret"}, (
        "get_demo_jwt must POST a JSON {email, password} body — LoginIn "
        "(schemas.py) has no Form() dependency, so a form-encoded body 422s "
        "on every call (FND-057)"
    )
    assert "data" not in kwargs, (
        "regression for FND-057: must not fall back to form-encoded data=..."
    )
