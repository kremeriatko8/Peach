# Peach migration: first speculative preview

Status: updated 2026-10-29. PR #2 is published as a draft; subsequent local
remediation/security changes remain uncommitted. Three CLI speculative runs have
occurred. The latest has 41 imports and four sensitivity-only metadata updates,
no value differences or diagnostic errors. No adoption/state write has occurred.
The repository/default adoption gate remains false and all 41 protections remain.
The project owner accepts the four verified sensitivity-metadata-only Updates for
the initial adoption run. This does not call the preview zero-change or alter the
written rubric; the first post-adoption plan must still be genuinely `No changes`.
See the [core/rubric assessment](terraform-sensitivity-metadata-review.md) and
[operator handover](terraform-adoption-handover.md). The procedures below describe
separately authorized future preview/publication work.

## Candidate contents and review

- `infra/imports.tf` contains all 41 provider-format IDs from the October 27
  recorded inventory. The offline audit independently reconstructs the IDs from
  the filtered AWS snapshot and checks every destination against the HCL resource
  declarations. It rejects missing/duplicate addresses, wrong IDs, account/region
  mismatches and extra configuration in the import file.
- The root module binds explicitly to organization `ooad-kremeriatko8`, workspace
  `peach-dev`. The reported HCP project is `Default Project`. These are user-confirmed
  settings, not a new remote configuration or independently verified HCP access.
- All existing names, image digests, queue sizes, Google details, enabled schedule,
  enabled parser, IAM policies, networking and database inputs are preserved.
  No model, rate, image, log-retention or tag change is bundled into adoption.
- Resource lifecycle guards remain. Neither the HCL variable default nor
  `infra/terraform.tfvars` enables `adoption_inventory_complete`.
- Existing CloudFormation templates remain with the previously prepared, undeployed
  retention policies. This preparation did not change them. Backend/Aurora/site,
  migration runner, budget and bootstrap identity remain outside the import root.
- The original preparation inventory remains a null-ID scope baseline. The observed
  inventory and snapshot are retained separately for reproducibility. Recorded
  reads are not a guarantee that today's cloud has not changed.

Run `make infra-validate` with Terraform 1.13.5 on PATH. It audits IDs, initializes
an isolated directory with backend disabled, and validates the full source with
all import blocks present. It then quarantines **only the temporary import file**
for plan-only mock tests; the real repository import file is unchanged. Ambient
AWS credentials/profile/container/web-identity sources are disabled in this child
process. A second mocked test checks all 31 real public inputs against the recorded
worksheet, supplies synthetic missing inputs, and expects the adoption gate to block
planning. No real HCP secret values are used in local tests.

## Branch-history finding and isolated publication scope

The isolated patch is now transferred to `feat/terraform-migration-preview` in
`/private/tmp/peach-terraform-migration-preview-20261028`, based on fetched main
`0dad65c2608b851c035531239f9d6712783470be`. Main now includes Lab 6; this
branch adds only the 45 migration files. Application/deployment source matches
main. Original dirty `feat/paste-agenda` work is preserved in its original checkout.
See [the candidate review](terraform-pr-review.md).

## Publication and preview: separate approval required

1. Review the complete candidate locally, including untracked source/docs, rather
   than staging only `infra/`. The audit/tests require the scripts, baseline and
   observed inventories, filtered snapshot, public-input worksheet and lockfile.
   Exclude `.env*`, credentials, `.terraform/`, state, plan JSON/binaries, generated
   private artifacts and ignored `reports-local/` content. No secret variable value
   belongs in the PR description or source. Use the reviewed isolated preview scope; it holds release integration edits
   for later and adds no unrelated application changes. Do not bundle unrelated edits.
2. Before publication, obtain explicit approval for the feature-branch commit/push,
   opening a PR, and the automatic **speculative HCP plan** this can trigger.
   Use the prepared dedicated branch `feat/terraform-migration-preview` in its
   separate worktree. Confirm origin/main has not advanced before publication.
   Review the eventual PR commit range as well as its working-tree diff so unrelated
   branch history is not accidentally included. Do not push or merge into main.
3. In HCP, manually confirm automatic speculative plans are enabled and the VCS
   target is `main` with working directory `infra`, Terraform 1.13.5, Remote mode
   and auto-apply disabled. Confirm the corrected environment variable:
   `TFC_AWS_RUN_ROLE_ARN=arn:aws:iam::968053399627:role/peach-hcp-terraform-read`.
   The user reports the scoped policy, trust and seven inputs are configured and
   the DB URL comes from the deployed builder, not Docker; no values were re-read
   or copied here. Live authentication/read completeness is still untested.
4. After reviewing the exact 41-block candidate and authorizing preview, manually
   add a temporary **Terraform-category** workspace override:
   `adoption_inventory_complete = true`, with **HCL enabled** (a boolean, not a
   quoted string). Keep the versioned default/public tfvars false. Check that no
   priority variable set overrides the gate or other inputs. Do this only immediately
   before the approved preview; do not queue standard runs or approve pending applies.
   If the gate stays false, a preview should fail closed, not be mistaken for a
   provider/auth failure. HCP workspace Terraform variables override tfvars.
5. Push the approved feature branch and open an **unmerged PR targeting main**.
   HCP uses the PR candidate for a speculative run without changing its tracked
   branch. Feature-branch push alone does not update the main-connected workspace.
   In HCP, verify the run is **speculative/plan-only**, the SHA is the approved PR
   commit, and it uses the expected workspace. Do not use New run against main
   as a substitute: main has not received this candidate.
6. Read the complete plan. The rubric target is **41 to import, 0 to add,
   0 to change, 0 to destroy**. New public outputs are expected. The only approved
   deviation is the four exact sensitivity-metadata updates recorded in the
   assessment and operator handover; all must prove equal private values and no
   provider update path. Missing objects, any other update, replacement,
   destruction, unverified/deferred check or unexpected ID blocks progression. An
   IAM denial is a request to inspect the specific read permission, not grant
   writes/admin or hide a difference with ignore_changes. Keep the parser and
   weekly schedule enabled.
7. If exporting plan JSON for the offline guard, keep it private: it may include
   plaintext secrets even when console output is redacted. Only under separately
   approved secure handling, use ignored `infra/migration-private/` (0700 directory,
   0600 files), never Git or chat. The guard is:
   `python3 scripts/terraform-review-plan.py <private-plan.json> --mode adopt`.
   It checks exact recorded IDs and no managed mutations. An unverified plan format
   or provider normalization needs review; never bypass a failed check to apply.
8. After preview, restore/remove the temporary HCP gate override so the effective
   default is false until the next approved planning/handover window. This is a
   user-controlled HCP change, not performed locally. Keep the PR unmerged.

HCP does not apply speculative PR plans or import their objects into current state.
Creating/updating the PR can itself trigger a new speculative plan, so publication
approval includes that expected read-only run. The boolean gate is not an apply
lock: auto-apply disabled, speculative mode, read-only AWS permissions and human
control of HCP state/apply remain necessary safeguards.

## Verified repository workflow triggers

| Workflow | Triggers | Feature-branch PR behavior |
| --- | --- | --- |
| Deploy backend | push to main; workflow_dispatch | Does not run automatically for this PR |
| Clean up legacy tasks | workflow_dispatch; main-only job | Does not run automatically |
| Lint | push to main; pull_request | Lint/type checks |
| Terraform static checks | relevant-path pull_request; workflow_dispatch | Offline import audit, migration tests, validation and mock tests; contents:read only, no AWS identity |

Do not manually dispatch deployment/cleanup, merge the PR, or push directly to main.
A main push currently starts the backend deployment **even for documentation-only
changes**, independently of HCP auto-apply. These statements describe the checked-in
candidate workflows; other remote hooks/settings were not inspected. Automatic
HCP PR plans and remote repository permissions still require manual confirmation.

## Preview is not the ownership transfer

A read-only speculative import plan can inspect resources while CloudFormation
still owns them. It is **not** permission to apply that plan or delete a stack.
The later operations need separate approvals and a fresh plan:

1. Complete pending dependency/security checks and refresh the inventory.
2. Prepare/review retention-only CFN changes preserving deployed parameters; deploy
   and verify both Retain policies on every actual resource. Last observation had
   only 2 of 31 protected. Do not detach anything based on local YAML alone.
3. Coordinate/authorize a freeze of competing deploys before any main merge or
   stack detachment. Agree how the reviewed candidate reaches main/HCP without
   starting an unintended application release; the unmerged preview PR is not
   yet this release plan. HCP auto-apply stays off.
4. Detach only the three retained stack containers, verify every resource survives,
   re-enable the gate only for the reviewed handover, and require a fresh HCP
   standard import-only plan. A human separately approves its import apply.
5. Save the immediate no-change plan and verify stable IDs/accounts/reports/events.
   Cut output readers to Terraform only after verified state/outputs exist. Then
   remove temporary imports and original templates, update their remaining legacy
   checks/tools, and publish only with authorization.
6. Complete the later small reviewed VCS change and drift exercise. Capture the
   VCS-triggered Apply finished screenshot, final commit/merged PR link and clean
   plan output for the assignment. This preview satisfies none of those live
   completion claims by itself.

References: [HCP speculative run modes](https://docs.hashicorp.com/terraform/cloud-docs/workspaces/run/modes-and-options),
[VCS speculative-plan settings](https://docs.hashicorp.com/terraform/cloud-docs/workspaces/settings/vcs),
[HCP variable precedence](https://docs.hashicorp.com/terraform/cloud-docs/variables).
