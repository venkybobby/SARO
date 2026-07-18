# STORY-408 — Cross-Account Client Log Pull
Stage: standard

## Lifecycle
- [x] discover   (recon: S3LogStore's existing client-injection seam, TenantRiskConfig's
                   1:1-tenant-table convention, migrations numbering, boto3/moto availability)
- [x] shape      (AskUserQuestion → Decision Log: CFN-only, contract-test via moto)
- [ ] preview    (skipped — no UI, per story Non-Goals)
- [x] plan       (this session: re-confirmed the existing 9-step Plan below against
                   actual code state rather than trusting the checklist — see Build
                   note. No changes to the Plan's ordering or content were needed.)
- [x] build      (steps 1-7 of the Plan were found substantially complete from prior
                   WIP — this session's job was verifying that claim, not writing new
                   feature code. Confirmed step-by-step: (1) TenantLogSourceConfig +
                   migration 037 RLS — real, imports clean; (2) config validation —
                   20/20 tests pass, account_id cleverly derived from role_arn rather
                   than duplicated; (3) cross-account credentials — 5/5 tests pass;
                   (4) S3LogStore.for_tenant + KMS error mapping — 7/7 tests pass,
                   read adapters/bedrock/source.py directly to confirm the error
                   message actually names the KMS key ARN per AC-2.3; (5) security
                   tests (AC-3.2/3.3/3.4) — all green, but AC-3.1 confirmed
                   contract-only (see Deviations — moto doesn't enforce IAM trust-
                   policy ExternalId conditions); (6) CLI integration — 4/4 tests
                   pass, read cli.py directly, --source stays optional and the
                   tenant-config path refuses cleanly when missing/disabled; (7)
                   onboarding artifact — 9/9 tests pass. Step 8 (full gate suite) run
                   fresh this session: ruff clean, mypy clean, bandit only a Low-
                   severity assert-used note (not a CI blocker — CI gates at
                   --severity-level high), quality ratchet holds (coverage 86.93% vs
                   65.08% baseline). Regression check: STORY-336 guard (47 tests incl.
                   demo corpus + existing CLI ingest) all green — AC-2.4 holds. Step 9
                   (security-auditor review, AC-3.5) is NOT done — tracked as the
                   verify-stage gate below, not silently skipped.
- [x] verify     — security-auditor review (AC-3.5) dispatched and returned
                   **PASS-WITH-FINDINGS**; AC-3.5's mandatory gate is SATISFIED.
                   No CONFIRMED or PLAUSIBLE-needs-fix issues. All 9 specific checks
                   (confused-deputy call graph, KMS error mapping leakage, read-only
                   guarantee, prefix containment end-to-end, no-secrets-in-logs
                   including an untested exception path traced manually, RLS/repr
                   redaction, allowed_s3_buckets scoping, CloudFormation least-
                   privilege, requirements.txt diff) came back clean. Three
                   non-blocking hardening notes logged as open findings (not fixed —
                   auditor's own recommendation, since none are currently-wrong
                   behavior): FND-055 (`--account-id`/`--region` CLI override can
                   silently diverge from resolved tenant config), FND-056
                   (cross_account.py credential params aren't structurally bound to
                   one tenant, caller-discipline only today). A third note (KMS-vs-
                   generic-AccessDenied classification is a cosmetic heuristic, no
                   security impact) wasn't ledger-worthy — noted here only.
                   AC-4.1/4.2 (live template deploy, timed onboarding walkthrough)
                   remain genuinely not executable in this sandbox per Decision Log
                   Q2 — flagged open, not silently checked off; folded together with
                   AC-3.1's contract-test-only gap into one pre-pilot live-AWS
                   verification pass (see Deviations).
- [ ] sell       (not design-partner-facing; on request only)

## Discover — recon findings

- **Pilot gate overridden by owner.** Story spec says "PILOT-GATED — do not build until
  SummitCare pilot is signed." Owner explicitly instructed to build now, no wait.
  AC-4.1/AC-4.2 and the Verification checklist's live-AWS items (real cross-account
  pull, template deploy-clean, timed onboarding run) require a real second AWS
  account this environment does not have — documented as NOT executable here, not
  silently marked done (see Decision Log).
- **`S3LogStore` already has a client-injection seam**: `__init__(self, bucket, *,
  prefix_root="", client=None)` (`adapters/bedrock/source.py:169-181`) lazily
  imports boto3 only when `self._client is None`. This means cross-account support
  can be added via a NEW constructor path (a classmethod building a boto3 client
  from assumed-role credentials) with ZERO changes to the existing simple-path
  behavior — AC-2.4 ("existing local/own-account paths continue to work
  unchanged") is satisfiable by construction, not by careful testing alone.
- **`LogObjectStore` Protocol is already read-only by construction**
  (`source.py:113-117`): only `iter_object_keys`/`read_bytes`. Neither
  `S3LogStore` nor any caller (`replay_backfill`, `iter_backfill_records`) ever
  exposes or calls a write method — AC-3.2's "interface-level guarantee" is
  already true today; the new work is a test that asserts it (introspection: no
  put/delete method on the class), not new production code.
- **1:1-tenant-config-table is an established pattern**: `TenantRiskConfig`
  (`models.py:1053-1087`, migration 032-adjacent) and `ClientConfig`
  (`models.py:467+`, SSO/SCIM — a different concern, not reusable) both follow
  `tenant_id UUID UNIQUE FK ondelete=CASCADE` + a migration enabling per-tenant
  RLS. STORY-408's per-tenant source config (Open Question 3) fits this
  convention exactly — no existing table to extend, a new one matches
  precedent. Next migration number: 037 (`migrations/036_observation_coverage.sql`
  is the latest).
- **boto3/moto were not installed** in this sandbox (`requirements.txt` has boto3
  commented out — "optional, only needed when AWS_S3_BUCKET is set"). Installed
  both (`pip install boto3 moto`) — network access confirmed available. boto3
  becomes a REAL (uncommented) dependency now, since cross-account role
  assumption fundamentally requires an STS client; moto is a new **test-only**
  dependency for contract-testing STS/S3/KMS without live AWS.
- **`BedrockAdapterConfig.allowed_s3_buckets`** (`records.py:32-44`) already
  exists as a security control for S3-externalized body reads (FND-1 from
  STORY-406/407's security review) — the cross-account CLI path should populate
  this from the tenant config's `bucket` automatically, tightening scope
  consistently rather than leaving it empty-by-default (deny-all) or requiring a
  separate manual flag.
- **No existing infra/deploy directory** — created `docs/deploy/` for the new
  CloudFormation template + onboarding doc (matches the `docs/` convention
  already used for architecture/compliance artifacts).

## Decision Log
Q1 CloudFormation, Terraform, or both (owner)? → **CloudFormation only.** No
  external tool dependency for the client; matches the spec's primary framing;
  keeps this story to one artifact instead of two kept in sync. Terraform can
  follow as a separate story if a specific client needs it.

Q2 Live-AWS testing given this sandbox has no AWS account (owner)? → **Build
  everything; contract-test via moto (mocked STS/S3/KMS); explicitly flag the
  live-AWS-only verification items as open, not done.** Owner rejected the
  alternative (skip tests on the AWS-dependent paths) specifically because
  AC-3.5 requires security-auditor review before merge and this story IS the
  pilot's security review surface — untested cross-account auth code would be
  the wrong thing to hand a security reviewer.
  **Concretely NOT executable in this environment** (flagged in Verification,
  not silently checked off):
    - AC-4.1: template deploy-clean in a real fresh AWS test account
    - AC-4.2: the onboarding doc's step count/time estimate performed for real
    - Verification checklist: "full pull from a second AWS account... SSE-KMS
      enabled, end-to-end to findings" — moto simulates this at the contract
      level (assume_role + S3 GetObject + our own decrypt-error-mapping code);
      it does not prove real AWS SSE-KMS transparent decryption on GetObject
      (that's on the AWS side once real credentials work, not something our
      code decrypts itself — S3 handles SSE-KMS decryption server-side given
      `kms:Decrypt`; the only thing OUR code can test is correct credential
      wiring and clear error mapping on AccessDenied).

Q3 Per-tenant source config location (recon, confirmed no owner ambiguity)? →
  **New table `tenant_log_source_configs`**, 1:1 with Tenant, matching
  `TenantRiskConfig`'s exact convention (unique FK, CASCADE delete, per-tenant
  RLS via migration). `ClientConfig` is SSO/SCIM-specific, not reusable.

Q4 Credential refresh mechanism (mine, AC-2.2 explicitly offers a choice)? →
  **botocore's refreshable-credentials mechanism**
  (`botocore.credentials.RefreshableCredentials.create_from_metadata`), not
  re-assume-per-batch. Chosen because it's transparent to every caller (the S3
  client just works, refreshing under the hood on expiry) — zero new
  orchestration code at call sites (`replay_backfill`, the CLI), versus
  re-assume-per-batch which would need new re-assumption checkpoints threaded
  through the ingest loop. This is the "least new code at the integration
  points" reading of AC-2.2, even though the refresh plumbing itself is a
  self-contained ~30-line helper.

Q5 KMS error mapping (mine, AC-2.3)? → Wrap `S3LogStore.read_bytes`'s
  `get_object` call in a try/except for `botocore.exceptions.ClientError`;
  when the error code indicates a KMS access-denied
  (`AccessDenied`/`KMS.AccessDeniedException` with "kms" in the message,
  case-insensitive), re-raise `ValueError` naming the specific KMS key ARN
  requirement. This touches the SAME method the demo/local path also calls —
  additive (adds error clarity), never changes success-path behavior, so
  AC-2.4 still holds.

Q6 allowed_s3_buckets wiring (mine, tightening not required by spec but
  consistent with existing FND-1 control)? → CLI's tenant-config resolution
  path sets `BedrockAdapterConfig(allowed_s3_buckets=frozenset({config.bucket}))`
  automatically — the operator never has to remember a separate flag, and body
  reads can't silently be scoped wider than the configured cross-account bucket.

## Plan (ordered by tweak-likelihood)

1. **Data model (tweak-likely):** `models.py` — new `TenantLogSourceConfig`
   (role_arn, external_id, bucket, prefix, region, kms_key_arn nullable,
   enabled bool, timestamps), 1:1 Tenant FK. `migrations/037_tenant_log_source_
   config.sql` — table + per-tenant RLS (mirrors migration 036's pattern).
   Verify: `python -c "from models import TenantLogSourceConfig"` + a unit test
   creating/querying one row against the in-memory sqlite fixture.
2. **Config validation (tweak-likely, AC-1.1/1.2):** new
   `services/tenant_log_source_config.py` — `validate_source_config(...)`
   (ARN-shape regex, AWS region charset, prefix normalization — mirrors
   `demo_corpus_builder.py`'s `_validate_account_id`/`_validate_region`
   discipline) + `generate_external_id()` (`secrets.token_urlsafe(32)`,
   ≥32 chars). Verify: `pytest tests/test_tenant_log_source_config.py -q`
   (valid config passes; bad ARN/region/prefix rejected; external_id length +
   entropy check; never appears in `repr()`/`__str__` — informational, not a
   hard secret, but AC-1.2 says "never logged" so representation must not leak
   it into default object printing either).
3. **Cross-account credentials (tweak-likely, AC-2.1/2.2):** new
   `adapters/bedrock/cross_account.py` — `assume_role_credentials(role_arn,
   external_id, *, sts_client=None, session_name="saro-ingest")` (calls STS
   AssumeRole, always passing `ExternalId`) +
   `refreshable_session(role_arn, external_id, region, *, sts_client=None)`
   returning a `boto3.Session` backed by `RefreshableCredentials`. Verify:
   `pytest tests/test_cross_account_credentials.py -q` (moto: assume_role
   called with correct ExternalId; a role WITHOUT the matching ExternalId
   condition fails via moto's IAM/STS enforcement — AC-3.1; credentials
   refresh transparently past a simulated expiry — AC-2.2, via a fake
   sts_client whose second call returns fresh creds and asserting the S3 call
   after "expiry" still succeeds).
4. **S3LogStore cross-account entry point (tweak-likely, AC-2.1/2.3/2.4):**
   `adapters/bedrock/source.py` — `S3LogStore.for_tenant(config: TenantLogSourceConfig,
   *, sts_client=None) -> S3LogStore` classmethod building the client from
   `refreshable_session(...)`, `prefix_root=config.prefix`. `read_bytes`
   wrapped to map a KMS AccessDenied into a clear `ValueError` naming
   `config.kms_key_arn`. Verify: `pytest tests/test_cross_account_s3_store.py
   -q` (moto S3 bucket with SSE-KMS object, assumed-role client reads it
   transparently; a role missing `kms:Decrypt` gets the clear error; existing
   `LocalLogStore`/plain `S3LogStore` tests untouched — AC-2.4 regression
   check via re-running `tests/test_story407_demo_corpus_builder.py` and
   `tests/test_cli_ingest.py` unmodified).
5. **Security tests (tweak-likely, FR-3 — the story's stated security-review
   surface):**
   - AC-3.2: `tests/test_cross_account_s3_store.py` — introspection test:
     `S3LogStore`/`LogObjectStore` expose no put/delete method.
   - AC-3.3: prefix-bound read test — a key outside `config.prefix` is never
     requested (assert via a spy on the injected client's call args across a
     `discover_object_keys` + `iter_backfill_records` run).
   - AC-3.4: `tests/test_cross_account_no_secrets_in_logs.py` — run a full
     assumed-role pull under `caplog`, assert the external_id, any
     session-token-shaped string, and object body content never appear in
     captured log text.
   Verify: the three files above, `-q`.
6. **CLI integration (tweak-likely, FR-5/AC-5.1):** `cli.py`'s `ingest`
   command — `--source` becomes optional; when absent, resolve
   `TenantLogSourceConfig` for `--tenant`, refuse (clear `CliError`) if none
   exists or `enabled=False`, else build `S3LogStore.for_tenant(...)` and set
   `allowed_s3_buckets` (Decision Log Q6). `--source` still overrides for
   demo/local use, unchanged. Verify: `pytest tests/test_cli_ingest.py -k
   tenant_source_config -q` (new tests) + full existing `test_cli_ingest.py`
   run unmodified (regression).
7. **Onboarding artifact (BUILD NOW per spec, FR-4):**
   `docs/deploy/cross-account-role.yaml` (CloudFormation: IAM role, trust
   policy with `sts:ExternalId` condition, least-privilege inline policy —
   `s3:ListBucket` prefix-conditioned, `s3:GetObject` on
   `arn:aws:s3:::<bucket>/<prefix>*`, `kms:Decrypt` on the client's key, no
   wildcards) + `docs/deploy/cross-account-onboarding.md` (one page: enable
   Bedrock invocation logging, run the template, send the role ARN — reviewed
   against ADR-004, no capability overclaims). Verify: `aws cloudformation
   validate-template` is unavailable without live AWS — verify via `python -c
   "import yaml; yaml.safe_load(open('docs/deploy/cross-account-role.yaml'))"`
   (structural YAML validity) + a checklist cross-referencing every required
   field from FR-4's bullet list. AC-4.1/4.2 flagged open (Decision Log Q2).
8. **Full gate suite (close):** ruff, mypy, pytest unit/integration/regression,
   quality ratchet, bandit — engineering-standards.md gates 1-7.
9. **security-auditor review (mandatory, AC-3.5)** — this story's explicit
   security review surface; not optional per the story's own text.

## Deviations
- **AC-3.1 confused-deputy test is contract-only, not enforcement-verified**
  (discovered during Build, prior to this session — the docstring in
  tests/test_cross_account_credentials.py already said this was logged here,
  but it wasn't; backfilling now). moto does not simulate IAM trust-policy
  `sts:ExternalId` conditions on `AssumeRole` — a fake STS client will happily
  assume a role regardless of what `ExternalId` is passed, so there is no way
  to write a moto-based test that proves "wrong external_id → AssumeRole
  denied." **Conservative option taken:** a contract test
  (`test_assume_role_always_passes_external_id`) asserting our code always
  forwards the tenant's `ExternalId` to STS — this proves the client-side half
  of the confused-deputy defense (we never omit it), but not the
  server-side/IAM half (a real AWS trust policy actually rejecting a
  mismatched id), which requires live AWS. **Aggressive option not taken:**
  standing up a real or IAM-policy-simulator-backed test account in this
  sandbox — out of scope for CI, and STORY-408's own Decision Log Q2 already
  restricts this environment to moto contract tests. This gap is functionally
  the same class as AC-4.1/4.2 (live-AWS-only verification) and should be
  folded into the same pre-pilot live-AWS verification pass, not treated as
  separately resolved.
- Session interruption: user was troubleshooting the SARO-demo-runbook-bedrock-
  synthetic-logs.md runbook (Bedrock synthetic corpus generation) in a checkout
  that already had this STORY-408 WIP uncommitted. `git pull` was blocked by the
  conflict; per user instruction, stashed the 5 tracked files, pulled `main`
  (brought in STORY-411 — UC-5 now fires in the demo corpus), then restored the
  stash. `implementation-notes.md` conflicted (upstream had FND-052's now-merged
  notes) — resolved by keeping this file's STORY-408 content, since the file
  tracks the current task, not merged history. See verify-stage note above for
  the two incidental test fixes this required.

## Live-AWS verification pass (2026-07-13)

Owner had a working AWS CLI default profile (account `080888349074`) and asked
for the pre-pilot live-AWS pass flagged open in Verify — AC-3.1's IAM
enforcement gap and AC-4.1's template deploy — to be closed now rather than
waiting for the pilot. Confirmed with the owner first that this account was
the intended disposable target before creating anything (it's authenticated
as the account root user via CLI, which matters below).

**What was actually exercised, all against live AWS, no mocks:**
- **AC-4.1 (template deploy):** `docs/deploy/cross-account-role.yaml` deployed
  clean via `aws cloudformation deploy` against a dedicated throwaway test
  bucket — `CREATE_COMPLETE` on the first attempt, no template errors. Role +
  inline least-privilege policy created exactly as authored.
- **AC-4.1 (real pull):** ran SARO's actual production code path — not a
  hand-rolled script — against the deployed role: `S3LogStore.for_tenant(...)`
  → `discover_object_keys(...)` → `iter_backfill_records(...)`. It discovered
  exactly the one in-prefix test log object (a decoy object placed outside the
  configured prefix was correctly excluded) and round-tripped the gzipped
  NDJSON record end to end.
- **AC-3.1 (confused-deputy, real IAM enforcement):** first attempt used the
  root user's own credentials and produced `AccessDenied` — but a control call
  with the *correct* external_id also failed identically
  ("Roles may not be assumed by root accounts"), proving that failure was
  AWS's blanket root-AssumeRole restriction, not the ExternalId condition.
  **Methodology correction:** created a throwaway non-root IAM user scoped to
  only `sts:AssumeRole` on the target role, and re-ran both cases through it.
  Wrong external_id → real `AccessDenied` from STS's trust-policy condition
  evaluation. Correct external_id → real assumed credentials issued. This is
  now genuine proof of server-side IAM enforcement, not contract-only.
- **Bonus, beyond the spec'd ACs:** using the live assumed-role credentials
  directly (bypassing SARO's own client-side prefix trimming), confirmed AWS
  itself denies `GetObject` on a key outside the granted prefix and denies an
  unscoped `ListBucket` with no prefix filter — the `s3:prefix` `StringLike`
  condition is real defense-in-depth at the IAM layer, not just something
  SARO's own code chooses to respect.

**Honest caveat — not literally cross-account:** only one AWS account was
available in this environment, so the "assumed-role caller" and "role owner"
were the same account (080888349074), not two separate accounts as a real
SummitCare pilot would be. The mechanism under test (STS `AssumeRole` +
`sts:ExternalId` trust-policy condition + resource-scoped IAM policy) behaves
identically regardless of whether the caller and resource are same- or
cross-account, so this is still real evidence, not a simulation — but it does
not substitute for a literal two-account pilot dry run.

**Cleanup:** every resource created for this pass (throwaway IAM test-caller
user + access key, the CloudFormation stack and its role, the test S3 bucket
and both test objects, and the local temp file holding the test-caller's
access key) was deleted in-session and confirmed gone via `describe-stacks` /
`get-user` / `get-role` / bucket `ls` all returning not-found. Nothing
persists in account `080888349074` from this verification pass.

## AC-4.2 — onboarding doc timed cold-run (2026-07-13, same session)

Followed `docs/deploy/cross-account-onboarding.md`'s 3 steps literally against
account `080888349074`, timing each. Before touching Bedrock's account-level
logging config, snapshotted the existing one — it already pointed at
`saro-demo-bedrock-logs-080888349074-us-east-1-an` for other stories'
synthetic-log demo work — and restored it byte-for-byte afterward (confirmed
via `get-model-invocation-logging-configuration` diffed against the
snapshot).

**Real defect found and fixed in the doc itself:** the Step 1 CLI example only
set `textDataDeliveryEnabled`, and AWS does not default the other three
`*DataDeliveryEnabled` flags to `false` when omitted — running it exactly as
originally written silently turned on image/embedding/video delivery too.
Fixed the doc's example to set all four flags explicitly and added a callout.
This is exactly the class of thing a cold, literal walkthrough is for —
reading the doc and reasoning about it would not have caught this.

**Timing:** Step 1 ~3s, Step 2 (CFN deploy) ~38s, Step 3 (read RoleArn) ~2s —
~81s total AWS-side command latency. This is mechanics-only, bot-executed
latency, not a human's first-time clock time (reading, decision-making,
copy-pasting your own values in) — the doc's "5–10 minutes" estimate adds
that human factor on top but has not itself been clocked against an actual
person running it cold. Flagged as such in the doc rather than presented as a
fully validated number.

**Bonus finding:** enabling Bedrock invocation logging writes a
`amazon-bedrock-logs-permission-check` marker object into the target
bucket/prefix immediately — Bedrock validates its own write access at
config time, which is why the doc doesn't need a separate bucket-policy step
for the normal (same-account) client case.

**Cleanup:** onboarding-test stack/role and bucket deleted and confirmed gone;
original Bedrock logging config restored and confirmed identical to the
pre-test snapshot; local snapshot file removed.

**Still not covered:** a literal two-account dry run with a real distinct
client account (SummitCare or an equivalent test account) — both this pass
and the earlier AC-3.1/AC-4.1 pass ran with SARO's role and the "client"
role in the same AWS account, since only one account was available here.

## Follow-up session note (2026-07-17) — landing this as its own PR

This work sat uncommitted in the working tree from a prior session. This
session: independently re-ran the full STORY-408 test suite (46 tests) fresh
rather than trusting these notes' claims — all passed; confirmed
`models.py`/`cli.py` import cleanly with `TenantLogSourceConfig`; reviewed the
migration SQL. Dispatched an independent security-auditor agent (fresh
context, told explicitly not to just trust this file's narrative) against the
actual merged diff — verdict **PASS-WITH-FINDINGS**, all 7 specific checks
(ExternalId always passed to AssumeRole, no plaintext credential/role_arn
logging, RLS matches the `tenant_risk_configs` convention, no write method
reachable via `S3LogStore`, `external_id` uses `secrets.token_urlsafe(32)`
— 256 bits, no injection vectors in role_arn/bucket/prefix/region handling,
CloudFormation policy is least-privilege with no wildcard resources/actions)
independently confirmed against the code, not just the narrative below.
FND-055/FND-056 (already logged below) re-verified accurate and correctly
scoped as non-blocking. No new blocking findings.

This PR was originally going to be scoped separately from the demo-tenant
login fix (PR #119, already merged), but PR #119 was squash-merged before
this work was staged — so this is a fresh branch off the post-#119 `main`,
containing only the STORY-408 files (the demo-login fix is already on
`main` and is not re-included here).
