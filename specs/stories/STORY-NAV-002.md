# STORY-NAV-002: Add skip-to-content link for keyboard accessibility

**Status:** ready
**Screen/Area:** Navigation & Global Components

## Goal
Add a visually-hidden "Skip to content" link as the first focusable element in the AppShell. When focused, it becomes visible and allows keyboard users to jump directly to the main content area, bypassing the 20+ sidebar items.

## Acceptance Criteria (Given/When/Then — required before /story will run)
- AC-1: Given a keyboard user presses Tab at the start of page load, When the first Tab occurs, Then the focus moves to a visible "Skip to content" link
- AC-2: Given the "Skip to content" link is focused, When the user presses Enter, Then the focus moves directly to the `<main id="main-content">` element
- AC-3: Given the user has navigated past the skip link, When they Tab backward (Shift+Tab) to the start, Then the skip link becomes visible again
- AC-4: Given the page is rendered, When a sighted user views it, Then the skip link is not visible in normal layout (only visible on focus)
- AC-5: Given the skip link is clicked via mouse, When the click occurs, Then the focus is moved to main content and the link remains visually invisible (as if never focused)

## Edge Cases
- User presses Tab multiple times before reaching the skip link → the link is reachable within the first 2-3 Tab presses
- Multiple `<main>` elements exist on the page → use `id="main-content"` specifically (already present)

## Out of Scope
- Landmark navigation (<nav>, <main>, <footer>) — that's a separate accessibility story
- Skip-to-navigation link (only skip-to-content in this story)

## Non-Functional Requirements
- Skip link must be the first focusable element in DOM
- Skip link styling: `.skip-link { position: absolute; top: -40px; left: 0; background: #000; color: #fff; padding: 8px; border-radius: 0 0 4px 0; } .skip-link:focus { top: 0; }`
- Link must have adequate contrast (WCAG AA: 4.5:1 for text)
- No JavaScript required; pure HTML/CSS

## Traceability (filled at close by /story)
| AC | Test(s) | Files |
|---|---|---|
| AC-1 | a11y_skip_link_first_focus | App.jsx |
| AC-2 | e2e_skip_link_navigate | App.jsx |
| AC-3 | e2e_skip_link_reverse_tab | App.jsx |
| AC-4 | visual_skip_link_hidden | App.jsx, global.css |
| AC-5 | e2e_skip_link_mouse_click | App.jsx |

---
