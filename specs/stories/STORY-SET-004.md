# STORY-SET-004: Add "Role permissions are fixed in this release" clarification if matrix remains read-only

**Status:** draft
**Screen/Area:** Settings / Configuration

## Goal
If the decision is made to keep the Permissions Matrix read-only for v8.0 (instead of making it editable in SET-003), add a clear header note or information icon that explains "Role permissions are managed by your administrator and cannot be changed in this release."

## Acceptance Criteria (Given/When/Then — required before /story will run)
- AC-1: Given the Permissions Matrix section is displayed, When the user views it, Then a header note or info callout clearly states "Permissions are managed by your administrator" or "Editable permissions coming in v8.1"
- AC-2: Given the user hovers over or focuses the info icon, When the hover/focus occurs, Then a tooltip or popover provides context (e.g., "Contact your admin to request permission changes")
- AC-3: Given the matrix is read-only, When the user attempts to click a cell, Then no visual change occurs and the cursor remains default (not pointer)

## Edge Cases
- Admin role vs. non-admin viewing the matrix → both see the same message (or customize message based on role)

## Out of Scope
- Implementing editable matrix (that's SET-003)
- Admin request/approval workflow for permission changes

## Non-Functional Requirements
- Info callout is visually distinct but not alarming (compare to ConfirmDialog danger styling)
- Tooltip is keyboard-accessible

## Traceability (filled at close by /story)
| AC | Test(s) | Files |
|---|---|---|
| AC-1 | visual_permissions_read_only_note | components/PermissionsMatrix.jsx |
| AC-2 | e2e_info_icon_tooltip | components/PermissionsMatrix.jsx, ui/Tooltip.jsx |
| AC-3 | test_read_only_cell_no_edit | components/PermissionsMatrix.jsx |

---
