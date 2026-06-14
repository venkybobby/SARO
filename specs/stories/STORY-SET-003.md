# STORY-SET-003: Make Permissions Matrix editable (toggle role permissions with save action)

**Status:** ready
**Screen/Area:** Settings / Configuration

## Goal
Convert the read-only Users & Permissions table into an interactive matrix where admins can toggle permissions per role. Changes are saved via a single "Save Permission Changes" button at the bottom of the section.

## Acceptance Criteria (Given/When/Then — required before /story will run)
- AC-1: Given the Permissions Matrix is displayed, When a permission cell is clicked, Then it becomes editable (checkbox or toggle switch)
- AC-2: Given a permission checkbox is toggled, When the checkbox state changes, Then the change is marked visually (row highlights, or cell shows "modified" indicator)
- AC-3: Given the user has modified one or more permissions, When they click "Save Permission Changes", Then a PATCH request is sent to `/api/v1/tenants/{id}/permissions` with the modified role-permission pairs
- AC-4: Given the PATCH request succeeds, When the response is received, Then a toast shows "Permissions updated" and the visual "modified" indicators disappear
- AC-5: Given the user modified permissions but clicks "Cancel", When the button is clicked, Then all changes are reverted and the table shows the previous state

## Edge Cases
- User tries to remove all permissions from a role → show a warning: "At least one permission must be assigned per role"
- User's own role is being modified → allow the change but warn "You are modifying your own permissions"
- Permission change conflicts with a recently-applied backend change → show a conflict dialog and reload the current state

## Out of Scope
- Creating new roles (covered in a future RBAC epic)
- Time-based or conditional permissions
- Permission inheritance or role hierarchies

## Non-Functional Requirements
- Permissions table must be keyboard-navigable (Tab between cells, Space/Enter to toggle)
- Each cell must have an aria-label describing the role and permission
- Save/Cancel buttons only appear when changes are detected
- PATCH latency: <1s typical

## Traceability (filled at close by /story)
| AC | Test(s) | Files |
|---|---|---|
| AC-1 | e2e_permission_cell_edit | components/PermissionsMatrix.jsx |
| AC-2 | visual_modified_row_highlight | components/PermissionsMatrix.jsx, global.css |
| AC-3 | test_patch_permissions_request | api/tenantService.js, components/PermissionsMatrix.jsx |
| AC-4 | e2e_permissions_save_success | components/PermissionsMatrix.jsx |
| AC-5 | test_permissions_cancel_revert | components/PermissionsMatrix.jsx |

---
