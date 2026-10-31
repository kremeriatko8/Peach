# Lab 7: CloudFormation to Terraform handover

## Current status

The third CLI speculative run completed with 41 imports and four sensitivity-only
metadata updates; full private plan values are equal. HCP authentication and
read-only provider access work. No Terraform state has been adopted. Original
CFN templates remain, and retention must be reverified before any future handover
(the October 27 inventory recorded only two protected declarations).

The course text literally expects zero changes in the initial import plan as well
as a post-adoption `No changes` plan. The project owner has accepted the four
documented, state-metadata-only updates as a narrowly bounded *initial-adoption*
exception. This is not represented as zero changes and is not an interpretation
of the rubric. The post-adoption plan remains an unconditional `No changes`
requirement. See the [sensitivity/core and assignment assessment](terraform-sensitivity-metadata-review.md)
and the [operator handover](terraform-adoption-handover.md). Steps below are
future separately authorized operations, not permission to execute.

## Local checks

With Terraform on PATH:

```sh
make infra-fmt
make infra-validate
backend/.venv/bin/python -m pytest scripts/tests -q
```

`infra-validate` copies HCL and the lockfile into a temporary directory, initializes
with `-backend=false -input=false -lockfile=readonly`, validates the complete configuration with import blocks present, then quarantines
only the temporary imports file and runs only
`command = plan` tests with a mocked AWS provider. It separately validates all 31 public tfvars against the observation with
synthetic missing inputs and the adoption gate false. It downloads public providers
when uncached but does not configure AWS or contact HCP Terraform. No existing
`.terraform`, state, private inputs or credentials are copied. The check can need
permission to start the provider's local communication socket in a restricted
sandbox. Never solve this by enabling a real plan/apply.

The dedicated PR/manual Terraform workflow is credential-free. Existing backend
CI remains intact, including CFN checks while the source templates are retained.
The ordinary `make test` application suites are separate; this migration does not
require a production database, inference or an email to validate locally.

All managed resources have `prevent_destroy` and a precondition requiring
`adoption_inventory_complete`. Its default is false. This deliberately blocks
adoption plans until a human reviews the real inventory. It does not substitute
for reviewing the full plan, and removing a resource's HCL also removes its
lifecycle protection. Protect the workspace, Git branch and state access too.

## Inputs and secrets

All 31 observed non-secret inputs now appear in committed-intended
`terraform.tfvars`; no commit has occurred. They come from the public inventory
worksheet, including the enabled parser/schedule and distinct image digests.
Seven required inputs remain deliberately absent: Google ID/secret, DB URL,
report owner/sender/recipient and the exact public JWKS string. Follow
[the HCP input matrix](terraform-hcp-setup.md) for protected provisioning. The
adoption gate stays false. No input value should be inferred from CFN defaults.

Capture the existing parser role name, all Lambda permission statement IDs, S3
notification ID, Cognito email schema constraints, JWKS, architecture, immutable
image digests, network IDs, pricing strings and report settings. If the deployed
resources differ from the source templates, reconcile HCL before migration. Check
whether builder and mailer actually use the same image digest; otherwise split
the reporting image input before adoption. Preserve numeric environment string
formatting as well as values if the live plan detects a difference.

Put Google client secret, database_url, report_owner_sub, report_from_email and
report_recipient_email in sensitive **Terraform** workspace variables. Their
Terraform declarations are sensitive. Do not use `TF_VAR_*` on a machine with shell
tracing/history capture. Sensitive hides normal display, not state/plan contents.
No secret output is defined. State and plan JSON may still contain all of these
values; restrict workspace state access, private evidence and downloaded backups.
The DB URL also remains in the existing builder Lambda environment by design.
The Google secret remains in Cognito provider configuration and wherever it was
previously provisioned; migration does not rotate/delete it.

Keep private inventories, exported plans, handover evidence and any secret inputs
under ignored `infra/migration-private/`, with directory mode 0700 and file mode
0600. `.terraform`, state, plans, override files and auto tfvars are ignored.
Only non-secret reviewed configuration belongs in Git. No local state is created
by the local validation path. A separate bootstrap state, if needed later, is
also sensitive and must not be committed.

## Application integration and cutover

During preparation `PEACH_INFRA_SOURCE` defaults to `cloudformation`, preserving
existing auth/report lookups. Setting it to `terraform` explicitly enables the
new named public-output reader. Any other value fails; Terraform lookup failure
never falls back to CFN. Frontend builds also read the Terraform parser URL
after cutover; the HCP token is unset before dependency/image builds. The auth compatibility object retains the former output
keys for the existing public Cognito/JWKS configuration code. Individual outputs
also support `terraform -chdir=infra output -raw cognito_client_id`, `parser_url`,
`report_queue_url`, etc. Never read the full state/output set just to build UI config.

After verified adoption, set PEACH_INFRA_SOURCE=terraform consistently in local
release environments and the GitHub repository variable. The backend workflow's
Terraform setup/backend-init steps activate only for that repository value. It
needs TF_CLOUD_ORGANIZATION, TF_WORKSPACE and a secret PEACH_TF_OUTPUTS_TOKEN with
custom Read outputs only access to the intended workspace where available. The
built-in Read role includes complete state access and is broader; restrict who
can administer or use the token. It has no apply authorization.
The token is for HCP output access; AWS OIDC remains the application deployment
credential. Credentials are never embedded in HCL or backend command arguments.
Configure and verify this access during the separately approved live phase,
**before detaching CFN**, and freeze deployments during the short ownership gap.

`deploy-auth` and `ai-prepare-deploy` are deprecated Make aliases for infra-plan;
their old shell entry points stop with guidance instead of mutating AWS. The
historical agenda release driver refuses Terraform mode. Offline reports-prepare
and CFN/IAM historical tests remain available for retention handover; their
parameter artifacts are not Terraform inputs and must not be deployed after
cutover. Backend, migrations, frontend, budget and GitHub role CFN targets remain
outside the lab's three-stack migration.

Terraform owns the parser/reporting function images and entire environments.
GitHub Actions continues deploying the API through its existing guarded backend
CFN path. Do not add Lambda image/environment ignore_changes to mask competing
writers. Promote a new reporting/parser digest with a reviewed HCP change; API
releases do not automatically promote it. Terraform does not build or publish images.

For changes requiring both roads: publish compatible code/image first when the
new infrastructure references its digest; apply additive infrastructure/config
before deploying code that requires it. Use expand/contract releases where either
order alone would break compatibility. Do not run both writers concurrently or
remove old configuration until consumers have migrated.

## Approved live phase: ordered runbook (NOT EXECUTED)

1. Confirm the account, region, actual stack names and a stable release window.
   Capture deployed templates, parameters, outputs, physical IDs and current
   settings. Check external exports/imports and dependents, shared endpoint routes,
   Cognito users/client/domain, report objects/dedup state and queue/message counts.
   Back up configuration and state/evidence privately. No account or report is
   deleted for migration. Finish HCL reconciliation against this inventory.
2. Configure one HCP project workspace, Remote execution, working directory
   `infra`, and reviewed VCS repository/branch. Keep auto-apply off during adoption;
   queue no apply until all IDs and retention are verified. Set
   TF_CLOUD_ORGANIZATION/TF_WORKSPACE for CLI access without guessing organization
   names. Configure the same selected workspace in HCP and CI/local environments.
3. Reuse or separately bootstrap the HCP AWS OIDC provider/role. Use
   TFC_AWS_PROVIDER_AUTH=true and TFC_AWS_RUN_ROLE_ARN. Narrow trust to
   `organization:<org>:project:<project>:workspace:<workspace>:run_phase:*`, with
   `app.terraform.io:aud = aws.workload.identity`; scope permissions to inventory
   resources and required IAM pass-role/control actions. Do not import the bootstrap
   into the project state or grant arbitrary org workspaces production access.
   A plan role should be read-only; an apply role needs reviewed service mutations.
   Keep this separate from GitHub's application role and external parser boundary.
4. Review the already prepared 41 observed-ID import blocks and provisioned
   inputs. Run `python3 scripts/terraform-imports.py docs/terraform-live-import-inventory.json --check`
   offline. Google federation was observed present; do not omit it. Complete the
   PR-only speculative preview using [the dedicated instructions](terraform-first-preview.md)
   before ownership transfer. The versioned gate stays false; any temporary HCP
   override requires separate approval. Do not grant apply or detach resources
   merely because a speculative plan passed. Stop competing deployment writers
   before the later retention/detachment/import handover.
5. Review/deploy only the retention changes to the existing CFN stacks, preserving
   their current parameters and secrets. Retrieve the resulting deployed templates
   and verify both Retain policies on every actual resource. Review events and
   dependencies. Do not use retired deploy-auth/deploy-ai scripts or the backend
   application deployment for this operation. The exact live change sets still
   need preparation and approval; no generic deletion script is supplied.
6. Detach/delete only the three approved CFN stack containers with retention in
   effect. Wait for completion, verify every retained resource still exists and
   works, and stop if any discrepancy appears. Do not detach backend/database/site,
   budget, migration, GitHub OIDC or bootstrap resources. No Terraform apply while
   CloudFormation still owns these objects.
7. Run and review the full HCP import plan. The rubric target is 41 imports and
   **zero adds/changes/destroys**. Outputs may be new. The only project-approved
   exception is the four exact metadata-only Update actions documented in the
   handover; it must be proven from a full private plan, not inferred from redacted
   output. Privately export its plan JSON and run the strict
   `python3 scripts/terraform-review-plan.py <plan.json> --mode adopt` first.
   It intentionally rejects every Update, including this exception. Do not apply
   unless the separate human review confirms the exact exception evidence. Never
   publish raw plan JSON. All other resource differences, deferred actions and
   replacement proposals block the apply. Reconcile HCL to reality. No
   permission/notification recreation is currently necessary or approved, despite
   the assignment allowing exceptions.
8. A human approves the exact HCP import run after merge/review; HCP performs the
   apply. If it fails partway, preserve state and inspect the run. Imported objects
   remain in AWS; finish importing only the remaining objects after reconciling the
   actual state. Never delete/recreate or blindly retry a partially failed change.
9. Immediately run another full plan, require no changes, run the offline guard
   with `--mode clean`, and save the human-readable no-change output. Verify IDs,
   existing accounts/reports/messages/config and application behavior. Turn on the
   explicit application output cutover and verify backend/frontend/report lookups.
10. Remove imports.tf, any generated.tf and the three old templates only after
    successful handover. Migrate the retained CFN-specific tests, IAM preparation
    tools, README sections and CI lint references before that removal, using the
    Terraform tests/inventory as the new contract. Archive historical evidence with
    clear provenance; do not make the final repository depend on deleted templates.
11. Prove VCS execution with a small reviewed tag/log-retention PR. Review its HCP
    plan, merge it, approve HCP apply, and capture **Apply finished** with workspace,
    VCS commit/source and run visible. Make sure unrelated application deployments
    are safe to run: every main push currently triggers backend deployment.
12. Demonstrate drift with one separately approved reversible parser setting in
    the console, run HCP Plan only, inspect it, and restore via reviewed HCP apply.
    A real emergency fix must become reviewed HCL before the next apply, or the
    configuration will undo it. Recheck a clean final plan.

## Submission and discussion preparation

Submit the final commit/merged PR link, a VCS-triggered project HCP **Apply finished**
screenshot, and the immediate post-migration no-change plan output. Include README,
Makefile, Terraform/lockfile, and the reviewed ADR in the commit. Do not claim the
local mock plans are live evidence. No lab-7 screenshot/clean-plan evidence exists yet.

Be ready to explain actual import/recreation counts, force-replacement attributes
(pool username/schema choices and bucket name), state locking/recovery and why
state in Git leaks secrets and lacks live locking. State loss loses identity
mapping, not AWS resources: restore the correct workspace state version or rebuild
imports under review. A partially failed apply leaves real partial changes recorded
in state; reconcile rather than assuming automatic rollback. For HCP outages, wait;
never create a parallel local backend. For a staging/white-label environment, use
separate state/workspace and reviewed variables/account, shared configuration, and
no autonomous apply. Untracked resources should be deliberately adopted, left
external with documented ownership, or retired only after dependency review.
