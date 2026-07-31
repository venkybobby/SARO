# Security-scan waivers (STORY-367)

Waiver process: a gate finding may be waived ONLY by adding a row here with an
expiry date and a reason, and passing its ID to the scanner in
`.github/workflows/security-scans.yml`. Expired waivers fail the weekly run
(`scripts/check_scan_waivers.py`). No blanket suppressions.

| ID | Package | Reason | Expiry | Owner |
|---|---|---|---|---|
| PYSEC-2026-1325 | ecdsa 0.19.2 (transitive via python-jose[cryptography]) | No fixed release available upstream; SARO's JWT path uses the `cryptography` backend, not pure-python ecdsa signing. Re-check for a fix at expiry. | 2026-10-20 | Venky |
| PYSEC-2026-161 | starlette 0.52.1 (pinned, FND-069) | Fix requires starlette>=1.1.0, which requires fastapi>=0.135.0 (fastapi==0.129.0 pins starlette<1.0.0). Tried fastapi==0.141.1/starlette==1.3.1: reintroduces FND-069 in a worse form — `iter_api_routes()` on the real app sees 2 routes instead of 204+, i.e. even the version-independent recursive helper doesn't survive the new nesting shape. Not safe to ship blind; needs a dedicated investigation into the new route-tree shape before the fastapi/starlette pins can move. **Exposure check (2026-07-30):** grepped the repo for `StaticFiles`, `UploadFile`, `.form(`, and `multipart` — zero matches in `main.py`/`routers/`. SARO mounts no StaticFiles directory and no endpoint accepts multipart/form data, so this CVE's path-traversal-via-StaticFiles vector is unreachable in the current attack surface. Re-verify at renewal in case StaticFiles/UploadFile is added before the fastapi bump lands — if so, escalate priority immediately rather than re-waiving. | 2026-09-15 | Venky |
| PYSEC-2026-248 | starlette 0.52.1 (pinned, FND-069) | Same root cause, blocker, and exposure check as PYSEC-2026-161 — fix requires the same blocked fastapi/starlette bump; unreachable per the same StaticFiles/form-handling grep. | 2026-09-15 | Venky |
| PYSEC-2026-249 | starlette 0.52.1 (pinned, FND-069) | Same root cause, blocker, and exposure check as PYSEC-2026-161. | 2026-09-15 | Venky |
| PYSEC-2026-2280 | starlette 0.52.1 (pinned, FND-069) | Same root cause, blocker, and exposure check as PYSEC-2026-161. | 2026-09-15 | Venky |
| PYSEC-2026-2281 | starlette 0.52.1 (pinned, FND-069) | Same root cause, blocker, and exposure check as PYSEC-2026-161. | 2026-09-15 | Venky |
| CVE-2026-48818 | starlette 0.52.1 (pinned, FND-069) | Trivy-namespace ID for the same starlette gap as PYSEC-2026-161 (SSRF/NTLM credential theft via UNC paths in StaticFiles). Same blocker, same expiry. **Exposure:** unreachable — SARO mounts no StaticFiles directory anywhere (verified 2026-07-30, re-check at renewal). | 2026-09-15 | Venky |
| CVE-2026-54283 | starlette 0.52.1 (pinned, FND-069) | Trivy-namespace ID for the same starlette gap as PYSEC-2026-161 (request.form() limits silently ignored, DoS). Same blocker, same expiry. **Exposure:** unreachable — no endpoint in main.py/routers/ accepts multipart or form-encoded bodies (verified 2026-07-30, re-check at renewal). | 2026-09-15 | Venky |

## Retired waivers

Kept for provenance; no longer passed to the scanner.

| ID | Package | Retired | How resolved |
|---|---|---|---|
| GHSA-67mh-4wv8-2f99 | esbuild ≤0.24.2 → vite ≤6.4.2 chain (devDependencies) | 2026-07-22 | Frontend toolchain upgraded to vite 8.1.5 / vitest 4.1.10 / @vitejs/plugin-react 6.0.3; the vulnerable esbuild/vite chain is gone. `npm audit` is now clean at 0 vulnerabilities; build + 202 vitest tests green. |
| vitest-chain-2026 | vitest ≤3.2.5 (critical, devDependencies) + @vitest/mocker, vite-node | 2026-07-22 | Resolved by the same vitest 4 major bump. `restoreMocks: true` added to the test config for vitest-4 mock-isolation semantics. |
