/**
 * STORY-TAB-002: single source for mapping backend onboarding step keys
 * (routers/onboarding.py) to in-app sidebar pages. The API's cta_url values
 * are API paths (e.g. /api/v1/scan) and are NOT user-navigable — only keys
 * with an unambiguous in-app destination get a mapping; everything else
 * renders label-only. Unknown/future keys degrade gracefully the same way.
 */
export const ONBOARDING_STEP_NAV = {
  first_scan: "upload",
  aims_doc: "aims",
};
