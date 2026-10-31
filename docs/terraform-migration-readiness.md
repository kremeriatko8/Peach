> Current blocker (2026-10-29): third preview has 41 imports and four proven
> sensitivity-only metadata updates, with equal values and no AWS change actions.
> The assignment expects initial zero changes and a post-import No changes plan;
> no metadata exception is documented. Strict gates remain unchanged. Instructor
> clarification and user approval are required before any adoption exception or
> live handover. See [consolidated assessment](terraform-sensitivity-metadata-review.md).

# Lab 7 read-only migration readiness assessment

Assessment date: 2026-10-27, Europe/Kyiv. Observation started at
2026-10-27T06:57:58Z. **Not ready for ownership transfer or import apply.**

Only read-only AWS metadata operations and an unauthenticated HCP GET were used.
The existing reporting profile authenticated through its already-configured role;
no credentials, policies, resources or HCP settings were created or changed.
No Terraform init/plan/import/state/apply/destroy operation was run in this phase.
No commit, push, merge or deployment occurred. Application/Terraform code was not
changed in this assessment; local inventory and documentation were updated.

## Local reconciliation completed after discovery

The user approved local reconciliation after the read-only assessment. Updated
`infra/auth.tf` to preserve all observed Google details and username mapping,
`infra/reports.tf` to preserve 1,048,576-byte limits on all four queues, and
`infra/terraform.tfvars` with all 31 recorded public inputs. The schedule/parser
remain enabled in desired configuration; the adoption gate remains false. No
secret input, active import block, AWS/HCP setting, CloudFormation file or
retention policy was changed during this reconciliation phase. No live reads
were repeated; refresh the observation before actual migration.

See [HCP setup instructions](terraform-hcp-setup.md) and the
[two-action additional-read policy request](terraform-additional-read-permissions.json).
No organization/workspace name, role ARN or secret was guessed. The local
configuration fixes below are complete; HCP access/bootstrap, denied reads,
retention deployment, import-plan verification and state handover remain blocked
pending separate authorization/configuration.

Validation: isolated Terraform validation and 6 mocked plan tests passed (5
configuration scenarios plus the actual public-input file/gate test). The latter
checks all 31 inputs against the recorded worksheet with synthetic values for the
7 omitted inputs. All 26 Python migration tests, script lint/formatting, shell
syntax and diff checks passed. These are local checks, not a live no-change plan.

## Local PR candidate prepared (2026-10-28)

All 41 recorded import blocks are now in local `infra/imports.tf`, with an offline
cross-check against both resource declarations and the filtered AWS observations.
The plan guard also rejects a proposed imported ID different from this candidate.
The default/public-file adoption gate remains false. Root cloud selection is
explicitly bound to user-confirmed ooad-kremeriatko8 / peach-dev; no HCP setting
was changed. All resource settings and original CFN templates are unchanged in
this preparation. The isolated runner validates real import syntax before
excluding imports only from its temporary mock-test copy; it removes ambient AWS
credential sources and never runs a real import/plan/apply.

The user reports the HCP workspace, AWS OIDC provider/role/read policy, seven
Terraform inputs and two dynamic-credential variables are configured, with the
DB URL from deployed report-builder. This supersedes the earlier missing-setup
observation but is not independent verification: targeted reads of the new role
were denied to the existing discovery identity, and no HCP plan has run. Do not
request broader account listing just for that verification; inspect the supplied
trust/policy or review the eventual specific provider error.

Local checks now pass: 254 script tests/63 subtests, 38 migration tests, full
Terraform validation and 6 mocked plan tests; the isolated main-based preview
also passes 38 migration tests and 6 mocked plan tests. The publication-scope blocker is resolved locally: the isolated patch is now on
`feat/terraform-migration-preview`, based on fetched main `0dad65c`; all 45
changed/new files are migration-only. Original dirty work is preserved.
See [the candidate review](terraform-pr-review.md).

Publication remains blocked by approval, not by missing local import
blocks. Automatic HCP speculative PR plans and remote trigger settings must be
confirmed manually. A temporary workspace-only gate override requires explicit
preview approval; do not change the versioned gate. Keep the PR unmerged because
main pushes trigger application deployment. Follow
[the exact preview procedure](terraform-first-preview.md).

Expected preview: 41 imports and no managed mutations. Recorded IDs/settings
may have aged; the first real plan is still needed to identify current drift,
provider normalization and any missing read permission. The later retention-only
deployment, detachment and import/state apply remain unauthorized. Earlier
read-only discovery findings below are historical, not a current bootstrap audit.

## Verified environment and resources

AWS account **968053399627**, region **us-east-1**. The default profile resolves to
IAM user `sofiia`. The existing `peach-reports-deploy` profile assumes the existing
role of that name in the same account. Both identities were used for reads only.

| Stack | Live status | CFN declarations found | Both Retain policies deployed |
| --- | --- | ---: | ---: |
| peach-auth | UPDATE_COMPLETE | 5 | 0 |
| peach-reports | CREATE_COMPLETE | 20 | 2 |
| peach-ai | UPDATE_COMPLETE | 6 | 0 |
| Total | Stable stack statuses | 31 | 2 |

The live templates match the local CloudFormation files after removing retention
metadata. This is a template comparison, not a claim of zero live drift. All 31
CFN resources have observed IDs. Direct resource reads support the 41 proposed
Terraform object mappings, including existing embedded IAM/S3/queue configuration.
Google federation exists, so the expected count is **41**, not 40. No resource
recreation is planned. The actual HCP import plan remains unverified.

Files:

- [Consolidated, filtered live findings](terraform-live-assessment.json).
- [Observed import ID mapping](terraform-live-import-inventory.json), including
  the correct provider-specific composite IDs. This is documentation, not state
  and matches the now-active local imports.tf. Neither is approval to apply imports.
- [Public input worksheet](terraform-live-input-worksheet.json), deliberately not
  an auto-loaded tfvars file. The adoption gate remains false.

The original null-ID preparation inventory remains unchanged to preserve the
local test contract and distinguish planned scope from observed resources.

## Configuration and preservation findings

- Cognito pool `us-east-1_bs7cWxhJp`, public client
  `4vscaj9gks4n63ds52gbhi5ggn`, Essentials tier, email sign-in, existing domain,
  Managed Login v2 and branding all exist. Estimated pool user count: **4**;
  users and their personal data were not listed. Email string constraints are
  min 0/max 2048. The client has no generated secret, refresh validity 30 days,
  auth session validity 3 minutes, and the expected deployed/localhost callbacks.
- Google federation is present. Local client ID and secret were compared with
  live configuration **in memory** and match; their values were not persisted.
  Live mappings/details include additional service-populated entries described
  below. The branding import ID is pool ID plus branding UUID separated by comma;
  the CFN physical ID uses a different separator and must not be copied verbatim.
- Parser is enabled, arm64, 512 MB, timeout 30 seconds, no VPC or DB access,
  shared concurrency, POST-only URL/CORS, existing permissions boundary and two
  expected URL policy statements. Its immutable digest is
  `sha256:8bac6eded73b84a482bf307b4694ab7151ecc5ec3533701739872cbff8036da6`.
  Pricing strings are `0.06`/`0.24`; model remains Nova Lite. Auth/JWKS snapshots
  match the existing backend. No inference or Lambda invocation was performed.
- Builder and mailer use the same reporting digest:
  `sha256:ac2d47b04a705075df2e2c09fc0106c771f423fae008d7a7df2d775541935629`.
  This differs from the parser digest; the draft already supports that separation.
  Memory, timeout, architecture, handlers, logging and environment-key sets match
  the intended definitions. No reserved concurrency was found.
- Builder/backend database URL and VPC/subnet/SG sets compare equal; no DB
  connection or query was made. All five selected subnets resolve to existing
  route table `rtb-0fb1d48c2f3f092c2`, served by retained candidate S3 endpoint
  `vpce-0e24aa58428a2f072`. Their ownership remains outside this migration except
  for the existing reporting S3 endpoint. No new networking is needed.
- Direct GetEventSourceMapping confirms UUID
  `3910d1ed-06a8-4867-a77e-9192b19d8c6d`: enabled, batch 1, batching window 0,
  maximum concurrency 2. The reporting role cannot list mappings, but this exact
  read succeeded; an empty result from the initial denied list is not absence.
- Reporting roles, inline policies, scheduler trust and parser boundary are
  present. No attached managed policies were found on the four runtime roles.
  SES addresses in persisted policy findings are redacted. Private report settings
  were not copied into documentation. Builder/mailer scope values compare equal.
- Report bucket is private, BucketOwnerEnforced, AES256, 90-day reports-prefix
  expiry, unversioned, one existing Lambda notification, and the expected HTTPS
  policy. Its generated notification ID and mailer permission Sid are captured.
  Four report objects totaling 4,339 bytes were counted without retaining their
  names or reading their bodies. All queues reported approximately zero visible,
  delayed and in-flight messages at inspection. DynamoDB metadata reports 4 items;
  this is an approximate metadata count, not a scanned backup. Refresh these
  baselines before migration because the application/scheduler remain active.

## Observed differences and completed local reconciliation

The local differences below have been reconciled under the subsequent local-only
approval. No infrastructure change or import plan has occurred. The risks column
describes the original draft; live parity still requires a reviewed HCP plan.

| Observed finding | Risk in the original draft | Current local preparation |
| --- | --- | --- |
| All four SQS queues have MaximumMessageSize 1,048,576; original HCL omitted max_message_size and pinned provider defaults to 262,144 | Four unintended in-place configuration reductions | Completed: explicit max_message_size = 1048576 on all four queues; mock coverage added |
| Google live attribute_mapping includes username = sub; original HCL omitted it | Non-import identity-provider update | Completed: full live attribute mapping preserved and tested |
| Google live provider_details has six public metadata entries beyond the three configured inputs | Provider reads the complete required map into state; the smaller HCL map can propose removals/updates | Completed: all observed public details preserved/tested; existing ID/secret remain required protected inputs. Actual plan still pending |
| Weekly schedule is ENABLED although deployed CFN resource property says DISABLED | Using the CFN value would stop weekly reports | Completed: report_schedule_state = ENABLED in public tfvars. This is confirmed live drift from the CFN resource property |
| ParserEnabled is true although the template parameter default is false | Using defaults could disable the parser | Completed: parser_enabled = true in public tfvars; this is a parameter override, not proven CFN drift |
| 29 of 31 declarations lack deployed retention protection | Deleting the stacks now would delete users and other resources | Separately approve retention-only updates and verify the resulting deployed templates before any detachment |

Provider-specific review also confirmed:

- The bucket currently blocks SSE-C and has BucketKeyEnabled=false. In the pinned
  provider these fields are Optional+Computed, so omission alone is **not** a
  confirmed configuration change. Preserve/inspect them in the import plan.
- S3 lifecycle transition default is all_storage_classes_128K, matching the pinned
  provider default. Do not invent a lifecycle update.
- Cognito's standard schema defaults, computed client defaults and reserved
  aws:cloudformation tags require plan review; do not copy reserved tags into
  Terraform or mask unrelated changes with broad ignore_changes.
- Names/IDs, schema, bucket name, domain and role names must remain unchanged.
  Lifecycle guards block destruction while present, but no actual Terraform plan
  was run, so zero replacements or exact mutation counts cannot yet be certified.
- No unsupported import type has been identified. Provider-specific import IDs
  are captured for all 41 candidates, including permission Sids, the notification,
  IAM inline policies and `$LATEST` async configuration. Zero recreation remains
  the proposed approach, not a completed-migration claim.

Source checks use the pinned provider's official
[SQS docs](https://github.com/hashicorp/terraform-provider-aws/blob/v6.70.0/website/docs/r/sqs_queue.html.markdown),
[identity-provider implementation](https://github.com/hashicorp/terraform-provider-aws/blob/v6.70.0/internal/service/cognitoidp/identity_provider.go),
and [S3 encryption implementation](https://github.com/hashicorp/terraform-provider-aws/blob/v6.70.0/internal/service/s3/bucket_server_side_encryption_configuration.go).

## HCP and permissions assessment

HCP's public API is reachable and returns **401** without authentication. No
organization/workspace configuration or API token was found in the task environment,
standard Terraform credential/config locations, or project environment files.
No connected browser is available. **Workspace existence, VCS integration,
execution mode, variables, run permissions and state permissions are unknown**;
this is not evidence that no HCP organization/workspace exists.

The default AWS identity successfully enumerated IAM OIDC providers: no
`app.terraform.io` provider is present in this account. The standard HCP dynamic
AWS credential bootstrap is therefore missing. IAM ListRoles is denied, so no
claim is made that an HCP-named role is absent. Existing broad role trust and
permissions cannot be assessed without the actual intended role and HCP workspace.
No role, provider, token, variable, workspace or VCS setting was created.

Remaining read limitations:

| Read | Result and significance |
| --- | --- |
| lambda:GetPolicy on peach-report-builder | Denied under both available identities; cannot rule out extra resource-policy consumers. Need scoped read to finish that dependency audit |
| kms:DescribeKey on the table's observed key ARN | Denied under both identities; table encryption is visible, but AWS-managed/customer-managed classification and key policy dependencies remain unverified |
| iam:ListRoles | Denied; account-wide HCP-role enumeration unavailable. Supplying the intended role ARN plus read access can avoid a broad account listing |
| cloudformation:ListExports | Denied; however GetTemplate confirms none of the three stacks declares exported outputs, so there are no exports from these stacks for Fn::ImportValue consumers. Scripts using describe-stacks are a separate known cutover dependency |
| s3:GetBucketLocation / HeadBucket | Denied; the HEAD response still reports x-amz-bucket-region=us-east-1. Bucket configuration/list reads succeeded through the reporting role; region and contents are not inferred from the name alone |

Do not request administrator access just to fill these read gaps. The exact KMS
key ARN and function ARN are recorded in the filtered findings for a narrow policy.
A workspace admin must later verify VCS repository/branch, working directory infra,
Remote execution, selected Terraform version, variables, auto-apply setting and
human approval permissions. Dynamic AWS trust must be narrowed to that actual
organization/project/workspace; none of these names should be guessed.

For application CI, prefer a custom **Read outputs only** HCP permission where
available. HashiCorp documents that this supports terraform output. The built-in
Read role also reads complete state and is broader than necessary. The HCP token
and AWS application OIDC role serve different purposes.
[Official workspace permission reference](https://developer.hashicorp.com/terraform/cloud-docs/users-teams-organizations/permissions/workspace).

## Exact blockers and next sequence

1. **Finish access review.** User supplies authenticated HCP access and actual
   organization/workspace identifiers through the browser or a secure local
   credential mechanism, not chat. Grant the two narrow AWS metadata reads above
   or have an administrator provide sanitized results. Identify any existing
   intended HCP role. Do not run terraform login or create a token automatically
   under the present no-credential-modification restriction.
2. **Local reconciliation completed.** Queue sizes, complete Google configuration
   and all public inputs now follow the observation and pass local tests. Refresh
   inventory before a real plan. The local 41-block import candidate is prepared and the versioned adoption gate remains false.
3. **Separately approve bootstrap/configuration.** If no HCP workspace exists,
   the user creates/selects the organization/project/workspace and connects VCS
   with infra working directory and Remote execution. Create/review AWS OIDC
   trust/roles only after approval, with dynamic credentials, least privilege,
   actual workspace-restricted trust, protected state and auto-apply off for
   adoption. Populate existing sensitive inputs securely and configure CI's
   outputs-only access. No secrets need to be sent through this chat.
4. **Prepare reviewed migration artifacts.** Refresh the inventory, finish any
   permission-gap checks and parameter/default reconciliation, then stage exact
   import blocks and review an HCP import-only plan. No code is committed/pushed
   without separate approval. Feature-branch/PR planning and a human-approved
   HCP run should precede any ownership gap where practical.
5. **Authorize retention-only changes.** Review exact change sets using existing
   parameters; deploy/verify both Retain policies on every resource. Freeze
   competing infrastructure/application deploys before handover. Existing app
   requests need not stop, but main pushes currently trigger backend deployment.
6. **Authorize ownership transfer/import.** After retention verification, detach
   only these three stack containers, verify every resource survived, then review
   a fresh plan requiring 41 imports and zero adds/changes/destroys. A human
   approves the HCP run; the assistant does not apply from a laptop. Keep the
   schedule enabled and parser enabled unless a separate operational change is
   explicitly approved. Do not recreate permissions/notifications unnecessarily.
7. **Verify and finish.** Save the immediate clean plan, refresh data/identity
   baselines, verify the application, cut output readers to Terraform, and only
   then remove original templates/import blocks and their legacy consumers/tests.
   Perform the separately approved VCS apply proof and drift exercise, collect
   the screenshot and submission evidence, and commit/push/merge only as authorized.

This assessment ends before step 1 changes any permissions or credentials and
before all bootstrap, retention, detachment and state/import operations.
