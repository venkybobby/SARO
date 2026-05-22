"""GET /api/v1/engine/status — engine health and index metadata (SPEC-E3)."""
from __future__ import annotations


from fastapi import APIRouter, Depends, Request

from auth import get_current_user

router = APIRouter(prefix="/api/v1/engine", tags=["engine"])


@router.get("/status")
async def engine_status(
    request: Request,
    current_user=Depends(get_current_user),
) -> dict:
    """Return engine health, incidents indexed, index built time, rule packs loaded."""
    eng = getattr(request.app.state, "engine", None)
    if eng is None:
        return {
            "status": "degraded",
            "incidents_indexed": 0,
            "index_built_at": None,
            "rule_packs_loaded": [],
            "engine_version": "8.0.0",
        }
    rule_packs = [rp.name for rp in getattr(eng, "_rule_packs", [])]
    return {
        "status": "healthy",
        "incidents_indexed": getattr(
            request.app.state,
            "engine_index_count",
            len(getattr(eng, "_incidents", [])),
        ),
        "index_built_at": getattr(request.app.state, "engine_index_built_at", None),
        "rule_packs_loaded": rule_packs,
        "engine_version": "8.0.0",
        "rule_pack_hash": eng.get_rule_pack_hash()[:16],
    }
