# Reporting IAM review — local proposals, NOT APPLIED

Account **968053399627**, region **us-east-1**, project **peach**. These are proposed
policies, not an export of effective live IAM. Live facts supplied by the owner:
SES sandbox/Healthy, one verified sender=recipient identity with successful delivery,
and GitHub role `peach-github-deploy` with inline policy `deploy-backend`.
The repository's corresponding role template was inspected. No account API,
secret retrieval, deployment, migration, message or email was performed for this audit.

Actual sender/recipient and a fresh UUIDv4 scope are in ignored mode-0600
`reports-local/iam/configuration.json`. Filled-in JSON is in mode-0600
`reports-local/iam/rendered/`; the directory is mode 0700. Public files deliberately
use `__SENDER_EMAIL__`, `__RECIPIENT_EMAIL__`, `__REPORT_SCOPE_ID__`.
Do not paste unresolved templates into IAM. Re-render locally, without AWS calls:

```bash
python3 scripts/prepare-reports-iam.py --config reports-local/iam/configuration.json
```

Use the same private scope for `ReportScopeId` in the separate reporting parameter
file. This does not choose a Cognito owner or configure/deploy the application.
Review the owner-to-inbox mapping privately. Regeneration never replaces an existing
scope automatically. Review templates contain no email addresses, owner subjects,
database URLs or credentials. Account/region/network IDs are infrastructure metadata.

## Permission placement matrix

| Principal | JSON files | Purpose / current status |
|---|---|---|
| Existing GitHub `peach-github-deploy` | **None** | Preserve automatic backend CI/CD and original permissions. Reporting is not invoked by that workflow. |
| Temporary human reporting deployment role | `deployment-control`, `deployment-data`, `deployment-compute`, `deployment-network` | First reviewed CREATE and later controlled UPDATE/rollback. No SES send, SQL, migrations or backend updates. |
| CloudFormation, default execution | Same deployment operator session | Current example has no service role; CloudFormation derives temporary credentials from the caller. |
| Optional dedicated CloudFormation execution role | `deployment-data`, `deployment-compute`, `deployment-network`; `optional-trust-cloudformation` | Alternative only. Caller retains `deployment-control` and gets `optional-pass-cloudformation-role`. Not recommended for this first lab release. |
| Scheduler role `peach-report-scheduler` | `runtime-scheduler`, `trust-scheduler` | Send only to work queue and Scheduler delivery DLQ. Template already creates this role. |
| Builder role `peach-report-builder` | `runtime-builder`, `trust-lambda` | Queue polling, scoped CSV publication, logs and ENIs. Network hardening proposal differs from current template. |
| Mailer role `peach-report-mailer` | `runtime-mailer`, `trust-lambda` | Scoped CSV reads, conditional DDB claims, exact verified sender/inbox, async failure queue and logs. SES hardening proposal differs from template. |
| Evidence operator | `operator-readiness` | Metadata, scoped report download, known-key claim reads and logs. Config APIs can expose Lambda environments; handle privately. |
| Test-request operator | `operator-enqueue` | `report-now` stack lookup and SendMessage to work queue; explicitly mutating. |
| Activation operator | `operator-activation` | Get/Update the one schedule and PassRole only to Scheduler; explicitly mutating. |
| Recovery operator | `operator-recovery`, plus core deployment policies for stack recovery | DLQ handling, mailer requestPayload replay, mapping pause and reviewed stack rollback/deletion; explicitly mutating. |
| Console convenience | `optional-console-discovery` | Regional list APIs and account bucket-name listing. Add only if needed; not stack provisioning. |
| Image publisher | `optional-image-publish` | Only if a separate reviewed image push is authorized; otherwise reuse the reviewed backend release digest. |
| ECR bootstrap operator | `optional-ecr-retrieval-bootstrap` | Only if the existing Lambda retrieval repository policy is insufficient; can alter that policy, not granted by default. |

`resource-s3-bucket`, `resource-s3-endpoint`, `resource-mailer-invocation` are
**resource policies**, not identity policies to attach to people. The template
already supplies their equivalents. Trust documents are role trust policies.
`action-reference` and `provider-read-reference` are public validation evidence,
not policies. Do not attach every file to one role. The four core deployment
files each fit the 6,144-character managed-policy limit; use separate policies.

## Existing versus missing permissions

The supplied GitHub policy and `infra/github-oidc.yaml` already cover Peach stack
change sets, existing ECR operations, the three named IAM roles/PassRole, reporting
function APIs and most log management. They do **not** cover queue management,
Scheduler, report-bucket configuration, delivery-state table management or gateway
endpoint creation/modification/deletion. Additional gaps include event-source
mapping APIs: function-scoped `lambda:*` does not cover mapping resources.
New mappings need `CreateEventSourceMapping` on `*` with exact FunctionArn;
existing mapping read/update/delete can use the regional mapping ARN pattern
plus that condition. Mapping tagging needs its own resource/ownership conditions.
Provider reads such as `logs:GetDataProtectionPolicy`, `DescribeIndexPolicies`,
`DescribeResourcePolicies`, log untag/delete-retention and ECR lifecycle reads
are not all present in the original policy. These belong to the controlled
operator bundle; **no GitHub policy update is necessary for this strategy**.

Original broad grants (`cloudformation:*`, function `lambda:*`, selected `rds:*`,
role management, Secrets Manager writes and global log/EC2 describes) are retained
but deserve a separate review. Adding a narrow Allow does not cancel a broader
Allow already attached to a principal. Use a dedicated narrow human role when
possible, rather than treating an existing administrator as least privilege.
IAM PutRolePolicy on three roles can still assign arbitrary policy contents:
ARN restrictions are not a permissions boundary. Review the exact template and
runtime policies; protecting against malicious templates would require a separate
boundary/design review, not an AdministratorAccess grant.

## Focused CloudFormation control-policy review

The public AWS service-reference metadata was rechecked on 2026-10-10.
`CreateChangeSet` supports `cloudformation:ChangeSetName`; the required
`peach-reports-*` name pattern is valid. Create/Describe/Execute/DeleteChangeSet
all authorize the **stack** resource, not a change-set ARN. Consequently
`arn:aws:cloudformation:us-east-1:968053399627:stack/peach-reports/*` is the
appropriate restriction; adding `changeSet/...` ARNs is unnecessary.
The trailing wildcard covers the future generated stack ID for a first CREATE.
The stack need not exist: specify StackName `peach-reports` and ChangeSetType
`CREATE`; CloudFormation creates a REVIEW_IN_PROGRESS placeholder without
provisioning template resources until ExecuteChangeSet is called.

The control policy is unchanged after this review. It permits execution as a
separate API action; it is **not** an IAM-enforced review-only role. Human approval
is a procedural gate. The documented reporting create-change-set command does
not execute, and no automatic reporting deployment workflow exists. Do not reuse
the automatic backend deployment script for reporting. A later CLI `deploy`
command would execute by default unless explicitly given `--no-execute-changeset`.
Console template uploads can require additional artifact-bucket permissions;
use the documented direct template-body command instead of expanding this policy.
See [CreateChangeSet API behavior](https://docs.aws.amazon.com/AWSCloudFormation/latest/APIReference/API_CreateChangeSet.html)
and [public authorization metadata](https://servicereference.us-east-1.amazonaws.com/v1/cloudformation/cloudformation.json).
Offline tests verify the policy against recorded action metadata; they do not
simulate live IAM boundaries, SCPs or Console navigation permissions.

## Action inventory and least-privilege boundaries

The JSON files are the exact action lists; these mappings explain their necessity.

- **SQS:** create/delete/get URL/get and set attributes, tag/untag/list tags on
  exactly `peach-report-work`, `peach-report-builder-dlq`,
  `peach-report-scheduler-dlq`, `peach-report-mailer-failures`. Deployment has no
  message reads or sends. Recovery is separate; ReceiveMessage changes visibility
  and receive count and is not a harmless metadata read. SSE-SQS uses managed
  SQS encryption, not a customer KMS key; no queue KMS grants are needed.
- **Scheduler:** the group is `peach-reports`, schedule is `peach-weekly-report`
  inside it. Create/get/update/delete only that schedule; group management/tags
  only that group. No `events:*` is needed: EventBridge Scheduler uses `scheduler:`.
  IAM cannot constrain UpdateSchedule to only the State field; review the complete
  request so cron, timezone, role, payload, DLQ and retries remain unchanged.
- **S3:** configuration on the one regional-account-named bucket, no operator
  deployment object writes/deletes or bucket-public ACL permissions. CloudFormation
  read handlers inspect unset settings (including replication, metadata and ABAC),
  so scoped read actions cover them; they do not grant the corresponding writes.
  S3 SSE is AES256, no customer KMS key, no presigned URL or ACL permissions.
  DeleteBucket is included for lifecycle/failure cleanup; retained/nonempty objects
  cannot be purged through this bundle because DeleteObject is absent.
- **DynamoDB:** create/update/delete, describe configuration, tag/untag only
  `peach-report-mail-state`; no deployment Scan/Query/item mutation. The mailer
  alone gets GetItem/UpdateItem. The template's `SSEEnabled: true` selects the AWS
  managed DynamoDB KMS key, not the default AWS-owned key. Its AWS-managed key
  policy authorizes service-mediated grants; no blanket KMS grant or new key is
  proposed. AWS-managed-key KMS requests can cost money. No replicas, DAX,
  provisioned autoscaling, TTL, imports, backup exports or service-linked role
  creation are configured. Broad provider permission lists include those optional
  features; they are deliberately not copied wholesale.
- **Lambda:** only builder/mailer function CRUD, concurrency, tags and provider
  reads. Async configuration is mailer/$LATEST only. AddPermission is restricted
  to principal `s3.amazonaws.com` on the mailer; SourceAccount/SourceArn are verified
  in the template/resource policy (IAM lacks a request-field restriction for them).
  No function URL, publish-version/alias, backend mutation or builder direct-invoke
  permission is added. Template VPC verification requires EC2 describes by the
  deployer; runtime ENI writes belong to the builder role, not the deployer.
- **IAM:** only three exact runtime role ARNs, inline policy/trust/tag lifecycle,
  role inspection and PassRole split by `iam:PassedToService`. No managed-policy
  attach, user management, OIDC provider, service-linked role or policy version
  management is necessary. An IAM administrator bootstraps the temporary human
  role separately; the role cannot grant itself permissions.
- **ECR:** existing `peach-backend` image/repository-policy reads. Lambda pulls the
  image through the ECR service retrieval policy, not new broad runtime ECR grants.
  The previous audit's all-account-function retrieval policy would cover both
  functions; recheck it manually before release. Do not select a newest/cleanup
  image, and do not grant SetRepositoryPolicy unless bootstrap is truly required.
- **Networking:** CreateVpcEndpoint authorizes only the approved existing VPC and
  route table, plus an unknown new endpoint ID restricted to the S3 service and
  CloudFormation system stack tag. Modify/Delete/Tag scopes use the reporting
  stack's system name/id tags; the pinned provider schema supports system tags
  on creation. Only that approved route table may be associated. No CreateRoute,
  SG ingress/egress changes, NAT, VPC/subnet/route-table deletion, interface endpoint
  subnet/SG creation authority or PrivateLink service-network features are added.
  Template type remains Gateway; IAM is not a substitute for checking the type.
- **Logs:** only two seven-day log groups, separate ARN forms for tag APIs (without
  `:*`) and normal log-group APIs (with it). Runtime writes target log streams.
  DescribeLogGroups/DescribeResourcePolicies/DescribeIndexPolicies require regional
  wildcard scope for provider reads. No log delivery, Firehose, custom metrics,
  subscription filters or cross-account resource-policy writes.
- **Alarms:** **none exist in the template**; therefore no PutMetricAlarm,
  DeleteAlarms, alarm-action, SNS or alarm service-linked-role grant is proposed.
  Alarm permissions must accompany a future reviewed alarm resource change.
- **Database/authentication:** no RDS, `rds-db:connect`, Secrets Manager retrieval,
  Cognito/JWT changes, migrations or cleanup are required for report provisioning.
  Aurora is reached with the existing password URL over SQL. IAM does not enforce
  SQL row ownership; owner-filtered queries and the read-only transaction do.

## Focused compute authorization review

Rechecked public Lambda, Logs and IAM authorization metadata on 2026-10-10;
recorded selected evidence in `provider-read-reference.json`. No compute policy
Allow was broadened or removed by this review.

- Mapping creation supports `lambda:FunctionArn` but no resource-level ARN;
  Get/Update/Delete support eventSourceMapping ARNs and that same condition.
  Lambda supplies the function context even though Get/Delete requests use UUIDs.
  Keep the exact builder function condition and regional/account mapping pattern.
- TagResource supports request tags; the mapping resource type supports
  `aws:ResourceTag/${TagKey}` for Tag/Untag/ListTags. FunctionArn is not a
  supported condition on those tagging APIs and must not be added there.
- The bundled us-east-1 mapping provider declares `cloudFormationSystemTags: true`
  and `tagOnCreate: true`. That supports the creation stack-name request-tag gate
  and existing stack-name/stack-id resource-tag gates. Function tags are not
  inherited by mappings. These gates depend on CloudFormation creating the mapping;
  an untagged manually created mapping is intentionally not entitled to tag access.
  Schema declarations do not constitute a live request trace or prove regional
  propagation timing. If authorized deployment shows a missing system-tag context,
  inspect the failing event before changing permissions; do not preemptively grant
  TagResource on all mappings. No `IfExists` ownership bypass is introduced.
- Logs create/delete, retention and GetDataProtectionPolicy use the two exact
  log-group ARNs ending `:*`. TagResource/UntagResource/ListTagsForResource use
  the same group ARNs without `:*`, as required by the Logs LogGroup API docs.
- Role paths/names in the template match the three exact IAM role ARNs. Inline
  policy lifecycle and service-constrained PassRole are covered. No managed
  policy attachments, role boundary management or deployment-role management is
  allowed. Current roles set no custom Description/MaxSessionDuration/boundary;
  updates adding those properties need a separate permission review.

For current-template creation, ordinary updates and automatic rollback, the
compute permissions cover the configured operations, together with the other
three deployment policies. Optional provider handler grants for customer KMS,
managed-role-policy attachments and log delivery/index/resource policies are
not needed by this template. Whole-stack deletion/ContinueUpdateRollback remain
separate operator-recovery permissions. ECR retrieval policy compatibility,
account boundaries/SCPs and live provider behavior still require account-side
review; offline metadata validation is not an effective-access guarantee.

## Focused network authorization review

Current public EC2 action/resource metadata was rechecked on 2026-10-10.
`deployment-network.json` remains unchanged: no unsupported conditions were found.
Selected per-resource condition evidence is in `provider-read-reference.json`.

- CreateVpcEndpoint supports the exact VPC and route-table ARNs plus the unknown
  regional/account endpoint ARN. Service-name and request-tag conditions apply to
  the **endpoint** resource check; they must not be moved to the VPC/route statement.
  Gateway creation needs no subnet/security-group grants. The template specifies
  Gateway, the regional S3 service and supplied route tables.
- ModifyVpcEndpoint supports route-table and endpoint resources. The exact shared
  route-table grant is additional authorization for endpoint associations, not
  CreateRoute/DeleteRoute authority and not a standalone endpoint-management grant.
  DeleteVpcEndpoints authorizes endpoint resources, not route-table resources.
  Endpoint modify/delete/tag operations support the ownership resource-tag conditions.
- CreateTags supports ec2:CreateAction and endpoint request tags for tag-on-create.
  Later tagging uses the existing endpoint's stack-name and stack-id conditions;
  it does not require ec2:CreateAction. DeleteTags uses those same existing tags.
  The bundled endpoint provider declares system tags and tagOnCreate. Thus expected
  CREATE requests carry the system stack-name tag and the resulting endpoint has
  stack-name/id ownership tags. This is schema evidence, not a live trace proving
  regional tag propagation timing. Untagged or differently owned endpoints remain
  outside this role's update/deletion entitlement; never strip ownership tags.
- Initial creation, policy/tag/approved-route updates and ordinary automatic
  rollback are covered for this template. Replacement changing VPC, service or
  route tables is intentionally outside these restrictions and needs fresh review.
  IAM ownership tags are a boundary against unrelated resources, not proof that
  a template is safe: this role can create reporting-tagged endpoints and change
  its endpoint policy, affecting all clients on the authorized shared route table.

The full-access gateway policy preserves existing S3 IAM/bucket authorization;
no production backend resources, SGs, subnets or Aurora are edited. Nevertheless,
adding/removing its route changes shared S3 networking. A restrictive future policy
could disrupt backend/other clients, source-IP conditions may behave differently,
and open connections may need retries. Keep the non-restricting endpoint policy,
review change sets for networking impact, and use a quiet deployment window.
Offline metadata checks do not guarantee effective access under SCPs/boundaries or
successful cleanup if creation leaves an endpoint without its ownership tags.

## Why wildcard resources remain

| Statement/action | Reason and constraint |
|---|---|
| CreateEventSourceMapping | No resource ARN exists/support is absent for creation; exact `lambda:FunctionArn` binds it to the builder. Other mapping CRUD uses mapping ARNs. |
| EC2 Describe*, account concurrency, mapping list, SES GetAccount, global provider log descriptions | Those specific APIs lack resource-level authorization; region is restricted to us-east-1. No write wildcard added. |
| ValidateTemplate/GetTemplateSummary | Validating a supplied template body has no existing stack resource to authorize; regional only. |
| Optional console lists | Service list APIs cannot be resource-filtered; optional and regional. S3 ListAllMyBuckets is account-wide and not a report-object permission. |
| Optional ECR GetAuthorizationToken | Token retrieval has no repository ARN scope; regional. Actual push actions remain on the one repository. |
| Runtime explicit ENI Deny | `*` deliberately denies function-code network management through `lambda:SourceFunctionArn`; it is not an Allow. |
| Shared S3 endpoint Allow | `s3:*` / `Resource: *` preserve existing authorization through the shared route; identity and bucket policies still control access. This is not an identity-policy grant. |
| Bucket TLS Deny | `s3:*` deliberately denies insecure transport on the one bucket; it grants nothing. |

Unknown endpoint/ENI/mapping UUIDs use wildcard **IDs inside region/account ARNs**,
not unrestricted `Resource: *` writes. Existing ENI management is restricted by
Vpc and Subnet; creation also checks the exact approved subnet/SG resource ARNs.
The Lambda source-function Deny leaves Lambda's service ENI management usable.

## Template compatibility and runtime proposals

The actual template has the expected names, no RDS resources, one VPC builder,
one non-VPC mailer, four queues, retained bucket/table, correctly ordered S3
notification permission, and a disabled Monday 07:00 Europe/Kyiv schedule.
Creation dependencies are acyclic, including policy/notification ordering.
The core IAM bundle covers creation, update and automatic resource rollback for
those properties; recovery DeleteStack is a separate operator permission.
Retain does not authorize destructive manual cleanup. The original GitHub
CloudFormation scopes are sufficient for reporting change-set APIs, but its
resource permissions are insufficient for executing this stack.

**Runtime JSON files are review proposals, not automatically used by the template.**
The current builder grants the six standard EC2 ENI actions on `*`; the proposal
narrows writes to the selected network and denies ENI actions to function code.
The current mailer SES identity wildcard is already bounded by exact From/To
conditions; the proposal also pins the verified email identity and requires a
nonempty recipient condition. These are scoped hardening recommendations, not
claims that current delivery is broken. Adopting them requires a separately
reviewed edit to the CloudFormation-managed inline policies. Do not attach them
as extra Allow policies and assume the existing broader grants disappear.
The template, backend workflow, authentication and original IAM template remain
unchanged by this audit.

Historical network metadata from the prior read-only audit: VPC
`vpc-0def9c995c9c73f75`, main route table `rtb-0fb1d48c2f3f092c2`, builder SG
`sg-0545f0ff2d3d0ad76`, and five subnet ARNs in the runtime proposal. These are
not fresh account reads. They must match reviewed deployment parameters and
be reverified manually; regenerate the proposal if different subnets are selected.

**Shared-route policy resolved locally:** the owner confirmed in the Console that
all six subnets implicitly use main route table `rtb-0fb1d48c2f3f092c2` (zero
explicit associations) in `vpc-0def9c995c9c73f75`, with no VPC endpoints.
The template and `resource-s3-endpoint` now use the standard full-access endpoint
policy: Principal `*`, Action `s3:*`, Resource `*`. This is intentionally a
non-restricting network authorization layer for every existing S3 client; it does
not grant S3 permissions to a Lambda role or make any bucket public. Limiting this
shared endpoint to one role, account, bucket or prefix could block unrelated or
AWS-managed/cross-account buckets. IAM and bucket policies still authorize requests.

Builder IAM still allows only PutObject to the configured scope's CSV keys;
mailer IAM permits only GetObject there. The reporting bucket remains private,
public-access-blocked, owner-enforced, encrypted and TLS-only. It has no public
Allow and no endpoint-only condition (the mailer operates outside the VPC).
No deployment identity or runtime S3 permission has been broadened.

Repository inspection finds S3 calls only in the reporting builder/mailer, not the
existing API/migration handlers. The frontend's CloudFront-to-S3 origin access is
outside this VPC route. Unknown other VPC clients retain their IAM/bucket limits.
Before execution, still review source-IP-based bucket/IAM conditions: gateway
routing changes the source context and may disconnect existing S3 TCP connections.
Use a quiet window and clients with reconnect/retry support. Recheck endpoint
absence and SG/NACL HTTPS access; no existing routes, SGs or Aurora are replaced.

## First deployment strategy and AWS Console guide — NOT EXECUTED

Prefer a temporary dedicated **human** role `peach-reports-deploy` with the four
core policies and short-lived sessions, without a CloudFormation service role.
If an already suitably scoped operator role exists, temporary attachments there
avoid another role. IAM roles themselves add no hourly infrastructure cost.
Do not attach anything to `peach-github-deploy`, replace `deploy-backend`, or edit
GitHub settings. This role/template work does not deploy reporting on main pushes.

A dedicated CFN execution role is optional, not needed for this small lab. Once
attached, it persists on the stack and users with stack-operation permissions can
reuse it even without PassRole. Existing GitHub `cloudformation:*` on Peach stacks
makes that a particularly important privilege-reuse risk. Do not choose this
alternative without reviewing who can execute reporting change sets. If chosen,
its name is `peach-reports-cfn-exec`; use the optional trust/pass files and put the
three resource bundles on it, not on GitHub. Never use the backend deployment
role as a reporting execution role.

1. **Review locally first.** Inspect the four core public JSON files and private
   rendered variants. Verify region/account, network IDs, runtime names, ownership
   tags and chosen principal. Confirm `git check-ignore` covers private outputs.
2. **Later, after authorization, an IAM administrator** opens IAM → Policies →
   Create policy → JSON. Paste each *rendered* core document into a separate
   customer-managed policy named `PeachReportsDeploymentControl`,
   `PeachReportsDeploymentData`, `PeachReportsDeploymentCompute`,
   `PeachReportsDeploymentNetwork`. Review the Console policy validation findings.
   These actions are not performed or authorized by this local audit.
3. IAM → Roles → create/select the dedicated human role. Its trust must name the
   exact approved human/SSO operator principal, not GitHub, a wildcard principal
   or an unconditioned whole-account trust. Have the administrator verify its
   source principal's AssumeRole entitlement. Attach only the four core policies;
   add `operator-readiness`/optional discovery only if needed. Do not grant the
   role permissions to bootstrap itself or edit other roles/policies.
4. Switch into that role using an approved short-lived session. Check the Console
   account and **N. Virginia/us-east-1**. Preserve permissions until the stack is
   stable and rollback is complete. Runtime roles will be created by CFN; do not
   manually create or attach policies to them.
5. Confirm the existing image digest/provenance, ECR retrieval/retention, available
   shared unreserved Lambda capacity (SQS maximum concurrency 2), actual migration `0004` evidence, scoped
   owner/inbox configuration, SES sending enabled and verified identity. No new
   sender verification, production SES access or DNS/domain changes are needed
   for the already verified same-address sandbox test.
6. Inspect VPC → Subnets/Route tables/VPC endpoints, including inherited main
   routes and every affected S3 client. Check existing SG permits SQL from builder
   SG, egress/NACL permit SQL and S3 HTTPS, and endpoint does not conflict. Stop on
   source-context and reconnect considerations above. Do not change the SG or Aurora.
7. Prepare reporting parameters privately with the generated scope. CFN Console
   → Create stack → **Create change set for a new stack**, upload
   `infra/reports.yaml`, name the stack **peach-reports**. Use change-set name
   **peach-reports-first-reviewed** (the control policy requires `peach-reports-*`).
   Select **current permissions**, not an execution/service role; acknowledge
   named IAM resources (`CAPABILITY_NAMED_IAM`). Keep AllowDirectEvents false.
   Keep Monday schedule disabled. Use private NoEcho parameters; do not screenshot
   or expose password/owner/inbox configuration. No template upload bucket is needed
   for the current small template; if the Console offers an S3 upload workflow,
   use a direct template-body/local-file change-set path instead of adding unrelated
   artifact bucket permissions. Do not use Quick create/Submit to deploy immediately.
8. Inspect the complete CREATE change set. Exactly the reporting resource set is
   expected; no backend/auth/RDS/SG replacements, no NAT/interfaces, no surprise
   resource policy or route changes. **Stop for explicit execution approval.**
   Existing account SCPs, session policies/boundaries and bucket/ECR policies can
   still deny requests; offline validation does not prove effective AWS access.
9. Only after approval execute that reviewed change set. Verify CREATE_COMPLETE,
   system ownership tags, handlers/digests, notification permissions, lease table,
   queues/DLQ/batch settings, route and seven-day logs. Keep schedule disabled.
   Failures require event review, not blanket permission grants or manual execution
   of unreviewed change sets.
10. Separately authorize tests and attach `operator-enqueue` to the test operator
    temporarily. A request can wake Aurora and send mail. Evidence reads use
    `operator-readiness`; runtime SES send permission belongs only to the mailer.
    After valid/duplicate/DLQ evidence, separately authorize `operator-activation`.
    Update only State while preserving all schedule fields and record deliberate
    drift from disabled-by-default template. Remove temporary deployment/test grants
    when complete; retain needed recovery access with an explicit owner.

The current Console UI may require additional discovery reads for navigation;
those are separated in `optional-console-discovery`, not hidden service-wide grants.
If the chosen Console path insists on extra artifact upload permissions, stop and
use the documented direct template-body change-set path. Do not grant S3 writes
outside the report bucket to make a convenience upload work.

## Predeployment checklist and rollback

- [ ] Approve the exact local IAM documents and any runtime hardening template edits.
- [ ] Independently confirm deployed role policy/boundary/SCP constraints; this audit
      used repository policy and user-supplied facts, not a new effective-permissions read.
- [ ] Confirm account/region, network IDs and CloudFormation system-tag compatibility.
- [ ] Review shared-route source-IP conditions, reconnect behavior and endpoint conflicts.
- [ ] Review immutable Phase 3 image and retain live/rollback digests; never cleanup image.
- [ ] Confirm existing revision `0004` proof; reporting does not perform migrations.
- [ ] Match private scope/owner/inbox and verified sender to actual parameters.
- [ ] Confirm SES sending enabled/limits, Lambda headroom and disabled schedule.
- [ ] Review CREATE change set; get separate execution and mail-test authorization.

Automatic creation rollback needs resource delete permissions in the core bundles;
keep the temporary deployment grants until rollback stabilizes. Retained S3/DDB
may remain after failure/deletion: inspect before retrying, do not purge SENT data
or CSVs. Named retained resources may require a reviewed import/recovery strategy;
blindly creating another same-name stack can fail. Deployment grants intentionally
lack object purge/table-item deletion.

For delivery failures, disable schedule with activation permission, pause builder
mapping with recovery permission, let in-flight work finish, preserve queued work
and async envelopes, and replay **requestPayload** only after resolving the cause
and checking leases/SENT state. SQS redrive is builder-DLQ → work only; Scheduler
DLQ/manual correction and mailer failure envelopes are different recovery paths.
Exactly-once SES delivery is not guaranteed across send/state-write failure.

For reporting stack deletion, use a reviewed recovery action and inspect the shared
endpoint dependency before removing its route. It must not remove Aurora, existing
SGs, subnets or the main route table. Ordinary API rollback keeps additive Meetings
schema and user data. Do not downgrade `0004`, run legacy cleanup, or create a
snapshot/migration as a reporting-permission workaround.

## Static validation and authoritative references

Run `pytest scripts/tests/test_reports_iam.py scripts/tests/test_reports_infra.py`.
Tests validate JSON/action names, supported wildcard/resource handling, scope,
PassRole destinations, resource ownership conditions, provider reads, role names,
no RDS/alarm/SES deploy grants, runtime APIs, privacy/renderer refusal boundaries,
managed-policy size, disabled schedule and CI preservation. They do not call AWS
or a database. Metadata snapshots are public AWS IAM service reference data and
bundled regional CFN schemas, pinned for repeatable offline checks. They are not
an IAM simulator or evidence that an SCP/key/resource policy permits execution.

- [AWS service authorization metadata](https://servicereference.us-east-1.amazonaws.com/v1/)
- [Lambda mapping IAM permissions](https://docs.aws.amazon.com/lambda/latest/dg/permissions-user-function.html)
- [VPC endpoint resource/condition examples](https://docs.aws.amazon.com/vpc/latest/privatelink/security_iam_id-based-policy-examples.html)
- [Lambda VPC permissions](https://docs.aws.amazon.com/lambda/latest/dg/configuration-vpc.html)
- [Source-function ARN network hardening](https://docs.aws.amazon.com/lambda/latest/dg/permissions-source-function-arn.html)
- [CloudFormation service-role persistence](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-iam-servicerole.html)
- [DynamoDB managed-key grants](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/encryption.usagenotes.html)
- [SQS redrive permissions](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-configure-dead-letter-queue-redrive.html)

## Prepared local image and deferred secret transfer

The local `peach-reports:phase3-local` image is linux/arm64. Both reporting
handlers and backend/migration handlers import with Docker networking disabled;
its migration 0004 file is present. This does not prove production migration
success or complete database integration. No image was pushed. ImageUri remains
unset until a separately authorized publish provides a verified ECR digest.

`scripts/prepare-report-database-url.py` defaults to no retrieval. Only after
separate authorization, run with `--retrieve-authorized-secret` using a Python
environment with boto3. It uses profile default, validates the account and exact
previously verified secret ARN, refuses to overwrite DatabaseUrl, and atomically
writes a mode-0600 private parameter file. Secret response/errors never go to
stdout/stderr; the value is not a shell argument and no database is contacted.
Do not enable SDK debug logging, shell tracing or interactive debugger inspection.
The helper grants no permissions and must not run until retrieval is authorized.

Read-only attempts to discover the intended inbox's Cognito user and migration
stack/log evidence were denied: cognito-idp:ListUsers, cloudformation:DescribeStacks
on peach-migrations, and logs:FilterLogEvents on its log group. Do not broaden the
reporting deployment role. An already authorized operator may supply the selected
production owner's sub and existing successful migration evidence privately.

## Temporary evidence-read addition — NOT APPLIED

Both default (sofiia) and peach-reports-deploy profiles were denied the exact
owner, migration-stack and migration-log lookups. The matching frontend/backend
issuer configuration identifies pool us-east-1_bs7cWxhJp. Deployment code names
stack peach-migrations and log group /aws/lambda/peach-migrations; access denial
means their live existence cannot yet be established. An absent stack/group
would mean there is no evidence at that location, not that 0004 succeeded.

Proposed `operator-evidence-bootstrap.json` contains only ListUsers on that pool,
DescribeStacks on that migration stack, and FilterLogEvents on that log group,
all restricted to us-east-1. IAM cannot restrict ListUsers to an email filter or
FilterLogEvents to a particular search string: these permit reads across that
one pool/group. CloudFormation metadata/logs may contain historical sensitive
material; inspect responses privately and emit only evidence conclusions.

Recommended administrator action after approval: IAM > Users > sofiia >
Permissions > Add permissions > Create inline policy > JSON; use this document,
name it PeachReportsEvidenceRead. This is a separate temporary addition, not a
replacement for PeachBootstrapPolicy. Keep peach-github-deploy and the four
PeachReportsDeployment policies unchanged. Alternatively attach this same policy
to an approved evidence operator role. Existing boundaries/SCPs must allow the
reads; do not remove them. Remove temporary grants after the evidence is captured.
No secret retrieval, user mutation, Lambda invocation or database access is granted.
After attachment, Codex can perform all three reads and save the selected sub
privately, without asking the user to run diagnostic commands. Log evidence must
show a successful 0004 migration with preservation checks; merely mentioning
0004 or a CREATE_COMPLETE stack is insufficient. Seven-day retention may mean
older success evidence has expired.
