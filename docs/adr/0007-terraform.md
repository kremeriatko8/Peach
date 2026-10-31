# ADR 0007: Manage Cognito, reporting and the agenda parser with Terraform (HCP)

Date: proposed 2026-10-27; adoption completed 2026-10-31
Status: Accepted (2026-11-01)

## Context

Cognito sign-in (Lab 4), weekly reporting (Lab 5) and the agenda parser (Lab 6)
were three CloudFormation stacks: `peach-auth` (5 resources), `peach-reports` (20)
and `peach-ai` (6). They hold data that can't be rebuilt: 4 user accounts with
passwords, the user pool and client IDs baked into the frontend and backend token
checks, report CSVs in S3, mailer dedup state in DynamoDB, queued work in SQS, and
the parser's function URL used by the frontend. Lab 7 asks for Terraform with
shared remote state, VCS-driven runs, and a migration that doesn't replace anything.

## Decision

One Terraform root module in `infra/`, state in HCP Terraform workspace
`ooad-kremeriatko8/peach-dev` (pinned by the `cloud` block in `infra/versions.tf`),
AWS provider pinned to 6.70.0. It manages the 31 former CloudFormation resources as
41 Terraform objects. Inline IAM policies, S3 sub-configurations and the like become
separate resources. Backend/Aurora, the migration runner, the frontend site, the
budget and the GitHub OIDC role stay in CloudFormation. Moving them is a separate
decision.

### Why Terraform, and not CloudFormation, CDK or OpenTofu

- **Terraform (chosen).** A pull request gets a full plan before anything changes,
  next to the code diff. `import` blocks let us adopt live resources without
  re-creating them, and the first plan proves it (41 to import, 0 to add, 0 to
  destroy). HCP gives shared state with locking and history, VCS-triggered runs,
  manual apply approval, and short-lived AWS credentials through OIDC. The provider
  covers everything here, including Cognito Managed Login branding. It's also what
  the course requires.
- **CloudFormation (kept for other stacks).** Change sets and automatic rollback are
  real advantages. But ownership is tied to a stack, there's no PR-native plan, and
  it doesn't meet the Lab 7 HCP workflow. Keeping both tools for the same resources
  isn't allowed (see "Who can change infrastructure").
- **CDK.** It synthesizes to CloudFormation, so it has the same stack ownership and
  rollback model, plus a TypeScript/Python toolchain. That's a lot of tooling for
  41 fairly static resources.
- **OpenTofu.** An open-source (MPL) fork with nearly the same language, and a
  reasonable future option. HCP Terraform workspaces run Terraform, not OpenTofu,
  and the lab specifies Terraform. Switching later would mean moving the state to
  a different backend, which is a separate migration.
- **Delete and rebuild.** Rejected: it would destroy user accounts, change pool and
  client IDs, and lose reports and dedup state.

### Imported, not re-created, and why that was safe

All 41 objects were imported. None was re-created. The sequence on 2026-10-31:

1. Diffed the live templates against the repo. The only differences were the
   Retain keys being added.
2. Deployed `DeletionPolicy: Retain` and `UpdateReplacePolicy: Retain` to all 31
   resources. The change sets showed only Modify, with no replacements, and
   `get-template` confirmed 5/5, 6/6 and 20/20.
3. Deleted the three stacks. Retained resources survive stack deletion. Afterwards,
   verified the user pool (4 users), the three Lambdas (Active) and the report
   bucket (objects intact).
4. Merged PR #2 and applied HCP run `run-LeywB4kQGLuosjZ6`: 41 imported, 0 added,
   4 changed, 0 destroyed.
5. Ran an immediate full plan: `No changes. Your infrastructure matches the
   configuration.` (`docs/lab7-final-plan.txt`).

Guardrails that made a wrong step visible before it could do damage:

- Every object has `prevent_destroy = true`.
- There's no `ignore_changes`.
- Import IDs were checked offline against a recorded inventory.
- An `adoption_inventory_complete` gate blocked plans until the stacks were gone
  (the `variables.tf` default stays `false` as a fail-safe).
- Every plan was reviewed by a human before apply.

The import blocks were removed afterwards. Removing an `import` block after the
import doesn't change anything, and the cleanup PR's plan is `No changes`.

### The four sensitivity-only updates during import

The import plan showed 4 to change, not 0:
`aws_cognito_identity_provider.google[0]`, `aws_iam_role_policy.mailer`,
`aws_lambda_function.builder` and `aws_lambda_function.mailer`. Each one
references a `sensitive` variable (Google client secret, report emails, database
URL, owner ID). Terraform 1.13 shows a newly sensitive attribute as Update even
when the value is identical.

Before and after values were identical in all three plans that showed them
(preview, PR and merge run). Terraform core makes no provider API call for these
updates. Only the state metadata changed. We accepted exactly these four for the
one adoption run. The post-adoption plan has no changes at all, so they don't
come back.

## Consequences

### Who can change infrastructure now, and how

- **Proposing:** anyone with repo access opens a PR that edits `infra/*.tf`. CI runs
  `terraform-check.yml` (fmt, validate, mocked plan tests, no cloud access), and HCP
  posts a speculative plan to the PR.
- **Applying:** merging to `main` queues a run in HCP. Auto-apply is off. A member of
  the HCP organization with apply permission on `peach-dev` (today, the project
  owner) reviews the plan and clicks Confirm & Apply.
- **AWS identity:** HCP gets short-lived credentials over OIDC.
  `peach-hcp-terraform-read` is trusted only for `run_phase:plan` and has read
  permissions. `peach-hcp-terraform-apply` is trusted only for `run_phase:apply`
  on `peach-dev`, with a write policy scoped to these 41 objects. It explicitly
  denies deleting the user pool, bucket or table, reading Cognito users, and
  reading or writing report objects (`bootstrap/hcp-apply-role/`). These two roles
  are bootstrap resources created by hand, outside this state.
- **Nobody else applies:** no Make target or workflow runs `terraform apply`.
  `make infra-plan` only makes speculative plans, which HCP never applies on a
  VCS-connected workspace.
- **Known gap:** the GitHub Actions deploy role (`infra/github-oidc.yaml`) still has
  `lambda:*` on every `peach-*` function and IAM write access on every `peach-*`
  role. That covers the Terraform-owned report and parser Lambdas and their roles.
  Today, only the workflow's content keeps CI away from them: it deploys only the
  backend. Follow-up: narrow that role to the backend and migration resources.
- **Console changes** (an emergency fix) are drift. The next plan shows them, and
  they must be written into HCL before the next apply, or the apply reverts them.

### Where secrets end up, including state

- **HCP workspace variables:** `google_client_secret`, `database_url`,
  `report_owner_sub`, `report_from_email` and `report_recipient_email`, all marked
  sensitive. They're write-only in the UI and never in `terraform.tfvars` or Git.
- **Terraform state and saved plans in HCP:** the same values in plain text inside
  the state file. HCP encrypts state at rest, but anyone who can read state or
  plan JSON can see them. Give state-read access in HCP team settings only to
  people who need it. CI uses `PEACH_TF_OUTPUTS_TOKEN` only to read the public auth
  outputs. That token should be a team token that can read outputs only, not a
  user token.
- **AWS itself:** the Cognito identity provider, Lambda environment variables and
  the mailer's IAM policy, where they always lived.
- **Outputs:** `docs/terraform-output-contract.json` lists the allowed output keys.
  `scripts/infra-outputs.py` rejects anything else and never prints errors from
  Terraform. Only public values (pool ID, client ID, URLs) reach frontend builds.
- **Never committed:** state, plan JSON and credentials.

### What happens if HCP Terraform is down

- **Running services are unaffected.** Terraform isn't in the request path, so
  Cognito, reporting and the parser keep working.
- **Infrastructure changes pause.** No plans or applies. We don't switch to a local
  backend or copy state out, because that would split ownership and skip locking.
- **Backend and frontend releases also pause.** Both read the Cognito outputs from
  HCP. A broken release can wait, or the previous image stays live.
- **Break-glass:** an urgent AWS fix may be made in the console with a written
  incident note. Afterwards, it gets reconciled into HCL and checked with a plan
  showing no changes.
- **If state is lost or corrupted:** restore a previous state version in HCP. AWS
  resources are never re-created just because the state lost track of them.

### Which runs first when a change needs both app CI and infra

**Infrastructure first.** Merge and apply the Terraform change, then merge the
application change that depends on it. The backend workflow deploys on every push
to `main`.

For changes that aren't backward compatible, split them up:
1. Add the new resource or setting.
2. Ship code that uses it.
3. Remove the old path in a later Terraform change.

The image digests for the report builder, mailer and parser are Terraform inputs,
so a new reporting or parser image ships as a Terraform change after the image is
pushed. GitHub Actions only deploys the backend Lambda. This way, two systems never
write the same resource.

### Other consequences

Terraform has no automatic rollback. A failed apply means looking at the actual
resources and state, fixing the HCL, and reviewing a new plan.

Future environments (stage, prod) get their own workspace and state, not extra
variables in `peach-dev`.

History of the adoption is in `docs/terraform-adoption-handover.md`,
`docs/terraform-sensitivity-metadata-review.md` and `docs/lab7-final-plan.txt`.
