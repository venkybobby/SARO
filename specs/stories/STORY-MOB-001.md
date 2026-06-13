# STORY-MOB-001: Build mobile navigation with collapsible sidebar and hamburger menu (foundational)

**Status:** ready
**Screen/Area:** Responsive / Mobile Experience

## Goal
This story is the mobile counterpart to NAV-001 (Implement responsive sidebar). At <768px viewport, implement a hamburger menu button in the top navbar that toggles a slide-out drawer containing the sidebar. This is the single largest gap blocking mobile usability.

## Acceptance Criteria (Given/When/Then — required before /story will run)
- AC-1: Given the viewport is <768px, When the page renders, Then a hamburger menu button (☰ or icon) is visible in the top-left of the navbar
- AC-2: Given the hamburger button is clicked, When the click occurs, Then the sidebar slides in from the left as an overlay with a semi-transparent backdrop covering the main content
- AC-3: Given the drawer is open, When the user clicks outside the sidebar (on the backdrop) or presses Escape, Then the drawer slides out and the main content is fully accessible
- AC-4: Given a nav item is selected in the drawer, When the selection occurs, Then the drawer automatically closes and the main content updates
- AC-5: Given the viewport is resized from mobile (<768px) to desktop (≥768px), When the resize occurs, Then the drawer is hidden and the normal sidebar layout is shown
- AC-6: Given the user's theme is dark mode, When the drawer is open, Then the drawer background matches the dark theme palette

## Edge Cases
- Hamburger menu is clicked while drawer is already open → drawer closes (toggle behavior)
- Touch-drag on drawer edge → should allow swiping the drawer closed
- Content below the fold needs scroll → drawer should be scrollable independently

## Out of Scope
- Swipe gestures beyond basic slide-in/out
- Animated hamburger menu icon (nice-to-have)

## Non-Functional Requirements
- Hamburger button is at least 44x44px for touch targets
- Drawer animation: <200ms slide
- Drawer z-index must be above main content but below any modals
- No horizontal scroll introduced by drawer open/close

## Traceability (filled at close by /story)
| AC | Test(s) | Files |
|---|---|---|
| AC-1 | visual_mobile_hamburger | Sidebar.jsx, App.jsx, global.css |
| AC-2 | e2e_mobile_drawer_open | Sidebar.jsx |
| AC-3 | e2e_mobile_drawer_close | Sidebar.jsx |
| AC-4 | e2e_mobile_nav_close_on_select | Sidebar.jsx |
| AC-5 | e2e_responsive_drawer_layout | Sidebar.jsx, App.jsx |
| AC-6 | visual_dark_theme_drawer | Sidebar.jsx, global.css |

---
