# STORY-SET-001: Implement coming-soon visibility and messaging for incomplete settings groups

**Status:** ready
**Screen/Area:** Settings / Configuration

## Goal
Replace the current "coming soon" stub text with proper UI signals (e.g., badges, disabled tabs, informational callouts) so users understand that Integrations, Notifications, and Risk Framework are not yet available, rather than thinking they are bugs.

## Acceptance Criteria (Given/When/Then — required before /story will run)
- AC-1: Given the Settings page is loaded, When the left navigation is visible, Then "Integrations", "Notifications", and "Risk Framework" tabs show a "Planned Q3" or "Coming Soon" badge
- AC-2: Given a "coming soon" tab is present, When the user hovers over or focuses it, Then a tooltip explains "This feature is coming in Q3 2026"
- AC-3: Given the user attempts to click a disabled tab, When the click occurs, Then nothing happens (tab does not activate)
- AC-4: Given all tabs are visible, When the page layout is inspected, Then the disabled tabs are visually de-emphasized (grayed out or opacity reduced) compared to active tabs
- AC-5: Given the Settings page renders, When the main content area is checked, Then the coming-soon stubs are either hidden entirely or show a single informational message centered on the page (not a broken empty page)

## Edge Cases
- User has bookmarked a coming-soon tab URL → redirect to "General" or show a full-page "Coming Soon" message
- User's role has different feature availability → only show badges/disabled state for features their role cannot access (if applicable)

## Out of Scope
- Removing the tabs entirely (decision to keep them for forward-planning)
- Feature flags or A/B testing coming-soon visibility
- Estimated release dates beyond "Planned Q3"

## Non-Functional Requirements
- Badge/disabled visual state is clear and consistent with other UI patterns (compare to ConfirmDialog or other disabled states)
- Tooltips must be accessible and not hide on mobile (use aria-label instead)
- No broken links or 404 routes

## Traceability (filled at close by /story)
| AC | Test(s) | Files |
|---|---|---|
| AC-1 | visual_coming_soon_badge | Settings.jsx, SETTING_GROUPS constant |
| AC-2 | e2e_coming_soon_tooltip | Settings.jsx, ui/Tooltip.jsx |
| AC-3 | test_disabled_tab_no_activate | Settings.jsx |
| AC-4 | visual_disabled_tab_styling | Settings.jsx, global.css |
| AC-5 | test_coming_soon_page_content | Settings.jsx, components/ComingSoonPlaceholder.jsx |

---
