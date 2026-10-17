# Guarded agenda release — October 17 preparation

**NO-GO for production until the access and approval gates below are resolved.**
No AWS resources were changed, no snapshot created, no production SQL executed,
no inference invoked, and nothing pushed/merged during this preparation.

Starting branch/commit were exactly `feat/paste-agenda` /
`5dd75e6a67dd2607b4ae30516e4968b15b097bf6`, with a clean working tree. The safeguards are committed separately during the authorized preparation stage.
Pin the resulting full HEAD commit below: the runner event contract/fingerprint
has changed. Do not pin the old implementation commit with the new scripts.

## Resolved locally

- Docker Desktop is installed and starts successfully (engine 29.8.1).
- Linux ARM64 Lambda image builds with locked dependencies on the AWS Python 3.14
  base. All five handlers import with networking disabled, and missing JWT returns
  401 without model access. Local image `peach-agenda:release-prep-local` is retained.
- **210 backend tests passed against disposable PostgreSQL 17.**
- The actual Linux image also migrated a separate disposable PostgreSQL 17 DB
  from 0004 to 0005 and returned all schema/data-preservation proofs.
- Added a private READ ONLY revision-inspection action and a server-side,
  transactionally locked source-revision comparison before Alembic. The backend deployment sends expected_from=0004 (or approved retry 0005)
  and requires the matching returned proof. Unexpected revision fails before DDL.
- Captured 121 deployed frontend objects, ETags, metadata and SHA-256 hashes in
  ignored `reports-local/agenda/current-production-archive/`. Current backend,
  runner and report digests are recorded in private read-only preflight observations.
  Release-time preservation recaptures and rechecks these; today's archive is not
  a permanent guarantee that production will remain unchanged.

## Read-only AWS recheck

Account remains `968053399627`, region `us-east-1`, operator IAM user `sofiia`.
Backend/auth/migration/frontend stacks and private Aurora 17.4 remain stable.
Cognito snapshot still matches current public keys. Existing reporting identity
confirms active report functions and unchanged enabled Monday 07:00 Kyiv schedule.
Both configured profiles were explicitly checked for the missing reads; both
returned AccessDenied/403. No other configured authorized profile is available.
The GitHub OIDC role is not a laptop fallback; no trust or permission was changed.

The same access denials remain. The exact action/resource/reason/essential-vs-
optional matrix and an additive **read-only** policy are in
[infra/iam/agenda/README.md](../infra/iam/agenda/README.md) and
[readiness-readonly.json](../infra/iam/agenda/readiness-readonly.json).
Those files are proposals only; nothing was attached. An administrator can provide
results instead of granting reads. No AdministratorAccess or laptop inference
permission is requested by that policy.

Actual Aurora revision is **unknown today**: the deployed runner does not yet have
our new read-only inspection action, and no approved private SQL route is configured.
No runner was invoked to discover it. The prepared release resolves this without
new networking: after the separately approved runner code update, it invokes only
`inspect_revision` (READ ONLY transaction), checks the expected source revision,
then permits migration. A second locked comparison occurs immediately before DDL.
The only visible available manual snapshot is October 10; it fails the <24h gate.
No fresh snapshot can be created without the separate approval explicitly required
by this task. AI/budget stack absence must not be inferred from AccessDenied.

## Release automation

`scripts/agenda-release.py` has explicit phases. `plan` is offline and never deploys.
Other phases refuse dirty source, wrong account/region/branch/commit, changed
artifacts, missing rollback state or failed prerequisites. Mutation approval strings
are operator interlocks, not substitutes for the user's permission.

The automation never attaches IAM policies, creates snapshots, creates budgets,
activates parsing, pushes commits, creates NAT/endpoints, or silently invokes models.
Only `paid-smoke` can request inference, and it requires its own explicit approval.
No mutation phase has been run during preparation.

The current script is intentionally fail-closed if the account's service-quota
API does not identify a positive applicable Mantle/Opus 5.5 quota. Do not treat an
old-model quota as this model's quota. Have the administrator supply the exact
account-specific limit and adapt the reviewed quota query if necessary.

### 1. Local review, commit and exact-artifact verification (no AWS)

After the authorized safeguard commit, pin and verify the resulting full commit:

```sh
C=$(git rev-parse HEAD)
D="$PWD/reports-local/agenda/release-$C"
R=(backend/.venv/bin/python scripts/agenda-release.py)
"${R[@]}" plan --commit "$C" --directory "$D"
"${R[@]}" local-verify --commit "$C" --directory "$D"
```

`local-verify` builds Linux ARM64, tests handler imports without networking, runs
backend/script tests using its own temporary PostgreSQL 17 container, checks the
frontend and builds static export. It cleans up its own PG container and writes
commit-bound verification state only after success. Fonts/packages may require
ordinary download access; no AWS credentials are needed by tests. Ruff/cfn-lint
checks are included and must pass before the verification proof is written. No image is published.

### 2. Resolve read prerequisites, private revision access and rollback preservation

Have the administrator review the narrow read policy or provide verified results.
Confirm the intended budget email, then explicitly approve creation of the reviewed
$5 budget if no matching notification exists. Budget API IAM authorization is
`budgets:ModifyBudget` for create/update, separately from read-only ViewBudget.
Do not grant a nonexistent permission merely because the API is called CreateBudget.

Supply `PEACH_BUDGET_EMAIL` privately. No new private network connection is required
for the normal release path: the existing IAM-only migration runner gains the
explicit `inspect_revision` action. After approved image publication/runner update,
the backend script checks its actual read-only result before it invokes migration.
Default expected source is 0004; an explicitly reviewed retry may use
`--expected-db-revision 0005`. Unexpected revision stops before DDL/API change.
Today that action is not deployed, so it must not be invoked against production.

If an approved private route already exists and earlier revision inspection is
wanted, optional `check-db` accepts `PEACH_READONLY_DATABASE_URL` and optional
`PEACH_RDS_CA_FILE` privately. It requires the live Aurora endpoint/DB and verified
TLS, opens only a read-only repeatable-read transaction, and never migrates or
changes networking. Do not introduce NAT, an endpoint, or a public DB port. Even
a read can wake paused Aurora and use existing compute.

```sh
# Optional only when an existing approved private SQL route is available:
# "${R[@]}" check-db --commit "$C" --directory "$D"
"${R[@]}" preserve --commit "$C" --directory "$D" \
  --reports-profile peach-reports-deploy
```

`preserve` requires the prior exact-commit verification, model/project metadata,
capacity, quota, budget and AI/budget stack reads. It archives coherent frontend
objects with metadata, hashes and ETags; saves current API/runner/report image
identities; and checks ECR policy cannot expire the protected tagged images. It
will not change lifecycle rules or tag/delete images to bypass a retention issue.
Repeated preservation uses a new directory instead of overwriting rollback state.
If --profile is needed, pass the same intended deployment profile to every phase.

### 3. Snapshot and schema release (AWS mutations — separate approval)

After explicit backup approval only, use existing `scripts/snapshot-backend.sh`
with the intended account/profile/region verified first. It creates and waits for
a manual snapshot; record its identifier as `PEACH_RELEASE_SNAPSHOT_ID`. The release
phase rechecks exact cluster, available/manual state, and freshness <24 hours.
Nothing in agenda-release.py creates a snapshot automatically.

```sh
# STOP: obtain separate approval for creating this billable backup first.
# Explicitly verify the intended identity and account immediately before running:
AWS_PROFILE=default AWS_REGION=us-east-1 aws sts get-caller-identity
# After approval only (script prints the new verified identifier):
AWS_PROFILE=default AWS_REGION=us-east-1 PROJECT_NAME=peach STACK_NAME=peach-backend \
  bash scripts/snapshot-backend.sh
# Set privately to the identifier actually returned; do not use the old backup:
export PEACH_RELEASE_SNAPSHOT_ID=ACTUAL_VERIFIED_FRESH_SNAPSHOT_ID
# Set to the manifest hash explicitly reviewed, never an automatic command substitution:
export PEACH_APPROVED_MIGRATION_SHA256=REVIEWED_MANIFEST_HASH
```


Recompute the manifest with `backend/.venv/bin/python scripts/schema-release.py`.
Review the new hash and explicitly approve it as
`PEACH_APPROVED_MIGRATION_SHA256`; do not reuse the old hash after runner changes.

```sh
# After explicit approval of snapshot, image publication, migration and API release:
"${R[@]}" backend --commit "$C" --directory "$D" \
  --approve "968053399627:$C:backend"
```

Before mutations it repeats metadata/budget/capacity checks, baseline/image/archive
checks, snapshot and fingerprint checks (plus optional direct private DB read).
Existing backend release then publishes the image, checks the exact public change
set for RDS safety, smoke-tests the exact published digest with container networking disabled,
updates private runner, invokes its strictly read-only revision inspection and checks the approved source revision, compares it again inside the
migration transaction, upgrades to 0005 with preservation verification,
and updates API only after success. Reporting templates/images/schedule are not
updated. If anything fails, stop and inspect; do not automatically retry a partial
release. Snapshot restore is not routine rollback.

### 4. Disabled parser change set and execution (separate AWS approvals)

Prepare the public parameter JSON described in agenda-ai.md, using the exact
post-release backend digest in `$D/release.json`, current public Cognito settings,
frontend origin, default project ARN, reviewed rates and ParserEnabled=false.
The wrapper checks auth values and digest against the live backend and validates
all initial parameter constraints.

```sh
"${R[@]}" parser-disabled --commit "$C" --directory "$D" \
  --ai-parameters /private/tmp/ai-parameters.json \
  --approve "968053399627:$C:parser-disabled"
# Review the resulting exact change-set ARN/template/permissions, then separately approve:
"${R[@]}" execute-disabled --commit "$C" --directory "$D" \
  --change-set-id REVIEWED_EXACT_CHANGE_SET_ARN \
  --approve "968053399627:$C:execute-disabled"
```

Execution refuses unexpected resources/removals, enabled parameters, wrong image
or a stored template different from reviewed infra/ai.yml. If CloudFormation returns
a different template representation, stop for inspection rather than weakening the
comparison. Parser remains disabled after deployment.

Obtain one short-lived **access token** from your signed-in application session.
Save it privately to a mode-0600 file without posting it in chat or command history.
No OAuth password collection or new identity resources are needed.

```sh
"${R[@]}" smoke-disabled --commit "$C" --directory "$D" \
  --token-file /private/tmp/peach-access-token
```

This tests 401 without JWT, 413 oversized, and 503 disabled with a valid token.
It will not send a valid parse to a configuration it observes as enabled. A concurrent
configuration change is an operator risk: do not activate while disabled checks run.

### 5. Separate activation + one paid smoke, then frontend

After an explicit activation decision, use the reviewed UPDATE change-set commands
in agenda-ai.md to set ParserEnabled=true while preserving the other parameters.
This procedure does not activate automatically. Separately authorize a paid smoke:

```sh
"${R[@]}" paid-smoke --commit "$C" --directory "$D" \
  --token-file /private/tmp/peach-access-token \
  --approve "968053399627:$C:paid-smoke"
# Only after successful actual functional smoke and explicit frontend deployment approval:
"${R[@]}" frontend --commit "$C" --directory "$D" \
  --approve "968053399627:$C:frontend"
```

Paid smoke makes one normal parse request (parser may use its one allowed repair),
records actual JSON/metrics and request ID, and never retries automatically. Frontend
requires its receipt to be <15 minutes old and bound to the same commit, image,
URL and unchanged Lambda LastModified; it also checks model/isolation/concurrency.
It cannot deploy based on a mock smoke receipt created by this preparation.
The frontend phase uses the verified webpack builder. A user with write access to
local state can tamper with a receipt: these are operator interlocks, not signed
external attestations. Keep the release directory private and review it.

## Cost verification

Re-read the public us-east-1 catalog on October 17: its publication is still
2026-10-12 and regional standard Opus 5.5 is **$4.40/M input, $22/M output**; global
SKUs differ ($4/$20) and are not silently substituted. Model is unchanged.
Rates remain configuration, not hardcoded parser constants. Illustrative (not
measured) 1,000 input + 300 output = $0.011; ~2,600/month = $28.60 before repairs,
Lambda/log/storage. $5 is an alert, not a cap, and covers existing account costs too.
Two max-output attempts can cost $0.090112 output alone plus input. Cancelled or
failed responses may still incur charges. Warm-instance rate limiting resets on
cold start. No NAT, interface endpoint or provisioned throughput is introduced.

## Minimum operator/admin actions still needed

1. Review/grant the narrowly scoped reads or supply the equivalent results,
   including applicable model quota, model entitlement and budget-email status.
   Deployment IAM must separately permit only the reviewed release resources;
   simulation is optional and not a substitute for effective IAM/SCP review.
2. Provide the intended budget email. The old snapshot is insufficient; explicitly
   approve a fresh one and the private runner code update/read-only inspection as
   part of the guarded release. No new database route/credentials are required.
3. The local safeguard commit is authorized and completed during this preparation;
   separately authorize the staged release mutations above. No push/main merge is needed to perform a locally approved release.
4. Sign in once to provide a private short-lived access-token file; explicitly
   authorize parser activation and paid requests separately from disabled deployment.
5. Finally approve frontend publication and, when ready, feature-branch push for
   the public commit link. Publishing a link is distinct from production CI/main.

## Rollback

Before frontend mutation, preserve the archive/metadata/ETags and image identities.
After separately approved rollback, disable parser (or set concurrency zero in an
approved emergency), restore API image and exact prior frontend objects with their
recorded ContentType/CacheControl/ContentEncoding/Metadata, then invalidate the
existing CloudFront distribution. Verify hashes before upload and review any new
object deletions separately; do not blindly run `s3 sync --delete`. Keep current
schema marker and additive 0005. Do not downgrade/drop agendas or restore an old
snapshot over newer meeting/report data. Leave reporting images and schedule alone.

## Five submission categories with minimum repeated work

1. After separately approved feature-branch push, use the release commit URL.
2. Record one <=45s deployed UI flow: paste → Parse → edit one field → Save. Use
   the Ukrainian case to serve both recording and test evidence.
3. Run the five assignment cases once in deployed UI with fixed recorded local
   date/timezone. Capture actual parser responses in browser Network; copy response
   bodies only, never a HAR containing Authorization headers. Put input, actual
   response, status and human annotations into a private JSON object with
   `frontend_url`, `commit`, `today`, `tz`, `cases` (IDs 1..5). Generate the table:
   `backend/.venv/bin/python scripts/agenda-evidence.py table --input PRIVATE.json
   --output reports-local/agenda/submission/test-table.md`.
4. Collect actual existing logs with the helper's `logs --start-ms ... --end-ms ...
   --output reports-local/agenda/submission/logs.json` in a bounded <=1h window.
   This performs only FilterLogEvents; no inference or log examples are fabricated.
5. Replace pending answers in docs/agenda-evaluation.md with measured observations,
   sum repairs' tokens/cost, calculate monthly scenario and describe paired held-out
   v1/v2 evaluation. No new models need to be called for the theoretical v2 answer.


Serialize this release window with other local/CI releases and parser configuration
changes. GitHub's workflow concurrency lock does not lock a separately run laptop
script. No main push is needed, and this preparation did not trigger production CI.

## Final preparation verification

| Check | October 17 result |
|---|---|
| PostgreSQL 17.11 backend suite | 210 passed |
| Deployment/evidence/release scripts | 129 passed, 63 subtests passed |
| Final release/evidence helper regression subset | 9 passed |
| Frontend suite / ESLint / TypeScript / Prettier | 93 passed; all checks passed |
| Ruff backend/scripts, shell syntax, whitespace | Passed |
| cfn-lint AI/budget templates | Passed |
| Actual Linux ARM64 image | Build/import/auth checks passed |
| Linux image + PostgreSQL 17 | READ ONLY revision inspection and guarded 0004→0005 passed |
| Frontend rollback archive | 121 files; all local SHA-256 hashes and current S3 ETags match |
| Production mutation/inference paths | Prepared and unit-tested only; NOT executed/integration-verified on AWS |

Local PostgreSQL container was removed after testing; local images/ignored rollback
artifacts remain. PostgreSQL major-version compatibility is verified, but this is
not an Aurora production network/permission/load test. The current new migration
fingerprint is `90ab389e380f6437f77290af7d63f8951ddd574987c334279f1bd0950dc09707`;
recompute after any later runner/model/migration edit and review the exact value.

For the five UI cases, allow at least 21 seconds between Parse starts (or wait out
Retry-After) to stay within the three-per-minute warm-instance limit. Use the first
mandatory case for the short recording instead of paying for a separate demo run.
Unauthenticated requests cannot invoke Bedrock but still consume ordinary public
Lambda requests/compute. Budget notifications are delayed alerts, not automatic
shutdown. No new paid abuse-protection service was introduced.

## Identity and target isolation

The release wrapper freezes the credentials from the session whose account STS
verified, removes inherited profile/session selection, pins all Peach stack/repository
names and ARM64, and prevents child scripts from sourcing root `.env`. Frontend
builds use the live verified API URL. Ordinary scripts retain their existing behavior
outside the wrapper. Credentials stay in child-process environment only and are
never written to release state or logs. Expired role credentials stop the release;
obtain a fresh session and review partial state before any retry.

The initial read policy and later release-verification reads are separate. Follow
[the minimal administrator Console checklist](../infra/iam/agenda/README.md#minimum-console-actions-administrator-after-separate-permission-approval).
After reads succeed, review budget/model/quota/retention results. Only then can a
separately authorized snapshot, existing guarded backend+0005 release, and isolated
disabled AI stack proceed. These stages do not update `infra/reports.yml`, report
images, report IAM, reporting schedule or existing report objects. The shared ECR
repository still requires the retention gate to protect those images.
