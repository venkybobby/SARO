# STORY-SET-005: Refactor Settings left-nav into two groups (main and danger) with structural divider

**Status:** ready
**Screen/Area:** Settings / Configuration

## Goal
Replace fragile conditional inline styles that separate the "Danger Zone" from main settings with a proper structural refactor. Split SETTING_GROUPS into mainGroups and dangerGroups arrays, render a real visual divider between them, and apply consistent styling.

## Acceptance Criteria (Given/When/Then — required before /story will run)
- AC-1: Given the Settings left-nav is displayed, When the page renders, Then SETTING_GROUPS is split into two logical arrays: mainGroups (General, Users, etc.) and dangerGroups (Delete Organization, etc.)
- AC-2: Given both group arrays are defined, When the nav is rendered, Then mainGroups are displayed in one section and dangerGroups are displayed below a visual separator (e.g., <hr> or a styled divider)
- AC-3: Given the divider is visible, When the user inspects styling, Then the divider is a real DOM element or CSS rule, not inline marginTop or borderTop hacks on individual buttons
- AC-4: Given a dangerGroup item is highlighted/selected, When the visual state is applied, Then the styling is consistent (no special per-button overrides)
- AC-5: Given the Settings page is responsive (mobile), When viewport is resized below 768px, Then the divider remains visible and the two-group structure is preserved (or adapts appropriately for mobile nav)

## Edge Cases
- Danger group has no items → divider is hidden or not rendered
- Both groups are empty → the nav is hidden or shows a "No settings available" message

## Out of Scope
- Adding new danger-zone actions (those come in follow-up stories)
- Customizing divider styling beyond standard UI patterns

## Non-Functional Requirements
- Refactoring must not change Settings behavior or introduce bugs
- Code must be cleaner and more maintainable (verifiable in code review)
- All tests must pass (no regression)

## Traceability (filled at close by /story)
| AC | Test(s) | Files |
|---|---|---|
| AC-1 | test_setting_groups_split | Settings.jsx, constants/settings.js |
| AC-2 | visual_main_danger_divider | Settings.jsx |
| AC-3 | test_divider_is_dom_element | Settings.jsx, global.css |
| AC-4 | visual_danger_group_consistency | Settings.jsx, global.css |
| AC-5 | e2e_mobile_settings_nav | Settings.jsx, global.css |

---
