/**
 * Framework reference navigation — STORY-003.
 *
 * Maps an insight's framework metadata to an in-app navigation target
 * (the Claims Matrix documents what SARO does / does not claim per
 * framework — insights never link to unvalidated internal reasoning,
 * per SARO_GRC_SME_Validation_Requirements).
 */
const FRAMEWORK_TARGETS = {
  "NIST AI RMF": { page: "claims_matrix", section: "nist-ai-rmf" },
  "EU AI Act":   { page: "claims_matrix", section: "eu-ai-act" },
  "ISO 42001":   { page: "claims_matrix", section: "iso-42001" },
  "AIGP":        { page: "claims_matrix", section: "aigp" },
};

/**
 * Resolve the navigation target for a framework name.
 * Returns { page, section, label } or null when no documented target
 * exists (caller hides or disables the link — STORY-003 AC-3).
 */
export function getFrameworkTarget(framework) {
  if (!framework) return null;
  const key = Object.keys(FRAMEWORK_TARGETS).find(
    (k) => k.toLowerCase() === String(framework).trim().toLowerCase()
  );
  if (!key) return null;
  return { ...FRAMEWORK_TARGETS[key], label: `View ${key} reference` };
}
