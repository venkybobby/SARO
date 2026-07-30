# Documentation vs. Code — Verified Gaps

This is the most important document in this knowledge base for restoring
accurate context: it lists specific claims in `CLAUDE.md` and
`.claude/skills/*/SKILL.md` that **do not match what `engine.py` actually
does**. These aren't stylistic nitpicks — if you (or a future Claude Code
session) plan a change assuming these features exist, the plan will be built
on a false premise.

Methodology: for each claim, a repo-wide grep was run for the exact
symbol/term named in the docs. Zero hits means the feature is not implemented
anywhere in the codebase — not "implemented elsewhere," not "renamed,"
literally absent.

---

## 1. "DIR formula" — does not exist

**Claimed** (`.claude/skills/risk-scoring/SKILL.md:18-19`, referenced in
`CLAUDE.md`'s architecture description): a "Dimension-weighted Incident Rate"
formula, `dir_score = sum(weight_i * indicator_i) / sum(weight_i) * 100`,
producing an int 0–100.

**Verified reality:** grep for `DIR`/`dir_score` across `engine.py` — zero
matches. What's actually computed and persisted as the risk score
(`ScanReport.overall_risk_score`) is a **Beta-Binomial Bayesian posterior
mean** in `[0,1]` (`engine.py:2356-2418`):
- Per-domain and overall priors `Beta(α₀, β₀)`, default Jeffreys prior
  `α₀=β₀=0.5`, optionally calibrated from the incident corpus.
- Posterior updated by `k` = flagged-sample count, `n` = total samples.
- `risk_probability = posterior.mean()`, with a 95% credible interval via
  `scipy.stats.beta.ppf`.

This is a real, working, different scoring mechanism — not a bug, just not
what the docs describe. If "DIR" is a term stakeholders expect to see (e.g.
in a sales deck or compliance doc), it should either be **redefined as an
alias for `bayesian_scores.overall`**, or the docs should be corrected to
describe the Bayesian approach as it actually works.

## 2. SHAP explainability — not implemented

**Claimed** (`.claude/skills/risk-scoring/SKILL.md:27-32,42`):
`shap.TreeExplainer`/`shap.LinearExplainer`, a `SHAP_EXPLAINED` TRACE event,
a `shap_summary` dict.

**Verified reality:** `import shap` — zero hits anywhere in the repo. The
only case-insensitive matches for the substring "shap" in `engine.py` are
inside unrelated words ("evidence-**shap**ed", "technique's **shap**e").
There is no `shap_summary`, no `SHAP_EXPLAINED` event, no explainability
computation of any kind resembling SHAP.

What SARO actually does for explainability is different and arguably
simpler: `_record_explain_trace` (`engine.py:2214-2256`) writes a
human-readable summary of the top-3 risk domains by Bayesian probability,
MIT coverage score, and incident-match count — no per-feature attribution.

## 3. KS-test drift / "2σ auto-incident rule" — not implemented

**Claimed** (`.claude/skills/drift-sentinel/SKILL.md`, `drift-agent.md`):
`ks_2samp`/`kstest` statistical drift detection, `KS_DRIFT_THRESHOLD`,
`CIRCUIT_BREAKER_*` config, `check_sigma_rule`, PagerDuty routing
(`PAGERDUTY_SERVICE_KEY`).

**Verified reality:** none of `ks_2samp`, `kstest`, `KS_DRIFT_THRESHOLD`,
`CIRCUIT_BREAKER_*`, `check_distribution_drift`, `check_sigma_rule`, or
`PAGERDUTY_SERVICE_KEY` appear in any `.py` file in the repository. Hits
exist only in the two markdown design-spec files named above.

**What "drift" actually means in the shipped code** is a completely
different concept: **rule-pack framework-version staleness**, not
statistical drift on model output distributions:
- `services/rule_service.py:77-90` — `check_drift(framework, current_version, latest_version)`
  string-compares a rule pack's version against a hardcoded "latest known
  framework version" map and returns an alert if they differ.
- Surfaced via `GET /api/v1/rules/drift-alerts` (`routers/rule_packs.py:71-77`)
  and the `DriftAlerts.jsx` frontend page, whose own comment describes it
  accurately as "framework version drift detection."

If statistical/distributional drift monitoring on model outputs is something
you actually want, it needs to be built from scratch — the `drift-sentinel`
skill file and `drift-agent.md` are a design document for a feature that was
never implemented, not documentation of an existing one.

## 4. The 7-step linear TRACE lifecycle — different shape in code

**Claimed** (`.claude/skills/risk-scoring/SKILL.md:36-46`): a linear
`SCAN_INITIATED → ... → SHAP_EXPLAINED → DRIFT_CHECKED → ... → SCAN_COMPLETE`
event sequence.

**Verified reality:** TRACE is built from six emitter functions
(`engine.py:1835-2289`), each keyed by `gate_id`/`check_type`
(`gate_result`, `risk_domain`, `injection_scan`, `explain`, `remediate`,
plus per-rule Gate-4 traces) — not a linear named-event lifecycle, and with
no `SHAP_EXPLAINED`/`DRIFT_CHECKED` steps (consistent with §2/§3 above, since
those features don't exist to have trace steps for).

---

## What this means practically

`.claude/skills/risk-scoring/SKILL.md` and `.claude/skills/drift-sentinel/SKILL.md`
are currently **aspirational design documents wearing the clothes of
"enforced guidance."** Both are listed in CLAUDE.md as skills Claude Code
"follows automatically" when editing `engine.py` or drift logic — meaning a
future session could easily be steered into "fixing" `engine.py` to match a
formula/feature that was never there, or reporting confidently that SHAP/KS-test
drift exist because the skill file said so. Two options going forward (not
acted on here, since this task was scoped to documentation only):

1. **Rewrite the skill files** to describe the actual Bayesian/rule-pack-drift
   mechanisms, so they stop asserting fictional formulas.
2. **Or**, if DIR/SHAP/KS-test-drift are genuinely on the roadmap, relabel the
   skill files as forward-looking specs (not "enforce these invariants") so
   they're not mistaken for descriptions of current behavior.

Either way, any future work session should treat `risk-scoring/SKILL.md` and
`drift-sentinel/SKILL.md` claims about DIR/SHAP/KS-test as unverified until
this gap is resolved.
