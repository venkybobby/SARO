# STORY-RISKFORM-002: Replace Hardcoded Colors with Design Tokens

**Status:** ready  
**Screen/Area:** Risk Creation / Edit Form

## Goal
Eliminate hardcoded hex colors (#fca5a5, #d1d5db, #ef4444) in RiskForm.jsx and use project design tokens (var(--color-critical), var(--color-border-default), etc.) for consistency and proper contrast support across light/dark modes.

## Acceptance Criteria (Given/When/Then — required before /story will run)
- AC-1: Given the Risk Form is rendered on any background theme, When the form displays with any color (border, error text, success state), Then all colors use CSS custom properties (var(--color-*)) from the design token system.
- AC-2: Given the form renders with error states, When an error field is shown, Then the error text and border use `var(--color-critical)` (not #ef4444).
- AC-3: Given the form renders with default (non-error) state, When an input border is drawn, Then it uses `var(--color-border-default)` (not #d1d5db).
- AC-4: Given the form is viewed on light or dark mode, When the CSS is applied, Then contrast ratios for all text/border combinations meet WCAG AA minimum (4.5:1 for text, 3:1 for borders).

## Edge Cases
- Form inputs with `disabled` state (ensure border/background tokens for disabled state are applied).
- Form inputs with `focus` state (ensure focus ring uses `var(--color-focus-ring)` or equivalent).
- Optional fields with no error (ensure default border token is not too light).
- Required field indicators (* asterisk color must use `var(--color-critical)`, not hardcoded #ef4444).

## Out of Scope
- Modifying the design token definitions themselves (assume tokens are already defined in global CSS).
- Creating new tokens (use only existing tokens).
- Refactoring other screens' hardcoded colors (this story is Risk Form only).

## Non-Functional Requirements
- All inline `style={}` objects replaced with CSS classes referencing tokens, or inline styles updated to use `var()` notation.
- No performance impact; CSS variable lookup is negligible.
- Accessibility: verify no contrast regressions with axe-core or similar audit tool.
