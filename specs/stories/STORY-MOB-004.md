# STORY-MOB-004: Convert Settings page two-column layout to horizontal tab bar on mobile

**Status:** ready
**Screen/Area:** Responsive / Mobile Experience

## Goal
At <768px viewport, the Settings page's left-nav sidebar (220px fixed width) is not suitable for mobile. Replace it with a horizontal scrollable tab bar at the top of the Settings page, allowing mobile users to tap between setting groups. The main content area expands to fill the width.

## Acceptance Criteria (Given/When/Then — required before /story will run)
- AC-1: Given the viewport is <768px, When Settings page loads, Then the left sidebar nav is hidden and a horizontal tab bar appears at the top of the content area
- AC-2: Given the tab bar is displayed, When all tabs are visible, Then tabs are scrollable horizontally if they exceed the viewport width (scrollable container with scroll arrows or snap-to-fit)
- AC-3: Given a tab is tapped, When the selection occurs, Then the corresponding setting group content is displayed below the tab bar
- AC-4: Given the viewport is resized to ≥768px, When the resize occurs, Then the left sidebar nav reappears and the horizontal tab bar is hidden
- AC-5: Given a mobile tab is selected, When the Settings page is reloaded, Then the previously selected tab is active (state persisted)

## Edge Cases
- More than 10 tabs exist → scrollable horizontal container with scroll indicators or pagination
- Tab name is very long → truncate with "..." on mobile, show full name on hover/focus
- User scrolls tab bar while a modal (e.g., ConfirmDialog) is open → modal remains above tab bar

## Out of Scope
- Animated scroll snapping (basic scroll is sufficient)
- Nesting tabs within tabs

## Non-Functional Requirements
- Tab bar height: 48-56px (fits mobile header sizing)
- Tab touch target: at least 44x44px
- Scrollable tab container: smooth scroll, no jumpy behavior
- Active tab visual indicator (underline or highlight color)

## Traceability (filled at close by /story)
| AC | Test(s) | Files |
|---|---|---|
| AC-1 | visual_mobile_settings_tab_bar | Settings.jsx, global.css |
| AC-2 | e2e_mobile_tab_scroll | Settings.jsx |
| AC-3 | e2e_mobile_tab_select | Settings.jsx |
| AC-4 | e2e_responsive_settings_return | Settings.jsx, global.css |
| AC-5 | test_mobile_settings_state_persist | Settings.jsx, utils/storage.js |

---
