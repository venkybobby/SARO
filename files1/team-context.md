# Skill: SARO Team Context

## Team Members

| Name | Role | Responsibilities |
|------|------|-----------------|
| Venky R (venkybobby) | Lead Developer & Product Owner | Architecture decisions, product direction, final approval on all deliverables |
| Alex Rivera | ML Lead | ML model outputs, GradientBoostingClassifier (Finance), RandomForestClassifier (Healthcare), NLP content moderation (Technology), NIST AI RMF assessment (Government). **Must author "How SARO Reasons" transparency doc before TRACE demo.** |
| Jordan Lee | Backend Lead | API endpoints, async patterns, database layer, Koyeb deployment |
| Sam Patel | QA | Test framework execution, FR/NFR coverage, fixture validation |
| Taylor Kim | QA | Test framework execution, E2E Playwright, performance (Locust), security (OWASP) |

## Communication Style (Venky's preferences)

- Action over discussion — "execute" or "proceed" means act immediately
- Integrated delivery only — never create standalone repos or separate deliverable folders
- Show only changed code, never full files
- Honest and critical assessment preferred over diplomatic hedging
- Specs uploaded as documents → direct execution expected, not re-summarization

## Claude AI Integration (Per-Role SDK Setup)

Each team member has a role-specific Claude SDK integration with:
- Shared client wrapper (rate limiting, exponential backoff, structured JSON output)
- Interactive architecture diagram
- Makefile targets

## AutoGen Agentic Architecture (MVP4)

Three-agent pipeline prototype:
- **DriftAgent** → detects model/data drift
- **ComplianceAgent** → maps drift to regulatory impact
- **ReportAgent** → generates structured compliance report
