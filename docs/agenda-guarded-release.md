> **Current budget:** the manually created peach-monthly-cost-alert is verified.
> Do not create a duplicate budget stack or repeat the completed ECR change. The
> release verifier accepts both legacy CostTypes and equivalent Console
> FilterExpression/Metrics, including default percentage alerts, without relaxing
> cost/email checks. Use the updated private pinned runbook after this fix's commit.

> **First protected release commands (October 19):** [exact ordered procedure](agenda-first-release.md).
> Includes private email parameters, pinned source, preservation, encrypted snapshot,
> guarded revision/migration, disabled parser and no-inference checks. Not executed.

# Peach Lab 6 — simple safe demo release

Current plan: Amazon Nova Lite amazon.nova-lite-v1:0 / non-streaming Converse,
us-east-1, **no reserved concurrency and no quota increase**. Shared account quota
10 is adequate for the expected serial demonstration. Several concurrent parses
can still consume the shared pool and throttle API/reporting; run one at a time,
honor Retry-After and disable parsing outside the approved window. The warm-instance
rate limit and $5 alert are not global spending caps. No extra limiter service is added.

No deployment, snapshot, migration, paid inference, commit or push is authorized
by this document. Previously completed local checks need not be repeated merely
because time elapsed. `local-verify` is optional comprehensive revalidation and
runs disposable local migrations, so do not use it under a no-migrations restriction.
The normal backend release still verifies its exact published ARM64 image.

## Essential preparation

1. Apply the single untagged-only 30-day ECR policy after approval, before any image
   push. Preserve all tagged API/runner/report/rollback digests. Keep existing tag
   mutability. Detailed Console/CLI steps: [infrastructure actions](agenda-infrastructure-actions.md).
2. Create the reviewed $5 account-wide pre-credit monthly email budget through
   infra/budget.yml, stack peach-budget. Supply email privately. No actions/Reports.
3. Review and commit the local changes on feat/paste-agenda after commit approval.
   This pins exactly what is deployed; no push/main merge is needed to release.
4. Freeze other releases during this short deployment window. Preserve old API,
   runner/report digests and frontend objects with metadata. Verify live ECR retention
   again immediately before publication. No report deployment is part of this lab.

## One ordered procedure after release approval

Use the existing release wrapper's phases as one sequence; approval strings are
operator interlocks, not separate permission conversations for each command.

```sh
C=$(git rev-parse HEAD) # reviewed, approved, clean feature commit
D="$PWD/reports-local/agenda/release-$C"
R=(backend/.venv/bin/python scripts/agenda-release.py)
"${R[@]}" plan --commit "$C" --directory "$D"
"${R[@]}" preserve --commit "$C" --directory "$D" \
  --reports-profile peach-reports-deploy
```

Once the ECR/budget and local review checks pass, create the approved fresh manual
Aurora cluster snapshot using [the prepared steps](agenda-infrastructure-actions.md#4-aurora-backup-and-guarded-revision).
Require exact peach-db, manual/available/encrypted, <24 hours. The existing automated
snapshot is useful backup metadata but does not replace this pre-change checkpoint.
No private SQL route or additional networking is required.

Set PEACH_RELEASE_SNAPSHOT_ID to the actually verified identifier. Review the output
of `backend/.venv/bin/python scripts/schema-release.py`, then explicitly set
PEACH_APPROVED_MIGRATION_SHA256 to its approved fingerprint; never auto-approve it.

```sh
"${R[@]}" backend --commit "$C" --directory "$D" \
  --approve "968053399627:$C:backend"
```

This publishes and verifies the new immutable image, checks the RDS-safe change set,
updates the existing private runner, reads the actual revision with inspect_revision,
compares it again under a lock before DDL, applies additive 0005, then updates API.
Unexpected revision or any failure stops the release. Do not retry automatically.
Reporting functions/schedule, Cognito and existing meeting/task data are preserved.

Prepare the AI parameter JSON described in [agenda-ai.md](agenda-ai.md): exact new
backend digest, existing Cognito public configuration, frontend origin, exact Nova
ARN, rates 0.06/0.24, ParserEnabled=false. No concurrency parameter is needed.

```sh
"${R[@]}" parser-disabled --commit "$C" --directory "$D" \
  --ai-parameters /private/tmp/ai-parameters.json \
  --approve "968053399627:$C:parser-disabled"
# Review returned exact change set: only parser role/log/function/URL/permissions.
"${R[@]}" execute-disabled --commit "$C" --directory "$D" \
  --change-set-id REVIEWED_EXACT_CHANGE_SET_ARN \
  --approve "968053399627:$C:execute-disabled"
"${R[@]}" smoke-disabled --commit "$C" --directory "$D" \
  --token-file /private/tmp/peach-access-token
```

Token file must contain a short-lived app access token and be mode 0600; never
paste it in chat/history/evidence. Disabled checks require no-JWT 401, oversize 413,
and valid-JWT 503. No valid parse is billed while disabled.

## Activation and submission (separate paid approval)

Use the activation UPDATE change-set commands in agenda-ai.md; preserve every
parameter except ParserEnabled=true. Do not reattach laptop inference permission.

```sh
"${R[@]}" paid-smoke --commit "$C" --directory "$D" \
  --token-file /private/tmp/peach-access-token \
  --approve "968053399627:$C:paid-smoke"
"${R[@]}" frontend --commit "$C" --directory "$D" \
  --approve "968053399627:$C:frontend"
```

One HTTP smoke can invoke Nova at most twice (repair). Frontend requires an actual
successful receipt for the same commit/image/Lambda configuration/URL and enabled
parser. No arbitrary receipt age forces another paid call. Re-test if configuration
changes, an error occurs or the endpoint fails. The frontend phase rebuilds with
real verified URLs; never upload earlier synthetic-URL build artifacts.

Five required inputs and null-result capture template:
[agenda-submission-template.json](agenda-submission-template.json).
Instructions and answer drafts: [agenda-evaluation.md](agenda-evaluation.md).
Run each through the deployed UI once, serially, spacing starts >=21 seconds apart
or honoring Retry-After. Capture actual JSON/usage/cost/latency without a JWT/HAR.
Record the Ukrainian case: paste → Parse → edit one field → Save, <=45 seconds.
Use it for both table and demo. Read one real parser CloudWatch line using
scripts/agenda-evidence.py in a bounded run window; finish four answers and authorize
feature-branch push for the commit link. These are five submission categories,
not five extra independently repeated workflows. No mock result is model evidence.

The original assignment requires Claude Opus 5.5/AnthropicBedrockMantle. Account
unavailability/zero Mantle quotas led to Nova. This remains a transparent deviation,
**not instructor-approved**. The prior basic OK smoke did not prove agenda quality.

## Practical rollback and approval scope

On failure stop. After approved rollback disable parsing with a reviewed parameter
update, restore retained compatible API image and exact frontend contents/metadata,
and keep additive 0005 and the successful schema marker. Do not drop agendas,
blindly delete S3 objects, touch report resources or restore a stale snapshot over
newer data. Keep the safe retention policy and budget. No destructive cleanup.

Two scoped approvals can cover the work without per-command approval prompts:
1. Reviewed local commit plus ECR/budget, preservation, fresh backup, guarded
   migration/API and disabled-parser release. Snapshot and migration are explicitly
   included only when that exact release plan/fingerprint has been approved.
2. Activation plus bounded paid functional/UI tests, frontend, evidence collection
   and explicitly authorized feature-branch push. No implicit main merge/push,
   unrelated IAM change, extra inference, or snapshot restore.

At present neither approval has been exercised; this pass only edits/tests local
files and reads AWS metadata. Essential safeguards remain; quota bureaucracy,
arbitrary smoke expiration, and obligatory repeated full audits are removed.


## This local simplification was verified

229 offline backend/parser/script tests and 63 subtests passed; 13 frontend agenda
tests passed. Release-configured Ruff lint/format, AI/budget cfn-lint and whitespace
checks passed. Read-only AWS confirmed shared capacity 10, unchanged protected
API/runner/report digests and existing tags, unsafe old lifecycle policy still live,
and zero budgets. No resource, quota, IAM, database or inference change was made.
Live parser deployment/tool-use quality and actual production revision remain
unverified; those checks happen only in the approved sequence above.
