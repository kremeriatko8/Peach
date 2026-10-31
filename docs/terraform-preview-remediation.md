# First speculative preview remediation

Run: https://app.terraform.io/app/ooad-kremeriatko8/peach-dev/runs/run-KkT61Sro17vKC8Dd

The run was plan-only, Terraform 1.13.5, and errored. Its incomplete summary was
29 imports, 1 addition, 2 updates and 1 destruction. No resource or state changes
were applied. The workspace has no current state version; auto-apply remains off.
The versioned adoption gate remains false. No new real plan has been run.

## Evidence and corrections

Authenticated reads retrieved the full diagnostic log and the CLI redacted JSON
representation. The normal JSON-output endpoint returned HTTP 204. Raw logs and
JSON stay outside Git in private temporary files: imported Google details and
mailer conditions can contain secrets even when proposed sensitive fields are
redacted. Only sanitized addresses, action counts and replacement paths are in
terraform-preview-remediation-evidence.json.

### Cognito frontend client: proven create-only import mismatch

The JSON replace_paths is exactly [["generate_secret"]]. The imported value is
null and the configured value was false. The live DescribeUserPoolClient read
confirmed the same existing client ID and no client secret. Provider 6.70.0 marks
generate_secret RequiresReplace; its import sets only IDs and its Read does not
populate generate_secret. The user_pool_id is also replacement-triggering but is
not listed as a replacement cause in this plan. Other computed changes were
consequences of replacing the client, not separate replacement paths.

Local correction: omit generate_secret and expect null in mocked tests. This
preserves the existing secretless client's identity, OAuth settings and
prevent_destroy. No ignore_changes, targeting, client recreation or lifecycle
weakening was introduced. A regression test checks the recorded replacement
cause and rejects reintroducing this create-only setting.

Provider source:
https://github.com/hashicorp/terraform-provider-aws/blob/v6.70.0/internal/service/cognitoidp/user_pool_client.go

### Google provider: secret-only discrepancy, proposed value unavailable

The changed path is only provider_details.client_secret. A fresh live AWS read
matched the plan-before provider details and attribute mapping exactly. All
non-secret Google details, mapping, name, type and pool match the proposed values.
The proposed secret is a redacted 64-character value with after_sensitive=true;
it is not a usable secret and must not be copied into configuration. The provider
passes changed provider_details to UpdateIdentityProvider, so accepting this
update could rotate or overwrite the existing Google credential.

No local configuration change is justified. Verify the existing sensitive HCP
input against the deployed provider's credential privately, including accidental
quotes, whitespace or wrong credentials; correct only a confirmed mismatch under
separate approval. The proposed map has no unknown attributes. The exact private-value comparison
remains blocked by redaction and HCP's write-only variable API. Do not rotate
credentials or ignore the field to obtain a clean plan.

### Mailer inline policy: opaque proposed document

The name report-mailer and its role are unchanged. Parsed policy-before matches
the recorded policy after normalizing Action/Resource scalar-or-list forms and
statement ordering and excluding private SES condition values. All five configured
grant groups match that baseline: log writes, scoped report CSV reads, mail-state
DynamoDB reads/updates, SES SendRawEmail, and failure-queue SendMessage. Resource
ARNs, effects, absence of Sids and condition operators also match. The SES
FromAddress is StringEquals; Recipients is ForAllValues:StringEquals with a list.

However, the entire proposed policy is redacted because it depends on sensitive
sender/recipient variables. It cannot be JSON-decoded or semantically compared as
a real policy. Its redacted placeholder must not be interpreted as policy text.
Further analysis confirms after_unknown is empty, so this is not unknown-value
propagation. Provider 6.70.0 uses SuppressEquivalentPolicyDiffs and JSON
normalization for role policies, so ordinary whitespace, object-key ordering,
statement ordering and equivalent scalar/list encodings are not a supported
explanation for this update. Existing grants and condition structure match the
configuration, leaving SES sender/recipient input mismatch as the leading cause.
The exact private condition/value cannot be proved from the redacted response.
The default identity's targeted iam:GetRolePolicy read was denied. The existing
peach-reports-deploy profile was then checked against the expected AWS account and
successfully read this exact inline policy. It matches plan-before exactly. No
broader IAM discovery permission was requested. This rules out a subsequent live
policy change as the source of the discrepancy.

No mailer IAM change, ignore_changes, or permissions expansion was introduced.
Privately verify the two HCP email inputs against the existing policy conditions;
request a reviewable non-sensitive field-path diff if a future run still differs.

## Minimum read-policy supplement

terraform-preview-read-permissions.json contains exactly two new statements:

- lambda:ListVersionsByFunction on only peach-report-builder, peach-report-mailer
  and peach-agenda-parser function ARNs, restricted to us-east-1.
- ec2:DescribePrefixLists on Resource "*", restricted to us-east-1. AWS does not
  support resource-level scoping for this action; it reads metadata, not workloads.

Both are classified IsWrite=false in official AWS service-reference metadata:
https://servicereference.us-east-1.amazonaws.com/v1/lambda/lambda.json
https://servicereference.us-east-1.amazonaws.com/v1/ec2/ec2.json

The local previously reviewed PeachHcpReadOnly.json was inspected. The proposed
merged copy has 64 distinct read actions and 5918 compact JSON characters. No
existing statement is changed. Its current live attachment/document could not be
independently read with the local identity; compare the console document before
appending these statements. This supplement is not permission to apply it.

Temporary review artifacts:
- /private/tmp/peach-worktree-transfer-audit/PeachHcpReadOnly.patch.json (RFC 6902)
- /private/tmp/peach-worktree-transfer-audit/PeachHcpReadOnly.proposed.json

The selected supplement includes the parser ARN because its unqualified import
uses the same mandatory latest-version read. This is source-backed rather than
an observed parser denial. The former two-function candidate would leave that
provider read uncovered. Both actions remain read-only and no wildcard Lambda
access is added.

Provider read paths:
https://github.com/hashicorp/terraform-provider-aws/blob/v6.70.0/internal/service/lambda/function.go
https://github.com/hashicorp/terraform-provider-aws/blob/v6.70.0/internal/service/iam/role_policy.go
https://github.com/hashicorp/terraform-provider-aws/blob/v6.70.0/internal/verify/json.go

## Minimal manual actions

1. AWS Console: IAM > Roles > peach-hcp-terraform-read > Permissions > Add
   permissions > Create inline policy > JSON. Paste the complete contents of
   terraform-preview-read-permissions.json. Review and save as
   PeachHcpMigrationPreviewRead. This additive policy preserves existing grants
   and avoids replacing an existing policy whose current document the local
   identity cannot read. It adds only the two required metadata actions above.
   This is a privileged change requiring the user's authorization; no policy has
   been created or attached by this remediation.
2. HCP sensitive inputs are write-only: GET returns no value, even with the
   current owner's credentials. Do not remove sensitivity to inspect them.
   A private in-memory check confirmed the original checkout's .env key
   GOOGLE_CLIENT_SECRET exactly matches the currently deployed Google provider.
   Use that existing local value as the authoritative source for verifying or
   re-entering google_client_secret; do not rotate it or print it here. Verify/re-enter report_from_email and
   report_recipient_email from the existing peach-report-mailer / report-mailer
   inline policy's ses:FromAddress and ses:Recipients conditions, respectively.
   Use HCP workspace Variables > edit each Terraform variable, Sensitive enabled,
   HCL disabled, with the raw string and no surrounding quotes or extra newlines.
   Copy these only within trusted local administrative UIs; never into chat,
   reports, terminal commands or source files. Only a confirmed mismatch warrants
   changing a value; if the originals cannot be compared because HCP hides them,
   re-entering the authoritative existing values establishes equality without
   changing the deployed credentials or permissions. No secret value was printed
   or newly persisted for this comparison attempt.
3. No other HCP variable change is indicated. Keep the workspace adoption gate
   absent/false; the eventual preview uses only the approved run-specific override.

HCP write-only variable API:
https://developer.hashicorp.com/terraform/cloud-docs/api-docs/workspace-variables

## Remaining 12 imports

These are pending evaluation, not proven missing resources. Their addresses and
IDs match all 41 static import blocks and the recorded inventory:

- aws_lambda_permission.parser_invoke
- aws_lambda_function.parser
- aws_lambda_function_url.parser
- aws_lambda_permission.parser_url
- aws_cognito_managed_login_branding.frontend
- aws_lambda_function.builder
- aws_lambda_event_source_mapping.builder
- aws_lambda_function.mailer
- aws_lambda_function_event_invoke_config.mailer
- aws_lambda_permission.mailer_s3
- aws_s3_bucket_notification.reports
- aws_vpc_endpoint.reports_s3

The builder/mailer reads and endpoint read failed; related downstream resources
and Cognito branding could not be fully evaluated. Parser evaluation was also
absent. No import IDs have been removed or guessed. The evidence file and tests
verify the 29 + 12 partition exactly covers the inventory.

## Next controlled steps

1. Review this uncommitted migration-only local diff and IAM supplement.
2. Separately approve the minimal IAM read additions and any confirmed private-input
   corrections. No workspace variables were changed here.
3. Review the local correction before a new CLI preview. A CLI preview can upload
   a private snapshot of reviewed local changes without committing. Updating the
   published PR itself requires a separately approved commit/push; publishing can
   trigger speculative HCP planning, so authorization must cover that event.
4. Rebuild and initialize a new private archive of the reviewed corrected source,
   with an exact manifest of the base commit and approved local patch hashes. The
   earlier archive and published commit remain unchanged and contain the old
   generate_secret setting; do not reuse them for the corrected preview.
5. Separately approve one fresh plan-only run with the same run-only gate override.
   Require exactly 41 imports, zero additions/updates/destructions/replacements,
   correct IDs and no unresolved checks before retention or detachment.

This configuration is locally corrected for the proven Cognito cause, but is not
yet ready for an expected-clean second preview: missing IAM reads and the two
sensitive-value update investigations remain blockers. No ownership transfer is
authorized by this report.

## Local validation results

Terraform formatting, full configuration validation with active imports, all six
mocked tests, and the 41-ID audit passed. The complete scripts suite passed
256 tests and 63 subtests (including 41 migration safety tests). Ruff lint/format
on all five migration Python files, actionlint, cfn-lint on all three source
templates, and diff whitespace checks passed. No new real plan was executed.

## Corrected CLI archive prepared

/private/tmp/peach-cli-preview-corrected-drewnele contains exactly 62 infrastructure
files from published commit 7e2fcf32373c611f7a3e9f5be0479a38a0d1cd7c, with only
infra/auth.tf and infra/tests/migration.tftest.hcl overlaid from the reviewed local
remediation. It contains no environment files, state, secrets or unrelated local
changes. Exact file hashes and the local infrastructure patch hash are recorded
outside the upload tree in corrected-preview-manifest.json. Both source gate
defaults remain false. It was safely initialized against existing remote peach-dev
with auto-apply disabled and external local metadata; no plan was executed.

After the outstanding IAM/private-input checks and separate plan approval:

```bash
env -u TF_CLI_CONFIG_FILE -u TF_CLI_ARGS -u TF_CLI_ARGS_plan \
  TF_DATA_DIR=/private/tmp/peach-worktree-transfer-audit/corrected-preview-tfdata \
  /private/tmp/peach-lab7-tools/terraform \
  -chdir=/private/tmp/peach-cli-preview-corrected-drewnele/infra plan \
  -input=false -var-file=terraform.tfvars \
  -var='adoption_inventory_complete=true'
```

No -out or apply is permitted. Recheck ambient Terraform overrides, archive hashes
and live workspace safety settings before execution. This command is prepared,
not executed. The published PR and original working branch remain untouched.
