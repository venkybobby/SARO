# STORY-RISKFORM-004: Fix Action Row Layout (Disclaimer Text Wrapping)

**Status:** ready  
**Screen/Area:** Risk Creation / Edit Form

## Goal
Resolve the cramped action row layout where the "Human review required..." disclaimer text wraps awkwardly on narrow viewports. Improve readability and button accessibility by restructuring the row with proper flex wrapping.

## Acceptance Criteria (Given/When/Then — required before /story will run)
- AC-1: Given the Risk Form is displayed on a narrow viewport (mobile, <768px), When the Save/Cancel buttons and disclaimer text are rendered, Then the disclaimer wraps to a new line cleanly without pushing buttons off-screen.
- AC-2: Given the action row is displayed on desktop, When both buttons and disclaimer are present, Then they remain on the same row with adequate spacing and the disclaimer does not crowd the buttons.
- AC-3: Given the action row is resized (viewport width changes), When the flex layout reflows, Then the transition is smooth and buttons are always accessible (tappable/clickable).
- AC-4: Given the form is in a modal or drawer, When the action row width is constrained, Then all elements (Save, Cancel, disclaimer) remain visible and properly spaced.

## Edge Cases
- Disclaimer text is very long (future i18n with longer translations); ensure it wraps without truncation.
- One button is disabled (e.g., Save is disabled pending validation); spacing remains consistent.
- Screen is extremely narrow (< 320px); disclaimer should stack above buttons if needed (graceful degradation).
- RTL languages (if applicable); flex direction and text alignment must adapt.

## Out of Scope
- Changing the disclaimer text itself (content review is separate).
- Moving the disclaimer to a tooltip or popover (layout-only fix; future UX enhancement).
- Modifying button styles or labels.

## Non-Functional Requirements
- Action row container must have `flexWrap: "wrap"` or equivalent CSS (`flex-wrap: wrap`).
- Spacing (gap/margin) must remain consistent after wrap (use CSS `gap` property).
- No horizontal scroll on any viewport size.
- Mobile-first: test at 320px, 375px, 768px, 1024px, 1920px.
