# STORY-372: Status & Degradation Communication

**Status:** ready
**Screen/Area:** Ops (Pack Epic 16)
**Depends on:** STORY-368 canary

## Goal
A public status surface for both apps plus a documented maintenance-window
announcement procedure.

## Acceptance Criteria
- AC-1: Minimal static status page fed by the STORY-368 canary (GitHub Actions
  writes status JSON to a gh-pages-style artifact or the frontend serves a
  `/status` page reading the canary output). Hosted-SaaS option documented as
  the human-gated alternative.
- AC-2: Maintenance-window announcement procedure documented (`docs/ops/maintenance-windows.md`).
- AC-3: Linked from the SLA doc (STORY-369).

## Traceability (filled at close)
| AC | Test(s) | Files |
|---|---|---|
| AC-1 | `test_status_page_exists_where_vite_will_publish_it`, `test_page_probes_health_live_rather_than_reading_a_cached_file`, `test_page_has_no_external_dependencies`, `test_no_hardcoded_operational_claim_in_markup` | `frontend/public/status.html` |
| AC-2 | `test_procedure_states_notice_period_and_window`, `test_procedure_covers_unplanned_degradation_not_only_maintenance`, `test_procedure_forbids_the_dishonest_moves` | `docs/ops/maintenance-windows.md` |
| AC-3 | `test_sla_links_the_procedure_and_the_status_page`, `test_sla_repeats_the_independence_caveat` | `docs/legal/sla-draft-v0.1.md` §4 |

## Verified in a real browser (not just by test)
| Stubbed `/health` | Rendered |
|---|---|
| `200 {status:ok, db_ok:true, version:8.0.0}` | API **green** "Operational · v8.0.0"; DB **green** "Reachable" |
| `503 {status:degraded, db_ok:false}` | API **amber** "Responding with 503"; DB **red** "Not reachable — evaluations will fail" |
| fetch throws (no backend) | API **red** "Unreachable from this browser"; DB **red** "Unknown" |

The third case is the default state on a cold load with no backend — the page
fails **red**, never to a green default.

## Design notes
- **Live probe, not canary-fed.** A cached "all systems operational" banner
  states the opposite of the truth during an outage, which is precisely when it
  is read. Live probing cannot go stale.
- **503 is degraded, not down** — it is the documented healthy-process /
  unhealthy-dependency response; calling it an outage would misreport a
  partially working system.
- **No external assets** — the page must keep working when the rest does not.

## Human gate
**[HUMAN — OPEN] Independent hosting.** The page is served by the frontend Fly
app and shares its fate — stated on the page itself and repeated in the SLA
rather than hidden. True independence needs a third-party status service
(account, subscription, and a new vendor in the Epic 15 security-review
surface), so it was not set up unilaterally.
