from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from database import get_db

class TenantContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Extract tenant from JWT token claims (set by auth middleware)
        tenant_id = getattr(request.state, "tenant_id", None)
        if tenant_id:
            # Set Supabase RLS context variable per request
            async with get_db() as db:
                db.execute(f"SET LOCAL app.current_tenant = '{tenant_id}'")
        response = await call_next(request)
        return response
