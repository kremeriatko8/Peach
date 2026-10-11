# Weekly Reports final audit — 2026-10-11, Europe/Kyiv

Status update (2026-10-11): scoped S3 HEAD and DynamoDB SENT evidence checks
now pass. The existing schedule is ENABLED for October 12 at 07:00 Kyiv; W41
is still pending. The dated audit/preparation details below record the earlier
snapshot and must not be interpreted as the current schedule state.

Verdict: NOT COMPLETE. Manual report is proven end to end; real scheduled report,
two distinct production CSVs and live failure demonstration remain unverified.
This audit made only AWS reads, local test-database operations and this local
report. No schedules, reports, policies, infrastructure or production data changed.

Sources: Phase 2 and Phase 3 pasted user requirements; infra/reports.yaml;
backend/app/reports/*; backend/app/reporting/*; scripts/report-now.py; deployment
scripts/workflows; docs/reporting.md; live CloudFormation/Lambda/Scheduler/SQS/S3
and runtime-role evidence. PASS for implementation does not imply a live test.

| Requirement | Status | Evidence / remaining work |
|---|---|---|
| Separate deliberate reporting deployment, 20 resources | PASS | Live stack CREATE_COMPLETE; all 20 resources CREATE_COMPLETE. |
| Scheduler Monday 07:00 Europe/Kyiv, flexible window OFF | PASS | Live cron/timezone/window match template. |
| Schedule disabled by default and currently disabled | PASS | Live DISABLED. Deliberate activation still requires approval. |
| REAL Scheduler → SQS → report | NOT VERIFIED | No real scheduled execution evidenced; manual SQS message cannot substitute. |
| Previous completed ISO week from scheduled time | PASS (local) | Strict event parser + tests; actual scheduled execution NOT VERIFIED. |
| Direct-event intermediate demonstration support | PASS (local) | Strict opt-in parser/tests; direct path remains disabled in deployed configuration; live intermediate demonstration NOT VERIFIED if instructor requires it. |
| Standard SQS, encrypted queues, DLQs | PASS | Four queues; work retention 4 days, failures 14 days, managed SSE. |
| Three-failure redrive threshold | PASS (configuration) | maxReceiveCount=3; actual controlled DLQ demonstration NOT VERIFIED. |
| Batch 1; visibility >=6× timeout; conservative concurrency | PASS | Enabled mapping, batch 1, max concurrency 2; 720s visibility/120s builder; no reporting reservations. |
| Builder in existing VPC; mailer outside VPC | PASS | Live VPC/subnets/SG match backend; mailer has no VPC. |
| Immutable arm64 images and handler overrides | PASS | Both use digest ac2d47b04a705075df2e2c09fc0106c771f423fae008d7a7df2d775541935629; correct commands; Active. |
| Existing Aurora, additive migration 0004, preservation | PASS (prior guarded evidence) | Prior successful runner checks and release marker; no new production DB query during audit. |
| Owner-scoped queries, trusted configuration only | PASS | Query filters on owner; strict payload keys prevent owner/recipient/bucket overrides; isolated multi-owner tests. |
| Required meetings statistics | PASS (local) | Count, duration, previous week, absolute/percent changes, zero base handling, stable top five. |
| Kyiv DST/year boundaries, full duration assigned by start | PASS (local) | Parser and query tests; UTC half-open interval and deterministic ordering. |
| Optional task metrics accurately labeled | PASS (local) | Weekly created count; current status snapshot, not historical completions. |
| CSV UTF-8/escaping/formula safety | PASS (local + received evidence) | Renderer tests; user confirms readable W40 attachment. Production values not independently reconciled with DB. |
| AWS-independent reusable report core/local command | PASS | Reports core used by local CLI and builder; local regression tests pass. |
| Aurora read-only snapshot access | PASS | Builder uses REPEATABLE READ and SET TRANSACTION READ ONLY; published manual result proves successful generator execution. |
| Private S3 controls | PASS | All four public blocks, BucketOwnerEnforced, AES256, HTTPS-only deny, 90-day expiration live. |
| S3 CSV existence | PASS | ListObjectsV2 confirms W40, 1061 bytes; publication/mailer logs agree. |
| Direct object HEAD metadata read by operator | FAIL | 403; effective object-read authorization blocked. See diagnosis below. |
| S3 ObjectCreated → mailer → SES → readable attachment | PASS | Correlated manual builder and S3 mailer logs; SES ID; user confirms inbox attachment. |
| Deterministic scoped atomic publication | PASS (local) | IfNoneMatch='*'; duplicates successful; conflicts/errors remain retryable. Production duplicate test NOT VERIFIED. |
| DynamoDB dedup leases, SENT state and recovery | PASS (local + successful-send path) | Conditional writes/lease tests; mailer sent log occurs after finish succeeds. Independent production GetItem/duplicate replay NOT VERIFIED. |
| Mailer retry/failure destination | PASS (configuration/local) | 2 retries, 6h event age, failure queue live. Actual failure/redrive recovery NOT VERIFIED. |
| SES sandbox verified identity and receipt | PASS (existing evidence) | Prior SES verification and user-confirmed delivery; no new email sent during audit. |
| One manual request, correct queue, useful error/message ID | PASS | Accepted W40 message; helper error sanitization tests; no arbitrary owner input. |
| Two distinct scheduled/on-demand S3 CSVs | NOT VERIFIED | Explicit Phase 3 requirement. Listing shows only W40. |
| Least-privilege separate runtime roles | PASS with limitations | Live inline policies reviewed: exact work queue/prefix/table; SES sender/recipient conditions. ENI APIs Resource *; SES identity/* could tighten to exact verified identity. Full deploy-role policy/boundary/SCP audit not readable. |
| S3 gateway endpoint/shared-route safety | PASS | Available gateway; approved main route table; permissive endpoint policy preserves existing IAM/bucket authorization. No NAT/interface endpoint created by stack. |
| No always-on worker/new database | PASS | Template inventory has no NAT, instance, Redis, Celery, or RDS resource. Persistent bucket/table/logs/queues remain. |
| Cost/credits/card safeguards | NOT VERIFIED | Usage and persistent storage can cost money; billing/credits not proven. No new budgets or paid metrics requests made. |
| Reporting changes do not deploy automatically | PASS with push caution | Backend workflow does not deploy reports; main pushes still deliberately deploy backend. Work remains uncommitted/untracked. |
| Documentation/discussion/security/cost outline | PASS with stale content | docs/reporting.md contains required topics and failure procedures, but concurrency descriptions still claim reservations 3+2. Correct before submission. |
| Screenshots and submission commit link | NOT VERIFIED | No complete evidence packet or commit containing this work was supplied; no commit/push authorized. |

## Existing report evidence

Week: 2026-W40, Kyiv September 28 00:00 through October 5 00:00 (exclusive).
SQS message: 6464ad94-b6ac-438a-a61e-cc7e3f905f32.
Correlation: dc0d7f9d-a008-4b55-8e68-84c2a596c18f.
Builder log: trigger=manual, result=published, matching message/correlation.
Object: reports/<private-scope>/2026-W40.csv, 1061 bytes;
last modified 2026-10-11 01:25:31 Europe/Kyiv.
Mailer log: trigger=s3, result=sent, matching correlation and object key.
SES message: 010001a127ebefb8-466901fd-56d8-4c7a-bda2-d0052f913203-000000.
Mailer code logs sent only AFTER a successful S3 read, SES acceptance and successful
DynamoDB SENT update. User confirms a readable CSV attachment arrived. This proves
more than SES acceptance; it does not prove a Scheduler execution or live metric
accuracy against production rows. Raw CSV/report contents were not retrieved.

## HeadObject 403 diagnosis

The CSV exists (listing and successful mailer read). HeadObject requires
s3:GetObject, not just ListBucket or bucket-management permissions. The deployed
bucket policy contains only a non-HTTPS deny; this HTTPS request does not match.
Bucket ownership is enforced; bucket default and builder upload use AES256
(SSE-S3), so KMS grants/customer keys do not explain this standard HEAD denial.
Gateway endpoint policy is full access and the local CLI does not use that VPC
path. Runtime mailer has GetObject and succeeds; operator role lacks effective
object-read access. The original deployment/enqueue policies add no GetObject.
Full operator attachment/version/boundary/SCP enumeration is denied, so the exact
identity-policy omission versus higher-level restriction cannot be conclusively
attributed from the generic 403 alone. No speculative policy change was made.

Minimal administrator review: add/verify s3:GetObject on ONLY the W40 object (or
private scope/*.csv for final two-object evidence) for an authorized evidence
operator. Existing ListBucket and log reads work. No broad S3 grant, KMS grant or
bucket-policy change is needed based on current evidence. Consolidate optional
GetItem on the exact mail-state table and required schedule update authorization
in that same review if final dedup/Scheduler evidence requires them. Do not assume
the deploy role needs wider runtime or database permissions.

AWS references:
https://docs.aws.amazon.com/AmazonS3/latest/API/API_HeadObject.html
https://docs.aws.amazon.com/scheduler/latest/UserGuide/managing-schedule-context-attributes.html

## Tests and diff

179 backend tests PASS against verified local PostgreSQL container loopback:55433,
separate disposable peach_audit_test database (never production).
101 script tests + 55 subtests PASS. 80 frontend tests PASS.
Backend Ruff/configured formatting, CI-selected script Ruff/formatting, frontend
ESLint/TypeScript/Prettier, reports cfn-lint and git diff --check PASS.
An exploratory lint using broader root settings flags 12 unrelated script rules;
repo/CI-configured checks pass. No fixes were made during this audit.
Git diff reviewed includes intended Meetings/reporting/backend safeguards and the
preserved automatic backend workflow. Many implementation files remain untracked;
tracked-only git diff/stat is not the full deliverable. Private parameters/output
are gitignored. Audit adds only this document, not an implementation fix.

## Ordered completion and evidence plan — NOT EXECUTED

1. One administrator evidence-permission review: scope object GetObject, optional
   table GetItem, schedule UpdateSchedule/GetSchedule to exact report resources.
   Preserve existing policies; verify boundaries/default policy versions once.
2. Read W40 object metadata and retain the already received attachment. Capture
   private S3 listing/size/encryption, builder manual log and mailer sent log.
   Compare expected required CSV sections without querying production DB.
3. Correct stale concurrency documentation (no reservations; SQS max 2; shared
   pool throttling possible). If exact scheduled_time/schedule_arn must appear in
   logs for the instructor, current builder logs omit those fields: add sanitized
   scheduled metadata and tests locally, then separately authorize a release.
   Existing logs already record source/week/execution correlation/message ID.
4. Separately authorize REAL weekly schedule activation for one firing. Preserve
   Monday 07:00 Kyiv/SQS target/context/retries; capture enabled configuration and
   target payload. The next Monday after audit date is October 12, 2026, reporting
   W41. Do not enqueue W41 manually first: immutable key would consume evidence.
5. After the actual Scheduler fires, correlate trigger=schedule, W41, Scheduler
   execution-id with configured context/real firing time and SQS message; capture
   builder published result, second CSV and mailer SES/received email. A manually
   crafted source=schedule SQS message is NOT real Scheduler evidence. Scheduling
   a one-off sooner is possible only with separate approval and must derive the
   previous COMPLETED week, yielding W40 during this weekend and thus duplicate.
6. Separately authorize disabling immediately after that firing; confirm DISABLED
   and empty queues. No perpetual schedule needed for lab evidence.
7. If instructor requires controlled three-failure DLQ proof, separately approve
   one invalid week payload failing before DB queries. Observe three receives/DLQ,
   capture screenshots, then authorize exact-message cleanup. Do not weaken queue
   visibility or break production networking/IAM to manufacture failure.
8. Collect requested intermediate direct-trigger demonstration if required by the
   actual university rubric; only local support is currently tested. Separate
   approval for a constrained demonstration is required, then restore SQS path.
9. Assemble screenshots: CFN 20 resources; Monday cron/timezone/target/disabled
   final state; queues/redrive/mapping; Lambda handlers/networking; gateway route;
   two S3 keys/metadata; required CSV sections; correlated logs/SES IDs; email with
   attachment; DLQ demonstration if required. Redact emails/private report titles,
   owner subjects, credentials and unrelated personal information as appropriate.
10. Obtain separate commit/push authorization only when ready. Review all untracked
    files/private exclusions first. A future main push runs backend CI/CD; account
    for that before choosing a submission branch. Provide a real commit URL that
    contains the final implementation. Existing old commit is not proof of this
    uncommitted lab work.

Costs: Lambda/SQS polling, SES sends, S3 and DynamoDB storage/requests, log ingestion
and Aurora resumed ACU activity are usage-dependent. No provisioned concurrency,
NAT or paid interface endpoint added. S3/table retained on deletion; table has no
TTL, so state persists. The existing manual Aurora snapshot may incur storage
cost; do not delete it without separate approval. Credits and bank-card exposure
remain account-specific unknowns; budgets are not automatic billing caps.
