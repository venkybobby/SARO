# Changelog

All notable changes to SARO are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the platform
version follows [Semantic Versioning](https://semver.org/).

A customer's own change-management process reads this file, so entries describe
what changed from a *user's* perspective — not a commit log. The
[changelog-drafter](.github/workflows/changelog-drafter.yml) proposes entries
from Conventional Commits; a human curates them before release.

## [Unreleased]

### Added
- Single-source platform version (`_version.py`) and a public
  `GET /api/v1/version` endpoint reporting version, build commit, and
  environment. Version also shown in the UI footer.
- Tagged-release pipeline: pushing a `v*` tag runs the conformance suite and the
  full test suite before deploying, then the post-deploy canary confirms the
  release end to end.
- Documented, rehearsable release-rollback procedure.

### Changed
- The FastAPI app version and `/health` now read the single version source
  instead of a hardcoded literal.

## [8.0.0] — 2026-07

Baseline release at which this changelog begins. Prior history is in git.

### Added
- Observation adapters for Bedrock, Azure OpenAI, and Vertex AI, with a
  cross-adapter conformance suite and a generated capability matrix.
- Genesis observation rule-packs `RP-OBS-COMPLETE` and `RP-TOOL-SCOPE`.
- Platform monitoring (`/metrics`, alert rules, synthetic canary), SLO/SLA
  documents, DR backup-and-restore verification, support model, and a live
  status page.
- Idempotent tenant provisioning CLI and usage metering with exact-recount
  verification and CSV/JSON export.

### Security
- HMAC-signed single-use OAuth state for the Jira callback (was an
  attacker-controllable tenant binding).
- Session revocation on credential change (`token_version`).
- Authentication events are now recorded (login success and failure).
- Secret-scanning, dependency/container scanning, and route-authorization
  probes added to CI.

[Unreleased]: https://github.com/venkybobby/SARO/compare/v8.0.0...HEAD
[8.0.0]: https://github.com/venkybobby/SARO/releases/tag/v8.0.0
