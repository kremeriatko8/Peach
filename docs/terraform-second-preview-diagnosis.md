> Superseded by third-preview evidence below: all five authoritative values and
> all four resources' complete before/after attributes are equal. The remaining
> Update actions change sensitivity marks only, not resource values. Do not infer
> incorrect private inputs from the earlier redacted representations.

# Second preview: consolidated diagnosis and next actions

Run: https://app.terraform.io/app/ooad-kremeriatko8/peach-dev/runs/run-wbpcotimuA5vGsad

Actual incomplete result: 40 imports, 4 updates, no additions, replacements or
destructions. The client is no-op with its original ID. No state version exists.
No plan, retry, cloud change, HCP variable change or publication was performed in
this investigation. All source adoption gates and prevent_destroy remain intact.

## One missing read action

The remaining resource is aws_cognito_managed_login_branding.frontend. Provider
reading requires cognito-idp:ListUserPoolClients on the existing pool. AWS service
metadata classifies this action as read-only and supports userpool resource scope.

AWS Console > IAM > Roles > peach-hcp-terraform-read > Permissions > inline policy
PeachHcpMigrationPreviewRead > Edit JSON. Append the following object to the
existing Statement array. Preserve every existing statement and Version field:

```json
{
  "Sid": "ReadExistingPoolClientsForBrandingImport",
  "Effect": "Allow",
  "Action": "cognito-idp:ListUserPoolClients",
  "Resource": "arn:aws:cognito-idp:us-east-1:968053399627:userpool/us-east-1_bs7cWxhJp",
  "Condition": {
    "StringEquals": {
      "aws:RequestedRegion": "us-east-1"
    }
  }
}
```

The complete reviewed supplement, preserving the two earlier Lambda/EC2 statements,
is in terraform-preview-read-permissions.json. The exact append operation is also
in /private/tmp/peach-worktree-transfer-audit/branding-permission-amendment.json.
No other action or wildcard resource grant is requested. This permission has not
been added to AWS by this investigation.

## Four updates, five private inputs

| Resource | Proven changed paths | Source for preserving current deployed behavior |
| --- | --- | --- |
| Google identity provider | provider_details.client_secret | Cognito DescribeIdentityProvider Google / ProviderDetails.client_secret |
| Builder Lambda | environment DATABASE_URL, REPORT_OWNER_SUB | GetFunctionConfiguration peach-report-builder / Environment.Variables |
| Mailer Lambda | environment REPORT_FROM_EMAIL, REPORT_RECIPIENT_EMAIL | GetFunctionConfiguration peach-report-mailer / Environment.Variables |
| Mailer IAM policy | policy | GetRolePolicy peach-report-mailer / report-mailer; SES FromAddress and Recipients conditions |

The mappings in Terraform are direct and correct. No trim, URL rewrite, email case
conversion, null substitution or key swap is performed. HCP variables use string
mode (HCL disabled). Google changed no other detail. The policy's grants, resources,
role/name and condition structure match imported AWS. A fresh reporting-profile
read confirms the live policy is unchanged. The provider suppresses semantically
equivalent policies; after_unknown is empty. Thus unknown propagation and ordinary
JSON normalization do not explain the proposed mailer update. A mismatch in private
input values is the leading explanation, not a proven comparison of hidden values.

The current AWS values for all five inputs match their second-plan imported values
exactly. Mailer environment emails match its single-value SES IAM conditions
exactly. Original local .env GOOGLE_CLIENT_SECRET matches deployed Google. Original
local Docker DATABASE_URL differs from deployed builder and is not used as an
input source. No private value or fingerprint is printed or included here.

HCP sensitive inputs are write-only. The APIs return no usable stored value; the
redacted plan replaces proposed sensitive data with opaque tokens. Those tokens
are not documented equality digests and must not be used to infer secret equality,
reversed, or copied as values. No result from candidate hashing is treated as proof.
The precise hidden mismatch and any remaining provider-specific import/sensitivity
behavior cannot be established without another separately approved controlled
preview. No ignore_changes or other drift suppression is justified.

References:
- https://developer.hashicorp.com/terraform/cloud-docs/api-docs/workspace-variables
- https://github.com/hashicorp/terraform-provider-aws/blob/v6.70.0/internal/service/iam/role_policy.go
- https://github.com/hashicorp/terraform-provider-aws/blob/v6.70.0/internal/verify/json.go
- https://servicereference.us-east-1.amazonaws.com/v1/cognito-idp/cognito-idp.json

## Avoid another manual secret-copy loop

scripts/terraform-live-inputs.py now provides a read-only default mode. It checks:

- Exact archive hashes, the 41 imports, client fix and false source gate.
- Existing Remote peach-dev, disabled auto-apply and expected OIDC environment.
- No HCP variable sets that could outrank run-specific inputs.
- Both AWS sessions belong to account 968053399627.
- Fresh Google/provider and builder/mailer values, using only existing read access.
- Exactly one literal SES sender/recipient; correct condition operators; exact
  agreement between mailer environment and IAM conditions. Multiple values,
  wildcards, source disagreement, missing values or surrounding whitespace stop it.

Default mode was executed successfully. It prints only fixed messages, not values.
It neither writes secrets nor runs Terraform. All five live values remain in
process memory only. Sources use the default profile for Google and the existing
peach-reports-deploy profile for Lambda and IAM reads. No new operator permission
is required for these reads.

A future explicitly approved execution can supply these exact values as child
process TF_VAR_* inputs. HCP documents run-specific TF_VAR variables as higher
precedence than workspace values; no priority sets currently exist. The public
-var-file contains none of these private inputs. The command adds only the
run-specific adoption gate override, has no -out, and cannot execute apply. This
eliminates manual HCP variable edits as a prerequisite and distinguishes stale
workspace input issues from provider behavior in the next controlled preview.

No permanent HCP variable correction is asserted to be necessary or performed.
If this controlled preview still shows sensitive-field updates, investigate the
provider/import representation rather than rotating credentials or applying them.

## Prepared execution, not executed

Archive: /private/tmp/peach-cli-preview-corrected-drewnele
Manifest: /private/tmp/peach-worktree-transfer-audit/corrected-preview-manifest.json
The 62-file upload archive is unchanged. The helper and diagnostics are outside
it; only the Cognito configuration/test corrections overlay the published base.

Read-only reproduction:

```bash
PYTHONDONTWRITEBYTECODE=1 /usr/bin/sandbox-exec \
  -p '(version 1)(allow default)(deny file-write*)(allow file-write-data (literal "/dev/null"))' \
  /Users/sofiakremer/Documents/peach/Peach/backend/.venv/bin/python \
  scripts/terraform-live-inputs.py \
  --manifest /private/tmp/peach-worktree-transfer-audit/corrected-preview-manifest.json
```

After IAM amendment and separate approval for one new speculative plan:

```bash
PEACH_APPROVE_INFRA_PLAN=yes \
PYTHONDONTWRITEBYTECODE=1 /usr/bin/sandbox-exec \
  -p '(version 1)(allow default)(deny file-write*)(allow file-write-data (literal "/dev/null"))' \
  /Users/sofiakremer/Documents/peach/Peach/backend/.venv/bin/python \
  scripts/terraform-live-inputs.py \
  --manifest /private/tmp/peach-worktree-transfer-audit/corrected-preview-manifest.json \
  --execute-preview \
  --terraform /private/tmp/peach-lab7-tools/terraform \
  --data-dir /private/tmp/peach-worktree-transfer-audit/corrected-preview-tfdata
```

The execution guard requires both the explicit flag and approval environment
variable. It removes ambient TF_VAR/TF_CLI_ARGS/TF_LOG/AWS overrides before the
child plan. Five private values and the existing HCP token are passed only through
process environment, never arguments or files. Exactly one subprocess plan is
invoked, without retry. Terraform logs remain sensitive; keep their handling private.

## Validation and readiness

Terraform fmt/validate, 6 mocked scenarios, complete script suite (264 tests and
63 subtests), migration/helper tests, Ruff, actionlint and original CFN checks pass.
Tests prove default mode cannot execute, execution is approval-gated, command args
contain no private values or -out/target/replace options, and ambiguous SES sources
stop. No new HCL secret-mapping fix is warranted. The original application branch
and published PR are unchanged.

Minimum user involvement: append one IAM statement, then authorize one controlled
preview with the helper. No manual secret copy or HCP setting change is required.
Acceptance remains 41 imports, zero additions/updates/replacements/destructions,
correct IDs and resolved checks. Do not detach CloudFormation yet.

## Output and crash hardening before the third preview

The earlier inherited stdout/stderr path is removed. Child stdout and stderr are
captured in memory, stdin is /dev/null, check=False avoids automatic exception
formatting, and arbitrary diagnostics are never forwarded. An output-schema
allowlist admits only canonical HCP URLs, enumerated statuses/categories and
bounded counts. Argparse errors, exceptions, nonzero exits, malformed data and
crashes fail closed without echoing input or tracebacks. API plans and signed
log bodies are parsed in memory and never written to disk.

Launch the entire helper through the macOS sandbox shown above. It denies all
regular-file writes for the helper and descendants; only the nonpersistent
/dev/null sink is permitted for subprocess stdin plumbing. Parent and child
write-denial probes are required before execution. Core dumps are disabled,
Python bytecode writes are disabled, and ambient TF_LOG/TF_CLI_ARGS/TF_VAR/AWS
overrides are removed from the Terraform child. The source/archive remain
read-only. No debug, crash, plan, temporary secret, or provider-cache file can be
written by this controlled local process. If the OS boundary is unavailable or
the pinned CLI cannot run within it, stop before planning.

Pinned source review: Terraform 1.13.5 uses go-tfe v1.74.1. Configuration upload
packs the verified public archive into bytes.Buffer, not disk. Its panic handler
writes to fd 2, which is captured privately. OS denial also protects against
unexpected file-writing failure paths. Remote provider execution is in HCP, not
a local provider process.

Synthetic tests cover stdout/stderr, successful and failed output, exceptions,
unknown arguments, malformed output, negative/signal exits, simulated crashes,
opaque private fields and a real OS-denied secret-bearing crash-file attempt.
No marker reaches user-visible output. Full regression checks pass. The helper
security suite now has 25 tests. Terraform validate and six mock tests also pass.

Limits: this does not claim secrecy against a privileged OS observer reading
process memory/environment, OS-managed swap or third-party HCP infrastructure.
HCP necessarily receives these authorized run inputs over TLS and may retain
encrypted artifacts; remote provider/service logs are governed by that service.
Within this local mechanism, raw diagnostics are never displayed or saved. These
external limits are not hidden by sensitive=true or a claim of absolute secrecy.

## Third controlled preview: actual outcome

https://app.terraform.io/app/ooad-kremeriatko8/peach-dev/runs/run-imy3iE9GiZh9i2WD

Exactly one plan-only run was executed through the hardened helper in the mandatory
OS sandbox. HCP reports planned_and_finished: 41 imports, zero additions, four
updates, zero replacements and zero destructions, no errors or warnings. All
import IDs match. The new Cognito read permission is effective.

The completed unredacted JSON became readable and was inspected entirely in memory.
For all five private inputs, before == after == authoritative live AWS value.
The complete before/after attribute objects for all four updated resources are
equal, including the mailer policy string. Their only differences are sensitivity
marks. Thus the authoritative overrides did not remove the Update actions, but
they conclusively rule out value/configuration drift for this run.

Terraform 1.13.5 intentionally upgrades NoOp to Update when marks differ (lines
1175-1185), and on apply explicitly skips the provider update call for equal-value
sensitivity-only updates (lines 2397 onward). This is a state-metadata transition
caused by import/config sensitivity propagation. It is not an unresolved IAM error,
wrong credential, email mismatch, policy JSON normalization or infrastructure
replacement. No nonsensitive/ignore_changes workaround is introduced.

https://github.com/hashicorp/terraform/blob/v1.13.5/internal/terraform/node_resource_abstract_instance.go#L1175
https://github.com/hashicorp/terraform/blob/v1.13.5/internal/terraform/node_resource_abstract_instance.go#L2397

The strict acceptance criterion still fails because it requires zero Update
actions. The existing adoption guard correctly rejects this plan. No apply, state
write, retry, further variable change or CloudFormation detachment is authorized.
The smallest next step is explicit review of this sensitivity-metadata exception
versus the zero-update criterion, retaining all security/lifecycle safeguards.
Do not change credentials again or weaken sensitivity merely to force no-op.

Sanitized machine-readable result: terraform-third-preview-result.json. The raw
CLI streams, full JSON and signed diagnostic bodies were never written locally or
forwarded. The helper now categorizes sensitivity-only updates when a full JSON
plan proves them; redacted data alone cannot establish that classification.
