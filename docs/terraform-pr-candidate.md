# Proposed PR: Prepare Peach Terraform adoption preview

This is a local description draft, not an opened PR.

Peach's authentication, reporting and parser resources are currently owned by
three CloudFormation stacks. This candidate prepares adoption of the existing
resources through HCP Terraform without changing their names or behavior. It
contains 41 observed-ID import blocks; the versioned adoption gate remains false.

The Terraform configuration preserves deployed images, queue sizes, Google
federation, event wiring, database/network inputs, and enabled schedule/parser
settings. The preview scope includes public outputs/read helpers, retention-only source-template
preparation, the ADR and handover runbook. Application release integration is held
for the separately approved later cutover. The
original templates remain until a separately approved live handover succeeds.

Offline checks audit all IDs against the recorded AWS reads and declarations,
validate full HCL with imports, then exclude imports only from a temporary copy
for mock tests. The dedicated PR workflow receives no AWS identity. Actual
provider authentication, a 41-import/no-mutation HCP plan, and cloud preservation
remain live checks, not claims established by these tests.

Publishing/opening this PR requires separate approval because HCP may automatically
start a speculative plan. Keep it unmerged: every main push triggers backend
deployment. Follow [the first-preview instructions](terraform-first-preview.md)
for the temporary workspace gate override and plan acceptance criteria. No apply,
CFN retention deployment/detachment, state import, or model/image update is part
of preview approval.

Validation results and remaining risks are recorded in
[the local validation report](terraform-local-validation.md) and
[readiness assessment](terraform-migration-readiness.md). No state, plan export,
credential files or secret input values belong in this PR.

The dedicated `feat/terraform-migration-preview` branch is based on fetched main
`0dad65c2608b851c035531239f9d6712783470be`. Its 45 changed/new files contain
only migration preparation. The original dirty feature checkout is preserved.
See [the candidate review](terraform-pr-review.md).
