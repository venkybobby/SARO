"""Data retention policy engine for SARO.

Enforces tenant-configurable retention periods on audit data and processes
GDPR right-to-erasure requests with deletion certificates.
"""
from datetime import datetime, timedelta
from typing import Optional
import hashlib
import json


def calculate_retention_cutoff(retention_days: int) -> datetime:
    """Return the datetime before which data is eligible for purge."""
    return datetime.utcnow() - timedelta(days=retention_days)


def is_eligible_for_purge(created_at: datetime, retention_days: int) -> bool:
    """Return True if an audit record has exceeded its retention period."""
    cutoff = calculate_retention_cutoff(retention_days)
    return created_at < cutoff


def create_tombstone_record(event_id: int, tenant_id: int, reason: str = "retention_purge") -> dict:
    """Create a tombstone audit record to preserve hash chain integrity after deletion.

    The tombstone maintains the chain while hiding the deleted content.
    """
    return {
        "original_event_id": event_id,
        "tenant_id": tenant_id,
        "deleted_at": datetime.utcnow().isoformat(),
        "reason": reason,
        "tombstone_hash": hashlib.sha256(
            f"TOMBSTONE:{event_id}:{tenant_id}:{reason}".encode()
        ).hexdigest(),
    }


def generate_deletion_certificate(tenant_id: int, deleted_count: int,
                                   erasure_request_id: str) -> dict:
    """Generate a GDPR deletion certificate for legal records."""
    return {
        "certificate_type": "GDPR_ERASURE",
        "tenant_id": tenant_id,
        "erasure_request_id": erasure_request_id,
        "records_deleted": deleted_count,
        "completed_at": datetime.utcnow().isoformat(),
        "certificate_hash": hashlib.sha256(
            f"CERT:{tenant_id}:{deleted_count}:{erasure_request_id}".encode()
        ).hexdigest(),
    }
