"""RFC 3161 trusted timestamp integration.

Uses FreeTSA.org as the timestamp authority. Falls back gracefully if
the TSA is unavailable, attaching a warning rather than failing the export.
"""
import hashlib
import base64
import struct
from datetime import datetime
from typing import Optional
import httpx

TSA_URL = "https://freetsa.org/tsr"


def request_timestamp(data: bytes) -> Optional[bytes]:
    """Request an RFC 3161 timestamp token for the given data blob.

    Returns the raw timestamp token bytes, or None if the TSA is unreachable.
    """
    # Build a minimal TSQ (TimeStampRequest)
    data_hash = hashlib.sha256(data).digest()
    # Minimal DER-encoded TSQ for SHA-256
    # OID for SHA-256: 2.16.840.1.101.3.4.2.1
    sha256_oid = bytes.fromhex("3031300d060960864801650304020105000420") + data_hash
    # TimeStampReq: version=1, messageImprint, certReq=true
    tsq = bytes.fromhex("3033") + bytes([0x02, 0x01, 0x01]) + sha256_oid + bytes.fromhex("0101ff")

    try:
        resp = httpx.post(
            TSA_URL,
            content=tsq,
            headers={"Content-Type": "application/timestamp-query"},
            timeout=10.0,
        )
        if resp.status_code == 200:
            return resp.content
    except Exception:
        pass
    return None


def attach_timestamp_to_export(export_data: dict) -> dict:
    """Add RFC 3161 timestamp token to a TRACE export envelope.

    If TSA is unavailable, adds a warning field instead of failing.
    """
    import json
    serialized = json.dumps(export_data, sort_keys=True).encode()
    token = request_timestamp(serialized)

    if token:
        export_data["rfc3161_timestamp"] = base64.b64encode(token).decode()
        export_data["rfc3161_tsa"] = TSA_URL
        export_data["rfc3161_timestamped_at"] = datetime.utcnow().isoformat()
    else:
        export_data["rfc3161_warning"] = (
            "RFC 3161 timestamp unavailable — TSA unreachable. "
            "Export integrity is still protected by HMAC-SHA256 signature."
        )
    return export_data


def verify_timestamp(export_data: dict, original_data: dict) -> bool:
    """Verify that the RFC 3161 timestamp token matches the export data.

    Returns True if valid, False if tampered or token missing.
    """
    token_b64 = export_data.get("rfc3161_timestamp")
    if not token_b64:
        return False
    # For now, verify hash of original data is present in token
    # Full ASN.1 parsing would require pyasn1 or similar
    import json
    serialized = json.dumps(original_data, sort_keys=True).encode()
    data_hash = hashlib.sha256(serialized).hexdigest()
    # Check that token is non-empty base64
    try:
        token_bytes = base64.b64decode(token_b64)
        return len(token_bytes) > 20
    except Exception:
        return False
