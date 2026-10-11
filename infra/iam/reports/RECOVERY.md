# Reporting CREATE recovery — proposed, NOT executed

Read-only inspection on 2026-10-11 (Europe/Kyiv): peach-reports is
ROLLBACK_FAILED. ScheduleGroup peach-reports exists and is ACTIVE. Queues and
log groups are DELETE_COMPLETE. MailState is DELETE_SKIPPED in CloudFormation,
but DynamoDB DescribeTable returns ResourceNotFoundException: no table currently
exists. S3 endpoint is absent; the shared route table contains only local and
internet-gateway routes. Reporting Lambdas/weekly schedule were never created.
Do not treat DELETE_SKIPPED as proof of a retained physical resource.

The local four deployment policies were reviewed; live role policy enumeration
is denied. Administrator must compare the attached policy versions with local
files before applying this correction. No claim is made that all later provider
permissions were exercised: deployment stopped before Lambda creation.

## One administrator action

Create customer-managed policy PeachReportsDeploymentRecovery from
infra/iam/reports/deployment-recovery.json and attach ONLY to peach-reports-deploy.
Preserve the four original policies, user policies and backend roles. No trust or
permissions-boundary changes. Administrator must check the role boundary/SCPs
also allow these actions; the observed failures were identity-policy denials.

The supplement removes dependence on implicit CloudFormation request tags at
endpoint creation. Only regional S3 endpoint creation is added; existing separate
CreateVpcEndpoint statements still authorize only the approved VPC and route
 table, which are separately evaluated required resources. Endpoint IDs are
unknown before creation, so endpoint ARN needs a wildcard. Tag-on-create uses
only ec2:CreateAction; existing post-create ownership protections are preserved.
Two exact log-group names cover both ARN variants for the TagResource dependent
check during CreateLogGroup. Scheduler DeleteSchedule allows only peach-reports
GROUP children: the observed DeleteScheduleGroup handler checks that wildcard,
even without a created weekly schedule. DeleteStack covers only peach-reports.
No database, IAM mutation, report invocation or email permissions are added.

## Recovery sequence — NOT EXECUTED; separate cleanup approval required

1. After administrator attachment, explicitly approve normal deletion of ONLY
   the failed peach-reports stack and its failed scheduler group.
2. Using peach-reports-deploy in us-east-1, run:

   aws cloudformation delete-stack --stack-name peach-reports
   aws cloudformation wait stack-delete-complete --stack-name peach-reports

   This is a failed CREATE, not UPDATE_ROLLBACK_FAILED. Do not use
   ContinueUpdateRollback, RollbackStack, force deletion or skip resources.
   If normal deletion fails, stop and inspect exact events.
3. Recheck schedule group absence, table absence and endpoint/routes. Do not
   delete a retained table just because its CloudFormation record says retained.
   If a table unexpectedly exists, stop for explicit retention/import/deletion
   choice: a named fresh CREATE cannot adopt it and would conflict. ItemCount is
   approximate and must not be used as proof of emptiness. No table deletion is
   needed or authorized based on current evidence.
4. Prepare unchanged private parameters and lint; create a NEW peach-reports
   CREATE change set. Review all 20 additions again, especially gateway endpoint
   and DISABLED schedule. The old executed change set cannot be reused.
5. Obtain approval for execution of that new exact change set. Keep schedules
   disabled; verify stack/Lambdas afterward. Manual reports require separate
   authorization.

Confirmed denials: endpoint CreateVpcEndpoint, log-group TagResource and schedule
DeleteSchedule during group rollback. Missing DeleteStack is a clearly required
recovery grant in the local deployment-control policy, not a probed live denial.
No guarantee is made against later permission gaps because IAM simulation/live
policy export are unavailable. Do not broaden permissions speculatively.

AWS references:
- https://docs.aws.amazon.com/AWSCloudFormation/latest/APIReference/API_DeleteStack.html
- https://docs.aws.amazon.com/AWSCloudFormation/latest/APIReference/API_ContinueUpdateRollback.html
- https://docs.aws.amazon.com/AWSCloudFormation/latest/APIReference/API_RollbackStack.html
- https://docs.aws.amazon.com/service-authorization/latest/reference/list_ec2.html
