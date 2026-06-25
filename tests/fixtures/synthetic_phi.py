"""Synthetic PHI fixture (STORY-403) — shared test asset.

All data here is FABRICATED. Never put real member data in this file. Used by the
edge-redaction tests (STORY-403), the block-lane detector, and later shadow-mode eval.

Provides:
- reference_safe_harbor_catalog(): a caller-supplied data-classification catalog covering
  all 18 HIPAA Safe Harbor identifier classes (regex for text-detectable, field-kind for
  structured/non-text). This is *example* policy-as-code, NOT a list baked into SARO.
- labeled_text_sample(): free text with known identifiers, for coverage/residual SLI math.
- structured_phi_record(): a structured record + the fields that hold PHI.
"""

from __future__ import annotations

from services.edge_redaction import FieldClass

# Regex classes — text-detectable HIPAA categories. Patterns are deliberately specific
# and non-overlapping so SLI math on the labeled sample is deterministic.
_REGEX_CLASSES: list[FieldClass] = [
    FieldClass("date", 3, "regex", pattern=r"\b\d{4}-\d{2}-\d{2}\b"),
    FieldClass("phone", 4, "regex", pattern=r"\(\d{3}\)\s?\d{3}-\d{4}"),
    FieldClass("fax", 5, "regex", pattern=r"(?i)fax[:\s]+\d{3}-\d{3}-\d{4}"),
    FieldClass("email", 6, "regex", pattern=r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    FieldClass("ssn", 7, "regex", pattern=r"\b\d{3}-\d{2}-\d{4}\b"),
    FieldClass("mrn", 8, "regex", pattern=r"\bMRN-\d+\b"),
    FieldClass("health_plan", 9, "regex", pattern=r"\bHPN-\d+\b"),
    FieldClass("account", 10, "regex", pattern=r"\bACCT-\d+\b"),
    FieldClass("license", 11, "regex", pattern=r"\bLIC-[A-Z0-9]+\b"),
    FieldClass("vehicle_vin", 12, "regex", pattern=r"\b[A-HJ-NPR-Z0-9]{17}\b"),
    FieldClass("device_serial", 13, "regex", pattern=r"\bSN-[A-Z0-9]+\b"),
    FieldClass("url", 14, "regex", pattern=r"https?://[^\s]+"),
    FieldClass("ip", 15, "regex", pattern=r"\b\d{1,3}(?:\.\d{1,3}){3}\b"),
    FieldClass("other_unique_code", 18, "regex", pattern=r"\bUID-[A-Z0-9]+\b"),
]

# Field-kind classes — structured / non-text HIPAA categories redacted wholesale.
_FIELD_CLASSES: list[FieldClass] = [
    FieldClass("name", 1, "field", field_name="patient_name"),
    FieldClass("geographic", 2, "field", field_name="address"),
    FieldClass("biometric", 16, "field", field_name="biometric_id"),
    FieldClass("full_face_photo", 17, "field", field_name="photo_ref"),
]


def reference_safe_harbor_catalog() -> list[FieldClass]:
    """Fresh catalog covering HIPAA categories 1–18 (new FieldClass objects each call)."""
    return [
        FieldClass(
            fc.name,
            fc.hipaa_category,
            fc.kind,
            pattern=fc.pattern,
            field_name=fc.field_name,
        )
        for fc in (*_REGEX_CLASSES, *_FIELD_CLASSES)
    ]


def labeled_text_sample() -> dict:
    """Free text containing one known value per text-detectable identifier class."""
    identifiers = {
        "date": ["1985-07-22"],
        "phone": ["(617) 555-0143"],
        "fax": ["fax 617-555-0188"],
        "email": ["jdoe@example.com"],
        "ssn": ["123-45-6789"],
        "mrn": ["MRN-558210"],
        "health_plan": ["HPN-99821"],
        "account": ["ACCT-4471920"],
        "license": ["LIC-DR4471"],
        "vehicle_vin": ["1HGCM82633A004352"],
        "device_serial": ["SN-XR12K99"],
        "url": ["https://portal.example.org/p/9"],
        "ip": ["10.0.12.45"],
        "other_unique_code": ["UID-7781ZZ"],
    }
    text = (
        "Patient DOB 1985-07-22 called from (617) 555-0143 and fax 617-555-0188. "
        "Contact jdoe@example.com, SSN 123-45-6789, record MRN-558210, plan HPN-99821, "
        "billing ACCT-4471920, license LIC-DR4471, vehicle 1HGCM82633A004352, "
        "monitor SN-XR12K99 synced to https://portal.example.org/p/9 from 10.0.12.45 "
        "ref UID-7781ZZ."
    )
    return {"text": text, "expected_identifiers": identifiers}


def structured_phi_record() -> tuple[dict, list[str]]:
    """A structured record plus the list of fields that hold PHI (field-kind classes)."""
    record = {
        "patient_name": "John Q. Public",
        "address": "417 Elm Street, Boston",
        "biometric_id": "FP-AB12CD34",
        "photo_ref": "facephoto-7781.jpg",
        "note": "Follow up scheduled; reachable at jdoe@example.com.",
        "age": 47,
    }
    phi_fields = ["patient_name", "address", "biometric_id", "photo_ref"]
    return record, phi_fields
