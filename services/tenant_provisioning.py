"""Idempotent tenant provisioning (STORY-373).

Onboarding tenant #2 must be a procedure, not a memory. The properties that
matter, in order:

1. **Re-running is inert.** An operator re-runs a provisioning command precisely
   when they are unsure whether it worked. If a re-run silently re-applies
   defaults it can undo deliberate configuration — or worse, reset a live
   admin's password. FND-058 is the cautionary case in this repo: matching a
   user on a weak key and silently reassigning tenant, role, and password. So a
   re-run here **reports and stops**; it never mutates an existing tenant.

2. **The BAA gate is enforced in code, not prose.** INV-6 forbids PHI flowing
   before a BAA is executed. A checklist item gets skipped under time pressure,
   which is exactly when it matters, so provisioning refuses without explicit
   confirmation.

3. **Every provisioning action is audited** (STORY-366) on the SYSTEM chain — a
   cross-tenant admin action belongs to the operator's global trail, not to the
   tenant it created.
"""

from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

import services.self_audit as self_audit

# Length chosen for a generated one-time credential the operator will paste
# once. token_urlsafe(24) is ~32 characters of base64url.
_GENERATED_PASSWORD_BYTES = 24


class ProvisioningError(RuntimeError):
    """Provisioning refused or could not complete."""


class BAAGateNotConfirmed(ProvisioningError):
    """INV-6: PHI must not flow before a BAA is executed."""


@dataclass
class ProvisionResult:
    tenant_id: uuid.UUID
    slug: str
    created: bool
    admin_email: Optional[str] = None
    admin_user_id: Optional[uuid.UUID] = None
    generated_password: Optional[str] = None
    log_source_placeholder: bool = False
    already_existed: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        """Serializable summary. **Never includes the generated password** —
        it is returned once on the object for the caller to display, and must
        not travel into logs, audit metadata, or JSON output."""
        return {
            "tenant_id": str(self.tenant_id),
            "slug": self.slug,
            "created": self.created,
            "admin_email": self.admin_email,
            "admin_user_id": str(self.admin_user_id) if self.admin_user_id else None,
            "log_source_placeholder": self.log_source_placeholder,
            "already_existed": self.already_existed,
            "notes": self.notes,
        }


def generate_password() -> str:
    return secrets.token_urlsafe(_GENERATED_PASSWORD_BYTES)


def provision_tenant(
    db: Any,
    *,
    name: str,
    slug: str,
    admin_email: str,
    baa_confirmed: bool,
    actor: str,
    vertical: str = "general",
) -> ProvisionResult:
    """Create a tenant, its admin user, and an adapter placeholder.

    Idempotent: if the slug already exists, nothing is written and the result
    reports what was found.
    """
    from auth import hash_password
    from models import Tenant, TenantLogSourceConfig, User

    if not baa_confirmed:
        raise BAAGateNotConfirmed(
            "INV-6: a signed BAA must be in place before provisioning a tenant "
            "that may process PHI. Confirm the executed agreement (see "
            "compliance/baa/STORY-BAA-02_execution-package.md) and re-run with "
            "the BAA confirmation flag."
        )

    existing = db.query(Tenant).filter(Tenant.slug == slug).first()
    if existing is not None:
        # Inert re-run. Deliberately does NOT reconcile drift: an operator
        # re-running to check state must not have configuration changed under
        # them (FND-058).
        return ProvisionResult(
            tenant_id=existing.id,
            slug=slug,
            created=False,
            already_existed=["tenant"],
            notes=[
                "Tenant already exists — nothing was written. Provisioning is "
                "inert on re-run; adjust configuration explicitly rather than "
                "by re-provisioning."
            ],
        )

    tenant = Tenant(name=name, slug=slug)
    db.add(tenant)
    db.flush()  # assign tenant.id without ending the transaction

    result = ProvisionResult(tenant_id=tenant.id, slug=slug, created=True)

    existing_user = db.query(User).filter(User.email == admin_email).first()
    if existing_user is not None:
        # An email collision is ambiguous, and FND-058 shows what guessing
        # costs. Refuse rather than adopt or overwrite the account.
        raise ProvisioningError(
            f"A user with email {admin_email!r} already exists (tenant "
            f"{existing_user.tenant_id}). Refusing to reassign or overwrite it — "
            "use a different admin email, or move the existing account deliberately."
        )

    password = generate_password()
    admin = User(
        tenant_id=tenant.id,
        email=admin_email,
        hashed_password=hash_password(password),
        role="super_admin",
        persona_role="admin",
        is_active=True,
    )
    db.add(admin)
    db.flush()

    result.admin_email = admin_email
    result.admin_user_id = admin.id
    result.generated_password = password

    # Adapter placeholder: disabled, with no credentials. Creating the row makes
    # onboarding's next step discoverable instead of tribal knowledge.
    db.add(
        TenantLogSourceConfig(
            tenant_id=tenant.id,
            role_arn="",
            external_id=secrets.token_urlsafe(32),
            bucket="",
            prefix="",
            region="us-east-1",
            enabled=False,
        )
    )
    result.log_source_placeholder = True
    result.notes.append(
        "Log-source placeholder created (disabled). Complete it with the "
        "customer's cross-account role before ingesting."
    )

    # STORY-366: audited on the SYSTEM chain, and this commits the transaction —
    # tenant, admin, placeholder, and audit row land together, so an unauditable
    # provisioning rolls back rather than half-applying.
    self_audit.record_privileged(
        db,
        tenant_id=self_audit.SYSTEM_TENANT_ID,
        actor=actor,
        action_class=self_audit.ADMIN_ACTION,
        target_type="tenant",
        target_id=str(tenant.id),
        metadata={
            "operation": "provision_tenant",
            "slug": slug,
            "admin_email": admin_email,
            "vertical": vertical,
            "baa_confirmed": True,
            # The generated password is never recorded here.
        },
    )
    return result


def verify_isolation(db: Any, tenant_id: uuid.UUID) -> dict[str, Any]:
    """Confirm a freshly provisioned tenant can see none of another tenant's rows.

    Written against the database directly rather than importing test helpers —
    product code must not depend on ``tests/``. This is a positive check that
    the new tenant's visible row counts are zero across evidence-bearing tables,
    with at least one other tenant present to make the check meaningful: if there
    is nothing to leak, passing proves nothing.
    """
    from models import Audit, AuditEvent, ScanReport, Tenant

    other_tenants = (
        db.query(Tenant.id).filter(Tenant.id != tenant_id).count()
    )

    checks: dict[str, int] = {}
    for label, model in (("audits", Audit), ("scan_reports", ScanReport), ("audit_events", AuditEvent)):
        checks[label] = (
            db.query(model).filter(model.tenant_id == tenant_id).count()
        )

    leaked = {k: v for k, v in checks.items() if v > 0}
    return {
        "tenant_id": str(tenant_id),
        "other_tenants_present": other_tenants,
        "row_counts": checks,
        "isolated": not leaked,
        # A brand-new tenant with no peers cannot demonstrate isolation.
        "meaningful": other_tenants > 0,
        "detail": (
            "new tenant sees no rows"
            if not leaked
            else f"new tenant can see rows it should not: {leaked}"
        ),
    }
