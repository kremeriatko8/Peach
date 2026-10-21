> **Historical audit details:** the current [short demo release procedure](agenda-guarded-release.md)
> supersedes mandatory repeated verification and timed-smoke recommendations below.
> Shared concurrency 10 is accepted for the serial lab; no quota request is needed.

> **Infrastructure unblock plan:** [exact ECR, quota, budget and snapshot steps](agenda-infrastructure-actions.md).
> Latest backup read includes an October 18 automated snapshot; a fresh manual
> pre-migration snapshot and the existing approval gates are still required.

# Lab 6 release-readiness audit — October 18, 2026

**NOT READY for production deployment. Local implementation is ready for review.**
This is the current readiness record; earlier readiness documents contain historical
observations. No AWS mutations, inference, production SQL, migrations, commits or
pushes were performed in this audit. Safe disposable local ORM tests created their
own test database; no Alembic migration was run. Docker Desktop was started locally.

## Source and review

Branch feat/paste-agenda, starting HEAD 2f47130de827478ffacf87fbbbba25851f109ce3.
The working tree includes earlier uncommitted implementation and IAM safeguards;
no staged files. Dirty source cannot satisfy the release wrapper's exact-commit gate.
Pattern scan of changed/untracked files found no AWS access keys, private keys or
GitHub tokens. This is not a comprehensive secret-scanner attestation. Only
.env.example is tracked among environment files; real environment files and local
reports/build outputs remain ignored. No reporting source/template/workflow changed.

Parser review confirms signature/issuer/client/access-token/expiry/subject validation
before inference; source text is untrusted; only record_agenda data is exposed.
No parser DB connection, credentials or write API. GET/PUT ownership is derived
from the parent meeting's Cognito owner; reviewed saves use the existing API.
Original suggestions are stored separately from corrected fields. UI cancellation
ignores late responses but cannot undo a billable provider request. Null/ambiguous
starts remain null; timestamps require valid dates and explicit offsets; strict
models reject coercion, extras and whitespace-only topics/tasks. One repair,
max output tokens, size limits, deadline, disabled mode and manual entry remain.
Warm-instance throttling is not a durable spending cap. JWT public key snapshots
must be refreshed on key rotation; runtime does not fetch them automatically.

Official Nova documentation supports named forced tool choice and only
`type`, `properties`, `required` at the tool-schema root. The adapter follows this:
https://docs.aws.amazon.com/nova/latest/userguide/tool-choice.html
https://docs.aws.amazon.com/nova/latest/userguide/tools-troubleshooting.html
Mock/SDK tests do not establish that the full live agenda request works.

## Local fixes in this audit

- scripts/agenda-release.py: missing model-agreement metadata now fails closed.
- scripts/tests/test_agenda_release.py: missing/empty/unavailable agreement tests.
- backend/app/ai/costs.py: nonfinite configured rates return unknown cost, so the
  existing HTTP pre-inference pricing gate disables parsing.
- backend/tests/test_agenda_lambda.py: both nonfinite-rate paths tested before inference.
- Current-status links in agenda-ai.md, agenda-deployment-readiness.md,
  agenda-guarded-release.md and agenda-nova-adaptation.md supersede old observations.
- ADR 0006 now records verified access and the separate minimal smoke accurately.
- agenda-evaluation.md distinguishes that smoke from the five pending real UI cases.
- agenda-submission-template.json supplies five inputs and null actual results;
  copy into ignored reports-local/agenda before collecting real evidence.
- This audit records gates, verification limits and the ordered release below.

No API shape, database schema, IAM JSON, reporting logic or template was changed.

## Verification

- 285 selected offline backend/script tests passed, 63 subtests passed; three
  database-dependent report tests excluded from that run. Socket connections blocked.
- 216 backend tests passed on disposable localhost PostgreSQL 17.11; three private
  runner tests deselected and migration/guarded-revision/legacy-cleanup test files
  excluded. Includes auth, tasks, meetings, agenda ownership/provenance and reports.
- 93 frontend tests passed (all eight files); ESLint, Prettier and TypeScript passed.
- Backend configured Ruff lint/format and release-configured isolated script
  Ruff lint/format passed. A broad unconfigured script Ruff invocation found 19
  additional style warnings; these are outside the release's selected rule set.
- cfn-lint AI/budget templates passed. Broader backend/migrations lint found existing
  W1011 secret-parameter guidance at infra/backend.yaml:195; backend preflight needs
  the existing exact database secret and preserves it. No secret redesign was attempted.
- AWS ValidateTemplate AI/budget passed. IAM syntax/size/exact-model/boundary tests passed.
  These do not replace IAM Access Analyzer or an actual CloudFormation deployment.
- Shell syntax and git whitespace passed. Installed base dependency constraints
  passed; Linux frozen lock export/install succeeded. No vulnerability database scan
  was available (no pip-audit/gitleaks/trivy installed); none were installed.
- Final Linux ARM64 Lambda image built: local tag peach-agenda:readiness-20261018,
  image ID sha256:127e52e747cd3df178cf47b054b1fe3b72ae40a0e94ec2082b68bd0aea3e99cc.
  Five handlers import, no-JWT returns 401, container networking disabled. Image
  was not published. Build uses upstream base/uv tags: a later build can differ;
  approve and deploy the exact later verified immutable ECR digest.
- Current schema fingerprint (offline): 0005 /
  90ab389e380f6437f77290af7d63f8951ddd574987c334279f1bd0950dc09707.
  Recompute after source changes; this is not a production database revision proof.
- Frontend webpack static export passed (all seven routes). The first sandboxed
  attempt failed Google Fonts DNS resolution; the network-enabled retry passed.
  Build uses synthetic API/parser URLs and must never be uploaded; release rebuilds
  with verified production URLs. Generated artifacts stay ignored.

## Read-only AWS facts

Identity verified: arn:aws:iam::968053399627:user/sofiia, us-east-1.
Existing explicitly configured peach-reports-deploy profile used only for reporting
metadata, same account. No Root credentials, fallback access escalation or IAM changes.

| Prerequisite | Status / observed fact |
|---|---|
| Nova access | PASS: ACTIVE, ON_DEMAND, AUTHORIZED; agreement/entitlement/region AVAILABLE |
| Nova quotas | PASS: 4,000,000 TPM L-70423BF8; 200 RPM L-E386A278 |
| Prior minimal smoke | Actual prior request: 4/21 tokens, 0.869s, $0.00000528 estimate, retries 0; not an agenda/tool-use test |
| Six live Agenda IAM policies | All semantically match saved files; Readiness v3, Release v2, ParserProvisioning v1, Boundary v2, IAMAudit v1, LaptopInference v2 |
| Temporary inference access | Laptop policy zero attachments; absent from user's direct attachments |
| Boundary | Zero ordinary attachments and zero boundary uses; new role must enforce it |
| Lambda capacity | PASS for serial lab demo: total/unreserved 10; parser now uses shared concurrency without reservation |
| Shared ECR | BLOCKED: tagStatus any, expire beyond newest 3; exactly 3 existing digests, including active report and rollback images |
| Existing stacks | Backend/migrations/auth UPDATE_COMPLETE; frontend/reports CREATE_COMPLETE; no persisted service role on any inspected stack |
| Existing functions | API, runner, report builder/mailer Active / Successful, pinned images |
| Reporting schedule | ENABLED cron(0 7 ? * MON *), Europe/Kyiv; exact schedule read succeeded |
| New resources | peach-ai and peach-budget stacks absent; peach-agenda-parser Lambda absent |
| Aurora | available, encrypted PostgreSQL 17.4; 0–1 ACU / auto-pause 300s; deletion protection false; backup retention 1 day |
| Manual snapshot | BLOCKED: only visible available manual backup October 10, older than 24h |
| PITR | LatestRestorableTime returned October 12; current restore freshness is not proven; verify fresh manual snapshot after approval |
| Actual DB revision | UNKNOWN: no private SQL or migration Lambda invocation performed |
| Budget | BLOCKED: successful DescribeBudgets yielded zero budgets; no budget stack |
| Frontend hosting | CloudFront Deployed; S3 versioning response has no Status (not enabled); preserve exact objects/metadata externally before upload |
| Credits / total spend | UNKNOWN; not queried through billable Cost Explorer; Console review needed if relying on credits |

Read error: scheduler:ListSchedules was denied to peach-reports-deploy on
arn:aws:scheduler:us-east-1:968053399627:schedule/*/*. No permission was requested;
existing CloudFormation resource metadata supplied the exact schedule name and
scoped GetSchedule succeeded. Earlier IAM group listing/simulation denials remain
optional audit limitations; matching policy versions are not a full SCP/effective
permission attestation. No inference permissions are needed on the operator for
parser deployment; the future parser role receives exact-model InvokeModel.

## Prioritized blockers and smallest resolutions (separate approvals)

1. Preserve tagged images BEFORE pushing anything. Administrator reviews ECR
   lifecycle change to exclude protected tagged live/rollback/report images;
   the current wrapper accepts only untagged-only expiry (or no expiry policy).
   Retaining tagged images adds ordinary storage charges; do not delete old digests.
2. No Lambda quota increase is needed for the serial university demo. The parser
   now uses shared concurrency; retain positive capacity and run one parse at a time.
3. Review pending local diff; separately authorize commit (no push required).
   Full wrapper local-verify runs disposable migration tests, so authorize those
   local migrations separately before using it under the present restriction.
4. Supply budget email privately and approve the reviewed $5 monthly notification.
   Budget is an alert across account costs, not a hard cap. Verify notification.
5. Approve fresh Aurora manual snapshot and verify correct cluster, available,
   manual and <24h. Investigate stale LatestRestorableTime before relying on PITR.
6. Production revision stays unknown until an approved private READ ONLY path or
   approved runner code update introduces inspect_revision. Require source 0004
   (or separately reviewed 0005 retry), with a second locked check before DDL.
7. Separately approve image publication, migration/API release, disabled parser,
   activation/paid functional checks and frontend, then evidence capture/push.
   Nova is a disclosed deviation, not instructor-approved; grading acceptance unknown.

## Ordered guarded release — DO NOT EXECUTE without phase approval

Use docs/agenda-guarded-release.md and agenda-ai.md for complete commands and
parameter files. Approval strings are interlocks, not authorization by themselves.
Never run commands below as a continuation of this audit.

1. Resolve ECR retention; obtain budget email and budget approval. Review exact
   local diff and authorize commit. Serialize laptop and CI release windows.
2. After clean approved commit, set C=$(git rev-parse HEAD),
   D="$PWD/reports-local/agenda/release-$C", and
   R=(backend/.venv/bin/python scripts/agenda-release.py).
   Run `"${R[@]}" plan --commit "$C" --directory "$D"`.
3. After disposable local migration-test permission, run wrapper `local-verify`.
   It builds/imports/tests ARM64 and PostgreSQL 17, frontend/static checks, then
   binds verification proof to exact clean commit/artifacts. Today's tests are not
   that proof and must not be hand-written into verification.json.
4. After approved budget exists, run `preserve --commit "$C" --directory "$D"
   --reports-profile peach-reports-deploy`. Archives frontend contents/metadata/
   ETags and pins API/runner/report digests. Fail on retention or baseline changes.
5. After explicit snapshot approval run scripts/snapshot-backend.sh with account/
   region/profile pinned; review actual fresh ID and schema fingerprint, set
   PEACH_RELEASE_SNAPSHOT_ID and PEACH_APPROVED_MIGRATION_SHA256 privately.
6. After backend/migration approval, wrapper `backend --commit "$C" --directory
   "$D" --approve "968053399627:$C:backend"`. Publishes exact image, tests digest,
   reviews RDS-safe change set, updates existing runner, READ ONLY inspects revision,
   checks it again under lock, applies additive 0005, then updates API. Stop on
   failure; do not auto-retry. No reporting deployment or Cognito update.
7. Prepare public AI parameter JSON using the new backend digest, existing Cognito
   settings, exact frontend origin, exact Nova ARN, rates 0.06/0.24, enabled false.
   Approve wrapper `parser-disabled` to CREATE CHANGE SET ONLY; review exact changes.
   Separately approve `execute-disabled` with its exact ARN. Each needs its own
   account:commit:phase approval string. Reject persisted service roles/replacements.
8. Provide private mode-0600 short-lived Cognito access-token file. Run
   `smoke-disabled` to verify 401, oversized 413 and authenticated disabled 503.
9. Separately approve reviewed activation UPDATE change set, then wrapper
   `paid-smoke` with token file and its explicit approval. This is one HTTP parse,
   potentially two model calls (one repair). Prior plain OK smoke is not this proof.
10. Only after fresh exact-configuration paid receipt, approve wrapper `frontend`.
    It rebuilds real URLs, publishes existing S3 site and invalidates CloudFront.
11. Verify manual agenda Save, review/correction/provenance, owner isolation, tasks,
    meetings and reporting metadata without sending extra report emails. Collect
    five real cases and <=45s deployed recording under bounded paid-call approval.
12. Authorize feature-branch push when reviewed; do not merge/push main to bypass gates.

## Rollback

Preserve prior API/runner/report digests and exact frontend objects/metadata first.
On a failure stop for review. After rollback approval disable parsing, restore
previous frontend assets and compatible API image, preserving successful schema
marker and additive 0005. Verify archive hashes and review extra-file removals;
never blindly sync --delete. Do not downgrade/drop agendas, touch report resources,
or restore an old snapshot over later meeting/report data. Snapshot restore is
an exceptional data-recovery decision requiring separate impact review.

## Costs and submission

Configured standard Nova rates: $0.06/M input, $0.24/M output. At assumed 1K input +
300 output, one parse is $0.000132; 20 organizations ×30/week ×52/12 =2600/month,
$0.3432 inference before repairs, Lambda/log/S3/ECR/Aurora/snapshot costs. This is
not a measured agenda average. The assignment's $7.30/month endpoint is additional
inference infrastructure avoided here. No NAT, paid endpoint, provisioned inference
or provisioned concurrency is introduced. Cancelled/failed calls can still bill.
Existing Aurora/hosting spend and credits are not established; storage persists.

Exactly five final evidence categories:
1. GitHub commit link: implementation exists locally; review/commit/push pending.
2. <=45s deployed UI recording: pending deployment and approved parsing/save.
3. Five original assignment inputs + actual JSON/evaluation/usage/cost/latency:
   pending; agenda-submission-template.json is a skeleton, not evidence. Reuse
   Ukrainian case for recording and avoid duplicate paid runs; space requests
   at least 21s apart or honor Retry-After.
4. Real parser CloudWatch structured line: pending parser deployment/inference.
   Existing laptop OK response is not a Lambda log. agenda-evidence.py logs reads
   bounded <=1h FilterLogEvents only; never export JWT-containing HAR files.
5. Four written answers: drafts in agenda-evaluation.md; finalize from actual five
   cases. Paired held-out v1/v2 evaluation proposal is already documented; source
   text consent/retention is necessary since stored suggestions alone cannot re-run prompts.

Parser, infra/ai.yml, UI, ADR and C4 diagram exist. make llm-hello / make parse use
Nova Runtime; required Claude/AnthropicBedrockMantle is intentionally not fulfilled.
AWS reported required Claude account unavailable/zero Mantle quotas; Nova preserved
functionality without waiting for external approval. This remains an explicit
assignment deviation, NOT instructor-approved. Optional Claude comparison not run.
