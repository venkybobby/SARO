# EU AI Act / AIGP / Governance / NIST Rule Sets — Build Logic & Implementation Status

Answers, with file:line citations, exactly how `eu_ai_act_rules`,
`aigp_principles`, `governance_rules`, and `nist_ai_rmf_controls` are built
and consumed, and what "implemented" actually means for each. The short
version: **these four tables are not what decides whether a compliance
finding fires.** A separate, much smaller YAML system does that. These
tables are a citation corpus that only partially, and inconsistently,
reaches the customer.

---

## The two-system split — read this first

SARO has **two independent mechanisms** that both claim to represent
"compliance framework content." Confusing them is the easiest way to
misjudge what's actually implemented.

| | **Rule packs** (`rule_packs/*/v1.0.0/rules.yaml`) | **Reference tables** (these 4 SQL tables) |
|---|---|---|
| What it is | 17 hand-curated rules total (5 EU AI Act, 5 NIST, 4 ISO 42001, 3 AIGP) | 188 rows total (41+72+28+47) — a much larger citation corpus |
| What it does | **Actually decides** which domain flag → which rule fires (`_gate4_compliance_mapping`, `engine.py:1739`) | Loaded into memory at engine startup; used **only** as a text-lookup fallback for obligation wording |
| Versioned/hash-chained? | Yes — `rule_pack_snapshots` via `rule_packs/loader.py` | Partially — 3 of the 4 tables (not AIGP) can be frozen into a *separate* snapshot mechanism (`rule_pack_snapshots` DB table, same name, different code path — see below) |
| Governs Gate 4 pass/fail | Yes, directly | No — never the trigger, only ever a fallback obligation-text source |

Two completely different features share the name "rule pack" / "rule
snapshot" here — `rule_packs/loader.py` (YAML files → Gate 4 triggers) and
`services/rule_pack_snapshot_service.py` (SQL reference tables → immutable
DB snapshots for reproducibility). They both write to the same
`rule_pack_snapshots` table but via different code paths and different
source data. Worth keeping straight.

---

## How a reference-table row actually gets used (the real code path)

1. **`SARoEngine.__init__` → `_load_reference_data(db)`** (`engine.py:779-907`)
   loads all four tables into in-memory Python lists at every engine
   startup: `self._eu_rules`, `self._nist_controls`, `self._aigp`,
   `self._gov_rules`. Each table is loaded in its own `try/except` — a
   missing/broken table degrades to an empty list rather than crashing the
   engine (`engine.py:780-784`).
2. Two of the four (`eu_ai_act_rules`, `governance_rules`) are filtered at
   load time by `validation_status` through `services/rule_visibility.py`'s
   fail-closed allowlist (see below) — `engine.py:844,899`. The other two
   (`nist_ai_rmf_controls`, `aigp_principles`) have **no such column** and
   are loaded in full, unconditionally.
3. **`_gate4_compliance_mapping`** (`engine.py:1739-1805`) decides which
   rules fire using `self._compliance_triggers` (built from the YAML rule
   packs via `build_domain_trigger_map`, `rule_packs/loader.py:177-201`) —
   **not** the reference tables.
4. For each firing rule, the obligation text is `t.get("obligation")` from
   the YAML pack **first**; only if that's falsy does it call
   `self._lookup_obligations(framework, rule_id)` (`engine.py:1807-1831`),
   which substring-matches against the four in-memory lists.
5. **Every YAML rule pack rule has a required, non-empty `obligation` field**
   (`rule_packs/loader.py:36`). The legacy hardcoded fallback dict
   (`_COMPLIANCE_TRIGGERS`, `engine.py:313+`) is the only path whose entries
   lack an `obligation` key — and that dict is only used at all if
   `self._compliance_triggers` comes back empty, i.e. **the YAML rule-pack
   loader failed entirely** (`engine.py:1756-1760`).

**Conclusion: under normal operation, `_lookup_obligations()` — the only
function that reads these four tables for scoring purposes — is never
invoked.** The reference tables are real, wired, loaded-every-startup data,
but they are not currently reachable by the pipeline that would use them,
because the primary path never needs the fallback. They'd only start
mattering if the YAML rule-pack directory ever failed to load — a degraded
mode, not the normal path.

---

## Where these tables ARE actually read for display (a second, separate consumer)

`services/compliance_matrix_service.py` — backs `GET /api/v1/compliance-matrix`
and the `ClaimsMatrix.jsx` frontend page — reads two of the four tables
directly, with real effect on what a user sees:

| Table | Read by compliance_matrix_service? | What happens |
|---|---|---|
| `eu_ai_act_rules` | **Yes** (`compliance_matrix_service.py:118-142`) | Every visible row (by `validation_status`) is shown, but `"status"` is **hardcoded to `"In Progress"` for every single row** (line 132) and `coverage_pct` is **always `None`** (line 133) — neither is computed from anything. |
| `nist_ai_rmf_controls` | **Yes** (`compliance_matrix_service.py:145-163`) | All 72 rows always shown (no validation-status column to filter on). `"status"` is **hardcoded to `"Evidence Supported"` for every row** (line 155), `coverage_pct` always `None`. |
| `aigp_principles` | **No.** | The AIGP rows a user actually sees on this page are **2 hand-typed static dicts** (`_STATIC_ROWS`, `compliance_matrix_service.py:38-62`) with fabricated `coverage_pct` values (85, 90) — the real 28-row `aigp_principles` table is not queried by this service at all, despite a comment claiming AIGP is "not yet in DB tables" (`compliance_matrix_service.py:37`), which is false — the table exists with 28 rows; it's simply not wired here. |
| `governance_rules` | **No.** | The "ISO 42001" rows shown on this page are **3 more hand-typed static dicts** (same `_STATIC_ROWS` block) with fabricated `coverage_pct` (62, 35, 88) and a `notes: "Pending SME review"` on one — none of this comes from the real 47-row `governance_rules` table. |

So on the one screen where a customer would actually browse this content,
half of it (EU AI Act, NIST) is real DB data wearing fake, non-computed
status labels, and the other half (AIGP, ISO 42001) is entirely fabricated
placeholder rows unconnected to the real tables sitting right next to them
in the schema.

---

## The validation-status governance workflow (real, and partially enforced)

`services/rule_visibility.py` implements a genuine SME-review lifecycle
(migration `radar_scan1_validation_status_columns`, `models.py:404-407`):

```
LEGACY_UNREVIEWED | DRAFT_UNVALIDATED | SME_VALIDATED | RETIRED
```
Fail-closed: `DRAFT_UNVALIDATED`, `RETIRED`, and `NULL` are **always** hidden
from a default view; `SME_VALIDATED` is always shown; `LEGACY_UNREVIEWED` is
shown only if `settings.saro_show_legacy_rules` is true — **which it is, by
default** (`config.py:66`). So in practice today, "visible" means "legacy or
validated," and "hidden" means "draft or retired."

**Live data** (queried directly, 2026-07-30):

| Table | `DRAFT_UNVALIDATED` (hidden) | `LEGACY_UNREVIEWED` (visible) | `RETIRED` (hidden) | `SME_VALIDATED` (visible) |
|---|---|---|---|---|
| `eu_ai_act_rules` (41 rows) | 24 | 17 | 0 | **0** |
| `governance_rules` (47 rows) | 4 | 36 | 7 | **0** |
| `nist_ai_rmf_controls` | — no such column, all 72 always visible — | | | |
| `aigp_principles` | — no such column, all 28 always visible — | | | |

**Zero rows in any table have ever reached `SME_VALIDATED`** — consistent
with `docs/COMPLIANCE_CLAIMS_MATRIX.md`'s EVF section stating no framework
has completed external SME validation yet. Everything currently shown is
shown because it's "legacy," not because it's been reviewed.

**What the 24 hidden EU AI Act drafts actually are** — traced to
`migrations/031_radar_scan1_rule_pack_delta_data.sql` (a 2026-07-04 update,
~4 weeks before this audit): rows 9–20 and 34–41 are **Annex III, Article 6,
the high-risk-system chapter (Articles 9–17), and the deployer obligations
(Articles 26/27)** — arguably the substantively most important part of the
EU AI Act — plus rows 21–24 (**Article 50 transparency**, including a note
about a "Digital Omnibus grace period" pending SME confirmation). These were
deliberately marked draft and hidden by the same migration, per
STORY-CHUB-011's policy of never presenting unreviewed regulatory mappings as
authoritative. **This is good governance discipline, not a bug** — but it
does mean the EU AI Act rule set's core high-risk provisions are currently
absent from what a customer sees, until an SME reviews them.

**What changed in `governance_rules` at the same time:** the since-revoked US
Executive Order 14110 was marked `RETIRED` (7 rows), and two new 2026 state
laws — **Colorado SB 189** and **Texas TRAIGA** — were added as 4 new
`DRAFT_UNVALIDATED` rows, explicitly flagged "SME/counsel review required"
in their own obligation text (`migrations/031_...sql:49`).

---

## Rule-pack versioning/snapshot coverage — AIGP is left out

`services/rule_pack_snapshot_service.py:43-71` defines `_RULE_TABLES`, the
registry of what gets captured when a rule-pack version is published
(`POST /api/v1/rules/versions`): **`eu_ai_act_rules`, `governance_rules`, and
`nist_ai_rmf_controls` only.** `aigp_principles` is not in this list at all.
Publishing an immutable, hash-chained snapshot of "what rules were in force"
therefore **never includes AIGP content** — if AIGP obligation text ever
changes, there's no versioned, reproducible record of it the way there is
for the other three.

The service also **blocks publication** (`DraftRowsPresentError`) if any
`DRAFT_UNVALIDATED` row is in scope — meaning, as of today, a real attempt to
publish a new snapshot covering `eu_ai_act_rules`/`governance_rules` would
need to explicitly exclude the 24 + 4 current draft rows or it would fail.

---

## A third, unrelated NIST asset — worth flagging for coherence

`GET /api/v1/reports/nist-coverage` (`routers/reports.py:344-404`) does
**not** query `nist_ai_rmf_controls` at all. It uses `_NIST_COVERAGE_MAP`
(`routers/reports.py:301`), a **hardcoded Python dict of "68 NIST AI RMF 1.0
subcategory IDs,"** maintained independently in this router file and in
`docs/nist-coverage-rubric.md`. So there are now **three separate NIST
assets that never reference each other**: the 72-row `nist_ai_rmf_controls`
DB table, the 68-item hardcoded coverage map, and the 5-rule YAML pack that
actually drives scoring. Nothing in code keeps these in sync — the "68 vs
72" discrepancy was already flagged in the prior (2026-06-15) gap analysis
and is still unresolved.

---

## Where the data itself came from

`models.py:367` labels these "Reference tables (read-only, populated by
`import_*.py` scripts)." **No `import_*.py` script exists anywhere in the
current repository** (checked directly) — only `scripts/seed_control_library.py`
(which seeds the unrelated, currently-empty `controls`/`control_framework_mappings`
tables), `seed_demo.py`, `seed_demo_tenant.py`, and `generate_governance_pdfs.py`.
The only migration that touches these four tables' *data* (as opposed to
their schema) is `migrations/031_radar_scan1_rule_pack_delta_data.sql`, which
is explicitly a **delta** (status transitions + a handful of new rows), not
an original load. **The original population of the 41/72/28/47 rows is not
traceable to any script or migration currently in the repo** — it most
likely happened via a one-off manual load (direct SQL, or the Supabase
MCP/dashboard) before this repo's tracked-migration discipline existed. If
you ever need to refresh this content (e.g. for an EU AI Act or NIST AI RMF
version bump), there is currently no reproducible, code-driven way to do it
— that itself is a gap worth noting.

---

## Implementation status — the direct answer, per rule set

| Rule set | Rows | Drives Gate 4 scoring? | Shown on Compliance Matrix? | Versioned/snapshotted? | Review status |
|---|---|---|---|---|---|
| **EU AI Act** (`eu_ai_act_rules`) | 41 | No — only as a dormant fallback lookup; real triggering comes from the 5-rule YAML pack | Yes, but with a hardcoded, non-computed `"In Progress"` status on every row | Yes (`_RULE_TABLES`) | 0 SME-validated, 17 legacy (shown), 24 draft (hidden, incl. all high-risk-chapter articles) |
| **NIST AI RMF** (`nist_ai_rmf_controls`) | 72 | No — same dormant fallback; real triggering from the 5-rule YAML pack | Yes, but with a hardcoded, non-computed `"Evidence Supported"` status on every row | Yes (`_RULE_TABLES`) | No validation-status column — no review gate exists at all |
| **AIGP** (`aigp_principles`) | 28 | No — dormant fallback only | **No** — real rows are never queried; 2 fabricated placeholder rows shown instead | **No** — excluded from `_RULE_TABLES` entirely | No validation-status column — no review gate exists at all |
| **Governance / cross-framework** (`governance_rules`) | 47 | No — dormant fallback only (used for "ISO 42001" lookups specifically) | **No** — real rows never queried; 3 fabricated placeholder rows shown instead | Yes (`_RULE_TABLES`) | 0 SME-validated, 36 legacy (shown), 4 draft + 7 retired (hidden) |

**What "implemented" means for each, in one line:**
- **EU AI Act**: real data, real (if currently thin) governance-review workflow, but the customer-facing status label is fake and the scoring-relevant lookup path is unreachable in normal operation.
- **NIST AI RMF**: real data, but no review workflow at all, a fake status label on display, and a *third*, unrelated hardcoded list (`_NIST_COVERAGE_MAP`) actually answers "what does SARO cover" for NIST.
- **AIGP**: real data that is functionally inert — not used for scoring in practice, not shown to customers, and not covered by the versioning system.
- **Governance/cross-framework**: real data with the most active review workflow of the four (regulatory tracking is clearly happening — the Colorado/Texas/EO 14110 updates prove it) but, like AIGP, invisible on the one screen a customer would look at.
