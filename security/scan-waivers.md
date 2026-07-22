# Security-scan waivers (STORY-367)

Waiver process: a gate finding may be waived ONLY by adding a row here with an
expiry date and a reason, and passing its ID to the scanner in
`.github/workflows/security-scans.yml`. Expired waivers fail the weekly run
(`scripts/check_scan_waivers.py`). No blanket suppressions.

| ID | Package | Reason | Expiry | Owner |
|---|---|---|---|---|
| PYSEC-2026-1325 | ecdsa 0.19.2 (transitive via python-jose[cryptography]) | No fixed release available upstream; SARO's JWT path uses the `cryptography` backend, not pure-python ecdsa signing. Re-check for a fix at expiry. | 2026-10-20 | Venky |

## Retired waivers

Kept for provenance; no longer passed to the scanner.

| ID | Package | Retired | How resolved |
|---|---|---|---|
| GHSA-67mh-4wv8-2f99 | esbuild ≤0.24.2 → vite ≤6.4.2 chain (devDependencies) | 2026-07-22 | Frontend toolchain upgraded to vite 8.1.5 / vitest 4.1.10 / @vitejs/plugin-react 6.0.3; the vulnerable esbuild/vite chain is gone. `npm audit` is now clean at 0 vulnerabilities; build + 202 vitest tests green. |
| vitest-chain-2026 | vitest ≤3.2.5 (critical, devDependencies) + @vitest/mocker, vite-node | 2026-07-22 | Resolved by the same vitest 4 major bump. `restoreMocks: true` added to the test config for vitest-4 mock-isolation semantics. |
