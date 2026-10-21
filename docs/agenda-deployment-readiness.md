> **Current October 18 readiness:** [release audit](agenda-release-audit.md)
> supersedes historical access/build/test observations below. No deployment has occurred.
> The single approved minimal Nova smoke succeeded; agenda tool use and the five
> deployed test cases remain unverified. No additional inference is authorized here.

> **October 18 Nova adaptation:** Provider/model instructions below are historical.
> Current implementation uses amazon.nova-lite-v1:0 via Runtime Converse; see
> [current release guide](agenda-ai.md) and [ADR 0006](adr/0006-llm-agenda-parsing.md).
> This deviation from required Claude is not instructor approved. Existing infrastructure
> blockers remain; historical model checks/results are not Nova availability evidence.

# Agenda lab: reviewed deployment handoff

> October 17 update: see [guarded release procedure](agenda-guarded-release.md)
> for resolved Docker/PostgreSQL 17 checks, current blockers, and automated gates.

Preparation completed October 16, 2026 (Europe/Kyiv), on `feat/paste-agenda`.
This document supersedes the first local implementation handoff for readiness.
No resource was created/updated/deleted, no model was invoked, no production SQL
was run, and nothing was pushed. Private sanitized AWS observations are in ignored
`reports-local/agenda/`; they are not submission model-run evidence.

## Review and fixes

- Existing JWT verifier checks RSA signature, issuer, access-token type, app client,
  expiry and subject. Handler authenticates before client construction/inference.
- GET/PUT agenda ownership derives exclusively from the parent meeting's verified
  Cognito subject. Cross-account access returns 404. PUT locks the owned parent,
  validates fields and atomically saves reviewed agenda/optional meeting changes.
- Parser has no database import/URL/permissions or save capability. The browser
  separately calls the validated API after review. Parsed owner names are labels.
- Editor keeps original proposal separate from edits. Normal manual edits retain
  provenance. A newly saved parse replaces the current proposal; this is not an
  append-only history or a cryptographically signed provider receipt.
- Prompt segregates untrusted source, requests one tool call, forbids invented
  values and preserves names. Schema/ownership validation and human review limit
  damage; mocked tests cannot prove real model injection resistance.
- Fixed loss of known first-attempt token usage when a repair call has a connection
  failure. Log marks failed upstream usage incomplete; unobserved billing is unknown.
- Explicit AWS session credentials force SigV4 even if unrelated bearer-token env
  variables exist. No credentials are logged or stored in source.
- Restricted template to the default Mantle project used by the SDK. Retained
  `bedrock-mantle:Model` condition. Template rejects wildcard/invalid origins.
- Replaced assertion-based deploy checks (bypassable under Python optimization)
  with explicit validation: disabled initial state, immutable digest, finite
  positive rates, default project, public Cognito settings and 4 KB environment.
- Added explicit `FRONTEND_BUILD_ENGINE=webpack` deployment option for the locally
  verified builder; default Turbopack behavior is preserved.
- One repair maximum, SDK automatic retries disabled, 10,000-character input,
  bounded output, shared concurrency, three requests/minute/subject per warm instance.
  This is burst reduction, not a globally durable monthly spend cap. HTTP timeout
  phases and platform deadline are not a guarantee against charge on cancellation.

## Read-only AWS results

Default credentials resolve to IAM user `sofiia`, account `968053399627`, region
`us-east-1`. Existing reporting profile assumes `peach-reports-deploy` in the same
account. No alternate profile was used to broaden Bedrock permissions.

| Check | Observation |
|---|---|
| Backend / auth / migrations stacks | UPDATE_COMPLETE |
| Frontend stack | CREATE_COMPLETE |
| Backend and private runner | Active; successful last updates; ARM64; distinct pinned images |
| Cognito public keys | Deployed snapshot matches both current keys; backend env 1,297 bytes |
| Aurora | Available, PostgreSQL 17.4, private instance, 0–1 ACU, 300-second auto-pause |
| Data protection | Deletion protection false; retention 1 day; keep replacement/deletion guards |
| Visible manual snapshot | October 10, available; too old for the less-than-24-hour release gate |
| Reporting stack | CREATE_COMPLETE via existing reporting profile |
| Report Lambdas | Active/successful; both pinned to existing digest `ac2d47b04a705075df2e2c09fc0106c771f423fae008d7a7df2d775541935629` |
| Weekly schedule | ENABLED, cron(0 7 ? * MON *), Europe/Kyiv |
| Actual DB revision | Not verified: no safe private SQL path used and runner was NOT invoked |
| Backend release marker | Existing fingerprint differs from local 0005; schema release required |
| AI/budget stack existence | Unknown: DescribeStacks denied; do not infer absence |
| Bedrock model access | Metadata/availability reads denied; access and agreement requirements unknown |
| Mantle default project / model | Signed GETs returned 403 GetProject / GetModel |
| Inference IAM simulation | iam:SimulatePrincipalPolicy denied; no actual inference attempted |
| Budgets / quotas | Denied; existing budget/email and concurrency/model quota unknown |
| ECR retention policy | GetLifecyclePolicy denied; preserve report and rollback digests before publishing |

Exact blocked read actions (not a request for broad access):

- `bedrock:ListFoundationModels`; `bedrock:GetFoundationModelAvailability` on the
  configured model. Mantle is authoritative for this newer model path; successful
  legacy discovery alone would not prove Mantle inference access.
- `bedrock-mantle:GetProject`, `bedrock-mantle:GetModel` on
  `arn:aws:bedrock-mantle:us-east-1:968053399627:project/default`.
- `iam:SimulatePrincipalPolicy` on the current IAM user; an authorized admin can
  inspect effective policies instead. Simulation is not a guarantee against SCPs,
  permission boundaries or runtime model-access restrictions.
- `budgets:ViewBudget` on account budgets.
- `servicequotas:ListServiceQuotas`; `lambda:GetAccountSettings`.
- `ecr:GetLifecyclePolicy` on existing `peach-backend` repository.
- `cloudformation:DescribeStacks` for `peach-ai` and `peach-budget`.

Default-user reporting reads were denied, but the already configured reporting
profile completed the scoped checks; no additional reporting permissions needed.
No policies were attached/changed. An authorized administrator can supply read
results or narrowly grant these reads; AdministratorAccess is unnecessary.

## New and changed resources

| Scope | Intended changes after approval |
|---|---|
| Existing backend ECR | Publish one new immutable ARM64 image; retain old API/runner/report digests |
| Existing migration stack | Update runner image only; existing VPC/role/DB configuration preserved |
| Existing Aurora schema | Add `agendas` via 0005; no existing task/meeting columns/rows rewritten |
| Existing backend stack | Update API image and successful schema marker; no RDS replacement or recreation |
| Separate AI stack | IAM role + inline scoped policy, seven-day log group, 512 MB/30 s Lambda outside VPC, shared concurrency, Function URL and two invoke permissions |
| Separate budget stack | Optional account-wide monthly USD 5 budget and email notification after duplicate/email review |
| Existing frontend | Rebuild/upload static files with parser URL; CloudFront invalidation; no hosting redesign |
| Reporting / Cognito | No template, image, schedule, identity-provider or policy changes |

A backend release does not deploy reporting. The pinned reporting images stay
unchanged. Indirect shared risks are Aurora connection/lock/load, deleting a shared
ECR image, an unsafe RDS change set, or restoring an old database snapshot. Additive
schema and fail-closed release guards reduce these risks, but do not prove zero
production impact. Existing task/meeting/report tests pass on a disposable DB.

## Exact deployment order and approval gates

1. **Readiness, no deployment:** resolve the denied reads; verify actual DB revision
   through an already approved read-only private connection or trusted release
   evidence. Never invoke the migration runner to discover revision. Confirm AI
   stack create/update type, effective IAM, model access, quota for reserved
   shared concurrency availability, budget email and rates.
   Validate ARM64 Linux image and PostgreSQL 17 compatibility before production.
2. **Backup approval:** preserve current image digests/frontend rollback assets and
   reporting baseline. Create a new manual Aurora snapshot with the existing
   `scripts/snapshot-backend.sh` procedure and verify available/<24 hours. This is
   an explicit AWS mutation and was not performed during preflight.
3. **Budget approval:** inspect existing budgets first, then create/update only the
   reviewed USD 5 email alert with `infra/budget.yml`. This is an alert, not a cap.
4. **Backend release approval:** compute
   `backend/.venv/bin/python scripts/schema-release.py`. Review/finalize manifest,
   set exact `PEACH_APPROVED_MIGRATION_SHA256` and fresh
   `PEACH_RELEASE_SNAPSHOT_ID`, then run existing `make deploy-backend` using the
   approved deployment identity. It publishes the immutable image, checks the
   public change set for RDS safety, updates private runner, migrates/verifies
   0005, then executes the exact API change set. Ordinary main pushes deploy;
   do not push/merge until separately authorized. CI ignores root .env and needs
   temporary OIDC credentials and repository release variables.
5. **Disabled AI stack approval:** use the same new reviewed image digest, existing
   public Cognito configuration, exact frontend origin, default Mantle project ARN,
   verified rates and ParserEnabled=false. Run
   `PEACH_APPROVE_AI_DEPLOY=yes AI_PARAMETERS_FILE=... make ai-prepare-deploy`.
   Review the generated change set, then separately approve its execution. It
   remains disabled; no database permissions or network resources are created.
6. **Paid-call/activation approval:** verify authentication rejection and disabled
   behavior first. Create/review an UPDATE change set setting ParserEnabled=true
   with otherwise preserved parameters, then execute and make one approved parse.
   Document latency/permissions/usage; no automatic Marketplace subscription or
   broad runtime access. Commands are in agenda-ai.md.
7. **Frontend approval:** set `PARSER_URL` to the verified HTTPS Function URL and run
   `FRONTEND_BUILD_ENGINE=webpack make deploy-frontend` on the reviewed build host.
   The deploy script now supports this explicit fallback while retaining Turbopack
   as its default. The exact webpack static export passed locally. This command
   remains a production mutation requiring separate approval.
   Frontend may be delayed until endpoint is ready; backend remains compatible with
   the old frontend. Manual agenda operation does not depend on parser availability.
8. Verify owner isolation, manual Save, parse/review/correction/Save, CORS/preflight,
   and existing meeting/task/report behavior. Avoid triggering extra report emails.

Runtime permission: `bedrock-mantle:CreateInference` on default project with exact
model condition, and CloudWatch writes to its own log group. Deployer separately
needs scoped CloudFormation/IAM create-role/inline-policy/PassRole, Lambda URL/
permissions/configuration, logs and ECR image access; the guarded backend deployer
needs its existing RDS/secret/network reads and private migration invocation.
No runtime Marketplace subscribe, project creation, S3, SES, DynamoDB, Aurora or
Secrets Manager access is added to the parser.

## Configuration

Required parser values: public `COGNITO_AUTHORITY`, `COGNITO_CLIENT_ID`,
`COGNITO_JWKS_JSON`; `PARSER_MODEL`; verified positive
`PARSER_INPUT_USD_PER_MILLION` / `PARSER_OUTPUT_USD_PER_MILLION`;
`PARSER_ENABLED` (false until approved), token/request bounds supplied by template.
Existing template uses ARM64, 512 MB, 30 seconds, no reserved concurrency for the low-traffic lab. Deployment
helper validates initial disabled state and 4 KB environment limit. Existing DB
connection/settings are reused by the API only. Frontend needs `PARSER_URL` at
build time; local frontend uses `NEXT_PUBLIC_PARSER_URL`. Credentials never enter
the browser. Helper creates a change set; it neither executes nor activates it.

## Costs

AWS public regional catalog published 2026-10-12 lists Opus 5.5 standard us-east-1
input $4.40 / million and output $22 / million tokens. Global SKUs ($4/$20) also
exist; the regional endpoint used here should use regional configuration, and
billing should be checked during the first approved run. Source:
https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonBedrockFoundationModels/current/us-east-1/index.json

Illustration only, not measured: 1,000 input + 300 output tokens = $0.011 per parse;
2,600/month = $28.60 inference. Repair calls add their actual input/output usage;
a repeat at identical usage would double that figure. At 2,048 output tokens,
one attempt alone can cost $0.045056 for output plus input; two attempts can cost
$0.090112 output plus input. The $5 alarm will not sustain that monthly example.

No new NAT/interface endpoint/provisioned-throughput/idle Lambda compute charge.
Incremental recurring costs are image/log storage, saved agenda/Aurora storage and
snapshot retention, plus usage-based Lambda/inference and any existing hosting
traffic. Credits/free-tier eligibility, taxes and current total account spend are
not verified. Budget covers existing account spend too. The assignment's $7.30
endpoint would be additional to inference, not an alternative to token charges.

## Rollback

Disable parser with reviewed CloudFormation parameter update (ParserEnabled=false),
or set reserved concurrency to zero through an explicitly approved emergency
change. Revert static frontend to retained assets and API image to the verified
compatible previous digest. Preserve the current successful schema marker and
0005 schema; never downgrade/drop agendas/meetings for routine rollback. If the
migration fails, transaction/runner guards stop API update; inspect before retry.
If migration succeeds but API fails, retain additive schema and investigate the
exact change set. Do not restore a stale snapshot over post-snapshot meetings or
weekly-report data. Leave reporting images, queues, bucket and schedule untouched.

## Shortest path to the five submission artifacts

Resolve read/access/build gates → approve snapshot/budget/backend/disabled parser →
approve paid activation + frontend deployment → run five cases once through the
deployed frontend → capture one real log and <=45 s correction/Save recording →
complete evaluation/answers and, when push is approved, publish the local commit.
A local commit hash is ready for a future link but is not yet a reachable Moodle
GitHub artifact. No model outputs or logs may be fabricated.

## Final local verification

- Backend: **209 passed** against disposable localhost PostgreSQL 16.2, including
  existing meetings/tasks/auth/reporting, real additive migrations, ownership,
  parser/Lambda and SDK transport tests. No PostgreSQL 17 or Linux container run
  was possible: Docker daemon/Desktop is unavailable on this host.
- Deployment scripts: **120 passed, 58 subtests passed**; includes fail-closed
  schema-release and new AI parameter validation tests.
- Frontend: **93 passed**; ESLint, Prettier and TypeScript passed.
- Ruff backend and scripts lint/format, shell syntax and whitespace checks passed.
- cfn-lint AI/budget templates passed. Supported webpack static export passed.
- Local migration manifest: head `0005`, SHA-256
  `524f25167e7d1b629eaa5eee7d2fbd6c3c94f0ef62d8adf2376ca8a0addec33d`.
  Recompute after any later migration/model/runner edit; never seed the deployed
  marker manually.

Host uv is currently available at `/private/tmp/peach-agenda-tools/bin/uv`; add its
bin directory to PATH or install the normal project tool before approved Make
commands. Temporary tools are not committed. Backend venv and frontend dependencies
are ignored. The disposable PostgreSQL instance is stopped after verification.

## Complete administrative-session policy bundle

See [one-session IAM bundle](../infra/iam/agenda/ADMIN-SESSION.md) for the complete scoped operator policies, parser runtime boundary,
verified permission evidence, validation limits and a single Console checklist.
It supersedes the earlier incremental read-only attachment recommendation.
No AWS policy was attached.
