# Peach Lab 7 adoption handover

This is the sole operator checklist for the live phase. It prepares no cloud
change and does not authorize one. It is based on the submitted assignment text,
the 2026-10-27 read-only inventory, and the successful 2026-10-31 CLI preview.

## Fixed facts and boundaries

- Scope is exactly the existing stacks `peach-auth` (5 CloudFormation
  declarations), `peach-reports` (20), and `peach-ai` (6): 31 declarations mapped
  to 41 importable Terraform objects. Run the offline audit below before every
  live window.
- `infra/imports.tf` has all 41 reviewed IDs, every managed object has
  `prevent_destroy`, and `adoption_inventory_complete = false` remains the
  committed default. There is no `ignore_changes` exception.
- The source templates already contain both Retain policies for all 31 declarations,
  but the last live snapshot recorded only 2/31 protected. Local YAML is not proof
  that live stacks are safe to delete.
- The accepted initial-plan exception is exactly four Terraform sensitivity-mark
  transitions: Google provider `provider_details.client_secret`, mailer policy,
  builder environment, and mailer environment. The plan is truthfully **41
  imports, 0 additions, 4 updates, 0 replacements, 0 destructions**. All attribute
  values were privately verified equal; Terraform core does not call the provider
  update path for these equal unmarked values. This is still not a literal
  zero-update plan.
- The required post-adoption plan has no exception: it must say `No changes`.

## Offline go/no-go checks

Run these in the migration worktree only. They make no cloud calls:

```sh
python3 scripts/terraform-imports.py docs/terraform-live-import-inventory.json --check
make infra-fmt
make infra-validate
backend/.venv/bin/python -m pytest scripts/tests -q
git diff --check
git status --short
```

**Go only if:** the audit reports 41, source gate is false, all validation passes,
and the reviewed diff contains only migration documents/configuration/tests.

## Manual live sequence (one controlled window)

1. **Publish, but do not merge, the reviewed migration changes.** Obtain approval
   to commit/push the current isolated branch and update draft PR #2. Confirm the
   diff does not contain application changes. The main branch must not receive the
   Terraform root yet.
2. **Repair/prove HCP VCS delivery before cutover.** Previous PR events produced
   zero HCP workspace runs despite the recorded workspace settings. In HCP, verify
   the GitHub App connection is active for `kremeriatko8/Peach`, branch `main`,
   working directory `infra`, path filter `infra/**`, Remote execution, automatic
   speculative plans enabled, and auto-apply disabled. If PR events still create
   no workspace check, reconnect the repository in HCP (manual workspace setting
   change) and cause one reviewed branch synchronization after approval. Do not
   use a CLI run as proof for the assignment's VCS-run evidence.
3. **Freeze competing writers.** Pause application infrastructure releases that
   can modify the three stacks/resources. Preserve the existing application data,
   queues, schedules, user pool, report bucket and state. Capture fresh stack
   parameters, outputs, exports/imports, physical IDs, resource settings, and
   resource/data counts privately. Stop if any ID/configuration differs from the
   recorded inventory.
4. **Deploy Retain-only updates, one stack at a time.** In CloudFormation Console,
   create a change set for each exact current stack template (`auth.yaml`,
   `reports.yaml`, `ai.yml`), retain existing parameters/secrets, and use the
   required IAM capability if CloudFormation requests it. Review it: no resource
   creation, replacement, deletion, parameter change, or application setting
   change is acceptable. Execute only the reviewed Retain-policy update, wait for
   `UPDATE_COMPLETE`, then retrieve the deployed template and verify both
   `DeletionPolicy: Retain` and `UpdateReplacePolicy: Retain` on every resource.
   A missing policy or unexpected change is a hard stop.
5. **Detach only the three stack containers.** Delete `peach-auth`, wait for
   `DELETE_COMPLETE`, verify its retained resources still exist and work; repeat
   serially for `peach-reports`, then `peach-ai`. This is the assignment-required
   detachment: deletion without first proving both policies would delete physical
   resources. Do not detach any other stack. Stop immediately on a failed delete,
   missing object, or changed identifier.
6. **Enable the gate only as a temporary workspace override.** After all three
   stacks are absent and resource checks pass, set HCP Terraform variable
   `adoption_inventory_complete` to boolean `true` for the reviewed adoption run.
   Do not edit the committed `terraform.tfvars`; restore the workspace override to
   `false` after the operation. Reconfirm all seven HCP inputs and the OIDC role.
7. **Merge PR #2 to start the VCS run.** This must be the source of the HCP run,
   with auto-apply still disabled. Inspect the full private plan before any apply:
   41 correct imports; 0 adds/replacements/destructions; only the four documented
   sensitivity metadata updates; no diagnostic errors/deferred checks. If anything
   differs, discard the run and stop. A CLI speculative run is not a substitute.
8. **Human-confirm the exact HCP run.** This is the first state-writing operation.
   Confirm & Apply only after the review in step 7. It imports the 41 existing
   resources and persists state/sensitivity metadata; it must not create, delete,
   replace, or provider-update AWS resources. Capture the VCS-sourced **Apply
   finished** screen required for submission.
9. **Immediately prove steady state.** Run a full HCP Plan-only or remote
   `terraform plan` against the same workspace. It must have zero imports and end
   `No changes. Your infrastructure matches the configuration.` Run the strict
   clean guard against a private plan JSON:

   ```sh
   python3 scripts/terraform-review-plan.py /secure/private/post-adoption.json --mode clean
   ```

   Never commit the JSON. This is the required submission artifact, not the
   earlier preview.
10. **Clean source only after success.** With the clean evidence retained, remove
    `imports.tf`, any `generated.tf`, and `auth.yaml`, `reports.yaml`, `ai.yml` in
    a reviewed cleanup commit. Update tests/CI/docs that still require those
    templates. Confirm its HCP plan is clean. Do not delete evidence or HCP state.
11. **Complete the later rubric exercises separately.** Make one small reviewed
    Terraform change through a PR/VCS HCP run, and perform the authorized parser
    timeout drift demonstration. A genuine emergency console fix must first be
    reflected in HCL before the next Terraform apply.

## Recovery rules

- Before stack deletion, a Retain-only update can be rolled back through a reviewed
  CloudFormation update. After deletion, the stack container and CloudFormation
  ownership are gone while physical resources remain. Do not recreate a stack or
  resource blindly; preserve IDs/templates and obtain a separate CloudFormation
  resource-import recovery design if ownership must be restored.
- If the HCP import apply fails, do not retry, run `terraform import`, use
  `terraform state rm`, or delete anything. Preserve the HCP run/state version,
  determine exactly which mappings reached state, refresh the live inventory, and
  prepare a new reviewed plan for only the unresolved discrepancy.
- A failed clean plan blocks template/import cleanup and the application output
  cutover. Restore the gate override to false, keep resources protected, and
  reconcile HCL to reality rather than masking drift.

## Submission map

| Assignment item | Evidence |
| --- | --- |
| Commit or merged PR replacing templates + Makefile + README + ADR | Final merged PR/commit after step 10 |
| VCS push/merge HCP **Apply finished** screenshot | Step 8, workspace/run/source visible |
| `terraform plan` immediately after migration ending in `No changes` | Step 9 terminal/HCP output and private clean-guard result |

Use [the evidence checklist](submission/lab7/README.md) for what may be retained
in Git. No raw plan, state, secret, or private workspace archive belongs here.
