# SARO Cross-Account Log Access — Client Setup

**Audience:** your cloud/platform engineer. **Estimated time:** 5–10 minutes
of active work for someone comfortable with the AWS CLI (3 commands total).
Validated against a real AWS account on 2026-07-13 — see the note at the
bottom for exactly what that validation did and did not cover.

SARO reads your Amazon Bedrock model-invocation logs by assuming a read-only
IAM role you create and control. SARO never receives your AWS credentials,
never writes to your account, and can only read the specific S3 prefix you
configure. You can revoke access at any time by deleting the role.

## What you're granting

The template below creates exactly one IAM role with:
- **Read-only** `s3:ListBucket` (scoped to your log prefix) and `s3:GetObject`
  on your log bucket — no `PutObject`, no `DeleteObject`, no wildcard resource.
- Optionally `kms:Decrypt` on your log-encryption key, if you use SSE-KMS.
- A trust condition (`sts:ExternalId`) that only SARO's issued external ID can
  satisfy — no one else can assume this role even if they learn the role ARN.

Nothing else. SARO has no visibility into any other resource in your account.

## Steps

1. **Enable Bedrock model-invocation logging to S3**, if not already enabled.
   - Console: Bedrock → Settings → Model invocation logging → enable "S3" as
     the delivery destination, choose your bucket and prefix.
   - CLI alternative:
     ```
     aws bedrock put-model-invocation-logging-configuration \
       --logging-config '{"s3Config":{"bucketName":"<your-bucket>","keyPrefix":"<your-prefix>"},"textDataDeliveryEnabled":true,"imageDataDeliveryEnabled":false,"embeddingDataDeliveryEnabled":false,"videoDataDeliveryEnabled":false,"audioDataDeliveryEnabled":false}'
     ```
     **Set every `*DataDeliveryEnabled` flag explicitly.** AWS does not default
     an omitted flag to `false` — a real run of this exact command with only
     `textDataDeliveryEnabled` set came back with image/embedding/video
     delivery all silently turned on. If you only intend to log text
     invocations, say so explicitly for every modality or you will deliver
     more than you intended.
2. **Deploy the role template** (`cross-account-role.yaml` in this directory),
   using the SARO account ID and External ID SARO gave you during onboarding:
   ```
   aws cloudformation deploy \
     --template-file cross-account-role.yaml \
     --stack-name saro-cross-account-access \
     --capabilities CAPABILITY_NAMED_IAM \
     --parameter-overrides \
         SaroAccountId=<saro-account-id> \
         ExternalId=<external-id-saro-gave-you> \
         LogBucketName=<your-bucket> \
         LogPrefix=<your-prefix> \
         LogKmsKeyArn=<your-kms-key-arn-if-any>
   ```
3. **Send SARO the role ARN** from the stack output (`RoleArn`). That's the
   only thing SARO needs back from you.

## What SARO does NOT do

- SARO does not certify or guarantee your AWS account's security posture —
  this template is scoped narrowly to the access it needs, not a general
  security review of your environment.
- SARO does not modify, delete, or write to anything in your account.
- SARO does not require you to disable any existing logging, monitoring, or
  security tooling.

## Validation status (STORY-408 AC-4.1 / AC-4.2)

**Executed for real against AWS account 080888349074 on 2026-07-13**, all
three steps in order, timed:
- Step 1 (enable Bedrock invocation logging to a test bucket): ~3s of AWS API
  time. Surfaced the data-delivery-flags defect fixed above — the very
  reason to run this cold instead of trusting the doc as written.
- Step 2 (deploy `cross-account-role.yaml`): ~38s of AWS API time
  (CloudFormation changeset creation + stack `CREATE_COMPLETE`).
- Step 3 (read `RoleArn` from stack outputs): ~2s.
- Total observed AWS-side command latency: **~81 seconds**. The 5–10 minute
  estimate above adds realistic human time (reading each step, filling in
  your own bucket/prefix/account values, copy-pasting the output back) on top
  of that — the 5–10 minute figure itself has not been clocked against an
  actual first-time human run, only the mechanics and mechanics-only latency
  have been.
- Bonus finding: enabling Bedrock invocation logging writes a
  `amazon-bedrock-logs-permission-check` marker object into your bucket/prefix
  immediately — this is Bedrock validating its own write access at
  configuration time, which is why the doc does not need a separate
  bucket-policy step for the normal case (your own bucket, your own account).

**Not covered by this pass:** a literal two-account dry run (client account
distinct from SARO's account) — only one AWS account was available, so the
"client" and "SARO" roles in this test were the same account. The IAM
mechanism (trust-policy `ExternalId` condition, resource-scoped policy) is
verified for real elsewhere (see STORY-408's implementation notes,
2026-07-13 live-AWS verification pass) and behaves identically regardless of
account topology, but a true cross-account SummitCare dry run before go-live
is still the strongest remaining validation step.
