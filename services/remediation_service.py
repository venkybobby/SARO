"""Remediation steps service — structured actionable fix plans with effort estimates."""
from typing import Optional


VALID_EFFORT_RANGES = ["1-2 hours", "half-day", "1 day", "2-3 days", "1 week", "2+ weeks"]
VALID_ROLES = ["Developer", "ML Engineer", "Compliance Officer", "Legal Counsel",
               "Data Scientist", "Security Engineer", "Product Manager"]


def validate_remediation_step(step: dict) -> tuple[bool, list[str]]:
    """Validate a remediation step has all required fields with valid values.

    Returns: (is_valid, list_of_errors)
    """
    errors = []
    required = ["description", "effort_estimate", "suggested_role", "reference_clause"]
    for field in required:
        if field not in step or not step[field]:
            errors.append(f"Missing required field: {field}")

    if "effort_estimate" in step and step["effort_estimate"]:
        estimate = step["effort_estimate"]
        # Accept any string but warn if not in standard ranges
        if not isinstance(estimate, str):
            errors.append(f"effort_estimate must be a string, got {type(estimate)}")

    return len(errors) == 0, errors


def generate_remediation_steps(finding: dict) -> list[dict]:
    """Generate structured remediation steps for a given finding.

    Args:
        finding: Dict with keys: rule_id, severity, description, check_type

    Returns:
        List of remediation step dicts with all required fields
    """
    rule_id = finding.get("rule_id", "UNKNOWN")
    severity = finding.get("severity", "MEDIUM").upper()
    description = finding.get("description", "")

    # Base steps by rule category
    if "BIAS" in rule_id.upper() or "FAIRNESS" in rule_id.upper() or "MEASURE" in rule_id:
        steps = [
            {
                "step_number": 1,
                "description": "Audit training data for demographic representation imbalances",
                "effort_estimate": "2-3 days",
                "suggested_role": "Data Scientist",
                "reference_clause": f"{rule_id} — Measure category",
            },
            {
                "step_number": 2,
                "description": "Run fairness metrics (demographic parity, equal opportunity) on model outputs",
                "effort_estimate": "1 day",
                "suggested_role": "ML Engineer",
                "reference_clause": "NIST AI RMF — MEASURE 2.5",
            },
            {
                "step_number": 3,
                "description": "Document bias mitigation measures and retest",
                "effort_estimate": "1 day",
                "suggested_role": "Compliance Officer",
                "reference_clause": f"{rule_id}",
            },
        ]
    elif "GOVERN" in rule_id.upper() or "POLICY" in rule_id.upper():
        steps = [
            {
                "step_number": 1,
                "description": "Draft AI governance policy covering this AI system's risk domain",
                "effort_estimate": "1 week",
                "suggested_role": "Compliance Officer",
                "reference_clause": f"{rule_id} — Govern category",
            },
            {
                "step_number": 2,
                "description": "Review draft with legal counsel and obtain approval",
                "effort_estimate": "2-3 days",
                "suggested_role": "Legal Counsel",
                "reference_clause": "NIST AI RMF — GOVERN 1.1",
            },
        ]
    elif "TRANS" in rule_id.upper() or "ART13" in rule_id.upper():
        steps = [
            {
                "step_number": 1,
                "description": "Add AI disclosure statement to user-facing communications",
                "effort_estimate": "half-day",
                "suggested_role": "Product Manager",
                "reference_clause": f"{rule_id} — Transparency obligation",
            },
            {
                "step_number": 2,
                "description": "Update terms of service to disclose AI usage",
                "effort_estimate": "1-2 hours",
                "suggested_role": "Legal Counsel",
                "reference_clause": "EU AI Act Article 13",
            },
        ]
    elif "HUMAN" in rule_id.upper() or "ART14" in rule_id.upper() or "OVERSIGHT" in rule_id.upper():
        steps = [
            {
                "step_number": 1,
                "description": "Implement a human review queue for all AI decisions above risk threshold",
                "effort_estimate": "2-3 days",
                "suggested_role": "Developer",
                "reference_clause": f"{rule_id} — Human oversight",
            },
            {
                "step_number": 2,
                "description": "Add audit log entry for each human review and override",
                "effort_estimate": "1 day",
                "suggested_role": "Developer",
                "reference_clause": "EU AI Act Article 14",
            },
        ]
    else:
        # Generic remediation steps
        steps = [
            {
                "step_number": 1,
                "description": f"Investigate root cause of: {description[:100]}",
                "effort_estimate": "1 day",
                "suggested_role": "ML Engineer",
                "reference_clause": rule_id,
            },
            {
                "step_number": 2,
                "description": "Implement fix and verify with targeted test case",
                "effort_estimate": "1-2 hours",
                "suggested_role": "Developer",
                "reference_clause": rule_id,
            },
            {
                "step_number": 3,
                "description": "Document remediation in audit trail and update evidence pack",
                "effort_estimate": "1-2 hours",
                "suggested_role": "Compliance Officer",
                "reference_clause": rule_id,
            },
        ]

    return steps
