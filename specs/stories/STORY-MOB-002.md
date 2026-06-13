# STORY-MOB-002: Implement card-based responsive table layout for Risk Register below 768px

**Status:** ready
**Screen/Area:** Responsive / Mobile Experience

## Goal
At <768px viewport, convert the horizontal-scrolling Risk Register table into a stacked card-based layout. Each row becomes a vertical card with label-value pairs, allowing mobile users to see all columns without horizontal scrolling.

## Acceptance Criteria (Given/When/Then — required before /story will run)
- AC-1: Given the viewport is <768px, When the Risk Register renders, Then each table row is displayed as a stacked card (not a horizontal table)
- AC-2: Given a card is displayed, When all columns are inspected, Then all data is visible without horizontal scrolling (each column is a label:value pair)
- AC-3: Given a card row contains actions (e.g., Edit, Delete), When the actions are displayed, Then they are either in a single overflow menu (⋮) or stacked vertically at the bottom of the card
- AC-4: Given the viewport is resized to ≥768px, When the resize occurs, Then the table layout returns to the normal horizontal table view
- AC-5: Given a mobile card is displayed, When the user views multiple cards, Then there is visible spacing between cards and they remain readable

## Edge Cases
- Overflow menu (⋮) is clicked on a card → menu pops out above the card (not below, to avoid covering next card)
- Card has a very long value (e.g., long risk description) → truncate with "..." and allow expand-on-click or modal view

## Out of Scope
- Sorting/filtering cards on mobile (those can remain in a header control)
- Paginating cards (use same pagination as table)

## Non-Functional Requirements
- Card layout is touch-friendly (min 44px touch targets for action buttons)
- Cards have clear visual hierarchy (header, body, footer sections)
- No horizontal scroll at any viewport size
- Card width fills available space with safe margins (16px-24px on sides)

## Traceability (filled at close by /story)
| AC | Test(s) | Files |
|---|---|---|
| AC-1 | visual_mobile_card_layout | RiskRegister.jsx, global.css |
| AC-2 | e2e_card_all_columns_visible | RiskRegister.jsx |
| AC-3 | visual_card_actions_overflow | RiskRegister.jsx, components/ActionMenu.jsx |
| AC-4 | e2e_responsive_table_return | RiskRegister.jsx, global.css |
| AC-5 | visual_card_spacing_readability | RiskRegister.jsx, global.css |

---
