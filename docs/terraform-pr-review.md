# Local Terraform PR candidate review

Date: 2026-10-28. Scope: local source and isolated preview preparation only.
No commit, push, PR, live AWS/HCP read/write, Terraform apply/import/state
operation or real migration plan occurred. A read-only remote fetch and a separate
local branch/worktree were authorized and completed.

## Publication scope finding

Fetched origin/main is `0dad65c2608b851c035531239f9d6712783470be`, advanced from
the patch's cached base `fb23fecdd165911fe8373fe3fc452c0ccb255030`. Main now
contains the merged Lab 6 PR. The dedicated local branch is
`feat/terraform-migration-preview`, in
`/private/tmp/peach-terraform-migration-preview-20261028`.

The original `feat/paste-agenda` checkout, index and uncommitted files are
preserved. The isolated patch was transferred without staging or committing.
Three overlaps were reconciled: Makefile retains main's application commands and
adds migration targets; infra/ai.yml adds only Retain policies; deploy-ai.sh becomes
a fail-closed retired entry point. Application code, database migrations and
existing backend/frontend deployment workflows/scripts remain identical to main.

The candidate contains exactly 45 changed/new migration files. Release/output
integration changes from the original dirty checkout are held for later cutover.

## Risk review

| Area | Local result and remaining limit |
| --- | --- |
| Scope | Exactly 41 declared Terraform resources, 41 static import destinations and 41 recorded IDs agree; wrong object IDs are rejected by both source audit and adoption-plan guard |
| Default creation | No active apply/plan has run. Default adoption gate stays false. Missing imports/objects or a create action must block the preview; lifecycle prevent_destroy alone does not prevent creation |
| Replacement/destruction | All managed resources retain prevent_destroy; stable names, pool/domain/client IDs, bucket name and role names match the recorded configuration. Actual provider replacement decisions are unverified until a real speculative plan |
| Existing behavior | No resource definition, image, queue limit, Google details, parser flag, schedule, event wiring, IAM policy, DB/network input, source CFN template or provider lockfile changed from local phase entry; only workspace binding/import/audit/test/docs preparation changed |
| IAM/KMS | User reports the scoped read role is attached/configured. Current credentials cannot independently read the new role; its real provider permissions and remaining KMS/builder dependency reads must be checked through approved access/planning. No broader policy was added/requested |
| Source/state separation | Static validation includes real import blocks. Mock tests exclude imports only from an isolated temporary copy and disable ambient AWS identity sources. Imported IDs are not state; no remote state has been written |
| CI | Same-repository feature PR to main can generate HCP speculative planning when enabled. Candidate PR checks are read-only/static. Backend deploy is push-main/manual; cleanup manual. No change to main or manual dispatch is approved |
| Secrets | No secret inputs, environment files, provider directories, state or plan exports belong in the publication patch. State/plan JSON may contain private values later and must stay out of Git/chat |
| Inventory age | IDs/settings were observed October 27. A zero-mutation real preview and refreshed checks are still needed; no local test establishes live drift-free adoption |
| Ownership | CFN retains ownership. Only 2/31 had both live Retain policies at last observation. Retention deployment/verification, detachment and a fresh HCP import apply require separate authorization |

## Readiness decision

The dedicated branch is ready for commit/publication review after the recorded
local checks. It is not ready for ownership transfer or apply. Original working
branch changes must not be bundled into this candidate.

The next step requires separate approval for a commit, feature-branch push and PR,
and the automatic speculative HCP plan publication may trigger. The temporary
HCP gate override also requires approval; versioned gate values remain false.
See [first-preview instructions](terraform-first-preview.md).

Validation evidence is in [the local validation record](terraform-local-validation.md).
