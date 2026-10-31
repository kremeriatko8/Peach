# ADR 0007: Adopt existing Lab 4–6 infrastructure with Terraform

Date: 2026-10-27
Status: Proposed; local implementation prepared, live adoption pending approval

## Context

Peach's Cognito, weekly reporting and agenda parser infrastructure currently use
three CloudFormation stacks. Their resources include existing user accounts,
reports, queued work and deduplication state. Recreating them would lose data or
break application identifiers. Several release scripts consume their stack
outputs. Lab 7 requires Terraform, centralized state, VCS-driven HCP execution and
a verified migration without resource replacement.

## Decision

Use one Terraform root module under infra/ and one HCP workspace for the existing
environment, selected using reviewed organization/workspace configuration. Keep
backend/Aurora/network, migration runner, site, budget and GitHub OIDC ownership
unchanged. Terraform manages the three lab stacks' retained resources, including
embedded IAM/S3 configuration as separate Terraform objects. All 41 candidate
objects support imports in the pinned AWS provider; actual IDs and the conditional
Google provider remain subject to live inventory. No recreation is planned.

A human reviews the complete mapping and plan, deploys/verifies Retain policies,
then authorizes detachment of only the three CFN stack containers. HCP imports
retained objects with zero adds/updates/deletes. Lifecycle destruction protection,
account restriction, a default-false adoption gate and an offline plan guard
reinforce the review. A clean full plan and resource/data checks establish success;
local validation cannot establish live parity.

Contributors propose HCL changes in Git. Reviewers inspect HCP's full plan and
approve the merged VCS run; HCP uses short-lived AWS credentials with trust narrowed
to the selected organization/project/workspace. No Make target performs apply.
The bootstrap identity infrastructure requires separate authorized ownership and
state. GitHub Actions retains application deployment ownership; Terraform owns
parser/reporting image digests and full environments to avoid competing writers.

## Alternatives

- Keep CloudFormation: fewer state responsibilities and AWS rollback, but does
  not satisfy this lab's HCP workflow or provide the same provider/workspace model.
- CDK: programming-language abstractions, but its usual CFN backend retains the
  same stack ownership model and does not meet this Terraform migration requirement.
- OpenTofu: an open-source fork with similar configuration; appropriate to consider
  independently, but this submission uses the requested Terraform/HCP path and its
  provider-backed validation. Do not assume interchangeable HCP execution support.
- Delete and rebuild: rejected because users, reports and stable IDs must survive.
- Migrate every stack or add new dev/stage resources now: rejected as unrelated
  scope that increases cost and migration risk. Future environments get separate
  state/workspaces, not different variables applied to this environment's state.

## Consequences

HCP stores and locks the shared state and keeps state history. Workspace variables
hold sensitive inputs; sensitive=true redacts display but does not encrypt values
within state/plan content. Secrets also remain in the services consuming them,
such as the Cognito identity provider and builder Lambda environment. Restrict
workspace/state/plan access, output-read tokens, backup files and logs; never commit
state, plans or credentials. Only public allowlisted outputs reach frontend builds.
CI's output reader may require state-read permission, which exposes more than the
public output names; treat its HCP token as sensitive even though the helper prints
only allowlisted public fields. AWS OIDC credentials and this HCP token serve
separate purposes.

If HCP is down, pause infrastructure changes and preserve the last known deployment.
Do not bypass locking with a new local backend or let two systems own the same
resources. A genuine break-glass action requires explicit incident approval,
exclusive access, recorded changes and later HCL/state reconciliation. Restore
state from the correct HCP version after state loss; existing AWS resources are
not recreated just because their state mapping was lost.

Terraform has no automatic rollback. A failed apply requires inspecting actual
resources and recorded state, correcting configuration, then reviewing a new plan.
A console emergency fix must become HCL before the next apply to survive drift
reconciliation. A change requiring code and infrastructure uses compatible staged
releases: publish referenced artifacts first, provision additive settings before
code that requires them, and remove old paths only after consumers migrate.

During local preparation, CFN output lookups remain the default. The explicit
Terraform cutover, HCP access setup, retention deployment, detachment/import,
VCS proof, drift exercise and final template removal are all pending live approval.

## 2026-10-31 initial-adoption exception and remaining control

Terraform 1.13.5 classifies newly propagated sensitivity paths as Update even
when imported values match. The third preview proves four such transitions; core
skips provider update calls for them but would persist state metadata. The project
owner accepts those four exact, verified transitions for the one initial adoption
run. This decision does not claim that the written rubric says zero changes: it
does not. It neither unmarks secrets nor changes the default-false adoption gate,
and it does not authorize a state operation by itself. A human must still review
the fresh HCP VCS run and authorize retention, detachment and apply separately.
The immediate post-adoption plan must be genuinely `No changes`; otherwise the
handover fails. See [the detailed assessment](../terraform-sensitivity-metadata-review.md)
and [operator handover](../terraform-adoption-handover.md).
