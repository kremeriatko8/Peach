# Sensitivity metadata: import assessment and approval blocker

Date: 2026-10-29. Terraform 1.13.5, AWS provider 6.70.0.
Run: https://app.terraform.io/app/ooad-kremeriatko8/peach-dev/runs/run-imy3iE9GiZh9i2WD

The successful speculative run contains 41 imports and four Update actions, with
no additions, replacements, destructions or diagnostic errors. Full private JSON
inspection proves every before/after resource attribute is identical and known.
Only sensitivity marks change. No state version exists; these marks have not been
adopted. No new plan, apply, import or state command was executed for this review.

## Exact affected resources and paths (no values)

| Resource | Paths gaining sensitivity | Source |
| --- | --- | --- |
| aws_cognito_identity_provider.google[0] | provider_details.client_secret | google_client_secret |
| aws_iam_role_policy.mailer | policy | report_from_email and report_recipient_email through jsonencode |
| aws_lambda_function.builder | environment[0].variables.DATABASE_URL; environment[0].variables.REPORT_OWNER_SUB | database_url; report_owner_sub |
| aws_lambda_function.mailer | environment[0].variables.REPORT_FROM_EMAIL; environment[0].variables.REPORT_RECIPIENT_EMAIL | report_from_email; report_recipient_email |

## Why the four Update actions exist

1. The provider's import/read path obtains the real object and IDs. The pinned
   provider schema does not mark provider_details, IAM role policy, or Lambda
   environment.variables sensitive. The imported before values therefore do not
   carry the configuration-derived marks at these paths. Contrast the Cognito
   client.client_secret schema, which does declare sensitive=true.
2. The five root input variables declare sensitive=true. Their marks propagate
   into the Google map and Lambda environment. jsonencode propagates a sensitive
   descendant into the whole resulting policy string; it cannot attach marks to
   individual fields inside an opaque JSON string.
3. Terraform adds configuration and schema marks back to the planned value before
   deciding the final action. At node_resource_abstract_instance.go lines
   1175-1185, a NoOp is deliberately promoted to Update if marks differ, even when
   all unmarked values compare equal. This is intentional core behavior, not an
   AWS drift, policy-normalization, credential, input-formatting or replacement bug.
4. State stores raw attributes separately from sensitive path metadata (internal
   AttrSensitivePaths, serialized as sensitive_attributes). Sensitivity controls
   redaction, not encryption of those raw values. HCP state access remains private.
5. At apply lines 2390-2415, Terraform strips marks, checks exact value equality,
   and returns the new marked state before calling provider.ApplyResourceChange.
   Thus these exact four equal-value mark transitions take the state-only branch:
   no provider UpdateIdentityProvider, PutRolePolicy or UpdateFunctionConfiguration
   call is issued for these transitions. Import/refresh still performs AWS reads.
   This says nothing about unrelated future plans or separately authorized CFN
   retention/detachment operations.

Pinned primary sources:
- Core mark propagation/action: https://github.com/hashicorp/terraform/blob/v1.13.5/internal/terraform/node_resource_abstract_instance.go#L1025
- Core Update promotion: https://github.com/hashicorp/terraform/blob/v1.13.5/internal/terraform/node_resource_abstract_instance.go#L1175
- Core state-only apply branch: https://github.com/hashicorp/terraform/blob/v1.13.5/internal/terraform/node_resource_abstract_instance.go#L2390
- State encoding: https://github.com/hashicorp/terraform/blob/v1.13.5/internal/states/instance_object.go#L151
- Serialized state metadata: https://github.com/hashicorp/terraform/blob/v1.13.5/internal/states/statefile/version4.go#L650
- Google schema: https://github.com/hashicorp/terraform-provider-aws/blob/v6.70.0/internal/service/cognitoidp/identity_provider.go#L61
- IAM schema: https://github.com/hashicorp/terraform-provider-aws/blob/v6.70.0/internal/service/iam/role_policy.go#L63
- Lambda schema: https://github.com/hashicorp/terraform-provider-aws/blob/v6.70.0/internal/service/lambda/function.go

The schema flags were also verified against the provider_schemas included in the
actual pinned-provider plan representation, without printing resource values.
Full-plan equality checks were repeated read-only in memory. Redacted placeholders
are never used to establish value equality.

## Can configuration safely make the initial plan zero-update?

No supported configuration-only correction was identified for this pinned stack
while retaining the required sensitivity declarations and an unadopted state.
Import blocks select identity/provider; they do not offer a setting that pre-seeds
configuration-derived sensitive paths in the imported prior object.

| Candidate | Assessment |
| --- | --- |
| Add sensitive() or move the same inputs through locals/modules | Still adds marks only to the planned configuration; does not seed prior import metadata |
| Remove sensitive=true or use nonsensitive() | Can remove the difference by weakening redaction; rejected, not implemented |
| ignore_changes | Conceals or reverts changes without solving metadata provenance; rejected |
| Omit secrets/environment/policy | Required fields or altered management/behavior; not a legitimate preservation fix |
| Change import ID/order or split blocks | Selects the same provider import result; no sensitivity metadata option |
| Direct CLI import first | Writes state (not authorized), still obtains provider-only marks, and is not evidence that the first full plan will be zero-update |
| Refresh-only, state editing, state seeding or a preliminary apply | Requires state changes, moves rather than removes the initial reconciliation, and is not a configuration-only solution |
| Upgrade/fork the core/provider | No verified fix identified; the current behavior is intentional. Do not change pinned versions or claim an untested upgrade solves it |

No HCL secret handling, provider version, import address, lifecycle protection or
acceptance gate has been changed. No hypothetical workaround was executed.

## What the assignment actually says

The user-supplied assignment text was read directly. Exact excerpts and its SHA256
are recorded in terraform-sensitivity-assessment.json, independent of web summaries.

| Stage | Written requirement/evidence |
| --- | --- |
| Initial import | Part 2 Step 3 says the plan must show only imports. Step 3c gives the goal: `Plan: 14 to import, 0 to add, 0 to change, 0 to destroy.` The example count is illustrative; Peach's mapped count is 41 |
| Post-import | Step 3c requires another plan after adoption with `No changes`; submission item 3 explicitly requires that output immediately after migration |
| HCP evidence | Submission item 2 requires Apply finished from a push/merge, not a laptop run; a CLI speculative run is not this deliverable |
| Code evidence | Submission item 1 requires a commit/merged PR replacing the three lab templates and updating Makefile, README and the ADR |

The written material expects zero changes in the initial plan as well as a genuine
post-adoption no-change result. It does not state an exception for sensitivity
metadata or provide numerical grading weights. Therefore we cannot silently
reinterpret zero changes as zero AWS update calls or claim rubric compliance.
The current user-imposed strict zero-update requirement is also still binding.

## Consolidated recommendation: bounded initial-adoption exception

1. The project owner accepted the following *operational* exception on 2026-10-31:
   a single initial import run may contain the four verified metadata-only Update
   actions. This does not re-label the plan as zero-change or waive the written
   rubric. Keep the strict guard unchanged: it remains the default protection
   against every resource mutation.
2. Before an apply, a human must confirm all 41 correct import IDs; no creates,
   deletes or replacements; exactly the recorded four addresses and mark paths;
   full private before==after equality, fully known values, sensitivity only added
   rather than removed, unchanged identities, no other resource/output value
   mutation, no deferred/failed checks, pinned versions and documented approval.
   Do not accept this merely from an opaque/redacted plan or global ignore flag.
3. The submission should disclose the literal initial-plan count if it is shown.
   If an instructor requires the Step 3c numerical target literally, obtain their
   written confirmation before presenting the result as acceptable.
4. After this review, separately authorize retention deployment/verification,
   writer freeze, CFN detachment and HCP VCS-based adoption using a fresh reviewed
   plan. Its effective private values must match the verified authoritative values;
   CLI run-only overrides do not certify the stored HCP workspace inputs used by
   a VCS run. Keep the reviewed effective adoption gate true for authorized
   adoption/verification while retaining false in source. Speculative plans cannot
   be applied. Do not reuse this old speculative result as the reviewed adoption
   run. The current task authorizes none of this.
5. The approved adoption would persist the four sensitivity-path changes together
   with the imports. Refresh reapplies prior marks (core lines 718-725); the same
   configuration, private inputs, provider versions and approved effective gate
   should then plan NoOp for these resources. Require a fresh full
   post-adoption plan, zero imports and zero resource/output changes, with the
   existing --mode clean guard. This is an expectation from source, not an observed
   result: no adoption or post-import plan has occurred.
6. Save the genuine No changes output for submission. Remove completed import
   blocks and original templates only after successful adoption/preservation
   verification. Complete the separately reviewed VCS apply screenshot and other
   assignment steps; neither synthetic tests nor a preview substitutes for them.

If no exception is approved, live migration remains blocked. Continue only local
review and instructor clarification; do not sacrifice secret handling to force a
numerical zero. No new IAM or private-input correction is indicated by this evidence.

## Scripts, documentation and tests

scripts/terraform-review-plan.py retains its original strict adopt/clean behavior.
The hardened helper labels metadata-only updates diagnostically but keeps their
Update counts and rejects the zero-update acceptance check. No accepting mode or
exception flag was added. Synthetic regressions prove both gates still reject the
four metadata-only Update actions and that a genuine future no-op-shaped plan can
pass clean mode once marks already match. They do not execute adoption or prove a
live post-adoption result. Any exception gate implementation remains pending approval.

## Local validation of this assessment

No configuration-only fix is applied because none was justified. Only evidence,
runbook/ADR/status corrections and strict-gate regressions were added. The full
script suite passes 285 tests and 63 subtests; migration/helper subset passes
70 tests. Terraform fmt/validate and six mock scenarios pass. Ruff lint/format,
actionlint, cfn-lint on all three original templates and whitespace checks pass.
These tests do not adopt resources or supply the required live clean-plan artifact.
The strict review script, source defaults, secret flags, resource HCL and corrected
62-file archive remain unchanged by this investigation.
