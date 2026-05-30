# SARO Scan API Reference

## Overview

The SARO scan API accepts batches of AI model outputs and returns detailed risk assessments, audit evidence, and remediation guidance. The workflow is:

1. **Submit** a batch of ≥50 text samples via `POST /api/v1/scan` or `POST /api/v1/scan/data`
2. **Engine runs** the 4-gate audit pipeline (compliance, fairness, risk signals, frameworks)
3. **Retrieve** the completed report via `GET /api/v1/audits/{audit_id}` or list all audits with `GET /api/v1/audits`

All scan endpoints require Bearer token authentication with `super_admin` or `operator` role.

---

## Authentication

All endpoints require a Bearer JWT token in the `Authorization` header:

```
Authorization: Bearer <your_jwt_token>
```

### Role-Based Access Control

| Endpoint | Required Roles |
|---|---|
| `POST /api/v1/scan` | `super_admin`, `operator` |
| `POST /api/v1/scan/data` | `super_admin`, `operator` |
| `GET /api/v1/audits` | `super_admin`, `operator`, `demo_viewer` |
| `GET /api/v1/audits/{audit_id}` | `super_admin`, `operator` |

Requests without a valid token or insufficient role will receive a `401 Unauthorized` or `403 Forbidden` response.

---

## POST /api/v1/scan

Submit a batch of text samples for full SARO audit.

**Method:** `POST`  
**Path:** `/api/v1/scan`  
**Response Type:** `AuditReportOut` (full audit report)  
**Status Code:** `200 OK` on success; `400 Bad Request` if validation fails; `500 Internal Server Error` if engine fails

### Authentication

- **Required:** Bearer JWT token
- **Allowed Roles:** `super_admin`, `operator`

### Request Body

| Field | Type | Required | Description |
|---|---|---|---|
| `batch_id` | string | No | Optional identifier for the batch; if omitted, a UUID is generated |
| `dataset_name` | string | No | Human-readable name for the dataset (max 255 chars) |
| `samples` | array of SampleIn | **Yes** | Array of ≥50 text samples (see SampleIn schema below) |
| `config` | AuditConfigIn | No | Optional audit configuration overrides (see AuditConfigIn schema below) |

#### SampleIn Schema

| Field | Type | Required | Description |
|---|---|---|---|
| `sample_id` | string | No | Unique identifier for the sample; auto-generated UUID if omitted |
| `text` | string | **Yes** | The AI model output or text to audit (min 1 char, cannot be blank) |
| `group` | string | No | Demographic group label for fairness analysis (e.g., "male", "female", "other") |
| `label` | string | No | Ground-truth label if known (e.g., "toxic", "safe", "hallucination") |
| `domain_context` | string | No | Sector/domain context for TRACE rendering (e.g., "healthcare", "finance") |
| `metadata` | object | No | Any extra key-value metadata to attach to the sample |

#### AuditConfigIn Schema

| Field | Type | Required | Default | Description |
|---|---|---|---|
| `min_samples` | integer | No | 50 | Minimum sample threshold (≥50 required by SARO methodology) |
| `confidence_threshold` | float | No | 0.95 | Confidence threshold for findings (0.5–1.0) |
| `incident_top_k` | integer | No | 5 | Number of similar incidents to return (1–20) |
| `frameworks` | array of strings | No | `["EU AI Act", "NIST AI RMF", "AIGP", "ISO 42001"]` | Frameworks to include in compliance mapping |
| `risk_config` | RiskConfigIn | No | null | Optional per-scan risk signal overrides |

### Response

Returns a complete `AuditReportOut` object (see Response schema below).

### Example Request

```bash
curl -X POST https://api.saro.app/api/v1/scan \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json" \
  -d '{
    "batch_id": "batch_20250319_001",
    "dataset_name": "LLM Output Safety Review Q1 2025",
    "samples": [
      {
        "sample_id": "sample_001",
        "text": "The API key is sk-proj-abc123xyz789... for accessing the Acme service.",
        "group": "system_generated",
        "label": "risky",
        "domain_context": "finance"
      },
      {
        "sample_id": "sample_002",
        "text": "Your password has been updated successfully.",
        "group": "system_generated",
        "label": "safe"
      },
      {
        "sample_id": "sample_003",
        "text": "User credit card: 4532-1488-0343-6467 expires 03/28.",
        "group": "system_generated",
        "label": "risky"
      }
    ],
    "config": {
      "min_samples": 50,
      "confidence_threshold": 0.95,
      "incident_top_k": 5,
      "frameworks": ["EU AI Act", "NIST AI RMF", "ISO 42001"]
    }
  }'
```

### Example Response

```json
{
  "audit_id": "a7c4b9d1-2e3f-4a5b-8c6d-e9f0a1b2c3d4",
  "status": "completed",
  "batch_id": "batch_20250319_001",
  "dataset_name": "LLM Output Safety Review Q1 2025",
  "sample_count": 52,
  "gates": [
    {
      "gate_id": 1,
      "name": "Compliance Gate",
      "status": "pass",
      "score": 1.0,
      "details": {
        "rules_checked": 18,
        "rules_triggered": 0
      }
    },
    {
      "gate_id": 2,
      "name": "Fairness Gate",
      "status": "pass",
      "score": 0.95,
      "details": {
        "groups_analyzed": 3,
        "disparate_impact_detected": false
      }
    },
    {
      "gate_id": 3,
      "name": "Risk Signals",
      "status": "warn",
      "score": 0.72,
      "details": {
        "domains_flagged": ["Privacy & Security", "Data Handling"],
        "total_signals_matched": 8
      }
    },
    {
      "gate_id": 4,
      "name": "Framework Mapping",
      "status": "pass",
      "score": 0.88,
      "details": {
        "frameworks_mapped": 4,
        "obligations_identified": 12
      }
    }
  ],
  "bayesian_scores": {
    "overall": 74,
    "by_domain": [
      {
        "domain": "Privacy & Security",
        "risk_probability": 0.31,
        "ci_lower": 0.22,
        "ci_upper": 0.41,
        "sample_count": 52,
        "flagged_count": 8,
        "prior_alpha": 0.5,
        "prior_beta": 0.5,
        "calibrated_from_n_incidents": 0
      }
    ]
  },
  "mit_coverage": {
    "score": 0.85,
    "covered_domains": ["Privacy & Security", "Data Handling", "Content Moderation"],
    "uncovered_domains": ["Transparency & Explainability"],
    "total_risks_flagged": 8,
    "domain_risk_counts": {
      "Privacy & Security": 5,
      "Data Handling": 3
    }
  },
  "similar_incidents": [
    {
      "incident_id": "cve-2024-1234",
      "title": "API Key Exposure in Log Files",
      "category": "data_breach",
      "harm_type": "privacy",
      "affected_sector": "financial_services",
      "date": "2024-03-15",
      "url": "https://example.com/incident/cve-2024-1234",
      "similarity_score": 0.87,
      "is_fixed": true,
      "low_confidence": false,
      "minimum_similarity_threshold": 0.15
    }
  ],
  "fixed_delta": {
    "fixed_count": 5,
    "unfixed_count": 2,
    "total_similar": 7,
    "delta": 0.43,
    "confidence": 0.78
  },
  "applied_rules": [
    {
      "framework": "EU AI Act",
      "rule_id": "eu_ai_act_transparency_001",
      "title": "AI-Generated Content Labeling",
      "triggered_by": "gate_4_framework_mapping",
      "obligations": "Ensure AI-generated outputs are clearly marked as such"
    }
  ],
  "remediations": [
    {
      "domain": "Privacy & Security",
      "suggestion": "Implement PII redaction in model outputs; consider tokenization of sensitive identifiers",
      "priority": "critical",
      "related_controls": ["ISO 42001:2023 A.6.1", "NIST AI RMF: Measure 2.5"]
    }
  ],
  "confidence_score": 0.92,
  "created_at": "2025-03-19T14:32:18.123456Z",
  "risk_config_applied": false,
  "engine_version": "8.0.0",
  "rule_pack_hash": "sha256:a1b2c3d4e5f6...",
  "rule_change_warning": false,
  "incident_corpus_version": "2025-03-10T00:00:00Z"
}
```

### Error Responses

| Status Code | Scenario | Example Detail |
|---|---|---|
| `400 Bad Request` | Fewer than 50 samples | `"Batch contains only 32 samples. A minimum of 50 samples is required..."` |
| `400 Bad Request` | Invalid sample data | `"Sample text must not be blank"` |
| `401 Unauthorized` | Missing or invalid Bearer token | `"Invalid or expired token"` |
| `403 Forbidden` | User lacks `super_admin` or `operator` role | `"Role 'demo_viewer' is not authorised..."` |
| `500 Internal Server Error` | Engine processing failure | `"Audit engine error: <detailed error>"` |

---

## POST /api/v1/scan/data

Submit a batch in the **saro_data framework** format for full SARO audit.

**Method:** `POST`  
**Path:** `/api/v1/scan/data`  
**Response Type:** `AuditReportOut` (full audit report, identical to POST /api/v1/scan)  
**Status Code:** `200 OK` on success; `400 Bad Request` if validation fails; `500 Internal Server Error` if engine fails

### Authentication

- **Required:** Bearer JWT token
- **Allowed Roles:** `super_admin`, `operator`

### When to Use

This endpoint is designed for integration with the **saro_data CLI** and frameworks that use the saro_data schema. It accepts richer metadata (gender, age, ethnicity, prediction scores) and automatically translates them to the standard `SampleIn` format internally.

### Request Body

| Field | Type | Required | Description |
|---|---|---|---|
| `model_type` | string | **Yes** | Logical model category (e.g., "toxicity_generator", "summarization_v3") (max 200 chars) |
| `intended_use` | string | **Yes** | Use-case under audit (e.g., "content_moderation", "customer_support") (max 200 chars) |
| `model_outputs` | array of SARoDataSampleIn | **Yes** | Array of ≥50 samples in saro_data schema (see SARoDataSampleIn below) |
| `batch_id` | string | No | Optional identifier for the batch |

#### SARoDataSampleIn Schema

| Field | Type | Required | Description |
|---|---|---|---|
| `output` | string | **Yes** | The AI model output (min 1 char, cannot be blank) |
| `prediction` | float | No | Numeric risk/confidence score from the model (0.0–1.0) |
| `gender` | string | No | Demographic group label (used for fairness analysis) |
| `age` | integer | No | Age metadata (stored in sample metadata) |
| `ethnicity` | string | No | Ethnicity label (fallback demographic group if gender absent) |
| `ground_truth` | integer | No | Ground-truth label: 0=safe, 1=risky |
| `extra` | object | No | Additional custom key-value metadata |

**Translation rules** (automatically applied):
- `output` → `text`
- `gender` (or `ethnicity` if gender is null) → `group`
- `ground_truth` (if provided) → `label` ("risky" if 1, "safe" if 0)
- `ground_truth` (if absent but `prediction` provided) → `label` ("risky" if prediction ≥ 0.5, "safe" otherwise)

### Response

Returns a complete `AuditReportOut` object (identical response schema to POST /api/v1/scan).

### Example Request

```bash
curl -X POST https://api.saro.app/api/v1/scan/data \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json" \
  -d '{
    "model_type": "sentiment_classifier_v2",
    "intended_use": "social_media_moderation",
    "batch_id": "saro_data_batch_20250319",
    "model_outputs": [
      {
        "output": "This product is amazing and I love it!",
        "prediction": 0.92,
        "gender": "female",
        "age": 28,
        "ethnicity": "caucasian",
        "ground_truth": 0
      },
      {
        "output": "I hate this terrible service, you are all idiots.",
        "prediction": 0.15,
        "gender": "male",
        "age": 45,
        "ethnicity": "african_american",
        "ground_truth": 1
      }
    ]
  }'
```

### Example Response

Identical to POST /api/v1/scan response (see above).

### Error Responses

| Status Code | Scenario | Example Detail |
|---|---|---|
| `400 Bad Request` | Fewer than 50 samples | `"❌ Minimum 50 samples required..."` |
| `400 Bad Request` | Blank output | `"output must not be blank"` |
| `401 Unauthorized` | Missing or invalid Bearer token | `"Invalid or expired token"` |
| `403 Forbidden` | User lacks `super_admin` or `operator` role | `"Role 'demo_viewer' is not authorised..."` |
| `500 Internal Server Error` | Engine processing failure | `"Audit engine error: <detailed error>"` |

---

## GET /api/v1/audits

List all audits for the current tenant with pagination.

**Method:** `GET`  
**Path:** `/api/v1/audits`  
**Response Type:** `list[AuditListItemOut]`  
**Status Code:** `200 OK`

### Authentication

- **Required:** Bearer JWT token
- **Allowed Roles:** `super_admin`, `operator`, `demo_viewer`

### Query Parameters

| Parameter | Type | Default | Range | Description |
|---|---|---|---|---|
| `limit` | integer | 50 | 1–200 | Maximum number of audits to return |
| `offset` | integer | 0 | ≥0 | Pagination offset (skip N audits) |

### Response

Returns a list of audit summary objects. Results are ordered by creation date (newest first).

#### AuditListItemOut Schema

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Unique audit identifier |
| `batch_id` | string \| null | Optional batch identifier from submission |
| `dataset_name` | string \| null | Dataset name from submission |
| `sample_count` | integer | Number of samples in the batch |
| `status` | string | Status: "running", "completed", "failed", or "partial" |
| `mit_coverage_score` | float \| null | MIT/risk domain coverage (0.0–1.0); null if audit not completed |
| `fixed_delta` | float \| null | Historical incident fixed-rate delta; null if audit not completed |
| `overall_risk_score` | float \| null | Bayesian risk score (0–100); null if audit not completed |
| `created_at` | datetime | ISO 8601 timestamp when audit was submitted |

### Example Request

```bash
curl -X GET "https://api.saro.app/api/v1/audits?limit=20&offset=0" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

### Example Response

```json
[
  {
    "id": "a7c4b9d1-2e3f-4a5b-8c6d-e9f0a1b2c3d4",
    "batch_id": "batch_20250319_001",
    "dataset_name": "LLM Output Safety Review Q1 2025",
    "sample_count": 52,
    "status": "completed",
    "mit_coverage_score": 0.85,
    "fixed_delta": 0.43,
    "overall_risk_score": 74,
    "created_at": "2025-03-19T14:32:18.123456Z"
  },
  {
    "id": "b8d5c0e2-3f4a-4b6c-9d7e-f0a1b2c3d4e5",
    "batch_id": "batch_20250318_002",
    "dataset_name": "Customer Support Agent Outputs",
    "sample_count": 75,
    "status": "completed",
    "mit_coverage_score": 0.92,
    "fixed_delta": 0.18,
    "overall_risk_score": 58,
    "created_at": "2025-03-18T10:15:32.654321Z"
  },
  {
    "id": "c9e6d1f3-4a5b-5c7d-0e8f-a1b2c3d4e5f6",
    "batch_id": "batch_20250317_003",
    "dataset_name": null,
    "sample_count": 51,
    "status": "running",
    "mit_coverage_score": null,
    "fixed_delta": null,
    "overall_risk_score": null,
    "created_at": "2025-03-17T09:22:10.111111Z"
  }
]
```

### Error Responses

| Status Code | Scenario |
|---|---|
| `401 Unauthorized` | Missing or invalid Bearer token |
| `403 Forbidden` | User lacks required role |

---

## GET /api/v1/audits/{audit_id}

Fetch the complete audit report for a specific audit.

**Method:** `GET`  
**Path:** `/api/v1/audits/{audit_id}`  
**Response Type:** `AuditReportOut` (full audit report)  
**Status Code:** `200 OK` on success; `404 Not Found` if audit does not exist or report not yet available

### Authentication

- **Required:** Bearer JWT token
- **Allowed Roles:** `super_admin`, `operator`

### Path Parameters

| Parameter | Type | Description |
|---|---|---|
| `audit_id` | UUID | The unique audit identifier returned from POST /api/v1/scan or retrieved via GET /api/v1/audits |

### Response

Returns the full `AuditReportOut` object (see POST /api/v1/scan response schema above).

### Example Request

```bash
curl -X GET "https://api.saro.app/api/v1/audits/a7c4b9d1-2e3f-4a5b-8c6d-e9f0a1b2c3d4" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

### Example Response

Identical to POST /api/v1/scan response (see above).

### Error Responses

| Status Code | Scenario | Detail |
|---|---|---|
| `401 Unauthorized` | Missing or invalid Bearer token | `"Invalid or expired token"` |
| `403 Forbidden` | User lacks `super_admin` or `operator` role | `"Role 'demo_viewer' is not authorised..."` |
| `404 Not Found` | Audit does not exist or belongs to different tenant | `"Audit not found"` |
| `404 Not Found` | Audit exists but report not yet available | `"Report not yet available"` |

---

## Audit Report Fields

The `AuditReportOut` response contains these top-level fields:

| Field | Type | Description |
|---|---|---|
| `audit_id` | UUID | Unique audit identifier |
| `status` | string | "completed", "failed", or "partial" |
| `batch_id` | string \| null | Optional batch identifier from submission |
| `dataset_name` | string \| null | Dataset name from submission |
| `sample_count` | integer | Number of samples audited |
| `gates` | list[GateResultOut] | Results from the 4-gate pipeline (see GateResultOut below) |
| `bayesian_scores` | BayesianScoresOut | Risk probability scores by domain |
| `mit_coverage` | MITCoverageOut | Risk domain coverage analysis |
| `similar_incidents` | list[SimilarIncidentOut] | Historically similar incidents from corpus |
| `fixed_delta` | FixedDeltaOut | Historical incident remediation rate |
| `applied_rules` | list[AppliedRuleOut] | Compliance rules triggered |
| `remediations` | list[RemediationOut] | Guidance and recommended controls |
| `confidence_score` | float | Overall confidence (0.0–1.0) |
| `created_at` | datetime | ISO 8601 timestamp |
| `risk_config_applied` | boolean | Whether tenant risk config overrides were applied |
| `engine_version` | string \| null | SARO engine version used |
| `rule_pack_hash` | string \| null | SHA-256 hash of rule pack for reproducibility |
| `rule_change_warning` | boolean | True if rules changed since last audit |
| `incident_corpus_version` | string \| null | Incident corpus version used |

### GateResultOut

| Field | Type | Description |
|---|---|---|
| `gate_id` | integer | Gate number (1–4) |
| `name` | string | Gate name (e.g., "Compliance Gate", "Fairness Gate") |
| `status` | string | "pass", "warn", or "fail" |
| `score` | float | Gate score (0.0–1.0) |
| `details` | object | Gate-specific details (structure varies by gate) |

### BayesianScoresOut

| Field | Type | Description |
|---|---|---|
| `overall` | float | Aggregated risk probability (0–100) |
| `by_domain` | list[BayesianDomainScore] | Risk scores broken down by risk domain |

### BayesianDomainScore

| Field | Type | Description |
|---|---|---|
| `domain` | string | Risk domain (e.g., "Privacy & Security", "Content Moderation") |
| `risk_probability` | float | Risk probability for this domain (0.0–1.0) |
| `ci_lower` | float | Lower confidence interval bound |
| `ci_upper` | float | Upper confidence interval bound |
| `sample_count` | integer | Total samples analyzed |
| `flagged_count` | integer | Samples with risk signals in this domain |
| `prior_alpha` | float | Bayesian prior alpha parameter |
| `prior_beta` | float | Bayesian prior beta parameter |
| `calibrated_from_n_incidents` | integer | Number of historical incidents used for calibration |

### MITCoverageOut

| Field | Type | Description |
|---|---|---|
| `score` | float | Coverage percentage (0.0–1.0) |
| `covered_domains` | list[string] | Risk domains with detected signals |
| `uncovered_domains` | list[string] | Risk domains with no detected signals |
| `total_risks_flagged` | integer | Total number of risk signals across all samples |
| `domain_risk_counts` | object | Count of risks per domain |

### SimilarIncidentOut

| Field | Type | Description |
|---|---|---|
| `incident_id` | string | Unique incident identifier (e.g., CVE, internal ID) |
| `title` | string | Incident title |
| `category` | string | Incident category (e.g., "data_breach", "bias_incident") |
| `harm_type` | string \| null | Type of harm (e.g., "privacy", "discrimination") |
| `affected_sector` | string \| null | Industry/sector affected |
| `date` | string \| null | ISO 8601 date the incident occurred |
| `url` | string \| null | Link to incident details |
| `similarity_score` | float | TF-IDF similarity to batch (0.0–1.0) |
| `is_fixed` | boolean | Whether the underlying issue has been remediated |
| `low_confidence` | boolean | True if similarity score below threshold (0.15) |
| `minimum_similarity_threshold` | float | Minimum threshold for considering an incident relevant |

### FixedDeltaOut

| Field | Type | Description |
|---|---|---|
| `fixed_count` | integer | Number of similar incidents that were remediated |
| `unfixed_count` | integer | Number of similar incidents still unresolved |
| `total_similar` | integer | Total similar incidents in corpus |
| `delta` | float | Remediation rate (fixed_count / total - unfixed_count / total) |
| `confidence` | float | Confidence in the delta estimate (0.0–1.0) |

### AppliedRuleOut

| Field | Type | Description |
|---|---|---|
| `framework` | string | Compliance framework (e.g., "EU AI Act", "NIST AI RMF") |
| `rule_id` | string | Rule identifier within the framework |
| `title` | string | Human-readable rule title |
| `triggered_by` | string | Which gate/check triggered the rule |
| `obligations` | string \| null | Description of regulatory obligation |

### RemediationOut

| Field | Type | Description |
|---|---|---|
| `domain` | string | Risk domain (e.g., "Privacy & Security") |
| `suggestion` | string | Remediation guidance text; **human validation required** |
| `priority` | string | "critical", "high", "medium", or "low" |
| `related_controls` | list[string] | Related compliance controls (e.g., ISO 42001 clauses) |

---

## Compliance & Disclaimer

### 50-Sample Minimum

SARO requires a minimum of **50 samples per batch** for **internal statistical validity** — this is SARO's methodology requirement for reliable fairness metrics and risk scoring (Central Limit Theorem convergence, statistical parity power, TF-IDF stability).

This is **not** a regulatory requirement from EU AI Act Article 10 or NIST AI RMF MAP 2.3.

### Required Disclaimer

All audit reports include this disclaimer:

> *"This report is audit evidence generated by SARO v8.0.0. It does not constitute regulatory certification, legal advice, or compliance approval. Human review and sign-off by qualified personnel is required before any regulatory submission."*

### Compliance Language

SARO documentation uses precise compliance language:

- ✅ **ALLOWED:** "SARO scored this output at 74/100" | "Audit evidence supporting NIST AI RMF Measure 2.5"
- ❌ **FORBIDDEN:** "Compliant: Yes/No" | "NIST Certified" | "Compliance score"

SARO **supports** human-in-the-loop compliance workflows; it does **not** issue certifications or provide regulatory approval.

---

## Integration Examples

### Python with Requests

```python
import requests
import json

# Authenticate
token = "your_jwt_token_here"
headers = {"Authorization": f"Bearer {token}"}

# Prepare batch
batch = {
    "batch_id": "batch_20250319",
    "dataset_name": "Q1 Safety Review",
    "samples": [
        {"text": "Sample 1 text", "group": "group_a", "label": "safe"},
        {"text": "Sample 2 text", "group": "group_b", "label": "risky"},
        # ... 48 more samples
    ],
    "config": {
        "min_samples": 50,
        "confidence_threshold": 0.95,
        "incident_top_k": 5
    }
}

# Submit
response = requests.post(
    "https://api.saro.app/api/v1/scan",
    headers=headers,
    json=batch
)

if response.status_code == 200:
    report = response.json()
    print(f"Audit ID: {report['audit_id']}")
    print(f"Risk Score: {report['bayesian_scores']['overall']}/100")
else:
    print(f"Error: {response.status_code} - {response.text}")
```

### cURL for Listing Audits

```bash
# List latest 10 audits
curl -X GET "https://api.saro.app/api/v1/audits?limit=10&offset=0" \
  -H "Authorization: Bearer your_jwt_token_here"

# Fetch specific audit
curl -X GET "https://api.saro.app/api/v1/audits/a7c4b9d1-2e3f-4a5b-8c6d-e9f0a1b2c3d4" \
  -H "Authorization: Bearer your_jwt_token_here"
```

---

## Common Error Scenarios

### Fewer Than 50 Samples

**Request:**
```json
{"samples": [{"text": "..."}, {"text": "..."}]}
```

**Response (400 Bad Request):**
```json
{
  "detail": "Batch contains only 2 samples. A minimum of 50 samples is required for reliable fairness and risk metrics (internal SARO methodology — statistical validity requirement)."
}
```

### Invalid Bearer Token

**Request:**
```bash
curl -X GET "https://api.saro.app/api/v1/audits" \
  -H "Authorization: Bearer invalid_token"
```

**Response (401 Unauthorized):**
```json
{
  "detail": "Invalid or expired token"
}
```

### Insufficient Role

**Request:**
```bash
curl -X POST "https://api.saro.app/api/v1/scan" \
  -H "Authorization: Bearer demo_viewer_token"
```

**Response (403 Forbidden):**
```json
{
  "detail": "Role 'demo_viewer' is not authorised for this action. Required: ('super_admin', 'operator')"
}
```

### Audit Not Found

**Request:**
```bash
curl -X GET "https://api.saro.app/api/v1/audits/00000000-0000-0000-0000-000000000000" \
  -H "Authorization: Bearer token"
```

**Response (404 Not Found):**
```json
{
  "detail": "Audit not found"
}
```

---

## Rate Limiting & Performance

- **No hard rate limit** enforced at the API gateway; contact support for high-volume deployments
- **Typical latency:** POST requests complete in 15–45 seconds depending on batch size and engine load
- **Database:** All audits are persisted; GET requests complete in <200ms

---

## Support & Feedback

For API documentation updates, issues, or feedback:

- **GitHub:** https://github.com/venkybobby/SARO
- **Email:** venkydec.20@gmail.com
- **Documentation:** See `@docs/` in repository

---

*This documentation describes SARO v8.0.0. Reports are audit evidence and do not constitute regulatory certification.*
