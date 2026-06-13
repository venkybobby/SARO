# STORY-NAV-001: Implement responsive sidebar with collapse toggle and mobile drawer

**Status:** ready
**Screen/Area:** Navigation & Global Components

## Goal
Replace the fixed-width sidebar with a responsive design. On desktop (≥768px), a visible toggle button collapses the sidebar to icon-only mode. On mobile (<768px), the sidebar becomes a slide-out drawer with a hamburger menu button in the header. Users can dismiss the drawer by clicking outside it or pressing Escape.

## Acceptance Criteria (Given/When/Then — required before /story will run)
- AC-1: Given the viewport is ≥768px (desktop), When the page renders, Then a collapse toggle button is visible in the sidebar header (chevron icon or ⋮)
- AC-2: Given the user clicks the collapse toggle on desktop, When the click occurs, Then the sidebar collapses to icon-only width (~60px) and all nav text is hidden
- AC-3: Given the sidebar is collapsed, When the user hovers over a nav icon, Then a tooltip shows the full nav label
- AC-4: Given the viewport is <768px (mobile), When the page renders, Then a hamburger menu button is visible in the top navbar and the sidebar is hidden off-canvas
- AC-5: Given the hamburger menu is clicked on mobile, When the click occurs, Then the sidebar slides in from the left as an overlay/drawer with a semi-transparent backdrop
- AC-6: Given the drawer is open on mobile, When the user clicks outside the drawer or presses Escape, Then the drawer slides out and the page is fully accessible again
- AC-7: Given a nav item is selected in the drawer (mobile), When the selection occurs, Then the drawer automatically closes
- AC-8: Given the sidebar state is toggled, When the page is reloaded, Then the previous collapse/expand state is restored (saved to localStorage)

## Edge Cases
- User resizes from desktop to mobile while sidebar is collapsed → drawer appears in correct state
- Touch-drag on the drawer edge → should not conflict with hamburger menu behavior
- Sidebar is open and user opens a modal → backdrop z-index must not conflict

## Out of Scope
- Animated hamburger menu icon rotation (nice-to-have for v8.1)
- Swipe-to-open on mobile (fine as enhancement)
- Nested submenu expansion in drawer

## Non-Functional Requirements
- Collapse/expand toggle: <100ms animation
- Drawer open/close: <200ms slide animation
- Hamburger button is at least 44x44px for touch targets
- Sidebar collapse/expand state persists in localStorage with key "saro-sidebar-collapsed"
- Drawer backdrop is keyboard-dismissible (Escape key)

## Traceability (filled at close by /story)
| AC | Test(s) | Files |
|---|---|---|
| AC-1 | visual_desktop_collapse_toggle | Sidebar.jsx, App.jsx |
| AC-2 | e2e_desktop_collapse_click | Sidebar.jsx |
| AC-3 | e2e_collapsed_icon_tooltip | Sidebar.jsx, ui/Tooltip.jsx |
| AC-4 | visual_mobile_hamburger_menu | Sidebar.jsx, App.jsx |
| AC-5 | e2e_mobile_drawer_open | Sidebar.jsx |
| AC-6 | e2e_mobile_drawer_close_backdrop, e2e_drawer_escape_key | Sidebar.jsx |
| AC-7 | e2e_drawer_auto_close_on_select | Sidebar.jsx |
| AC-8 | test_sidebar_state_localStorage | Sidebar.jsx, utils/storage.js |

---
