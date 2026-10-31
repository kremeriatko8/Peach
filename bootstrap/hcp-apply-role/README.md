# HCP apply role for peach-dev (draft, not applied)

Lab 7 Part 1 Step 7: split HCP's AWS identity into a plan role and an apply role.
`peach-hcp-terraform-read` was created by hand in the console (see
`docs/terraform-hcp-setup.md`), so this stays a hand-run bootstrap with its own
files, outside the `infra/` root module and its state.

| File | Purpose |
| --- | --- |
| `plan-trust.json` | New trust for `peach-hcp-terraform-read`: `run_phase:plan` only |
| `apply-trust.json` | Trust for new `peach-hcp-terraform-apply`: `run_phase:apply` only |
| `apply-permissions.json` | Inline write policy scoped to the 41 objects in `infra/` |

The apply role also needs the same read policy the plan role already has, which
covers provider refresh. Copy it rather than re-deriving it (step 1).

## Commands (AWS admin identity, account 968053399627)

Step 0 is read-only. Steps 1–4 change IAM.

```bash
export AWS_PROFILE=<admin-profile>   # must resolve to 968053399627
aws sts get-caller-identity
cd bootstrap/hcp-apply-role

# 0. Inspect the current role. Save the trust policy so step 3 can be reverted.
aws iam get-role --role-name peach-hcp-terraform-read \
  --query Role.AssumeRolePolicyDocument > plan-trust.before.json
aws iam list-attached-role-policies --role-name peach-hcp-terraform-read
aws iam list-role-policies --role-name peach-hcp-terraform-read

# 1. Create the apply role.
aws iam create-role --role-name peach-hcp-terraform-apply \
  --assume-role-policy-document file://apply-trust.json \
  --max-session-duration 3600 \
  --description "HCP Terraform peach-dev apply phase" \
  --tags Key=PROJECT_NAME,Value=peach

# 2. Give it the same reads as the plan role. Repeat for every attached
#    managed policy ARN and inline policy listed in step 0.
aws iam attach-role-policy --role-name peach-hcp-terraform-apply \
  --policy-arn <read-policy-arn-from-step-0>
# Inline read policy instead? Copy it:
#   aws iam get-role-policy --role-name peach-hcp-terraform-read \
#     --policy-name <name> --query PolicyDocument > read-inline.json
#   aws iam put-role-policy --role-name peach-hcp-terraform-apply \
#     --policy-name <name> --policy-document file://read-inline.json

# 3. Add the scoped write policy.
aws iam put-role-policy --role-name peach-hcp-terraform-apply \
  --policy-name peach-infra-apply \
  --policy-document file://apply-permissions.json

# 4. Narrow the plan role to the plan phase. Do this only after step 1 succeeds.
aws iam update-assume-role-policy --role-name peach-hcp-terraform-read \
  --policy-document file://plan-trust.json
# Revert: --policy-document file://plan-trust.before.json

aws iam get-role --role-name peach-hcp-terraform-apply --query Role.Arn
```

## HCP workspace variables (peach-dev → Variables, category Environment)

| Key | Value | Action |
| --- | --- | --- |
| `TFC_AWS_PROVIDER_AUTH` | `true` | keep |
| `TFC_AWS_PLAN_ROLE_ARN` | `arn:aws:iam::968053399627:role/peach-hcp-terraform-read` | add |
| `TFC_AWS_APPLY_ROLE_ARN` | `arn:aws:iam::968053399627:role/peach-hcp-terraform-apply` | add |
| `TFC_AWS_RUN_ROLE_ARN` | (current read role) | delete after the two above are saved |

Verify with a plan-only run: it must still reach the same 41 imports / 4
sensitivity-only updates. An apply-phase credential check happens only on a real
apply, which needs its own approval.
