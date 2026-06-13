# STORY-NAV-006: Add aria-label grouping to Sidebar navigation sections

**Status:** draft
**Screen/Area:** Navigation & Global Components

## Goal
Enhance the Sidebar nav landmark with clearer aria-label groupings. Break the single `<nav aria-label="Main navigation">` into logical sections ("Workspace Navigation", "Persona", "User Menu") or add nested landmark structure so screen readers can announce the nav organization.

## Acceptance Criteria (Given/When/Then — required before /story will run)
- AC-1: Given the Sidebar is rendered, When a screen reader user navigates to the nav, Then the nav is announced with a descriptive aria-label (e.g., "Main navigation")
- AC-2: Given the nav contains "switch persona", "nav items", and "sign out", When a screen reader user navigates the nav, Then they can distinguish these sections (via aria-label, <section>, or <nav> nesting)
- AC-3: Given nav items are listed, When a screen reader user reads them, Then each item's aria-label clearly describes its purpose (e.g., "Dashboard" vs. "Switch to Finance Persona")

## Edge Cases
- Nested navs might confuse some screen readers → test with NVDA, JAWS, VoiceOver

## Out of Scope
- Custom landmark navigation UI
- Screen reader-only content beyond aria-labels

## Non-Functional Requirements
- No visual change (CSS-agnostic)
- All screen reader testing must pass with major readers (NVDA, JAWS, VoiceOver)

## Traceability (filled at close by /story)
| AC | Test(s) | Files |
|---|---|---|
| AC-1 | a11y_nav_landmark_aria | Sidebar.jsx |
| AC-2 | a11y_nav_section_grouping | Sidebar.jsx |
| AC-3 | a11y_nav_item_aria_labels | Sidebar.jsx |

---
