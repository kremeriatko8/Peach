# Lab 7 local validation record

Date: 2026-10-28 (Europe/Kyiv). Dedicated branch:
`feat/terraform-migration-preview`, separate worktree
`/private/tmp/peach-terraform-migration-preview-20261028`.
Base: fetched origin/main `0dad65c2608b851c035531239f9d6712783470be`.

## Fresh-base transfer

The remote main advanced from cached `fb23fec` and now includes the Lab 6 PR.
The isolated migration patch was applied without staging or committing. Three
expected overlaps were resolved narrowly: Makefile migration targets, AI template
Retain policies, and retirement of the AI deployment entry point. All application
code, database migrations and deferred release/deployment files match fresh main.
Exactly **45 changed/new files** match the migration publication allowlist.
The original branch, HEAD, index, dirty status and fingerprinted local files,
including local environment files, were verified unchanged.

## Validation on the dedicated branch

| Check | Result |
| --- | --- |
| Offline declaration/import/recorded-ID audit | 41/41 passed |
| Terraform 1.13.5 fmt and AWS provider 6.70.0 validate with imports | Passed |
| Isolated mock resource scenarios | 5 passed |
| Exact public-input/gate mock scenario | 1 passed; 31 inputs, gate false |
| Complete scripts/tests suite | 253 passed, 63 subtests passed |
| Migration safety subset | 38 passed |
| Ruff lint/format on five changed/new Python files | Passed |
| Backend CI Ruff lint/format from backend directory | Passed; 67 files formatted |
| GitHub Actions actionlint | Passed |
| cfn-lint: auth.yaml, reports.yaml, ai.yml | Passed |
| Shell syntax on migration shell scripts | Passed |
| Whitespace / publication allowlist / original preservation | Passed |
| Secret/generated-file review of additions and new files | No findings |

The suite count differs from the earlier dirty-checkout run (254) because the
candidate deliberately retains main's deployment tests rather than later-cutover
edits. Mock tests invoke no cloud services. Full HCL is validated with imports;
only a temporary copy excludes import blocks for mocked tests. Backend init is
disabled and ambient AWS credential sources are cleared. A sandbox-only provider
socket restriction required rerunning these local checks outside that restriction.
The cached, previously verified provider and unchanged readonly lockfile were used.

An exploratory whole-script lint using ambient parent configuration found existing
issues in unchanged main files. Those unrelated files were left untouched; migration
Python files pass the same ambient lint and formatting checks. Application/frontend
integration tests were not repeated because their sources are identical to main.

No real Terraform plan, import, apply, destroy, remote state operation, AWS/HCP API
operation, commit, push, merge, PR or deployment occurred. Only the authorized fetch,
local branch/worktree creation and local source edits/checks were performed.
Both adoption gate defaults remain false. Runtime OIDC permissions, effective HCP
variables/speculative settings and a drift-free adoption plan remain unverified.

## Next approval

Approve commit, feature-branch publication and PR creation, including the speculative
HCP plan this can trigger. Separately authorize the temporary HCP workspace-only
gate override. Keep main unmodified and the PR unmerged. Follow
[the first-preview instructions](terraform-first-preview.md); require exactly 41
imports and zero adds/changes/destroys before considering retention and detachment.
