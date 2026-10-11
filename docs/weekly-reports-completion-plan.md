# Final completion plan — prepared only, 2026-10-11 Europe/Kyiv

Status update (2026-10-11): scoped S3 HEAD and DynamoDB SENT evidence checks
now pass. The existing schedule is ENABLED for October 12 at 07:00 Kyiv; W41
is still pending. The dated audit/preparation details below record the earlier
snapshot and must not be interpreted as the current schedule state.

No AWS mutations have been performed by this preparation.

## One administrator review

Attach PeachReportsFinalEvidenceRead to peach-reports-deploy using the filled
ignored file reports-local/deployment/operator-final-evidence.json. Reviewable
source: infra/iam/reports/operator-final-evidence.json; its scope placeholder must
NOT be attached literally. It adds only:

- s3:GetObject on this reporting bucket's configured scope/*.csv. HeadObject uses
  this action; there is no s3:HeadObject IAM action. It also permits downloading
  those reports, so treat the role and CSVs as private. No KMS permission needed
  for existing AES256 reports.
- dynamodb:GetItem on peach-report-mail-state, for consistent reads of known
  SHA256(bucket/key) report_id entries; no scan/write grants.

Existing deployment/enqueue/log policies already provide the rest of this plan:

| Operation | Existing permission and restriction |
|---|---|
| Read schedule/configuration, enable AND disable | scheduler:GetSchedule/UpdateSchedule on schedule/peach-reports/peach-weekly-report |
| Resubmit unchanged target during UpdateSchedule | iam:PassRole on peach-report-scheduler, PassedToService=scheduler.amazonaws.com |
| Stack/resources, mapping UUID | cloudformation:DescribeStacks/ListStackResources on stack/peach-reports/* |
| Function metadata and mapping | lambda:GetFunction/GetFunctionConfiguration/GetFunctionConcurrency on two report functions; GetEventSourceMapping on the mapping resource |
| Queue status/settings | sqs:GetQueueAttributes on four reporting queues |
| Logs/result correlation | logs:FilterLogEvents on two reporting log groups (already exercised successfully) |
| Object listing | s3:ListBucket on reporting bucket (already exercised); keep existing scope restriction where applicable |
| Bucket controls/notification | existing reporting-bucket read grants, already exercised |
| Delivery state and CSV HEAD | the two supplemental actions above |

Do NOT add SendMessage, Lambda InvokeFunction, SES send, new IAM mutation,
CloudTrail, global metrics/discovery or database permissions for this verification.
The previous successful configuration reads establish existing access; complete
policy/boundary enumeration is not permitted. Administrator should verify attached
DEFAULT policy versions and boundaries/SCPs once before the authorized session.
A restrictive higher-level deny cannot be fixed by adding an Allow blindly.

## Verified date, target and week

Live schedule: DISABLED; cron(0 7 ? * MON *); Europe/Kyiv; flexible window OFF.
Existing start/end constraints do not exclude October 12.
Monday October 12, 2026 at 07:00 Kyiv is 04:00 UTC. Previous completed ISO week is
2026-W41: October 5 00:00 Kyiv through October 12 00:00 Kyiv (exclusive).
Target remains SQS peach-report-work, with the same execution role, scheduler DLQ
and retry policy. Scheduler substitutes scheduled-time, execution-id, schedule-arn
and attempt-number into the configured payload. Week selection uses scheduled
time, not processing time. Manual W40 remains the other distinct report.

## Activation — requires separate explicit approval, NOT EXECUTED

1. After administrator review, refresh peach-reports-deploy credentials. Before
   activation, verify W40 HEAD, delivery state and continued DISABLED state. Ensure
   W41 does not already exist; do not manually enqueue W41. Confirm approvals
   include Aurora resumption, CSV creation and SES sending from the real firing.
2. Immediately before any update, read the live schedule again. Compare its target,
   role, input, cron, timezone, retry, DLQ and time limits with the prepared JSON.
   Regenerate payloads if ANY setting changed: UpdateSchedule replaces settings
   and omitted optional fields can reset to defaults.
3. Only after approval and BEFORE October 12 07:00 Kyiv, execute:

   AWS_PROFILE=peach-reports-deploy AWS_REGION=us-east-1 aws scheduler update-schedule --cli-input-json file://reports-local/deployment/schedule-activate.json

   The prepared payload preserves all current updateable schedule fields and only
   changes State to ENABLED. Verify GetSchedule shows ENABLED and unchanged target.
   Do not create a substitute manual source=schedule message or invoke a Lambda.
4. Observe the real firing at 07:00 (Scheduler precision is within the minute,
   not guaranteed exact second). Read logs after ingestion delay. Builder must
   show trigger=schedule, week=W41, published result, execution correlation and SQS
   message ID. Capture enabled configuration/context input plus actual firing
   evidence. Current builder logs omit raw scheduled_time/schedule_arn; correlate
   scheduled execution-id, trigger and actual time with Scheduler configuration.
   If the instructor requires those exact fields logged, that is a separate local
   logging change/release; do not substitute a forged payload as proof.
5. Verify W41 listing and HEAD size/type/AES256; mailer trigger=s3 and sent SES ID;
   consistently read its DynamoDB SENT state/SES ID using known report_id hash.
   Check inbox/Spam and attached CSV. Capture both W40/W41 keys and metadata. No
   report content, credentials or raw Cognito subject in shared screenshots.
6. Explicitly include post-firing disable in the activation authorization. After
   the one firing, run:

   AWS_PROFILE=peach-reports-deploy AWS_REGION=us-east-1 aws scheduler update-schedule --cli-input-json file://reports-local/deployment/schedule-disable.json

   Recheck latest configuration before using this payload; it changes only State
   to DISABLED. Disable even if the report fails; inspect failures read-only, do
   not repeatedly enqueue. Disabling prevents future schedule executions; it does
   not cancel messages already sent or Lambda/SQS retries already underway.
7. Verify DISABLED, inspect work/DLQ/failure counts and logs, record final state.
   If successful, compile scheduled/manual CSV evidence, emails and log IDs.
   Controlled DLQ demonstration and Git commit/push remain separately authorized.

If permission/configuration checks fail, stop BEFORE activation. If scheduled
processing fails, do not manufacture a second execution: capture its exact result
and obtain authorization for any repair. No perpetual recurring workload is needed.

Prepared files under ignored reports-local/deployment are mode 0600 and contain
private scope or target details. They are NOT executed by make reports-prepare.

AWS references:
https://docs.aws.amazon.com/AmazonS3/latest/API/API_HeadObject.html
https://docs.aws.amazon.com/scheduler/latest/APIReference/API_UpdateSchedule.html
https://docs.aws.amazon.com/scheduler/latest/UserGuide/managing-schedule-context-attributes.html
