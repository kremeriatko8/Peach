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

## Publication CI portability correction

The first GitHub Linux validation run downloaded the signed AWS 6.70.0 provider,
but validation failed because the readonly lockfile contained only the Mac h1
package hash. Generated the additional linux_amd64 h1 hash with Terraform's
`providers lock -platform=linux_amd64` in an isolated temporary directory.
Terraform verified the package as signed by HashiCorp. The correction adds one
platform hash; provider version, existing hashes, gate and infrastructure source
are unchanged. No plan, backend initialization or cloud operation was used.

## Post-preview local remediation

After run-KkT61Sro17vKC8Dd failed, removed only the proven create-only
generate_secret import mismatch. All protection gates remain intact. Prepared
a two-action read-policy supplement and sanitized evidence for the 29 evaluated
and 12 unevaluated imports. Google secret and opaque mailer-policy differences
remain unresolved; no ignore_changes or IAM runtime-policy changes were made.

Checks: Terraform fmt/validate and 6 mocked tests passed; 256 script tests and
63 subtests passed, including 41 migration tests. Migration Ruff lint/format,
actionlint, three-template cfn-lint, shell syntax and whitespace checks passed.
No second real plan, commit, push, HCP variable edit or cloud mutation occurred.
See [the remediation report](terraform-preview-remediation.md).

## Corrected preview preparation follow-up

Selected the same two read actions scoped to all three unqualified migration
Lambda functions and regional EC2 metadata. Added parser coverage to the permission
regression test. Repeated checks passed: 256 script tests/63 subtests, 6 Terraform
mock tests, fmt/validate, migration lint/format, actionlint and three-template
cfn-lint. Live mailer policy was read using the existing reporting profile and
matches the imported policy. HCP sensitive inputs are unreadable by design; only
input availability/equality booleans were reported. The original local Google
secret matches deployed AWS in memory. A corrected private 62-file infrastructure
archive is initialized; no real plan or workspace variable update was performed.

## Second-preview diagnosis and private-input guard

Added the minimum pool-scoped ListUserPoolClients statement and a read-only-default
helper for authoritative run-specific private inputs. Its live default-mode
checks passed: all five values load in memory, SES policy/environment agree,
archive and HCP safety checks pass. No real plan ran. New mocked tests and
complete scripts suite passed (264 tests, 63 subtests); Terraform validation and
6 mock scenarios passed. Migration CI now includes the new helper tests. The
corrected 62-file upload archive remains unchanged. See the consolidated diagnosis.

## Secret-output and crash boundary hardening

Removed raw subprocess output inheritance. Added memory-only capture and parsing,
strict output schema, quiet argument failures, core-dump suppression and mandatory
OS write denial for the parent/helper and descendants. Only /dev/null is writable.
Read-only live probes pass inside this boundary, including authoritative AWS
inputs, Remote HCP workspace and pinned Terraform/configuration discovery.
Full script suite: 280 passed and 63 subtests; the additional quiet-argument test
passes in the 25-test security/helper suite. Terraform validation and 6 mock tests,
migration tests, Ruff, actionlint, CFN checks and secret/whitespace checks pass.
No synthetic private marker is emitted or written by the denied-crash test.

Final hardening/metadata regression results: 282 script tests and 63 subtests
passed, including 26 helper security tests. Third plan executed once; no raw
artifacts were written. Result: 41 imports, four sensitivity-only updates, zero
adds/replacements/deletes and no diagnostics. All four full before/after objects
are equal and all private inputs match AWS. Strict zero-update guard rejects it;
no apply/retry/state write followed. Original branch and archive remain unchanged.

## Sensitivity/rubric assessment (2026-10-29)

Reviewed pinned core import/plan/apply/state encoding, provider schema flags, full
private third-plan evidence and original assignment text. The assignment expects
initial zero changes and a genuine post-adoption No changes plan. The project owner
accepts the four verified metadata-only initial updates as an operational exception,
without describing the initial plan as zero-change or weakening the strict guard.
The post-adoption plan remains required to be genuinely clean. Three synthetic
regressions prove adopt/clean still reject metadata-only updates; a synthetic
stable-mark no-op plan passes clean. Full scripts: 285 passed, 63 subtests;
migration/helper: 70 passed; Terraform fmt/validate and 6 mocks passed; Ruff,
actionlint, three-template cfn-lint and whitespace checks passed. No new plan,
state operation, cloud write or publication occurred. See
terraform-sensitivity-metadata-review.md and terraform-adoption-handover.md.
