# Peach HCP Terraform setup worksheet

Status update, 2026-10-28: the user confirms organization ooad-kremeriatko8,
project Default Project, workspace peach-dev, repository kremeriatko8/Peach,
branch main, working directory infra, Remote execution, Terraform 1.13.5 and
auto-apply disabled. The user also confirms the OIDC provider, role
peach-hcp-terraform-read, scoped read policy, two environment variables and seven
Terraform inputs are configured. Correct role ARN:
`arn:aws:iam::968053399627:role/peach-hcp-terraform-read`.
These are user reports, not a successful credential exchange or live plan.
No setup was changed by this local preparation. Do not recreate confirmed resources.

The source now contains 41 active import blocks, with the versioned gate false,
and is explicitly bound to this organization/workspace. See
[the first-preview instructions](terraform-first-preview.md) for the safe
feature-branch publication and temporary workspace gate override.

## Selection and authentication

1. Sign in to HCP Terraform through its UI. Select the actual organization and
   project, and record their names. Inspect an existing intended workspace before
   creating anything. Workspace existence was not verifiable without authentication.
2. Use one workspace for the **existing** Peach environment in AWS account
   `968053399627`, region `us-east-1`. A name such as peach-dev is merely a possible
   workspace label; do not change PROJECT_NAME or AWS resource names to match it.
3. Select **Remote execution**, Terraform **1.13.5**, working directory **infra**,
   and manual apply approval. Keep auto-apply disabled during migration. Do not
   queue an initial apply, enable auto-destroy, or create a parallel local backend.
4. After publication is separately approved, connect only repository
   `kremeriatko8/Peach` through an appropriately scoped GitHub VCS connection. Agree
   the reviewed deployment branch and PR workflow with the user. The current local
   branch is feat/paste-agenda; it is not an instruction to use that branch for
   infrastructure. None of the new Terraform files has been committed/pushed yet,
   so today's remote repository must not be assumed to contain this configuration.
5. Grant reviewers plan visibility and reserve apply approval for the designated
   human. Restrict state and variable administration. HCP's built-in Read role can
   read complete state; use custom **Read outputs only** access for application CI
   where available. Do not grant an assistant or CI token write-state/apply rights
   just to inspect outputs. Review additive team/org permissions as well.

The explicit cloud block pins organization ooad-kremeriatko8 and workspace
peach-dev; ambient TF_CLOUD_ORGANIZATION/TF_WORKSPACE cannot redirect those names.
Authenticate future approved CLI/output reads through a securely provisioned
scoped token or the user's approved login. No login/token creation or backend
initialization against HCP was performed by local validation. Do not paste tokens
into chat, HCL, tfvars or shell command arguments. The existing CI design obtains
its token from a GitHub secret and unsets it before builds.

## Input matrix

The reconciled `infra/terraform.tfvars` contains all **31 observed non-secret
inputs**, including the exact account, names, network IDs, distinct image digests,
Cognito email constraints, parser flags/prices and ENABLED schedule state. Their
provenance is [the public worksheet](terraform-live-input-worksheet.json). Refresh
against live AWS before handover. Do not duplicate them in HCP with conflicting
workspace-variable overrides or variable sets. Complex values remain typed HCL.

Exactly seven required inputs intentionally remain outside that file:

| Terraform variable | HCP category | Sensitive | Source/action |
| --- | --- | --- | --- |
| google_client_id | Terraform | Optional privacy restriction; never expose the paired secret | Existing local Google ID was compared equal to live; provision securely |
| google_client_secret | Terraform | Yes | Existing verified Google secret; do not rotate during migration |
| database_url | Terraform | Yes | Existing report-builder value, verified equal to backend; no new DB URL |
| report_owner_sub | Terraform | Yes | Existing configured report owner; no reassignment |
| report_from_email | Terraform | Yes | Existing configured SES sender |
| report_recipient_email | Terraform | Yes | Existing configured SES recipient |
| cognito_jwks_json | Terraform | No, public key material | Exact existing parser/backend snapshot, verified equal; preserve its string representation |

Do not copy masked CloudFormation NoEcho placeholders as values. Keep the JSON
JWKS a Terraform string: enter its exact value with HCL parsing disabled, or use a
properly quoted HCL string if HCL parsing is enabled. Do not treat it as an object.
Secret variables should be entered through HCP's protected UI or an explicitly
approved in-memory provisioning path. Never generate secret tfvars/parameter
files, plan logs, state downloads or screenshots for this setup. Sensitive=true
redacts normal display; HCP state and saved plans still contain sensitive values.

`adoption_inventory_complete` stays **false** in the public configuration. Only a
separately approved mapping/configuration review may change it before an import
plan. All 41 observed-ID import blocks are active in source. They do not perform
imports until an approved apply; the default gate remains false.

## AWS workload identity bootstrap (approval required, not performed)

October 27 discovery found no standard app.terraform.io IAM OIDC provider in
the target account. The user subsequently confirms it and the intended read role
were created manually; do not create duplicates. Role enumeration was denied, so an existing intended role may still
exist; ask for its ARN and inspect it before creating another role.

An AWS administrator must review/create the identity provider and role trust only
after approval. Identity-provider URL: `https://app.terraform.io`, without a
trailing slash. Audience: `aws.workload.identity`. A separate bootstrap owner/state
must manage these resources; do not mix their creation into the 41-object import
root module. Verify any TLS thumbprint requirements through the supported IAM
setup process rather than copying a stale hardcoded fingerprint.

The user selected one read-only role for both phases, using
TFC_AWS_RUN_ROLE_ARN. Two phase-restricted roles remain optional future hardening. Trust format for the plan role
(the ORG, PROJECT, WORKSPACE placeholders are intentionally not real names):

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "Federated": "arn:aws:iam::968053399627:oidc-provider/app.terraform.io"
    },
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {
      "StringEquals": {
        "app.terraform.io:aud": "aws.workload.identity",
        "app.terraform.io:sub": "organization:ORG:project:PROJECT:workspace:WORKSPACE:run_phase:plan"
      }
    }
  }]
}
```

The apply-role trust uses the exact same organization/project/workspace and
`run_phase:apply`. Do not wildcard organization, project or workspace. Neither
trust policy is installed by this document. Role names/ARNs must come from the
approved bootstrap, not invented defaults.

Both roles can use AWS read-only permissions for an adoption whose only actions
are importing existing objects into Terraform state. HCP's import apply changes
**remote Terraform state**, so it remains a separate approval even when AWS reads
are the only service operations. No AWS mutation permissions are needed merely to
accept an import-only plan. The later tag/log-retention demonstration needs a
separate, narrowly scoped policy and explicit approval. Avoid AdministratorAccess
and don't grant access to alter the external parser boundary or recreate Aurora.

Provider reads span Cognito, IAM, Lambda, SQS, S3, DynamoDB, Logs, EC2 and Scheduler;
policies must cover the exact 41 objects and the SDK's required metadata reads.
Some account/region list/describe calls require Resource="*". Their least-privilege
policy must be reviewed against the pinned provider and actual role before use.
The two-action dependency policy below is **not** a complete HCP provider policy.
Additional provider permission failures must be resolved by adding specific reads,
not by allowing creates/updates or suppressing the plan differences.

Set these HCP **environment** variables after the bootstrap is approved:

| Name | Value |
| --- | --- |
| TFC_AWS_PROVIDER_AUTH | true |
| TFC_AWS_PLAN_ROLE_ARN | Actual approved plan-role ARN |
| TFC_AWS_APPLY_ROLE_ARN | Actual approved import/apply-role ARN |

When both phase-role ARNs are provided, TFC_AWS_RUN_ROLE_ARN is unnecessary. A
single approved role can instead use TFC_AWS_RUN_ROLE_ARN and phase-wildcard trust,
but phase-separated trust is narrower. Do not configure static AWS access keys or
AWS_PROFILE in the HCP workspace. The provider gets region/account restriction
from Terraform inputs and credentials from HCP workload identity.

## Minimum additional dependency-read access

[The proposed two-action policy](terraform-additional-read-permissions.json) adds:

- `lambda:GetPolicy` only on
  `arn:aws:lambda:us-east-1:968053399627:function:peach-report-builder`.
- `kms:DescribeKey` only on
  `arn:aws:kms:us-east-1:968053399627:key/ca6609f6-9d47-4344-8e37-81d176415ac0`.

An administrator may attach this to one approved discovery identity, for example
the existing reporting role, after approval. A separate Allow cannot override an
explicit Deny, SCP, boundary or KMS key-policy restriction; an administrator must
resolve any applicable restriction without broadening unrelated privileges.
The policy file is a request artifact only; it has not been applied or attached.

These two reads close the confirmed metadata denials. If DescribeKey reports a
customer-managed key, completing its key-policy dependency audit additionally
requires `kms:GetKeyPolicy` on that same key (PolicyName=default), or an
administrator-provided sanitized policy assessment. This conditional read is not
included in the minimum policy before key ownership is known. No kms:Decrypt,
secret retrieval, table scans or Lambda invocation is requested.

No broad iam:ListRoles, cloudformation:ListExports or S3 listing permission is
required for those two checks: the intended HCP role can be supplied directly,
none of the three stacks exports outputs, and region/object counts were already
observed. Auditing a supplied HCP role may require role-scoped GetRole,
ListRolePolicies, GetRolePolicy and ListAttachedRolePolicies, plus GetPolicy and
GetPolicyVersion on its actual attached policies if the current identity lacks
those reads. Scope these only after the real role/policy ARNs are known.

## Before any ownership transfer

Confirm the VCS configuration contains the reviewed reconciliation and observed
IDs, required variables are present, the IAM trust matches the exact workspace,
and a human can inspect and approve the full plan. Refresh inventory and close
the read gaps. Independently review and deploy retention-only CFN changes under
separate approval; verify both Retain policies on every resource. Stage/review
exact import blocks only when authorized, freeze competing deploys, and transfer
ownership through the reviewed HCP run. Require 41 imports with no managed
resource adds/updates/deletes, then a clean plan and preservation checks.

Do not change enabled schedules, parser flags, images, IAM permissions, events or
DB connectivity for migration convenience. No commit/push/merge, credential setup,
HCP bootstrap, retention deployment, detachment or import is authorized by this
worksheet. See the [readiness report](terraform-migration-readiness.md).

References: [HCP AWS dynamic credentials](https://developer.hashicorp.com/terraform/cloud-docs/dynamic-provider-credentials/aws-configuration),
[workspace permissions](https://developer.hashicorp.com/terraform/cloud-docs/users-teams-organizations/permissions/workspace).
