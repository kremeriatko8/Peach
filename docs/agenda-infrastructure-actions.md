# Lab 6 infrastructure unblock plan — October 18, 2026

**Prepared locally only. Do not execute mutations without the approval checkpoints below.**
AWS reads used IAM user arn:aws:iam::968053399627:user/sofiia, account 968053399627,
us-east-1. The configured reporting role was used only for reporting reads. No Root,
inference, quota request, lifecycle update, budget, snapshot, SQL or deployment was used.
This record supersedes older infrastructure observations in agenda-release-audit.md.

## 1. Exact ECR exposure and smallest safe correction

One shared release repository: `peach-backend`,
`arn:aws:ecr:us-east-1:968053399627:repository/peach-backend`.
URI: `968053399627.dkr.ecr.us-east-1.amazonaws.com/peach-backend`.
Repository AES256 encrypted, tag mutability MUTABLE, no exclusion filters.
No other repository is needed or proposed; this is not an account-wide inventory.
The repository is intentionally outside infra/backend.yaml; deploy-backend.sh only
checks it exists and publishes images. Neither resets its lifecycle policy during
normal release, so this correction is not overwritten by the backend template.

Live policy:
```json
{"rules":[{"rulePriority":1,"description":"keep the last 3 images","selection":{"tagStatus":"any","countType":"imageCountMoreThan","countNumber":3},"action":{"type":"expire"}}]}
```

Every protected function currently references the repository by digest:

| Function/reference | Full protected digest | Existing tags |
|---|---|---|
| peach-report-builder and peach-report-mailer; oldest | sha256:ac2d47b04a705075df2e2c09fc0106c771f423fae008d7a7df2d775541935629 | 077c4625ebe3-dirty-20261010203754; 077c4625ebe3-dirty-20261010210015; reports-phase3-4801d967bcb449309eda495502c750c2; 077c4625ebe3-dirty-20261010205004 |
| peach-migrations; next oldest | sha256:aa7c0324b1e7653782cec5c4a3bd41123ae6dfed081fd715dd25b98fdca898dc | 077c4625ebe3-dirty-20261010211649 |
| peach-backend; newest | sha256:763c0b78eaf43c322f4692842bc70a308a4358b001c88a0b0dfc8916d1c32df6 | fb23fecdd165911fe8373fe3fc452c0ccb255030-38135501545-1 |

Exactly three image digests currently exist and all are tagged. A fourth unique
image makes the reporting digest eligible under the count rule; further pushes
could expose the runner and API rollback digest. Deletion is asynchronous, not
necessarily immediate. Multiple tags on the report image do not defeat an `any`
rule. Digest pinning and immutable tags do not provide deletion protection.
An already cached Lambda image is not reliable proof that future cold/reactivation,
updates or rollback will work after its ECR image is deleted.

Proposed file: `infra/ecr/peach-backend-lifecycle.json`: expire only UNTAGGED images
older than 30 days, retain every tagged image. This is one PutLifecyclePolicy on
one repository. No new tags, repo, immutability setting, image push or cleanup is
needed. With the current inventory it expires none of the three protected images.
Age is since IMAGE PUSH, not time since losing its last tag: never untag protected
images. Older tagged rollback images accumulate until separately reviewed cleanup.

Leave MUTABLE unchanged for this unblock: release scripts use unique tags and pin
verified digests. Enabling immutability is separate hardening that can break retry
or retag workflows; it is not required to solve lifecycle deletion.

### Console (after checkpoint 1 approval)

1. Select account 968053399627 and Northern Virginia/us-east-1 using the authorized
   IAM administrator/operator; no Root credentials are needed.
2. Amazon ECR → Private registry → Repositories → peach-backend → Lifecycle policy.
3. Save the existing JSON privately. Review current image list and exact digests.
4. Edit/replace the lifecycle policy with the saved local proposed JSON; ensure
   there is NO remaining tagged/any expiration rule, then Save.
5. If using the Console test/preview, expect zero current protected expirations.
   StartLifecyclePolicyPreview changes preview metadata and is NOT part of today's
   read-only checks; use only inside the separately authorized admin session.
6. Re-read the actual policy and verify all protected digests still exist and have
   tags. Keep all deployers idle during the change and following verification.

### CLI equivalent (NOT executed; checkpoint 1)

Run from repo root, with identity confirmed immediately before mutation:
```sh
aws --profile default --region us-east-1 sts get-caller-identity
# STOP unless Arn is arn:aws:iam::968053399627:user/sofiia (or separately approved admin identity).
mkdir -p reports-local/agenda/infrastructure
aws --profile default --region us-east-1 ecr get-lifecycle-policy \
  --repository-name peach-backend --query lifecyclePolicyText --output text \
  > reports-local/agenda/infrastructure/ecr-policy-before.json
aws --profile default --region us-east-1 ecr describe-images \
  --repository-name peach-backend --output json \
  > reports-local/agenda/infrastructure/ecr-images-before.json
# MUTATION: requires explicit checkpoint 1 approval; no dry-run option.
aws --profile default --region us-east-1 ecr put-lifecycle-policy \
  --repository-name peach-backend \
  --lifecycle-policy-text file://infra/ecr/peach-backend-lifecycle.json
# Read-only verification:
aws --profile default --region us-east-1 ecr get-lifecycle-policy \
  --repository-name peach-backend --query lifecyclePolicyText --output text
aws --profile default --region us-east-1 ecr describe-images \
  --repository-name peach-backend --output json
```
Verify semantic equality to the local proposal and all three full digests/tags;
stop on any discrepancy before publishing. The wrapper now rechecks retention
both while preserving rollback state AND just before the backend publication.
Live-policy or tag changes can still race reads: serialize other local/CI releases.

Rollback of policy: safest is retain the new conservative policy and stop releases.
Do not automatically restore `any newest 3` after any push: it can expire live or
rollback images. Only restore archived JSON after an explicit rollback decision
and a fresh inventory proves no protected digest would expire. A lifecycle policy
rollback cannot recover deleted images. No destructive cleanup is proposed.

Cost: existing compressed image sizes sum to ~0.774 GB before layer sharing.
At published private ECR storage $0.10/GB-month, a full extra ~0.258 GB image is
about $0.026/month before sharing/free credits. Actual billing is layer-aware;
retaining tagged images adds storage over time, not an always-on service fee.
Source: https://aws.amazon.com/ecr/pricing/

## 2. Shared Lambda concurrency — no quota request

The university demo now omits ReservedConcurrentExecutions. Verified shared total
and unreserved concurrency are both 10, sufficient for one-at-a-time lab requests
alongside normal low traffic. No quota increase, reservation, provisioned concurrency,
account/region change, or reporting configuration change is needed.

Requests share the pool: several simultaneous authenticated parses can temporarily
throttle the API/reporting functions. Per-subject throttling is per warm instance,
not a global limiter or spending cap. Run one Parse at a time; wait for completion
and honor Retry-After. Keep parsing disabled outside the approved demo window.
JWT checks, 10K input, bounded output, one repair/no SDK retries, usage/cost logs,
manual fallback and the $5 alert remain. This is an explicit low-traffic tradeoff,
not a guarantee of workload isolation. For this lab no additional service is warranted.

Read-only capacity verification:
```sh
aws --profile default --region us-east-1 lambda get-account-settings
```
The release requires positive unreserved capacity; parser configuration checks
require no reservation. Disregard earlier quota-increase recommendations.

## 3. Exact $5 budget

Verified DescribeBudgets returned no budgets; peach-budget stack was absent in
prior current audit. Use existing reviewed `infra/budget.yml` via peach-budget:
- Name peach-monthly-cost-alert; COST, monthly, USD 5, account-wide (no filters).
- Unblended, not amortized; IncludeCredit=false, IncludeRefund=false.
- One ACTUAL notification, GREATER_THAN, ABSOLUTE_VALUE threshold 5 USD.
- EMAIL subscriber: the user's privately supplied address (still required).
- No budget actions, SNS, paid endpoint, auto-shutdown, model invocation or NAT.

This monitors unblended charges BEFORE credit/refund offsets, rather than the net
amount payable after credits. It does not neutralize free pricing, independently
verify invoice totals, limit spend to $5, stop Lambda/Bedrock/Aurora, or notify in
real time. Existing application charges count; alerts can arrive after overspend.
Monitoring/email budgets are free; no budget actions are configured. Do not enable
Budgets Reports (a separate billed emailed-report feature) for this lab.
https://docs.aws.amazon.com/aws-cost-management/latest/APIReference/API_budgets_CostTypes.html
https://aws.amazon.com/aws-cost-management/aws-budgets/pricing/

Preferred Console path (checkpoint 1): CloudFormation → Stacks → Create stack →
With new resources → Upload template infra/budget.yml → stack name peach-budget →
NotificationEmail actual private email → default locked budget name → retain normal
caller credentials/no unreviewed service role → review → Submit. This creates ONLY
the budget and notification and avoids later duplicate/manual-resource ownership.
Do not create a second manual Budget and then deploy a stack with the same name.
For inspection: Billing and Cost Management → Budgets → peach-monthly-cost-alert.

CLI equivalent with separate change-set review, NOT executed:
```sh
# Set private value interactively, never paste it into evidence:
read -r PEACH_BUDGET_EMAIL
aws --profile default --region us-east-1 cloudformation create-change-set \
  --stack-name peach-budget --change-set-name agenda-five-dollar-budget \
  --change-set-type CREATE --template-body file://infra/budget.yml \
  --parameters "ParameterKey=NotificationEmail,ParameterValue=$PEACH_BUDGET_EMAIL"
# Record returned exact change-set ARN, wait/review describe-change-set.
# Execute only after approval of that exact change set:
aws --profile default --region us-east-1 cloudformation execute-change-set \
  --stack-name peach-budget --change-set-name REVIEWED_EXACT_CHANGE_SET_ARN
aws --profile default --region us-east-1 cloudformation wait stack-create-complete \
  --stack-name peach-budget
```
CloudFormation uses the caller's scoped `budgets:ModifyBudget` plus tagging/read
permissions here; no persisted service role is proposed. Do not assume stack ARN
scope alone limits underlying permissions. Prior live IAM bundle matched local;
no new operator inference grant is needed. If any permission is denied, stop.

Read-only verification:
```sh
aws --profile default --region us-east-1 budgets describe-budget \
  --account-id 968053399627 --budget-name peach-monthly-cost-alert
aws --profile default --region us-east-1 budgets describe-notifications-for-budget \
  --account-id 968053399627 --budget-name peach-monthly-cost-alert
aws --profile default --region us-east-1 budgets describe-subscribers-for-notification \
  --account-id 968053399627 --budget-name peach-monthly-cost-alert \
  --notification NotificationType=ACTUAL,ComparisonOperator=GREATER_THAN,Threshold=5,ThresholdType=ABSOLUTE_VALUE
```
Confirm exact address privately, no actions, no filters, credits/refunds excluded.
Retain the alert if a deployment is rolled back; deleting it is not necessary or
an automatic cleanup step. Check the configured mailbox and delivery/spam settings.

## 4. Aurora backup and guarded revision

Exact source: arn:aws:rds:us-east-1:968053399627:cluster:peach-db.
Available/encrypted Aurora PostgreSQL 17.4; retention one day; deletion protection
false; backup window 03:44–04:14 UTC; 0–1 ACU, auto-pause 300 seconds.

Verified snapshots:
- Manual peach-pre-ownership-20261010-203025-2742, available, encrypted,
  October 10 20:35:35 UTC: too old for release.
- Automated rds:peach-db-2026-10-18-03-49, available, encrypted,
  October 18 03:50:08 UTC: current recovery artifact, but NOT the required fresh
  manual pre-migration snapshot. Do not rename/replace/reclassify it.
- Earliest and latest PITR timestamps both returned October 12 21:17:43 UTC.
  Fresh automated snapshot and stale PITR metadata are distinct facts, not proof
  of loss or a verified continuous restore range. Investigate in RDS Console before
  relying on PITR; do not wake/query/restore the production DB during this review.

Create manual snapshot only AFTER quota/retention/budget/local gates are resolved,
immediately before the approved release, so its <24h gate will not expire waiting
for a quota request. Console: RDS → Databases → peach-db cluster → Actions → Take
snapshot → DB cluster snapshot, name peach-pre-ownership-YYYYMMDD-HHMMSS-SUFFIX.
Verify account, region, source cluster, encrypted, manual, available, created <24h
and not future-dated. No instance snapshot, replacement DB or restore is requested.

CLI alternative after checkpoint 2 snapshot approval, NOT executed:
```sh
aws --profile default --region us-east-1 sts get-caller-identity
# Choose/review one unique name with the required IAM-scoped prefix:
SNAPSHOT_ID=peach-pre-ownership-YYYYMMDD-HHMMSS-SUFFIX
aws --profile default --region us-east-1 rds create-db-cluster-snapshot \
  --db-cluster-identifier peach-db --db-cluster-snapshot-identifier "$SNAPSHOT_ID"
aws --profile default --region us-east-1 rds wait db-cluster-snapshot-available \
  --db-cluster-snapshot-identifier "$SNAPSHOT_ID"
aws --profile default --region us-east-1 rds describe-db-cluster-snapshots \
  --db-cluster-snapshot-identifier "$SNAPSHOT_ID"
# After reviewing returned criteria, set PEACH_RELEASE_SNAPSHOT_ID to that exact ID.
```
Manual backups can accrue storage beyond the included backup allowance and persist
until separately approved removal. Exact incremental bytes/cost are unknown; do
not promise credits/free backup. Snapshot restore creates a recovery workflow,
not an application rollback, and cannot safely overwrite newer meetings/report data.

Actual production revision remains UNKNOWN. No runner/SQL call occurred. Existing
local runner's inspect_revision explicitly starts a READ ONLY transaction, checks
one known revision and verifies transaction_read_only=on. After the separately
approved runner image update, the release checks this returned proof before DDL.
The guarded migrate path then locks alembic_version and compares expected_from in
the same transaction before upgrading. Default expected 0004; 0005 retry requires
explicit review. Source HEAD 0005 is never evidence of actual production revision.

No migration/runner commands are authorized by checkpoint 1. During checkpoint 2,
use the existing exact-commit agenda-release.py backend procedure, fresh snapshot,
reviewed fingerprint and current image archives. If inspection/revision differs,
stop before migration/API changes. On failure retain additive 0005 if applied,
restore compatible prior API/frontend after approval, and leave report images,
roles/schedule/data untouched. Do not downgrade, delete snapshots or restore stale
backups automatically.

## 5. Local safeguard changes and validation

- infra/ecr/peach-backend-lifecycle.json: proposed untagged-only 30-day policy.
- scripts/agenda-release.py: use positive shared capacity without a quota request;
  validate exact named account-wide pre-credit budget and upward ACTUAL threshold;
  recheck all protected digests/tags/lifecycle at preservation AND pre-publication.
- scripts/tests/test_agenda_release.py: regressions for initial/already-reserved
  capacity, denied reads, filtered/net budgets, wrong notification direction,
  protected tags and untagged protected digests.
- infra/budget.yml: explicitly UseAmortized=false and lock budget name to the
  intended scoped name; no new resource or pricing behavior.
- scripts/tests/test_ai_infra.py: exact budget configuration assertions.
- docs/agenda-infrastructure-actions.md: this action plan.
- docs/agenda-release-audit.md and docs/agenda-guarded-release.md: current-plan links.

No public API, DB schema, parser/provider/model behavior, reporting code, or IAM
policy changed. Final local validation: all scripts/tests passed (161 tests,
63 subtests), including the 40-case focused release/AI/IAM subset before the final
budget assertions. Release-configured Ruff lint/format, AI/budget cfn-lint, ECR
proposal JSON assertions and git diff --check passed. Changed/untracked secret-pattern
scan found no AWS keys/private keys/GitHub tokens; this is not a full secret-scanner
attestation. No backend/frontend runtime source changed, so those previously passed
suites were not repeated unnecessarily.
Existing dirty implementation files are preserved, not committed. No migration,
paid model test, deployment or destructive cleanup was run.

## 6. Simple execution order and approvals

Use [the current short release procedure](agenda-guarded-release.md). No quota
request is needed. After approval, apply ECR retention and budget, review/commit,
preserve rollback assets, create fresh manual snapshot, perform guarded migration/API
release, deploy parser disabled and test auth/size/disabled mode. Separately approve
activation, one functional parse, frontend publication, five actual UI cases and
feature-branch push. There is no per-command permission conversation; the operator
interlocks still stop on failed proofs. Snapshot restore, deletion, extra inference
and IAM changes are not included. No operation above was executed in this preparation.
