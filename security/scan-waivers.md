# Security-scan waivers (STORY-367)

Waiver process: a gate finding may be waived ONLY by adding a row here with an
expiry date and a reason, and passing its ID to the scanner in
`.github/workflows/security-scans.yml`. Expired waivers fail the weekly run
(`scripts/check_scan_waivers.py`). No blanket suppressions.

| ID | Package | Reason | Expiry | Owner |
|---|---|---|---|---|
| PYSEC-2026-1325 | ecdsa 0.19.2 (transitive via python-jose[cryptography]) | No fixed release available upstream; SARO's JWT path uses the `cryptography` backend, not pure-python ecdsa signing. Re-check for a fix at expiry. | 2026-10-20 | Venky |
| GHSA-67mh-4wv8-2f99 | esbuild ≤0.24.2 → vite ≤6.4.2 chain (devDependencies) | Dev-server-only advisory; nothing from this chain ships in the production bundle. Fix = vite 8 / vitest 4 MAJOR bumps — scheduled as a dedicated frontend-toolchain upgrade, not a drive-by. npm gate blocks on `--omit=dev` (production deps), full audit runs report-only. | 2026-10-20 | Venky |
| vitest-chain-2026 | vitest ≤3.2.5 (critical, devDependencies) + @vitest/mocker, vite-node | Test-runner only, never deployed; same vite-8/vitest-4 major-bump story as above. | 2026-10-20 | Venky |
