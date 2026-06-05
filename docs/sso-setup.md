# SARO SAML 2.0 SSO Setup Guide

## Overview
SARO supports SP-initiated SAML 2.0 SSO. This guide covers Okta configuration.

## Prerequisites
- Okta Developer account or Okta org with admin access
- SARO tenant slug (provided by your SARO administrator)
- SARO SP metadata URL: `https://saro-platform.fly.dev/api/v1/sso/metadata/{tenant_slug}`

## Okta Configuration

### Step 1: Create a SAML App in Okta
1. In Okta Admin Console → Applications → Create App Integration
2. Select **SAML 2.0** → Next
3. App name: `SARO`

### Step 2: Configure SAML Settings
| Field | Value |
|-------|-------|
| Single sign on URL | `https://saro-platform.fly.dev/api/v1/sso/acs/{tenant_slug}` |
| Audience URI (SP Entity ID) | `https://saro.app/sp` |
| Name ID format | EmailAddress |
| Application username | Email |

### Step 3: Attribute Statements
Add the following attribute:
| Name | Value |
|------|-------|
| `persona_role` | `user.department` (or a custom Okta attribute mapping to: `compliance_lead`, `risk_officer`, `ai_auditor`, `admin`) |

### Step 4: Download IdP Metadata
1. In the Okta app → Sign On tab → View SAML setup instructions
2. Download the **Identity Provider metadata** XML
3. Provide this XML to your SARO administrator to configure via the SARO API:

```http
PATCH /api/v1/tenants/{tenant_id}/config
{
  "sso_enabled": true,
  "idp_provider": "okta",
  "idp_metadata": { ... }  // parsed IdP metadata object
}
```

### Step 5: Test SSO Login
1. Navigate to: `https://saro-platform.fly.dev/api/v1/sso/login/{tenant_slug}`
2. You will be redirected to Okta for authentication
3. After successful login, you will be redirected to the SARO dashboard

## Persona Role Mapping
SARO maps the `persona_role` SAML attribute to UI access:
| Attribute Value | SARO Persona | Default Landing |
|----------------|--------------|-----------------|
| `compliance_lead` | Compliance Lead | Compliance Hub |
| `risk_officer` | Risk Officer | Risk Summary |
| `ai_auditor` | AI Auditor | Dashboard |
| `admin` | Admin | Dashboard |

If no `persona_role` attribute is sent, users default to `compliance_lead`.

## MFA Requirements
If your tenant has `mfa_required: true`, SARO validates that the SAML assertion includes an MFA authentication context class. Ensure Okta enforces MFA before issuing the assertion.

## Troubleshooting
| Error | Cause | Fix |
|-------|-------|-----|
| `SAMLResponse signature missing` | Okta not signing response | Enable response signing in Okta app settings |
| `assertion_expired` | Clock skew > 5 min | Sync server clock with NTP |
| `mfa_required` | Tenant requires MFA but IdP not asserting it | Enable MFA policy in Okta |
| `magic_link_disabled` | Tenant has `allow_magic_link_fallback: false` | Use SSO login URL instead |

## Environment Variables (Backend)
```
SAML_SP_ENTITY_ID=https://saro.app/sp
SAML_SP_ACS_URL=https://saro-platform.fly.dev/api/v1/sso/acs
SAML_SP_CERT=<base64 PEM certificate>
SAML_SP_KEY=<base64 PEM private key>
```
