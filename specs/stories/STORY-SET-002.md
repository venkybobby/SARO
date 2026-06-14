# STORY-SET-002: Wire Settings > General Settings to persist orgName via PATCH /api/v1/tenants/{id}

**Status:** ready
**Screen/Area:** Settings / Configuration

## Goal
Replace the fake success toast with a real API call. When the user changes the organization name in General Settings and clicks "Save changes", the orgName is persisted to the backend and reflects in the sidebar on next load (or immediately via state update).

## Acceptance Criteria (Given/When/Then — required before /story will run)
- AC-1: Given the user enters a new organization name, When they click "Save changes", Then a PATCH request is sent to `/api/v1/tenants/{tenantId}` with `{ "orgName": "New Name" }`
- AC-2: Given the PATCH request succeeds (200 OK), When the response is received, Then a toast shows "Organization name updated successfully" and the sidebar immediately reflects the new name
- AC-3: Given the PATCH request fails (e.g., 400, 409), When the response is received, Then an error toast shows the error message (e.g., "Name already in use") and the form reverts to the previous value
- AC-4: Given the user is updating the org name, When the request is in flight, Then the "Save changes" button is disabled and shows a loading spinner
- AC-5: Given the user hasn't changed any fields, When they click "Save changes", Then no API call is made (compare current state to initial state)

## Edge Cases
- User submits an empty or whitespace-only org name → client-side validation rejects it with "Name cannot be empty"
- Org name contains special characters (emoji, RTL text, etc.) → server accepts and stores; client displays correctly
- Network timeout during PATCH → show a retry button and keep the form open

## Out of Scope
- Updating other tenant-level settings (those come in follow-up stories)
- Audit logging of who changed the org name (covered in Audit Trail)
- Cascading updates to other systems (e.g., email headers)

## Non-Functional Requirements
- API latency: typical <500ms
- Form input validation (client-side) triggers before API call
- Toast dismissal time: 4s or manual close
- Button disabled state is clear (opacity, cursor: not-allowed)

## Traceability (filled at close by /story)
| AC | Test(s) | Files |
|---|---|---|
| AC-1 | test_patch_tenants_request | components/GeneralSettings.jsx, api/tenantService.js |
| AC-2 | e2e_org_name_update_success | components/GeneralSettings.jsx, Sidebar.jsx |
| AC-3 | test_patch_error_handling | api/tenantService.js, components/GeneralSettings.jsx |
| AC-4 | visual_save_button_loading_state | components/GeneralSettings.jsx |
| AC-5 | test_no_change_no_api_call | components/GeneralSettings.jsx |

---
